"""Workspace and membership use cases. Owns the transaction boundary.

Routes call these and translate the result; they never touch a session directly.
"""

import uuid
from typing import Any

from sqlalchemy.orm import Session
from ume_app.auth.dependencies import (
    WorkspaceAccess,
    require_at_least,
    require_writable,
)
from ume_app.auth.permissions import Principal
from ume_app.domain.enums import WorkspaceRole, WorkspaceStatus
from ume_app.domain.errors import ConflictError, NotFoundError, ValidationError
from ume_app.models.workspace import Workspace
from ume_app.repositories.base import Page
from ume_app.repositories.workspaces import (
    WorkspaceMemberRepository,
    WorkspaceRepository,
)
from ume_app.services.audit import record


def list_for_user(db: Session, user_id: uuid.UUID, *, limit: int, cursor: str | None) -> Page[Workspace]:
    return WorkspaceRepository(db).list_for_user(user_id, limit=limit, cursor=cursor)


def create(db: Session, principal: Principal, payload: dict[str, Any]) -> Workspace:
    """Create a workspace and seat the creator as owner in one transaction."""
    workspace = Workspace(
        name=payload["name"],
        description=payload.get("description"),
        owner_user_id=principal.actor_id,
        status=str(WorkspaceStatus.ACTIVE),
        default_memory_policy=payload.get("default_memory_policy") or {},
    )
    db.add(workspace)
    db.flush()

    WorkspaceMemberRepository(db).add(workspace.id, principal.actor_id, str(WorkspaceRole.OWNER))
    record(
        db,
        principal,
        action="workspace.create",
        resource_type="workspace",
        resource_id=workspace.id,
        workspace_id=workspace.id,
        details={"name": workspace.name},
    )
    db.commit()
    db.refresh(workspace)
    return workspace


def update(db: Session, access: WorkspaceAccess, changes: dict[str, Any]) -> Workspace:
    require_writable(access)
    workspace = access.workspace
    for key, value in changes.items():
        setattr(workspace, key, value)
    from ume_app.models.base import utcnow

    workspace.updated_at = utcnow()
    record(
        db,
        access.principal,
        action="workspace.update",
        resource_type="workspace",
        resource_id=workspace.id,
        workspace_id=workspace.id,
        details={"fields": sorted(changes)},
    )
    db.commit()
    db.refresh(workspace)
    return workspace


def delete(db: Session, access: WorkspaceAccess) -> None:
    """Delete a workspace and its membership rows.

    Refuses while projects still exist: at this phase the cascade is safe, but
    once conversations and memories arrive the delete has to go through the
    recoverable state machine in section 11.2 instead of a FK cascade.
    """
    require_at_least(access, WorkspaceRole.ADMIN)
    workspace_id = access.workspace.id

    from sqlalchemy import func, select
    from ume_app.models.project import Project

    project_count = db.execute(select(func.count(Project.id)).where(Project.workspace_id == workspace_id)).scalar_one()
    if project_count:
        raise ConflictError(
            "Workspace still contains projects. Delete them first, or archive the workspace instead.",
            details={"project_count": project_count},
        )

    db.delete(access.workspace)
    db.flush()
    record(
        db,
        access.principal,
        action="workspace.delete",
        resource_type="workspace",
        resource_id=workspace_id,
        workspace_id=workspace_id,
        details={},
    )
    db.commit()


def list_members(db: Session, access: WorkspaceAccess, *, limit: int, cursor: str | None) -> Page:
    return WorkspaceMemberRepository(db).list_members(access.workspace_id, limit=limit, cursor=cursor)


def add_member(db: Session, access: WorkspaceAccess, user_id: uuid.UUID, role: str) -> Any:
    require_at_least(access, WorkspaceRole.ADMIN)
    require_writable(access)
    if user_id == access.workspace.owner_user_id and role != str(WorkspaceRole.OWNER):
        raise ValidationError("The workspace owner cannot be demoted by adding a different role.")
    member = WorkspaceMemberRepository(db).add(access.workspace_id, user_id, role)
    record(
        db,
        access.principal,
        action="workspace.member.add",
        resource_type="workspace_member",
        resource_id=member.id,
        workspace_id=access.workspace_id,
        details={"target_user_id": str(user_id), "role": role},
    )
    db.commit()
    db.refresh(member)
    return member


def set_member_role(db: Session, access: WorkspaceAccess, user_id: uuid.UUID, role: str) -> Any:
    require_at_least(access, WorkspaceRole.ADMIN)
    require_writable(access)
    if user_id == access.workspace.owner_user_id and role != str(WorkspaceRole.OWNER):
        _guard_last_owner(db, access.workspace_id, user_id)
    member = WorkspaceMemberRepository(db).set_role(access.workspace_id, user_id, role)
    record(
        db,
        access.principal,
        action="workspace.member.update",
        resource_type="workspace_member",
        resource_id=member.id,
        workspace_id=access.workspace_id,
        details={"target_user_id": str(user_id), "role": role},
    )
    db.commit()
    db.refresh(member)
    return member


def remove_member(db: Session, access: WorkspaceAccess, user_id: uuid.UUID) -> None:
    require_at_least(access, WorkspaceRole.ADMIN)
    require_writable(access)
    if user_id == access.workspace.owner_user_id:
        _guard_last_owner(db, access.workspace_id, user_id)
    WorkspaceMemberRepository(db).remove(access.workspace_id, user_id)
    record(
        db,
        access.principal,
        action="workspace.member.remove",
        resource_type="workspace_member",
        resource_id=None,
        workspace_id=access.workspace_id,
        details={"target_user_id": str(user_id)},
    )
    db.commit()


def _guard_last_owner(db: Session, workspace_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """Refuse to leave a workspace without an owner."""
    from sqlalchemy import func, select
    from ume_app.models.workspace import WorkspaceMember

    owners = db.execute(
        select(func.count(WorkspaceMember.id)).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.role == str(WorkspaceRole.OWNER),
        )
    ).scalar_one()
    if owners <= 1:
        raise ConflictError("A workspace must keep at least one owner.")


def require_member_exists(db: Session, workspace_id: uuid.UUID, user_id: uuid.UUID) -> None:
    if WorkspaceMemberRepository(db).membership(workspace_id, user_id) is None:
        raise NotFoundError("Workspace member not found.")
