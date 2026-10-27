"""Add Azure deployment name to agent configurations."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a7c4e2b9d801"
down_revision: Union[str, None] = "f9a3b2c1d456"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ai_agent_configurations",
        sa.Column("azure_deployment_name", sa.String(length=200), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ai_agent_configurations", "azure_deployment_name")
