"""Tracker worker — consumes raw_trades Stream, filters by tracked wallets, persists to DB.

Flow:
  1. Reads tracked wallets from config/tracked_wallets.yaml
  2. Consumes Redis Stream raw_trades (consumer group, so restarts don't re-process)
  3. For each trade from a tracked wallet: persist to DB + publish to tracked_trades Stream
  4. Reloads wallet list periodically (config file can be updated without restart)
"""
from __future__ import annotations

import asyncio
import json
import signal
from datetime import datetime, timezone
from decimal import Decimal

import redis.asyncio as aioredis
import yaml
from sqlalchemy import select

from app.config import get_settings
from app.data.models import OrderSide, TradeEvent
from app.storage.db import SessionLocal
from app.storage import models as orm
from app.tracker.wallet_tracker import WalletTracker
from app.utils.logger import configure_logging, get_logger

RAW_STREAM = "raw_trades"
TRACKED_STREAM = "tracked_trades"
GROUP_NAME = "tracker_group"
CONSUMER_NAME = "tracker_worker_1"
BATCH_SIZE = 100
BLOCK_MS = 5_000            # block up to 5s waiting for new messages
WALLET_RELOAD_INTERVAL = 60  # reload wallets from yaml every 60s

log = get_logger(__name__)


def _load_tracked_addresses(path: str = "config/tracked_wallets.yaml") -> set[str]:
    try:
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        wallets: list[str] = data.get("wallets", [])
        return {w["address"].lower() for w in wallets if w.get("address")}
    except FileNotFoundError:
        log.warning("tracker.config_not_found", path=path)
        return set()
    except Exception as exc:
        log.error("tracker.config_load_failed", path=path, error=str(exc))
        return set()


def _deserialise_event(fields: dict[bytes, bytes]) -> TradeEvent | None:
    try:
        d = {k.decode(): v.decode() for k, v in fields.items()}
        # Backward/forward compatible decoding:
        # - collector publishes either the "trade event" shape (market_id/size/etc)
        #   or the "fill" shape (asset_id/size_tokens/maker/taker).
        market_id = d.get("market_id") or d.get("condition_id") or d.get("asset_id") or ""
        size_tokens = d.get("size") or d.get("size_tokens") or "0"
        maker = d.get("maker_address") or d.get("maker") or ""
        taker = d.get("taker_address") or d.get("taker") or ""
        outcome = d.get("outcome") or "YES"
        return TradeEvent(
            id=d["id"],
            market_id=market_id,
            asset_id=d.get("asset_id", ""),
            outcome=outcome,
            side=OrderSide(d.get("side", "BUY")),
            price=Decimal(d["price"]),
            size=Decimal(size_tokens),
            size_usd=Decimal(d["size_usd"]),
            fee_usd=Decimal(d.get("fee_usd", "0")),
            maker_address=maker,
            taker_address=taker,
            timestamp=datetime.fromisoformat(d["timestamp"]),
            tx_hash=d.get("tx_hash", ""),
        )
    except Exception as exc:
        log.warning("tracker.deserialise_failed", error=str(exc))
        return None


async def _ensure_consumer_group(redis_client: aioredis.Redis) -> None:
    try:
        await redis_client.xgroup_create(RAW_STREAM, GROUP_NAME, id="0", mkstream=True)
        log.info("tracker.consumer_group_created", group=GROUP_NAME)
    except aioredis.ResponseError as e:
        if "BUSYGROUP" not in str(e):
            raise


async def _persist_trade(event: TradeEvent, wallet_address: str) -> None:
    async with SessionLocal() as session:
        # Upsert wallet
        wallet = await session.get(orm.Wallet, wallet_address)
        if not wallet:
            wallet = orm.Wallet(
                address=wallet_address,
                is_tracked=True,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            session.add(wallet)

        # Upsert market stub (full data populated by REST poller later)
        market = await session.get(orm.Market, event.market_id)
        if not market:
            market = orm.Market(
                condition_id=event.market_id,
                question="[pending]",
                is_active=True,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            session.add(market)

        # Skip duplicate trade
        existing = await session.get(orm.Trade, event.id)
        if existing:
            return

        trade = orm.Trade(
            id=event.id,
            wallet_address=wallet_address,
            market_id=event.market_id,
            side=event.side.value,
            outcome=event.outcome,
            price=event.price,
            size=event.size,
            size_usd=event.size_usd,
            fee_usd=event.fee_usd,
            timestamp=event.timestamp,
            tx_hash=event.tx_hash,
        )
        session.add(trade)
        await session.commit()


async def run() -> None:
    configure_logging()
    settings = get_settings()
    log.info("tracker.starting")

    redis_client = aioredis.from_url(settings.redis_url, decode_responses=False)
    await _ensure_consumer_group(redis_client)

    tracker = WalletTracker(tracked_addresses=_load_tracked_addresses())
    log.info("tracker.wallets_loaded", count=tracker.tracked_count)

    shutdown = asyncio.Event()

    def _handle_signal(*_: object) -> None:
        shutdown.set()

    loop = asyncio.get_event_loop()
    loop.add_signal_handler(signal.SIGTERM, _handle_signal)
    loop.add_signal_handler(signal.SIGINT, _handle_signal)

    last_reload = asyncio.get_event_loop().time()

    try:
        while not shutdown.is_set():
            # ── Periodic wallet reload ─────────────────────────────────────
            now = asyncio.get_event_loop().time()
            if now - last_reload >= WALLET_RELOAD_INTERVAL:
                tracker.reload(_load_tracked_addresses())
                last_reload = now

            # ── Read batch from stream ─────────────────────────────────────
            results = await redis_client.xreadgroup(
                GROUP_NAME,
                CONSUMER_NAME,
                {RAW_STREAM: ">"},
                count=BATCH_SIZE,
                block=BLOCK_MS,
            )

            if not results:
                continue

            for _stream, messages in results:
                for msg_id, fields in messages:
                    event = _deserialise_event(fields)
                    if event is None:
                        await redis_client.xack(RAW_STREAM, GROUP_NAME, msg_id)
                        continue

                    wallet = tracker.is_relevant(event)
                    if wallet:
                        try:
                            await _persist_trade(event, wallet)
                            # forward to tracked_trades stream for Signal Engine
                            payload = {
                                "id": event.id,
                                "market_id": event.market_id,
                                "asset_id": event.asset_id,
                                "outcome": event.outcome,
                                "side": event.side.value,
                                "price": str(event.price),
                                "size": str(event.size),
                                "size_usd": str(event.size_usd),
                                "fee_usd": str(event.fee_usd),
                                "maker_address": event.maker_address,
                                "taker_address": event.taker_address,
                                "timestamp": event.timestamp.isoformat(),
                                "tx_hash": event.tx_hash,
                                "tracked_wallet": wallet,
                            }
                            await redis_client.xadd(
                                TRACKED_STREAM,
                                {"data": json.dumps(payload)},
                                maxlen=10_000,
                                approximate=True,
                            )
                            log.info(
                                "tracker.trade_tracked",
                                wallet=wallet[:10],
                                market=event.market_id[:12],
                                size_usd=str(event.size_usd),
                            )
                        except Exception as exc:
                            log.error("tracker.persist_failed", error=str(exc))
                            # don't ack — will be reprocessed on restart
                            continue

                    await redis_client.xack(RAW_STREAM, GROUP_NAME, msg_id)
    finally:
        await redis_client.aclose()
        log.info("tracker.stopped")


if __name__ == "__main__":
    asyncio.run(run())
