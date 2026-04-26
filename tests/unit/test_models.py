from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.data.models import Market, OrderBook, OrderBookLevel, OrderSide, Side, TradeEvent, WalletTrade


def test_market_time_to_resolution_minutes() -> None:
    now = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
    market = Market(
        condition_id="mkt1",
        question="Will X happen?",
        end_date=now + timedelta(hours=2),
        liquidity_usd=Decimal("10000"),
    )
    assert market.time_to_resolution_minutes(now) == 120.0
    assert market.time_to_resolution_minutes(now + timedelta(hours=3)) == 0.0
    assert Market(condition_id="mkt2", question="No end", end_date=None).time_to_resolution_minutes(now) is None


def test_orderbook_best_prices_and_depth() -> None:
    asks = [OrderBookLevel(price=Decimal("0.5"), size=Decimal("100")), OrderBookLevel(price=Decimal("0.6"), size=Decimal("200"))]
    bids = [OrderBookLevel(price=Decimal("0.49"), size=Decimal("150")), OrderBookLevel(price=Decimal("0.48"), size=Decimal("50"))]
    book = OrderBook(market_id="mkt1", asset_id="asset1", bids=bids, asks=asks)

    assert book.best_ask() == Decimal("0.5")
    assert book.best_bid() == Decimal("0.49")
    assert book.depth_usd(side="ask", levels=1) == Decimal("50.0")
    assert book.depth_usd(side="bid", levels=2) == Decimal("97.50")


def test_wallettrade_holding_minutes() -> None:
    opened = datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc)
    closed = opened + timedelta(hours=3)
    trade = WalletTrade(
        trade_id="t1",
        wallet_address="0xabc",
        market_id="mkt1",
        outcome="YES",
        side=OrderSide.BUY,
        price=Decimal("0.5"),
        size_usd=Decimal("100"),
        cost_usd=Decimal("100"),
        opened_at=opened,
        closed_at=closed,
        realized_pnl_usd=Decimal("10"),
    )
    assert trade.holding_minutes == 180.0


def test_tradeevent_outcome_side_normalises() -> None:
    event = TradeEvent(
        id="tx1",
        market_id="mkt1",
        asset_id="asset1",
        outcome="yes",
        side=OrderSide.BUY,
        price=Decimal("0.5"),
        size=Decimal("1"),
        size_usd=Decimal("50"),
        fee_usd=Decimal("0"),
        maker_address="0xmaker",
        taker_address="0xtaker",
        timestamp=datetime.now(tz=timezone.utc),
        tx_hash="0xtx",
    )
    assert event.outcome_side == Side.YES
