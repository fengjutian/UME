"""Top-level project routes: `/projects/{project_id}`.

The path carries no workspace, so the workspace is resolved from the project id
itself and then *re-validated* through the scoped repository. Resolving the
workspace is not the authorization step — membership and scope checks are, and
they run before any project field is returned.
"""

import uuid
from typing import Annotated

from db import get_db
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ume_app.api.responses import dump, success
from ume_app.auth.dependencies import WorkspaceAccess, get_actor, resolve_access
from ume_app.auth.permissions import Principal, Scope
from ume_app.domain.errors import NotFoundError
from ume_app.models.project import Project
from ume_app.repositories.projects import ProjectRepository
from ume_app.schemas.workspace import ProjectPatch
from ume_app.services import projects as project_service

router = APIRouter()


class ProjectAccess:
    """A project plus the workspace-scoped authorization that was proven for it."""

    def __init__(self, access: WorkspaceAccess, project: Project) -> None:
        self.workspace_access = access
        self.project = project

    @property
    def db(self) -> Session:
        return self.workspace_access.db

    @property
    def principal(self) -> Principal:
        return self.workspace_access.principal

    @property
    def workspace_id(self) -> uuid.UUID:
        return self.workspace_access.workspace_id


def project_access(required_scope: str):
    """Dependency factory returning a `ProjectAccess` bound to the owning workspace."""

    def dependency(
        project_id: uuid.UUID,
        db: Annotated[Session, Depends(get_db)],
        actor: Annotated[Principal, Depends(get_actor)],
    ) -> ProjectAccess:
        workspace_id = ProjectRepository(db).workspace_id_of(project_id)
        if workspace_id is None:
            raise NotFoundError("Project not found.")
        access = resolve_access(db, actor, workspace_id, required_scopes=(required_scope,))
        # Scoped re-read: the object the route touches is proven to belong to
        # the workspace the caller was just authorized against.
        project = ProjectRepository(db).require_in_workspace(workspace_id, project_id)
        return ProjectAccess(access=access, project=project)

    return dependency


@router.get("/projects/{project_id}", summary="Get a project")
def get_project(access: Annotated[ProjectAccess, Depends(project_access(Scope.PROJECT_READ))]):
    return success(dump(access.project))


@router.patch("/projects/{project_id}", summary="Update a project")
def update_project(
    payload: ProjectPatch,
    access: Annotated[ProjectAccess, Depends(project_access(Scope.PROJECT_WRITE))],
):
    return success(dump(project_service.update(access.workspace_access, access.project, payload.changes())))


@router.delete("/projects/{project_id}", summary="Delete a project")
def delete_project(access: Annotated[ProjectAccess, Depends(project_access(Scope.PROJECT_WRITE))]):
    project_id = access.project.id
    workspace_id = access.workspace_id
    project_service.delete(access.workspace_access, access.project)
    return success({"id": str(project_id), "workspace_id": str(workspace_id), "deleted": True})
