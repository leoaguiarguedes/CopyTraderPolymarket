"""Collector worker — connects Polymarket WebSocket → Redis Stream raw_trades.

Flow:
  1. Fetches all active markets from the REST API
  2. Opens a WebSocket subscription for those markets
  3. For every TradeEvent received, serialises and publishes to Redis Stream
  4. Reconnects automatically on disconnect (handled by PolymarketWebSocket)
  5. Periodically refreshes the market list to pick up new markets
"""
from __future__ import annotations

import asyncio
import json
import signal
from datetime import datetime
from decimal import Decimal

import redis.asyncio as aioredis

from app.config import get_settings
from app.data.polymarket_rest import PolymarketRestClient
from app.data.polymarket_ws import PolymarketWebSocket
from app.utils.logger import configure_logging, get_logger

STREAM_NAME = "raw_trades"
STREAM_MAXLEN = 50_000          # cap stream size
MARKET_REFRESH_INTERVAL = 300   # re-fetch active markets every 5 min

log = get_logger(__name__)


def _serialise_event(event: object) -> dict[str, str]:
    """Convert a TradeEvent dataclass to a flat Redis Stream field map."""
    from app.data.models import TradeEvent

    e: TradeEvent = event  # type: ignore[assignment]
    return {
        "id": e.id,
        "market_id": e.market_id,
        "asset_id": e.asset_id,
        "outcome": e.outcome,
        "side": e.side.value,
        "price": str(e.price),
        "size": str(e.size),
        "size_usd": str(e.size_usd),
        "fee_usd": str(e.fee_usd),
        "maker_address": e.maker_address,
        "taker_address": e.taker_address,
        "timestamp": e.timestamp.isoformat(),
        "tx_hash": e.tx_hash,
    }


async def run() -> None:
    configure_logging()
    settings = get_settings()
    log.info("collector.starting", mode=settings.execution_mode.value)

    redis_client = aioredis.from_url(settings.redis_url, decode_responses=False)
    rest = PolymarketRestClient(settings)

    shutdown = asyncio.Event()

    def _handle_signal(*_: object) -> None:
        log.info("collector.shutdown_signal")
        shutdown.set()

    loop = asyncio.get_event_loop()
    loop.add_signal_handler(signal.SIGTERM, _handle_signal)
    loop.add_signal_handler(signal.SIGINT, _handle_signal)

    market_ids: list[str] = []
    last_refresh = 0.0

    try:
        while not shutdown.is_set():
            # ── Refresh market list ────────────────────────────────────────
            now = asyncio.get_event_loop().time()
            if now - last_refresh >= MARKET_REFRESH_INTERVAL:
                try:
                    markets = await rest.get_all_active_markets()
                    market_ids = [m.condition_id for m in markets if m.condition_id]
                    log.info("collector.markets_loaded", count=len(market_ids))
                    last_refresh = now
                except Exception as exc:
                    log.error("collector.market_refresh_failed", error=str(exc))
                    if not market_ids:
                        await asyncio.sleep(10)
                        continue

            ws = PolymarketWebSocket(market_ids=market_ids, settings=settings)

            # ── Stream trades ──────────────────────────────────────────────
            try:
                async for event in ws.stream():
                    if shutdown.is_set():
                        break
                    fields = _serialise_event(event)
                    await redis_client.xadd(
                        STREAM_NAME, fields, maxlen=STREAM_MAXLEN, approximate=True
                    )
                    log.debug(
                        "collector.trade_published",
                        market=event.market_id[:12],
                        size_usd=str(event.size_usd),
                    )

                    # check for market refresh mid-stream
                    if asyncio.get_event_loop().time() - last_refresh >= MARKET_REFRESH_INTERVAL:
                        ws.stop()
                        break
            except Exception as exc:
                log.error("collector.stream_error", error=str(exc))
                await asyncio.sleep(5)
    finally:
        await rest.aclose()
        await redis_client.aclose()
        log.info("collector.stopped")


if __name__ == "__main__":
    asyncio.run(run())
