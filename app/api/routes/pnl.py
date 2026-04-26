"""PnL endpoints — realized PnL, equity curve, and portfolio summary."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.storage.db import get_db
from app.storage import models as orm
from app.utils.logger import get_logger

router = APIRouter(prefix="/pnl", tags=["pnl"])
log = get_logger(__name__)


def _range_cutoff(range_str: str) -> datetime:
    now = datetime.now(tz=timezone.utc)
    mapping = {"1d": 1, "7d": 7, "30d": 30}
    days = mapping.get(range_str, 0)
    if days:
        return now - timedelta(days=days)
    return datetime.min.replace(tzinfo=timezone.utc)


@router.get("/summary")
async def get_pnl_summary(
    range: str = Query("all", description="1d | 7d | 30d | all"),
    db: AsyncSession = Depends(get_db),
):
    """Overall PnL summary for the given time range."""
    cutoff = _range_cutoff(range)

    result = await db.execute(
        select(
            func.count(orm.Position.position_id).label("n_positions"),
            func.sum(orm.Position.realized_pnl_usd).label("total_pnl"),
            func.sum(orm.Position.size_usd).label("total_volume"),
            func.sum(
                case((orm.Position.realized_pnl_usd > 0, 1), else_=0)
            ).label("wins"),
        ).where(
            orm.Position.closed_at >= cutoff,
            orm.Position.closed_at.isnot(None),
        )
    )
    row = result.one()

    # Open positions unrealized PnL (approximate — would need live prices)
    open_result = await db.execute(
        select(
            func.count(orm.Position.position_id).label("open_count"),
            func.sum(orm.Position.size_usd).label("open_exposure"),
        ).where(orm.Position.closed_at.is_(None))
    )
    open_row = open_result.one()

    n = row.n_positions or 0
    total_pnl = float(row.total_pnl or 0)
    total_vol = float(row.total_volume or 0)
    wins = row.wins or 0

    return {
        "range": range,
        "total_pnl_usd": round(total_pnl, 2),
        "total_volume_usd": round(total_vol, 2),
        "n_closed_positions": n,
        "win_rate": round(wins / n, 4) if n else 0.0,
        "roi": round(total_pnl / total_vol, 4) if total_vol else 0.0,
        "open_positions": open_row.open_count or 0,
        "open_exposure_usd": round(float(open_row.open_exposure or 0), 2),
    }


@router.get("/equity-curve")
async def get_equity_curve(
    range: str = Query("30d", description="7d | 30d | all"),
    bucket: str = Query("1h", description="1h | 6h | 1d"),
    db: AsyncSession = Depends(get_db),
):
    """Cumulative PnL over time, bucketed for charting."""
    cutoff = _range_cutoff(range)

    result = await db.execute(
        select(orm.Position)
        .where(
            orm.Position.closed_at >= cutoff,
            orm.Position.closed_at.isnot(None),
            orm.Position.realized_pnl_usd.isnot(None),
        )
        .order_by(orm.Position.closed_at)
    )
    positions = result.scalars().all()

    # Build cumulative curve
    cumulative = 0.0
    points = []
    for pos in positions:
        cumulative += float(pos.realized_pnl_usd or 0)
        points.append({
            "ts": pos.closed_at.isoformat(),
            "pnl": round(float(pos.realized_pnl_usd or 0), 4),
            "cumulative": round(cumulative, 4),
            "exit_reason": pos.exit_reason,
        })

    return {"range": range, "points": points, "final_pnl": round(cumulative, 4)}
