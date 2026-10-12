"""Create ume_connectors

Revision ID: 013
Revises: 012
Create Date: 2026-10-10

Credentials are never stored in the clear: only a short display prefix and a
bcrypt hash are persisted, exactly as the existing `api_keys` table does.

Purely additive.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "013"
down_revision: Union[str, None] = "012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ume_connectors",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.Uuid(),
            sa.ForeignKey("ume_workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # SET NULL: removing a project must not delete the connector that was
        # using it; the connector keeps working at workspace scope.
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("ume_projects.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("connector_type", sa.String(64), nullable=False),
        # Identifies the calling client instance so one credential can be
        # attributed per machine.
        sa.Column("client_instance_id", sa.String(255), nullable=True),
        sa.Column("credential_prefix", sa.String(16), nullable=False),
        sa.Column("credential_hash", sa.Text(), nullable=False),
        sa.Column(
            "scopes", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")
        ),
        sa.Column(
            "capabilities",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("last_active_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_ume_connectors_workspace_id", "ume_connectors", ["workspace_id"])
    op.create_index("ix_ume_connectors_credential_prefix", "ume_connectors", ["credential_prefix"])
    # Only one live credential may carry a given prefix at a time, so a revoked
    # connector's prefix can be reissued without ambiguity.
    op.create_index(
        "uq_ume_connectors_prefix_active",
        "ume_connectors",
        ["credential_prefix"],
        unique=True,
        postgresql_where=sa.text("revoked_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_ume_connectors_prefix_active", table_name="ume_connectors")
    op.drop_index("ix_ume_connectors_credential_prefix", table_name="ume_connectors")
    op.drop_index("ix_ume_connectors_workspace_id", table_name="ume_connectors")
    op.drop_table("ume_connectors")
