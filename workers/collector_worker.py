"""Collector worker — Fase 1: connects to Polymarket WebSocket and emits raw trades.

Stub for Fase 0; full implementation lands in Fase 1.
"""
from __future__ import annotations

import asyncio

from app.utils.logger import configure_logging, get_logger


async def main() -> None:
    configure_logging()
    log = get_logger(__name__)
    log.info("collector.starting")

    while True:
        log.info("collector.heartbeat")
        await asyncio.sleep(30)


if __name__ == "__main__":
    asyncio.run(main())
