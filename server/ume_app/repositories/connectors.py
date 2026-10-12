"""Connector persistence."""

import uuid

from sqlalchemy import select
from ume_app.domain.errors import NotFoundError
from ume_app.models.connector import Connector
from ume_app.repositories.base import ScopedRepository


class ConnectorRepository(ScopedRepository[Connector]):
    model = Connector

    def list_for_workspace(
        self,
        workspace_id: uuid.UUID,
        *,
        include_revoked: bool = False,
        limit: int | None = None,
        cursor: str | None = None,
    ):
        stmt = self.db.query(Connector).filter(Connector.workspace_id == workspace_id)
        if not include_revoked:
            stmt = stmt.filter(Connector.revoked_at.is_(None))
        stmt = stmt.order_by(Connector.created_at.desc(), Connector.id.desc())
        return self._build_page(self.apply_cursor(stmt, cursor), self._size(limit))

    def get_in_workspace(self, workspace_id: uuid.UUID, connector_id: uuid.UUID) -> Connector | None:
        return self.db.execute(
            select(Connector).where(Connector.workspace_id == workspace_id, Connector.id == connector_id)
        ).scalar_one_or_none()

    def require_in_workspace(self, workspace_id: uuid.UUID, connector_id: uuid.UUID) -> Connector:
        connector = self.get_in_workspace(workspace_id, connector_id)
        if connector is None:
            raise NotFoundError("Connector not found.")
        return connector

    def find_by_prefix(self, prefix: str) -> list[Connector]:
        """Every connector whose stored prefix matches, revoked ones included.

        Revocation is enforced during credential verification, not here: a
        revoked connector must still be *findable* so it can be told apart from
        a token that never existed.
        """
        return list(self.db.query(Connector).filter(Connector.credential_prefix == prefix).all())

    @staticmethod
    def _size(limit: int | None) -> int:
        from ume_app.repositories.base import clamp_page_size

        return clamp_page_size(limit)
