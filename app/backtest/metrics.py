"""Backtest performance metrics.

Input: list of closed Position objects from BacktestResult.positions.
Output: BacktestMetrics dataclass with all computed stats.

Key metric: pct_timeout_exits — if >50% of trades exit by timeout the
strategy's max_holding_minutes is too tight or the TP targets are unrealistic.
"""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from decimal import Decimal
from typing import Sequence

from app.execution.base import Position


@dataclass
class BacktestMetrics:
    n_trades: int
    n_wins: int
    n_losses: int
    win_rate: float             # n_wins / n_trades
    total_pnl_usd: float
    roi: float                  # total_pnl / total_invested
    avg_pnl_usd: float          # mean PnL per trade
    avg_win_usd: float
    avg_loss_usd: float
    profit_factor: float        # gross_profit / gross_loss  (inf if no losses)
    expectancy_usd: float       # win_rate * avg_win - loss_rate * avg_loss
    sharpe: float               # mean(returns) / std(returns) — simplified
    max_drawdown: float         # worst peak-to-trough equity drop (fraction)
    avg_holding_minutes: float
    median_holding_minutes: float
    pct_tp_exits: float
    pct_sl_exits: float
    pct_timeout_exits: float
    equity_curve: list[float]   # cumulative PnL after each trade


def compute_metrics(positions: Sequence[Position]) -> BacktestMetrics | None:
    """Return metrics for a list of closed positions, or None if empty."""
    closed = [
        p for p in positions
        if p.closed_at is not None and p.realized_pnl_usd is not None
    ]
    if not closed:
        return None

    closed = sorted(closed, key=lambda p: p.closed_at)  # type: ignore[arg-type]

    pnls = [float(p.realized_pnl_usd) for p in closed]  # type: ignore[arg-type]
    invested = [float(p.size_usd) for p in closed]

    n = len(closed)
    wins = [v for v in pnls if v > 0]
    losses = [v for v in pnls if v <= 0]

    total_pnl = sum(pnls)
    total_invested = sum(invested)
    roi = total_pnl / total_invested if total_invested > 0 else 0.0

    gross_profit = sum(wins) if wins else 0.0
    gross_loss = abs(sum(losses)) if losses else 0.0
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float("inf")

    win_rate = len(wins) / n
    avg_win = statistics.mean(wins) if wins else 0.0
    avg_loss = abs(statistics.mean(losses)) if losses else 0.0
    expectancy = win_rate * avg_win - (1 - win_rate) * avg_loss

    # Simplified Sharpe: per-trade return (pnl / size)
    returns = [p / max(i, 1e-9) for p, i in zip(pnls, invested)]
    if len(returns) >= 2:
        mean_r = statistics.mean(returns)
        std_r = statistics.stdev(returns)
        sharpe = mean_r / std_r if std_r > 0 else 0.0
    else:
        sharpe = 0.0

    # Max drawdown over equity curve
    equity: list[float] = []
    running = 0.0
    for pnl in pnls:
        running += pnl
        equity.append(running)

    peak = equity[0]
    max_dd = 0.0
    for e in equity:
        if e > peak:
            peak = e
        dd = (peak - e) / max(abs(peak), 1e-9) if peak > 0 else 0.0
        if dd > max_dd:
            max_dd = dd

    # Holding times
    holding_mins = []
    for p in closed:
        if p.opened_at and p.closed_at:
            mins = (p.closed_at - p.opened_at).total_seconds() / 60
            holding_mins.append(mins)

    avg_holding = statistics.mean(holding_mins) if holding_mins else 0.0
    median_holding = statistics.median(holding_mins) if holding_mins else 0.0

    # Exit reasons
    exit_reasons = [p.exit_reason for p in closed]
    pct_tp = exit_reasons.count("tp") / n
    pct_sl = exit_reasons.count("sl") / n
    pct_timeout = exit_reasons.count("timeout") / n

    return BacktestMetrics(
        n_trades=n,
        n_wins=len(wins),
        n_losses=len(losses),
        win_rate=win_rate,
        total_pnl_usd=total_pnl,
        roi=roi,
        avg_pnl_usd=statistics.mean(pnls),
        avg_win_usd=avg_win,
        avg_loss_usd=avg_loss,
        profit_factor=profit_factor,
        expectancy_usd=expectancy,
        sharpe=sharpe,
        max_drawdown=max_dd,
        avg_holding_minutes=avg_holding,
        median_holding_minutes=median_holding,
        pct_tp_exits=pct_tp,
        pct_sl_exits=pct_sl,
        pct_timeout_exits=pct_timeout,
        equity_curve=equity,
    )
