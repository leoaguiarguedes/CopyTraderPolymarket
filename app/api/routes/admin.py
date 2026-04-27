"""Admin reset endpoints — wipe individual data entities or everything."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.storage.db import get_db
from app.storage import models as orm

router = APIRouter(prefix="/admin", tags=["admin"])

_ENTITIES = ("trades", "wallets", "signals", "backtest", "all")


@router.delete("/reset")
async def reset_data(
    entity: str = Query(..., enum=list(_ENTITIES)),
    db: AsyncSession = Depends(get_db),
):
    """
    Wipe data from the database in FK-safe order.
    - trades: all on-chain trade records
    - wallets: wallet_scores + trades + wallets
    - signals: positions + signals
    - backtest: backtest_runs
    - all: everything above
    """
    deleted: dict[str, int] = {}

    async def _del(model) -> int:
        result = await db.execute(delete(model))
        return result.rowcount

    if entity in ("signals", "all"):
        deleted["positions"] = await _del(orm.Position)
        deleted["signals"] = await _del(orm.Signal)

    if entity in ("trades", "wallets", "all"):
        deleted["trades"] = await _del(orm.Trade)

    if entity in ("wallets", "all"):
        deleted["wallet_scores"] = await _del(orm.WalletScore)
        deleted["wallets"] = await _del(orm.Wallet)

    if entity in ("backtest", "all"):
        deleted["backtest_runs"] = await _del(orm.BacktestRun)

    await db.commit()
    return {"reset": entity, "deleted": deleted}
