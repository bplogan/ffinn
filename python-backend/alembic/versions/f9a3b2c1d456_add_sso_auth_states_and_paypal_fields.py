"""add sso_auth_states and paypal subscription fields

Revision ID: f9a3b2c1d456
Revises: e8f2c4a1b903
Create Date: 2026-06-28 12:00:00.000000
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f9a3b2c1d456"
down_revision: str = "e8f2c4a1b903"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sso_auth_states",
        sa.Column("state", sa.String(length=128), primary_key=True),
        sa.Column(
            "config_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sso_configurations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("code_verifier", sa.String(length=256), nullable=True),
        sa.Column("return_url", sa.String(length=1024), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_sso_auth_states_config_id", "sso_auth_states", ["config_id"])

    op.add_column(
        "subscription_plans",
        sa.Column("paypal_plan_id_monthly", sa.String(length=200), nullable=True),
    )
    op.add_column(
        "subscription_plans",
        sa.Column("paypal_plan_id_annually", sa.String(length=200), nullable=True),
    )
    op.add_column(
        "enhanced_tenant_subscriptions",
        sa.Column("payment_provider", sa.String(length=32), nullable=False, server_default="stripe"),
    )
    op.create_table(
        "paypal_processed_events",
        sa.Column("event_id", sa.String(length=255), primary_key=True),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("paypal_processed_events")
    op.drop_column("enhanced_tenant_subscriptions", "payment_provider")
    op.drop_column("subscription_plans", "paypal_plan_id_annually")
    op.drop_column("subscription_plans", "paypal_plan_id_monthly")
    op.drop_index("ix_sso_auth_states_config_id", table_name="sso_auth_states")
    op.drop_table("sso_auth_states")
