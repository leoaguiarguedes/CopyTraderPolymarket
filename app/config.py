"""Application configuration loaded from environment variables and .env file."""
from __future__ import annotations

from enum import Enum
from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppEnv(str, Enum):
    development = "development"
    staging = "staging"
    production = "production"
    test = "test"


class ExecutionMode(str, Enum):
    paper = "paper"
    live = "live"


class LogFormat(str, Enum):
    json = "json"
    console = "console"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ───────────────────────────────────────────────
    app_env: AppEnv = AppEnv.development
    log_level: str = "INFO"
    log_format: LogFormat = LogFormat.json

    # ── Database ──────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://copytrader:changeme@postgres:5432/copytrader"

    # ── Redis ─────────────────────────────────────────────────────
    redis_url: str = "redis://redis:6379/0"

    # ── Polymarket ────────────────────────────────────────────────
    polymarket_gamma_url: str = "https://gamma-api.polymarket.com"
    polymarket_clob_url: str = "https://clob.polymarket.com"
    polymarket_data_url: str = "https://data-api.polymarket.com"
    polymarket_ws_url: str = "wss://ws-subscriptions-clob.polymarket.com/ws"

    # ── Subgraph ──────────────────────────────────────────────────
    subgraph_url: str = (
        "https://api.goldsky.com/api/public/"
        "project_cl6mb8i9h0003e201j6li0diw/subgraphs/polymarket-orderbook/0.0.7/gn"
    )
    subgraph_api_key: SecretStr | None = None

    # ── On-chain (Fase 4) ─────────────────────────────────────────
    polygon_rpc_url: str = "https://polygon-rpc.com"
    wallet_private_key: SecretStr | None = None
    wallet_address: str | None = None

    # ── Trading ───────────────────────────────────────────────────
    execution_mode: ExecutionMode = ExecutionMode.paper
    initial_capital_usd: float = Field(default=1000.0, gt=0)
    max_pct_per_trade: float = Field(default=0.02, gt=0, le=0.5)
    max_drawdown_daily: float = Field(default=0.05, gt=0, le=1.0)
    max_open_positions: int = Field(default=10, gt=0)

    # ── Auth (single-user) ────────────────────────────────────────
    admin_user: str = "admin"
    admin_pass: SecretStr = SecretStr("changeme")

    # ── Alerting (optional) ───────────────────────────────────────
    discord_webhook_url: str | None = None
    telegram_bot_token: SecretStr | None = None
    telegram_chat_id: str | None = None

    @property
    def is_production(self) -> bool:
        return self.app_env == AppEnv.production

    @property
    def is_paper_trading(self) -> bool:
        return self.execution_mode == ExecutionMode.paper


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Singleton accessor — cached so .env is parsed once."""
    return Settings()
