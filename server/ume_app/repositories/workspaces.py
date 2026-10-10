"""Workspace and membership persistence."""

import uuid

from ume_app.domain.errors import ConflictError, NotFoundError
from ume_app.models.workspace import Workspace, WorkspaceMember
from ume_app.repositories.base import Page, ScopedRepository, clamp_page_size


class WorkspaceRepository(ScopedRepository[Workspace]):
    model = Workspace

    def get(self, workspace_id: uuid.UUID) -> Workspace | None:
        """Fetch a workspace by id.

        A workspace *is* the scope root, so this lookup is intentionally not
        workspace-filtered; membership must be resolved by the caller before
        the id is treated as authoritative.
        """
        return self.db.get(Workspace, workspace_id)

    def require(self, workspace_id: uuid.UUID) -> Workspace:
        workspace = self.get(workspace_id)
        if workspace is None:
            raise NotFoundError("Workspace not found.")
        return workspace

    def list_for_user(
        self,
        user_id: uuid.UUID,
        *,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> Page[Workspace]:
        """Workspaces the user belongs to, newest first."""
        size = clamp_page_size(limit)
        stmt = (
            self.db.query(Workspace)
            .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
            .filter(WorkspaceMember.user_id == user_id)
            .order_by(Workspace.created_at.desc(), Workspace.id.desc())
        )
        return self._build_page(self.apply_cursor(stmt, cursor), size)


class WorkspaceMemberRepository(ScopedRepository[WorkspaceMember]):
    model = WorkspaceMember

    def membership(self, workspace_id: uuid.UUID, user_id: uuid.UUID) -> WorkspaceMember | None:
        """The member row binding a user to a workspace, or None."""
        return (
            self.db.query(WorkspaceMember)
            .filter(WorkspaceMember.workspace_id == workspace_id, WorkspaceMember.user_id == user_id)
            .one_or_none()
        )

    def list_members(self, workspace_id: uuid.UUID, *, limit: int | None = None, cursor: str | None = None) -> Page:
        size = clamp_page_size(limit)
        stmt = self._scoped(workspace_id).order_by(WorkspaceMember.created_at.desc(), WorkspaceMember.id.desc())
        return self._build_page(self.apply_cursor(stmt, cursor), size)

    def add(self, workspace_id: uuid.UUID, user_id: uuid.UUID, role: str) -> WorkspaceMember:
        if self.membership(workspace_id, user_id) is not None:
            raise ConflictError("User is already a member of this workspace.")
        member = WorkspaceMember(workspace_id=workspace_id, user_id=user_id, role=str(role))
        self.db.add(member)
        self.db.flush()
        return member

    def set_role(self, workspace_id: uuid.UUID, user_id: uuid.UUID, role: str) -> WorkspaceMember:
        member = self.membership(workspace_id, user_id)
        if member is None:
            raise NotFoundError("Workspace member not found.")
        member.role = str(role)
        self.db.flush()
        return member

    def remove(self, workspace_id: uuid.UUID, user_id: uuid.UUID) -> None:
        member = self.membership(workspace_id, user_id)
        if member is None:
            raise NotFoundError("Workspace member not found.")
        self.db.delete(member)
        self.db.flush()