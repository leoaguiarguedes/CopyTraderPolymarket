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
        tag_id: int | None = None,
    ) -> list[Market]:
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if active:
            params["active"] = "true"
            params["closed"] = "false"
        if tag_id is not None:
            params["tag_id"] = tag_id
        r = await self._gamma.get("/markets", params=params)
        r.raise_for_status()
        payload = r.json()
        # Gamma API may return {"data": [...]} or a plain list
        items: list = payload.get("data", payload) if isinstance(payload, dict) else payload
        return [self._parse_market(m) for m in items if isinstance(m, dict)]

    @retry(wait=wait_exponential(min=1, max=30), stop=stop_after_attempt(5), reraise=True)
    async def get_market(self, condition_id: str) -> Market | None:
        r = await self._gamma.get(f"/markets/{condition_id}")
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return self._parse_market(r.json())

    async def get_markets_by_token_ids(self, token_ids: list[str]) -> list[Market]:
        """Lookup markets by their outcome token IDs (decimal strings).

        The Gamma API accepts comma-separated token_ids and returns the parent
        markets that contain those tokens.  Used to enrich [pending] market stubs
        created from the subgraph (which only provides token IDs, not slugs).
        """
        if not token_ids:
            return []
        # Gamma API accepts decimal token_ids (not hex)
        ids_param = ",".join(token_ids[:50])  # max 50 per request
        try:
            r = await self._gamma.get(
                "/markets",
                params={"token_ids": ids_param, "limit": len(token_ids[:50])},
            )
            r.raise_for_status()
            payload = r.json()
            items: list = payload.get("data", payload) if isinstance(payload, dict) else payload
            return [self._parse_market(m) for m in items if isinstance(m, dict)]
        except Exception as exc:
            log.warning("rest.token_id_lookup_failed", error=str(exc)[:80])
            return []

    async def get_all_active_markets(
        self,
        max_markets: int = 2000,
        tag_ids: list[int] | None = None,
    ) -> list[Market]:
        """Paginate through active markets, optionally filtering by tag_id list (OR logic)."""
        if not tag_ids:
            # No filter — fetch all
            return await self._paginate_markets(max_markets, tag_id=None)

        # Fetch each tag separately and merge (Gamma API supports one tag_id at a time)
        seen: set[str] = set()
        merged: list[Market] = []
        for tid in tag_ids:
            page_markets = await self._paginate_markets(max_markets, tag_id=tid)
            for m in page_markets:
                if m.condition_id not in seen:
                    seen.add(m.condition_id)
                    merged.append(m)
                    if len(merged) >= max_markets:
                        break
            if len(merged) >= max_markets:
                break

        log.info("rest.markets_fetched", total=len(merged), tags=tag_ids)
        return merged

    async def _paginate_markets(self, max_markets: int, tag_id: int | None) -> list[Market]:
        markets: list[Market] = []
        offset = 0
        limit = 100
        while len(markets) < max_markets:
            page = await self.get_markets(active=True, limit=limit, offset=offset, tag_id=tag_id)
            markets.extend(page)
            if len(page) < limit:
                break
            offset += limit
        return markets[:max_markets]

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

        # "tokens" may be a JSON string '["id1","id2"]', a list of dicts, or a list of strings
        tokens_raw = raw.get("tokens", []) or raw.get("clobTokenIds", [])
        if isinstance(tokens_raw, str):
            try:
                import json as _json
                tokens_raw = _json.loads(tokens_raw)
            except Exception:
                tokens_raw = []
        token_ids: list[str] = []
        for t in (tokens_raw or []):
            if isinstance(t, dict):
                token_ids.append(str(t.get("token_id") or t.get("tokenID") or ""))
            elif t:
                token_ids.append(str(t))

        # Parse tags from Gamma API: list of {id, label, slug} objects
        raw_tags = raw.get("tags") or []
        tags = [
            {"id": t.get("id"), "label": t.get("label", ""), "slug": t.get("slug", "")}
            for t in raw_tags
            if isinstance(t, dict) and t.get("id") is not None
        ]

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
            tags=tags,
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
