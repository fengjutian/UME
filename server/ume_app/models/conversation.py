"""Conversation and message tables (migration 009).

Messages are archived verbatim and never mutated in place; corrections arrive as
a new row. Deduplication is a database concern, expressed as partial unique
indexes keyed on the external id when the connector supplies one.
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from ume_app.models.base import Base, JSONBType, new_uuid, utcnow


class Conversation(Base):
    __tablename__ = "ume_conversations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ume_workspaces.id", ondelete="CASCADE"), nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ume_projects.id", ondelete="SET NULL"), nullable=True
    )
    # NULL until P4 ships connectors. Kept as a plain UUID with no foreign key
    # so this migration does not depend on the connector table existing.
    connector_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    external_conversation_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False, default="generic")
    retention_policy: Mapped[str] = mapped_column(String(64), nullable=False, default="retain")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    __table_args__ = (
        Index("ix_ume_conversations_workspace_id", "workspace_id"),
        Index("ix_ume_conversations_project_id", "project_id"),
        Index("ix_ume_conversations_workspace_last_message", "workspace_id", "last_message_at"),
    )


class Message(Base):
    __tablename__ = "ume_messages"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ume_workspaces.id", ondelete="CASCADE"), nullable=False)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ume_conversations.id", ondelete="CASCADE"), nullable=False
    )
    external_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    content_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Non-text payloads (attachments, tool blobs) live outside the row; this
    # holds the pointer. At least one of content_text / content_ref is required.
    content_ref: Mapped[dict | None] = mapped_column(JSONBType, nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    extra_metadata: Mapped[dict] = mapped_column(JSONBType, nullable=False, default=dict)
    sensitivity: Mapped[str] = mapped_column(String(32), nullable=False, default="normal")
    message_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    import_job_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    # Tombstone marker: the row survives for provenance but must never be
    # returned to a caller.
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    __table_args__ = (
        CheckConstraint(
            "content_text IS NOT NULL OR content_ref IS NOT NULL",
            name="ck_ume_messages_has_content",
        ),
        CheckConstraint(
            "deleted_at IS NULL OR created_at IS NOT NULL",
            name="ck_ume_messages_tombstone_has_created_at",
        ),
        Index("ix_ume_messages_workspace_id", "workspace_id"),
        Index("ix_ume_messages_conversation_browse", "conversation_id", "message_at", "id"),
        Index("ix_ume_messages_conversation_dedup", "conversation_id", "content_hash", "message_at"),
        Index("ix_ume_messages_import_job_id", "import_job_id"),
    )
