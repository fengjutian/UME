"""Workspace routes. HTTP parsing and response shaping only.

Authorization arrives pre-resolved as `WorkspaceAccess`; the route never
re-derives a workspace from the request body.
"""

import uuid
from typing import Annotated

from db import get_db
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from ume_app.api.responses import created, dump, page, success
from ume_app.auth.dependencies import WorkspaceAccess, get_actor, workspace_access
from ume_app.auth.permissions import Principal, Scope
from ume_app.repositories.base import clamp_page_size
from ume_app.schemas.workspace import (
    ProjectCreate,
    WorkspaceCreate,
    WorkspaceMemberCreate,
    WorkspaceMemberPatch,
    WorkspacePatch,
)
from ume_app.services import projects as project_service
from ume_app.services import workspaces as workspace_service

router = APIRouter()

LimitQuery = Annotated[int | None, Query(ge=1, le=200)]
CursorQuery = Annotated[str | None, Query()]


@router.get("/workspaces", summary="List workspaces the caller belongs to")
def list_workspaces(
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[Principal, Depends(get_actor)],
    limit: LimitQuery = None,
    cursor: CursorQuery = None,
):
    result = workspace_service.list_for_user(db, actor.actor_id, limit=clamp_page_size(limit), cursor=cursor)
    return page([dump(item) for item in result.items], result.next_cursor, result.has_more)


@router.post("/workspaces", status_code=status.HTTP_201_CREATED, summary="Create a workspace")
def create_workspace(
    payload: WorkspaceCreate,
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[Principal, Depends(get_actor)],
):
    workspace = workspace_service.create(db, actor, payload.model_dump())
    return created(dump(workspace))


@router.get("/workspaces/{workspace_id}", summary="Get a workspace")
def get_workspace(access: Annotated[WorkspaceAccess, Depends(workspace_access(Scope.WORKSPACE_READ))]):
    return success(dump(access.workspace))


@router.patch("/workspaces/{workspace_id}", summary="Update a workspace")
def update_workspace(
    payload: WorkspacePatch,
    access: Annotated[WorkspaceAccess, Depends(workspace_access(Scope.WORKSPACE_MANAGE))],
):
    return success(dump(workspace_service.update(access.db, access, payload.changes())))


@router.delete("/workspaces/{workspace_id}", summary="Delete an empty workspace")
def delete_workspace(access: Annotated[WorkspaceAccess, Depends(workspace_access(Scope.WORKSPACE_MANAGE))]):
    workspace_id = access.workspace_id
    workspace_service.delete(access.db, access)
    return success({"id": str(workspace_id), "deleted": True})


@router.get("/workspaces/{workspace_id}/members", summary="List workspace members")
def list_members(
    access: Annotated[WorkspaceAccess, Depends(workspace_access(Scope.WORKSPACE_READ))],
    limit: LimitQuery = None,
    cursor: CursorQuery = None,
):
    result = workspace_service.list_members(access.db, access, limit=clamp_page_size(limit), cursor=cursor)
    return page([dump(item) for item in result.items], result.next_cursor, result.has_more)


@router.post("/workspaces/{workspace_id}/members", status_code=status.HTTP_201_CREATED, summary="Add a member")
def add_member(
    payload: WorkspaceMemberCreate,
    access: Annotated[WorkspaceAccess, Depends(workspace_access(Scope.WORKSPACE_MANAGE))],
):
    member = workspace_service.add_member(access.db, access, payload.user_id, payload.role)
    return created(dump(member))


@router.patch("/workspaces/{workspace_id}/members/{user_id}", summary="Change a member role")
def update_member(
    payload: WorkspaceMemberPatch,
    access: Annotated[WorkspaceAccess, Depends(workspace_access(Scope.WORKSPACE_MANAGE))],
    user_id: uuid.UUID,
):
    member = workspace_service.set_member_role(access.db, access, user_id, payload.role)
    return success(dump(member))


@router.delete("/workspaces/{workspace_id}/members/{user_id}", summary="Remove a member")
def remove_member(
    access: Annotated[WorkspaceAccess, Depends(workspace_access(Scope.WORKSPACE_MANAGE))],
    user_id: uuid.UUID,
):
    workspace_service.remove_member(access.db, access, user_id)
    return success({"user_id": str(user_id), "removed": True})


@router.get("/workspaces/{workspace_id}/projects", summary="List projects")
def list_projects(
    access: Annotated[WorkspaceAccess, Depends(workspace_access(Scope.PROJECT_READ))],
    limit: LimitQuery = None,
    cursor: CursorQuery = None,
    project_status: Annotated[str | None, Query(alias="status", max_length=32)] = None,
):
    result = project_service.list_for_workspace(
        access, limit=clamp_page_size(limit), cursor=cursor, status=project_status
    )
    return page([dump(item) for item in result.items], result.next_cursor, result.has_more)


@router.post("/workspaces/{workspace_id}/projects", status_code=status.HTTP_201_CREATED, summary="Create a project")
def create_project(
    payload: ProjectCreate,
    access: Annotated[WorkspaceAccess, Depends(workspace_access(Scope.PROJECT_WRITE))],
):
    return created(dump(project_service.create(access, payload.model_dump())))
