from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.routes import wallets


class FakeResult:
    def __init__(self, values):
        self._values = values

    def scalars(self):
        return self

    def all(self):
        return self._values

    def scalar_one_or_none(self):
        if isinstance(self._values, list):
            return self._values[0] if self._values else None
        return self._values


class FakeSession:
    def __init__(self, get_obj=None, execute_results=None):
        self.get_obj = get_obj
        self.execute_results = execute_results or []
        self.calls = 0

    async def execute(self, _query):
        result = self.execute_results[self.calls]
        self.calls += 1
        return FakeResult(result)

    async def get(self, _orm, addr):
        return self.get_obj


@pytest.mark.asyncio
async def test_list_wallets_includes_scores_and_sorts():
    wallet = SimpleNamespace(address="0xabc", proxy_address="0xproxy", label="label", is_tracked=True)
    score = SimpleNamespace(
        n_trades=5,
        roi=Decimal("0.25"),
        sharpe=Decimal("1.5"),
        win_rate=Decimal("0.8"),
        max_drawdown=Decimal("0.1"),
        avg_holding_minutes=10,
        median_holding_minutes=5,
        pct_closed_under_24h=Decimal("0.9"),
        window_days=30,
        computed_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    session = FakeSession(get_obj=None, execute_results=[[wallet], [score]])

    result = await wallets.list_wallets(tracked_only=True, sort_by="sharpe", limit=1, session=session)

    assert result[0]["address"] == "0xabc"
    assert result[0]["sharpe"] == 1.5


@pytest.mark.asyncio
async def test_get_wallet_returns_not_found():
    session = FakeSession(get_obj=None, execute_results=[[], []])

    with pytest.raises(HTTPException):
        await wallets.get_wallet("0xabc", session=session)


@pytest.mark.asyncio
async def test_get_wallet_returns_data_and_trades():
    wallet = SimpleNamespace(address="0xabc", proxy_address="0xproxy", label="label", is_tracked=True)
    score = SimpleNamespace(
        window_days=30,
        n_trades=3,
        roi=Decimal("0.2"),
        sharpe=Decimal("1.0"),
        win_rate=Decimal("0.5"),
        max_drawdown=Decimal("0.1"),
        avg_holding_minutes=15,
        median_holding_minutes=10,
        pct_closed_under_24h=Decimal("0.6"),
        computed_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    trade = SimpleNamespace(
        id="trade1",
        market_id="m1",
        side="SELL",
        outcome="NO",
        price=Decimal("0.4"),
        size_usd=Decimal("20"),
        fee_usd=Decimal("0.1"),
        timestamp=datetime(2024, 1, 1, 1, 0, tzinfo=timezone.utc),
        tx_hash="txhash",
    )
    session = FakeSession(get_obj=wallet, execute_results=[[score], [trade]])

    result = await wallets.get_wallet("0xabc", session=session)

    assert result["address"] == "0xabc"
    assert result["scores"][0]["roi"] == 0.2
    assert result["recent_trades"][0]["id"] == "trade1"
