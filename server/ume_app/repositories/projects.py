"""Project persistence. Every read is workspace-scoped by construction."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select
from ume_app.domain.errors import NotFoundError
from ume_app.models.base import utcnow
from ume_app.models.project import Project
from ume_app.repositories.base import Page, ScopedRepository, clamp_page_size


class ProjectRepository(ScopedRepository[Project]):
    model = Project

    def list_for_workspace(
        self,
        workspace_id: uuid.UUID,
        *,
        status: str | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> Page[Project]:
        """Projects in one workspace. `workspace_id` is required — there is no
        unscoped listing, so a missing filter cannot compile into a wide query."""
        size = clamp_page_size(limit)
        stmt = self.db.query(Project).filter(Project.workspace_id == workspace_id)
        if status is not None:
            stmt = stmt.filter(Project.status == status)
        stmt = stmt.order_by(Project.created_at.desc(), Project.id.desc())
        return self._build_page(self.apply_cursor(stmt, cursor), size)

    def get_in_workspace(self, workspace_id: uuid.UUID, project_id: uuid.UUID) -> Project | None:
        """Fetch a project *through its workspace*.

        This is the only supported project lookup: a bare primary-key fetch
        would let a caller pass another tenant's project id.
        """
        return self.db.execute(
            select(Project).where(Project.workspace_id == workspace_id, Project.id == project_id)
        ).scalar_one_or_none()

    def require_in_workspace(self, workspace_id: uuid.UUID, project_id: uuid.UUID) -> Project:
        project = self.get_in_workspace(workspace_id, project_id)
        if project is None:
            raise NotFoundError("Project not found.")
        return project

    def workspace_id_of(self, project_id: uuid.UUID) -> uuid.UUID | None:
        """Which workspace owns this project id?

        Only used to route `/projects/{id}` requests to the right workspace
        before membership is checked. It returns an id, never a project, so a
        caller still has to go through `require_in_workspace` to read data.
        """
        return self.db.execute(select(Project.workspace_id).where(Project.id == project_id)).scalar_one_or_none()

    def create(self, workspace_id: uuid.UUID, name: str, **fields: Any) -> Project:
        project = Project(workspace_id=workspace_id, name=name, **fields)
        self.db.add(project)
        self.db.flush()
        return project

    def update(self, project: Project, **fields: Any) -> Project:
        for key, value in fields.items():
            if value is not None:
                setattr(project, key, value)
        project.updated_at = utcnow()
        self.db.flush()
        return project

    def touch_activity(self, project: Project, *, when: datetime | None = None) -> Project:
        project.last_activity_at = when or utcnow()
        self.db.flush()
        return project

    def delete(self, project: Project) -> None:
        self.db.delete(project)
        self.db.flush()
