"""Fractional Kelly position sizing.

Kelly formula:
    f* = (p * b - q) / b
    where:
        p = win probability
        b = average win / average loss ratio (odds)
        q = 1 - p

Fractional Kelly: actual_fraction = kelly_fraction * f*

The result is clamped between min_pct and max_pct to prevent reckless sizing.
When no history is available, falls back to the default size from the signal.
"""
from __future__ import annotations

import statistics
from collections import deque
from dataclasses import dataclass, field
from decimal import Decimal
from typing import TYPE_CHECKING

from app.utils.logger import get_logger

if TYPE_CHECKING:
    from app.execution.base import Position

log = get_logger(__name__)

_MIN_SAMPLES = 10  # need at least this many closed trades to use Kelly


@dataclass
class KellySizer:
    """Computes fractional Kelly position size from closed-trade history."""

    kelly_fraction: float = 0.25   # how much of full Kelly to use
    min_pct: float = 0.005         # 0.5% floor
    max_pct: float = 0.05          # 5% ceiling (same as paper executor safety cap)
    window: int = 100              # how many recent trades to use

    _history: deque[float] = field(default_factory=lambda: deque(maxlen=100))

    def record(self, position: "Position") -> None:
        """Register a closed position's PnL for future sizing estimates."""
        if position.realized_pnl_usd is None or position.size_usd == 0:
            return
        # Normalise PnL as a fraction of trade size
        pnl_pct = float(position.realized_pnl_usd) / float(position.size_usd)
        self._history.append(pnl_pct)

    def size_pct(self, signal_size_pct: float) -> float:
        """Return the recommended position size as a fraction of capital.

        Falls back to ``signal_size_pct`` clamped to [min_pct, max_pct] when
        there is not enough history to compute Kelly.
        """
        if len(self._history) < _MIN_SAMPLES:
            return max(self.min_pct, min(self.max_pct, signal_size_pct))

        wins = [r for r in self._history if r > 0]
        losses = [abs(r) for r in self._history if r < 0]

        if not wins:
            # No winning trades at all — Kelly is negative; use minimum
            log.warning("kelly.no_wins", n=len(self._history))
            return self.min_pct

        if not losses:
            # No losing trades — Kelly unbounded; cap at maximum
            return self.max_pct

        p = len(wins) / len(self._history)
        q = 1.0 - p
        avg_win = statistics.mean(wins)
        avg_loss = statistics.mean(losses)

        if avg_loss == 0:
            return self.max_pct

        b = avg_win / avg_loss  # win/loss ratio
        f_star = (p * b - q) / b

        if f_star <= 0:
            # Negative edge — Kelly says don't trade; use minimum
            log.warning("kelly.negative_edge", p=round(p, 3), b=round(b, 3), f_star=round(f_star, 4))
            return self.min_pct

        fractional = self.kelly_fraction * f_star
        result = max(self.min_pct, min(self.max_pct, fractional))

        log.debug(
            "kelly.computed",
            p=round(p, 3),
            b=round(b, 3),
            f_star=round(f_star, 4),
            fractional=round(fractional, 4),
            applied=round(result, 4),
            n=len(self._history),
        )
        return result

    @property
    def sample_count(self) -> int:
        return len(self._history)

    @property
    def has_enough_history(self) -> bool:
        return len(self._history) >= _MIN_SAMPLES
