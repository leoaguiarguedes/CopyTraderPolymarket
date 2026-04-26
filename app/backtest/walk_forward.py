"""Walk-forward validation — avoids overfitting by testing on unseen future data.

Split:
  in_sample  (60% of window) → strategy is "trained" / tuned here
  out_sample (40% of window) → strategy runs with SAME params on future data

Divergence check: if |in_sharpe - out_sharpe| / max(|in_sharpe|, 0.01) > 0.30
the strategy is considered overfit for those params.

Both halves run independently through BacktestEngine so the full
signal→risk→executor pipeline is exercised in each period.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from app.backtest.engine import BacktestEngine
from app.backtest.metrics import BacktestMetrics, compute_metrics
from app.utils.logger import get_logger

log = get_logger(__name__)


@dataclass
class WalkForwardResult:
    run_id: str
    strategy: str
    full_start: datetime
    full_end: datetime
    split_date: datetime          # boundary between in/out sample
    wallets: list[str]
    params: dict[str, Any]

    in_start: datetime = field(init=False)
    in_end: datetime = field(init=False)
    out_start: datetime = field(init=False)
    out_end: datetime = field(init=False)

    in_sample: BacktestMetrics | None = None
    out_sample: BacktestMetrics | None = None

    in_signals: int = 0
    out_signals: int = 0
    in_positions: int = 0
    out_positions: int = 0

    overfit_flag: bool = False
    divergence: float = 0.0       # |in_sharpe - out_sharpe| / max(|in_sharpe|, 0.01)

    error: str = ""
    finished_at: datetime | None = None

    def __post_init__(self) -> None:
        total = (self.full_end - self.full_start).total_seconds()
        split_ts = self.full_start.timestamp() + total * 0.60
        self.split_date = datetime.fromtimestamp(split_ts, tz=timezone.utc)
        self.in_start = self.full_start
        self.in_end = self.split_date
        self.out_start = self.split_date + timedelta(seconds=1)
        self.out_end = self.full_end


class WalkForwardEngine:
    _OVERFIT_THRESHOLD = 0.30

    def __init__(self, backtest_engine: BacktestEngine | None = None) -> None:
        self._engine = backtest_engine or BacktestEngine()

    async def run(
        self,
        strategy: str,
        start_date: datetime,
        end_date: datetime,
        wallets: list[str],
        params: dict[str, Any] | None = None,
        capital_usd: float = 10_000.0,
    ) -> WalkForwardResult:
        run_id = str(uuid.uuid4())
        result = WalkForwardResult(
            run_id=run_id,
            strategy=strategy,
            full_start=start_date,
            full_end=end_date,
            split_date=start_date,   # placeholder, overwritten in __post_init__
            wallets=wallets,
            params=params or {},
        )

        try:
            await self._execute(result, strategy, wallets, params or {}, capital_usd)
        except Exception as exc:
            log.error("walk_forward.error", run_id=run_id[:8], error=str(exc))
            result.error = str(exc)
        finally:
            result.finished_at = datetime.now(tz=timezone.utc)

        return result

    async def _execute(
        self,
        result: WalkForwardResult,
        strategy: str,
        wallets: list[str],
        params: dict[str, Any],
        capital_usd: float,
    ) -> None:
        log.info(
            "walk_forward.start",
            run_id=result.run_id[:8],
            strategy=strategy,
            in_sample=f"{result.in_start.date()} → {result.in_end.date()}",
            out_sample=f"{result.out_start.date()} → {result.out_end.date()}",
        )

        # Run in-sample
        in_bt = await self._engine.run(
            strategy=strategy,
            start_date=result.in_start,
            end_date=result.in_end,
            wallets=wallets,
            params=params,
            capital_usd=capital_usd,
        )
        result.in_signals = in_bt.signals_total
        result.in_positions = len(in_bt.positions)
        result.in_sample = compute_metrics(in_bt.positions)

        # Run out-of-sample with the SAME params (no re-tuning)
        out_bt = await self._engine.run(
            strategy=strategy,
            start_date=result.out_start,
            end_date=result.out_end,
            wallets=wallets,
            params=params,
            capital_usd=capital_usd,
        )
        result.out_signals = out_bt.signals_total
        result.out_positions = len(out_bt.positions)
        result.out_sample = compute_metrics(out_bt.positions)

        # Divergence check
        in_sharpe = result.in_sample.sharpe if result.in_sample else 0.0
        out_sharpe = result.out_sample.sharpe if result.out_sample else 0.0
        result.divergence = abs(in_sharpe - out_sharpe) / max(abs(in_sharpe), 0.01)
        result.overfit_flag = result.divergence > self._OVERFIT_THRESHOLD

        log.info(
            "walk_forward.done",
            run_id=result.run_id[:8],
            in_sharpe=f"{in_sharpe:.3f}",
            out_sharpe=f"{out_sharpe:.3f}",
            divergence=f"{result.divergence:.2f}",
            overfit=result.overfit_flag,
        )
