"""Create ume_conversations and ume_messages

Revision ID: 009
Revises: 008
Create Date: 2026-10-10

Purely additive. Deduplication is enforced by *partial* unique indexes: a
conversation or message without an external id must not collide with every other
row that also lacks one, so the constraint only applies where the connector
actually supplied an identifier.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ume_conversations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.Uuid(),
            sa.ForeignKey("ume_workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # SET NULL: archiving a project must not delete the conversation history
        # that was filed under it.
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("ume_projects.id", ondelete="SET NULL"), nullable=True),
        sa.Column("connector_id", sa.Uuid(), nullable=True),
        sa.Column("external_conversation_id", sa.String(255), nullable=True),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("source_type", sa.String(64), nullable=False, server_default="generic"),
        sa.Column("retention_policy", sa.String(64), nullable=False, server_default="retain"),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_ume_conversations_workspace_id", "ume_conversations", ["workspace_id"])
    op.create_index("ix_ume_conversations_project_id", "ume_conversations", ["project_id"])
    op.create_index(
        "ix_ume_conversations_workspace_last_message",
        "ume_conversations",
        ["workspace_id", "last_message_at"],
    )
    # A connector re-sending the same external conversation must resolve to the
    # same row. Rows without an external id are exempt: NULL would otherwise
    # make every such row "distinct" only under a plain UNIQUE, which is why
    # this is a partial unique index instead of a table constraint.
    op.create_index(
        "uq_ume_conversations_external",
        "ume_conversations",
        ["workspace_id", "connector_id", "external_conversation_id"],
        unique=True,
        postgresql_where=sa.text("external_conversation_id IS NOT NULL"),
    )

    op.create_table(
        "ume_messages",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.Uuid(),
            sa.ForeignKey("ume_workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "conversation_id",
            sa.Uuid(),
            sa.ForeignKey("ume_conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("external_message_id", sa.String(255), nullable=True),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("content_text", sa.Text(), nullable=True),
        sa.Column("content_ref", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column(
            "extra_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("sensitivity", sa.String(32), nullable=False, server_default="normal"),
        sa.Column("message_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("import_job_id", sa.Uuid(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        # A row with neither inline text nor an external pointer is unreadable.
        sa.CheckConstraint(
            "content_text IS NOT NULL OR content_ref IS NOT NULL",
            name="ck_ume_messages_has_content",
        ),
    )
    op.create_index("ix_ume_messages_workspace_id", "ume_messages", ["workspace_id"])
    op.create_index(
        "ix_ume_messages_conversation_browse", "ume_messages", ["conversation_id", "message_at", "id"]
    )
    op.create_index(
        "ix_ume_messages_conversation_dedup", "ume_messages", ["conversation_id", "content_hash", "message_at"]
    )
    op.create_index("ix_ume_messages_import_job_id", "ume_messages", ["import_job_id"])
    op.create_index(
        "uq_ume_messages_external",
        "ume_messages",
        ["conversation_id", "external_message_id"],
        unique=True,
        postgresql_where=sa.text("external_message_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_ume_messages_external", table_name="ume_messages")
    op.drop_index("ix_ume_messages_import_job_id", table_name="ume_messages")
    op.drop_index("ix_ume_messages_conversation_dedup", table_name="ume_messages")
    op.drop_index("ix_ume_messages_conversation_browse", table_name="ume_messages")
    op.drop_index("ix_ume_messages_workspace_id", table_name="ume_messages")
    op.drop_table("ume_messages")

    op.drop_index("uq_ume_conversations_external", table_name="ume_conversations")
    op.drop_index("ix_ume_conversations_workspace_last_message", table_name="ume_conversations")
    op.drop_index("ix_ume_conversations_project_id", table_name="ume_conversations")
    op.drop_index("ix_ume_conversations_workspace_id", table_name="ume_conversations")
    op.drop_table("ume_conversations")