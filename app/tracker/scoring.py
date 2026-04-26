"""Wallet scoring — quality filter to avoid copying lucky/bad traders.

Metrics computed:
- roi: total realized PnL / total invested
- sharpe: mean(trade_returns) / std(trade_returns)  (simplified, not annualized)
- win_rate: fraction of trades with positive PnL
- max_drawdown: worst peak-to-trough equity drop
- avg/median_holding_minutes: holding time distribution
- pct_closed_under_24h: fraction of trades held < 1440 min (our key short-horizon filter)

Filters for short-horizon strategy:
  n_trades >= 50
  sharpe >= 1.0
  max_drawdown <= 0.30
  median_holding_minutes <= 2880   (48h)
  pct_closed_under_24h >= 0.60
"""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from decimal import Decimal

from app.data.models import OrderSide, WalletTrade
from app.utils.logger import get_logger

log = get_logger(__name__)


@dataclass
class WalletScore:
    wallet_address: str
    window_days: int
    n_trades: int
    roi: float
    sharpe: float
    win_rate: float
    max_drawdown: float
    total_volume_usd: float
    avg_holding_minutes: float
    median_holding_minutes: float
    pct_closed_under_24h: float

    def is_trackable(
        self,
        min_trades: int = 20,
        min_sharpe: float = 0.1,
        min_roi: float = 0.0,
        max_drawdown: float = 0.50,
        max_median_holding_minutes: float = 2880.0,
        min_pct_under_24h: float = 0.50,
    ) -> bool:
        """Quality filter for short-horizon copy trading.

        Thresholds are calibrated for prediction market scalping, where binary
        outcomes create inherently high return variance (low Sharpe is normal).
        ROI and drawdown are the primary quality gates; Sharpe is a secondary
        sanity check (positive, not 1.0+).
        """
        return (
            self.n_trades >= min_trades
            and self.sharpe >= min_sharpe
            and self.roi >= min_roi
            and self.max_drawdown <= max_drawdown
            and self.median_holding_minutes <= max_median_holding_minutes
            and self.pct_closed_under_24h >= min_pct_under_24h
        )

    def summary(self) -> dict[str, float | int | str]:
        return {
            "wallet": self.wallet_address,
            "window_days": self.window_days,
            "n_trades": self.n_trades,
            "roi": round(self.roi, 4),
            "sharpe": round(self.sharpe, 3),
            "win_rate": round(self.win_rate, 3),
            "max_drawdown": round(self.max_drawdown, 3),
            "total_volume_usd": round(self.total_volume_usd, 2),
            "avg_holding_min": round(self.avg_holding_minutes, 1),
            "median_holding_min": round(self.median_holding_minutes, 1),
            "pct_under_24h": round(self.pct_closed_under_24h, 3),
            "trackable": self.is_trackable(),
            "trackable_reason": self._trackable_reason(),
        }

    def _trackable_reason(self) -> str:
        """Human-readable reason why a wallet is/isn't trackable."""
        fails = []
        if self.n_trades < 20:
            fails.append(f"n_trades={self.n_trades}<20")
        if self.sharpe < 0.1:
            fails.append(f"sharpe={self.sharpe:.2f}<0.1")
        if self.roi < 0.0:
            fails.append(f"roi={self.roi:.3f}<0")
        if self.max_drawdown > 0.50:
            fails.append(f"dd={self.max_drawdown:.3f}>0.5")
        if self.median_holding_minutes > 2880:
            fails.append(f"med_hold={self.median_holding_minutes:.0f}>2880")
        if self.pct_closed_under_24h < 0.50:
            fails.append(f"pct24h={self.pct_closed_under_24h:.2f}<0.5")
        return "ok" if not fails else ", ".join(fails)


def compute_score(trades: list[WalletTrade], window_days: int = 90) -> WalletScore | None:
    """Compute quality score from a list of WalletTrade.

    Returns None if there are no closed trades to score.
    """
    if not trades:
        return None

    wallet = trades[0].wallet_address
    closed = [t for t in trades if t.closed_at is not None and t.realized_pnl_usd is not None]
    # Also accept trades that have pnl but no close timestamp (e.g. from subgraph fills)
    has_pnl = [t for t in trades if t.realized_pnl_usd is not None]

    if not has_pnl:
        log.debug("scoring.no_pnl_trades", wallet=wallet[:10])
        return None

    # Use has_pnl for financial metrics, closed for holding-time metrics
    scored = has_pnl

    # ── Returns per trade ─────────────────────────────────────────────────
    trade_returns: list[float] = []
    total_invested = 0.0
    total_pnl = 0.0
    wins = 0

    for t in scored:
        # Use cost_usd (invested capital = buy side) for return denominator.
        # Fall back to size_usd if cost_usd is zero (e.g., sell-only position).
        cost = float(getattr(t, "cost_usd", t.size_usd))
        invested = cost if cost > 0 else float(t.size_usd)
        pnl = float(t.realized_pnl_usd or Decimal(0))
        total_invested += invested
        total_pnl += pnl
        if pnl > 0:
            wins += 1
        r = pnl / invested if invested > 0 else 0.0
        trade_returns.append(r)

    roi = total_pnl / total_invested if total_invested > 0 else 0.0
    win_rate = wins / len(scored)
    total_volume = sum(float(t.size_usd) for t in trades)

    # ── Sharpe (simplified) ───────────────────────────────────────────────
    if len(trade_returns) >= 2:
        mean_r = statistics.mean(trade_returns)
        std_r = statistics.stdev(trade_returns)
        sharpe = mean_r / std_r if std_r > 0 else 0.0
    else:
        sharpe = 0.0

    # ── Max drawdown (additive PnL curve, normalized by total invested) ────
    # Prediction markets produce r = -1.0 when a token resolves to 0, which
    # permanently zeros the compound equity curve.  We use an additive PnL
    # curve instead: drawdown = (peak_pnl − current_pnl) / total_invested.
    # This is bounded [0, 1] even when individual trades are total losses.
    pnl_equity = 0.0
    pnl_peak = 0.0
    max_dd = 0.0
    for t in scored:
        pnl_equity += float(t.realized_pnl_usd or Decimal(0))
        if pnl_equity > pnl_peak:
            pnl_peak = pnl_equity
        if total_invested > 0:
            dd = (pnl_peak - pnl_equity) / total_invested
            if dd > max_dd:
                max_dd = dd
    max_dd = min(max_dd, 1.0)  # cap at 100 %

    # ── Holding time metrics ──────────────────────────────────────────────
    holding_minutes = [
        t.holding_minutes for t in closed if t.holding_minutes is not None
    ]
    if holding_minutes:
        avg_holding = statistics.mean(holding_minutes)
        median_holding = statistics.median(holding_minutes)
        under_24h = sum(1 for h in holding_minutes if h < 1440)
        pct_under_24h = under_24h / len(holding_minutes)
    else:
        avg_holding = 0.0
        median_holding = 0.0
        pct_under_24h = 0.0

    score = WalletScore(
        wallet_address=wallet,
        window_days=window_days,
        n_trades=len(scored),
        roi=roi,
        sharpe=sharpe,
        win_rate=win_rate,
        max_drawdown=max_dd,
        total_volume_usd=total_volume,
        avg_holding_minutes=avg_holding,
        median_holding_minutes=median_holding,
        pct_closed_under_24h=pct_under_24h,
    )
    log.debug("scoring.computed", **score.summary())
    return score


def score_is_finite(score: WalletScore) -> bool:
    """Guard against NaN/Inf from edge cases in the math."""
    return all(
        math.isfinite(v)
        for v in (score.roi, score.sharpe, score.win_rate, score.max_drawdown)
    )
