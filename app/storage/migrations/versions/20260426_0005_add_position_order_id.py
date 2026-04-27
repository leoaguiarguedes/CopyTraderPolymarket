"""add order_id to positions (Fase 4 live execution)

Revision ID: 20260426_0005
Revises: 20260426_0004
Create Date: 2026-04-26
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260426_0005"
down_revision = "20260426_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "positions",
        sa.Column("order_id", sa.String(80), nullable=True),
    )
    op.create_index("ix_positions_order_id", "positions", ["order_id"])


def downgrade() -> None:
    op.drop_index("ix_positions_order_id", table_name="positions")
    op.drop_column("positions", "order_id")
