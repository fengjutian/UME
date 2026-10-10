"""Create ume_audit_events

Revision ID: 008
Revises: 007
Create Date: 2026-10-10

Numbering note: section 6 of the implementation doc schedules connectors for
008 and puts audit together with the memory edges in 011. Task 1.2 requires a
working audit trail, so audit takes 008 here and the later migrations shift by
one. Renumbering is mechanical and can be done in one commit if the doc's
sequence is preferred.

Purely additive: no existing table is touched.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ume_audit_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        # SET NULL, not CASCADE: an audit row outlives the workspace it refers
        # to, otherwise deleting a workspace would erase the record that it was
        # deleted.
        sa.Column(
            "workspace_id",
            sa.Uuid(),
            sa.ForeignKey("ume_workspaces.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("actor_type", sa.String(32), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("resource_type", sa.String(64), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=True),
        sa.Column("result", sa.String(32), nullable=False),
        sa.Column("request_id", sa.String(64), nullable=False),
        sa.Column(
            "details", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_ume_audit_events_workspace_created", "ume_audit_events", ["workspace_id", "created_at"])
    op.create_index("ix_ume_audit_events_resource", "ume_audit_events", ["resource_type", "resource_id"])
    op.create_index("ix_ume_audit_events_actor", "ume_audit_events", ["actor_type", "actor_id"])


def downgrade() -> None:
    op.drop_index("ix_ume_audit_events_actor", table_name="ume_audit_events")
    op.drop_index("ix_ume_audit_events_resource", table_name="ume_audit_events")
    op.drop_index("ix_ume_audit_events_workspace_created", table_name="ume_audit_events")
    op.drop_table("ume_audit_events")
