from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.api.routes import pnl


class FakeResult:
    def __init__(self, values):
        self._values = values

    def scalars(self):
        return self

    def one(self):
        return self._values

    def all(self):
        return self._values


class FakeSession:
    def __init__(self, row, open_row, positions):
        self._row = row
        self._open_row = open_row
        self._positions = positions
        self.calls = 0

    async def execute(self, _query):
        self.calls += 1
        if self.calls == 1:
            if self._row is not None:
                return FakeResult(self._row)
            return FakeResult(self._positions)
        if self.calls == 2:
            return FakeResult(self._open_row)
        return FakeResult(self._positions)


@pytest.mark.asyncio
async def test_get_pnl_summary_computes_totals():
    row = SimpleNamespace(n_positions=2, total_pnl=Decimal("100"), total_volume=Decimal("200"), wins=1)
    open_row = SimpleNamespace(open_count=1, open_exposure=Decimal("50"))
    session = FakeSession(row, open_row, [])

    result = await pnl.get_pnl_summary(range="7d", db=session)

    assert result["range"] == "7d"
    assert result["total_pnl_usd"] == 100.0
    assert result["total_volume_usd"] == 200.0
    assert result["n_closed_positions"] == 2
    assert result["win_rate"] == 0.5
    assert result["open_positions"] == 1


@pytest.mark.asyncio
async def test_get_equity_curve_builds_cumulative_points():
    pos1 = SimpleNamespace(realized_pnl_usd=Decimal("10"), closed_at=datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc), exit_reason="tp")
    pos2 = SimpleNamespace(realized_pnl_usd=Decimal("5"), closed_at=datetime(2024, 1, 1, 1, 0, tzinfo=timezone.utc), exit_reason="sl")
    session = FakeSession(None, None, [pos1, pos2])

    result = await pnl.get_equity_curve(range="30d", bucket="1h", db=session)

    assert result["range"] == "30d"
    assert result["final_pnl"] == 15.0
    assert result["points"][0]["cumulative"] == 10.0
