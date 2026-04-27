"""Abstract base for all executors (paper and live)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.signals.models import Signal


@dataclass
class Position:
    """An open or closed position resulting from an executed signal."""

    position_id: str
    signal_id: str
    strategy: str
    market_id: str
    asset_id: str
    side: str          # BUY or SELL
    entry_price: Decimal
    size_usd: Decimal
    size_tokens: Decimal  # number of outcome tokens bought/sold
    tp_price: Decimal     # take-profit price
    sl_price: Decimal     # stop-loss price
    max_holding_minutes: int
    opened_at: datetime
    closed_at: datetime | None = None
    exit_price: Decimal | None = None
    realized_pnl_usd: Decimal | None = None
    exit_reason: str = ""       # tp | sl | timeout | expiry | manual
    order_id: str | None = None  # CLOB order ID (live mode only)


class BaseExecutor(ABC):
    """Interface for paper and live executors."""

    @abstractmethod
    async def open_position(self, signal: Signal, capital_usd: float) -> Position:
        """Open a position based on the signal. Returns the opened Position."""
        ...

    @abstractmethod
    async def close_position(self, position: Position, reason: str) -> Position:
        """Close the position and record exit price and PnL."""
        ...

    @abstractmethod
    async def get_current_price(self, asset_id: str) -> Decimal | None:
        """Fetch the current market price for an asset."""
        ...
