"""Conversation and message use cases."""

import uuid
from typing import Any

from ume_app.auth.dependencies import WorkspaceAccess, require_writable
from ume_app.domain.enums import ConversationStatus
from ume_app.models.base import utcnow
from ume_app.models.conversation import Conversation, Message
from ume_app.repositories.base import Page
from ume_app.repositories.conversations import ConversationRepository, MessageRepository
from ume_app.services.audit import record
from ume_app.services.hashing import content_hash


def list_for_workspace(
    access: WorkspaceAccess,
    *,
    limit: int,
    cursor: str | None,
    project_id: uuid.UUID | None = None,
    status: str | None = None,
) -> Page[Conversation]:
    return ConversationRepository(access.db).list_for_workspace(
        access.workspace_id, limit=limit, cursor=cursor, project_id=project_id, status=status
    )


def create(access: WorkspaceAccess, payload: dict[str, Any]) -> Conversation:
    require_writable(access)
    conversation = ConversationRepository(access.db).create(
        access.workspace_id,
        project_id=payload.get("project_id"),
        title=payload.get("title"),
        source_type=payload.get("source_type") or "generic",
        retention_policy=payload.get("retention_policy") or "retain",
        external_conversation_id=payload.get("external_conversation_id"),
        status=str(ConversationStatus.ACTIVE),
        started_at=payload.get("started_at"),
    )
    record(
        access.db,
        access.principal,
        action="conversation.create",
        resource_type="conversation",
        resource_id=conversation.id,
        workspace_id=access.workspace_id,
        details={"source_type": conversation.source_type},
    )
    access.db.commit()
    access.db.refresh(conversation)
    return conversation


def update(access: WorkspaceAccess, conversation: Conversation, changes: dict[str, Any]) -> Conversation:
    require_writable(access)
    ConversationRepository(access.db).update(conversation, **changes)
    record(
        access.db,
        access.principal,
        action="conversation.update",
        resource_type="conversation",
        resource_id=conversation.id,
        workspace_id=access.workspace_id,
        details={"fields": sorted(changes)},
    )
    access.db.commit()
    access.db.refresh(conversation)
    return conversation


def delete(access: WorkspaceAccess, conversation: Conversation) -> None:
    """Delete a conversation and its messages.

    A hard delete is acceptable only while messages are the leaf data. Once
    memory records point at messages (P2), this has to become the section 11.2
    state machine instead of relying on the cascade.
    """
    require_writable(access)
    workspace_id = access.workspace_id
    conversation_id = conversation.id
    ConversationRepository(access.db).delete(conversation)
    record(
        access.db,
        access.principal,
        action="conversation.delete",
        resource_type="conversation",
        resource_id=conversation_id,
        workspace_id=workspace_id,
        details={},
    )
    access.db.commit()


def list_messages(
    access: WorkspaceAccess,
    conversation: Conversation,
    *,
    limit: int,
    cursor: str | None,
    order: str = "asc",
) -> Page[Message]:
    return MessageRepository(access.db).list_for_conversation(
        access.workspace_id, conversation.id, limit=limit, cursor=cursor, order=order
    )


def append_messages(
    access: WorkspaceAccess,
    conversation: Conversation,
    payloads: list[dict[str, Any]],
    *,
    import_job_id: uuid.UUID | None = None,
) -> tuple[int, int]:
    """Append messages to a conversation.

    Returns `(inserted, skipped)`. Skips are counted rather than raised: a bulk
    write where one row is a duplicate should still land the rest.
    """
    require_writable(access)
    repository = MessageRepository(access.db)
    inserted, skipped = 0, 0

    for payload in payloads:
        message_at = payload.get("timestamp") or utcnow()
        digest = content_hash(payload.get("content"), payload.get("content_ref"))

        external_id = payload.get("external_message_id")
        if external_id is not None and repository.find_by_external(conversation.id, external_id) is not None:
            skipped += 1
            continue
        if external_id is None and repository.find_by_hash(conversation.id, digest, message_at) is not None:
            skipped += 1
            continue

        repository.add(
            conversation.id,
            access.workspace_id,
            external_message_id=external_id,
            role=payload["role"],
            content_text=payload.get("content"),
            content_ref=payload.get("content_ref"),
            content_hash=digest,
            extra_metadata=payload.get("metadata") or {},
            sensitivity=payload.get("sensitivity") or "normal",
            message_at=message_at,
            import_job_id=import_job_id,
        )
        inserted += 1

    if inserted:
        timestamps = [p.get("timestamp") for p in payloads if p.get("timestamp")]
        newest = max(timestamps) if timestamps else utcnow()
        if conversation.last_message_at is None or newest > conversation.last_message_at:
            conversation.last_message_at = newest
        if conversation.started_at is None:
            conversation.started_at = min(timestamps) if timestamps else newest
        conversation.updated_at = utcnow()
        access.db.flush()

    return inserted, skipped
