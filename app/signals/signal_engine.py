"""Signal engine — orchestrates all strategies and routes signals.

Consumes TrackedTrade events (from Redis Stream `tracked_trades`) and
produces Signal objects that are published to Stream `signals`.

Strategies run in sequence; any can emit a signal for a given event.
Deduplication: at most one signal per (market_id, side) in any 5-minute window.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

import yaml

from app.data.models import TradeEvent
from app.signals.models import Signal
from app.signals.strategies import consensus, momentum_odds, whale_copy
from app.tracker.scoring import WalletScore
from app.utils.logger import get_logger

log = get_logger(__name__)

_DEDUP_WINDOW_MINUTES = 5


class SignalEngine:
    """Runs all enabled strategies against incoming trade events."""

    def __init__(self, strategies_yaml_path: str = "config/strategies.yaml") -> None:
        self._config_path = strategies_yaml_path
        self._config: dict[str, Any] = {}
        self._reload_config()

        # Strategy state objects (maintain rolling windows)
        self._consensus = consensus.ConsensusAccumulator()
        self._momentum = momentum_odds.MomentumOddsAccumulator()

        # Dedup: (market_id, side) → last signal timestamp
        self._recent_signals: dict[tuple, datetime] = defaultdict(
            lambda: datetime.min.replace(tzinfo=timezone.utc)
        )

        # Current open market ids (set externally by execution layer)
        self.open_market_ids: set[str] = set()

    def _reload_config(self) -> None:
        try:
            with open(self._config_path) as f:
                self._config = yaml.safe_load(f) or {}
        except FileNotFoundError:
            log.warning("signal_engine.config_not_found", path=self._config_path)
            self._config = {}

    @property
    def _strategies_cfg(self) -> dict[str, Any]:
        return self._config.get("strategies", {})

    def process_event(
        self,
        event: TradeEvent,
        wallet_score: WalletScore | None,
    ) -> list[Signal]:
        """Process one trade event; return any generated signals."""
        signals: list[Signal] = []

        # 1. Whale copy
        sig = whale_copy.evaluate(
            event,
            wallet_score,
            self._strategies_cfg.get("whale_copy", {}),
            self.open_market_ids,
        )
        if sig:
            signals.append(sig)

        # 2. Consensus
        sig = self._consensus.on_event(
            event,
            wallet_score,
            self._strategies_cfg.get("consensus", {}),
            self.open_market_ids,
        )
        if sig:
            signals.append(sig)

        # 3. Momentum odds
        sig = self._momentum.on_event(
            event,
            wallet_score,
            self._strategies_cfg.get("momentum_odds", {}),
            self.open_market_ids,
        )
        if sig:
            signals.append(sig)

        # Deduplicate signals per (market, side) within window
        deduped: list[Signal] = []
        now = datetime.now(tz=timezone.utc)
        for s in signals:
            key = (s.market_id, s.side.value)
            last = self._recent_signals[key]
            if now - last < timedelta(minutes=_DEDUP_WINDOW_MINUTES):
                log.debug(
                    "signal_engine.dedup",
                    strategy=s.strategy,
                    market=s.market_id[:10],
                )
                continue
            self._recent_signals[key] = now
            deduped.append(s)

        return deduped
