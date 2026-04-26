from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.data.subgraph_client import SubgraphClient


@pytest.mark.asyncio
async def test_get_top_wallets_deduplicates_and_sorts(monkeypatch):
    settings = SimpleNamespace(
        subgraph_pnl_url="https://pnl",
        subgraph_url="https://subgraph",
        subgraph_orderbook_url="https://orderbook",
        subgraph_api_key=None,
    )
    client = SubgraphClient(settings)

    async def fake_query(url, query, variables, timeout=30.0):
        if variables["skip"] == 0:
            return {
                "userPositions": [
                    {"user": "0xabc", "realizedPnl": "2000000", "totalBought": "1000000"},
                    {"user": "0xabc", "realizedPnl": "1000000", "totalBought": "500000"},
                ]
            }
        return {"userPositions": []}

    monkeypatch.setattr(client, "_query", fake_query)
    result = await client.get_top_wallets(limit=10)

    assert result == [{"id": "0xabc", "profit": 3.0, "volume": 1.5, "numTrades": 1}]


@pytest.mark.asyncio
async def test_get_active_wallets_filters_by_min_fills(monkeypatch):
    settings = SimpleNamespace(
        subgraph_pnl_url="https://pnl",
        subgraph_url="https://subgraph",
        subgraph_orderbook_url="https://orderbook",
        subgraph_api_key=None,
    )
    client = SubgraphClient(settings)

    async def fake_query(url, query, variables, timeout=30.0):
        return {
            "orderFilledEvents": [
                {"taker": "0xabc", "maker": "0xdef", "makerAmountFilled": "1000000", "takerAmountFilled": "2000000"},
                {"taker": "0xabc", "maker": "0xghi", "makerAmountFilled": "500000", "takerAmountFilled": "500000"},
            ]
        }

    monkeypatch.setattr(client, "_query", fake_query)
    results = await client.get_active_wallets(days_back=1, min_fills=2, max_events=10)

    assert any(wallet["id"] == "0xabc" for wallet in results)
    assert results[0]["fills"] == 2


def test_fills_to_wallet_trades_aggregates_buy_and_sell():
    settings = SimpleNamespace(
        subgraph_pnl_url="https://pnl",
        subgraph_url="https://subgraph",
        subgraph_orderbook_url="https://orderbook",
        subgraph_api_key=None,
    )
    client = SubgraphClient(settings)
    wallet = "0xabc"

    fills = [
        {
            "id": "1",
            "maker": "0xabc",
            "taker": "0xdef",
            "makerAssetId": "0",
            "takerAssetId": "token",
            "makerAmountFilled": "1000000",
            "takerAmountFilled": "1000000",
            "timestamp": "1700000000",
        },
        {
            "id": "2",
            "maker": "0xabc",
            "taker": "0xdef",
            "makerAssetId": "token",
            "takerAssetId": "0",
            "makerAmountFilled": "1000000",
            "takerAmountFilled": "2000000",
            "timestamp": "1700000001",
        },
    ]

    trades = client._fills_to_wallet_trades(fills, wallet)
    assert len(trades) == 1
    assert trades[0].wallet_address == wallet
    assert trades[0].realized_pnl_usd == Decimal("1")


@pytest.mark.asyncio
async def test_get_wallet_pnl_summary_returns_zero_and_totals(monkeypatch):
    settings = SimpleNamespace(
        subgraph_pnl_url="https://pnl",
        subgraph_url="https://subgraph",
        subgraph_orderbook_url="https://orderbook",
        subgraph_api_key=None,
    )
    client = SubgraphClient(settings)

    async def fake_query(url, query, variables, timeout=30.0):
        if variables.get("skip") == 0:
            return {"userPositions": [{"realizedPnl": "2000000", "totalBought": "500000"}]}
        return {"userPositions": []}

    monkeypatch.setattr(client, "_query", fake_query)
    summary = await client.get_wallet_pnl_summary("0xabc")

    assert summary["total_pnl_usd"] == 2.0
    assert summary["total_volume_usd"] == 0.5
    assert summary["n_positions"] == 1


@pytest.mark.asyncio
async def test_fetch_fills_pages_until_max_fills(monkeypatch):
    settings = SimpleNamespace(
        subgraph_pnl_url="https://pnl",
        subgraph_url="https://subgraph",
        subgraph_orderbook_url="https://orderbook",
        subgraph_api_key=None,
    )
    client = SubgraphClient(settings)

    async def fake_query(url, query, variables, timeout=30.0):
        skip = variables.get("skip", 0)
        if skip == 0:
            return {"orderFilledEvents": [{"id": "1"}]}
        if skip == 1:
            return {"orderFilledEvents": [{"id": "2"}]}
        return {"orderFilledEvents": []}

    monkeypatch.setattr(client, "_query", fake_query)
    fills = await client._fetch_fills("0xabc", as_taker=True, min_ts=0, page_size=1, max_fills=2)

    assert len(fills) == 2


@pytest.mark.asyncio
async def test_get_wallet_trades_deduplicates_duplicates(monkeypatch):
    settings = SimpleNamespace(
        subgraph_pnl_url="https://pnl",
        subgraph_url="https://subgraph",
        subgraph_orderbook_url="https://orderbook",
        subgraph_api_key=None,
    )
    client = SubgraphClient(settings)

    async def fetch_fills(wallet, as_taker, min_ts, page_size, max_fills):
        return [
            {"id": "1", "maker": wallet, "taker": "0xother", "makerAssetId": "0", "takerAssetId": "token", "makerAmountFilled": "1000000", "takerAmountFilled": "1000000", "timestamp": "1700000000"},
            {"id": "1", "maker": wallet, "taker": "0xother", "makerAssetId": "0", "takerAssetId": "token", "makerAmountFilled": "1000000", "takerAmountFilled": "1000000", "timestamp": "1700000000"},
        ]

    monkeypatch.setattr(client, "_fetch_fills", fetch_fills)
    trades = await client.get_wallet_trades("0xabc")

    assert len(trades) == 1
