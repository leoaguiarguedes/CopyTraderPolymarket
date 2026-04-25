"""GET /wallets — list tracked wallets with latest scores."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.storage.db import get_session
from app.storage import models as orm

router = APIRouter(prefix="/wallets", tags=["wallets"])


@router.get("")
async def list_wallets(
    tracked_only: bool = True,
    sort_by: str = Query(default="sharpe", enum=["sharpe", "roi", "win_rate", "n_trades"]),
    limit: int = Query(default=50, le=200),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    q = select(orm.Wallet)
    if tracked_only:
        q = q.where(orm.Wallet.is_tracked == True)  # noqa: E712
    result = await session.execute(q.limit(limit))
    wallets = result.scalars().all()

    rows: list[dict[str, Any]] = []
    for w in wallets:
        # get latest score (30d window preferred, else any)
        score_q = (
            select(orm.WalletScore)
            .where(orm.WalletScore.wallet_address == w.address)
            .order_by(orm.WalletScore.computed_at.desc())
            .limit(1)
        )
        score_result = await session.execute(score_q)
        score = score_result.scalar_one_or_none()

        row: dict[str, Any] = {
            "address": w.address,
            "proxy_address": w.proxy_address,
            "label": w.label,
            "is_tracked": w.is_tracked,
        }
        if score:
            row.update(
                {
                    "n_trades": score.n_trades,
                    "roi": float(score.roi),
                    "sharpe": float(score.sharpe),
                    "win_rate": float(score.win_rate),
                    "max_drawdown": float(score.max_drawdown),
                    "avg_holding_minutes": float(score.avg_holding_minutes),
                    "median_holding_minutes": float(score.median_holding_minutes),
                    "pct_closed_under_24h": float(score.pct_closed_under_24h),
                    "score_window_days": score.window_days,
                    "score_computed_at": score.computed_at.isoformat(),
                }
            )
        rows.append(row)

    sort_key = sort_by
    rows.sort(key=lambda r: float(r.get(sort_key, 0) or 0), reverse=True)
    return rows


@router.get("/{address}")
async def get_wallet(
    address: str,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    addr = address.lower()
    wallet = await session.get(orm.Wallet, addr)
    if not wallet:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Wallet not found")

    scores_q = (
        select(orm.WalletScore)
        .where(orm.WalletScore.wallet_address == addr)
        .order_by(orm.WalletScore.computed_at.desc())
        .limit(5)
    )
    scores_result = await session.execute(scores_q)
    scores = scores_result.scalars().all()

    trades_q = (
        select(orm.Trade)
        .where(orm.Trade.wallet_address == addr)
        .order_by(orm.Trade.timestamp.desc())
        .limit(100)
    )
    trades_result = await session.execute(trades_q)
    trades = trades_result.scalars().all()

    return {
        "address": wallet.address,
        "proxy_address": wallet.proxy_address,
        "label": wallet.label,
        "is_tracked": wallet.is_tracked,
        "scores": [
            {
                "window_days": s.window_days,
                "n_trades": s.n_trades,
                "roi": float(s.roi),
                "sharpe": float(s.sharpe),
                "win_rate": float(s.win_rate),
                "max_drawdown": float(s.max_drawdown),
                "avg_holding_minutes": float(s.avg_holding_minutes),
                "median_holding_minutes": float(s.median_holding_minutes),
                "pct_closed_under_24h": float(s.pct_closed_under_24h),
                "computed_at": s.computed_at.isoformat(),
            }
            for s in scores
        ],
        "recent_trades": [
            {
                "id": t.id,
                "market_id": t.market_id,
                "side": t.side,
                "outcome": t.outcome,
                "price": float(t.price),
                "size_usd": float(t.size_usd),
                "timestamp": t.timestamp.isoformat(),
                "tx_hash": t.tx_hash,
            }
            for t in trades
        ],
    }
