"""On-chain reconciliation — compares open positions in DB against CLOB state.

Runs every N minutes (configurable) and alerts on mismatches:
  - Position in DB as 'open' but no matching CLOB order/token balance
  - CLOB order exists but no DB record (orphan)
  - Significant price deviation between DB entry_price and current price

Only active in EXECUTION_MODE=live. In paper mode this is a no-op.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import select

from app.storage.db import AsyncSessionFactory
from app.storage import models as orm
from app.utils.logger import get_logger

if TYPE_CHECKING:
    from app.execution.live_executor import LiveExecutor
    from app.utils.alerting import Alerter

log = get_logger(__name__)

_PRICE_DEVIATION_ALERT_PCT = 0.10  # alert if current price >10% away from entry


class Reconciler:
    """Periodically reconciles DB positions against live CLOB state."""

    def __init__(
        self,
        executor: "LiveExecutor",
        alerter: "Alerter",
        interval_seconds: int = 300,
    ) -> None:
        self._executor = executor
        self._alerter = alerter
        self._interval = interval_seconds

    async def run_forever(self) -> None:
        log.info("reconciler.started", interval_s=self._interval)
        while True:
            try:
                await asyncio.sleep(self._interval)
                await self.reconcile_once()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                log.error("reconciler.error", error=str(exc)[:120])
                await asyncio.sleep(30)

    async def reconcile_once(self) -> list[str]:
        """Run one reconciliation pass. Returns list of issue descriptions."""
        issues: list[str] = []

        # 1. Fetch open positions from DB
        async with AsyncSessionFactory() as session:
            result = await session.execute(
                select(orm.Position).where(orm.Position.closed_at.is_(None))
            )
            db_positions = result.scalars().all()

        if not db_positions:
            log.debug("reconciler.no_open_positions")
            return issues

        # 2. Fetch open orders from CLOB
        open_orders = await self._executor.get_open_orders()
        clob_order_ids = {o.get("id") or o.get("order_id", "") for o in open_orders}

        for pos in db_positions:
            position_issues = await self._check_position(pos, clob_order_ids)
            issues.extend(position_issues)

        # 3. Detect orphan CLOB orders (orders not in any DB position)
        db_order_ids = {
            pos.order_id for pos in db_positions
            if hasattr(pos, "order_id") and pos.order_id
        }
        orphan_ids = clob_order_ids - db_order_ids - {""}
        for oid in orphan_ids:
            msg = f"Orphan CLOB order with no DB record: {oid[:12]}"
            issues.append(msg)
            log.warning("reconciler.orphan_order", order_id=oid[:12])

        if issues:
            summary = "\n".join(f"• {i}" for i in issues[:20])
            log.warning("reconciler.mismatches_found", count=len(issues))
            await self._alerter.reconciliation_mismatch(summary)
        else:
            log.info("reconciler.ok", positions_checked=len(db_positions))

        return issues

    async def _check_position(self, pos: orm.Position, clob_order_ids: set[str]) -> list[str]:
        issues: list[str] = []
        pid = pos.position_id[:8]

        # Check if the CLOB order is still open (may have been filled and order closed)
        order_id = getattr(pos, "order_id", None)
        if order_id and order_id not in clob_order_ids:
            # This is expected once an order is filled — only flag if very recent
            age_minutes = (datetime.now(tz=timezone.utc) - pos.opened_at).total_seconds() / 60
            if age_minutes < 5:
                issues.append(f"Position {pid}: CLOB order {order_id[:12]} not found (age={age_minutes:.1f}min)")

        # Check current price vs entry price
        current_price = await self._executor.get_current_price(pos.asset_id)
        if current_price is not None:
            entry = float(pos.entry_price)
            deviation = abs(float(current_price) - entry) / entry if entry > 0 else 0
            if deviation > _PRICE_DEVIATION_ALERT_PCT:
                issues.append(
                    f"Position {pid}: price moved {deviation:.1%} from entry "
                    f"(entry={entry:.4f}, now={float(current_price):.4f})"
                )

        # Check age vs max_holding_minutes
        age_minutes = (datetime.now(tz=timezone.utc) - pos.opened_at).total_seconds() / 60
        if age_minutes > pos.max_holding_minutes * 1.5:
            issues.append(
                f"Position {pid}: stale position — open for {age_minutes:.0f}min, "
                f"max_holding={pos.max_holding_minutes}min"
            )

        return issues
