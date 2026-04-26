from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.data.models import OrderSide, TradeEvent, WalletTrade
from app.signals.strategies import consensus, momentum_odds, whale_copy
from app.signals.models import Signal
from app.tracker.scoring import WalletScore


def _make_event(wallet: str, timestamp: datetime, size_usd: float = 1500.0) -> TradeEvent:
    return TradeEvent(
        id=f"tx-{wallet}",
        market_id="mkt1",
        asset_id="asset1",
        outcome="YES",
        side=OrderSide.BUY,
        price=Decimal("0.5"),
        size=Decimal("100"),
        size_usd=Decimal(str(size_usd)),
        fee_usd=Decimal("0"),
        maker_address="0xmaker",
        taker_address=wallet,
        timestamp=timestamp,
        tx_hash="0xtx",
    )


def _wallet_score() -> WalletScore:
    return WalletScore(
        wallet_address="0xwallet",
        window_days=30,
        n_trades=50,
        roi=0.5,
        sharpe=1.0,
        win_rate=0.8,
        max_drawdown=0.2,
        total_volume_usd=10000.0,
        avg_holding_minutes=120.0,
        median_holding_minutes=90.0,
        pct_closed_under_24h=0.9,
    )


def test_whale_copy_creates_signal_when_eligible() -> None:
    event = _make_event("0xwhale", datetime.now(tz=timezone.utc), 2000.0)
    sig = whale_copy.evaluate(event, _wallet_score(), {"enabled": True}, set())
    assert isinstance(sig, Signal)
    assert sig.strategy == "whale_copy"


def test_whale_copy_rejects_small_trade() -> None:
    event = _make_event("0xwhale", datetime.now(tz=timezone.utc), 500.0)
    assert whale_copy.evaluate(event, _wallet_score(), {"enabled": True}, set()) is None


def test_consensus_accumulator_triggers_signal() -> None:
    acc = consensus.ConsensusAccumulator()
    now = datetime.now(tz=timezone.utc)
    config = {"enabled": True, "min_wallets": 2, "time_window_minutes": 10}

    first = acc.on_event(_make_event("0x1", now - timedelta(minutes=1)), _wallet_score(), config, set())
    assert first is None
    second = acc.on_event(_make_event("0x2", now), _wallet_score(), config, set())
    assert second is not None
    assert second.strategy == "consensus"


def test_momentum_odds_requires_whale_confirmation() -> None:
    acc = momentum_odds.MomentumOddsAccumulator()
    now = datetime.now(tz=timezone.utc)
    config = {"enabled": True, "min_odds_move_pct": 1, "odds_window_minutes": 30, "require_whale_confirmation": True}

    small = _make_event("0x1", now - timedelta(minutes=20), 500.0)
    assert acc.on_event(small, _wallet_score(), config, set()) is None


def test_momentum_odds_creates_signal_on_momentum() -> None:
    acc = momentum_odds.MomentumOddsAccumulator()
    now = datetime.now(tz=timezone.utc)
    config = {"enabled": True, "min_odds_move_pct": 1, "odds_window_minutes": 30, "require_whale_confirmation": True}

    acc.on_event(_make_event("0x1", now - timedelta(minutes=20), 2000.0), _wallet_score(), config, set())
    event = _make_event("0x2", now, 2000.0)
    event = event.__class__(
        **{**event.__dict__, "price": Decimal("0.6")}
    )
    assert acc.on_event(event, _wallet_score(), config, set()) is not None
