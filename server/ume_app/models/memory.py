"""Memory business-projection tables (migration 011)."""

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from ume_app.models.base import Base, JSONBType, new_uuid, utcnow


class MemoryRecord(Base):
    """UME's view of one engine memory.

    Holds no vector and no engine payload: `engine_memory_id` points into the
    engine, `current_text` is the projection the console renders and versions
    are built from. The two can drift, which is why `engine_state` exists.
    """

    __tablename__ = "ume_memory_records"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ume_workspaces.id", ondelete="CASCADE"), nullable=False)
    engine_memory_id: Mapped[str] = mapped_column(String(255), nullable=False)
    memory_type: Mapped[str] = mapped_column(String(64), nullable=False, default="semantic")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    current_text: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[list] = mapped_column(JSONBType, nullable=False, default=list)
    access_scope: Mapped[dict] = mapped_column(JSONBType, nullable=False, default=dict)
    engine_state: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    engine_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_type: Mapped[str] = mapped_column(String(32), nullable=False, default="user")
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("workspace_id", "engine_memory_id", name="uq_ume_memory_records_workspace_engine"),
        Index("ix_ume_memory_records_workspace_status", "workspace_id", "status"),
        Index("ix_ume_memory_records_engine_state", "engine_state"),
        Index("ix_ume_memory_records_deleted_at", "deleted_at"),
    )


class MemoryProjectLink(Base):
    __tablename__ = "ume_memory_projects"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    memory_record_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ume_memory_records.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ume_projects.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    __table_args__ = (
        UniqueConstraint("memory_record_id", "project_id", name="uq_ume_memory_projects_record_project"),
        Index("ix_ume_memory_projects_project_id", "project_id"),
    )


class MemorySource(Base):
    """Provenance: which message a memory came from.

    `conversation_id` and `message_id` are nullable on purpose. A source must
    survive its own message being deleted — the pointer becomes a tombstone
    rather than taking the memory with it.
    """

    __tablename__ = "ume_memory_sources"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ume_workspaces.id", ondelete="CASCADE"), nullable=False)
    memory_record_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ume_memory_records.id", ondelete="CASCADE"), nullable=False
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ume_conversations.id", ondelete="SET NULL"), nullable=True
    )
    message_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    extraction_method: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    __table_args__ = (
        Index("ix_ume_memory_sources_record_id", "memory_record_id"),
        Index("ix_ume_memory_sources_message_id", "message_id"),
        Index("ix_ume_memory_sources_conversation_id", "conversation_id"),
    )


class MemoryVersion(Base):
    """An immutable history entry. `current_text` always equals the newest one."""

    __tablename__ = "ume_memory_versions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    memory_record_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ume_memory_records.id", ondelete="CASCADE"), nullable=False
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    extra_metadata: Mapped[dict] = mapped_column(JSONBType, nullable=False, default=dict)
    change_type: Mapped[str] = mapped_column(String(32), nullable=False)
    change_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor_type: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    __table_args__ = (
        UniqueConstraint("memory_record_id", "version_no", name="uq_ume_memory_versions_record_version"),
        Index("ix_ume_memory_versions_record_created", "memory_record_id", "created_at"),
    )
