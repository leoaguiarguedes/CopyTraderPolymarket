"""Proxy wallet resolver — maps Polymarket Gnosis Safe proxy ↔ owner EOA.

Polymarket creates a Gnosis Safe proxy per user. The address seen in trades
is the proxy (Safe), not the user's EOA. We need the mapping to resolve
which real user made a trade.

Cache is in-memory (dict) + optional Redis for cross-process sharing.
"""
from __future__ import annotations

from app.data.polymarket_rest import PolymarketRestClient
from app.utils.logger import get_logger

log = get_logger(__name__)


class ProxyResolver:
    def __init__(
        self,
        client: PolymarketRestClient,
        redis_client: "redis.asyncio.Redis | None" = None,  # type: ignore[name-defined]
    ) -> None:
        self._client = client
        self._redis = redis_client
        # in-process cache: proxy_address → owner_address
        self._cache: dict[str, str] = {}
        # reverse: owner → proxy
        self._reverse: dict[str, str] = {}

    async def proxy_to_owner(self, proxy_address: str) -> str:
        """Return the owner EOA for a proxy address.

        Falls back to the proxy itself if the mapping is unknown — so callers
        can always treat the return value as "the address to track."
        """
        proxy = proxy_address.lower()
        if proxy in self._cache:
            return self._cache[proxy]

        if self._redis:
            cached = await self._redis.get(f"proxy:{proxy}")
            if cached:
                owner = cached.decode()
                self._cache[proxy] = owner
                return owner

        # Polymarket gamma API: GET /proxy-wallet/{owner} → gives proxy for owner
        # We don't have a reverse endpoint, so we can't look up owner from proxy directly.
        # For discovery flow, we resolve owner→proxy up-front and store both directions.
        log.debug("proxy_resolver.cache_miss", proxy=proxy[:10])
        return proxy  # fall through: treat proxy as the address

    async def resolve_owner_proxy(self, owner_address: str) -> str | None:
        """Given an owner EOA, return their proxy (Safe) address."""
        owner = owner_address.lower()
        if owner in self._reverse:
            return self._reverse[owner]

        proxy = await self._client.get_proxy_wallet(owner)
        if proxy:
            proxy = proxy.lower()
            self._cache[proxy] = owner
            self._reverse[owner] = proxy
            if self._redis:
                await self._redis.set(f"proxy:{proxy}", owner, ex=86400 * 7)
            log.debug("proxy_resolver.resolved", owner=owner[:10], proxy=proxy[:10])
        return proxy

    async def preload(self, owner_addresses: list[str]) -> None:
        """Bulk-resolve owners → proxies and warm up the cache."""
        import asyncio

        async def _resolve_one(owner: str) -> None:
            try:
                await self.resolve_owner_proxy(owner)
            except Exception as exc:
                log.warning("proxy_resolver.preload_failed", owner=owner[:10], error=str(exc))

        await asyncio.gather(*[_resolve_one(a) for a in owner_addresses])
        log.info("proxy_resolver.preloaded", count=len(owner_addresses))

    def known_proxies(self) -> set[str]:
        return set(self._cache.keys())

    def known_owners(self) -> set[str]:
        return set(self._reverse.keys())
