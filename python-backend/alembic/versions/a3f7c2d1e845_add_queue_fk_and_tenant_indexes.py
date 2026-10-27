"""add queue generation_id FK and tenant_id indexes

Revision ID: a3f7c2d1e845
Revises: 1b12fb9e4ee9
Create Date: 2026-03-22 00:00:00.000000

Changes:
- Add FK from ai_agent_queue.generation_id → ai_agent_generations.id (CASCADE DELETE)
- Add index on ai_agent_generations.tenant_id (multi-tenant list queries)
- Add index on ai_agent_queue.tenant_id
"""
from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3f7c2d1e845"
down_revision: str = "1b12fb9e4ee9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── FK: ai_agent_queue.generation_id → ai_agent_generations.id ──────────
    op.create_foreign_key(
        "fk_ai_agent_queue_generation_id",
        "ai_agent_queue",
        "ai_agent_generations",
        ["generation_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # ── Indexes for tenant-scoped list queries ───────────────────────────────
    op.create_index(
        "ix_ai_agent_generations_tenant_id",
        "ai_agent_generations",
        ["tenant_id"],
    )
    op.create_index(
        "ix_ai_agent_queue_tenant_id",
        "ai_agent_queue",
        ["tenant_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_ai_agent_queue_tenant_id", table_name="ai_agent_queue")
    op.drop_index("ix_ai_agent_generations_tenant_id", table_name="ai_agent_generations")
    op.drop_constraint("fk_ai_agent_queue_generation_id", "ai_agent_queue", type_="foreignkey")
