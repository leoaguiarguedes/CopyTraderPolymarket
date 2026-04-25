"""Tracker worker — Fase 1: filters raw trades by tracked wallets and persists.

Stub for Fase 0; full implementation lands in Fase 1.
"""
from __future__ import annotations

import asyncio

from app.utils.logger import configure_logging, get_logger


async def main() -> None:
    configure_logging()
    log = get_logger(__name__)
    log.info("tracker.starting")

    while True:
        log.info("tracker.heartbeat")
        await asyncio.sleep(30)


if __name__ == "__main__":
    asyncio.run(main())
