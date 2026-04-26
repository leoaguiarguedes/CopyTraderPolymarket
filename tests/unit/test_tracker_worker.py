import pytest
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

from app.data.models import TradeEvent
from workers import tracker_worker


def test_load_tracked_addresses_returns_empty_on_missing_file(monkeypatch):
    def fake_open(*args, **kwargs):
        raise FileNotFoundError("missing")

    monkeypatch.setattr("builtins.open", fake_open)
    assert tracker_worker._load_tracked_addresses("missing.yaml") == set()


def test_deserialise_event_parses_fields():
    fields = {
        b"id": b"1",
        b"market_id": b"m1",
        b"price": b"0.5",
        b"size": b"2",
        b"size_usd": b"1.0",
        b"timestamp": b"2024-01-01T00:00:00+00:00",
    }

    event = tracker_worker._deserialise_event(fields)
    assert event is not None
    assert event.market_id == "m1"


@pytest.mark.asyncio
async def test_ensure_consumer_group_ignores_busygroup(monkeypatch):
    class FakeRedis:
        async def xgroup_create(self, *args, **kwargs):
            raise tracker_worker.aioredis.ResponseError("BUSYGROUP Consumer Group name already exists")

    await tracker_worker._ensure_consumer_group(FakeRedis())


@pytest.mark.asyncio
async def test_ensure_consumer_group_raises_other_errors(monkeypatch):
    class FakeRedis:
        async def xgroup_create(self, *args, **kwargs):
            raise tracker_worker.aioredis.ResponseError("other")

    with pytest.raises(tracker_worker.aioredis.ResponseError):
        await tracker_worker._ensure_consumer_group(FakeRedis())


@pytest.mark.asyncio
async def test_persist_trade_creates_wallet_and_trade(monkeypatch):
    added = []

    class FakeSession:
        def __init__(self):
            self.added = []
            self.committed = False

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, orm, key):
            return None

        def add(self, obj):
            self.added.append(obj)

        async def commit(self):
            self.committed = True

    fake_session = FakeSession()
    monkeypatch.setattr(tracker_worker, "SessionLocal", lambda: fake_session)

    event = TradeEvent(
        id="trade1",
        market_id="m1",
        asset_id="token",
        outcome="YES",
        side=tracker_worker.OrderSide.BUY,
        price=Decimal("0.5"),
        size=Decimal("2"),
        size_usd=Decimal("1.0"),
        fee_usd=Decimal("0.01"),
        maker_address="maker",
        taker_address="taker",
        timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
        tx_hash="tx1",
    )

    await tracker_worker._persist_trade(event, "0xabc")
    assert len(fake_session.added) >= 1
