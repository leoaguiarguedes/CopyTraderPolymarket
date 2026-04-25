"""FastAPI application entry point."""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.api.routes import health, trades, wallets
from app.config import get_settings
from app.utils.logger import configure_logging, get_logger
from app.utils.metrics import registry


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    log = get_logger(__name__)
    settings = get_settings()
    log.info("api.startup", env=settings.app_env.value, mode=settings.execution_mode.value)
    yield
    log.info("api.shutdown")


app = FastAPI(
    title="CopyTrader Polymarket",
    version="0.1.0",
    description="Automated copytrading bot for Polymarket — short-horizon scalping",
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(wallets.router)
app.include_router(trades.router)


@app.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    return Response(generate_latest(registry), media_type=CONTENT_TYPE_LATEST)
