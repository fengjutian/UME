"""Shared column helpers for UME business tables.

The container copies `server/` to `/app` and runs `uvicorn main:app`, so `db`
is importable as a top-level module exactly like the pre-existing `server/models.py`
does it. Keeping the import identical means `ume_app` tables land in the same
`Base.metadata` that `alembic/env.py` already uses for autogenerate.
"""

import uuid
from datetime import datetime, timezone

from db import Base
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB

#: JSONB on PostgreSQL (what the migration creates), plain JSON elsewhere so
#: unit tests can run the repository layer on SQLite without a dialect shim.
JSONBType = JSON().with_variant(JSONB, "postgresql")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_uuid() -> uuid.UUID:
    return uuid.uuid4()


__all__ = ["Base", "JSONBType", "new_uuid", "utcnow"]