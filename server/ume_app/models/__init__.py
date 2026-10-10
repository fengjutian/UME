"""SQLAlchemy models for the UME business tables.

Importing this package registers every UME table on the same `Base.metadata`
the Alembic environment already targets.
"""

from ume_app.models.audit import AuditEvent
from ume_app.models.base import Base, JSONBType, new_uuid, utcnow
from ume_app.models.conversation import Conversation, Message
from ume_app.models.import_job import IdempotencyKey, ImportJob
from ume_app.models.project import Project
from ume_app.models.workspace import Workspace, WorkspaceMember

__all__ = [
    "AuditEvent",
    "Base",
    "Conversation",
    "IdempotencyKey",
    "ImportJob",
    "JSONBType",
    "Message",
    "Project",
    "Workspace",
    "WorkspaceMember",
    "new_uuid",
    "utcnow",
]
