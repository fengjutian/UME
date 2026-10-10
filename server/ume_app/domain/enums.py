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


#: Statuses whose data may still be read through normal UME routes.
READABLE_WORKSPACE_STATUSES = frozenset({WorkspaceStatus.ACTIVE, WorkspaceStatus.ARCHIVED})

#: Statuses a workspace can be created or restored into.
WRITABLE_WORKSPACE_STATUSES = frozenset({WorkspaceStatus.ACTIVE, WorkspaceStatus.ARCHIVED})

#: Role precedence. Higher wins when comparing two roles for the same user.
WORKSPACE_ROLE_RANK = {
    WorkspaceRole.VIEWER: 0,
    WorkspaceRole.MEMBER: 1,
    WorkspaceRole.ADMIN: 2,
    WorkspaceRole.OWNER: 3,
}
