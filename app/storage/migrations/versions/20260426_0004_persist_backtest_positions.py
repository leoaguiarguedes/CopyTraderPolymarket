"""persist backtest positions and signal counters

Revision ID: 20260426_0004
Revises: 20260426_0003
Create Date: 2026-04-26
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260426_0004"
down_revision = "20260426_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "backtest_runs",
        sa.Column("signals_total", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "backtest_runs",
        sa.Column("signals_approved", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "backtest_runs",
        sa.Column("signals_rejected", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "backtest_runs",
        sa.Column("positions_json", sa.Text(), nullable=True),
    )
    op.alter_column("backtest_runs", "signals_total", server_default=None)
    op.alter_column("backtest_runs", "signals_approved", server_default=None)
    op.alter_column("backtest_runs", "signals_rejected", server_default=None)


def downgrade() -> None:
    op.drop_column("backtest_runs", "positions_json")
    op.drop_column("backtest_runs", "signals_rejected")
    op.drop_column("backtest_runs", "signals_approved")
    op.drop_column("backtest_runs", "signals_total")
