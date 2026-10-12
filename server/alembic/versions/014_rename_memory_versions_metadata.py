"""Rename ume_memory_versions.metadata to extra_metadata

Revision ID: 014
Revises: 013
Create Date: 2026-10-12

Migration 011 created this column as `metadata`, which collides with SQLAlchemy's
own `Base.metadata`. The Python attribute was renamed to `extra_metadata` to
escape the collision, but the column kept the old name and the two artefacts
drifted apart.

That drift broke the write path in two separate ways:

* `MemoryVersion.extra_metadata` mapped to a column `extra_metadata` that no
  migration ever created, so every version insert died with
  `UndefinedColumn: column "extra_metadata" of relation "ume_memory_versions"
  does not exist`.
* Mapping the attribute onto a column still named `metadata` fixed the insert
  but broke `repositories.base.row_to_dict`, which reads `getattr(row,
  column.name)` — on an ORM instance `row.metadata` resolves to the class-level
  `MetaData` object, so JSON encoding walked the whole table graph and raised
  `RecursionError`.

Both are invisible to the unit suite because `conftest.py` builds its SQLite
schema with `Base.metadata.create_all`, i.e. from the models rather than from
the migrations. Only a real migrated database shows the disagreement.

Renaming the column is the fix that removes the footgun rather than working
around it. 011 is published and is not edited.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "014"
down_revision: Union[str, None] = "013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "ume_memory_versions"
_OLD = "metadata"
_NEW = "extra_metadata"


def upgrade() -> None:
    op.alter_column(
        _TABLE,
        _OLD,
        new_column_name=_NEW,
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        existing_nullable=False,
        existing_server_default=sa.text("'{}'::jsonb"),
    )


def downgrade() -> None:
    op.alter_column(
        _TABLE,
        _NEW,
        new_column_name=_OLD,
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        existing_nullable=False,
        existing_server_default=sa.text("'{}'::jsonb"),
    )
