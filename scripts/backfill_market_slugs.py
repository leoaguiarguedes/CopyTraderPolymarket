"""One-time backfill: enrich [pending] Market rows with slug/question/category.

Searches Gamma /events (including closed markets) to find matching events by
CLOB token ID.  Run once after deploying the tracker_worker fix.

Usage:
    python scripts/backfill_market_slugs.py
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
from sqlalchemy import select

from app.config import get_settings
from app.storage.db import SessionLocal
from app.storage import models as orm
from app.utils.logger import configure_logging, get_logger

log = get_logger(__name__)

GAMMA_URL = "https://gamma-api.polymarket.com"


def _hex_to_dec(hex_id: str) -> str:
    try:
        return str(int(hex_id, 16))
    except (ValueError, TypeError):
        return hex_id


async def _fetch_events_page(client: httpx.AsyncClient, offset: int, active_only: bool) -> list[dict]:
    params: dict = {"limit": 100, "offset": offset}
    if active_only:
        params["active"] = "true"
    r = await client.get("/events", params=params)
    r.raise_for_status()
    payload = r.json()
    items: list = payload.get("data", payload) if isinstance(payload, dict) else payload
    return [i for i in items if isinstance(i, dict)]


async def _build_full_index(max_pages: int = 100) -> dict[str, dict]:
    """Build a token-id index by scanning all events (active + closed).

    Searches active events first (fast), then closed events.
    """
    index: dict[str, dict] = {}

    async with httpx.AsyncClient(base_url=GAMMA_URL, timeout=20.0) as client:
        # Pass 1: active events
        print("  Scanning active events...")
        offset = 0
        while offset < max_pages * 100:
            items = await _fetch_events_page(client, offset, active_only=True)
            if not items:
                break
            _index_events(items, index)
            offset += 100
            if len(items) < 100:
                break
        print(f"  Active events indexed {len(index)} tokens")

        # Pass 2: all events (includes closed)
        print("  Scanning all events (including closed)...")
        offset = 0
        pages = 0
        while pages < max_pages:
            items = await _fetch_events_page(client, offset, active_only=False)
            if not items:
                break
            _index_events(items, index)
            offset += 100
            pages += 1
            if len(items) < 100:
                break
            if pages % 10 == 0:
                print(f"    ... scanned {offset} events, {len(index)} tokens indexed")

    return index


def _index_events(events: list[dict], index: dict[str, dict]) -> None:
    for event in events:
        slug: str = event.get("slug", "") or ""
        event_question: str = (
            event.get("title") or event.get("name") or event.get("question") or ""
        )
        category: str = event.get("category") or ""

        for market in event.get("markets") or []:
            if not isinstance(market, dict):
                continue
            clob_ids_raw = market.get("clobTokenIds") or []
            if isinstance(clob_ids_raw, str):
                try:
                    clob_ids_raw = json.loads(clob_ids_raw)
                except Exception:
                    clob_ids_raw = []

            mq: str = market.get("question") or market.get("title") or event_question

            for token_id in clob_ids_raw:
                tid = str(token_id).strip()
                if tid and tid not in index:
                    index[tid] = {
                        "slug": slug,
                        "question": mq or event_question,
                        "category": category,
                    }


async def main() -> None:
    configure_logging()
    settings = get_settings()

    # Fetch all pending markets from DB
    async with SessionLocal() as session:
        result = await session.execute(
            select(orm.Market).where(orm.Market.question == "[pending]")
        )
        pending: list[orm.Market] = list(result.scalars())

    print(f"Found {len(pending)} pending markets to enrich")
    if not pending:
        print("Nothing to do.")
        return

    # Build the full index
    print("Building event index from Gamma API (this may take a minute)...")
    index = await _build_full_index(max_pages=200)
    print(f"Index built: {len(index)} tokens")

    # Match and update
    updated = 0
    marked_closed = 0

    async with SessionLocal() as session:
        for pm in pending:
            db_market = await session.get(orm.Market, pm.condition_id)
            if not db_market:
                continue

            dec = _hex_to_dec(pm.condition_id)
            info = index.get(dec)

            if info and info.get("slug"):
                db_market.question = info["question"] or db_market.question
                db_market.slug = info["slug"]
                db_market.category = info.get("category") or db_market.category
                updated += 1
            else:
                # Market not found in any event — it's definitely closed
                db_market.question = "[closed]"
                marked_closed += 1

        await session.commit()

    print(f"Done! Updated: {updated}, marked [closed]: {marked_closed}")


if __name__ == "__main__":
    asyncio.run(main())
