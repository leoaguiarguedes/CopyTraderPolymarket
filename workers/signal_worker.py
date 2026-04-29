"""Signal worker — consumes tracked_trades stream and emits signals.

Redis Stream layout:
  consumed:  tracked_trades  (group: signal_workers)
  published: signals         (each signal as a JSON dict)
"""
from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import redis.asyncio as aioredis

from app.config import get_settings
from app.data.models import OrderSide, TradeEvent
from app.data.polymarket_rest import PolymarketRestClient
from app.data.subgraph_client import SubgraphClient
from app.risk.kill_switch import KillSwitch
from app.signals.signal_engine import SignalEngine
from app.tracker.scoring import WalletScore, compute_score
from app.utils.logger import configure_logging, get_logger

log = get_logger(__name__)

_STREAM_IN = "tracked_trades"
_STREAM_OUT = "signals"
_GROUP = "signal_workers"
_CONSUMER = "signal_worker_1"
_BATCH_SIZE = 100
_BLOCK_MS = 2000
_SCORE_CACHE_TTL_SECONDS = 3600  # re-score wallets hourly


class SignalWorker:
    def __init__(self) -> None:
        self._s = get_settings()
        self._r: aioredis.Redis | None = None
        self._engine = SignalEngine()
        self._subgraph = SubgraphClient(self._s)
        self._score_cache: dict[str, tuple[WalletScore | None, float]] = {}  # wallet → (score, ts)

    async def start(self) -> None:
        self._r = aioredis.from_url(self._s.redis_url, decode_responses=False)
        ks = KillSwitch(self._r)

        # Create consumer group — use id="0" so a fresh worker processes all
        # historical messages.  On restart the group already exists (BUSYGROUP),
        # so the exception is ignored and the current position is preserved.
        try:
            await self._r.xgroup_create(_STREAM_IN, _GROUP, id="0", mkstream=True)
        except aioredis.ResponseError:
            pass  # group already exists — position is preserved

        log.info("signal_worker.started")

        while True:
            try:
                if await ks.is_active():
                    log.warning("signal_worker.kill_switch_active")
                    await asyncio.sleep(5)
                    continue

                messages = await self._r.xreadgroup(
                    _GROUP, _CONSUMER,
                    streams={_STREAM_IN: ">"},
                    count=_BATCH_SIZE,
                    block=_BLOCK_MS,
                )
                if not messages:
                    continue

                for _stream, entries in messages:
                    for msg_id, fields in entries:
                        await self._process_message(msg_id, fields)
                        await self._r.xack(_STREAM_IN, _GROUP, msg_id)

            except asyncio.CancelledError:
                break
            except Exception as exc:
                log.error("signal_worker.error", error=str(exc))
                await asyncio.sleep(1)

    async def _process_message(self, msg_id: bytes, fields: dict) -> None:
        try:
            data = json.loads(fields.get(b"data", b"{}"))
        except Exception:
            return

        event = _dict_to_trade_event(data)
        if event is None:
            return

        # Prefer the tracked wallet address (owner) when available.
        wallet = (data.get("tracked_wallet") or event.taker_address or "").lower()
        score = await self._get_score(wallet)

        signals = self._engine.process_event(event, score)
        for sig in signals:
            payload = {
                "signal_id": sig.signal_id,
                "strategy": sig.strategy,
                "market_id": sig.market_id,
                "asset_id": sig.asset_id,
                "side": sig.side.value,
                "confidence": sig.confidence,
                "entry_price": str(sig.entry_price),
                "size_pct": sig.size_pct,
                "tp_pct": sig.tp_pct,
                "sl_pct": sig.sl_pct,
                "max_holding_minutes": sig.max_holding_minutes,
                "source_wallet": sig.source_wallet,
                "timestamp": sig.timestamp.isoformat(),
                "reason": sig.reason,
            }
            assert self._r is not None
            await self._r.xadd(_STREAM_OUT, {"data": json.dumps(payload)})
            log.info(
                "signal_worker.emitted",
                signal_id=sig.signal_id[:8],
                strategy=sig.strategy,
                market=sig.market_id[:10],
            )

    async def _get_score(self, wallet: str) -> WalletScore | None:
        import time
        now = time.time()
        cached = self._score_cache.get(wallet)
        if cached and now - cached[1] < _SCORE_CACHE_TTL_SECONDS:
            return cached[0]

        try:
            trades = await self._subgraph.get_wallet_trades(wallet, days_back=30, max_fills=500)
            score = compute_score(trades)
        except Exception as exc:
            log.warning("signal_worker.score_failed", wallet=wallet[:10], error=str(exc)[:60])
            score = None

        self._score_cache[wallet] = (score, now)
        return score


def _dict_to_trade_event(data: dict) -> TradeEvent | None:
    try:
        from decimal import Decimal

        return TradeEvent(
            id=data["id"],
            market_id=data["market_id"],
            asset_id=data["asset_id"],
            outcome=data.get("outcome", "YES"),
            side=OrderSide(data["side"]),
            price=Decimal(str(data["price"])),
            size=Decimal(str(data["size"])),
            size_usd=Decimal(str(data["size_usd"])),
            fee_usd=Decimal(str(data.get("fee_usd", "0"))),
            maker_address=data.get("maker_address", ""),
            taker_address=data.get("taker_address", ""),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            tx_hash=data.get("tx_hash", ""),
        )
    except Exception as exc:
        log.warning("signal_worker.parse_error", error=str(exc)[:80])
        return None


async def main() -> None:
    configure_logging()
    worker = SignalWorker()
    await worker.start()


if __name__ == "__main__":
    asyncio.run(main())
