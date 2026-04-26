from decimal import Decimal

import pytest

from app.signals.confidence import compute_confidence
from app.tracker.scoring import WalletScore


def test_compute_confidence_unknown_wallet() -> None:
    confidence = compute_confidence(None, strategy_weight=0.35)
    assert confidence == pytest.approx(0.105, rel=1e-6)


def test_compute_confidence_wallet_score() -> None:
    score = WalletScore(
        wallet_address="0xabc",
        window_days=30,
        n_trades=20,
        roi=0.5,
        sharpe=1.5,
        win_rate=0.8,
        max_drawdown=0.2,
        total_volume_usd=10000.0,
        avg_holding_minutes=120.0,
        median_holding_minutes=90.0,
        pct_closed_under_24h=0.9,
    )
    confidence = compute_confidence(score, strategy_weight=0.5)
    assert 0.0 < confidence <= 1.0
    assert confidence > 0.3


def test_compute_confidence_clamps_to_zero_and_one() -> None:
    score = WalletScore(
        wallet_address="0xabc",
        window_days=30,
        n_trades=20,
        roi=-1.0,
        sharpe=-1.0,
        win_rate=0.0,
        max_drawdown=0.0,
        total_volume_usd=1000.0,
        avg_holding_minutes=120.0,
        median_holding_minutes=90.0,
        pct_closed_under_24h=0.0,
    )
    assert compute_confidence(score, strategy_weight=0.5) == 0.0
    assert compute_confidence(score, strategy_weight=10.0) == 0.0
