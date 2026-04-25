"""Unit tests for WalletTracker."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from app.data.models import OrderSide, TradeEvent
from app.tracker.wallet_tracker import WalletTracker


def _make_event(taker: str, size_usd: float = 500.0) -> TradeEvent:
    return TradeEvent(
        id="tx1",
        market_id="mkt1",
        asset_id="asset1",
        outcome="YES",
        side=OrderSide.BUY,
        price=Decimal("0.5"),
        size=Decimal("1000"),
        size_usd=Decimal(str(size_usd)),
        fee_usd=Decimal("0"),
        maker_address="0xmaker",
        taker_address=taker,
        timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc),
        tx_hash="0xtx",
    )


def test_is_relevant_detects_tracked_taker() -> None:
    tracker = WalletTracker({"0xwhale"})
    event = _make_event(taker="0xwhale")
    assert tracker.is_relevant(event) == "0xwhale"


def test_is_relevant_normalises_case() -> None:
    tracker = WalletTracker({"0xWHALE"})
    event = _make_event(taker="0xwhale")
    assert tracker.is_relevant(event) == "0xwhale"


def test_is_relevant_ignores_untracked() -> None:
    tracker = WalletTracker({"0xother"})
    event = _make_event(taker="0xwhale")
    assert tracker.is_relevant(event) is None


def test_is_relevant_filters_small_trades() -> None:
    tracker = WalletTracker({"0xwhale"}, min_size_usd=100.0)
    event = _make_event(taker="0xwhale", size_usd=10.0)
    assert tracker.is_relevant(event) is None


def test_is_relevant_detects_tracked_maker() -> None:
    tracker = WalletTracker({"0xmaker"})
    event = TradeEvent(
        id="tx2",
        market_id="mkt1",
        asset_id="asset1",
        outcome="YES",
        side=OrderSide.BUY,
        price=Decimal("0.5"),
        size=Decimal("100"),
        size_usd=Decimal("500"),
        fee_usd=Decimal("0"),
        maker_address="0xmaker",
        taker_address="0xother",
        timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc),
        tx_hash="0xtx2",
    )
    assert tracker.is_relevant(event) == "0xmaker"


def test_add_remove_wallet() -> None:
    tracker = WalletTracker(set())
    tracker.add_wallet("0xnew")
    assert tracker.is_relevant(_make_event("0xnew")) == "0xnew"
    tracker.remove_wallet("0xnew")
    assert tracker.is_relevant(_make_event("0xnew")) is None


def test_filter_batch() -> None:
    tracker = WalletTracker({"0xwhale"})
    events = [
        _make_event("0xwhale"),
        _make_event("0xrandom"),
        _make_event("0xwhale"),
    ]
    result = tracker.filter_batch(events)
    assert len(result) == 2
    assert all(wallet == "0xwhale" for _, wallet in result)
