"""Create ume_memory_records, ume_memory_projects, ume_memory_sources, ume_memory_versions

Revision ID: 011
Revises: 010
Create Date: 2026-10-10

These tables are a *business projection*, not a copy of the engine: they hold no
vector and no engine payload, only the engine memory id plus the UME metadata a
console needs (status, current text, provenance, versions).

`engine_state` is the recovery handle for the fact that the business row and the
engine write cannot share a transaction. A record left in `pending` or `failed`
is a retryable write; one in `deleting` is a deletion that was interrupted.

Purely additive.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ume_memory_records",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.Uuid(),
            sa.ForeignKey("ume_workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("engine_memory_id", sa.String(255), nullable=False),
        sa.Column("memory_type", sa.String(64), nullable=False, server_default="semantic"),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("current_text", sa.Text(), nullable=False),
        sa.Column(
            "tags", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")
        ),
        sa.Column(
            "access_scope",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("engine_state", sa.String(32), nullable=False, server_default="pending"),
        # Redacted on the way in: never store a provider message that may echo
        # back a credential or a raw request body.
        sa.Column("engine_error", sa.Text(), nullable=True),
        sa.Column("created_by_type", sa.String(32), nullable=False, server_default="user"),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        # One business record per engine memory *within a workspace*. The same
        # engine id may legitimately exist in two workspaces, so the pair — not
        # the id alone — is the uniqueness boundary.
        sa.UniqueConstraint("workspace_id", "engine_memory_id", name="uq_ume_memory_records_workspace_engine"),
    )
    op.create_index("ix_ume_memory_records_workspace_status", "ume_memory_records", ["workspace_id", "status"])
    op.create_index("ix_ume_memory_records_engine_state", "ume_memory_records", ["engine_state"])
    op.create_index("ix_ume_memory_records_deleted_at", "ume_memory_records", ["deleted_at"])

    op.create_table(
        "ume_memory_projects",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "memory_record_id",
            sa.Uuid(),
            sa.ForeignKey("ume_memory_records.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("ume_projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("memory_record_id", "project_id", name="uq_ume_memory_projects_record_project"),
    )
    op.create_index("ix_ume_memory_projects_project_id", "ume_memory_projects", ["project_id"])

    op.create_table(
        "ume_memory_sources",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.Uuid(),
            sa.ForeignKey("ume_workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "memory_record_id",
            sa.Uuid(),
            sa.ForeignKey("ume_memory_records.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # SET NULL: a conversation or message can be deleted while the memory it
        # produced stays. Provenance must survive as a tombstone rather than
        # pulling the memory down with it.
        sa.Column(
            "conversation_id",
            sa.Uuid(),
            sa.ForeignKey("ume_conversations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("message_id", sa.Uuid(), nullable=True),
        sa.Column("source_type", sa.String(64), nullable=False),
        sa.Column("extraction_method", sa.String(64), nullable=False),
        # Never copied from a message whose sensitivity is `restricted`.
        sa.Column("evidence_excerpt", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_ume_memory_sources_record_id", "ume_memory_sources", ["memory_record_id"])
    op.create_index("ix_ume_memory_sources_message_id", "ume_memory_sources", ["message_id"])
    op.create_index("ix_ume_memory_sources_conversation_id", "ume_memory_sources", ["conversation_id"])

    op.create_table(
        "ume_memory_versions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "memory_record_id",
            sa.Uuid(),
            sa.ForeignKey("ume_memory_records.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column("change_type", sa.String(32), nullable=False),
        sa.Column("change_reason", sa.Text(), nullable=True),
        sa.Column("actor_type", sa.String(32), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("memory_record_id", "version_no", name="uq_ume_memory_versions_record_version"),
    )
    op.create_index("ix_ume_memory_versions_record_created", "ume_memory_versions", ["memory_record_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_ume_memory_versions_record_created", table_name="ume_memory_versions")
    op.drop_table("ume_memory_versions")

    op.drop_index("ix_ume_memory_sources_conversation_id", table_name="ume_memory_sources")
    op.drop_index("ix_ume_memory_sources_message_id", table_name="ume_memory_sources")
    op.drop_index("ix_ume_memory_sources_record_id", table_name="ume_memory_sources")
    op.drop_table("ume_memory_sources")

    op.drop_index("ix_ume_memory_projects_project_id", table_name="ume_memory_projects")
    op.drop_table("ume_memory_projects")

    op.drop_index("ix_ume_memory_records_deleted_at", table_name="ume_memory_records")
    op.drop_index("ix_ume_memory_records_engine_state", table_name="ume_memory_records")
    op.drop_index("ix_ume_memory_records_workspace_status", table_name="ume_memory_records")
    op.drop_table("ume_memory_records")
