"""Positions endpoints — open and closed paper/live positions."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.storage.db import get_db
from app.storage import models as orm

router = APIRouter(prefix="/positions", tags=["positions"])


@router.get("")
async def list_positions(
    status: str = Query("open", description="open | closed | all"),
    limit: int = Query(100, ge=1, le=1000),
    strategy: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List positions with age and forced-exit countdown."""
    q = (
        select(
            orm.Position,
            orm.Market.category.label("market_category"),
            orm.Market.slug.label("market_slug"),
        )
        .outerjoin(orm.Market, orm.Position.market_id == orm.Market.condition_id)
        .order_by(orm.Position.opened_at.desc())
        .limit(limit)
    )

    if status == "open":
        q = q.where(orm.Position.closed_at.is_(None))
    elif status == "closed":
        q = q.where(orm.Position.closed_at.isnot(None))

    if strategy:
        q = q.where(orm.Position.strategy == strategy)

    result = await db.execute(q)
    rows = result.all()

    now = datetime.now(tz=timezone.utc)
    return [_position_to_dict(row[0], now, row[1], row[2]) for row in rows]


def _position_to_dict(p: orm.Position, now: datetime, market_category: str | None = None, market_slug: str | None = None) -> dict:
    opened = p.opened_at
    age_min = (now - opened).total_seconds() / 60 if opened else 0.0
    time_to_force_exit = max(0.0, p.max_holding_minutes - age_min) if not p.closed_at else None

    return {
        "position_id": p.position_id,
        "signal_id": p.signal_id,
        "strategy": p.strategy,
        "market_id": p.market_id,
        "market_category": market_category,
        "market_slug": market_slug,
        "side": p.side,
        "entry_price": float(p.entry_price),
        "size_usd": float(p.size_usd),
        "tp_price": float(p.tp_price),
        "sl_price": float(p.sl_price),
        "max_holding_minutes": p.max_holding_minutes,
        "opened_at": p.opened_at.isoformat() if p.opened_at else None,
        "age_minutes": round(age_min, 1),
        "time_to_force_exit_minutes": round(time_to_force_exit, 1) if time_to_force_exit is not None else None,
        "closed_at": p.closed_at.isoformat() if p.closed_at else None,
        "exit_price": float(p.exit_price) if p.exit_price else None,
        "realized_pnl_usd": float(p.realized_pnl_usd) if p.realized_pnl_usd else None,
        "exit_reason": p.exit_reason,
        "execution_mode": p.execution_mode,
    }
