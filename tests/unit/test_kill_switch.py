import pytest

from app.risk.kill_switch import KillSwitch


class DummyRedis:
    def __init__(self) -> None:
        self.store = {}

    async def get(self, key: str):
        value = self.store.get(key)
        if isinstance(value, str):
            return value.encode()
        return value

    async def set(self, key: str, value: str):
        self.store[key] = value

    async def delete(self, key: str):
        self.store.pop(key, None)


@pytest.mark.asyncio
async def test_kill_switch_activation_and_deactivation() -> None:
    r = DummyRedis()
    ks = KillSwitch(r)

    assert await ks.is_active() is False
    await ks.activate("manual")
    assert await ks.is_active() is True
    await ks.deactivate()
    assert await ks.is_active() is False
