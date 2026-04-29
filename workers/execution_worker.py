"""Execution worker — consumes signals stream, validates with risk manager, executes.

Redis Stream layout:
  consumed:  signals    (group: execution_workers)
  published: positions  (new/updated position JSON)

Also runs the exit manager and (in live mode) the reconciler as background tasks.

Fase 4 additions:
  - Selects PaperExecutor or LiveExecutor based on EXECUTION_MODE
  - KellySizer adjusts position size dynamically
  - CircuitBreaker monitors consecutive losses
  - Alerter sends Discord/Telegram notifications on fills, closes, and errors
  - Reconciler (live only) verifies DB positions against on-chain state every 5min
"""
from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import redis.asyncio as aioredis

from app.config import ExecutionMode, get_settings
from app.data.models import OrderSide
from app.data.polymarket_rest import PolymarketRestClient
from app.execution.base import BaseExecutor
from app.execution.circuit_breaker import CircuitBreaker
from app.execution.exit_manager import ExitManager
from app.execution.kelly import KellySizer
from app.execution.paper_executor import PaperExecutor
from app.risk.kill_switch import KillSwitch
from app.risk.risk_manager import RiskManager
from app.signals.models import Signal, SignalStatus
from app.storage.db import AsyncSessionFactory
from app.storage import models as orm
from app.utils.alerting import Alerter
from app.utils.logger import configure_logging, get_logger

log = get_logger(__name__)

_STREAM_IN = "signals"
_STREAM_POSITIONS = "positions"
_GROUP = "execution_workers"
_CONSUMER = "execution_worker_1"
_BATCH_SIZE = 50
_BLOCK_MS = 1000


class ExecutionWorker:
    def __init__(self) -> None:
        self._s = get_settings()
        self._r: aioredis.Redis | None = None
        self._rest = PolymarketRestClient(self._s)

    async def start(self) -> None:
        self._r = aioredis.from_url(self._s.redis_url, decode_responses=False)
        ks = KillSwitch(self._r)
        alerter = Alerter(self._s)

        # Select executor based on EXECUTION_MODE
        executor = await self._build_executor(alerter)

        risk = RiskManager(ks)
        risk.capital_usd = self._s.initial_capital_usd

        kelly = KellySizer(
            kelly_fraction=self._s.kelly_fraction,
            min_pct=self._s.kelly_min_pct,
            max_pct=self._s.kelly_max_pct,
        )

        circuit = CircuitBreaker(
            kill_switch=ks,
            alerter=alerter,
            max_consecutive_losses=self._s.circuit_breaker_max_consecutive,
            threshold_sigma=self._s.circuit_breaker_sigma,
        )

        async def on_position_closed(position) -> None:
            await self._on_position_closed(position)
            kelly.record(position)
            await circuit.record(position)
            await alerter.closed(
                position.position_id,
                position.exit_reason,
                float(position.realized_pnl_usd or 0),
            )
            # Persist circuit breaker state so API can read it
            assert self._r is not None
            await self._r.set(
                "copytrader:circuit_breaker:consecutive",
                circuit.consecutive_losses,
                ex=86400,
            )

        exit_mgr = ExitManager(
            executor=executor,
            kill_switch=ks,
            rest_client=self._rest,
            on_close=on_position_closed,
        )

        # Create consumer group — use id="0" so a fresh worker always processes
        # all signals from the beginning of the stream.  On restart the group
        # already exists (BUSYGROUP), so the exception is silently ignored and
        # the existing position (where we left off) is preserved.
        try:
            await self._r.xgroup_create(_STREAM_IN, _GROUP, id="0", mkstream=True)
        except aioredis.ResponseError:
            pass

        log.info("execution_worker.started", mode=self._s.execution_mode.value)

        # Background tasks
        asyncio.create_task(exit_mgr.run_forever())

        if self._s.execution_mode == ExecutionMode.live:
            from app.execution.live_executor import LiveExecutor
            from app.execution.reconciliation import Reconciler
            if isinstance(executor, LiveExecutor):
                reconciler = Reconciler(
                    executor=executor,
                    alerter=alerter,
                    interval_seconds=self._s.reconciliation_interval_seconds,
                )
                asyncio.create_task(reconciler.run_forever())

        # Main loop
        while True:
            try:
                messages = await self._r.xreadgroup(
                    _GROUP, _CONSUMER,
                    streams={_STREAM_IN: ">"},
                    count=_BATCH_SIZE,
                    block=_BLOCK_MS,
                )
                if not messages:
                    continue

                for _stream, entries in messages:
                    for msg_id, fields in entries:
                        await self._process_signal(
                            msg_id, fields, risk, executor, exit_mgr, kelly, alerter
                        )
                        await self._r.xack(_STREAM_IN, _GROUP, msg_id)

            except asyncio.CancelledError:
                await alerter.close()
                break
            except Exception as exc:
                log.error("execution_worker.error", error=str(exc))
                await asyncio.sleep(1)

    async def _build_executor(self, alerter: Alerter) -> BaseExecutor:
        if self._s.execution_mode == ExecutionMode.live:
            try:
                from app.execution.live_executor import LiveExecutor
                executor = await LiveExecutor.create()
                log.info("execution_worker.live_mode_active")
                return executor
            except Exception as exc:
                msg = f"LiveExecutor init failed: {exc}"
                log.error("execution_worker.live_init_failed", error=str(exc))
                await alerter.error("live_executor", msg)
                raise
        return PaperExecutor(self._rest)

    async def _process_signal(
        self,
        msg_id: bytes,
        fields: dict,
        risk: RiskManager,
        executor: BaseExecutor,
        exit_mgr: ExitManager,
        kelly: KellySizer,
        alerter: Alerter,
    ) -> None:
        try:
            data = json.loads(fields.get(b"data", b"{}"))
        except Exception:
            return

        sig = _dict_to_signal(data)
        if sig is None:
            return

        # Provide current open market ids to risk manager
        risk.open_positions = {
            pid: {"market_id": p.market_id}
            for pid, p in exit_mgr.positions.items()
        }

        decision = await risk.validate(sig, market=None, orderbook=None)

        # Persist signal to DB
        await self._persist_signal(sig, decision.approved, decision.reason)

        if not decision.approved:
            log.info(
                "execution_worker.signal_rejected",
                signal_id=sig.signal_id[:8],
                reason=decision.reason,
            )
            return

        # Apply Kelly sizing: override signal.size_pct
        kelly_pct = kelly.size_pct(sig.size_pct)
        if kelly_pct != sig.size_pct:
            from dataclasses import replace as dc_replace
            sig = dc_replace(sig, size_pct=kelly_pct)
            log.debug(
                "execution_worker.kelly_applied",
                signal_id=sig.signal_id[:8],
                size_pct=round(kelly_pct, 4),
                kelly_samples=kelly.sample_count,
            )

        # In live mode: refresh and cache USDC balance before each trade
        usdc_balance: float | None = None
        if self._s.execution_mode == ExecutionMode.live:
            from app.execution.live_executor import LiveExecutor
            if isinstance(executor, LiveExecutor):
                try:
                    usdc_balance = await executor.get_usdc_balance()
                    assert self._r is not None
                    await self._r.set("copytrader:live:usdc_balance", usdc_balance, ex=300)
                except Exception:
                    pass

        # Balance guard: reject if effective balance < position size
        position_size_usd = float(sig.size_pct) * float(risk.capital_usd)
        if self._s.execution_mode == ExecutionMode.live:
            if usdc_balance is not None and usdc_balance < position_size_usd:
                log.warning(
                    "execution_worker.insufficient_balance",
                    signal_id=sig.signal_id[:8],
                    usdc_balance=round(usdc_balance, 2),
                    position_size_usd=round(position_size_usd, 2),
                )
                return
        else:
            # Paper mode: estimate simulated balance from Redis-cached PnL metrics
            try:
                assert self._r is not None
                pnl_raw = await self._r.get("copytrader:paper:realized_pnl")
                exposure_raw = await self._r.get("copytrader:paper:open_exposure")
                realized_pnl = float(pnl_raw) if pnl_raw else 0.0
                open_exposure = float(exposure_raw) if exposure_raw else 0.0
                simulated_balance = float(risk.capital_usd) + realized_pnl - open_exposure
                if simulated_balance < position_size_usd:
                    log.warning(
                        "execution_worker.insufficient_simulated_balance",
                        signal_id=sig.signal_id[:8],
                        simulated_balance=round(simulated_balance, 2),
                        position_size_usd=round(position_size_usd, 2),
                    )
                    return
            except Exception:
                pass  # If we can't read balance, allow the trade

        # Open position
        try:
            position = await executor.open_position(sig, risk.capital_usd)
        except Exception as exc:
            log.error("execution_worker.open_position_failed", signal_id=sig.signal_id[:8], error=str(exc)[:120])
            await alerter.error("open_position", str(exc)[:200])
            return

        exit_mgr.positions[position.position_id] = position

        # Persist position
        await self._persist_position(position)

        # Notify
        assert self._r is not None
        await self._r.xadd(
            _STREAM_POSITIONS,
            {"data": json.dumps(_position_to_dict(position, "opened"))},
        )
        await alerter.fill(
            position.position_id,
            sig.market_question or sig.market_id,
            position.side,
            float(position.entry_price),
            float(position.size_usd),
        )

    async def _on_position_closed(self, position) -> None:
        await self._persist_position(position, update=True)
        assert self._r is not None
        await self._r.xadd(
            _STREAM_POSITIONS,
            {"data": json.dumps(_position_to_dict(position, "closed"))},
        )

    async def _persist_signal(self, sig: Signal, approved: bool, reason: str) -> None:
        status = "approved" if approved else "rejected"
        try:
            async with AsyncSessionFactory() as session:
                record = orm.Signal(
                    signal_id=sig.signal_id,
                    strategy=sig.strategy,
                    market_id=sig.market_id,
                    asset_id=sig.asset_id,
                    side=sig.side.value,
                    confidence=Decimal(str(sig.confidence)),
                    entry_price=sig.entry_price,
                    size_pct=Decimal(str(sig.size_pct)),
                    tp_pct=Decimal(str(sig.tp_pct)),
                    sl_pct=Decimal(str(sig.sl_pct)),
                    max_holding_minutes=sig.max_holding_minutes,
                    source_wallet=sig.source_wallet,
                    status=status,
                    reject_reason="" if approved else reason,
                    reason=sig.reason,
                    market_question=sig.market_question,
                )
                session.add(record)
                await session.commit()
        except Exception as exc:
            log.warning("execution_worker.persist_signal_failed", error=str(exc)[:80])

    async def _persist_position(self, position, update: bool = False) -> None:
        try:
            async with AsyncSessionFactory() as session:
                if update:
                    record = await session.get(orm.Position, position.position_id)
                    if record:
                        record.closed_at = position.closed_at
                        record.exit_price = position.exit_price
                        record.realized_pnl_usd = position.realized_pnl_usd
                        record.exit_reason = position.exit_reason
                        await session.commit()
                        return
                record = orm.Position(
                    position_id=position.position_id,
                    signal_id=position.signal_id,
                    strategy=position.strategy,
                    market_id=position.market_id,
                    asset_id=position.asset_id,
                    side=position.side,
                    entry_price=position.entry_price,
                    size_usd=position.size_usd,
                    size_tokens=position.size_tokens,
                    tp_price=position.tp_price,
                    sl_price=position.sl_price,
                    max_holding_minutes=position.max_holding_minutes,
                    opened_at=position.opened_at,
                    closed_at=position.closed_at,
                    exit_price=position.exit_price,
                    realized_pnl_usd=position.realized_pnl_usd,
                    exit_reason=position.exit_reason,
                    execution_mode=self._s.execution_mode.value,
                    order_id=getattr(position, "order_id", None),
                )
                session.add(record)
                await session.commit()
        except Exception as exc:
            log.warning("execution_worker.persist_position_failed", error=str(exc)[:80])


def _dict_to_signal(data: dict) -> Signal | None:
    try:
        return Signal(
            signal_id=data["signal_id"],
            strategy=data["strategy"],
            market_id=data["market_id"],
            asset_id=data["asset_id"],
            side=OrderSide(data["side"]),
            confidence=float(data["confidence"]),
            entry_price=Decimal(str(data["entry_price"])),
            size_pct=float(data["size_pct"]),
            tp_pct=float(data["tp_pct"]),
            sl_pct=float(data["sl_pct"]),
            max_holding_minutes=int(data["max_holding_minutes"]),
            source_wallet=data["source_wallet"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            reason=data.get("reason", ""),
            market_question=data.get("market_question", ""),
        )
    except Exception as exc:
        log.warning("execution_worker.parse_signal_failed", error=str(exc)[:80])
        return None


def _position_to_dict(position, event: str) -> dict:
    return {
        "event": event,
        "position_id": position.position_id,
        "strategy": position.strategy,
        "market_id": position.market_id,
        "side": position.side,
        "entry_price": str(position.entry_price),
        "size_usd": str(position.size_usd),
        "tp_price": str(position.tp_price),
        "sl_price": str(position.sl_price),
        "max_holding_minutes": position.max_holding_minutes,
        "opened_at": position.opened_at.isoformat(),
        "closed_at": position.closed_at.isoformat() if position.closed_at else None,
        "exit_price": str(position.exit_price) if position.exit_price else None,
        "realized_pnl_usd": str(position.realized_pnl_usd) if position.realized_pnl_usd else None,
        "exit_reason": position.exit_reason,
        "order_id": getattr(position, "order_id", None),
    }


async def main() -> None:
    configure_logging()
    worker = ExecutionWorker()
    await worker.start()


if __name__ == "__main__":
    asyncio.run(main())
