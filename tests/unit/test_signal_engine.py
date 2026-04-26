import yaml
from datetime import datetime, timezone
from decimal import Decimal

from app.data.models import OrderSide, TradeEvent
from app.signals.signal_engine import SignalEngine
from app.tracker.scoring import WalletScore


def _make_event() -> TradeEvent:
    return TradeEvent(
        id="tx1",
        market_id="mkt1",
        asset_id="asset1",
        outcome="YES",
        side=OrderSide.BUY,
        price=Decimal("0.5"),
        size=Decimal("100"),
        size_usd=Decimal("1500"),
        fee_usd=Decimal("0"),
        maker_address="0xmaker",
        taker_address="0xwhale",
        timestamp=datetime.now(tz=timezone.utc),
        tx_hash="0xtx",
    )


def test_process_event_generates_signal(tmp_path) -> None:
    config_path = tmp_path / "strategies.yaml"
    config_path.write_text(yaml.safe_dump({"strategies": {}}))

    engine = SignalEngine(str(config_path))
    event = _make_event()
    signals = engine.process_event(event, None)
    assert len(signals) == 1
    assert signals[0].strategy == "whale_copy"
    assert signals[0].market_id == "mkt1"


def test_process_event_deduplicates_signals(tmp_path) -> None:
    config_path = tmp_path / "strategies.yaml"
    config_path.write_text(yaml.safe_dump({"strategies": {}}))

    engine = SignalEngine(str(config_path))
    event = _make_event()
    first = engine.process_event(event, None)
    assert len(first) == 1
    second = engine.process_event(event, None)
    assert second == []


def test_process_event_skips_open_market(tmp_path) -> None:
    config_path = tmp_path / "strategies.yaml"
    config_path.write_text(yaml.safe_dump({"strategies": {}}))

    engine = SignalEngine(str(config_path))
    engine.open_market_ids.add("mkt1")
    event = _make_event()
    assert engine.process_event(event, None) == []
