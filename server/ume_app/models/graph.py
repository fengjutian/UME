"""Memory relation edges (migration 012)."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column
from ume_app.models.base import Base, JSONBType, new_uuid, utcnow


class MemoryEdge(Base):
    """A directed relation between two memories.

    The database treats the pair as unordered: `source -> target` and
    `target -> source` with the same relation type are the same edge, so a
    second write in the reverse direction is reported as a conflict rather than
    silently duplicating the relation.

    The unordered-pair unique index lives only in migration 012: it needs
    `least()`/`greatest()` and a partial `WHERE`, which are PostgreSQL-only and
    would break `Base.metadata.create_all` on the SQLite test database. The
    repository enforces the same rule in application code so the behaviour is
    covered either way.
    """

    __tablename__ = "ume_memory_edges"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ume_workspaces.id", ondelete="CASCADE"), nullable=False)
    source_memory_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ume_memory_records.id", ondelete="CASCADE"), nullable=False
    )
    target_memory_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ume_memory_records.id", ondelete="CASCADE"), nullable=False
    )
    relation_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    evidence_ref: Mapped[dict] = mapped_column(JSONBType, nullable=False, default=dict)
    created_by_type: Mapped[str] = mapped_column(String(32), nullable=False, default="user")
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    __table_args__ = (CheckConstraint("source_memory_id <> target_memory_id", name="ck_ume_memory_edges_no_self_loop"),)

    def as_dict(self, **extra: Any) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "source_memory_id": str(self.source_memory_id),
            "target_memory_id": str(self.target_memory_id),
            "relation_type": self.relation_type,
            "status": self.status,
            "created_at": self.created_at,
            **extra,
        }
