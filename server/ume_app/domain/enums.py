"""UME domain vocabulary.

Kept free of SQLAlchemy and FastAPI imports so services, repositories and tests
can all depend on these names without dragging in a transport or a DB session.
"""

from enum import StrEnum


class ActorType(StrEnum):
    """Who is acting on a resource. Mirrors section 7.1 of the implementation doc."""

    USER = "user"
    CONNECTOR = "connector"
    SYSTEM = "system"


class WorkspaceStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETING = "deleting"


class WorkspaceRole(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


class ProjectStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class ConversationStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class Sensitivity(StrEnum):
    """How freely a message body may be surfaced elsewhere in UME.

    `restricted` bodies are never used as evidence excerpts and never enter
    context assembly.
    """

    NORMAL = "normal"
    SENSITIVE = "sensitive"
    RESTRICTED = "restricted"


class ImportJobStatus(StrEnum):
    """Import state machine (section 10.2).

    `EXTRACTING` is only entered when an extractor is bound; without one the
    job goes `importing -> completed` because there is nothing to fail.
    """

    PENDING = "pending"
    VALIDATING = "validating"
    IMPORTING = "importing"
    EXTRACTING = "extracting"
    COMPLETED = "completed"
    VALIDATION_FAILED = "validation_failed"
    IMPORT_FAILED = "import_failed"
    EXTRACTION_PARTIAL = "extraction_partial"


#: Terminal states: a job in one of these never changes again on its own.
TERMINAL_IMPORT_STATES = frozenset(
    {
        ImportJobStatus.COMPLETED,
        ImportJobStatus.VALIDATION_FAILED,
        ImportJobStatus.IMPORT_FAILED,
        ImportJobStatus.EXTRACTION_PARTIAL,
    }
)

#: The only forward transitions the import service is allowed to make.
IMPORT_TRANSITIONS: dict[ImportJobStatus, frozenset[ImportJobStatus]] = {
    ImportJobStatus.PENDING: frozenset({ImportJobStatus.VALIDATING, ImportJobStatus.VALIDATION_FAILED}),
    ImportJobStatus.VALIDATING: frozenset({ImportJobStatus.IMPORTING, ImportJobStatus.VALIDATION_FAILED}),
    ImportJobStatus.IMPORTING: frozenset(
        {
            ImportJobStatus.EXTRACTING,
            ImportJobStatus.COMPLETED,
            ImportJobStatus.IMPORT_FAILED,
            ImportJobStatus.EXTRACTION_PARTIAL,
        }
    ),
    ImportJobStatus.EXTRACTING: frozenset({ImportJobStatus.COMPLETED, ImportJobStatus.EXTRACTION_PARTIAL}),
    ImportJobStatus.COMPLETED: frozenset(),
    ImportJobStatus.VALIDATION_FAILED: frozenset({ImportJobStatus.VALIDATING}),
    ImportJobStatus.IMPORT_FAILED: frozenset({ImportJobStatus.IMPORTING}),
    ImportJobStatus.EXTRACTION_PARTIAL: frozenset({ImportJobStatus.EXTRACTING}),
}


#: Statuses whose data may still be read through normal UME routes.
READABLE_WORKSPACE_STATUSES = frozenset({WorkspaceStatus.ACTIVE, WorkspaceStatus.ARCHIVED})


class MemoryStatus(StrEnum):
    """Business lifecycle of a memory record (section 5.4)."""

    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


class EngineState(StrEnum):
    """How far the engine half of a write got.

    The business row and the engine write cannot share a transaction, so this
    column is the recovery handle: a record stuck in `pending` or `failed` is
    safe to retry, one in `deleting` is safe to finish.
    """

    PENDING = "pending"
    READY = "ready"
    FAILED = "failed"
    DELETING = "deleting"
    DELETED = "deleted"


class MemoryChangeType(StrEnum):
    CREATED = "created"
    UPDATED = "updated"
    RESTORED = "restored"
    ARCHIVED = "archived"
    DELETED = "deleted"


#: `current_text` is the business projection of the engine memory. A record
#: whose projection and engine text disagree is repairable rather than lost.
RECONCIABLE_ENGINE_STATES = frozenset({EngineState.READY, EngineState.FAILED, EngineState.DELETING})

#: Statuses whose text may be returned to a caller.
READABLE_MEMORY_STATUSES = frozenset({MemoryStatus.ACTIVE, MemoryStatus.ARCHIVED})

#: Statuses a workspace can be created or restored into.
WRITABLE_WORKSPACE_STATUSES = frozenset({WorkspaceStatus.ACTIVE, WorkspaceStatus.ARCHIVED})

#: Role precedence. Higher wins when comparing two roles for the same user.
WORKSPACE_ROLE_RANK = {
    WorkspaceRole.VIEWER: 0,
    WorkspaceRole.MEMBER: 1,
    WorkspaceRole.ADMIN: 2,
    WorkspaceRole.OWNER: 3,
}
