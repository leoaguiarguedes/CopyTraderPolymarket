"""Circuit breaker — pauses trading if consecutive losses exceed historical norms.

Rule: if the last N consecutive closed positions each realized a PnL that is more
than ``threshold_sigma`` standard deviations below the historical mean PnL, the
circuit breaker trips and activates the kill switch.

Uses the actual distribution of historical PnL to detect outlier losses —
NOT an artificial "expected" value based on TP/SL params.

Example with threshold_sigma=2:
  - Historical mean PnL = -$0.10, std = $0.30
  - Threshold = -0.10 - 2 × 0.30 = -$0.70
  - A loss of -$5 is "bad" (well below threshold)
  - A loss of -$0.30 is "normal" (above threshold)
"""
from __future__ import annotations

import statistics
from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from app.utils.logger import get_logger

if TYPE_CHECKING:
    from app.execution.base import Position
    from app.risk.kill_switch import KillSwitch
    from app.utils.alerting import Alerter

log = get_logger(__name__)

_MIN_HISTORY = 5  # need at least this many trades before applying the circuit


@dataclass
class CircuitBreaker:
    """Tracks recent trade outcomes and trips kill switch on consecutive bad losses."""

    kill_switch: "KillSwitch"
    alerter: "Alerter | None" = None
    max_consecutive_losses: int = 3
    threshold_sigma: float = 2.0

    _history: deque[float] = field(default_factory=lambda: deque(maxlen=50))
    _consecutive_losses: int = field(default=0, init=False)

    async def record(self, position: "Position") -> None:
        """Call this whenever a position is closed to evaluate the circuit breaker."""
        if position.realized_pnl_usd is None:
            return

        # Don't re-trip if kill switch is already active
        if await self.kill_switch.is_active():
            return

        pnl = float(position.realized_pnl_usd)
        self._history.append(pnl)

        if pnl >= 0:
            self._consecutive_losses = 0
            return

        # Not enough history — skip circuit breaker evaluation
        if len(self._history) < _MIN_HISTORY:
            return

        mean = statistics.mean(self._history)
        std = self._estimate_std()
        threshold = mean - self.threshold_sigma * std  # e.g., mean - 2σ

        if pnl < threshold:
            self._consecutive_losses += 1
            log.warning(
                "circuit_breaker.bad_loss",
                position_id=position.position_id[:8],
                pnl=f"{pnl:+.4f}",
                mean=f"{mean:+.4f}",
                threshold=f"{threshold:.4f}",
                consecutive=self._consecutive_losses,
            )
        else:
            self._consecutive_losses = 0

        if self._consecutive_losses >= self.max_consecutive_losses:
            reason = (
                f"circuit_breaker: {self._consecutive_losses} consecutive losses "
                f"each >{self.threshold_sigma:.1f}σ below historical mean"
            )
            await self.kill_switch.activate(reason)
            if self.alerter:
                await self.alerter.circuit_breaker(
                    self._consecutive_losses, self.threshold_sigma
                )
            self._consecutive_losses = 0
            log.error("circuit_breaker.tripped", reason=reason)

    def _estimate_std(self) -> float:
        pnls = list(self._history)
        if len(pnls) < 2:
            return 1.0
        try:
            return max(statistics.stdev(pnls), 1e-4)
        except statistics.StatisticsError:
            return 1.0

    @property
    def consecutive_losses(self) -> int:
        return self._consecutive_losses
