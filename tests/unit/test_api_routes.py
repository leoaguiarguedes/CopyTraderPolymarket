from datetime import datetime, timezone
from types import SimpleNamespace

from app.api.routes import pnl, positions, signals, trades


class FakeResult:
    def __init__(self, values):
        self._values = values

    def scalars(self):
        return self

    def all(self):
        return self._values


class FakeSession:
    def __init__(self, values):
        self.values = values

    async def execute(self, _query):
        return FakeResult(self.values)


def test_range_cutoff_valid_and_invalid(monkeypatch):
    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2024, 1, 2, tzinfo=timezone.utc)

    monkeypatch.setattr(pnl, "datetime", FixedDateTime)

    one_day_cutoff = pnl._range_cutoff("1d")
    assert one_day_cutoff == datetime(2024, 1, 1, tzinfo=timezone.utc)
    assert pnl._range_cutoff("unknown") == datetime.min.replace(tzinfo=timezone.utc)


def test_position_to_dict_open_and_closed():
    now = datetime(2024, 1, 2, 12, 0, tzinfo=timezone.utc)
    open_position = SimpleNamespace(
        position_id="p1",
        signal_id="s1",
        strategy="test",
        market_id="m1",
        side="BUY",
        entry_price=1.23,
        size_usd=100,
        tp_price=1.5,
        sl_price=1.0,
        max_holding_minutes=120,
        opened_at=datetime(2024, 1, 2, 10, 0, tzinfo=timezone.utc),
        closed_at=None,
        exit_price=None,
        realized_pnl_usd=None,
        exit_reason=None,
        execution_mode="paper",
    )

    data = positions._position_to_dict(open_position, now)
    assert data["age_minutes"] == 120.0
    assert data["time_to_force_exit_minutes"] == 0.0

    closed_position = SimpleNamespace(**{**open_position.__dict__, "closed_at": datetime(2024, 1, 2, 11, 0, tzinfo=timezone.utc)})
    closed_data = positions._position_to_dict(closed_position, now)
    assert closed_data["time_to_force_exit_minutes"] is None


def test_signal_to_dict():
    signal = SimpleNamespace(
        signal_id="sig1",
        strategy="momentum",
        market_id="m1",
        market_question="Will it happen?",
        side="BUY",
        confidence=0.87,
        entry_price=0.55,
        size_pct=0.1,
        tp_pct=0.12,
        sl_pct=0.05,
        max_holding_minutes=180,
        source_wallet="0xabc",
        status="approved",
        reject_reason=None,
        reason="strong bet",
        created_at=datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc),
    )

    result = signals._signal_to_dict(signal)
    assert result["signal_id"] == "sig1"
    assert result["confidence"] == 0.87
    assert result["created_at"] == "2024-01-01T00:00:00+00:00"


async def test_list_positions_filters_by_status():
    open_position = SimpleNamespace(closed_at=None, opened_at=datetime(2024, 1, 2, 0, 0, tzinfo=timezone.utc), max_holding_minutes=120)
    open_position.position_id = "p1"
    open_position.signal_id = "s1"
    open_position.strategy = "test"
    open_position.market_id = "m1"
    open_position.side = "BUY"
    open_position.entry_price = 1
    open_position.size_usd = 100
    open_position.tp_price = 2
    open_position.sl_price = 0.5
    open_position.exit_price = None
    open_position.realized_pnl_usd = None
    open_position.exit_reason = None
    open_position.execution_mode = "paper"

    session = FakeSession([open_position])
    result = await positions.list_positions(status="open", limit=100, strategy=None, db=session)
    assert result[0]["position_id"] == "p1"


async def test_list_trades_returns_serialized_records():
    trade = SimpleNamespace(
        id="t1",
        wallet_address="0xabc",
        market_id="m1",
        side="BUY",
        outcome="YES",
        price=0.5,
        size_usd=100,
        fee_usd=1,
        timestamp=datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc),
        tx_hash="tx123",
    )
    session = FakeSession([trade])
    result = await trades.list_trades(wallet=None, market_id=None, limit=50, session=session)
    assert result == [
        {
            "id": "t1",
            "wallet_address": "0xabc",
            "market_id": "m1",
            "side": "BUY",
            "outcome": "YES",
            "price": 0.5,
            "size_usd": 100.0,
            "fee_usd": 1.0,
            "timestamp": "2024-01-01T00:00:00+00:00",
            "tx_hash": "tx123",
        }
    ]
