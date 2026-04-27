"""Tests for Alerter — verifies payload construction without hitting real webhooks."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.utils.alerting import Alerter


def _make_settings(discord: str | None = None, tg_token: str | None = None, tg_chat: str | None = None):
    s = MagicMock()
    s.discord_webhook_url = discord
    if tg_token:
        tg = MagicMock()
        tg.get_secret_value.return_value = tg_token
        s.telegram_bot_token = tg
    else:
        s.telegram_bot_token = None
    s.telegram_chat_id = tg_chat
    return s


def test_send_no_channels_is_noop():
    async def _run():
        alerter = Alerter(_make_settings())
        await alerter.send("hello")
        await alerter.close()

    asyncio.run(_run())


def test_discord_payload_posted():
    async def _run():
        settings = _make_settings(discord="https://discord.example/webhook")
        alerter = Alerter(settings)

        with patch.object(alerter._client, "post", new_callable=AsyncMock) as mock_post:
            mock_resp = AsyncMock()
            mock_resp.raise_for_status = MagicMock()
            mock_post.return_value = mock_resp

            await alerter.send("Test message", title="Test Title", level="success")

            mock_post.assert_called_once()
            payload = mock_post.call_args.kwargs["json"]
            assert "embeds" in payload
            assert payload["embeds"][0]["title"] == "Test Title"
            assert "Test message" in payload["embeds"][0]["description"]

        await alerter.close()

    asyncio.run(_run())


def test_fill_convenience():
    async def _run():
        settings = _make_settings(discord="https://discord.example/webhook")
        alerter = Alerter(settings)

        with patch.object(alerter._client, "post", new_callable=AsyncMock) as mock_post:
            mock_resp = AsyncMock()
            mock_resp.raise_for_status = MagicMock()
            mock_post.return_value = mock_resp

            await alerter.fill("position123", "Will Trump win?", "BUY", 0.65, 50.0)
            mock_post.assert_called_once()

        await alerter.close()

    asyncio.run(_run())


def test_kill_switch_alert():
    async def _run():
        settings = _make_settings(discord="https://discord.example/webhook")
        alerter = Alerter(settings)

        with patch.object(alerter._client, "post", new_callable=AsyncMock) as mock_post:
            mock_resp = AsyncMock()
            mock_resp.raise_for_status = MagicMock()
            mock_post.return_value = mock_resp

            await alerter.kill_switch("daily drawdown exceeded")
            mock_post.assert_called_once()
            payload = mock_post.call_args.kwargs["json"]
            assert payload["embeds"][0]["color"] == 0xED4245  # error red

        await alerter.close()

    asyncio.run(_run())


def test_send_swallows_http_errors():
    async def _run():
        settings = _make_settings(discord="https://discord.example/webhook")
        alerter = Alerter(settings)

        with patch.object(alerter._client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = Exception("Network error")
            await alerter.send("test")

        await alerter.close()

    asyncio.run(_run())
