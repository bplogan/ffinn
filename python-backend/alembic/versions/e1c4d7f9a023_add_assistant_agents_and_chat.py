"""Assistant agents (chat) alongside the build agent: agent kind, conversations, messages, attachments."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "e1c4d7f9a023"
down_revision: Union[str, None] = "d7a1b3c5e902"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("ai_agent_configurations", sa.Column("kind", sa.String(20), nullable=False, server_default="build"))
    op.add_column("ai_agent_configurations", sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("ai_agent_configurations", sa.Column("description", sa.String(500), nullable=True))
    op.add_column("ai_agent_configurations", sa.Column("system_prompt", sa.Text(), nullable=True))
    op.add_column("ai_agent_configurations", sa.Column("temperature", sa.Numeric(3, 2), nullable=True))
    op.add_column("ai_agent_configurations", sa.Column("avatar", sa.String(40), nullable=True))

    op.create_table(
        "ai_conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ai_agent_configurations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("title", sa.String(200), nullable=False, server_default="New chat"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "ai_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ai_conversations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("attachments", sa.JSON(), nullable=True),
        sa.Column("model", sa.String(200), nullable=True),
        sa.Column("tokens_used", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "ai_attachments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("storage_path", sa.String(500), nullable=False),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("ai_attachments")
    op.drop_table("ai_messages")
    op.drop_table("ai_conversations")
    for col in ("avatar", "temperature", "system_prompt", "description", "is_default", "kind"):
        op.drop_column("ai_agent_configurations", col)
