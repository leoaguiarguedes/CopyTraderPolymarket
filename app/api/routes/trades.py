"""GET /trades — recent trades from tracked wallets."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.storage.db import get_session
from app.storage import models as orm

router = APIRouter(prefix="/trades", tags=["trades"])


@router.get("")
async def list_trades(
    wallet: str | None = Query(default=None, description="Filter by wallet address"),
    market_id: str | None = Query(default=None),
    limit: int = Query(default=50, le=500),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    q = select(orm.Trade).order_by(orm.Trade.timestamp.desc())
    if wallet:
        q = q.where(orm.Trade.wallet_address == wallet.lower())
    if market_id:
        q = q.where(orm.Trade.market_id == market_id)
    q = q.limit(limit)

    result = await session.execute(q)
    trades = result.scalars().all()

    return [
        {
            "id": t.id,
            "wallet_address": t.wallet_address,
            "market_id": t.market_id,
            "side": t.side,
            "outcome": t.outcome,
            "price": float(t.price),
            "size_usd": float(t.size_usd),
            "fee_usd": float(t.fee_usd),
            "timestamp": t.timestamp.isoformat(),
            "tx_hash": t.tx_hash,
        }
        for t in trades
    ]
