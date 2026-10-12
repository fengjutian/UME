"""Connector routes.

Credential creation is admin-only and returns the plaintext token exactly once.
Everything else a connector does arrives as a `Bearer umec_...` principal rather
than through these routes.
"""

import uuid
from typing import Annotated

from db import get_db
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from ume_app.api.responses import created, page, success
from ume_app.auth.dependencies import get_actor, resolve_access
from ume_app.auth.permissions import Principal, Scope
from ume_app.domain.errors import NotFoundError
from ume_app.models.connector import Connector
from ume_app.repositories.base import clamp_page_size
from ume_app.schemas.connector import ConnectorCreate, ConnectorPatch
from ume_app.services import connectors as connector_service

router = APIRouter()

LimitQuery = Annotated[int | None, Query(ge=1, le=200)]
CursorQuery = Annotated[str | None, Query()]


def _load(db: Session, connector_id: uuid.UUID) -> Connector:
    """Load a connector by id without a workspace, for resolution only.

    The workspace is then taken from the row itself and the caller's membership
    in *that* workspace is what authorises the read — the same order used for
    conversations, projects and import jobs.
    """
    connector = db.query(Connector).filter(Connector.id == connector_id).one_or_none()
    if connector is None:
        raise NotFoundError("Connector not found.")
    return connector


@router.get("/connectors", summary="List connectors")
def list_connectors(
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[Principal, Depends(get_actor)],
    workspace_id: Annotated[uuid.UUID, Query()],
    include_revoked: bool = False,
    limit: LimitQuery = None,
    cursor: CursorQuery = None,
):
    access = resolve_access(db, actor, workspace_id, required_scopes=(Scope.WORKSPACE_MANAGE,))
    result = connector_service.list_for_workspace(
        access,
        limit=clamp_page_size(limit),
        cursor=cursor,
        include_revoked=include_revoked,
    )
    return page([item.as_dict() for item in result.items], result.next_cursor, result.has_more)


@router.post("/connectors", status_code=status.HTTP_201_CREATED, summary="Create a connector credential")
def create_connector(
    payload: ConnectorCreate,
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[Principal, Depends(get_actor)],
):
    access = resolve_access(db, actor, payload.workspace_id, required_scopes=(Scope.CONNECTOR_MANAGE,))
    connector, plaintext = connector_service.create(
        access,
        name=payload.name,
        connector_type=payload.connector_type,
        scopes=payload.scopes,
        project_id=payload.project_id,
        client_instance_id=payload.client_instance_id,
        capabilities=payload.capabilities,
    )
    # The only moment the plaintext exists outside the caller's memory.
    return created({**connector.as_dict(), "credential": plaintext})


@router.get("/connectors/{connector_id}", summary="Get a connector")
def get_connector(
    connector_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[Principal, Depends(get_actor)],
):
    connector = _load(db, connector_id)
    resolve_access(db, actor, connector.workspace_id, required_scopes=(Scope.WORKSPACE_MANAGE,))
    return success(connector.as_dict())


@router.patch("/connectors/{connector_id}", summary="Update a connector")
def update_connector(
    payload: ConnectorPatch,
    connector_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[Principal, Depends(get_actor)],
):
    connector = _load(db, connector_id)
    access = resolve_access(db, actor, connector.workspace_id, required_scopes=(Scope.CONNECTOR_MANAGE,))
    updated = connector_service.update(
        access,
        connector,
        name=payload.name,
        scopes=payload.scopes,
        capabilities=payload.capabilities,
    )
    return success(updated.as_dict())


@router.post("/connectors/{connector_id}/revoke", summary="Revoke a connector credential")
def revoke_connector(
    connector_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[Principal, Depends(get_actor)],
):
    connector = _load(db, connector_id)
    access = resolve_access(db, actor, connector.workspace_id, required_scopes=(Scope.CONNECTOR_MANAGE,))
    return success(connector_service.revoke(access, connector).as_dict())
