"""add is_system to identity_roles

Revision ID: b5e8d3f2a190
Revises: a3f7c2d1e845
Create Date: 2026-03-22 00:00:00.000000

Changes:
- Add is_system boolean column to identity_roles (default false)
  Admin and User roles are system roles that cannot be deleted.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b5e8d3f2a190"
down_revision: str = "a3f7c2d1e845"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "identity_roles",
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default="false"),
    )
    # Mark existing host-level Admin and User roles as system roles
    op.execute(
        "UPDATE identity_roles SET is_system = true "
        "WHERE tenant_id IS NULL AND normalized_name IN ('ADMIN', 'USER')"
    )


def downgrade() -> None:
    op.drop_column("identity_roles", "is_system")
