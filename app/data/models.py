"""Pure dataclasses for Polymarket domain objects.

These are wire-layer types — no ORM, no DB deps. They flow through Redis Streams
and get mapped to ORM models only at persistence time.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum


class Side(str, Enum):
    YES = "YES"
    NO = "NO"


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


@dataclass(frozen=True)
class TradeEvent:
    """A single matched trade on the Polymarket CLOB."""

    id: str                         # tx_hash + "-" + log_index (or taker_order_id)
    market_id: str                  # condition_id (hex)
    asset_id: str                   # token_id / outcome token address
    outcome: str                    # "YES" or "NO"
    side: OrderSide                 # BUY or SELL from taker perspective
    price: Decimal                  # 0–1 (cents format in Polymarket)
    size: Decimal                   # outcome token qty
    size_usd: Decimal               # price * size approximation
    fee_usd: Decimal
    maker_address: str
    taker_address: str
    timestamp: datetime
    tx_hash: str

    @property
    def outcome_side(self) -> Side:
        """Which outcome (YES/NO) the taker is buying/selling."""
        if self.outcome.upper() == "YES":
            return Side.YES
        return Side.NO


@dataclass(frozen=True)
class Market:
    """Polymarket market (condition)."""

    condition_id: str
    question: str
    slug: str | None = None
    category: str | None = None
    end_date: datetime | None = None
    is_active: bool = True
    is_resolved: bool = False
    resolved_outcome: str | None = None
    volume_24h_usd: Decimal | None = None
    liquidity_usd: Decimal | None = None
    # token ids: index 0 = YES, 1 = NO
    token_ids: list[str] = field(default_factory=list)

    def time_to_resolution_minutes(self, now: datetime) -> float | None:
        if self.end_date is None:
            return None
        delta = self.end_date - now
        return max(0.0, delta.total_seconds() / 60)


@dataclass
class OrderBookLevel:
    price: Decimal
    size: Decimal


@dataclass
class OrderBook:
    market_id: str
    asset_id: str
    bids: list[OrderBookLevel] = field(default_factory=list)
    asks: list[OrderBookLevel] = field(default_factory=list)
    timestamp: datetime | None = None

    def best_ask(self) -> Decimal | None:
        return min((a.price for a in self.asks), default=None)

    def best_bid(self) -> Decimal | None:
        return max((b.price for b in self.bids), default=None)

    def depth_usd(self, side: str = "ask", levels: int = 5) -> Decimal:
        """Approximate USD depth for top N levels."""
        book = self.asks if side == "ask" else self.bids
        top = sorted(book, key=lambda x: x.price)[: levels]
        return sum(lvl.price * lvl.size for lvl in top)


@dataclass(frozen=True)
class WalletTrade:
    """A historical trade for a wallet — used for scoring."""

    trade_id: str
    wallet_address: str
    market_id: str
    outcome: str
    side: OrderSide
    price: Decimal
    size_usd: Decimal          # total USDC volume (buys + sells)
    cost_usd: Decimal          # capital invested (buys only = usdc_in)
    opened_at: datetime
    closed_at: datetime | None  # None = still open
    realized_pnl_usd: Decimal | None = None  # set when closed

    @property
    def holding_minutes(self) -> float | None:
        if self.closed_at is None:
            return None
        return (self.closed_at - self.opened_at).total_seconds() / 60
