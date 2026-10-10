"""Repository primitives: workspace scoping and keyset pagination.

Section 7.2 requires the workspace/project filter to be part of the query
itself, not something a caller remembers to add afterwards. Every UME
repository derives from `ScopedRepository` and exposes only lookups that take a
mandatory `workspace_id`, so a route cannot accidentally build an unscoped
`WHERE`.
"""

import base64
import binascii
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Generic, Sequence, TypeVar

from ume_app.domain.errors import ValidationError
from sqlalchemy import Select, tuple_
from sqlalchemy.orm import Session

ModelT = TypeVar("ModelT")

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200


@dataclass(frozen=True)
class Page(Generic[ModelT]):
    items: list[ModelT]
    next_cursor: str | None
    has_more: bool


def encode_cursor(created_at: datetime, row_id: uuid.UUID) -> str:
    raw = f"{created_at.isoformat()}|{row_id}"
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    padded = cursor + "=" * (-len(cursor) % 4)
    try:
        raw = base64.urlsafe_b64decode(padded.encode()).decode()
        timestamp, row_id = raw.split("|", 1)
        return datetime.fromisoformat(timestamp), uuid.UUID(row_id)
    except (ValueError, binascii.Error, UnicodeDecodeError) as exc:
        raise ValidationError("Invalid cursor.") from exc


def clamp_page_size(limit: int | None) -> int:
    if limit is None:
        return DEFAULT_PAGE_SIZE
    if limit < 1 or limit > MAX_PAGE_SIZE:
        raise ValidationError(f"limit must be between 1 and {MAX_PAGE_SIZE}.")
    return limit


class ScopedRepository(Generic[ModelT]):
    """Base class binding a model to a workspace-scoped query builder."""

    model: type[ModelT]

    def __init__(self, db: Session) -> None:
        self.db = db

    def _scoped(self, workspace_id: uuid.UUID) -> Select:
        return self.db.query(self.model).filter(self.model.workspace_id == workspace_id)

    def apply_cursor(self, stmt: Select, cursor: str | None) -> Select:
        """Apply keyset pagination to a query ordered by (created_at DESC, id DESC).

        Both columns are needed in the sort key: `created_at` alone collides
        whenever a batch lands inside the same transaction.
        """
        if cursor is None:
            return stmt
        cursor_created_at, cursor_id = decode_cursor(cursor)
        return stmt.filter(tuple_(self.model.created_at, self.model.id) < tuple_(cursor_created_at, cursor_id))

    def _build_page(self, stmt: Select, limit: int) -> Page[ModelT]:
        """Run the query with one extra row to decide `has_more` without a count."""
        rows: Sequence[ModelT] = list(stmt.limit(limit + 1))
        has_more = len(rows) > limit
        items = list(rows[:limit])
        next_cursor = None
        if has_more and items:
            last = items[-1]
            next_cursor = encode_cursor(last.created_at, last.id)
        return Page(items=items, next_cursor=next_cursor, has_more=has_more)


def row_to_dict(row: Any) -> dict[str, Any]:
    return {column.name: getattr(row, column.name) for column in row.__table__.columns}