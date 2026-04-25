"""Unit tests for wallet scoring."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.data.models import OrderSide, WalletTrade
from app.tracker.scoring import WalletScore, compute_score


def _make_trade(
    i: int,
    pnl: float,
    holding_min: float,
    wallet: str = "0xabc",
) -> WalletTrade:
    opened = datetime(2025, 1, i + 1, tzinfo=timezone.utc)
    from datetime import timedelta

    closed = opened + timedelta(minutes=holding_min)
    return WalletTrade(
        trade_id=f"t{i}",
        wallet_address=wallet,
        market_id=f"mkt{i}",
        outcome="YES",
        side=OrderSide.BUY,
        price=Decimal("0.5"),
        size_usd=Decimal("100"),
        opened_at=opened,
        closed_at=closed,
        realized_pnl_usd=Decimal(str(pnl)),
    )


def test_compute_score_basic() -> None:
    trades = [_make_trade(i, pnl, 60) for i, pnl in enumerate([10, 8, -3, 5, 12, -2, 7, 9, 4, 6])]
    score = compute_score(trades)
    assert score is not None
    assert score.n_trades == 10
    assert score.win_rate > 0.7
    assert score.roi > 0
    assert score.sharpe > 0
    assert score.avg_holding_minutes == pytest.approx(60.0)
    assert score.pct_closed_under_24h == 1.0  # all under 24h


def test_compute_score_holding_time_filter() -> None:
    # mix of short (60min) and long (3000min) trades
    short = [_make_trade(i, 5, 60) for i in range(7)]
    long_ = [_make_trade(i + 10, 5, 3000) for i in range(3)]
    score = compute_score(short + long_)
    assert score is not None
    assert score.pct_closed_under_24h == pytest.approx(0.7)
    assert score.median_holding_minutes < 1440


def test_compute_score_swing_trader_not_trackable() -> None:
    # swing trader: all trades held 5000 min (>48h)
    trades = [_make_trade(i, 5, 5000) for i in range(60)]
    score = compute_score(trades)
    assert score is not None
    assert not score.is_trackable()  # median_holding > 2880


def test_compute_score_good_trader_trackable() -> None:
    # good short-horizon trader
    trades = [_make_trade(i, pnl, 120) for i, pnl in enumerate([8] * 55 + [-3] * 5)]
    score = compute_score(trades)
    assert score is not None
    assert score.is_trackable()


def test_compute_score_returns_none_for_no_closed_trades() -> None:
    open_trade = WalletTrade(
        trade_id="t1",
        wallet_address="0xabc",
        market_id="m1",
        outcome="YES",
        side=OrderSide.BUY,
        price=Decimal("0.5"),
        size_usd=Decimal("100"),
        opened_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        closed_at=None,
        realized_pnl_usd=None,
    )
    assert compute_score([open_trade]) is None


def test_compute_score_max_drawdown() -> None:
    # big losing streak then recovery
    pnls = [-10, -10, -10, 5, 5, 5, 5, 5, 5, 5]
    trades = [_make_trade(i, p, 30) for i, p in enumerate(pnls)]
    score = compute_score(trades)
    assert score is not None
    assert score.max_drawdown > 0
