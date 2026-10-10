"""Memory routes.

The workspace comes from the body for writes and from a required query
parameter for the collection routes, matching section 9.3, and is verified
against the caller's membership before any query runs.
"""

import uuid
from typing import Annotated

from db import get_db
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from ume_app.api.responses import created, dump, page, success
from ume_app.auth.dependencies import (
    WorkspaceAccess,
    get_actor,
    resolve_access,
    workspace_query_access,
)
from ume_app.auth.permissions import Principal, Scope
from ume_app.domain.errors import NotFoundError
from ume_app.repositories.base import clamp_page_size
from ume_app.repositories.memories import MemoryRecordRepository
from ume_app.schemas.memory import (
    MemoryArchive,
    MemoryCreate,
    MemoryForget,
    MemoryPatch,
    MemoryRestore,
    MemoryRetry,
    MemorySearchRequest,
)
from ume_app.services import memories as memory_service

router = APIRouter()

LimitQuery = Annotated[int | None, Query(ge=1, le=200)]
CursorQuery = Annotated[str | None, Query()]


def memory_access(required_scope: str):
    """Resolve the owning workspace from a memory id, then re-check scope."""

    def dependency(
        memory_id: uuid.UUID,
        db: Annotated[Session, Depends(get_db)],
        actor: Annotated[Principal, Depends(get_actor)],
    ) -> WorkspaceAccess:
        workspace_id = MemoryRecordRepository(db).workspace_id_of(memory_id)
        if workspace_id is None:
            raise NotFoundError("Memory not found.")
        access = resolve_access(db, actor, workspace_id, required_scopes=(required_scope,))
        memory_service.get(access, memory_id)
        return access

    return dependency


@router.get("/memories", summary="List memories")
def list_memories(
    access: Annotated[WorkspaceAccess, Depends(workspace_query_access(Scope.MEMORY_READ))],
    limit: LimitQuery = None,
    cursor: CursorQuery = None,
    memory_status: Annotated[str | None, Query(alias="status", max_length=32)] = None,
    memory_type: Annotated[str | None, Query(max_length=64)] = None,
    project_id: Annotated[uuid.UUID | None, Query()] = None,
    include_deleted: bool = False,
):
    result = memory_service.list_for_workspace(
        access,
        limit=clamp_page_size(limit),
        cursor=cursor,
        status=memory_status,
        memory_type=memory_type,
        project_id=project_id,
        include_deleted=include_deleted,
    )
    return page([dump(item) for item in result.items], result.next_cursor, result.has_more)


@router.post("/memories", status_code=status.HTTP_201_CREATED, summary="Create a memory")
def create_memory(
    payload: MemoryCreate,
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[Principal, Depends(get_actor)],
):
    access = resolve_access(db, actor, payload.workspace_id, required_scopes=(Scope.MEMORY_WRITE,))
    memory_row = memory_service.create(
        access,
        messages=[item.model_dump() for item in payload.messages],
        memory_type=payload.memory_type,
        tags=payload.tags,
        project_ids=payload.project_ids,
        sources=payload.sources,
        infer=payload.infer,
    )
    return created(dump(memory_row))


@router.post("/memory-search", summary="Semantic memory search")
def search_memories(
    payload: MemorySearchRequest,
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[Principal, Depends(get_actor)],
):
    access = resolve_access(db, actor, payload.workspace_id, required_scopes=(Scope.MEMORY_READ,))
    hits = memory_service.search(access, query=payload.query, limit=payload.limit, project_id=payload.project_id)
    return success([{"memory": dump(row), "score": hit.score, "engine_id": hit.id} for row, hit in hits])


@router.get("/memories/{memory_id}", summary="Get a memory")
def get_memory(
    access: Annotated[WorkspaceAccess, Depends(memory_access(Scope.MEMORY_READ))],
    memory_id: uuid.UUID,
):
    return success(dump(memory_service.get(access, memory_id)))


@router.patch("/memories/{memory_id}", summary="Update a memory")
def update_memory(
    payload: MemoryPatch,
    access: Annotated[WorkspaceAccess, Depends(memory_access(Scope.MEMORY_WRITE))],
    memory_id: uuid.UUID,
):
    updated = memory_service.update(
        access,
        memory_service.get(access, memory_id),
        text=payload.text,
        change_reason=payload.change_reason,
        tags=payload.tags,
    )
    return success(dump(updated))


@router.post("/memories/{memory_id}/archive", summary="Archive a memory")
def archive_memory(
    payload: MemoryArchive,
    access: Annotated[WorkspaceAccess, Depends(memory_access(Scope.MEMORY_WRITE))],
    memory_id: uuid.UUID,
):
    return success(dump(memory_service.archive(access, memory_service.get(access, memory_id), reason=payload.reason)))


@router.post("/memories/{memory_id}/restore", summary="Restore a memory to a prior version")
def restore_memory(
    payload: MemoryRestore,
    access: Annotated[WorkspaceAccess, Depends(memory_access(Scope.MEMORY_WRITE))],
    memory_id: uuid.UUID,
):
    restored = memory_service.restore(access, memory_service.get(access, memory_id), version_no=payload.version_no)
    return success(dump(restored))


@router.post("/memories/{memory_id}/forget", summary="Delete a memory from the engine and tombstone it")
def forget_memory(
    payload: MemoryForget,
    access: Annotated[WorkspaceAccess, Depends(memory_access(Scope.MEMORY_WRITE))],
    memory_id: uuid.UUID,
):
    forgotten = memory_service.forget(access, memory_service.get(access, memory_id), reason=payload.reason)
    return success(dump(forgotten))


@router.post("/memories/{memory_id}/retry", summary="Retry a failed engine write")
def retry_memory(
    payload: MemoryRetry,
    access: Annotated[WorkspaceAccess, Depends(memory_access(Scope.MEMORY_WRITE))],
    memory_id: uuid.UUID,
):
    retried = memory_service.retry_engine_sync(
        access, memory_service.get(access, memory_id), [item.model_dump() for item in payload.messages]
    )
    return success(dump(retried))


@router.get("/memories/{memory_id}/sources", summary="List a memory's provenance")
def list_sources(
    access: Annotated[WorkspaceAccess, Depends(memory_access(Scope.MEMORY_READ))],
    memory_id: uuid.UUID,
):
    memory_row = memory_service.get(access, memory_id)
    return success([dump(source) for source in memory_service.list_sources(access, memory_row)])


@router.get("/memories/{memory_id}/versions", summary="List a memory's version history")
def list_versions(
    access: Annotated[WorkspaceAccess, Depends(memory_access(Scope.MEMORY_READ))],
    memory_id: uuid.UUID,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
):
    memory_row = memory_service.get(access, memory_id)
    versions = memory_service.list_versions(access, memory_row, limit=limit)
    return success([dump(version) for version in versions])
