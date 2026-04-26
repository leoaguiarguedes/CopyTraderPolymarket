"""Collector worker — polls Polymarket subgraph for tracked-wallet trades → Redis Stream.

Strategy: poll orderFilledEvents for each tracked wallet every POLL_INTERVAL seconds.
Uses Redis Sets to de-duplicate (tx_hash seen check) so no event is published twice.

Why polling instead of WebSocket:
  - Polymarket CLOB WebSocket requires auth for trades; public market channel
    has unstable protocol (immediate close after subscription).
  - Subgraph polling works reliably, adds ~30s latency (fine for 3-60min holds).
  - Simpler, restartable, no reconnect state to manage.
"""
from __future__ import annotations

import asyncio
import json
import signal
import sys
import hashlib
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml
import redis.asyncio as aioredis

from app.config import get_settings
from app.data.subgraph_client import SubgraphClient
from app.utils.logger import configure_logging, get_logger

STREAM_NAME = "raw_trades"
STREAM_MAXLEN = 50_000
POLL_INTERVAL = 30          # seconds between polling rounds
DEDUP_TTL = 3600            # seconds to keep seen tx hashes in Redis
DEDUP_KEY = "collector:seen_txhash"
WALLETS_PATH = "config/tracked_wallets.yaml"
LOOKBACK_MINUTES = 60       # fetch fills from the last N minutes each poll

log = get_logger(__name__)


def _load_wallet_addresses(path: str) -> list[str]:
    try:
        data = yaml.safe_load(open(path))
        wallets = data.get("wallets", [])
        return [w["address"].lower() for w in wallets if w.get("address")]
    except Exception as exc:
        log.warning("collector.wallets_load_failed", error=str(exc))
        return []


async def run() -> None:
    configure_logging()
    settings = get_settings()
    log.info("collector.starting", mode=settings.execution_mode.value)

    redis_client = aioredis.from_url(settings.redis_url, decode_responses=False)
    subgraph = SubgraphClient(settings)

    shutdown = asyncio.Event()

    def _handle_signal(*_: object) -> None:
        shutdown.set()

    loop = asyncio.get_event_loop()
    loop.add_signal_handler(signal.SIGTERM, _handle_signal)
    loop.add_signal_handler(signal.SIGINT, _handle_signal)

    wallets: list[str] = []
    last_wallets_reload = 0.0
    WALLET_RELOAD_INTERVAL = 60.0

    log.info("collector.poll_mode", interval_s=POLL_INTERVAL)

    try:
        while not shutdown.is_set():
            now = asyncio.get_event_loop().time()

            # Reload wallet list periodically
            if now - last_wallets_reload >= WALLET_RELOAD_INTERVAL:
                wallets = _load_wallet_addresses(WALLETS_PATH)
                last_wallets_reload = now
                log.info("collector.wallets_loaded", count=len(wallets))

            if not wallets:
                await asyncio.sleep(POLL_INTERVAL)
                continue

            # Poll each wallet for recent fills
            cutoff_ts = int(
                (datetime.now(tz=timezone.utc) - timedelta(minutes=LOOKBACK_MINUTES)).timestamp()
            )
            new_total = 0

            for wallet in wallets:
                if shutdown.is_set():
                    break
                try:
                    fills = await _fetch_recent_fills(subgraph, wallet, cutoff_ts)
                    for fill in fills:
                        tx = fill.get("transactionHash", "") or fill.get("id", "")
                        if not tx:
                            continue

                        # Deduplicate via Redis Set
                        key = f"{DEDUP_KEY}:{tx}"
                        already_seen = await redis_client.exists(key)
                        if already_seen:
                            continue
                        await redis_client.setex(key, DEDUP_TTL, b"1")

                        # Publish to stream
                        fields = _fill_to_stream_fields(fill, wallet)
                        await redis_client.xadd(
                            STREAM_NAME, fields, maxlen=STREAM_MAXLEN, approximate=True
                        )
                        new_total += 1
                        log.debug(
                            "collector.trade_published",
                            wallet=wallet[:10],
                            tx=tx[:16],
                        )
                except Exception as exc:
                    log.warning(
                        "collector.wallet_poll_failed",
                        wallet=wallet[:10],
                        error=str(exc)[:80],
                    )

            log.info("collector.poll_done", new_trades=new_total, wallets=len(wallets))

            # Wait for next poll
            await asyncio.sleep(POLL_INTERVAL)

    finally:
        await redis_client.aclose()
        log.info("collector.stopped")


_FILLS_QUERY = """
query fills($wallet: String!, $since: BigInt!) {
  orderFilledEvents(
    where: { %(side)s: $wallet, timestamp_gte: $since }
    first: 50
    orderBy: timestamp
    orderDirection: desc
  ) {
    id
    transactionHash
    timestamp
    maker
    taker
    makerAssetId
    takerAssetId
    makerAmountFilled
    takerAmountFilled
    fee
  }
}
"""


async def _fetch_recent_fills(
    subgraph: SubgraphClient,
    wallet: str,
    since_ts: int,
) -> list[dict]:
    """Fetch orderFilledEvents for wallet (as maker or taker) since_ts."""
    vars_ = {"wallet": wallet, "since": str(since_ts)}
    fills: list[dict] = []
    for side in ("maker", "taker"):
        try:
            result = await subgraph._query(
                subgraph._s.subgraph_url,
                _FILLS_QUERY % {"side": side},
                vars_,
                timeout=15.0,
            )
            fills.extend(result.get("orderFilledEvents", []))
        except Exception as exc:
            log.debug("collector.fill_fetch_error", side=side, wallet=wallet[:10], error=str(exc)[:60])
    return fills


def _fill_to_stream_fields(fill: dict, wallet: str) -> dict[str, bytes | str]:
    """Convert a subgraph orderFilledEvent to a flat Redis Stream field map."""
    maker = fill.get("maker", "").lower()
    taker = fill.get("taker", "").lower()
    maker_asset = fill.get("makerAssetId", "0")
    taker_asset = fill.get("takerAssetId", "0")

    # Determine side: if makerAssetId == "0" → maker paid USDC → maker BOUGHT tokens
    scale = Decimal("1e6")
    if maker_asset == "0":
        side = "BUY"
        asset_id = taker_asset
        usdc_amount = Decimal(fill.get("makerAmountFilled", "0")) / scale
        token_amount = Decimal(fill.get("takerAmountFilled", "0")) / scale
    else:
        side = "SELL"
        asset_id = maker_asset
        usdc_amount = Decimal(fill.get("takerAmountFilled", "0")) / scale
        token_amount = Decimal(fill.get("makerAmountFilled", "0")) / scale

    price = (usdc_amount / token_amount) if token_amount > 0 else Decimal("0")
    fee_usd = (Decimal(fill.get("fee", "0") or "0") / scale).quantize(Decimal("0.000001"))

    def _as_hex66(dec_str: str) -> str:
        """Convert decimal token id to 0x-prefixed 32-byte hex (len=66)."""
        try:
            n = int(str(dec_str or "0"))
            if n < 0:
                n = 0
            return "0x" + format(n, "064x")
        except Exception:
            return "0x" + "0" * 64

    raw_id = str(fill.get("id", "") or "")
    # DB constraint: trades.id is VARCHAR(80). Subgraph ids can exceed this.
    # We store a stable hash for the trade primary key.
    trade_id = "fill_" + hashlib.sha256(raw_id.encode("utf-8")).hexdigest()

    return {
        "id": trade_id,
        "tx_hash": fill.get("transactionHash", fill.get("id", "")),
        "wallet": wallet,
        # keep both naming conventions for downstream compatibility
        "maker": maker,
        "taker": taker,
        "maker_address": maker,
        "taker_address": taker,
        "asset_id": asset_id,
        # NOTE: orderbook subgraph doesn't expose condition_id directly here.
        # As a fallback, we convert token id → fixed 32-byte hex so DB constraints work.
        "market_id": _as_hex66(asset_id),
        "outcome": "YES",
        "side": side,
        "price": str(price.quantize(Decimal("0.000001"))),
        "size_usd": str(usdc_amount.quantize(Decimal("0.01"))),
        "size_tokens": str(token_amount.quantize(Decimal("0.000001"))),
        "size": str(token_amount.quantize(Decimal("0.000001"))),
        "fee_usd": str(fee_usd),
        "timestamp": datetime.fromtimestamp(
            int(fill.get("timestamp", 0)), tz=timezone.utc
        ).isoformat(),
    }


if __name__ == "__main__":
    asyncio.run(run())
