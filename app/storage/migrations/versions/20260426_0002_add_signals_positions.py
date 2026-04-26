"""Add signals and positions tables.

Revision ID: 20260426_0002
Revises: 20260425_0001
Create Date: 2026-04-26
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260426_0002"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "signals",
        sa.Column("signal_id", sa.String(36), primary_key=True),
        sa.Column("strategy", sa.String(50), nullable=False),
        sa.Column("market_id", sa.String(66), nullable=False),
        sa.Column("asset_id", sa.String(80), nullable=False),
        sa.Column("side", sa.String(10), nullable=False),
        sa.Column("confidence", sa.Numeric(6, 4), nullable=False),
        sa.Column("entry_price", sa.Numeric(20, 8), nullable=False),
        sa.Column("size_pct", sa.Numeric(10, 6), nullable=False),
        sa.Column("tp_pct", sa.Numeric(10, 6), nullable=False),
        sa.Column("sl_pct", sa.Numeric(10, 6), nullable=False),
        sa.Column("max_holding_minutes", sa.Integer, nullable=False),
        sa.Column("source_wallet", sa.String(42), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("reject_reason", sa.String(200), nullable=False, server_default=""),
        sa.Column("reason", sa.Text, nullable=False, server_default=""),
        sa.Column("market_question", sa.Text, nullable=False, server_default=""),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_signals_strategy", "signals", ["strategy"])
    op.create_index("ix_signals_market_id", "signals", ["market_id"])
    op.create_index("ix_signals_source_wallet", "signals", ["source_wallet"])
    op.create_index("ix_signals_status", "signals", ["status"])
    op.create_index("ix_signals_created_at", "signals", ["created_at"])
    op.create_index("ix_signals_strategy_created", "signals", ["strategy", "created_at"])

    op.create_table(
        "positions",
        sa.Column("position_id", sa.String(36), primary_key=True),
        sa.Column(
            "signal_id",
            sa.String(36),
            sa.ForeignKey("signals.signal_id"),
            nullable=False,
        ),
        sa.Column("strategy", sa.String(50), nullable=False),
        sa.Column("market_id", sa.String(66), nullable=False),
        sa.Column("asset_id", sa.String(80), nullable=False),
        sa.Column("side", sa.String(10), nullable=False),
        sa.Column("entry_price", sa.Numeric(20, 8), nullable=False),
        sa.Column("size_usd", sa.Numeric(20, 2), nullable=False),
        sa.Column("size_tokens", sa.Numeric(30, 8), nullable=False),
        sa.Column("tp_price", sa.Numeric(20, 8), nullable=False),
        sa.Column("sl_price", sa.Numeric(20, 8), nullable=False),
        sa.Column("max_holding_minutes", sa.Integer, nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.Column("exit_price", sa.Numeric(20, 8)),
        sa.Column("realized_pnl_usd", sa.Numeric(20, 6)),
        sa.Column("exit_reason", sa.String(50), nullable=False, server_default=""),
        sa.Column("execution_mode", sa.String(10), nullable=False, server_default="paper"),
    )
    op.create_index("ix_positions_signal_id", "positions", ["signal_id"])
    op.create_index("ix_positions_strategy", "positions", ["strategy"])
    op.create_index("ix_positions_market_id", "positions", ["market_id"])
    op.create_index("ix_positions_opened_at", "positions", ["opened_at"])
    op.create_index("ix_positions_closed_at", "positions", ["closed_at"])
    op.create_index("ix_positions_market_open", "positions", ["market_id", "closed_at"])


def downgrade() -> None:
    op.drop_table("positions")
    op.drop_table("signals")
