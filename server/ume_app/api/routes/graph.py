"""Graph, timeline and context routes."""

import uuid
from typing import Annotated

from db import get_db
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from ume_app.api.responses import created, dump, success
from ume_app.auth.dependencies import (
    WorkspaceAccess,
    get_actor,
    resolve_access,
    workspace_query_access,
)
from ume_app.auth.permissions import Principal, Scope
from ume_app.domain.enums import EdgeStatus, RelationType
from ume_app.schemas.graph import ContextRequest, EdgeCreate, EdgePatch, TimelineQuery
from ume_app.services.graph import (
    MAX_CONTEXT_TOKENS,
    MAX_INITIAL_NODES,
    MAX_NEIGHBORS_PER_NODE,
    GraphService,
    assemble_context,
    timeline,
)

router = APIRouter()

WorkspaceQuery = Annotated[WorkspaceAccess, Depends(workspace_query_access(Scope.GRAPH_READ))]


def node_access(required_scope: str):
    """Resolve the owning workspace from a graph node id.

    Same shape as the memory dependency, but keyed on `node_id` because that is
    the path parameter section 9.3 defines for this route.
    """

    def dependency(
        node_id: uuid.UUID,
        db: Annotated[Session, Depends(get_db)],
        actor: Annotated[Principal, Depends(get_actor)],
    ) -> WorkspaceAccess:
        from ume_app.domain.errors import NotFoundError
        from ume_app.repositories.memories import MemoryRecordRepository

        workspace_id = MemoryRecordRepository(db).workspace_id_of(node_id)
        if workspace_id is None:
            raise NotFoundError("Memory not found.")
        return resolve_access(db, actor, workspace_id, required_scopes=(required_scope,))

    return dependency


def _graph_payload(page) -> dict:
    return {
        "nodes": [
            {
                "id": str(node.id),
                "text": node.current_text,
                "memory_type": node.memory_type,
                "status": node.status,
                "engine_id": node.engine_memory_id,
                "created_at": node.created_at,
            }
            for node in page.nodes
        ],
        "edges": [edge.as_dict() for edge in page.edges],
        "next_cursor": page.next_cursor,
        "has_more": page.has_more,
    }


@router.get("/graph", summary="Load the initial graph window")
def load_graph(
    access: WorkspaceQuery,
    project_id: Annotated[uuid.UUID | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_INITIAL_NODES)] = MAX_INITIAL_NODES,
):
    """Nodes and edges only — never a message body.

    Section 15.3 caps the first load; the client expands a node's neighbours on
    demand instead of pulling the whole workspace.
    """
    return success(_graph_payload(GraphService(access).window(project_id=project_id, limit=limit)))


@router.get("/graph/nodes/{node_id}/neighbors", summary="Expand one node")
def node_neighbors(
    node_id: uuid.UUID,
    access: Annotated[WorkspaceAccess, Depends(node_access(Scope.GRAPH_READ))],
    limit: Annotated[int, Query(ge=1, le=MAX_NEIGHBORS_PER_NODE)] = MAX_NEIGHBORS_PER_NODE,
):
    """Expand one node.

    The workspace comes from the node itself, so the caller cannot name a
    different one — the same rule as `/memories/{id}`.
    """
    return success(_graph_payload(GraphService(access).neighbors(node_id, limit=limit)))


@router.post("/graph/edges", status_code=201, summary="Create a relation")
def create_edge(
    payload: EdgeCreate,
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[Principal, Depends(get_actor)],
):
    access = resolve_access(db, actor, payload.workspace_id, required_scopes=(Scope.GRAPH_WRITE,))
    edge = GraphService(access).create_edge(
        payload.source_memory_id,
        payload.target_memory_id,
        payload.relation_type,
        evidence_ref=payload.evidence_ref,
    )
    return created(dump(edge))


@router.patch("/graph/edges/{edge_id}", summary="Update a relation")
def update_edge(
    payload: EdgePatch,
    edge_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[Principal, Depends(get_actor)],
):
    workspace_id = _edge_workspace(db, edge_id)
    access = resolve_access(db, actor, workspace_id, required_scopes=(Scope.GRAPH_WRITE,))
    edge = GraphService(access).update_edge(edge_id, status=payload.status, relation_type=payload.relation_type)
    return success(dump(edge))


@router.delete("/graph/edges/{edge_id}", summary="Delete a relation")
def delete_edge(
    edge_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[Principal, Depends(get_actor)],
):
    workspace_id = _edge_workspace(db, edge_id)
    access = resolve_access(db, actor, workspace_id, required_scopes=(Scope.GRAPH_WRITE,))
    GraphService(access).delete_edge(edge_id)
    return success({"id": str(edge_id), "deleted": True})


def _edge_workspace(db: Session, edge_id: uuid.UUID) -> uuid.UUID:
    from sqlalchemy import select
    from ume_app.domain.errors import NotFoundError
    from ume_app.models.graph import MemoryEdge

    workspace_id = db.execute(select(MemoryEdge.workspace_id).where(MemoryEdge.id == edge_id)).scalar_one_or_none()
    if workspace_id is None:
        raise NotFoundError("Edge not found.")
    return workspace_id


@router.get("/timeline", summary="Merged message and memory timeline")
def load_timeline(access: WorkspaceQuery, query: Annotated[TimelineQuery, Query()]):
    return success(
        timeline(
            access,
            limit=query.limit,
            since=query.since,
            until=query.until,
            project_id=query.project_id,
        )
    )


@router.post("/context", summary="Assemble a token-budgeted context")
def build_context(
    payload: ContextRequest,
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[Principal, Depends(get_actor)],
):
    access = resolve_access(db, actor, payload.workspace_id, required_scopes=(Scope.CONTEXT_READ,))
    return success(
        assemble_context(
            access,
            query=payload.query,
            limit=payload.limit,
            token_budget=payload.token_budget or MAX_CONTEXT_TOKENS,
            project_id=payload.project_id,
        )
    )


__all__ = ["EdgeStatus", "RelationType", "router"]
