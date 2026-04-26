import pytest
from datetime import datetime, timezone
from decimal import Decimal

from app.data.models import OrderSide, TradeEvent
from app.tracker.wallet_tracker import WalletTracker


class DummyResolver:
    def __init__(self, owner: str) -> None:
        self._owner = owner

    def known_proxies(self) -> set[str]:
        return {"0xproxy"}

    async def proxy_to_owner(self, proxy_address: str) -> str:
        return self._owner


def _make_event(taker: str, maker: str = "0xmaker") -> TradeEvent:
    return TradeEvent(
        id="tx1",
        market_id="mkt1",
        asset_id="asset1",
        outcome="YES",
        side=OrderSide.BUY,
        price=Decimal("0.5"),
        size=Decimal("100"),
        size_usd=Decimal("500"),
        fee_usd=Decimal("0"),
        maker_address=maker,
        taker_address=taker,
        timestamp=datetime.now(tz=timezone.utc),
        tx_hash="0xtx",
    )


@pytest.mark.asyncio
async def test_is_relevant_async_uses_proxy_resolver() -> None:
    tracker = WalletTracker({"0xowner"}, resolver=DummyResolver("0xowner"))
    event = _make_event("0xproxy")
    result = await tracker.is_relevant_async(event)
    assert result == "0xowner"


def test_reload_resets_tracked_set() -> None:
    tracker = WalletTracker({"0xone"})
    tracker.reload({"0xtwo"})
    assert tracker.tracked_count == 1
    assert tracker.is_relevant(_make_event("0xtwo")) == "0xtwo"
