"""System status, market-filter management, and env-var update endpoints."""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml
import redis.asyncio as aioredis
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import get_settings
from app.risk.kill_switch import KillSwitch

_ENV_PATH = Path(".env")

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


# ── /system/env ───────────────────────────────────────────────────────────────

_ALLOWED_ENV_KEYS = {
    "EXECUTION_MODE",
    "WALLET_ADDRESS",
    "DISCORD_WEBHOOK_URL",
    "WALLET_PRIVATE_KEY",
}

_SENSITIVE_KEYS = {"WALLET_PRIVATE_KEY"}


class EnvUpdateRequest(BaseModel):
    vars: dict[str, str]


class EnvStatus(BaseModel):
    execution_mode: str
    wallet_address: str | None
    discord_webhook_url: str | None
    wallet_private_key_set: bool


@router.get("/env", response_model=EnvStatus)
async def get_env_status() -> EnvStatus:
    """Return current runtime-relevant env var values (private key is never returned)."""
    current = _read_env_file()
    settings = get_settings()
    return EnvStatus(
        execution_mode=current.get("EXECUTION_MODE", settings.execution_mode.value),
        wallet_address=current.get("WALLET_ADDRESS") or None,
        discord_webhook_url=current.get("DISCORD_WEBHOOK_URL") or None,
        wallet_private_key_set=bool(current.get("WALLET_PRIVATE_KEY")),
    )


@router.patch("/env", response_model=EnvStatus)
async def update_env(body: EnvUpdateRequest) -> EnvStatus:
    """Write allowed env vars to the .env file. Sensitive values are write-only."""
    unknown = set(body.vars) - _ALLOWED_ENV_KEYS
    if unknown:
        raise HTTPException(status_code=422, detail=f"Chaves não permitidas: {sorted(unknown)}")

    if "EXECUTION_MODE" in body.vars:
        val = body.vars["EXECUTION_MODE"].lower()
        if val not in ("live", "paper"):
            raise HTTPException(status_code=422, detail="EXECUTION_MODE deve ser 'live' ou 'paper'")
        body.vars["EXECUTION_MODE"] = val

    current = _read_env_file()
    for k, v in body.vars.items():
        if v.strip() == "" and k in _SENSITIVE_KEYS:
            continue  # don't overwrite sensitive key with blank
        current[k] = v

    _write_env_file(current)

    # Propagate changes to the live OS environment so Settings() re-reads correctly.
    # (Docker injects env_file as OS env vars at startup; we must mirror changes here.)
    for k, v in current.items():
        os.environ[k] = v

    # Invalidate the settings LRU cache so the next request creates a fresh Settings()
    from app.config import get_settings as _get_settings
    _get_settings.cache_clear()

    return await get_env_status()


def _read_env_file() -> dict[str, str]:
    """Read .env file into a dict, preserving values."""
    result: dict[str, str] = {}
    if not _ENV_PATH.exists():
        return result
    for line in _ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        result[key.strip()] = value.strip().strip('"').strip("'")
    return result


def _write_env_file(data: dict[str, str]) -> None:
    """Update .env file, preserving comments and unknown lines, updating known keys."""
    if not _ENV_PATH.exists():
        lines = [f"{k}={v}" for k, v in data.items()]
        _ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return

    original = _ENV_PATH.read_text(encoding="utf-8").splitlines()
    updated_keys: set[str] = set()
    new_lines: list[str] = []

    for line in original:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in data:
                new_lines.append(f"{key}={data[key]}")
                updated_keys.add(key)
                continue
        new_lines.append(line)

    # Append any keys not already in file
    for key, value in data.items():
        if key not in updated_keys:
            new_lines.append(f"{key}={value}")

    _ENV_PATH.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


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
