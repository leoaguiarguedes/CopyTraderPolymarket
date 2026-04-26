"""Goldsky subgraph client for Polymarket historical data.

Two subgraphs are used:
  - orderbook-subgraph/0.0.1  → OrderFilledEvent (trade history per wallet)
  - pnl-subgraph/0.0.14       → UserPosition (PnL + leaderboard)

Amount encoding (confirmed from live data):
  - makerAmountFilled / takerAmountFilled are raw integer counts
  - When makerAssetId == "0": maker paid USDC, taker paid outcome tokens
      price = makerAmountFilled / takerAmountFilled  (0–1 probability)
      size_usd = makerAmountFilled / 1e6              (USDC with 6 decimals)
  - When takerAssetId == "0": inverse (maker sold tokens, got USDC)
  - avgPrice and realizedPnl in UserPosition are also 1e6-scaled
"""
from __future__ import annotations

import time
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import httpx

from app.config import Settings, get_settings
from app.data.models import OrderSide, WalletTrade
from app.utils.logger import get_logger

log = get_logger(__name__)

_USDC_ASSET_ID = "0"
_DECIMALS = Decimal("1000000")  # 1e6

# ── Queries ───────────────────────────────────────────────────────────────

_WALLET_TRADES_QUERY = """
query WalletTrades($wallet: String!, $first: Int!, $skip: Int!, $minTs: Int!) {
  orderFilledEvents(
    where: {
      taker: $wallet
      timestamp_gte: $minTs
    }
    first: $first
    skip: $skip
    orderBy: timestamp
    orderDirection: asc
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

_WALLET_MAKER_TRADES_QUERY = """
query WalletMakerTrades($wallet: String!, $first: Int!, $skip: Int!, $minTs: Int!) {
  orderFilledEvents(
    where: {
      maker: $wallet
      timestamp_gte: $minTs
    }
    first: $first
    skip: $skip
    orderBy: timestamp
    orderDirection: asc
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

_LEADERBOARD_QUERY = """
query TopPositions($first: Int!, $skip: Int!, $minPnl: String!) {
  userPositions(
    where: { realizedPnl_gt: $minPnl }
    first: $first
    skip: $skip
    orderBy: realizedPnl
    orderDirection: desc
  ) {
    user
    tokenId
    realizedPnl
    totalBought
    avgPrice
    amount
  }
}
"""

_WALLET_PNL_QUERY = """
query WalletPnl($wallet: String!, $first: Int!, $skip: Int!) {
  userPositions(
    where: { user: $wallet }
    first: $first
    skip: $skip
  ) {
    tokenId
    realizedPnl
    totalBought
    avgPrice
    amount
  }
}
"""

_RECENT_EVENTS_QUERY = """
query RecentEvents($minTs: Int!, $first: Int!, $skip: Int!) {
  orderFilledEvents(
    where: { timestamp_gte: $minTs }
    first: $first
    skip: $skip
    orderBy: timestamp
    orderDirection: desc
  ) {
    taker
    maker
    makerAmountFilled
    takerAmountFilled
  }
}
"""


class SubgraphClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self._s = settings or get_settings()

    async def _query(
        self,
        url: str,
        query: str,
        variables: dict[str, Any],
        timeout: float = 30.0,
    ) -> dict[str, Any]:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._s.subgraph_api_key:
            headers["Authorization"] = f"Bearer {self._s.subgraph_api_key.get_secret_value()}"

        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(
                url,
                json={"query": query, "variables": variables},
                headers=headers,
            )
            r.raise_for_status()
            body = r.json()

        if errors := body.get("errors"):
            log.error("subgraph.graphql_error", errors=errors, url=url)
            raise RuntimeError(f"Subgraph errors: {errors}")

        return body.get("data", {})

    # ── Leaderboard (pnl-subgraph) ────────────────────────────────────────

    async def get_top_wallets(
        self,
        limit: int = 500,
        min_pnl_usd: float = 10.0,
    ) -> list[dict[str, Any]]:
        """Return deduplicated top wallets by realized PnL from the PnL subgraph.

        Returns list of {id, profit, volume, numTrades} dicts compatible with
        the discover_wallets.py consumer.
        """
        # min_pnl in raw units (1e6 scale)
        min_pnl_raw = str(int(min_pnl_usd * 1_000_000))

        seen_wallets: dict[str, dict[str, Any]] = {}
        skip = 0
        page_size = 100

        while len(seen_wallets) < limit:
            data = await self._query(
                self._s.subgraph_pnl_url,
                _LEADERBOARD_QUERY,
                {
                    "first": page_size,
                    "skip": skip,
                    "minPnl": min_pnl_raw,
                },
            )
            rows: list[dict[str, Any]] = data.get("userPositions", [])
            if not rows:
                break

            for row in rows:
                user = row.get("user", "").lower()
                if not user:
                    continue
                if user not in seen_wallets:
                    pnl_raw = int(row.get("realizedPnl", "0") or "0")
                    bought_raw = int(row.get("totalBought", "0") or "0")
                    seen_wallets[user] = {
                        "id": user,
                        "profit": pnl_raw / 1_000_000,
                        "volume": bought_raw / 1_000_000,
                        "numTrades": 1,  # will be counted from orderbook
                    }
                else:
                    # accumulate PnL across positions for same wallet
                    pnl_raw = int(row.get("realizedPnl", "0") or "0")
                    bought_raw = int(row.get("totalBought", "0") or "0")
                    seen_wallets[user]["profit"] += pnl_raw / 1_000_000
                    seen_wallets[user]["volume"] += bought_raw / 1_000_000

            if len(rows) < page_size:
                break
            skip += page_size

        result = sorted(seen_wallets.values(), key=lambda x: x["profit"], reverse=True)[:limit]
        log.info("subgraph.leaderboard_fetched", total=len(result))
        return result

    # ── Active wallet discovery (orderbook-subgraph) ─────────────────────

    async def get_active_wallets(
        self,
        days_back: int = 30,
        min_fills: int = 20,
        max_fills_in_sample: int = 500,
        limit: int = 200,
        max_events: int = 10_000,
    ) -> list[dict[str, Any]]:
        """Discover recently active CLOB traders from the orderbook subgraph.

        Scans recent OrderFilledEvents and ranks wallets by fill count.
        max_fills_in_sample filters out likely bots (wallets with too many
        fills even in the limited event sample are almost certainly market makers).
        Returns list of {id, fills, profit, volume, numTrades} dicts.
        """
        min_ts = int(time.time()) - days_back * 86400
        wallet_fills: dict[str, int] = defaultdict(int)
        wallet_usdc: dict[str, float] = defaultdict(float)
        skip = 0
        page_size = 1000
        total_fetched = 0

        while total_fetched < max_events:
            data = await self._query(
                self._s.subgraph_url,
                _RECENT_EVENTS_QUERY,
                {"minTs": min_ts, "first": page_size, "skip": skip},
            )
            rows: list[dict[str, Any]] = data.get("orderFilledEvents", [])
            if not rows:
                break

            for row in rows:
                taker = row.get("taker", "").lower()
                maker = row.get("maker", "").lower()
                # Compute USDC amount for this fill
                ma = int(row.get("makerAmountFilled", "0") or "0")
                ta = int(row.get("takerAmountFilled", "0") or "0")
                # Either maker or taker provided USDC (the smaller of the two in prediction markets)
                usdc = min(ma, ta) / 1_000_000 if min(ma, ta) > 0 else 0.0
                if taker:
                    wallet_fills[taker] += 1
                    wallet_usdc[taker] += usdc
                if maker:
                    wallet_fills[maker] += 1
                    wallet_usdc[maker] += usdc

            total_fetched += len(rows)
            if len(rows) < page_size:
                break
            skip += page_size

        active = [
            {
                "id": addr,
                "fills": count,
                "profit": 0.0,
                "volume": wallet_usdc.get(addr, 0.0),
                "numTrades": count,
            }
            for addr, count in wallet_fills.items()
            if min_fills <= count <= max_fills_in_sample
        ]
        active.sort(key=lambda x: x["fills"], reverse=True)
        result = active[:limit]
        log.info(
            "subgraph.active_wallets_discovered",
            total_events=total_fetched,
            unique_wallets=len(wallet_fills),
            qualifying=len(active),
            returned=len(result),
        )
        return result

    # ── Wallet trade history (orderbook-subgraph) ─────────────────────────

    async def get_wallet_trades(
        self,
        wallet_address: str,
        days_back: int = 90,
        page_size: int = 500,
        max_fills: int = 3000,
    ) -> list[WalletTrade]:
        """Fetch fills for a wallet (as taker + as maker) going back days_back days.

        max_fills caps the total per direction to avoid bot wallets that have
        hundreds of thousands of fills and cause subgraph statement timeouts.
        Anything beyond max_fills/2 per side is almost certainly a market-maker
        bot, not a human directional trader worth copying.
        """
        wallet = wallet_address.lower()
        min_ts = int(time.time()) - days_back * 86400
        per_side = max_fills // 2

        taker_fills = await self._fetch_fills(
            wallet, as_taker=True, min_ts=min_ts, page_size=page_size, max_fills=per_side
        )
        maker_fills = await self._fetch_fills(
            wallet, as_taker=False, min_ts=min_ts, page_size=page_size, max_fills=per_side
        )

        all_fills = taker_fills + maker_fills
        # deduplicate
        seen: set[str] = set()
        unique = []
        for f in all_fills:
            if f["id"] not in seen:
                seen.add(f["id"])
                unique.append(f)

        trades = self._fills_to_wallet_trades(unique, wallet)
        log.info("subgraph.wallet_trades_fetched", wallet=wallet[:10], fills=len(unique), trades=len(trades))
        return trades

    async def _fetch_fills(
        self,
        wallet: str,
        as_taker: bool,
        min_ts: int,
        page_size: int,
        max_fills: int = 1500,
    ) -> list[dict[str, Any]]:
        """Page through fills, stopping at max_fills to avoid deep-pagination timeouts."""
        query = _WALLET_TRADES_QUERY if as_taker else _WALLET_MAKER_TRADES_QUERY
        fills: list[dict[str, Any]] = []
        skip = 0
        while len(fills) < max_fills:
            data = await self._query(
                self._s.subgraph_url,
                query,
                {"wallet": wallet, "first": page_size, "skip": skip, "minTs": min_ts},
            )
            rows: list[dict[str, Any]] = data.get("orderFilledEvents", [])
            fills.extend(rows)
            if len(rows) < page_size:
                break
            skip += page_size
        return fills[:max_fills]

    def _fills_to_wallet_trades(
        self, fills: list[dict[str, Any]], wallet: str
    ) -> list[WalletTrade]:
        """Convert raw fills to WalletTrade, grouped by outcome token.

        CLOB direction semantics (confirmed from live data):
          makerAssetId=0 → maker provided USDC, taker provided tokens
            → taker SOLD tokens, received USDC
            → maker BOUGHT tokens, paid USDC
          takerAssetId=0 → taker provided USDC, maker provided tokens
            → taker BOUGHT tokens, paid USDC
            → maker SOLD tokens, received USDC

        For each fill we tag whether wallet was acting as taker or maker,
        then compute the direction (BUY/SELL from wallet's perspective).
        """
        by_token: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for f in fills:
            maker_asset = f.get("makerAssetId", "")
            taker_asset = f.get("takerAssetId", "")
            # The outcome token is whichever asset is NOT USDC
            token_id = taker_asset if maker_asset == _USDC_ASSET_ID else maker_asset
            if not token_id:
                continue
            by_token[token_id].append(f)

        trades: list[WalletTrade] = []
        for token_id, token_fills in by_token.items():
            token_fills.sort(key=lambda x: int(x.get("timestamp", 0)))

            usdc_in = Decimal(0)    # USDC spent to buy tokens
            usdc_out = Decimal(0)   # USDC received from selling tokens
            total_size_usd = Decimal(0)
            buy_fills: list[dict[str, Any]] = []
            sell_fills: list[dict[str, Any]] = []

            for f in token_fills:
                maker_asset = f.get("makerAssetId", "")
                maker_amt = Decimal(str(f.get("makerAmountFilled", "0") or "0"))
                taker_amt = Decimal(str(f.get("takerAmountFilled", "0") or "0"))
                wallet_is_taker = f.get("taker", "").lower() == wallet
                wallet_is_maker = f.get("maker", "").lower() == wallet

                if maker_asset == _USDC_ASSET_ID:
                    # maker paid USDC → maker BOUGHT tokens
                    # taker paid tokens → taker SOLD tokens
                    usdc_amount = maker_amt / _DECIMALS
                    if wallet_is_maker:
                        # wallet is buyer
                        usdc_in += usdc_amount
                        total_size_usd += usdc_amount
                        buy_fills.append(f)
                    elif wallet_is_taker:
                        # wallet is seller
                        usdc_out += usdc_amount
                        total_size_usd += usdc_amount
                        sell_fills.append(f)
                else:
                    # takerAssetId == "0": taker paid USDC → taker BOUGHT tokens
                    # maker paid tokens → maker SOLD tokens
                    usdc_amount = taker_amt / _DECIMALS
                    if wallet_is_taker:
                        # wallet is buyer
                        usdc_in += usdc_amount
                        total_size_usd += usdc_amount
                        buy_fills.append(f)
                    elif wallet_is_maker:
                        # wallet is seller
                        usdc_out += usdc_amount
                        total_size_usd += usdc_amount
                        sell_fills.append(f)

            if not buy_fills and not sell_fills:
                continue

            # Need at least 1 buy to estimate entry price
            entry_fills = buy_fills or sell_fills
            first_ts = int(token_fills[0].get("timestamp", 0))
            last_ts = int(token_fills[-1].get("timestamp", 0))
            has_both = bool(buy_fills and sell_fills)
            pnl = (usdc_out - usdc_in) if has_both else None

            # Average entry price from buy fills
            if buy_fills:
                prices = []
                for f in buy_fills:
                    maker_asset = f.get("makerAssetId", "")
                    ma = Decimal(str(f.get("makerAmountFilled", "1") or "1"))
                    ta = Decimal(str(f.get("takerAmountFilled", "1") or "1"))
                    if maker_asset == _USDC_ASSET_ID:
                        # wallet is maker buying: price = USDC / tokens
                        if ta > 0:
                            prices.append(ma / ta)
                    else:
                        # wallet is taker buying: price = USDC(taker) / tokens(maker)
                        if ma > 0:
                            prices.append(ta / ma)
                avg_price = sum(prices) / len(prices) if prices else Decimal("0.5")
            else:
                avg_price = Decimal("0.5")

            open_ts = datetime.fromtimestamp(first_ts, tz=timezone.utc)
            close_ts = datetime.fromtimestamp(last_ts, tz=timezone.utc) if has_both else None

            trades.append(
                WalletTrade(
                    trade_id=entry_fills[0]["id"],
                    wallet_address=wallet,
                    market_id=token_id,
                    outcome="YES",
                    side=OrderSide.BUY if buy_fills else OrderSide.SELL,
                    price=avg_price,
                    size_usd=total_size_usd,
                    cost_usd=usdc_in,   # invested capital (buy side only)
                    opened_at=open_ts,
                    closed_at=close_ts,
                    realized_pnl_usd=pnl,
                )
            )

        return trades

    # ── Wallet PnL summary (pnl-subgraph) ────────────────────────────────

    async def get_wallet_pnl_summary(
        self, wallet_address: str
    ) -> dict[str, float]:
        """Fast PnL summary for a wallet from the pnl-subgraph."""
        wallet = wallet_address.lower()
        positions: list[dict[str, Any]] = []
        skip = 0
        while True:
            data = await self._query(
                self._s.subgraph_pnl_url,
                _WALLET_PNL_QUERY,
                {"wallet": wallet, "first": 500, "skip": skip},
            )
            rows = data.get("userPositions", [])
            positions.extend(rows)
            if len(rows) < 500:
                break
            skip += 500

        if not positions:
            return {"total_pnl_usd": 0.0, "total_volume_usd": 0.0, "n_positions": 0}

        total_pnl = sum(int(p.get("realizedPnl", "0") or "0") for p in positions) / 1_000_000
        total_bought = sum(int(p.get("totalBought", "0") or "0") for p in positions) / 1_000_000
        return {
            "total_pnl_usd": total_pnl,
            "total_volume_usd": total_bought,
            "n_positions": len(positions),
        }
