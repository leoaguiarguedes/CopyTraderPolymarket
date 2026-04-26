"""Grid search — exhaustive parameter sweep over strategies.yaml knobs.

Usage:
    engine = GridSearchEngine()
    result = await engine.run(
        strategy="whale_copy",
        start_date=..., end_date=..., wallets=[...],
        param_grid={
            "min_trade_size_usd": [50, 100, 250],
            "tp_pct": [0.10, 0.15, 0.20],
            "sl_pct": [0.05, 0.07, 0.10],
        },
    )
    # result.top_configs[:10]  → sorted by Sharpe desc

Total combinations = product of all list lengths.
A hard cap (_MAX_COMBINATIONS) prevents accidental DoS.
"""
from __future__ import annotations

import itertools
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.backtest.engine import BacktestEngine
from app.backtest.metrics import BacktestMetrics, compute_metrics
from app.utils.logger import get_logger

log = get_logger(__name__)

_MAX_COMBINATIONS = 200


@dataclass
class GridConfig:
    params: dict[str, Any]
    n_trades: int
    total_pnl_usd: float
    roi: float
    sharpe: float
    win_rate: float
    max_drawdown: float
    profit_factor: float
    pct_timeout_exits: float


@dataclass
class GridSearchResult:
    run_id: str
    strategy: str
    start_date: datetime
    end_date: datetime
    wallets: list[str]
    param_grid: dict[str, list[Any]]
    total_combinations: int
    completed: int
    top_configs: list[GridConfig] = field(default_factory=list)
    error: str = ""
    finished_at: datetime | None = None


class GridSearchEngine:
    def __init__(self, backtest_engine: BacktestEngine | None = None) -> None:
        self._engine = backtest_engine or BacktestEngine()

    async def run(
        self,
        strategy: str,
        start_date: datetime,
        end_date: datetime,
        wallets: list[str],
        param_grid: dict[str, list[Any]],
        capital_usd: float = 10_000.0,
        top_n: int = 10,
    ) -> GridSearchResult:
        run_id = str(uuid.uuid4())
        result = GridSearchResult(
            run_id=run_id,
            strategy=strategy,
            start_date=start_date,
            end_date=end_date,
            wallets=wallets,
            param_grid=param_grid,
            total_combinations=0,
            completed=0,
        )

        try:
            await self._execute(result, strategy, start_date, end_date, wallets, param_grid, capital_usd, top_n)
        except Exception as exc:
            log.error("grid_search.error", run_id=run_id[:8], error=str(exc))
            result.error = str(exc)
        finally:
            result.finished_at = datetime.now(tz=timezone.utc)

        return result

    async def _execute(
        self,
        result: GridSearchResult,
        strategy: str,
        start_date: datetime,
        end_date: datetime,
        wallets: list[str],
        param_grid: dict[str, list[Any]],
        capital_usd: float,
        top_n: int,
    ) -> None:
        keys = list(param_grid.keys())
        values = [param_grid[k] for k in keys]
        combinations = list(itertools.product(*values))

        if len(combinations) > _MAX_COMBINATIONS:
            raise ValueError(
                f"Grid has {len(combinations)} combinations (max {_MAX_COMBINATIONS}). "
                "Reduce the grid or increase _MAX_COMBINATIONS."
            )

        result.total_combinations = len(combinations)
        log.info(
            "grid_search.start",
            strategy=strategy,
            combinations=len(combinations),
            run_id=result.run_id[:8],
        )

        configs: list[GridConfig] = []

        for combo in combinations:
            params = dict(zip(keys, combo))
            try:
                bt = await self._engine.run(
                    strategy=strategy,
                    start_date=start_date,
                    end_date=end_date,
                    wallets=wallets,
                    params=params,
                    capital_usd=capital_usd,
                )
                metrics = compute_metrics(bt.positions)
                result.completed += 1

                if metrics is None:
                    log.debug("grid_search.no_metrics", params=params)
                    continue

                pf = metrics.profit_factor if metrics.profit_factor != float("inf") else 9999.0
                configs.append(
                    GridConfig(
                        params=params,
                        n_trades=metrics.n_trades,
                        total_pnl_usd=metrics.total_pnl_usd,
                        roi=metrics.roi,
                        sharpe=metrics.sharpe,
                        win_rate=metrics.win_rate,
                        max_drawdown=metrics.max_drawdown,
                        profit_factor=pf,
                        pct_timeout_exits=metrics.pct_timeout_exits,
                    )
                )
            except Exception as exc:
                log.warning(
                    "grid_search.combo_error",
                    params=params,
                    error=str(exc)[:80],
                )
                result.completed += 1

        # Sort by Sharpe desc, break ties by ROI
        configs.sort(key=lambda c: (c.sharpe, c.roi), reverse=True)
        result.top_configs = configs[:top_n]

        log.info(
            "grid_search.done",
            run_id=result.run_id[:8],
            completed=result.completed,
            configs_with_trades=len(configs),
            top_n=len(result.top_configs),
        )
