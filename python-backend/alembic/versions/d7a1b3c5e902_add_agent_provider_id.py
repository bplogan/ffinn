"""Link agent configurations to a saved AI provider (single source of truth for keys)."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "d7a1b3c5e902"
down_revision: Union[str, None] = "c4e8a1f2b903"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ai_agent_configurations",
        sa.Column("provider_id", postgresql.UUID(as_uuid=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ai_agent_configurations", "provider_id")
