"""ORM models — keep field names aligned with Polymarket API conventions."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.storage.db import Base
from app.utils.time import utcnow


class Wallet(Base):
    __tablename__ = "wallets"

    address: Mapped[str] = mapped_column(String(42), primary_key=True)
    proxy_address: Mapped[str | None] = mapped_column(String(42), index=True)
    label: Mapped[str | None] = mapped_column(String(100))
    is_tracked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    scores: Mapped[list[WalletScore]] = relationship(back_populates="wallet")


class WalletScore(Base):
    __tablename__ = "wallet_scores"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    wallet_address: Mapped[str] = mapped_column(
        String(42), ForeignKey("wallets.address"), nullable=False, index=True
    )
    window_days: Mapped[int] = mapped_column(nullable=False)  # 7 / 30 / 90
    n_trades: Mapped[int] = mapped_column(nullable=False)
    roi: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    sharpe: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    win_rate: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    max_drawdown: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    total_volume_usd: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    avg_holding_minutes: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    median_holding_minutes: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    pct_closed_under_24h: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    wallet: Mapped[Wallet] = relationship(back_populates="scores")

    __table_args__ = (
        Index("ix_wallet_scores_wallet_window", "wallet_address", "window_days"),
    )


class Market(Base):
    __tablename__ = "markets"

    condition_id: Mapped[str] = mapped_column(String(66), primary_key=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str | None] = mapped_column(String(255))
    category: Mapped[str | None] = mapped_column(String(100), index=True)
    end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    resolved_outcome: Mapped[str | None] = mapped_column(String(20))
    volume_24h_usd: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    liquidity_usd: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class Trade(Base):
    __tablename__ = "trades"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)  # tx_hash + log_index
    wallet_address: Mapped[str] = mapped_column(
        String(42), ForeignKey("wallets.address"), nullable=False, index=True
    )
    market_id: Mapped[str] = mapped_column(
        String(66), ForeignKey("markets.condition_id"), nullable=False, index=True
    )
    side: Mapped[str] = mapped_column(String(10), nullable=False)  # YES / NO / BUY / SELL
    outcome: Mapped[str] = mapped_column(String(20), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    size: Mapped[Decimal] = mapped_column(Numeric(30, 8), nullable=False)
    size_usd: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    fee_usd: Mapped[Decimal] = mapped_column(Numeric(20, 8), default=Decimal(0), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    tx_hash: Mapped[str] = mapped_column(String(66), nullable=False, index=True)

    __table_args__ = (
        Index("ix_trades_wallet_timestamp", "wallet_address", "timestamp"),
        Index("ix_trades_market_timestamp", "market_id", "timestamp"),
    )
