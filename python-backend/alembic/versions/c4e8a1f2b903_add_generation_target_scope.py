"""Add target_scope to ai_agent_generations."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c4e8a1f2b903"
down_revision: Union[str, None] = "b8d5f3a2c912"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ai_agent_generations",
        sa.Column("target_scope", sa.String(length=20), nullable=False, server_default="tenant"),
    )


def downgrade() -> None:
    op.drop_column("ai_agent_generations", "target_scope")
