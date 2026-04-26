"""Kill switch — global stop flag stored in Redis.

Any worker can check `is_active()` before processing.
The API can toggle via `activate()` / `deactivate()`.
"""
from __future__ import annotations

import redis.asyncio as aioredis

from app.utils.logger import get_logger

log = get_logger(__name__)

_KILL_SWITCH_KEY = "copytrader:kill_switch"


class KillSwitch:
    def __init__(self, redis: aioredis.Redis) -> None:
        self._r = redis

    async def is_active(self) -> bool:
        val = await self._r.get(_KILL_SWITCH_KEY)
        return val == b"1"

    async def activate(self, reason: str = "") -> None:
        await self._r.set(_KILL_SWITCH_KEY, "1")
        log.warning("kill_switch.activated", reason=reason)

    async def deactivate(self) -> None:
        await self._r.delete(_KILL_SWITCH_KEY)
        log.info("kill_switch.deactivated")
