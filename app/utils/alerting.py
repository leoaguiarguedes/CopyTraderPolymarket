"""Alerting utilities — Discord webhook and Telegram bot."""
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import httpx

from app.utils.logger import get_logger

if TYPE_CHECKING:
    from app.config import Settings

log = get_logger(__name__)


class Alerter:
    """Sends fire-and-forget alerts to Discord and/or Telegram."""

    def __init__(self, settings: "Settings") -> None:
        self._discord_url = settings.discord_webhook_url
        self._tg_token = settings.telegram_bot_token.get_secret_value() if settings.telegram_bot_token else None
        self._tg_chat = settings.telegram_chat_id
        self._client = httpx.AsyncClient(timeout=10)

    async def send(self, message: str, *, title: str = "", level: str = "info") -> None:
        tasks = []
        if self._discord_url:
            tasks.append(self._send_discord(message, title=title, level=level))
        if self._tg_token and self._tg_chat:
            tasks.append(self._send_telegram(message, title=title))
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for r in results:
                if isinstance(r, Exception):
                    log.warning("alerting.send_failed", error=str(r)[:80])

    async def _send_discord(self, message: str, *, title: str, level: str) -> None:
        colour = {"info": 0x5865F2, "success": 0x57F287, "warning": 0xFEE75C, "error": 0xED4245}.get(level, 0x5865F2)
        payload = {
            "embeds": [{
                "title": title or "CopyTrader",
                "description": message[:2048],
                "color": colour,
            }]
        }
        resp = await self._client.post(self._discord_url, json=payload)
        resp.raise_for_status()

    async def _send_telegram(self, message: str, *, title: str) -> None:
        text = f"*{title}*\n{message}" if title else message
        url = f"https://api.telegram.org/bot{self._tg_token}/sendMessage"
        resp = await self._client.post(url, json={
            "chat_id": self._tg_chat,
            "text": text[:4096],
            "parse_mode": "Markdown",
        })
        resp.raise_for_status()

    async def close(self) -> None:
        await self._client.aclose()

    # ── Convenience wrappers ──────────────────────────────────────────────

    async def fill(self, position_id: str, market: str, side: str, price: float, size_usd: float) -> None:
        await self.send(
            f"Position `{position_id[:8]}` opened\n"
            f"Market: `{market[:20]}`\n"
            f"Side: **{side}** @ `{price:.4f}` | Size: `${size_usd:.2f}`",
            title="✅ Order Filled",
            level="success",
        )

    async def closed(self, position_id: str, reason: str, pnl_usd: float) -> None:
        emoji = "🟢" if pnl_usd >= 0 else "🔴"
        await self.send(
            f"Position `{position_id[:8]}` closed\n"
            f"Reason: **{reason}** | PnL: `{pnl_usd:+.4f} USDC`",
            title=f"{emoji} Position Closed",
            level="success" if pnl_usd >= 0 else "warning",
        )

    async def kill_switch(self, reason: str) -> None:
        await self.send(
            f"Kill switch activated: **{reason}**\nAll trading halted.",
            title="🚨 Kill Switch",
            level="error",
        )

    async def circuit_breaker(self, losses: int, threshold: float) -> None:
        await self.send(
            f"{losses} consecutive losses exceeding `{threshold:.1%}` expected.\nTrading paused — review required.",
            title="⚠️ Circuit Breaker Triggered",
            level="error",
        )

    async def reconciliation_mismatch(self, details: str) -> None:
        await self.send(
            details[:1000],
            title="🔍 Reconciliation Mismatch",
            level="warning",
        )

    async def error(self, component: str, detail: str) -> None:
        await self.send(
            f"Component: `{component}`\n{detail[:400]}",
            title="❌ System Error",
            level="error",
        )
