"""Create ume_workspaces, ume_workspace_members and ume_projects

Revision ID: 007
Revises: 006
Create Date: 2026-10-10

Purely additive: no existing table is touched, so downgrade simply drops the
three new tables in reverse dependency order.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ume_workspaces",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        # RESTRICT, not CASCADE: deleting a user must never silently delete the
        # workspaces (and their memories) that user owns. V1.0 has no user
        # deletion endpoint, so this constraint cannot deadlock normal flows.
        sa.Column("owner_user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column(
            "default_memory_policy",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_ume_workspaces_owner_user_id", "ume_workspaces", ["owner_user_id"])

    op.create_table(
        "ume_workspace_members",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.Uuid(),
            sa.ForeignKey("ume_workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("role", sa.String(32), nullable=False, server_default="viewer"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("workspace_id", "user_id", name="uq_ume_workspace_members_workspace_user"),
    )
    op.create_index("ix_ume_workspace_members_user_id", "ume_workspace_members", ["user_id"])

    op.create_table(
        "ume_projects",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.Uuid(),
            sa.ForeignKey("ume_workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "tags", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")
        ),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_ume_projects_workspace_id", "ume_projects", ["workspace_id"])
    op.create_index("ix_ume_projects_workspace_status", "ume_projects", ["workspace_id", "status"])
    op.create_index("ix_ume_projects_last_activity_at", "ume_projects", ["last_activity_at"])


def downgrade() -> None:
    op.drop_index("ix_ume_projects_last_activity_at", table_name="ume_projects")
    op.drop_index("ix_ume_projects_workspace_status", table_name="ume_projects")
    op.drop_index("ix_ume_projects_workspace_id", table_name="ume_projects")
    op.drop_table("ume_projects")

    op.drop_index("ix_ume_workspace_members_user_id", table_name="ume_workspace_members")
    op.drop_table("ume_workspace_members")

    op.drop_index("ix_ume_workspaces_owner_user_id", table_name="ume_workspaces")
    op.drop_table("ume_workspaces")
