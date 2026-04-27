"""Tests for KellySizer."""
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.execution.kelly import KellySizer, _MIN_SAMPLES
from app.execution.base import Position


def _make_position(pnl_usd: float, size_usd: float = 20.0) -> Position:
    return Position(
        position_id="pos1",
        signal_id="sig1",
        strategy="whale_copy",
        market_id="mkt1",
        asset_id="asset1",
        side="BUY",
        entry_price=Decimal("0.50"),
        size_usd=Decimal(str(size_usd)),
        size_tokens=Decimal("40"),
        tp_price=Decimal("0.575"),
        sl_price=Decimal("0.465"),
        max_holding_minutes=240,
        opened_at=datetime.now(tz=timezone.utc),
        closed_at=datetime.now(tz=timezone.utc),
        realized_pnl_usd=Decimal(str(pnl_usd)),
        exit_reason="tp",
    )


class TestKellySizer:
    def test_fallback_before_enough_history(self):
        kelly = KellySizer(kelly_fraction=0.25, min_pct=0.005, max_pct=0.05)
        # With fewer than _MIN_SAMPLES, should clamp signal size_pct
        result = kelly.size_pct(0.03)
        assert 0.005 <= result <= 0.05
        assert result == 0.03  # unchanged since it's within bounds

    def test_fallback_clamps_to_max(self):
        kelly = KellySizer()
        result = kelly.size_pct(0.99)  # way above max
        assert result == kelly.max_pct

    def test_fallback_clamps_to_min(self):
        kelly = KellySizer()
        result = kelly.size_pct(0.001)  # below min
        assert result == kelly.min_pct

    def test_record_increments_sample_count(self):
        kelly = KellySizer()
        assert kelly.sample_count == 0
        kelly.record(_make_position(1.0))
        assert kelly.sample_count == 1

    def test_has_enough_history(self):
        kelly = KellySizer()
        assert not kelly.has_enough_history
        for _ in range(_MIN_SAMPLES):
            kelly.record(_make_position(1.0))
        assert kelly.has_enough_history

    def test_positive_edge_gives_larger_size(self):
        kelly = KellySizer(kelly_fraction=0.25, min_pct=0.005, max_pct=0.05)
        # Feed many winning trades
        for _ in range(15):
            kelly.record(_make_position(3.0))   # win: +15% of 20
        for _ in range(5):
            kelly.record(_make_position(-1.0))  # loss: -5% of 20

        result = kelly.size_pct(0.02)
        # Should be above the min and <= max
        assert kelly.min_pct <= result <= kelly.max_pct

    def test_negative_edge_returns_min(self):
        kelly = KellySizer(kelly_fraction=0.25, min_pct=0.005, max_pct=0.05)
        # Feed mostly losing trades
        for _ in range(20):
            kelly.record(_make_position(-3.0))

        result = kelly.size_pct(0.02)
        assert result == kelly.min_pct

    def test_all_wins_caps_at_max(self):
        kelly = KellySizer(kelly_fraction=0.25, min_pct=0.005, max_pct=0.05)
        for _ in range(20):
            kelly.record(_make_position(10.0))

        result = kelly.size_pct(0.02)
        assert result <= kelly.max_pct

    def test_skips_positions_without_pnl(self):
        kelly = KellySizer()
        pos = _make_position(1.0)
        pos = Position(
            **{**pos.__dict__, "realized_pnl_usd": None}
        )
        kelly.record(pos)
        assert kelly.sample_count == 0
