"""add edition pricing and features

Revision ID: c1e9f5a3b281
Revises: b5e8d3f2a190
Create Date: 2026-03-22 00:00:00.000000

Changes:
- Add pricing columns to editions table (price_monthly, price_annually, currency, sort_order, is_public)
- Create edition_features table for per-edition feature/capability definitions
- Add registration.paywall_enabled setting concept (stored in app_settings — no DDL needed)
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c1e9f5a3b281"
down_revision: str = "b5e8d3f2a190"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Extend editions table ─────────────────────────────────────────────────
    op.add_column("editions", sa.Column("price_monthly",  sa.Numeric(10, 2), nullable=False, server_default="0"))
    op.add_column("editions", sa.Column("price_annually", sa.Numeric(10, 2), nullable=False, server_default="0"))
    op.add_column("editions", sa.Column("currency",    sa.String(10),  nullable=False, server_default="USD"))
    op.add_column("editions", sa.Column("sort_order",  sa.Integer(),   nullable=False, server_default="0"))
    op.add_column("editions", sa.Column("is_public",   sa.Boolean(),   nullable=False, server_default="true"))

    # ── Create edition_features table ─────────────────────────────────────────
    op.create_table(
        "edition_features",
        sa.Column("id",            sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("edition_id",    sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("editions.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("feature_name",  sa.String(256), nullable=False),
        sa.Column("display_name",  sa.String(256), nullable=False),
        sa.Column("feature_value", sa.String(500), nullable=True),
        sa.Column("is_included",   sa.Boolean(),   nullable=False, server_default="true"),
        sa.Column("sort_order",    sa.Integer(),   nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_table("edition_features")
    op.drop_column("editions", "is_public")
    op.drop_column("editions", "sort_order")
    op.drop_column("editions", "currency")
    op.drop_column("editions", "price_annually")
    op.drop_column("editions", "price_monthly")
