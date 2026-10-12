"""Create ume_memory_edges

Revision ID: 012
Revises: 011
Create Date: 2026-10-10

Section 6 also put `ume_audit_events` here; it already landed at 008 because
Task 1.2 needed a working audit trail before this point.

Purely additive.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ume_memory_edges",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.Uuid(),
            sa.ForeignKey("ume_workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_memory_id",
            sa.Uuid(),
            sa.ForeignKey("ume_memory_records.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "target_memory_id",
            sa.Uuid(),
            sa.ForeignKey("ume_memory_records.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("relation_type", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column(
            "evidence_ref",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_by_type", sa.String(32), nullable=False, server_default="user"),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        # A memory related to itself is always a modelling mistake.
        sa.CheckConstraint("source_memory_id <> target_memory_id", name="ck_ume_memory_edges_no_self_loop"),
    )
    # Uniqueness over the *unordered* pair: (a,b) and (b,a) are the same
    # relation, and the direction column only says how it was first written.
    op.create_index(
        "uq_ume_memory_edges_pair",
        "ume_memory_edges",
        [
            "workspace_id",
            sa.text("least(source_memory_id, target_memory_id)"),
            sa.text("greatest(source_memory_id, target_memory_id)"),
            "relation_type",
        ],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_index("ix_ume_memory_edges_source", "ume_memory_edges", ["source_memory_id"])
    op.create_index("ix_ume_memory_edges_target", "ume_memory_edges", ["target_memory_id"])
    op.create_index("ix_ume_memory_edges_workspace_status", "ume_memory_edges", ["workspace_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_ume_memory_edges_workspace_status", table_name="ume_memory_edges")
    op.drop_index("ix_ume_memory_edges_target", table_name="ume_memory_edges")
    op.drop_index("ix_ume_memory_edges_source", table_name="ume_memory_edges")
    op.drop_index("uq_ume_memory_edges_pair", table_name="ume_memory_edges")
    op.drop_table("ume_memory_edges")
