"""Backtest engine — event-replay of wallet trades against signal+risk pipeline.

Architecture:
  1. Fetch all WalletTrades for the given wallets+window from the Subgraph.
  2. Build a price timeline {asset_id: [(ts, price), ...]} from those fills.
  3. Replay trades chronologically: each fill is wrapped into a TradeEvent
     and fed to SignalEngine → lightweight risk check → BacktestExecutor.
  4. BacktestExecutor opens/closes positions using the price timeline
     (no live CLOB or Redis calls).
  5. Returns a BacktestResult with all positions + run metadata.
"""
from __future__ import annotations

import asyncio
import os
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

import yaml

from app.data.models import OrderSide, TradeEvent
from app.data.subgraph_client import SubgraphClient
from app.execution.base import Position
from app.signals.signal_engine import SignalEngine
from app.tracker.scoring import WalletScore, compute_score
from app.utils.logger import get_logger

log = get_logger(__name__)

_DEFAULT_CAPITAL_USD = 10_000.0
_SLIPPAGE = Decimal("0.003")


@dataclass
class BacktestResult:
    run_id: str
    strategy: str
    start_date: datetime
    end_date: datetime
    wallets: list[str]
    params: dict[str, Any]
    positions: list[Position] = field(default_factory=list)
    signals_total: int = 0
    signals_approved: int = 0
    signals_rejected: int = 0
    error: str = ""
    finished_at: datetime | None = None


class _PriceTimeline:
    """Fast nearest-price lookup from historical fills."""

    def __init__(self) -> None:
        self._data: dict[str, list[tuple[datetime, Decimal]]] = {}

    def add(self, asset_id: str, ts: datetime, price: Decimal) -> None:
        self._data.setdefault(asset_id, []).append((ts, price))

    def build(self) -> None:
        for k in self._data:
            self._data[k].sort(key=lambda x: x[0])

    def price_at(self, asset_id: str, ts: datetime) -> Decimal | None:
        """Nearest price at or before ts."""
        pts = self._data.get(asset_id)
        if not pts:
            return None
        lo, hi, result = 0, len(pts) - 1, None
        while lo <= hi:
            mid = (lo + hi) // 2
            if pts[mid][0] <= ts:
                result = pts[mid][1]
                lo = mid + 1
            else:
                hi = mid - 1
        return result

    def scan_forward(
        self,
        asset_id: str,
        fill_price: Decimal,
        entry_ts: datetime,
        tp_price: Decimal,
        sl_price: Decimal,
        side: str,
        deadline: datetime,
    ) -> tuple[str, Decimal, datetime]:
        """Walk forward from entry_ts; return (exit_reason, exit_price, exit_ts)."""
        pts = self._data.get(asset_id, [])
        for ts, price in pts:
            if ts <= entry_ts:
                continue
            if ts > deadline:
                break
            if side == "BUY":
                if price >= tp_price:
                    return "tp", price, ts
                if price <= sl_price:
                    return "sl", price, ts
            else:
                if price <= tp_price:
                    return "tp", price, ts
                if price >= sl_price:
                    return "sl", price, ts

        last = self.price_at(asset_id, deadline) or fill_price
        return "timeout", last, deadline


class BacktestExecutor:
    """Opens and closes positions using the price timeline (no live calls)."""

    def __init__(self, timeline: _PriceTimeline, capital_usd: float) -> None:
        self._timeline = timeline
        self.capital_usd = capital_usd

    def open_and_close(self, signal: Any) -> Position | None:
        entry_price = self._timeline.price_at(signal.asset_id, signal.timestamp)
        if entry_price is None:
            entry_price = signal.entry_price

        if signal.side == OrderSide.BUY:
            fill_price = entry_price * (1 + _SLIPPAGE)
        else:
            fill_price = entry_price * (1 - _SLIPPAGE)
        fill_price = min(Decimal("0.9999"), max(Decimal("0.0001"), fill_price))

        trade_usd = min(float(signal.size_pct), 0.05) * self.capital_usd
        trade_usd = max(trade_usd, 1.0)
        size_tokens = Decimal(str(trade_usd)) / fill_price

        if signal.side == OrderSide.BUY:
            tp_price = fill_price * Decimal(str(1 + signal.tp_pct))
            sl_price = fill_price * Decimal(str(1 - signal.sl_pct))
        else:
            tp_price = fill_price * Decimal(str(1 - signal.tp_pct))
            sl_price = fill_price * Decimal(str(1 + signal.sl_pct))

        deadline = signal.timestamp + timedelta(minutes=signal.max_holding_minutes)

        exit_reason, exit_price, exit_ts = self._timeline.scan_forward(
            asset_id=signal.asset_id,
            fill_price=fill_price,
            entry_ts=signal.timestamp,
            tp_price=tp_price,
            sl_price=sl_price,
            side=signal.side.value,
            deadline=deadline,
        )

        if signal.side == OrderSide.BUY:
            pnl = (exit_price - fill_price) * size_tokens
        else:
            pnl = (fill_price - exit_price) * size_tokens

        return Position(
            position_id=str(uuid.uuid4()),
            signal_id=signal.signal_id,
            strategy=signal.strategy,
            market_id=signal.market_id,
            asset_id=signal.asset_id,
            side=signal.side.value,
            entry_price=fill_price,
            size_usd=Decimal(str(round(trade_usd, 6))),
            size_tokens=size_tokens,
            tp_price=tp_price,
            sl_price=sl_price,
            max_holding_minutes=signal.max_holding_minutes,
            opened_at=signal.timestamp,
            closed_at=exit_ts,
            exit_price=exit_price,
            realized_pnl_usd=pnl,
            exit_reason=exit_reason,
        )


def _simple_risk_check(
    signal: Any,
    open_market_ids: set[str],
    max_open: int = 10,
) -> tuple[bool, str]:
    """Lightweight risk check that doesn't require Redis/KillSwitch."""
    if len(open_market_ids) >= max_open:
        return False, "max_open_positions"
    if signal.market_id in open_market_ids:
        return False, "position_already_open"
    if signal.confidence < 0.05:
        return False, f"low_confidence_{signal.confidence:.2f}"
    return True, ""


class BacktestEngine:
    def __init__(
        self,
        subgraph: SubgraphClient | None = None,
        strategies_yaml_path: str = "config/strategies.yaml",
    ) -> None:
        self._subgraph = subgraph or SubgraphClient()
        self._yaml_path = strategies_yaml_path

    async def run(
        self,
        strategy: str,
        start_date: datetime,
        end_date: datetime,
        wallets: list[str],
        params: dict[str, Any] | None = None,
        capital_usd: float = _DEFAULT_CAPITAL_USD,
        run_id: str | None = None,
    ) -> BacktestResult:
        run_id = run_id or str(uuid.uuid4())
        result = BacktestResult(
            run_id=run_id,
            strategy=strategy,
            start_date=start_date,
            end_date=end_date,
            wallets=wallets,
            params=params or {},
        )

        try:
            await self._execute(result, strategy, start_date, end_date, wallets, params or {}, capital_usd)
        except Exception as exc:
            log.error("backtest.error", run_id=run_id[:8], error=str(exc))
            result.error = str(exc)
        finally:
            result.finished_at = datetime.now(tz=timezone.utc)

        return result

    async def _execute(
        self,
        result: BacktestResult,
        strategy: str,
        start_date: datetime,
        end_date: datetime,
        wallets: list[str],
        params: dict[str, Any],
        capital_usd: float,
    ) -> None:
        # days_back must cover start_date relative to NOW (not end_date - start_date),
        # because the Subgraph query uses `now - days_back` as its lower timestamp bound.
        now = datetime.now(tz=timezone.utc)
        days_back = max(1, int((now - start_date).total_seconds() / 86400) + 2)

        log.info(
            "backtest.fetching_trades",
            wallets=len(wallets),
            days_back=days_back,
            strategy=strategy,
        )

        wallet_trades_list = await asyncio.gather(
            *[self._subgraph.get_wallet_trades(w, days_back=days_back) for w in wallets],
            return_exceptions=True,
        )

        timeline = _PriceTimeline()
        all_wallet_trades: list[tuple[str, Any]] = []

        for wallet, trades_or_exc in zip(wallets, wallet_trades_list):
            if isinstance(trades_or_exc, Exception):
                log.warning(
                    "backtest.wallet_fetch_error",
                    wallet=wallet[:10],
                    error=str(trades_or_exc)[:80],
                )
                continue
            for trade in trades_or_exc:
                ts = trade.opened_at
                if not (start_date <= ts <= end_date):
                    continue
                if trade.price > 0:
                    timeline.add(trade.market_id, ts, trade.price)
                all_wallet_trades.append((wallet, trade))

        timeline.build()
        all_wallet_trades.sort(key=lambda x: x[1].opened_at)
        log.info("backtest.trades_loaded", count=len(all_wallet_trades))

        # Compute scores once per wallet
        wallet_scores: dict[str, WalletScore | None] = {}
        for wallet, trades_or_exc in zip(wallets, wallet_trades_list):
            if isinstance(trades_or_exc, Exception):
                wallet_scores[wallet] = None
                continue
            wallet_scores[wallet] = compute_score(list(trades_or_exc), window_days=days_back)

        # Load strategy config, apply param overrides
        try:
            with open(self._yaml_path) as f:
                cfg: dict[str, Any] = yaml.safe_load(f) or {}
        except FileNotFoundError:
            cfg = {}

        if params:
            cfg.setdefault("strategies", {}).setdefault(strategy, {}).update(params)

        tmp_path = ""
        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as tmp:
                yaml.dump(cfg, tmp)
                tmp_path = tmp.name

            signal_engine = SignalEngine(strategies_yaml_path=tmp_path)
            executor = BacktestExecutor(timeline, capital_usd)

            # Track open market ids for lightweight risk check
            open_market_ids: set[str] = set()
            # Track which positions are "open" at each point in time
            active_positions: list[Position] = []

            for wallet, trade in all_wallet_trades:
                now = trade.opened_at

                # Close any positions whose deadline has passed
                still_open = []
                for pos in active_positions:
                    if pos.closed_at and pos.closed_at <= now:
                        open_market_ids.discard(pos.market_id)
                    else:
                        still_open.append(pos)
                active_positions = still_open

                event = TradeEvent(
                    id=trade.trade_id,
                    market_id=trade.market_id,
                    asset_id=trade.market_id,
                    outcome=trade.outcome,
                    side=trade.side,
                    price=trade.price,
                    size=trade.size_usd / max(trade.price, Decimal("0.0001")),
                    size_usd=trade.size_usd,
                    fee_usd=Decimal(0),
                    maker_address="",
                    taker_address=wallet,
                    timestamp=trade.opened_at,
                    tx_hash=trade.trade_id,
                )

                score = wallet_scores.get(wallet)
                signals = signal_engine.process_event(event, score)

                for sig in signals:
                    if sig.strategy != strategy:
                        continue

                    result.signals_total += 1
                    approved, reject_reason = _simple_risk_check(sig, open_market_ids)
                    if not approved:
                        result.signals_rejected += 1
                        continue

                    result.signals_approved += 1
                    position = executor.open_and_close(sig)
                    if position:
                        result.positions.append(position)
                        open_market_ids.add(sig.market_id)
                        active_positions.append(position)

        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

        log.info(
            "backtest.done",
            run_id=result.run_id[:8],
            signals=result.signals_total,
            approved=result.signals_approved,
            positions=len(result.positions),
        )
