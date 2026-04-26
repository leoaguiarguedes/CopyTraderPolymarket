"""add backtest_runs table

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-26
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260426_0003"
down_revision = "20260426_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "backtest_runs",
        sa.Column("run_id", sa.String(36), primary_key=True),
        sa.Column("strategy", sa.String(50), nullable=False),
        sa.Column("start_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("wallets_json", sa.Text, nullable=False, server_default="[]"),
        sa.Column("params_json", sa.Text, nullable=False, server_default="{}"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("n_trades", sa.Integer, nullable=True),
        sa.Column("total_pnl_usd", sa.Numeric(20, 4), nullable=True),
        sa.Column("roi", sa.Numeric(20, 8), nullable=True),
        sa.Column("sharpe", sa.Numeric(20, 8), nullable=True),
        sa.Column("max_drawdown", sa.Numeric(10, 6), nullable=True),
        sa.Column("win_rate", sa.Numeric(10, 6), nullable=True),
        sa.Column("pct_timeout_exits", sa.Numeric(10, 6), nullable=True),
        sa.Column("metrics_json", sa.Text, nullable=True),
        sa.Column("error", sa.Text, nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_backtest_runs_strategy", "backtest_runs", ["strategy"])
    op.create_index("ix_backtest_runs_status", "backtest_runs", ["status"])
    op.create_index("ix_backtest_runs_created_at", "backtest_runs", ["created_at"])


def downgrade() -> None:
    op.drop_table("backtest_runs")
