"""add notification_configurations for tenant SMS and push settings

Revision ID: e8f2c4a1b903
Revises: d2f0a4c6b377
Create Date: 2026-06-28 00:00:00.000000
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e8f2c4a1b903"
down_revision: str = "d2f0a4c6b377"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notification_configurations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True),
        sa.Column("sms_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("twilio_account_sid", sa.String(length=64), nullable=True),
        sa.Column("twilio_auth_token_encrypted", sa.Text(), nullable=True),
        sa.Column("twilio_from_number", sa.String(length=32), nullable=True),
        sa.Column("push_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("push_provider", sa.String(length=32), nullable=True),
        sa.Column("firebase_project_id", sa.String(length=128), nullable=True),
        sa.Column("firebase_credentials_encrypted", sa.Text(), nullable=True),
        sa.Column("twilio_notify_service_sid", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("tenant_id", name="uq_notification_configurations_tenant_id"),
    )
    op.create_index(
        "ix_notification_configurations_tenant_id",
        "notification_configurations",
        ["tenant_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_notification_configurations_tenant_id", table_name="notification_configurations")
    op.drop_table("notification_configurations")
