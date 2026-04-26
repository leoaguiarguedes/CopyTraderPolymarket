import json
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.signals.models import Signal
from app.data.models import OrderSide
from workers import signal_worker


@pytest.mark.asyncio
async def test_get_score_caches_results(monkeypatch):
    settings = SimpleNamespace(redis_url="redis://localhost", subgraph_url="https://subgraph", subgraph_orderbook_url="https://orderbook", polymarket_gamma_url="https://gamma", polymarket_clob_url="https://clob", polymarket_data_url="https://data")
    monkeypatch.setattr(signal_worker, "get_settings", lambda: settings)

    worker = signal_worker.SignalWorker()
    async def fake_get_wallet_trades(wallet, days_back=30, max_fills=500):
        return []

    worker._subgraph = SimpleNamespace(get_wallet_trades=fake_get_wallet_trades)
    monkeypatch.setattr(signal_worker, "compute_score", lambda trades: "score")

    score1 = await worker._get_score("0xabc")
    score2 = await worker._get_score("0xabc")

    assert score1 == "score"
    assert score2 == "score"


@pytest.mark.asyncio
async def test_get_score_handles_errors(monkeypatch):
    settings = SimpleNamespace(redis_url="redis://localhost", subgraph_url="https://subgraph", subgraph_orderbook_url="https://orderbook", polymarket_gamma_url="https://gamma", polymarket_clob_url="https://clob", polymarket_data_url="https://data")
    monkeypatch.setattr(signal_worker, "get_settings", lambda: settings)

    worker = signal_worker.SignalWorker()

    async def fake_get_wallet_trades(wallet, days_back=30, max_fills=500):
        raise RuntimeError("bad")

    worker._subgraph = SimpleNamespace(get_wallet_trades=fake_get_wallet_trades)

    score = await worker._get_score("0xabc")

    assert score is None


def test_dict_to_trade_event_returns_none_for_invalid_payload():
    assert signal_worker._dict_to_trade_event({"id": "t1"}) is None


@pytest.mark.asyncio
async def test_process_message_emits_signal(monkeypatch):
    settings = SimpleNamespace(redis_url="redis://localhost", subgraph_url="https://subgraph", subgraph_orderbook_url="https://orderbook", polymarket_gamma_url="https://gamma", polymarket_clob_url="https://clob", polymarket_data_url="https://data")
    monkeypatch.setattr(signal_worker, "get_settings", lambda: settings)

    worker = signal_worker.SignalWorker()
    async def fake_get_wallet_trades(wallet, days_back=30, max_fills=500):
        return None

    worker._subgraph = SimpleNamespace(get_wallet_trades=fake_get_wallet_trades)

    signal_out = Signal(
        signal_id="sig1",
        strategy="momentum",
        market_id="m1",
        asset_id="a1",
        side=OrderSide.BUY,
        confidence=0.8,
        entry_price=0.5,
        size_pct=0.1,
        tp_pct=0.1,
        sl_pct=0.05,
        max_holding_minutes=30,
        source_wallet="0xabc",
        timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
        reason="test",
    )

    def fake_process_event(event, score):
        return [signal_out]

    worker._engine.process_event = fake_process_event

    added = []

    async def fake_xadd(stream, data):
        added.append((stream, data))

    worker._r = SimpleNamespace(xadd=fake_xadd)

    payload = {
        "id": "trade1",
        "market_id": "m1",
        "asset_id": "a1",
        "price": "0.5",
        "size": "1",
        "size_usd": "0.5",
        "side": "BUY",
        "timestamp": "2024-01-01T00:00:00+00:00",
    }
    await worker._process_message(b"1", {b"data": json.dumps(payload).encode()})

    assert added
    assert added[0][0] == "signals"
