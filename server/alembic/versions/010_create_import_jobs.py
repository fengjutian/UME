"""Create ume_import_jobs and ume_idempotency_keys

Revision ID: 010
Revises: 009
Create Date: 2026-10-10

Numbering note: section 6 of the implementation doc schedules `012_create_import_jobs`
and reserves 010 for the memory-metadata tables. Both the audit table (008) and
the import jobs have moved earlier because P1 and Task 1.2 need them; the memory
metadata tables therefore land at 011 and the edges at 012. Renumbering is a
mechanical follow-up if the documented sequence is preferred.

Purely additive.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ume_import_jobs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.Uuid(),
            sa.ForeignKey("ume_workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("ume_projects.id", ondelete="SET NULL"), nullable=True),
        sa.Column("connector_id", sa.Uuid(), nullable=True),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column(
            "input_summary",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "result_summary",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "error_summary",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("workspace_id", "idempotency_key", name="uq_ume_import_jobs_workspace_idem"),
    )
    op.create_index("ix_ume_import_jobs_workspace_status", "ume_import_jobs", ["workspace_id", "status"])

    op.create_table(
        "ume_idempotency_keys",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.Uuid(),
            sa.ForeignKey("ume_workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("actor_type", sa.String(32), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column(
            "response_summary",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "workspace_id",
            "actor_type",
            "actor_id",
            "idempotency_key",
            name="uq_ume_idempotency_scope_key",
        ),
    )
    op.create_index("ix_ume_idempotency_keys_expires_at", "ume_idempotency_keys", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_ume_idempotency_keys_expires_at", table_name="ume_idempotency_keys")
    op.drop_table("ume_idempotency_keys")

    op.drop_index("ix_ume_import_jobs_workspace_status", table_name="ume_import_jobs")
    op.drop_table("ume_import_jobs")