"""initial schema — wallets, wallet_scores, markets, trades

Revision ID: 0001_initial
Revises:
Create Date: 2026-04-25

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "wallets",
        sa.Column("address", sa.String(length=42), primary_key=True),
        sa.Column("proxy_address", sa.String(length=42), nullable=True),
        sa.Column("label", sa.String(length=100), nullable=True),
        sa.Column("is_tracked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_wallets_proxy_address", "wallets", ["proxy_address"])
    op.create_index("ix_wallets_is_tracked", "wallets", ["is_tracked"])

    op.create_table(
        "markets",
        sa.Column("condition_id", sa.String(length=66), primary_key=True),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=True),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column("end_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_resolved", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("resolved_outcome", sa.String(length=20), nullable=True),
        sa.Column("volume_24h_usd", sa.Numeric(20, 2), nullable=True),
        sa.Column("liquidity_usd", sa.Numeric(20, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_markets_category", "markets", ["category"])
    op.create_index("ix_markets_end_date", "markets", ["end_date"])
    op.create_index("ix_markets_is_active", "markets", ["is_active"])

    op.create_table(
        "wallet_scores",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "wallet_address",
            sa.String(length=42),
            sa.ForeignKey("wallets.address"),
            nullable=False,
        ),
        sa.Column("window_days", sa.Integer(), nullable=False),
        sa.Column("n_trades", sa.Integer(), nullable=False),
        sa.Column("roi", sa.Numeric(20, 8), nullable=False),
        sa.Column("sharpe", sa.Numeric(20, 8), nullable=False),
        sa.Column("win_rate", sa.Numeric(10, 6), nullable=False),
        sa.Column("max_drawdown", sa.Numeric(20, 8), nullable=False),
        sa.Column("total_volume_usd", sa.Numeric(20, 2), nullable=False),
        sa.Column("avg_holding_minutes", sa.Numeric(20, 2), nullable=False),
        sa.Column("median_holding_minutes", sa.Numeric(20, 2), nullable=False),
        sa.Column("pct_closed_under_24h", sa.Numeric(10, 6), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_wallet_scores_wallet_address", "wallet_scores", ["wallet_address"])
    op.create_index(
        "ix_wallet_scores_wallet_window",
        "wallet_scores",
        ["wallet_address", "window_days"],
    )

    op.create_table(
        "trades",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column(
            "wallet_address",
            sa.String(length=42),
            sa.ForeignKey("wallets.address"),
            nullable=False,
        ),
        sa.Column(
            "market_id",
            sa.String(length=66),
            sa.ForeignKey("markets.condition_id"),
            nullable=False,
        ),
        sa.Column("side", sa.String(length=10), nullable=False),
        sa.Column("outcome", sa.String(length=20), nullable=False),
        sa.Column("price", sa.Numeric(20, 8), nullable=False),
        sa.Column("size", sa.Numeric(30, 8), nullable=False),
        sa.Column("size_usd", sa.Numeric(20, 2), nullable=False),
        sa.Column("fee_usd", sa.Numeric(20, 8), nullable=False, server_default="0"),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tx_hash", sa.String(length=66), nullable=False),
    )
    op.create_index("ix_trades_wallet_address", "trades", ["wallet_address"])
    op.create_index("ix_trades_market_id", "trades", ["market_id"])
    op.create_index("ix_trades_timestamp", "trades", ["timestamp"])
    op.create_index("ix_trades_tx_hash", "trades", ["tx_hash"])
    op.create_index("ix_trades_wallet_timestamp", "trades", ["wallet_address", "timestamp"])
    op.create_index("ix_trades_market_timestamp", "trades", ["market_id", "timestamp"])


def downgrade() -> None:
    op.drop_table("trades")
    op.drop_table("wallet_scores")
    op.drop_table("markets")
    op.drop_table("wallets")
