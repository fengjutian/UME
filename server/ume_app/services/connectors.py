"""Connector use cases."""

import uuid
from typing import Any

from ume_app.auth.credentials import issue, normalise_scopes, touch
from ume_app.auth.dependencies import WorkspaceAccess, require_at_least
from ume_app.domain.enums import ConnectorStatus, WorkspaceRole
from ume_app.domain.errors import ConflictError, NotFoundError
from ume_app.models.base import utcnow
from ume_app.models.connector import Connector
from ume_app.repositories.base import Page
from ume_app.repositories.connectors import ConnectorRepository
from ume_app.repositories.projects import ProjectRepository
from ume_app.services.audit import record


def list_for_workspace(
    access: WorkspaceAccess,
    *,
    limit: int,
    cursor: str | None,
    include_revoked: bool = False,
) -> Page[Connector]:
    """Paged connector list.

    `include_revoked` filters in SQL: filtering after the page was taken would
    shrink a page without reporting it as truncated, so the caller would see a
    short page with `has_more` false and wrongly conclude the list was complete.
    """
    return ConnectorRepository(access.db).list_for_workspace(
        access.workspace_id, limit=limit, cursor=cursor, include_revoked=include_revoked
    )


def create(
    access: WorkspaceAccess,
    *,
    name: str,
    connector_type: str,
    scopes: list[str] | None,
    project_id: uuid.UUID | None,
    client_instance_id: str | None,
    capabilities: dict[str, Any] | None,
) -> tuple[Connector, str]:
    """Create a connector and return it with its one-time plaintext token."""
    require_at_least(access, WorkspaceRole.ADMIN)
    if (
        project_id is not None
        and ProjectRepository(access.db).get_in_workspace(access.workspace_id, project_id) is None
    ):
        raise NotFoundError("Project not found.")

    resolved_scopes = normalise_scopes(scopes)
    connector = Connector(
        workspace_id=access.workspace_id,
        project_id=project_id,
        name=name,
        connector_type=connector_type,
        client_instance_id=client_instance_id,
        capabilities=capabilities or {},
        status=str(ConnectorStatus.ACTIVE),
        created_by=access.principal.actor_id,
    )
    plaintext = issue(connector, scopes=resolved_scopes)
    access.db.add(connector)
    access.db.flush()
    record(
        access.db,
        access.principal,
        action="connector.create",
        resource_type="connector",
        resource_id=connector.id,
        workspace_id=access.workspace_id,
        details={"connector_type": connector_type, "scope_count": len(resolved_scopes)},
    )
    access.db.commit()
    access.db.refresh(connector)
    return connector, plaintext


def get(access: WorkspaceAccess, connector_id: uuid.UUID) -> Connector:
    return ConnectorRepository(access.db).require_in_workspace(access.workspace_id, connector_id)


def update(
    access: WorkspaceAccess,
    connector: Connector,
    *,
    name: str | None = None,
    scopes: list[str] | None = None,
    capabilities: dict[str, Any] | None = None,
) -> Connector:
    """Update connector metadata.

    Scopes can be narrowed but not widened: a caller who can create a connector
    could otherwise mint one with any scope it liked by editing in two steps.
    """
    require_at_least(access, WorkspaceRole.ADMIN)
    if connector.is_revoked:
        raise ConflictError("A revoked connector cannot be updated.", details={"status": connector.status})

    if name is not None:
        connector.name = name
    if capabilities is not None:
        connector.capabilities = capabilities
    if scopes is not None:
        requested = normalise_scopes(scopes)
        if not set(requested) <= set(connector.scopes or ()):
            raise ConflictError(
                "Connector scopes can only be narrowed.",
                details={"current": sorted(connector.scopes or ()), "requested": requested},
            )
        connector.scopes = requested

    connector.updated_at = utcnow()
    record(
        access.db,
        access.principal,
        action="connector.update",
        resource_type="connector",
        resource_id=connector.id,
        workspace_id=access.workspace_id,
        details={"fields": sorted(f for f in ("name", "scopes", "capabilities") if f in locals())},
    )
    access.db.commit()
    access.db.refresh(connector)
    return connector


def revoke(access: WorkspaceAccess, connector: Connector) -> Connector:
    """Revoke immediately. There is no grace period on purpose."""
    require_at_least(access, WorkspaceRole.ADMIN)
    if connector.is_revoked:
        raise ConflictError("Connector is already revoked.")
    connector.revoked_at = utcnow()
    connector.status = str(ConnectorStatus.REVOKED)
    connector.updated_at = utcnow()
    record(
        access.db,
        access.principal,
        action="connector.revoke",
        resource_type="connector",
        resource_id=connector.id,
        workspace_id=access.workspace_id,
        details={},
    )
    access.db.commit()
    access.db.refresh(connector)
    return connector


def mark_used(access: WorkspaceAccess, connector: Connector) -> None:
    """Best-effort activity stamp; never fail a request over telemetry."""
    try:
        touch(connector)
        access.db.commit()
    except Exception:  # pragma: no cover - bookkeeping must not break a call
        access.db.rollback()
