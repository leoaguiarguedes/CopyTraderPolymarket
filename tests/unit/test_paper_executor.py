from datetime import datetime, timezone
from decimal import Decimal

from app.data.models import OrderBook, OrderBookLevel
from app.execution.paper_executor import PaperExecutor
from app.signals.models import Signal


class DummyRest:
    async def get_orderbook(self, asset_id: str) -> OrderBook:
        return OrderBook(
            market_id="mkt1",
            asset_id=asset_id,
            bids=[OrderBookLevel(price=Decimal("0.49"), size=Decimal("100"))],
            asks=[OrderBookLevel(price=Decimal("0.51"), size=Decimal("100"))],
        )


def _make_signal(side: str = "BUY") -> Signal:
    from app.data.models import OrderSide

    return Signal(
        signal_id="sig1",
        strategy="whale_copy",
        market_id="mkt1",
        asset_id="asset1",
        side=OrderSide.BUY if side == "BUY" else OrderSide.SELL,
        confidence=0.5,
        entry_price=Decimal("0.5"),
        size_pct=0.02,
        tp_pct=0.10,
        sl_pct=0.05,
        max_holding_minutes=60,
        source_wallet="0xwhale",
        timestamp=datetime.now(tz=timezone.utc),
        reason="test",
    )


def test_paper_open_position_uses_orderbook_slippage() -> None:
    executor = PaperExecutor(DummyRest())
    position = asyncio_run(executor.open_position(_make_signal(), 1000.0))
    assert position.entry_price > Decimal("0.5")
    assert position.tp_price > position.entry_price
    assert position.sl_price < position.entry_price
    assert position.size_usd == Decimal("20.0")


def test_paper_close_position_computes_pnl_for_buy() -> None:
    executor = PaperExecutor(DummyRest())
    signal = _make_signal("BUY")
    position = asyncio_run(executor.open_position(signal, 1000.0))
    closed = asyncio_run(executor.close_position(position, "test"))
    assert closed.exit_price < closed.entry_price or closed.exit_price == closed.entry_price
    assert closed.exit_reason == "test"


def test_paper_close_position_computes_pnl_for_sell() -> None:
    executor = PaperExecutor(DummyRest())
    signal = _make_signal("SELL")
    position = asyncio_run(executor.open_position(signal, 1000.0))
    closed = asyncio_run(executor.close_position(position, "test"))
    assert closed.exit_reason == "test"


def asyncio_run(coro):
    import asyncio

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()
