"""Request-level authorization for UME routes.

Enforces section 7.2 in order: authenticate -> resolve the workspace *from the
path* -> verify membership -> verify project boundary -> verify scope. Routes
receive a ready `WorkspaceAccess` and never see a raw user object.

Existence-leak policy: a workspace the caller is not a member of answers 404,
not 403. A 403 would confirm that the id exists. Inside a workspace the caller
*is* a member of, a missing scope answers 403, because there is nothing left to
hide.
"""

import uuid
from dataclasses import dataclass
from typing import Annotated

from auth import require_auth
from db import get_db
from fastapi import Depends, Path
from sqlalchemy.orm import Session
from ume_app.auth.permissions import Principal, role_at_least, scopes_for_role
from ume_app.domain.enums import (
    READABLE_WORKSPACE_STATUSES,
    WorkspaceRole,
    WorkspaceStatus,
)
from ume_app.domain.errors import (
    NotFoundError,
    PermissionDeniedError,
    WorkspaceArchivedError,
)
from ume_app.models.workspace import Workspace
from ume_app.repositories.workspaces import (
    WorkspaceMemberRepository,
    WorkspaceRepository,
)


@dataclass
class WorkspaceAccess:
    """Resolved authorization context for one workspace-scoped request."""

    db: Session
    workspace: Workspace
    role: WorkspaceRole
    principal: Principal

    @property
    def workspace_id(self) -> uuid.UUID:
        return self.workspace.id

    @property
    def user_id(self) -> uuid.UUID:
        assert self.principal.actor_id is not None
        return self.principal.actor_id


async def get_actor(user=Depends(require_auth)) -> Principal:
    """Identity only. Data scopes stay empty until a workspace resolves a role."""
    return Principal(
        actor_type="user",
        actor_id=user.id,
        scopes=frozenset(),
    )


def resolve_access(
    db: Session,
    actor: Principal,
    workspace_id: uuid.UUID,
    *,
    required_scopes: tuple[str, ...] = (),
) -> WorkspaceAccess:
    workspace = WorkspaceRepository(db).get(workspace_id)
    if workspace is None:
        from ume_app.services.audit import record_denial

        record_denial(
            actor,
            action="workspace.access",
            resource_type="workspace",
            resource_id=workspace_id,
            reason="not_found",
        )
        raise NotFoundError("Workspace not found.")

    member = WorkspaceMemberRepository(db).membership(workspace_id, actor.actor_id)
    if member is None:
        from ume_app.services.audit import record_denial

        record_denial(
            actor,
            action="workspace.access",
            resource_type="workspace",
            resource_id=workspace_id,
            reason="not_a_member",
        )
        # Same answer as "no such workspace" — see module docstring.
        raise NotFoundError("Workspace not found.")

    try:
        role = WorkspaceRole(member.role)
    except ValueError as exc:
        raise PermissionDeniedError("当前主体无权访问该资源") from exc

    if workspace.status not in READABLE_WORKSPACE_STATUSES:
        raise WorkspaceArchivedError(f"Workspace is {workspace.status} and does not accept requests.")

    principal = Principal(
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        scopes=scopes_for_role(role),
        workspace_id=workspace.id,
    )

    for scope in required_scopes:
        try:
            principal.require_scope(scope)
        except PermissionDeniedError:
            from ume_app.services.audit import record_denial

            record_denial(
                principal,
                action="workspace.access",
                resource_type="workspace",
                resource_id=workspace.id,
                workspace_id=workspace.id,
                reason=f"missing_scope:{scope}",
            )
            raise

    return WorkspaceAccess(db=db, workspace=workspace, role=role, principal=principal)


def workspace_access(*required_scopes: str):
    """FastAPI dependency factory. Usage: `access = Depends(workspace_access(Scope.PROJECT_READ))`."""

    def dependency(
        workspace_id: Annotated[uuid.UUID, Path()],
        db: Annotated[Session, Depends(get_db)],
        actor: Annotated[Principal, Depends(get_actor)],
    ) -> WorkspaceAccess:
        return resolve_access(db, actor, workspace_id, required_scopes=required_scopes)

    return dependency


def require_writable(access: WorkspaceAccess) -> None:
    """Reject writes to a workspace that is not `active`.

    Reads of an archived workspace stay allowed so an owner can still inspect
    and export it; writes do not.
    """
    if access.workspace.status != WorkspaceStatus.ACTIVE:
        raise WorkspaceArchivedError(f"Workspace is {access.workspace.status}; writes are not accepted.")


def require_owner(access: WorkspaceAccess) -> None:
    if not role_at_least(access.role, WorkspaceRole.OWNER):
        raise PermissionDeniedError("Only the workspace owner can perform this action.")


def require_at_least(access: WorkspaceAccess, minimum: WorkspaceRole) -> None:
    if not role_at_least(access.role, minimum):
        raise PermissionDeniedError("当前主体无权访问该资源")
