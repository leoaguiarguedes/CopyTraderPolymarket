"""FastAPI application entry point."""
from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from typing import AsyncIterator

import redis.asyncio as aioredis
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.api.routes import health, pnl, positions, signals, trades, wallets
from app.config import get_settings
from app.risk.kill_switch import KillSwitch
from app.utils.logger import configure_logging, get_logger
from app.utils.metrics import registry

log = get_logger(__name__)

# Connected WebSocket clients (for live push)
_ws_clients: list[WebSocket] = []


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    settings = get_settings()
    log.info("api.startup", env=settings.app_env.value, mode=settings.execution_mode.value)

    # Start background task to forward Redis position events to WS clients
    task = asyncio.create_task(_ws_broadcast_loop(settings.redis_url))
    yield

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    log.info("api.shutdown")


app = FastAPI(
    title="CopyTrader Polymarket",
    version="0.2.0",
    description="Automated copytrading bot for Polymarket — short-horizon scalping",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(wallets.router)
app.include_router(trades.router)
app.include_router(pnl.router)
app.include_router(signals.router)
app.include_router(positions.router)


@app.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    return Response(generate_latest(registry), media_type=CONTENT_TYPE_LATEST)


@app.post("/kill-switch", tags=["risk"])
async def toggle_kill_switch(active: bool):
    """Activate (active=true) or deactivate the global kill switch."""
    settings = get_settings()
    r = aioredis.from_url(settings.redis_url, decode_responses=False)
    ks = KillSwitch(r)
    if active:
        await ks.activate("manual_api")
    else:
        await ks.deactivate()
    await r.aclose()
    return {"kill_switch": active}


@app.get("/kill-switch", tags=["risk"])
async def get_kill_switch():
    settings = get_settings()
    r = aioredis.from_url(settings.redis_url, decode_responses=False)
    ks = KillSwitch(r)
    active = await ks.is_active()
    await r.aclose()
    return {"kill_switch": active}


# ── WebSocket live feed ───────────────────────────────────────────────────────

@app.websocket("/ws/live")
async def websocket_live(ws: WebSocket):
    """Push-based WebSocket that forwards signals + position events to the frontend."""
    await ws.accept()
    _ws_clients.append(ws)
    log.info("ws.connected", total=len(_ws_clients))
    try:
        while True:
            # Keep connection alive; actual data is pushed by _ws_broadcast_loop
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        _ws_clients.remove(ws)
        log.info("ws.disconnected", total=len(_ws_clients))


async def _ws_broadcast_loop(redis_url: str) -> None:
    """Read from Redis `positions` stream and broadcast to all WS clients."""
    r = aioredis.from_url(redis_url, decode_responses=False)
    last_id = "$"
    try:
        while True:
            try:
                messages = await r.xread(
                    streams={"positions": last_id},
                    count=20,
                    block=500,
                )
                if not messages:
                    continue
                for _stream, entries in messages:
                    for msg_id, fields in entries:
                        last_id = msg_id
                        payload = fields.get(b"data", b"{}")
                        await _broadcast(payload.decode())
            except Exception as exc:
                log.warning("ws_broadcast.error", error=str(exc)[:60])
                await asyncio.sleep(1)
    finally:
        await r.aclose()


async def _broadcast(payload: str) -> None:
    dead = []
    for ws in list(_ws_clients):
        try:
            await ws.send_text(payload)
        except Exception:
            dead.append(ws)
    for ws in dead:
        try:
            _ws_clients.remove(ws)
        except ValueError:
            pass
