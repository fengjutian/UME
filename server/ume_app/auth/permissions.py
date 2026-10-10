"""Identity and the workspace permission matrix.

Section 7 of the implementation doc requires that authorization be decided on the
server and re-checked at the data-access layer. This module owns the first half:
it defines the scope vocabulary, the role -> scope matrix, and the `Principal`
that routes and repositories thread through the request.

Scope vocabulary follows section 7.3. The doc lists the ten scopes a connector
needs; a user-driven API additionally has to express "manage this workspace",
"write a project row" and "run an import", so those three are added here and
called out in the delivery notes as an extension of the suggested list. No
connector is ever granted them by default.
"""

import uuid
from dataclasses import dataclass, field

from ume_app.domain.enums import WORKSPACE_ROLE_RANK, ActorType, WorkspaceRole
from ume_app.domain.errors import PermissionDeniedError, UnauthenticatedError


class Scope:
    """Scope constants. Plain strings so they can be stored in JSONB as-is."""

    # Read scopes (section 7.3).
    WORKSPACE_READ = "workspace:read"
    PROJECT_READ = "project:read"
    CONVERSATION_READ = "conversation:read"
    MEMORY_READ = "memory:read"
    CONTEXT_READ = "context:read"
    GRAPH_READ = "graph:read"
    EXPORT_READ = "export:read"

    # Write scopes (section 7.3).
    CONVERSATION_WRITE = "conversation:write"
    MEMORY_WRITE = "memory:write"
    GRAPH_WRITE = "graph:write"

    # Management scopes (extension beyond section 7.3, user actors only).
    WORKSPACE_MANAGE = "workspace:manage"
    PROJECT_WRITE = "project:write"
    CONNECTOR_MANAGE = "connector:manage"
    IMPORT_WRITE = "import:write"


READ_SCOPES = frozenset(
    {
        Scope.WORKSPACE_READ,
        Scope.PROJECT_READ,
        Scope.CONVERSATION_READ,
        Scope.MEMORY_READ,
        Scope.CONTEXT_READ,
        Scope.GRAPH_READ,
        Scope.EXPORT_READ,
    }
)

WRITE_SCOPES = frozenset(
    {
        Scope.CONVERSATION_WRITE,
        Scope.MEMORY_WRITE,
        Scope.GRAPH_WRITE,
    }
)

#: Capabilities a plain member needs beyond reading and writing memories:
#: creating/updating project rows and running an import. Without these, a
#: member could write memories but not decide which project they belong to.
MEMBER_SCOPES = (
    READ_SCOPES
    | WRITE_SCOPES
    | {
        Scope.PROJECT_WRITE,
        Scope.IMPORT_WRITE,
    }
)

#: Capabilities reserved for admins: administering the workspace itself and
#: issuing connector credentials.
ADMIN_ONLY_SCOPES = frozenset(
    {
        Scope.WORKSPACE_MANAGE,
        Scope.CONNECTOR_MANAGE,
    }
)

ADMIN_SCOPES = MEMBER_SCOPES | ADMIN_ONLY_SCOPES

ALL_SCOPES = ADMIN_SCOPES

#: Scopes a connector credential may hold. Connectors never administer the
#: workspace itself, they only read/write their assigned project data.
CONNECTOR_SCOPES = frozenset(
    {
        Scope.WORKSPACE_READ,
        Scope.PROJECT_READ,
        Scope.CONVERSATION_READ,
        Scope.CONVERSATION_WRITE,
        Scope.MEMORY_READ,
        Scope.MEMORY_WRITE,
        Scope.CONTEXT_READ,
        Scope.GRAPH_READ,
    }
)

ROLE_SCOPES: dict[WorkspaceRole, frozenset[str]] = {
    WorkspaceRole.VIEWER: READ_SCOPES,
    WorkspaceRole.MEMBER: MEMBER_SCOPES,
    WorkspaceRole.ADMIN: ADMIN_SCOPES,
    WorkspaceRole.OWNER: ALL_SCOPES,
}


def scopes_for_role(role: WorkspaceRole) -> frozenset[str]:
    """Scopes granted by a workspace role. Raises on an unknown role name."""
    try:
        return ROLE_SCOPES[WorkspaceRole(role)]
    except (KeyError, ValueError) as exc:
        raise ValueError(f"unknown workspace role: {role!r}") from exc


def role_at_least(role: WorkspaceRole, minimum: WorkspaceRole) -> bool:
    return WORKSPACE_ROLE_RANK[WorkspaceRole(role)] >= WORKSPACE_ROLE_RANK[WorkspaceRole(minimum)]


@dataclass(frozen=True)
class Principal:
    """The authenticated actor plus the scope set it may act with.

    `workspace_id`/`project_id` are the *binding* of this credential to data
    scope; they are derived from the credential, never from a request body.
    """

    actor_type: ActorType
    actor_id: uuid.UUID
    scopes: frozenset[str] = field(default_factory=frozenset)
    workspace_id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None
    system_action: str | None = None

    def __post_init__(self) -> None:
        if self.actor_type == ActorType.SYSTEM and not self.system_action:
            raise ValueError("a system principal must declare an explicit system_action")

    @property
    def is_system(self) -> bool:
        return self.actor_type == ActorType.SYSTEM

    def has_scope(self, scope: str) -> bool:
        return scope in self.scopes

    def has_all_scopes(self, scopes: frozenset[str] | set[str]) -> bool:
        return scopes <= self.scopes

    def require_scope(self, scope: str) -> None:
        if not self.has_scope(scope):
            raise PermissionDeniedError("当前主体无权访问该资源")

    def require_workspace(self, workspace_id: uuid.UUID) -> None:
        """Reject a principal that is bound to a different workspace.

        This is a coarse guard for credentials with a fixed workspace binding.
        Unbound user principals pass; route-level membership checks decide them.
        """
        if self.workspace_id is not None and self.workspace_id != workspace_id:
            raise PermissionDeniedError("当前主体无权访问该资源")

    def require_authenticated(self) -> None:
        raise UnauthenticatedError("Authentication required.")


def user_principal(
    user_id: uuid.UUID,
    scopes: frozenset[str],
    *,
    workspace_id: uuid.UUID | None = None,
    project_id: uuid.UUID | None = None,
) -> Principal:
    return Principal(
        actor_type=ActorType.USER,
        actor_id=user_id,
        scopes=scopes,
        workspace_id=workspace_id,
        project_id=project_id,
    )


def system_principal(actor_id: uuid.UUID, system_action: str, scopes: frozenset[str]) -> Principal:
    return Principal(
        actor_type=ActorType.SYSTEM,
        actor_id=actor_id,
        scopes=scopes,
        system_action=system_action,
    )
