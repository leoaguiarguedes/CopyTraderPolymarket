from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from workers.collector_worker import _fetch_recent_fills, _fill_to_stream_fields, _load_wallet_addresses


def test_fill_to_stream_fields_buy_and_sell():
    buy_fill = {
        "id": "1",
        "transactionHash": "tx1",
        "maker": "0xmaker",
        "taker": "0xtaker",
        "makerAssetId": "0",
        "takerAssetId": "token",
        "makerAmountFilled": "2000000",
        "takerAmountFilled": "1000000",
        "timestamp": "1700000000",
    }
    fields = _fill_to_stream_fields(buy_fill, "0xtaker")
    assert fields["side"] == "BUY"
    assert fields["asset_id"] == "token"
    assert fields["wallet"] == "0xtaker"

    sell_fill = {
        "id": "2",
        "transactionHash": "tx2",
        "maker": "0xmaker",
        "taker": "0xtaker",
        "makerAssetId": "token",
        "takerAssetId": "0",
        "makerAmountFilled": "1000000",
        "takerAmountFilled": "2000000",
        "timestamp": "1700000001",
    }
    fields = _fill_to_stream_fields(sell_fill, "0xtaker")
    assert fields["side"] == "SELL"
    assert fields["asset_id"] == "token"


def test_load_wallet_addresses_returns_empty_on_failure(monkeypatch):
    def fake_open(*args, **kwargs):
        raise FileNotFoundError("missing")

    monkeypatch.setattr("builtins.open", fake_open)
    assert _load_wallet_addresses("missing.yaml") == []


@pytest.mark.asyncio
async def test_fetch_recent_fills_queries_both_sides(monkeypatch):
    class FakeSubgraph:
        def __init__(self):
            self._s = SimpleNamespace(subgraph_url="https://orderbook")

        async def _query(self, url, query, variables, timeout=15.0):
            return {"orderFilledEvents": [{"taker": "0xabc", "maker": "0xdef", "makerAmountFilled": "1000000", "takerAmountFilled": "1000000"}]}

    subgraph = FakeSubgraph()
    results = await _fetch_recent_fills(subgraph, "0xabc", 0)
    assert len(results) == 2
