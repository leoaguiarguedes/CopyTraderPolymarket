"""Polymarket REST client — Gamma (markets) + CLOB (orderbook, trades)."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import Settings, get_settings
from app.data.models import Market, OrderBook, OrderBookLevel, TradeEvent
from app.utils.logger import get_logger
from app.utils.time import utcnow

log = get_logger(__name__)


class PolymarketRestClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self._s = settings or get_settings()
        self._gamma = httpx.AsyncClient(
            base_url=self._s.polymarket_gamma_url,
            timeout=15.0,
            headers={"Accept": "application/json"},
        )
        self._clob = httpx.AsyncClient(
            base_url=self._s.polymarket_clob_url,
            timeout=15.0,
            headers={"Accept": "application/json"},
        )

    async def aclose(self) -> None:
        await self._gamma.aclose()
        await self._clob.aclose()

    async def __aenter__(self) -> PolymarketRestClient:
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.aclose()

    # ── Markets ───────────────────────────────────────────────────────────

    @retry(wait=wait_exponential(min=1, max=30), stop=stop_after_attempt(5), reraise=True)
    async def get_markets(
        self,
        active: bool = True,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Market]:
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if active:
            params["active"] = "true"
            params["closed"] = "false"
        r = await self._gamma.get("/markets", params=params)
        r.raise_for_status()
        return [self._parse_market(m) for m in r.json()]

    @retry(wait=wait_exponential(min=1, max=30), stop=stop_after_attempt(5), reraise=True)
    async def get_market(self, condition_id: str) -> Market | None:
        r = await self._gamma.get(f"/markets/{condition_id}")
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return self._parse_market(r.json())

    async def get_all_active_markets(self) -> list[Market]:
        """Paginate through all active markets."""
        markets: list[Market] = []
        offset = 0
        limit = 100
        while True:
            page = await self.get_markets(active=True, limit=limit, offset=offset)
            markets.extend(page)
            if len(page) < limit:
                break
            offset += limit
        log.info("rest.markets_fetched", total=len(markets))
        return markets

    # ── Proxy wallet ──────────────────────────────────────────────────────

    @retry(wait=wait_exponential(min=1, max=30), stop=stop_after_attempt(3), reraise=True)
    async def get_proxy_wallet(self, owner_address: str) -> str | None:
        """Return the proxy (Safe) address for a given owner EOA, or None."""
        r = await self._gamma.get(f"/proxy-wallet/{owner_address.lower()}")
        if r.status_code == 404:
            return None
        r.raise_for_status()
        data = r.json()
        return data.get("proxyWallet") or data.get("proxy_wallet")

    # ── Orderbook ─────────────────────────────────────────────────────────

    @retry(wait=wait_exponential(min=1, max=30), stop=stop_after_attempt(5), reraise=True)
    async def get_orderbook(self, token_id: str) -> OrderBook:
        r = await self._clob.get("/book", params={"token_id": token_id})
        r.raise_for_status()
        data = r.json()
        return OrderBook(
            market_id=data.get("market", ""),
            asset_id=token_id,
            bids=[
                OrderBookLevel(price=Decimal(str(b["price"])), size=Decimal(str(b["size"])))
                for b in data.get("bids", [])
            ],
            asks=[
                OrderBookLevel(price=Decimal(str(a["price"])), size=Decimal(str(a["size"])))
                for a in data.get("asks", [])
            ],
            timestamp=utcnow(),
        )

    # ── Trades ────────────────────────────────────────────────────────────

    @retry(wait=wait_exponential(min=1, max=30), stop=stop_after_attempt(5), reraise=True)
    async def get_trades(
        self,
        market_id: str | None = None,
        maker: str | None = None,
        taker: str | None = None,
        limit: int = 100,
        after_ts: int | None = None,
    ) -> list[TradeEvent]:
        """Fetch trades from the CLOB data API with optional filters."""
        params: dict[str, Any] = {"limit": limit}
        if market_id:
            params["market"] = market_id
        if maker:
            params["maker"] = maker
        if taker:
            params["taker"] = taker
        if after_ts:
            params["after"] = after_ts

        # trades endpoint lives on the data API
        async with httpx.AsyncClient(
            base_url=self._s.polymarket_data_url, timeout=15.0
        ) as data_client:
            r = await data_client.get("/trades", params=params)
            r.raise_for_status()

        raw: list[dict[str, Any]] = r.json()
        events = [self._parse_trade(t) for t in raw if t]
        return [e for e in events if e is not None]

    # ── Parsers ───────────────────────────────────────────────────────────

    def _parse_market(self, raw: dict[str, Any]) -> Market:
        end_date: datetime | None = None
        if raw.get("endDate") or raw.get("end_date"):
            try:
                raw_end = raw.get("endDate") or raw.get("end_date", "")
                end_date = datetime.fromisoformat(str(raw_end).replace("Z", "+00:00"))
            except (ValueError, TypeError):
                pass

        tokens: list[dict[str, Any]] = raw.get("tokens", []) or raw.get("clobTokenIds", [])
        token_ids = [str(t.get("token_id") or t) for t in tokens if t]

        return Market(
            condition_id=raw.get("conditionId") or raw.get("condition_id", ""),
            question=raw.get("question", ""),
            slug=raw.get("slug"),
            category=raw.get("category"),
            end_date=end_date,
            is_active=bool(raw.get("active", True)),
            is_resolved=bool(raw.get("closed", False)),
            resolved_outcome=raw.get("resolution"),
            volume_24h_usd=Decimal(str(raw["volume24hr"])) if raw.get("volume24hr") else None,
            liquidity_usd=Decimal(str(raw["liquidity"])) if raw.get("liquidity") else None,
            token_ids=token_ids,
        )

    def _parse_trade(self, raw: dict[str, Any]) -> TradeEvent | None:
        try:
            from app.data.models import OrderSide

            ts_raw = raw.get("timestamp") or raw.get("created_at") or raw.get("matchTime", 0)
            if isinstance(ts_raw, (int, float)):
                ts = datetime.fromtimestamp(int(ts_raw), tz=__import__("datetime").timezone.utc)
            else:
                ts = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00"))

            price = Decimal(str(raw.get("price", "0")))
            size = Decimal(str(raw.get("size", raw.get("outcomeTokens", "0"))))
            size_usd = price * size

            side_raw = (raw.get("side") or raw.get("takerSide") or "BUY").upper()
            side = OrderSide.BUY if side_raw in ("BUY", "YES") else OrderSide.SELL

            return TradeEvent(
                id=str(raw.get("id") or raw.get("tradeId", "")),
                market_id=str(raw.get("market") or raw.get("conditionId", "")),
                asset_id=str(raw.get("asset_id") or raw.get("tokenId", "")),
                outcome=str(raw.get("outcome", "YES")).upper(),
                side=side,
                price=price,
                size=size,
                size_usd=size_usd,
                fee_usd=Decimal(str(raw.get("fee", "0"))),
                maker_address=str(raw.get("maker", raw.get("makerAddress", ""))).lower(),
                taker_address=str(raw.get("taker", raw.get("takerAddress", ""))).lower(),
                timestamp=ts,
                tx_hash=str(raw.get("transactionHash") or raw.get("tx_hash", "")),
            )
        except Exception:
            log.warning("rest.trade_parse_failed", raw=raw)
            return None
