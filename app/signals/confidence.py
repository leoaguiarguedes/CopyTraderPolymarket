"""Confidence scorer — combines wallet quality + strategy weight + market factors."""
from __future__ import annotations

from app.tracker.scoring import WalletScore
from app.utils.logger import get_logger

log = get_logger(__name__)

# Maximum Sharpe we normalise against (scores above this get 1.0)
_MAX_SHARPE = 2.0
# Maximum ROI for normalisation
_MAX_ROI = 5.0


def compute_confidence(
    wallet_score: WalletScore | None,
    strategy_weight: float,
    *,
    liquidity_factor: float = 1.0,
    timing_factor: float = 1.0,
) -> float:
    """Return a confidence score in [0, 1].

    confidence = wallet_quality × strategy_weight × liquidity_factor × timing_factor

    wallet_quality: blend of normalised Sharpe + ROI + win_rate
    strategy_weight: per-strategy constant from strategies.yaml
    liquidity_factor: 1.0 if orderbook depth is sufficient, scaled down otherwise
    timing_factor: recency of the triggering trade (1.0 = immediate, 0.5 = delayed)
    """
    wallet_quality = _wallet_quality(wallet_score)
    confidence = wallet_quality * strategy_weight * liquidity_factor * timing_factor
    return min(1.0, max(0.0, confidence))


def _wallet_quality(score: WalletScore | None) -> float:
    if score is None:
        return 0.3  # default for unknown wallets

    # Normalise each metric to [0, 1]
    sharpe_norm = min(1.0, max(0.0, score.sharpe / _MAX_SHARPE))
    roi_norm = min(1.0, max(0.0, score.roi / _MAX_ROI))
    wr_norm = score.win_rate  # already 0-1

    # Win rate is the most direct quality signal; Sharpe and ROI support it
    quality = 0.5 * wr_norm + 0.3 * sharpe_norm + 0.2 * roi_norm
    return quality
