import asyncio
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from dataclasses import replace

from app.data.models import Market
from app.execution.base import BaseExecutor, Position
from app.execution.exit_manager import ExitManager
from app.risk.kill_switch import KillSwitch


class DummyExecutor(BaseExecutor):
    def __init__(self, current_price: Decimal) -> None:
        self.current_price = current_price
        self.closed_positions: list[Position] = []

    async def open_position(self, signal, capital_usd):
        raise NotImplementedError

    async def close_position(self, position: Position, reason: str) -> Position:
        closed = replace(
            position,
            closed_at=datetime.now(tz=timezone.utc),
            exit_price=self.current_price,
            realized_pnl_usd=Decimal("1.0"),
            exit_reason=reason,
        )
        self.closed_positions.append(closed)
        return closed

    async def get_current_price(self, asset_id: str) -> Decimal | None:
        return self.current_price


class DummyKillSwitch(KillSwitch):
    def __init__(self, active: bool = False) -> None:
        self._active = active

    async def is_active(self) -> bool:
        return self._active


def _make_position(reason: str, opened_at: datetime, max_holding_minutes: int) -> Position:
    return Position(
        position_id="p1",
        signal_id="sig1",
        strategy="whale_copy",
        market_id="mkt1",
        asset_id="asset1",
        side="BUY",
        entry_price=Decimal("0.5"),
        size_usd=Decimal("100"),
        size_tokens=Decimal("200"),
        tp_price=Decimal("0.55"),
        sl_price=Decimal("0.45"),
        max_holding_minutes=max_holding_minutes,
        opened_at=opened_at,
    )


async def _run_check(manager: ExitManager, cfg: dict) -> None:
    await manager._check_all_positions(cfg)


def test_exit_manager_closes_on_timeout(tmp_path) -> None:
    executor = DummyExecutor(Decimal("0.5"))
    manager = ExitManager(executor, DummyKillSwitch(False), None, strategies_yaml_path=str(tmp_path / "exit.yaml"))
    manager.positions["p1"] = _make_position("test", datetime.now(tz=timezone.utc) - timedelta(minutes=61), 60)

    cfg = {
        "trailing_stop_enabled": True,
        "trailing_stop_activation_pct": 0.10,
        "trailing_stop_distance_pct": 0.05,
        "expiry_close_buffer_minutes": 360,
    }
    asyncio.run(_run_check(manager, cfg))
    assert "p1" not in manager.positions
    assert executor.closed_positions[0].exit_reason == "timeout"


def test_exit_manager_closes_on_kill_switch(tmp_path) -> None:
    executor = DummyExecutor(Decimal("0.5"))
    manager = ExitManager(executor, DummyKillSwitch(True), None, strategies_yaml_path=str(tmp_path / "exit.yaml"))
    manager.positions["p1"] = _make_position("test", datetime.now(tz=timezone.utc), 60)

    cfg = {
        "trailing_stop_enabled": True,
        "trailing_stop_activation_pct": 0.10,
        "trailing_stop_distance_pct": 0.05,
        "expiry_close_buffer_minutes": 360,
    }
    asyncio.run(_run_check(manager, cfg))
    assert executor.closed_positions[0].exit_reason == "kill_switch"
