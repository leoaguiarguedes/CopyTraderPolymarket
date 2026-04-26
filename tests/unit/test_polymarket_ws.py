import json
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.data.polymarket_ws import PolymarketWebSocket


def test_parse_message_filters_by_event_type():
    client = PolymarketWebSocket(["m1"], settings=SimpleNamespace(polymarket_ws_url="wss://test"))
    data = json.dumps([
        {"event_type": "trade", "id": "1", "market_id": "m1", "price": "0.1", "size": "2", "maker": "maker", "taker": "taker"},
        {"event_type": "other", "id": "2"},
    ])

    events = client._parse_message(data)
    assert len(events) == 1
    assert events[0].market_id == "m1"


def test_parse_message_invalid_json_returns_empty():
    client = PolymarketWebSocket(["m1"], settings=SimpleNamespace(polymarket_ws_url="wss://test"))
    assert client._parse_message("not-json") == []


def test_parse_trade_timestamp_and_side_variants():
    client = PolymarketWebSocket(["m1"], settings=SimpleNamespace(polymarket_ws_url="wss://test"))
    raw = {
        "id": "trade1",
        "market_id": "m1",
        "asset_id": "token1",
        "outcome": "YES",
        "price": "0.7",
        "size": "3",
        "fee": "0.02",
        "maker": "MAKER",
        "taker": "TAKER",
        "timestamp": "2024-01-01T00:00:00Z",
        "transaction_hash": "tx123",
        "side": "yes",
    }
    trade = client._parse_trade(raw)

    assert trade is not None
    assert trade.side == trade.side.BUY
    assert trade.price == Decimal("0.7")
    assert trade.tx_hash == "tx123"


@pytest.mark.asyncio
async def test_subscribe_sends_subscription(monkeypatch):
    client = PolymarketWebSocket(["m1"], asset_ids=["token1"], settings=SimpleNamespace(polymarket_ws_url="wss://test"))

    class FakeWebSocket:
        def __init__(self):
            self.sent = []

        async def send(self, message):
            self.sent.append(message)

    ws = FakeWebSocket()
    await client._subscribe(ws)

    assert len(ws.sent) == 1
    assert "Market" in ws.sent[0]
    assert "Asset" in ws.sent[0]


def test_parse_trade_returns_none_for_invalid_data():
    client = PolymarketWebSocket(["m1"], settings=SimpleNamespace(polymarket_ws_url="wss://test"))
    raw = {"id": "trade1", "timestamp": "not-a-date", "price": "nan", "size": "bad", "side": "BUY"}
    assert client._parse_trade(raw) is None
