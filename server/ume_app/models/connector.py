"""Connector credentials (migration 013)."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from ume_app.models.base import Base, JSONBType, new_uuid, utcnow


class Connector(Base):
    """A machine credential bound to one workspace and optionally one project.

    `credential_hash` is a bcrypt hash; the plaintext is shown once at creation
    and never recoverable. `revoked_at` is checked on every request rather than
    cached, so a revoke takes effect on the next call rather than the next
    expiry.
    """

    __tablename__ = "ume_connectors"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ume_workspaces.id", ondelete="CASCADE"), nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ume_projects.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    connector_type: Mapped[str] = mapped_column(String(64), nullable=False)
    client_instance_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    credential_prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    credential_hash: Mapped[str] = mapped_column(Text, nullable=False)
    scopes: Mapped[list] = mapped_column(JSONBType, nullable=False, default=list)
    capabilities: Mapped[dict] = mapped_column(JSONBType, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    created_by: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at is not None

    def as_dict(self) -> dict:
        """Wire shape. Deliberately omits `credential_hash`."""
        return {
            "id": str(self.id),
            "workspace_id": str(self.workspace_id),
            "project_id": str(self.project_id) if self.project_id else None,
            "name": self.name,
            "connector_type": self.connector_type,
            "client_instance_id": self.client_instance_id,
            "credential_prefix": self.credential_prefix,
            "scopes": list(self.scopes or []),
            "capabilities": dict(self.capabilities or {}),
            "status": self.status,
            "last_active_at": self.last_active_at,
            "revoked_at": self.revoked_at,
            "created_at": self.created_at,
        }
