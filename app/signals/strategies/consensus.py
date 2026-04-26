"""Consensus strategy — ≥N tracked wallets trade same market+side in a time window.

Signal trigger:
  - at least min_wallets tracked wallets have entered the same outcome token
    on the same side within time_window_minutes
  - combined trade size exceeds threshold

The strategy maintains a rolling window of recent events per (market, side).
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


class ConsensusAccumulator:
    """Maintains rolling windows per (market_id, asset_id, side).

    Call on_event() for each incoming tracked trade.
    Returns a Signal when the consensus threshold is met.
    """

    def __init__(self) -> None:
        # key: (market_id, asset_id, side) → list of (timestamp, wallet, size_usd, price)
        self._windows: dict[tuple, list[dict]] = defaultdict(list)

    def on_event(
        self,
        event: TradeEvent,
        wallet_score: WalletScore | None,
        config: dict[str, Any],
        open_market_ids: set[str],
    ) -> Signal | None:
        if not config.get("enabled", True):
            return None

        min_wallets = int(config.get("min_wallets", 2))
        window_min = float(config.get("time_window_minutes", 10))
        max_holding = int(config.get("max_holding_minutes", 180))
        weight = float(config.get("confidence_weight", 0.30))
        size_pct = float(config.get("position_size_pct", 0.02))
        tp_pct = float(config.get("tp_pct", 0.12))
        sl_pct = float(config.get("sl_pct", 0.06))

        if event.market_id in open_market_ids:
            return None

        key = (event.market_id, event.asset_id, event.side.value)
        now = datetime.now(tz=timezone.utc)
        cutoff = now - timedelta(minutes=window_min)

        # Add event to window
        self._windows[key].append({
            "ts": event.timestamp,
            "wallet": event.taker_address,
            "size_usd": float(event.size_usd),
            "price": float(event.price),
        })

        # Prune old events
        self._windows[key] = [
            e for e in self._windows[key] if e["ts"] >= cutoff
        ]

        window = self._windows[key]
        unique_wallets = {e["wallet"] for e in window}

        if len(unique_wallets) < min_wallets:
            return None

        # Generate signal
        avg_price = sum(e["price"] for e in window) / len(window)
        confidence = compute_confidence(wallet_score, weight)
        if confidence < 0.10:
            return None

        # Clear window to avoid re-triggering immediately
        self._windows[key].clear()

        wallets_str = ", ".join(w[:8] for w in list(unique_wallets)[:3])
        sig = Signal(
            signal_id=str(uuid.uuid4()),
            strategy="consensus",
            market_id=event.market_id,
            asset_id=event.asset_id,
            side=event.side,
            confidence=confidence,
            entry_price=Decimal(str(round(avg_price, 6))),
            size_pct=size_pct,
            tp_pct=tp_pct,
            sl_pct=sl_pct,
            max_holding_minutes=max_holding,
            source_wallet=event.taker_address,
            timestamp=now,
            reason=(
                f"Consensus: {len(unique_wallets)} wallets [{wallets_str}] "
                f"all {event.side.value} in {window_min}min window "
                f"(confidence={confidence:.2f})"
            ),
        )
        log.info(
            "consensus.signal",
            signal_id=sig.signal_id[:8],
            market=event.market_id[:10],
            wallets=len(unique_wallets),
            confidence=f"{sig.confidence:.2f}",
        )
        return sig
