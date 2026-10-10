"""Import job and idempotency tables (migration 010).

`ume_idempotency_keys` is a generic record, not an import-only one: section 9.4
requires idempotency for batch message writes, connector creation and export
jobs too, and a separate table for each would mean three migrations that all
carry the same columns.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from ume_app.models.base import Base, JSONBType, new_uuid, utcnow


class ImportJob(Base):
    __tablename__ = "ume_import_jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ume_workspaces.id", ondelete="CASCADE"), nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ume_projects.id", ondelete="SET NULL"), nullable=True
    )
    connector_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    input_summary: Mapped[dict] = mapped_column(JSONBType, nullable=False, default=dict)
    result_summary: Mapped[dict] = mapped_column(JSONBType, nullable=False, default=dict)
    error_summary: Mapped[dict] = mapped_column(JSONBType, nullable=False, default=dict)
    created_by: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("workspace_id", "idempotency_key", name="uq_ume_import_jobs_workspace_idem"),
        Index("ix_ume_import_jobs_workspace_status", "workspace_id", "status"),
    )


class IdempotencyKey(Base):
    """Replay guard for non-idempotent POSTs (section 9.4).

    The key is scoped to (workspace, actor) rather than to the workspace alone so
    two callers cannot collide on, or read each other's, replay records.
    """

    __tablename__ = "ume_idempotency_keys"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ume_workspaces.id", ondelete="CASCADE"), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    # Hash of the canonical request body: same key + different body is a
    # conflict, not a replay.
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    # Enough of the first response to replay it, never the whole payload.
    response_summary: Mapped[dict] = mapped_column(JSONBType, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "actor_type", "actor_id", "idempotency_key", name="uq_ume_idempotency_scope_key"
        ),
        Index("ix_ume_idempotency_keys_expires_at", "expires_at"),
    )
