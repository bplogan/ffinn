"""add stripe_processed_events idempotency table

Revision ID: d2f0a4c6b377
Revises: c1e9f5a3b281
Create Date: 2026-05-11 00:00:00.000000
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "d2f0a4c6b377"
down_revision: str = "c1e9f5a3b281"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stripe_processed_events",
        sa.Column("event_id", sa.String(length=255), primary_key=True),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column(
            "processed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    # NOTE: dropping this table re-enables duplicate webhook processing.
    op.drop_table("stripe_processed_events")
