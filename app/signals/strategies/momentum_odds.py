"""Momentum-odds strategy — odds moved >= X% in last N minutes + whale confirms.

Signal trigger:
  - the current trade price differs from the price N minutes ago by >= min_odds_move_pct
  - if require_whale_confirmation: the triggering wallet qualifies as a whale
    (trade size >= 1000 USD)

The strategy tracks recent prices per asset_id in a rolling window.
"""
from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from app.data.models import OrderSide, TradeEvent
from app.signals.confidence import compute_confidence
from app.signals.models import Signal
from app.tracker.scoring import WalletScore
from app.utils.logger import get_logger

log = get_logger(__name__)


class MomentumOddsAccumulator:
    """Tracks price history per asset and detects momentum moves."""

    def __init__(self) -> None:
        # asset_id → list of (timestamp, price, size_usd)
        self._prices: dict[str, list[dict]] = defaultdict(list)

    def on_event(
        self,
        event: TradeEvent,
        wallet_score: WalletScore | None,
        config: dict[str, Any],
        open_market_ids: set[str],
    ) -> Signal | None:
        if not config.get("enabled", True):
            return None

        min_move_pct = float(config.get("min_odds_move_pct", 5)) / 100.0
        window_min = float(config.get("odds_window_minutes", 30))
        require_whale = bool(config.get("require_whale_confirmation", True))
        max_holding = int(config.get("max_holding_minutes", 60))
        weight = float(config.get("confidence_weight", 0.30))
        size_pct = float(config.get("position_size_pct", 0.015))
        tp_pct = float(config.get("tp_pct", 0.10))
        sl_pct = float(config.get("sl_pct", 0.05))

        if event.market_id in open_market_ids:
            return None

        # Whale check
        if require_whale and float(event.size_usd) < 1000:
            return None

        now = datetime.now(tz=timezone.utc)
        cutoff = now - timedelta(minutes=window_min)
        aid = event.asset_id

        self._prices[aid].append({
            "ts": event.timestamp,
            "price": float(event.price),
            "size_usd": float(event.size_usd),
        })
        # Prune old
        self._prices[aid] = [p for p in self._prices[aid] if p["ts"] >= cutoff]

        history = self._prices[aid]
        if len(history) < 2:
            return None

        oldest_price = history[0]["price"]
        current_price = float(event.price)
        if oldest_price <= 0:
            return None

        move = (current_price - oldest_price) / oldest_price
        if abs(move) < min_move_pct:
            return None

        # Direction: if price moved UP → buy (momentum continuation)
        # if price moved DOWN → sell (fade is fade_late; here we follow)
        side = OrderSide.BUY if move > 0 else OrderSide.SELL

        confidence = compute_confidence(wallet_score, weight)
        # Boost confidence by momentum magnitude (up to 30% boost)
        momentum_boost = min(0.3, abs(move) * 2)
        confidence = min(1.0, confidence * (1 + momentum_boost))

        if confidence < 0.10:
            return None

        sig = Signal(
            signal_id=str(uuid.uuid4()),
            strategy="momentum_odds",
            market_id=event.market_id,
            asset_id=aid,
            side=side,
            confidence=confidence,
            entry_price=event.price,
            size_pct=size_pct,
            tp_pct=tp_pct,
            sl_pct=sl_pct,
            max_holding_minutes=max_holding,
            source_wallet=event.taker_address,
            timestamp=now,
            reason=(
                f"Momentum: odds moved {move:+.1%} in {window_min}min "
                f"({oldest_price:.3f} → {current_price:.3f}), "
                f"whale ${float(event.size_usd):.0f} confirmed "
                f"(confidence={confidence:.2f})"
            ),
        )
        log.info(
            "momentum_odds.signal",
            signal_id=sig.signal_id[:8],
            market=event.market_id[:10],
            move_pct=f"{move:+.1%}",
            confidence=f"{confidence:.2f}",
        )
        return sig
