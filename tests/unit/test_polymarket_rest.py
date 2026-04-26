import json
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.data.polymarket_rest import PolymarketRestClient


class DummyResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("HTTP error")

    def json(self):
        return self._payload


@pytest.mark.asyncio
async def test_parse_market_with_json_string_tokens():
    settings = SimpleNamespace(
        polymarket_gamma_url="https://gamma",
        polymarket_clob_url="https://clob",
        polymarket_data_url="https://data",
    )
    client = PolymarketRestClient(settings)

    raw = {
        "conditionId": "0x1",
        "question": "Will it rain?",
        "tokens": json.dumps(["t1", "t2"]),
        "active": True,
        "closed": False,
        "volume24hr": "1000",
        "liquidity": "500",
    }
    market = client._parse_market(raw)

    assert market.condition_id == "0x1"
    assert market.token_ids == ["t1", "t2"]
    await client.aclose()


@pytest.mark.asyncio
async def test_parse_trade_int_timestamp_and_side_conversion():
    settings = SimpleNamespace(
        polymarket_gamma_url="https://gamma",
        polymarket_clob_url="https://clob",
        polymarket_data_url="https://data",
    )
    client = PolymarketRestClient(settings)

    raw = {
        "id": "trade1",
        "market": "market1",
        "asset_id": "token1",
        "outcome": "no",
        "price": "0.75",
        "size": "2",
        "fee": "0.01",
        "maker": "MAKER",
        "taker": "TAKER",
        "timestamp": 1700000000,
        "transactionHash": "txhash",
        "side": "SELL",
    }
    trade = client._parse_trade(raw)

    assert trade is not None
    assert trade.side == trade.side.SELL
    assert trade.price == Decimal("0.75")
    assert trade.size_usd == Decimal("1.50")
    await client.aclose()


@pytest.mark.asyncio
async def test_get_proxy_wallet_returns_none_on_404(monkeypatch):
    settings = SimpleNamespace(
        polymarket_gamma_url="https://gamma",
        polymarket_clob_url="https://clob",
        polymarket_data_url="https://data",
    )
    client = PolymarketRestClient(settings)

    async def fake_get(path):
        return DummyResponse(status_code=404)

    monkeypatch.setattr(client._gamma, "get", fake_get)

    assert await client.get_proxy_wallet("0xabc") is None
    await client.aclose()


@pytest.mark.asyncio
async def test_get_all_active_markets_paginates(monkeypatch):
    settings = SimpleNamespace(
        polymarket_gamma_url="https://gamma",
        polymarket_clob_url="https://clob",
        polymarket_data_url="https://data",
    )
    client = PolymarketRestClient(settings)

    async def fake_get_markets(active, limit, offset):
        if offset == 0:
            return [SimpleNamespace(condition_id="1", question="q1", slug=None, category=None, end_date=None, is_active=True, is_resolved=False, resolved_outcome=None, volume_24h_usd=None, liquidity_usd=None, token_ids=[])]
        return []

    monkeypatch.setattr(client, "get_markets", fake_get_markets)

    markets = await client.get_all_active_markets(max_markets=100)
    assert len(markets) == 1
    await client.aclose()


@pytest.mark.asyncio
async def test_get_orderbook_parses_levels(monkeypatch):
    settings = SimpleNamespace(
        polymarket_gamma_url="https://gamma",
        polymarket_clob_url="https://clob",
        polymarket_data_url="https://data",
    )
    client = PolymarketRestClient(settings)

    payload = {
        "market": "m1",
        "bids": [{"price": "0.15", "size": "10"}],
        "asks": [{"price": "0.16", "size": "5"}],
    }

    async def fake_get(path, params=None):
        return DummyResponse(status_code=200, payload=payload)

    monkeypatch.setattr(client._clob, "get", fake_get)

    orderbook = await client.get_orderbook("token1")
    assert orderbook.market_id == "m1"
    assert orderbook.best_bid() == Decimal("0.15")
    assert orderbook.best_ask() == Decimal("0.16")
    await client.aclose()


@pytest.mark.asyncio
async def test_get_markets_parses_data_payload(monkeypatch):
    settings = SimpleNamespace(
        polymarket_gamma_url="https://gamma",
        polymarket_clob_url="https://clob",
        polymarket_data_url="https://data",
    )
    client = PolymarketRestClient(settings)

    async def fake_get(path, params=None):
        return DummyResponse(payload={"data": [{"conditionId": "0x2", "question": "Yes?", "tokens": ["t1"]}]})

    monkeypatch.setattr(client._gamma, "get", fake_get)

    markets = await client.get_markets(active=False, limit=1, offset=0)
    assert markets[0].condition_id == "0x2"
    await client.aclose()


@pytest.mark.asyncio
async def test_get_trades_constructs_parameters(monkeypatch):
    settings = SimpleNamespace(
        polymarket_gamma_url="https://gamma",
        polymarket_clob_url="https://clob",
        polymarket_data_url="https://data",
    )
    client = PolymarketRestClient(settings)

    class FakeAsyncClient:
        def __init__(self, base_url=None, timeout=None):
            self.base_url = base_url

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, path, params=None):
            assert path == "/trades"
            assert params["market"] == "m1"
            assert params["maker"] == "maker"
            assert params["taker"] == "taker"
            assert params["after"] == 123
            return DummyResponse(payload=[{"id": "trade1", "market": "m1", "asset_id": "token1", "outcome": "YES", "price": "0.5", "size": "2", "maker": "maker", "taker": "taker", "transactionHash": "tx1", "timestamp": 1700000000}])

    monkeypatch.setattr("app.data.polymarket_rest.httpx.AsyncClient", FakeAsyncClient)

    trades = await client.get_trades(market_id="m1", maker="maker", taker="taker", after_ts=123)
    assert len(trades) == 1
    await client.aclose()
