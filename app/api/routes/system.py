"""System status and market-filter management endpoints."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
import redis.asyncio as aioredis
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import get_settings
from app.risk.kill_switch import KillSwitch

router = APIRouter(prefix="/system", tags=["system"])

_MARKET_FILTERS_PATH = Path("config/market_filters.yaml")

# Redis keys written by execution_worker
_KEY_CB_CONSECUTIVE = "copytrader:circuit_breaker:consecutive"
_KEY_USDC_BALANCE = "copytrader:live:usdc_balance"


# ── /system/status ────────────────────────────────────────────────────────────

class SystemStatus(BaseModel):
    execution_mode: str
    kill_switch_active: bool
    circuit_breaker_consecutive: int
    circuit_breaker_max: int
    usdc_balance: float | None        # null in paper mode
    capital_usd: float
    tracked_tag_ids: list[int]


@router.get("/status", response_model=SystemStatus)
async def get_system_status() -> SystemStatus:
    settings = get_settings()
    r = aioredis.from_url(settings.redis_url, decode_responses=True)
    try:
        ks = KillSwitch(r)
        ks_active = await ks.is_active()

        cb_raw = await r.get(_KEY_CB_CONSECUTIVE)
        cb_consecutive = int(cb_raw) if cb_raw else 0

        usdc_raw = await r.get(_KEY_USDC_BALANCE)
        usdc_balance: float | None = float(usdc_raw) if usdc_raw else None
        if settings.is_paper_trading:
            usdc_balance = None
    finally:
        await r.aclose()

    tracked_ids = _load_tracked_tag_ids()

    return SystemStatus(
        execution_mode=settings.execution_mode.value,
        kill_switch_active=ks_active,
        circuit_breaker_consecutive=cb_consecutive,
        circuit_breaker_max=settings.circuit_breaker_max_consecutive,
        usdc_balance=usdc_balance,
        capital_usd=settings.initial_capital_usd,
        tracked_tag_ids=tracked_ids,
    )


# ── /system/market-tags ───────────────────────────────────────────────────────

class MarketTag(BaseModel):
    id: int
    label: str
    slug: str
    description: str
    tracked: bool


class MarketTagsResponse(BaseModel):
    tags: list[MarketTag]
    tracked_tag_ids: list[int]


class UpdateMarketTagsRequest(BaseModel):
    tracked_tag_ids: list[int]


@router.get("/market-tags", response_model=MarketTagsResponse)
async def get_market_tags() -> MarketTagsResponse:
    data = _load_market_filters()
    tracked = set(data.get("tracked_tag_ids") or [])
    tags = [
        MarketTag(
            id=t["id"],
            label=t["label"],
            slug=t["slug"],
            description=t.get("description", ""),
            tracked=t["id"] in tracked,
        )
        for t in data.get("available_tags", [])
    ]
    return MarketTagsResponse(tags=tags, tracked_tag_ids=list(tracked))


@router.patch("/market-tags", response_model=MarketTagsResponse)
async def update_market_tags(body: UpdateMarketTagsRequest) -> MarketTagsResponse:
    """Update which market categories the collector tracks. Takes effect on next poll cycle."""
    data = _load_market_filters()

    valid_ids = {t["id"] for t in data.get("available_tags", [])}
    invalid = [tid for tid in body.tracked_tag_ids if tid not in valid_ids]
    if invalid:
        raise HTTPException(status_code=422, detail=f"Unknown tag IDs: {invalid}")

    data["tracked_tag_ids"] = body.tracked_tag_ids
    _save_market_filters(data)

    return await get_market_tags()


# ── helpers ───────────────────────────────────────────────────────────────────

def _load_market_filters() -> dict[str, Any]:
    try:
        return yaml.safe_load(_MARKET_FILTERS_PATH.read_text(encoding="utf-8")) or {}
    except Exception:
        return {"available_tags": [], "tracked_tag_ids": []}


def _save_market_filters(data: dict[str, Any]) -> None:
    _MARKET_FILTERS_PATH.write_text(
        yaml.dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )


def _load_tracked_tag_ids() -> list[int]:
    return _load_market_filters().get("tracked_tag_ids") or []
