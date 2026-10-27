"""Add projects and project_files tables."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql


revision: str = "b8d5f3a2c912"
down_revision: Union[str, None] = "a7c4e2b9d801"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

project_status = postgresql.ENUM(
    "draft", "active", "completed", "archived", name="project_status", create_type=False
)


def upgrade() -> None:
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE project_status AS ENUM ('draft', 'active', 'completed', 'archived');
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
        """
    )

    bind = op.get_bind()
    tables = inspect(bind).get_table_names()

    if "projects" not in tables:
        op.create_table(
            "projects",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
            sa.Column("title", sa.String(length=256), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("status", project_status, nullable=False, server_default="draft"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )

    if "project_files" not in tables:
        op.create_table(
            "project_files",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("file_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("file_uploads.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("label", sa.String(length=128), nullable=True),
        )


def downgrade() -> None:
    op.drop_table("project_files")
    op.drop_table("projects")
    op.execute("DROP TYPE IF EXISTS project_status")
