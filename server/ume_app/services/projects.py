"""Project use cases.

Every read goes through `ProjectRepository`, which requires a workspace id, so
a project can never be fetched by bare primary key.
"""

from typing import Any

from ume_app.auth.dependencies import WorkspaceAccess, require_writable
from ume_app.domain.enums import ProjectStatus
from ume_app.models.project import Project
from ume_app.repositories.base import Page
from ume_app.repositories.projects import ProjectRepository
from ume_app.services.audit import record


def list_for_workspace(
    access: WorkspaceAccess,
    *,
    limit: int,
    cursor: str | None,
    status: str | None = None,
) -> Page[Project]:
    return ProjectRepository(access.db).list_for_workspace(
        access.workspace_id, limit=limit, cursor=cursor, status=status
    )


def create(access: WorkspaceAccess, payload: dict[str, Any]) -> Project:
    require_writable(access)
    repository = ProjectRepository(access.db)
    project = repository.create(
        access.workspace_id,
        payload["name"],
        description=payload.get("description"),
        tags=payload.get("tags") or [],
        status=str(ProjectStatus.ACTIVE),
    )
    repository.touch_activity(project)
    record(
        access.db,
        access.principal,
        action="project.create",
        resource_type="project",
        resource_id=project.id,
        workspace_id=access.workspace_id,
        details={"name": project.name},
    )
    access.db.commit()
    access.db.refresh(project)
    return project


def update(access: WorkspaceAccess, project: Project, changes: dict[str, Any]) -> Project:
    require_writable(access)
    repository = ProjectRepository(access.db)
    repository.update(project, **changes)
    record(
        access.db,
        access.principal,
        action="project.update",
        resource_type="project",
        resource_id=project.id,
        workspace_id=access.workspace_id,
        details={"fields": sorted(changes)},
    )
    access.db.commit()
    access.db.refresh(project)
    return project


def delete(access: WorkspaceAccess, project: Project) -> None:
    require_writable(access)
    ProjectRepository(access.db).delete(project)
    record(
        access.db,
        access.principal,
        action="project.delete",
        resource_type="project",
        resource_id=project.id,
        workspace_id=access.workspace_id,
        details={},
    )
    access.db.commit()
