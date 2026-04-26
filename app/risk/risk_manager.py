"""Risk manager — validates signals before execution.

Checks:
  1. Kill switch active → reject all
  2. Max open positions
  3. Max % per trade
  4. Max exposure per market
  5. Daily drawdown kill switch
  6. Min market liquidity
  7. Min time to resolution (don't enter if market resolves soon)
  8. Sufficient orderbook depth to exit
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import yaml

from app.data.models import Market, OrderBook
from app.risk.kill_switch import KillSwitch
from app.signals.models import Signal, SignalStatus
from app.utils.logger import get_logger

log = get_logger(__name__)


@dataclass
class RiskDecision:
    approved: bool
    reason: str
    signal: Signal

    def with_status(self) -> Signal:
        from dataclasses import replace

        return replace(
            self.signal,
            status=SignalStatus.APPROVED if self.approved else SignalStatus.REJECTED,
            reject_reason="" if self.approved else self.reason,
        )


class RiskManager:
    def __init__(
        self,
        kill_switch: KillSwitch,
        strategies_yaml_path: str = "config/strategies.yaml",
    ) -> None:
        self._ks = kill_switch
        self._config_path = strategies_yaml_path
        self._config: dict[str, Any] = {}
        self._reload_config()

        # Runtime state (set by execution layer)
        self.open_positions: dict[str, Any] = {}  # position_id → position
        self.capital_usd: float = 1000.0
        self.daily_pnl_usd: float = 0.0
        self.daily_pnl_start: datetime = datetime.now(tz=timezone.utc)

    def _reload_config(self) -> None:
        try:
            with open(self._config_path) as f:
                self._config = yaml.safe_load(f) or {}
        except FileNotFoundError:
            self._config = {}

    @property
    def _risk_cfg(self) -> dict[str, Any]:
        return self._config.get("risk", {})

    async def validate(
        self,
        signal: Signal,
        market: Market | None,
        orderbook: OrderBook | None,
    ) -> RiskDecision:
        """Validate a signal and return an approval/rejection decision."""

        # 1. Kill switch
        if await self._ks.is_active():
            return RiskDecision(False, "kill_switch_active", signal)

        # 2. Daily drawdown kill switch
        max_dd_daily = float(self._risk_cfg.get("max_drawdown_daily", 0.05))
        dd_pct = -self.daily_pnl_usd / max(self.capital_usd, 1.0)
        if dd_pct > max_dd_daily:
            await self._ks.activate(f"daily drawdown {dd_pct:.1%} exceeded {max_dd_daily:.1%}")
            return RiskDecision(False, f"daily_drawdown_{dd_pct:.1%}", signal)

        # 3. Max open positions
        max_open = int(self._risk_cfg.get("max_open_positions", 10))
        if len(self.open_positions) >= max_open:
            return RiskDecision(False, f"max_open_positions_{max_open}", signal)

        # 4. Position already open in this market
        if signal.market_id in {p.get("market_id") for p in self.open_positions.values()}:
            return RiskDecision(False, "position_already_open", signal)

        # 5. Market checks
        if market is not None:
            now = datetime.now(tz=timezone.utc)

            # Min liquidity
            min_liq = float(self._risk_cfg.get("min_liquidity_usd", 5000))
            if market.liquidity_usd is not None and float(market.liquidity_usd) < min_liq:
                return RiskDecision(False, f"liquidity_{float(market.liquidity_usd):.0f}<{min_liq}", signal)

            # Time to resolution
            min_buffer = float(self._risk_cfg.get("min_time_to_resolution_buffer_minutes", 30))
            ttm = market.time_to_resolution_minutes(now)
            max_hold = signal.max_holding_minutes
            if ttm is not None and ttm < max_hold + min_buffer:
                return RiskDecision(
                    False,
                    f"ttm_{ttm:.0f}min<hold_{max_hold}+buf_{min_buffer:.0f}",
                    signal,
                )

        # 6. Orderbook depth check
        if orderbook is not None:
            min_depth = float(self._risk_cfg.get("min_market_depth_usd", 500))
            depth = float(orderbook.depth_usd(side="ask" if signal.side.value == "BUY" else "bid"))
            if depth < min_depth:
                return RiskDecision(False, f"depth_{depth:.0f}<{min_depth}", signal)

        # 7. Max % per trade
        max_pct = float(self._risk_cfg.get("max_pct_per_trade", 0.02))
        actual_pct = min(signal.size_pct, max_pct)
        trade_usd = actual_pct * self.capital_usd
        if trade_usd < 1.0:
            return RiskDecision(False, "trade_size_too_small", signal)

        log.info(
            "risk.approved",
            signal_id=signal.signal_id[:8],
            strategy=signal.strategy,
            market=signal.market_id[:10],
            trade_usd=f"{trade_usd:.2f}",
            confidence=f"{signal.confidence:.2f}",
        )
        return RiskDecision(True, "ok", signal)
