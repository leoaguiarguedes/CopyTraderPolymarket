"""Signals endpoints — feed of generated signals with risk decisions."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.storage.db import get_db
from app.storage import models as orm

router = APIRouter(prefix="/signals", tags=["signals"])


@router.get("")
async def list_signals(
    limit: int = Query(50, ge=1, le=500),
    strategy: str | None = Query(None),
    status: str | None = Query(None, description="pending|approved|rejected|executed"),
    db: AsyncSession = Depends(get_db),
):
    """Latest signals with strategy, confidence, status and risk decision."""
    q = (
        select(
            orm.Signal,
            orm.Market.category.label("market_category"),
            orm.Market.slug.label("market_slug"),
        )
        .outerjoin(orm.Market, orm.Signal.market_id == orm.Market.condition_id)
        .order_by(orm.Signal.created_at.desc())
        .limit(limit)
    )
    if strategy:
        q = q.where(orm.Signal.strategy == strategy)
    if status:
        q = q.where(orm.Signal.status == status)
    result = await db.execute(q)
    rows = result.all()
    return [_signal_to_dict(row[0], row[1], row[2]) for row in rows]


def _signal_to_dict(s: orm.Signal, market_category: str | None = None, market_slug: str | None = None) -> dict:
    return {
        "signal_id": s.signal_id,
        "strategy": s.strategy,
        "market_id": s.market_id,
        "market_question": s.market_question,
        "market_category": market_category,
        "market_slug": market_slug,
        "side": s.side,
        "confidence": float(s.confidence),
        "entry_price": float(s.entry_price),
        "size_pct": float(s.size_pct),
        "tp_pct": float(s.tp_pct),
        "sl_pct": float(s.sl_pct),
        "max_holding_minutes": s.max_holding_minutes,
        "source_wallet": s.source_wallet,
        "status": s.status,
        "reject_reason": s.reject_reason,
        "reason": s.reason,
        "created_at": s.created_at.isoformat(),
    }
