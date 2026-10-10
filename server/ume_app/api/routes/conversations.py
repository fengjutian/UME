"""Conversation, message and import routes.

The workspace comes from a required query parameter on the collection routes
(section 9.3 defines no workspace path segment for them) and is verified against
the caller's membership before any query runs.
"""

import uuid
from typing import Annotated

from db import get_db
from fastapi import APIRouter, Depends, Header, Query, status
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
from ume_app.models.conversation import Conversation
from ume_app.repositories.base import clamp_page_size
from ume_app.repositories.conversations import ConversationRepository
from ume_app.repositories.imports import ImportJobRepository
from ume_app.schemas.conversation import (
    ConversationCreate,
    ConversationImport,
    ConversationPatch,
    ImportPreviewOut,
    MessagesAppend,
)
from ume_app.services import conversations as conversation_service
from ume_app.services import imports as import_service
from ume_app.services.audit import record

router = APIRouter()

LimitQuery = Annotated[int | None, Query(ge=1, le=200)]
CursorQuery = Annotated[str | None, Query()]


def conversation_access(required_scope: str):
    """Resolve the owning workspace from a conversation id, then re-check scope."""

    def dependency(
        conversation_id: uuid.UUID,
        db: Annotated[Session, Depends(get_db)],
        actor: Annotated[Principal, Depends(get_actor)],
    ) -> ConversationAccess:
        workspace_id = ConversationRepository(db).workspace_id_of(conversation_id)
        if workspace_id is None:
            raise NotFoundError("Conversation not found.")
        access = resolve_access(db, actor, workspace_id, required_scopes=(required_scope,))
        conversation = ConversationRepository(db).require_in_workspace(workspace_id, conversation_id)
        return ConversationAccess(access=access, conversation=conversation)

    return dependency


class ConversationAccess:
    def __init__(self, access: WorkspaceAccess, conversation: Conversation) -> None:
        self.workspace_access = access
        self.conversation = conversation

    @property
    def db(self) -> Session:
        return self.workspace_access.db

    @property
    def workspace_id(self) -> uuid.UUID:
        return self.workspace_access.workspace_id


# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------


@router.get("/conversations", summary="List conversations")
def list_conversations(
    access: Annotated[WorkspaceAccess, Depends(workspace_query_access(Scope.CONVERSATION_READ))],
    limit: LimitQuery = None,
    cursor: CursorQuery = None,
    project_id: Annotated[uuid.UUID | None, Query()] = None,
    conversation_status: Annotated[str | None, Query(alias="status", max_length=32)] = None,
):
    result = conversation_service.list_for_workspace(
        access, limit=clamp_page_size(limit), cursor=cursor, project_id=project_id, status=conversation_status
    )
    return page([dump(item) for item in result.items], result.next_cursor, result.has_more)


@router.post("/conversations", status_code=status.HTTP_201_CREATED, summary="Create a conversation")
def create_conversation(
    payload: ConversationCreate,
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[Principal, Depends(get_actor)],
):
    if payload.workspace_id is None:
        # Defensive: the schema makes this required, so this only fires if the
        # schema and this signature ever drift apart.
        raise NotFoundError("Conversation not found.")
    access = resolve_access(db, actor, payload.workspace_id, required_scopes=(Scope.CONVERSATION_WRITE,))
    return created(dump(conversation_service.create(access, payload.model_dump())))


@router.get("/conversations/{conversation_id}", summary="Get a conversation")
def get_conversation(
    access: Annotated[ConversationAccess, Depends(conversation_access(Scope.CONVERSATION_READ))],
):
    return success(dump(access.conversation))


@router.patch("/conversations/{conversation_id}", summary="Update a conversation")
def update_conversation(
    payload: ConversationPatch,
    access: Annotated[ConversationAccess, Depends(conversation_access(Scope.CONVERSATION_WRITE))],
):
    return success(dump(conversation_service.update(access.workspace_access, access.conversation, payload.changes())))


@router.delete("/conversations/{conversation_id}", summary="Delete a conversation")
def delete_conversation(
    access: Annotated[ConversationAccess, Depends(conversation_access(Scope.CONVERSATION_WRITE))],
):
    conversation_id = access.conversation.id
    conversation_service.delete(access.workspace_access, access.conversation)
    return success({"id": str(conversation_id), "deleted": True})


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------


@router.get("/conversations/{conversation_id}/messages", summary="List messages")
def list_messages(
    access: Annotated[ConversationAccess, Depends(conversation_access(Scope.CONVERSATION_READ))],
    limit: LimitQuery = None,
    cursor: CursorQuery = None,
    order: Annotated[str, Query(pattern="^(asc|desc)$")] = "asc",
):
    result = conversation_service.list_messages(
        access.workspace_access, access.conversation, limit=clamp_page_size(limit), cursor=cursor, order=order
    )
    return page([dump(item) for item in result.items], result.next_cursor, result.has_more)


@router.post(
    "/conversations/{conversation_id}/messages",
    status_code=status.HTTP_201_CREATED,
    summary="Append messages",
)
def append_messages(
    payload: MessagesAppend,
    access: Annotated[ConversationAccess, Depends(conversation_access(Scope.CONVERSATION_WRITE))],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key", max_length=255)] = None,
):
    """Append a batch.

    Honours `Idempotency-Key` (section 9.4): a replay with the same body returns
    the original counts without writing twice.
    """
    workspace = access.workspace_access
    messages = [item.model_dump() for item in payload.messages]

    if idempotency_key:
        from ume_app.repositories.imports import IdempotencyKeyRepository
        from ume_app.services.hashing import request_hash

        keys = IdempotencyKeyRepository(workspace.db)
        digest = request_hash({"conversation_id": str(access.conversation.id), "messages": messages})
        existing = keys.find(
            workspace.workspace_id, str(workspace.principal.actor_type), workspace.principal.actor_id, idempotency_key
        )
        if existing is not None:
            if existing.request_hash != digest:
                from ume_app.domain.errors import ConflictError

                raise ConflictError(
                    "Idempotency-Key was already used with a different request body.",
                    details={"idempotency_key": idempotency_key},
                )
            return created({"conversation_id": str(access.conversation.id), **existing.response_summary})
        inserted, skipped = _append_and_record(workspace, access.conversation, messages, keys, idempotency_key, digest)
        return created({"conversation_id": str(access.conversation.id), "inserted": inserted, "skipped": skipped})

    inserted, skipped = conversation_service.append_messages(workspace, access.conversation, messages)
    workspace.db.commit()
    record(
        workspace.db,
        workspace.principal,
        action="conversation.messages.append",
        resource_type="conversation",
        resource_id=access.conversation.id,
        workspace_id=workspace.workspace_id,
        details={"inserted": inserted, "skipped": skipped},
    )
    workspace.db.commit()
    return created({"conversation_id": str(access.conversation.id), "inserted": inserted, "skipped": skipped})


def _append_and_record(workspace, conversation, messages, keys, key: str, digest: str):
    inserted, skipped = conversation_service.append_messages(workspace, conversation, messages)
    keys.create(
        workspace.workspace_id,
        str(workspace.principal.actor_type),
        workspace.principal.actor_id,
        key,
        digest,
        {"inserted": inserted, "skipped": skipped},
    )
    workspace.db.commit()
    return inserted, skipped


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------


@router.post("/conversations/imports/preview", summary="Preview a conversation import")
def preview_import(
    payload: ConversationImport,
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[Principal, Depends(get_actor)],
):
    access = resolve_access(db, actor, payload.workspace_id, required_scopes=(Scope.CONVERSATION_WRITE,))
    preview = import_service.preview(access, payload.model_dump())
    return success(ImportPreviewOut(**preview).model_dump(mode="json"))


@router.post(
    "/conversations/imports",
    status_code=status.HTTP_201_CREATED,
    summary="Import a conversation",
)
def run_import(
    payload: ConversationImport,
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[Principal, Depends(get_actor)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)],
):
    """Import a conversation.

    `Idempotency-Key` is required, not derived from the body. An auto-derived
    key would make "import the same payload again" a replay forever, which
    would silently hide the section 10.3 dedup path that a connector retry
    actually exercises.
    """
    access = resolve_access(db, actor, payload.workspace_id, required_scopes=(Scope.CONVERSATION_WRITE,))
    job, replayed = import_service.run_import(access, payload.model_dump(), idempotency_key=idempotency_key)
    return created({**dump(job), "replayed": replayed})


# ---------------------------------------------------------------------------
# Import jobs
# ---------------------------------------------------------------------------


@router.get("/import-jobs/{job_id}", summary="Get an import job")
def get_import_job(
    job_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[Principal, Depends(get_actor)],
):
    workspace_id = ImportJobRepository(db).workspace_id_of(job_id)
    if workspace_id is None:
        raise NotFoundError("Import job not found.")
    resolve_access(db, actor, workspace_id, required_scopes=(Scope.CONVERSATION_READ,))
    return success(dump(ImportJobRepository(db).require_in_workspace(workspace_id, job_id)))


@router.post("/import-jobs/{job_id}/retry", summary="Retry a failed import job")
def retry_import_job(
    job_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[Principal, Depends(get_actor)],
):
    workspace_id = ImportJobRepository(db).workspace_id_of(job_id)
    if workspace_id is None:
        raise NotFoundError("Import job not found.")
    access = resolve_access(db, actor, workspace_id, required_scopes=(Scope.CONVERSATION_WRITE,))
    job = ImportJobRepository(db).require_in_workspace(workspace_id, job_id)
    return success(dump(import_service.retry(access, job)))


__all__ = ["router"]
