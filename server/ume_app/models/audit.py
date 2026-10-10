"""Audit event table.

Written inside the same transaction as the business change: an audited write
that commits without its audit row is worse than a rejected write, because the
rejection is visible to the caller.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column
from ume_app.models.base import Base, JSONBType, new_uuid, utcnow


class AuditEvent(Base):
    __tablename__ = "ume_audit_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    # Nullable: authentication failures and workspace-level denials have no
    # workspace to attribute them to.
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ume_workspaces.id", ondelete="SET NULL"), nullable=True
    )
    actor_type: Mapped[str] = mapped_column(String(32), nullable=False)
    # Deliberately not a foreign key: the actor may be a connector credential
    # that is later deleted, or a system job with no user row at all.
    actor_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    result: Mapped[str] = mapped_column(String(32), nullable=False)
    request_id: Mapped[str] = mapped_column(String(64), nullable=False)
    # Non-sensitive summary only. Never put names, message bodies or tokens here.
    details: Mapped[dict] = mapped_column(JSONBType, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    __table_args__ = (
        Index("ix_ume_audit_events_workspace_created", "workspace_id", "created_at"),
        Index("ix_ume_audit_events_resource", "resource_type", "resource_id"),
        Index("ix_ume_audit_events_actor", "actor_type", "actor_id"),
    )
