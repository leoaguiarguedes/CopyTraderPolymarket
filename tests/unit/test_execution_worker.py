from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
from workers import execution_worker
from app.execution.base import Position
from app.signals.models import Signal
from app.data.models import OrderSide


def test_dict_to_signal_parses_valid_payload():
    data = {
        "signal_id": "sig1",
        "strategy": "momentum",
        "market_id": "market1",
        "asset_id": "asset1",
        "side": "BUY",
        "confidence": 0.8,
        "entry_price": 0.5,
        "size_pct": 0.1,
        "tp_pct": 0.1,
        "sl_pct": 0.05,
        "max_holding_minutes": 60,
        "source_wallet": "0xabc",
        "timestamp": "2024-01-01T00:00:00+00:00",
        "reason": "test",
        "market_question": "question",
    }

    sig = execution_worker._dict_to_signal(data)
    assert isinstance(sig, Signal)
    assert sig.signal_id == "sig1"


def test_dict_to_signal_returns_none_on_invalid_payload():
    assert execution_worker._dict_to_signal({"signal_id": "sig1"}) is None


def test_position_to_dict_formats_output():
    position = Position(
        position_id="pos1",
        signal_id="sig1",
        strategy="test",
        market_id="market1",
        asset_id="asset1",
        side="BUY",
        entry_price=Decimal("1.0"),
        size_usd=Decimal("10"),
        size_tokens=Decimal("10"),
        tp_price=Decimal("1.2"),
        sl_price=Decimal("0.9"),
        max_holding_minutes=60,
        opened_at=datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc),
    )

    data = execution_worker._position_to_dict(position, "opened")
    assert data["event"] == "opened"
    assert data["position_id"] == "pos1"
    assert data["exit_price"] is None


@pytest.mark.asyncio
async def test_on_position_closed_publishes_update(monkeypatch):
    worker = SimpleNamespace()
    worker._r = SimpleNamespace(adds=[])

    async def xadd(stream, fields):
        worker._r.adds.append((stream, fields))

    worker._r.xadd = xadd

    async def persist_position(position, update=False):
        return None

    worker._persist_position = persist_position

    position = Position(
        position_id="pos1",
        signal_id="sig1",
        strategy="test",
        market_id="market1",
        asset_id="asset1",
        side="BUY",
        entry_price=Decimal("1.0"),
        size_usd=Decimal("10"),
        size_tokens=Decimal("10"),
        tp_price=Decimal("1.2"),
        sl_price=Decimal("0.9"),
        max_holding_minutes=60,
        opened_at=datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc),
        closed_at=datetime(2024, 1, 1, 1, 0, tzinfo=timezone.utc),
        exit_price=Decimal("1.1"),
        realized_pnl_usd=Decimal("1.0"),
        exit_reason="tp",
    )

    await execution_worker.ExecutionWorker._on_position_closed(worker, position)

    import json

    assert worker._r.adds[0][0] == "positions"
    payload = json.loads(worker._r.adds[0][1]["data"])
    assert payload["event"] == "closed"


@pytest.mark.asyncio
async def test_process_signal_opens_position_and_publishes(monkeypatch):
    worker = SimpleNamespace()
    worker._r = SimpleNamespace(adds=[])

    async def xadd(stream, fields):
        worker._r.adds.append((stream, fields))

    worker._r.xadd = xadd
    async def persist_signal(*args, **kwargs):
        return None

    async def persist_position(*args, **kwargs):
        return None

    worker._persist_signal = persist_signal
    worker._persist_position = persist_position
    worker._s = SimpleNamespace(execution_mode=SimpleNamespace(value="paper"))

    async def open_position(sig, capital):
        return Position(
            position_id="pos1",
            signal_id=sig.signal_id,
            strategy=sig.strategy,
            market_id=sig.market_id,
            asset_id=sig.asset_id,
            side=sig.side.value,
            entry_price=sig.entry_price,
            size_usd=Decimal("10"),
            size_tokens=Decimal("10"),
            tp_price=Decimal("1.2"),
            sl_price=Decimal("0.9"),
            max_holding_minutes=60,
            opened_at=datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc),
        )

    executor = SimpleNamespace(open_position=open_position)

    async def validate(*args, **kwargs):
        return SimpleNamespace(approved=True, reason="ok")

    risk = SimpleNamespace(validate=validate, open_positions={}, capital_usd=100.0)
    exit_mgr = SimpleNamespace(positions={})
    data = {
        "signal_id": "sig1",
        "strategy": "momentum",
        "market_id": "market1",
        "asset_id": "asset1",
        "side": "BUY",
        "confidence": 0.8,
        "entry_price": 0.5,
        "size_pct": 0.1,
        "tp_pct": 0.1,
        "sl_pct": 0.05,
        "max_holding_minutes": 60,
        "source_wallet": "0xabc",
        "timestamp": "2024-01-01T00:00:00+00:00",
    }

    import json

    await execution_worker.ExecutionWorker._process_signal(
        worker,
        b"1",
        {b"data": json.dumps(data).encode()},
        risk,
        executor,
        exit_mgr,
    )

    assert worker._r.adds
    assert worker._r.adds[0][0] == "positions"
