import pytest
from app.tracker.proxy_resolver import ProxyResolver


class DummyClient:
    def __init__(self, proxy: str) -> None:
        self._proxy = proxy

    async def get_proxy_wallet(self, owner: str) -> str:
        return self._proxy


class DummyRedis:
    def __init__(self) -> None:
        self._store = {}

    async def get(self, key: str):
        return self._store.get(key)

    async def set(self, key: str, value: str, ex: int = None) -> None:
        self._store[key] = value


@pytest.mark.asyncio
async def test_resolve_owner_proxy_caches_result() -> None:
    client = DummyClient("0xproxy")
    redis = DummyRedis()
    resolver = ProxyResolver(client, redis)

    proxy = await resolver.resolve_owner_proxy("0xowner")
    assert proxy == "0xproxy"
    assert "0xproxy" in resolver.known_proxies()
    assert "0xowner" in resolver.known_owners()
    assert await resolver.proxy_to_owner("0xproxy") == "0xowner"
    assert redis._store["proxy:0xproxy"] == "0xowner"


@pytest.mark.asyncio
async def test_proxy_to_owner_returns_proxy_on_cache_miss() -> None:
    client = DummyClient("0xproxy")
    resolver = ProxyResolver(client)
    assert await resolver.proxy_to_owner("0xunknown") == "0xunknown"


@pytest.mark.asyncio
async def test_preload_handles_exceptions() -> None:
    class BadClient(DummyClient):
        async def get_proxy_wallet(self, owner: str) -> str:
            raise RuntimeError("fail")

    resolver = ProxyResolver(BadClient("0xproxy"))
    await resolver.preload(["0xowner"])
    assert resolver.known_proxies() == set()
