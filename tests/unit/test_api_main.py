import asyncio
import json
from types import SimpleNamespace

import pytest

from app.api import main


class DummyRedis:
    def __init__(self) -> None:
        self.active = False
        self.closed = False

    async def aclose(self) -> None:
        self.closed = True


class DummyKillSwitch:
    def __init__(self, redis: DummyRedis) -> None:
        self._redis = redis

    async def activate(self, reason: str = "") -> None:
        self._redis.active = True

    async def deactivate(self) -> None:
        self._redis.active = False

    async def is_active(self) -> bool:
        return self._redis.active


@pytest.mark.asyncio
async def test_toggle_kill_switch_activate(monkeypatch):
    settings = SimpleNamespace(redis_url="redis://localhost")
    dummy_redis = DummyRedis()

    monkeypatch.setattr(main, "get_settings", lambda: settings)
    monkeypatch.setattr(main.aioredis, "from_url", lambda url, decode_responses=False: dummy_redis)
    monkeypatch.setattr(main, "KillSwitch", DummyKillSwitch)

    result = await main.toggle_kill_switch(True)

    assert result == {"kill_switch": True}
    assert dummy_redis.active is True


@pytest.mark.asyncio
async def test_get_kill_switch(monkeypatch):
    settings = SimpleNamespace(redis_url="redis://localhost")
    dummy_redis = DummyRedis()

    monkeypatch.setattr(main, "get_settings", lambda: settings)
    monkeypatch.setattr(main.aioredis, "from_url", lambda url, decode_responses=False: dummy_redis)
    monkeypatch.setattr(main, "KillSwitch", DummyKillSwitch)

    dummy_redis.active = True
    result = await main.get_kill_switch()

    assert result == {"kill_switch": True}
    assert dummy_redis.closed is True


def test_metrics_response():
    response = main.metrics()

    assert response.media_type == main.CONTENT_TYPE_LATEST
    assert isinstance(response.body, (bytes, bytearray))
    assert b"# HELP" in response.body


@pytest.mark.asyncio
async def test_broadcast_removes_dead_websocket(monkeypatch):
    class FakeWs:
        def __init__(self, should_fail: bool = False) -> None:
            self.sent = []
            self.should_fail = should_fail

        async def send_text(self, text: str) -> None:
            if self.should_fail:
                raise RuntimeError("send failed")
            self.sent.append(text)

    ws_good = FakeWs(False)
    ws_bad = FakeWs(True)
    monkeypatch.setattr(main, "_ws_clients", [ws_good, ws_bad], raising=False)

    await main._broadcast("payload")

    assert ws_good.sent == ["payload"]
    assert ws_bad not in main._ws_clients


@pytest.mark.asyncio
async def test_ws_broadcast_loop_cancels_cleanly(monkeypatch):
    class FakeRedis:
        def __init__(self):
            self.closed = False

        async def xread(self, streams, count, block):
            await asyncio.sleep(0)
            return []

        async def aclose(self):
            self.closed = True

    monkeypatch.setattr(main.aioredis, "from_url", lambda url, decode_responses=False: FakeRedis())

    task = asyncio.create_task(main._ws_broadcast_loop("redis://localhost"))
    await asyncio.sleep(0)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_websocket_live_disconnects(monkeypatch):
    class FakeWebSocket:
        def __init__(self):
            self.accepted = False
            self.received = 0
            self.closed = False

        async def accept(self):
            self.accepted = True

        async def receive_text(self):
            self.received += 1
            raise main.WebSocketDisconnect()

        async def send_text(self, _: str):
            pass

    ws = FakeWebSocket()
    await main.websocket_live(ws)
    assert ws.accepted
    assert ws.received == 1
