"""Whale-copy strategy — follow large entries from high-quality wallets.

Signal trigger:
  - trade_size >= min_trade_size_usd
  - wallet score passes min_wallet_sharpe and max_wallet_median_holding_minutes
  - no existing open position in the same market+side

Produces one signal per qualifying trade event.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from app.data.models import OrderSide, TradeEvent
from app.signals.confidence import compute_confidence
from app.signals.models import Signal
from app.tracker.scoring import WalletScore
from app.utils.logger import get_logger

log = get_logger(__name__)


def evaluate(
    event: TradeEvent,
    wallet_score: WalletScore | None,
    config: dict[str, Any],
    open_market_ids: set[str],
) -> Signal | None:
    """Return a Signal if this trade event passes the whale-copy filter.

    Args:
        event: the incoming TradeEvent from the tracked wallet
        wallet_score: latest WalletScore for the source wallet (may be None)
        config: strategy config dict from strategies.yaml (strategies.whale_copy)
        open_market_ids: set of market_ids that already have an open position
    """
    if not config.get("enabled", True):
        return None

    min_size = float(config.get("min_trade_size_usd", 1000))
    min_sharpe = float(config.get("min_wallet_sharpe", 0.1))
    max_hold = float(config.get("max_wallet_median_holding_minutes", 720))
    max_holding = int(config.get("max_holding_minutes", 240))
    weight = float(config.get("confidence_weight", 0.35))
    size_pct = float(config.get("position_size_pct", 0.02))
    tp_pct = float(config.get("tp_pct", 0.15))
    sl_pct = float(config.get("sl_pct", 0.07))

    # Size filter
    if float(event.size_usd) < min_size:
        return None

    # Wallet quality filters
    if wallet_score is not None:
        if wallet_score.sharpe < min_sharpe:
            return None
        if wallet_score.median_holding_minutes > max_hold:
            return None

    # Don't stack positions on the same market
    if event.market_id in open_market_ids:
        log.debug("whale_copy.skip_open_position", market=event.market_id[:10])
        return None

    confidence = compute_confidence(wallet_score, weight)
    if confidence < 0.10:
        return None

    sig = Signal(
        signal_id=str(uuid.uuid4()),
        strategy="whale_copy",
        market_id=event.market_id,
        asset_id=event.asset_id,
        side=event.side,
        confidence=confidence,
        entry_price=event.price,
        size_pct=size_pct,
        tp_pct=tp_pct,
        sl_pct=sl_pct,
        max_holding_minutes=max_holding,
        source_wallet=event.taker_address,
        timestamp=datetime.now(tz=timezone.utc),
        reason=(
            f"Whale {event.taker_address[:10]} "
            f"{event.side.value} ${float(event.size_usd):.0f} "
            f"(confidence={confidence:.2f})"
        ),
    )
    log.info(
        "whale_copy.signal",
        signal_id=sig.signal_id[:8],
        market=event.market_id[:10],
        side=sig.side.value,
        confidence=f"{sig.confidence:.2f}",
        size_usd=float(event.size_usd),
    )
    return sig
