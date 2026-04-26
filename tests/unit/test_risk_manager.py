from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.data.models import Market, OrderBook, OrderBookLevel, OrderSide
from app.risk.kill_switch import KillSwitch
from app.risk.risk_manager import RiskManager
from app.signals.models import Signal


class DummyKillSwitch(KillSwitch):
    def __init__(self, active: bool = False) -> None:
        self._active = active

    async def is_active(self) -> bool:
        return self._active

    async def activate(self, reason: str = "") -> None:
        self._active = True

    async def deactivate(self) -> None:
        self._active = False


class DummyOrderBook:
    def __init__(self, depth: Decimal) -> None:
        self._depth = depth

    def depth_usd(self, side: str = "ask", levels: int = 5) -> Decimal:
        return self._depth


def _make_signal(size_pct: float = 0.02) -> Signal:
    return Signal(
        signal_id="sig1",
        strategy="whale_copy",
        market_id="mkt1",
        asset_id="asset1",
        side=OrderSide.BUY,
        confidence=0.5,
        entry_price=Decimal("0.5"),
        size_pct=size_pct,
        tp_pct=0.15,
        sl_pct=0.07,
        max_holding_minutes=60,
        source_wallet="0xwhale",
        timestamp=datetime.now(tz=timezone.utc),
        reason="test",
    )


def test_risk_manager_rejects_kill_switch(tmp_path) -> None:
    ks = DummyKillSwitch(active=True)
    rm = RiskManager(ks, strategies_yaml_path=str(tmp_path / "risk.yaml"))
    decision = pytest_run(rm.validate(_make_signal(), None, None))
    assert not decision.approved
    assert decision.reason == "kill_switch_active"


def test_risk_manager_rejects_due_to_low_liquidity(tmp_path) -> None:
    ks = DummyKillSwitch(active=False)
    rm = RiskManager(ks, strategies_yaml_path=str(tmp_path / "risk.yaml"))
    market = Market(
        condition_id="mkt1",
        question="q",
        end_date=datetime.now(tz=timezone.utc) + timedelta(hours=3),
        liquidity_usd=Decimal("1000"),
    )
    decision = pytest_run(rm.validate(_make_signal(), market, DummyOrderBook(1000)))
    assert not decision.approved
    assert "liquidity" in decision.reason


def test_risk_manager_rejects_due_to_ttm(tmp_path) -> None:
    ks = DummyKillSwitch(active=False)
    rm = RiskManager(ks, strategies_yaml_path=str(tmp_path / "risk.yaml"))
    market = Market(
        condition_id="mkt1",
        question="q",
        end_date=datetime.now(tz=timezone.utc) + timedelta(minutes=30),
        liquidity_usd=Decimal("10000"),
    )
    decision = pytest_run(rm.validate(_make_signal(), market, DummyOrderBook(10000)))
    assert not decision.approved
    assert "ttm_" in decision.reason


def test_risk_manager_rejects_due_to_depth(tmp_path) -> None:
    ks = DummyKillSwitch(active=False)
    rm = RiskManager(ks, strategies_yaml_path=str(tmp_path / "risk.yaml"))
    market = Market(
        condition_id="mkt1",
        question="q",
        end_date=datetime.now(tz=timezone.utc) + timedelta(hours=5),
        liquidity_usd=Decimal("10000"),
    )
    decision = pytest_run(rm.validate(_make_signal(), market, DummyOrderBook(100)))
    assert not decision.approved
    assert "depth" in decision.reason


def test_risk_manager_approves_valid_signal(tmp_path) -> None:
    ks = DummyKillSwitch(active=False)
    rm = RiskManager(ks, strategies_yaml_path=str(tmp_path / "risk.yaml"))
    market = Market(
        condition_id="mkt1",
        question="q",
        end_date=datetime.now(tz=timezone.utc) + timedelta(hours=5),
        liquidity_usd=Decimal("10000"),
    )
    decision = pytest_run(rm.validate(_make_signal(), market, DummyOrderBook(10000)))
    assert decision.approved
    assert decision.reason == "ok"


def pytest_run(coro):
    import asyncio

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()
