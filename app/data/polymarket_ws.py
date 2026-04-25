"""Polymarket WebSocket client — CLOB market channel.

Connects to wss://ws-subscriptions-clob.polymarket.com/ws/market and emits
TradeEvent objects for each matched trade. Reconnects automatically with
exponential backoff on disconnect.
"""
from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from decimal import Decimal
from typing import Any

import websockets
from websockets.exceptions import ConnectionClosed

from app.config import Settings, get_settings
from app.data.models import OrderSide, TradeEvent
from app.utils.logger import get_logger
from app.utils.metrics import trades_received_total, ws_disconnects_total
from app.utils.time import utcnow

log = get_logger(__name__)

_WS_PATH = "/ws/market"
_INITIAL_BACKOFF = 1.0
_MAX_BACKOFF = 60.0


class PolymarketWebSocket:
    """Async iterator that yields TradeEvent from the Polymarket CLOB WS."""

    def __init__(
        self,
        market_ids: list[str],
        asset_ids: list[str] | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._s = settings or get_settings()
        self._market_ids = market_ids
        self._asset_ids = asset_ids or []
        self._backoff = _INITIAL_BACKOFF
        self._running = True

    def stop(self) -> None:
        self._running = False

    async def stream(self) -> AsyncIterator[TradeEvent]:
        """Yield TradeEvents indefinitely, reconnecting on disconnect."""
        url = self._s.polymarket_ws_url + _WS_PATH
        while self._running:
            try:
                async with websockets.connect(url, ping_interval=20, ping_timeout=10) as ws:
                    log.info("ws.connected", url=url)
                    self._backoff = _INITIAL_BACKOFF
                    await self._subscribe(ws)
                    async for raw in ws:
                        events = self._parse_message(raw)
                        for event in events:
                            trades_received_total.labels(source="ws").inc()
                            yield event
            except ConnectionClosed as exc:
                ws_disconnects_total.labels(endpoint="market").inc()
                log.warning("ws.disconnected", reason=str(exc), backoff=self._backoff)
            except Exception as exc:
                ws_disconnects_total.labels(endpoint="market").inc()
                log.error("ws.error", error=str(exc), backoff=self._backoff)

            if not self._running:
                break
            await asyncio.sleep(self._backoff)
            self._backoff = min(self._backoff * 2, _MAX_BACKOFF)

    async def _subscribe(self, ws: Any) -> None:
        """Send subscription message for each market/asset."""
        subscriptions: list[dict[str, Any]] = []
        for market_id in self._market_ids:
            subscriptions.append({"type": "Market", "condition_id": market_id})
        for asset_id in self._asset_ids:
            subscriptions.append({"type": "Asset", "asset_id": asset_id})

        if subscriptions:
            msg = json.dumps(subscriptions)
            await ws.send(msg)
            log.debug("ws.subscribed", count=len(subscriptions))

    def _parse_message(self, raw: str | bytes) -> list[TradeEvent]:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return []

        # WS delivers single event or list
        events_raw: list[dict[str, Any]] = data if isinstance(data, list) else [data]
        result: list[TradeEvent] = []

        for msg in events_raw:
            event_type = msg.get("event_type") or msg.get("type", "")
            if event_type not in ("trade", "TRADE", "last_trade_price"):
                continue
            trade = self._parse_trade(msg)
            if trade:
                result.append(trade)

        return result

    def _parse_trade(self, msg: dict[str, Any]) -> TradeEvent | None:
        try:
            import datetime as _dt

            ts_raw = msg.get("timestamp") or msg.get("match_time")
            if ts_raw:
                if isinstance(ts_raw, (int, float)):
                    ts = _dt.datetime.fromtimestamp(int(ts_raw), tz=_dt.timezone.utc)
                else:
                    ts = _dt.datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00"))
            else:
                ts = utcnow()

            price = Decimal(str(msg.get("price", "0")))
            size = Decimal(str(msg.get("size", msg.get("shares", "0"))))
            size_usd = price * size

            side_raw = (msg.get("side") or msg.get("taker_side") or "BUY").upper()
            side = OrderSide.BUY if side_raw in ("BUY", "YES") else OrderSide.SELL

            trade_id = str(
                msg.get("id")
                or msg.get("trade_id")
                or f"{msg.get('transaction_hash', '')}-{msg.get('log_index', '0')}"
            )

            return TradeEvent(
                id=trade_id,
                market_id=str(msg.get("market_id") or msg.get("condition_id", "")),
                asset_id=str(msg.get("asset_id") or msg.get("token_id", "")),
                outcome=str(msg.get("outcome", "YES")).upper(),
                side=side,
                price=price,
                size=size,
                size_usd=size_usd,
                fee_usd=Decimal(str(msg.get("fee", "0"))),
                maker_address=str(msg.get("maker", msg.get("maker_address", ""))).lower(),
                taker_address=str(msg.get("taker", msg.get("taker_address", ""))).lower(),
                timestamp=ts,
                tx_hash=str(msg.get("transaction_hash") or msg.get("tx_hash", "")),
            )
        except Exception:
            log.warning("ws.trade_parse_failed", msg=msg)
            return None
