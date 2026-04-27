"""Tests for CircuitBreaker."""
import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

from app.execution.base import Position
from app.execution.circuit_breaker import CircuitBreaker, _MIN_HISTORY


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
        exit_reason="sl",
    )


def _make_kill_switch():
    """Mock kill switch that actually tracks its activation state."""
    _active = [False]

    ks = MagicMock()

    async def _activate(reason=""):
        _active[0] = True

    async def _is_active():
        return _active[0]

    ks.activate = AsyncMock(side_effect=_activate)
    ks.is_active = AsyncMock(side_effect=_is_active)
    return ks


def _build_history(cb: CircuitBreaker, pnls: list[float]) -> None:
    """Synchronously seed history without triggering circuit logic."""
    for pnl in pnls:
        cb._history.append(pnl)


def test_winning_trade_resets_streak():
    async def _run():
        ks = _make_kill_switch()
        cb = CircuitBreaker(kill_switch=ks, max_consecutive_losses=3, threshold_sigma=2.0)
        # Seed history with mixed normal pnls
        _build_history(cb, [-0.5, 0.3, -0.2, 0.8, -0.1])

        # Feed a few "normal" losses then a win
        await cb.record(_make_position(-0.3))
        assert cb.consecutive_losses == 0  # within normal range

        await cb.record(_make_position(5.0))  # win resets
        assert cb.consecutive_losses == 0
        ks.activate.assert_not_called()

    asyncio.run(_run())


def test_small_losses_within_std_do_not_trigger():
    async def _run():
        ks = _make_kill_switch()
        cb = CircuitBreaker(kill_switch=ks, max_consecutive_losses=3, threshold_sigma=2.0)
        # History: mean≈-0.5, std≈0.3 → threshold ≈ -0.5 - 2*0.3 = -1.1
        _build_history(cb, [-0.4, -0.5, -0.6, -0.5, -0.4, -0.6, -0.5])

        # Loss of -0.8 is above threshold (-1.1) → not bad
        for _ in range(5):
            await cb.record(_make_position(-0.8))

        ks.activate.assert_not_called()

    asyncio.run(_run())


def test_skips_positions_without_pnl():
    async def _run():
        ks = _make_kill_switch()
        cb = CircuitBreaker(kill_switch=ks, max_consecutive_losses=3)
        pos = _make_position(0.0)
        pos = Position(**{**pos.__dict__, "realized_pnl_usd": None})
        await cb.record(pos)
        ks.activate.assert_not_called()

    asyncio.run(_run())


def test_skips_when_kill_switch_already_active():
    async def _run():
        ks = _make_kill_switch()
        await ks.activate("pre-existing reason")  # activate before any trades
        cb = CircuitBreaker(kill_switch=ks, max_consecutive_losses=3, threshold_sigma=0.5)
        _build_history(cb, [-0.1, -0.1, -0.1, -0.1, -0.1])

        for _ in range(5):
            await cb.record(_make_position(-1000.0))

        # activate should NOT have been called again by circuit breaker
        assert ks.activate.call_count == 1  # only the pre-existing call

    asyncio.run(_run())


def test_massive_consecutive_losses_trip_breaker():
    async def _run():
        ks = _make_kill_switch()
        alerter = MagicMock()
        alerter.circuit_breaker = AsyncMock()
        cb = CircuitBreaker(
            kill_switch=ks,
            alerter=alerter,
            max_consecutive_losses=3,
            threshold_sigma=1.0,
        )
        # History: mostly small losses → std is small → threshold is near mean
        _build_history(cb, [-0.1, 0.2, -0.1, 0.1, -0.1, 0.3, -0.1])

        # Now feed 3 catastrophic losses (well below mean - 1σ)
        for _ in range(3):
            await cb.record(_make_position(-1000.0))

        ks.activate.assert_called_once()
        alerter.circuit_breaker.assert_called_once()

    asyncio.run(_run())


def test_streak_resets_after_trip():
    async def _run():
        ks = _make_kill_switch()
        cb = CircuitBreaker(kill_switch=ks, max_consecutive_losses=3, threshold_sigma=1.0)
        _build_history(cb, [-0.1, 0.2, -0.1, 0.1, -0.1])

        for _ in range(3):
            await cb.record(_make_position(-1000.0))

        assert cb.consecutive_losses == 0  # reset after trip

    asyncio.run(_run())


def test_insufficient_history_skips_evaluation():
    async def _run():
        ks = _make_kill_switch()
        cb = CircuitBreaker(kill_switch=ks, max_consecutive_losses=3, threshold_sigma=2.0)
        # Fewer than _MIN_HISTORY samples → circuit breaker inactive

        for _ in range(_MIN_HISTORY - 1):
            await cb.record(_make_position(-1000.0))

        ks.activate.assert_not_called()

    asyncio.run(_run())
