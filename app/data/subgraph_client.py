"""The Graph / Goldsky subgraph client for Polymarket historical data.

Used for wallet discovery and scoring — not for real-time tracking (use WS for that).
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

import httpx

from app.config import Settings, get_settings
from app.data.models import OrderSide, WalletTrade
from app.utils.logger import get_logger
from app.utils.time import utcnow

log = get_logger(__name__)

_TRADES_QUERY = """
query WalletTrades($wallet: String!, $first: Int!, $skip: Int!, $minTs: BigInt!) {
  orderFilledEvents(
    where: {
      trader: $wallet
      timestamp_gte: $minTs
    }
    first: $first
    skip: $skip
    orderBy: timestamp
    orderDirection: desc
  ) {
    id
    timestamp
    market { id }
    outcomeIndex
    side
    price
    amount
    fee
  }
}
"""

_LEADERBOARD_QUERY = """
query Leaderboard($first: Int!, $skip: Int!, $minVolume: BigDecimal!) {
  userStats(
    where: { volume_gte: $minVolume }
    first: $first
    skip: $skip
    orderBy: profit
    orderDirection: desc
  ) {
    id
    profit
    volume
    numTrades
  }
}
"""


class SubgraphClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self._s = settings or get_settings()

    async def _query(
        self, query: str, variables: dict[str, Any], timeout: float = 30.0
    ) -> dict[str, Any]:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._s.subgraph_api_key:
            headers["Authorization"] = f"Bearer {self._s.subgraph_api_key.get_secret_value()}"

        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(
                self._s.subgraph_url,
                json={"query": query, "variables": variables},
                headers=headers,
            )
            r.raise_for_status()
            body = r.json()

        if errors := body.get("errors"):
            log.error("subgraph.graphql_error", errors=errors)
            raise RuntimeError(f"Subgraph errors: {errors}")

        return body.get("data", {})

    # ── Wallet trades ─────────────────────────────────────────────────────

    async def get_wallet_trades(
        self,
        wallet_address: str,
        days_back: int = 90,
        page_size: int = 500,
    ) -> list[WalletTrade]:
        """Fetch all trades for a wallet going back `days_back` days."""
        import time

        min_ts = int(time.time()) - days_back * 86400
        wallet = wallet_address.lower()
        trades: list[WalletTrade] = []
        skip = 0

        while True:
            data = await self._query(
                _TRADES_QUERY,
                {"wallet": wallet, "first": page_size, "skip": skip, "minTs": min_ts},
            )
            raw_events: list[dict[str, Any]] = data.get("orderFilledEvents", [])
            for ev in raw_events:
                t = self._parse_wallet_trade(ev, wallet)
                if t:
                    trades.append(t)

            if len(raw_events) < page_size:
                break
            skip += page_size

        log.info("subgraph.wallet_trades_fetched", wallet=wallet[:10], total=len(trades))
        return trades

    # ── Leaderboard ───────────────────────────────────────────────────────

    async def get_top_wallets(
        self,
        limit: int = 500,
        min_volume_usd: float = 500.0,
    ) -> list[dict[str, Any]]:
        """Return top wallets by profit from the subgraph leaderboard."""
        wallets: list[dict[str, Any]] = []
        skip = 0
        page_size = 100

        while len(wallets) < limit:
            data = await self._query(
                _LEADERBOARD_QUERY,
                {
                    "first": min(page_size, limit - len(wallets)),
                    "skip": skip,
                    "minVolume": str(min_volume_usd),
                },
            )
            rows: list[dict[str, Any]] = data.get("userStats", [])
            wallets.extend(rows)
            if len(rows) < page_size:
                break
            skip += page_size

        log.info("subgraph.leaderboard_fetched", total=len(wallets))
        return wallets

    # ── Parsers ───────────────────────────────────────────────────────────

    def _parse_wallet_trade(
        self, raw: dict[str, Any], wallet: str
    ) -> WalletTrade | None:
        try:
            import datetime as _dt

            ts = _dt.datetime.fromtimestamp(
                int(raw["timestamp"]), tz=_dt.timezone.utc
            )
            price = Decimal(str(raw.get("price", "0")))
            amount = Decimal(str(raw.get("amount", "0")))
            size_usd = price * amount

            side_raw = str(raw.get("side", "0"))
            side = OrderSide.BUY if side_raw in ("0", "BUY") else OrderSide.SELL

            outcome_idx = int(raw.get("outcomeIndex", 0))
            outcome = "YES" if outcome_idx == 0 else "NO"

            market_id = raw.get("market", {}).get("id", "")

            return WalletTrade(
                trade_id=raw["id"],
                wallet_address=wallet,
                market_id=market_id,
                outcome=outcome,
                side=side,
                price=price,
                size_usd=size_usd,
                opened_at=ts,
                closed_at=None,  # subgraph doesn't give close time directly
                realized_pnl_usd=None,
            )
        except Exception:
            log.warning("subgraph.trade_parse_failed", raw=raw)
            return None
