"""Memory use cases and the engine-sync state machine (sections 11 and 5.4).

The business row and the engine write cannot share a transaction, so every
write follows the same recoverable shape:

    1. write the business row with `engine_state = pending`
    2. call the engine
    3. on success set `ready`; on failure set `failed` + a redacted error

A record is never reported as successful when the engine half did not land, and
a failed record stays readable so an operator can retry it.
"""

import uuid
from typing import Any

from ume_app.auth.dependencies import WorkspaceAccess, require_writable
from ume_app.domain.enums import (
    READABLE_MEMORY_STATUSES,
    EngineState,
    MemoryChangeType,
    MemoryStatus,
)
from ume_app.domain.errors import ConflictError, NotFoundError, ValidationError
from ume_app.engine.memory_adapter import EngineScope, get_adapter
from ume_app.models.base import utcnow
from ume_app.models.memory import MemoryRecord
from ume_app.repositories.base import Page
from ume_app.repositories.memories import (
    MemoryProjectLinkRepository,
    MemoryRecordRepository,
    MemorySourceRepository,
    MemoryVersionRepository,
)
from ume_app.repositories.projects import ProjectRepository
from ume_app.services.audit import record

MAX_ERROR_LENGTH = 500


def _redact(error: BaseException) -> str:
    """Keep the exception type, drop the message.

    Provider and driver messages routinely echo back request bodies, and this
    string is shown in the console. The type plus the state is what an operator
    actually acts on.
    """
    return f"{type(error).__name__}"[:MAX_ERROR_LENGTH]


def _scope(access: WorkspaceAccess, memory_record_id: uuid.UUID | None = None) -> EngineScope:
    projects = MemoryProjectLinkRepository(access.db).project_ids_for(memory_record_id) if memory_record_id else []
    return EngineScope(
        workspace_id=access.workspace_id,
        project_ids=tuple(projects),
        memory_record_id=memory_record_id,
    )


def _validate_projects(access: WorkspaceAccess, project_ids: list[uuid.UUID]) -> None:
    if not project_ids:
        return
    repository = ProjectRepository(access.db)
    missing = [pid for pid in project_ids if repository.get_in_workspace(access.workspace_id, pid) is None]
    if missing:
        raise ValidationError(
            "One or more project ids do not belong to this workspace.",
            details={"project_ids": [str(pid) for pid in missing]},
        )


def list_for_workspace(access: WorkspaceAccess, **filters: Any) -> Page[MemoryRecord]:
    return MemoryRecordRepository(access.db).list_for_workspace(access.workspace_id, **filters)


def get(access: WorkspaceAccess, memory_id: uuid.UUID) -> MemoryRecord:
    return MemoryRecordRepository(access.db).require_in_workspace(access.workspace_id, memory_id)


def create(
    access: WorkspaceAccess,
    *,
    messages: list[dict[str, Any]],
    memory_type: str = "semantic",
    tags: list[str] | None = None,
    project_ids: list[uuid.UUID] | None = None,
    sources: list[dict[str, Any]] | None = None,
    infer: bool = True,
) -> MemoryRecord:
    """Write a memory and mirror it into the engine.

    The record is committed in `pending` *before* the engine is called, so a
    crash between the two leaves a retryable row instead of a silent gap.
    """
    require_writable(access)
    if not messages:
        raise ValidationError("At least one message is required.")

    project_ids = project_ids or []
    _validate_projects(access, project_ids)

    engine_metadata = {"tags": tags or []}

    repository = MemoryRecordRepository(access.db)
    record_row = repository.create(
        access.workspace_id,
        engine_memory_id="",
        memory_type=memory_type,
        status=str(MemoryStatus.ACTIVE),
        current_text="",
        tags=tags or [],
        engine_state=str(EngineState.PENDING),
        created_by_type=str(access.principal.actor_type),
        created_by_id=access.principal.actor_id,
    )
    links = MemoryProjectLinkRepository(access.db)
    for project_id in project_ids:
        links.add(record_row.id, project_id)
    access.db.commit()

    try:
        created = get_adapter().add(
            messages, scope=_scope(access, record_row.id), metadata=engine_metadata, infer=infer
        )
    except Exception as exc:  # noqa: BLE001 - redacted and recorded as engine_state
        access.db.rollback()
        failed = repository.require_in_workspace(access.workspace_id, record_row.id)
        repository.set_engine_state(failed, EngineState.FAILED, error=_redact(exc))
        record(
            access.db,
            access.principal,
            action="memory.create",
            resource_type="memory",
            resource_id=record_row.id,
            workspace_id=access.workspace_id,
            details={"result": "engine_failed", "error_type": type(exc).__name__},
        )
        access.db.commit()
        raise

    if not created:
        access.db.rollback()
        pending = repository.require_in_workspace(access.workspace_id, record_row.id)
        repository.set_engine_state(pending, EngineState.FAILED, error="Engine returned no memory")
        access.db.commit()
        raise ConflictError("The memory engine returned no memory for this write.")

    text = created[0].text or "\n".join(str(m.get("content", "")) for m in messages)
    fresh = repository.require_in_workspace(access.workspace_id, record_row.id)
    repository.update(
        fresh,
        engine_memory_id=created[0].id,
        current_text=text,
        engine_state=str(EngineState.READY),
        engine_error=None,
    )
    MemoryVersionRepository(access.db).add(
        fresh.id,
        text,
        change_type=str(MemoryChangeType.CREATED),
        actor_type=str(access.principal.actor_type),
        actor_id=access.principal.actor_id,
    )
    _add_sources(access, fresh, sources or [])
    record(
        access.db,
        access.principal,
        action="memory.create",
        resource_type="memory",
        resource_id=fresh.id,
        workspace_id=access.workspace_id,
        details={"memory_type": memory_type, "projects": len(project_ids)},
    )
    access.db.commit()
    access.db.refresh(fresh)
    return fresh


def _as_uuid(value: Any) -> uuid.UUID | None:
    """Coerce a JSON string to UUID.

    Provenance ids arrive from the request body as strings; handing them straight
    to a UUID column fails at flush time with an opaque driver error.
    """
    if value is None or isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise ValidationError(
            "A source id is not a valid UUID.",
            details={"value": str(value)},
        ) from exc


def _add_sources(access: WorkspaceAccess, memory_row: MemoryRecord, sources: list[dict[str, Any]]) -> None:
    repository = MemorySourceRepository(access.db)
    for source in sources:
        repository.add(
            memory_row.id,
            access.workspace_id,
            conversation_id=_as_uuid(source.get("conversation_id")),
            message_id=_as_uuid(source.get("message_id")),
            source_type=source.get("source_type") or "conversation",
            extraction_method=source.get("extraction_method") or "unknown",
            evidence_excerpt=source.get("evidence_excerpt"),
            confidence=source.get("confidence"),
        )


def update(
    access: WorkspaceAccess,
    memory_row: MemoryRecord,
    *,
    text: str,
    change_reason: str | None = None,
    tags: list[str] | None = None,
) -> MemoryRecord:
    require_writable(access)
    if memory_row.status not in READABLE_MEMORY_STATUSES:
        raise ConflictError(
            f"Memory is {memory_row.status} and cannot be edited.", details={"status": memory_row.status}
        )

    repository = MemoryRecordRepository(access.db)
    try:
        get_adapter().update(
            memory_row.engine_memory_id,
            text,
            scope=_scope(access, memory_row.id),
            metadata={"tags": tags} if tags is not None else None,
        )
    except Exception as exc:  # noqa: BLE001
        access.db.rollback()
        repository.set_engine_state(memory_row, EngineState.FAILED, error=_redact(exc))
        record(
            access.db,
            access.principal,
            action="memory.update",
            resource_type="memory",
            resource_id=memory_row.id,
            workspace_id=access.workspace_id,
            details={"result": "engine_failed", "error_type": type(exc).__name__},
        )
        access.db.commit()
        raise

    repository.update(memory_row, current_text=text, tags=tags, engine_state=str(EngineState.READY), engine_error=None)
    MemoryVersionRepository(access.db).add(
        memory_row.id,
        text,
        change_type=str(MemoryChangeType.UPDATED),
        actor_type=str(access.principal.actor_type),
        actor_id=access.principal.actor_id,
        change_reason=change_reason,
    )
    record(
        access.db,
        access.principal,
        action="memory.update",
        resource_type="memory",
        resource_id=memory_row.id,
        workspace_id=access.workspace_id,
        details={},
    )
    access.db.commit()
    access.db.refresh(memory_row)
    return memory_row


def archive(access: WorkspaceAccess, memory_row: MemoryRecord, *, reason: str | None = None) -> MemoryRecord:
    """Archive is a business-only transition: the engine keeps the memory."""
    require_writable(access)
    if memory_row.status != str(MemoryStatus.ACTIVE):
        raise ConflictError("Only an active memory can be archived.", details={"status": memory_row.status})

    MemoryRecordRepository(access.db).update(memory_row, status=str(MemoryStatus.ARCHIVED))
    MemoryVersionRepository(access.db).add(
        memory_row.id,
        memory_row.current_text,
        change_type=str(MemoryChangeType.ARCHIVED),
        actor_type=str(access.principal.actor_type),
        actor_id=access.principal.actor_id,
        change_reason=reason,
    )
    record(
        access.db,
        access.principal,
        action="memory.archive",
        resource_type="memory",
        resource_id=memory_row.id,
        workspace_id=access.workspace_id,
        details={},
    )
    access.db.commit()
    access.db.refresh(memory_row)
    return memory_row


def restore(access: WorkspaceAccess, memory_row: MemoryRecord, *, version_no: int | None = None) -> MemoryRecord:
    """Restore to a prior version, producing a *new* version.

    History is append-only: restoring writes the old text forward as version
    N+1 rather than truncating history, so the restore itself is auditable.
    """
    require_writable(access)
    if memory_row.status != str(MemoryStatus.ARCHIVED):
        raise ConflictError("Only an archived memory can be restored.", details={"status": memory_row.status})

    versions = MemoryVersionRepository(access.db)
    target = versions.get_version(memory_row.id, version_no) if version_no is not None else None
    if target is None:
        raise NotFoundError("Version not found.")
    if target.text == memory_row.current_text:
        raise ConflictError("That version is already the current text.")

    repository = MemoryRecordRepository(access.db)
    try:
        get_adapter().update(memory_row.engine_memory_id, target.text, scope=_scope(access, memory_row.id))
    except Exception as exc:  # noqa: BLE001
        access.db.rollback()
        repository.set_engine_state(memory_row, EngineState.FAILED, error=_redact(exc))
        access.db.commit()
        raise

    repository.update(
        memory_row,
        current_text=target.text,
        status=str(MemoryStatus.ACTIVE),
        engine_state=str(EngineState.READY),
        engine_error=None,
    )
    versions.add(
        memory_row.id,
        target.text,
        change_type=str(MemoryChangeType.RESTORED),
        actor_type=str(access.principal.actor_type),
        actor_id=access.principal.actor_id,
        change_reason=f"restored from version {target.version_no}",
    )
    record(
        access.db,
        access.principal,
        action="memory.restore",
        resource_type="memory",
        resource_id=memory_row.id,
        workspace_id=access.workspace_id,
        details={"from_version": target.version_no},
    )
    access.db.commit()
    access.db.refresh(memory_row)
    return memory_row


def forget(access: WorkspaceAccess, memory_row: MemoryRecord, *, reason: str | None = None) -> MemoryRecord:
    """Delete from the engine, then tombstone the business row (section 11.2).

    Each step is committed separately. A failure between them leaves
    `engine_state = deleting`, which is resumable; nothing here ever reports a
    success that did not happen.
    """
    require_writable(access)
    if memory_row.status == str(MemoryStatus.DELETED):
        raise ConflictError("Memory is already deleted.")

    repository = MemoryRecordRepository(access.db)
    versions = MemoryVersionRepository(access.db)
    sources = MemorySourceRepository(access.db)

    repository.set_engine_state(memory_row, EngineState.DELETING)
    versions.add(
        memory_row.id,
        memory_row.current_text,
        change_type=str(MemoryChangeType.DELETED),
        actor_type=str(access.principal.actor_type),
        actor_id=access.principal.actor_id,
        change_reason=reason,
    )
    access.db.commit()

    try:
        get_adapter().delete(memory_row.engine_memory_id, scope=_scope(access, memory_row.id))
    except Exception as exc:  # noqa: BLE001
        access.db.rollback()
        stuck = repository.require_in_workspace(access.workspace_id, memory_row.id)
        repository.set_engine_state(stuck, EngineState.DELETING, error=_redact(exc))
        record(
            access.db,
            access.principal,
            action="memory.forget",
            resource_type="memory",
            resource_id=memory_row.id,
            workspace_id=access.workspace_id,
            details={"result": "engine_failed", "error_type": type(exc).__name__},
        )
        access.db.commit()
        raise

    # Provenance becomes a tombstone: the pointers are dropped but the rows stay
    # so "which message produced this" is still answerable.
    for source in sources.list_for_record(memory_row.id):
        source.message_id = None
        source.evidence_excerpt = None

    repository.update(
        memory_row,
        status=str(MemoryStatus.DELETED),
        engine_state=str(EngineState.DELETED),
        deleted_at=utcnow(),
    )
    record(
        access.db,
        access.principal,
        action="memory.forget",
        resource_type="memory",
        resource_id=memory_row.id,
        workspace_id=access.workspace_id,
        details={},
    )
    access.db.commit()
    access.db.refresh(memory_row)
    return memory_row


def retry_engine_sync(
    access: WorkspaceAccess, memory_row: MemoryRecord, messages: list[dict[str, Any]]
) -> MemoryRecord:
    """Re-run the engine half of a write that failed.

    Only `failed` records are eligible: retrying a `ready` record would create a
    second engine memory for the same text.
    """
    require_writable(access)
    if EngineState(memory_row.engine_state) != EngineState.FAILED:
        raise ConflictError(
            "Only a failed engine write can be retried.",
            details={"engine_state": memory_row.engine_state},
        )
    repository = MemoryRecordRepository(access.db)
    repository.set_engine_state(memory_row, EngineState.PENDING)
    access.db.commit()

    created = get_adapter().add(messages, scope=_scope(access, memory_row.id), metadata={"tags": memory_row.tags})
    if not created:
        repository.set_engine_state(memory_row, EngineState.FAILED, error="Engine returned no memory")
        access.db.commit()
        raise ConflictError("The memory engine returned no memory for this retry.")

    text = created[0].text or memory_row.current_text
    repository.update(
        memory_row,
        engine_memory_id=created[0].id,
        current_text=text,
        engine_state=str(EngineState.READY),
        engine_error=None,
    )
    MemoryVersionRepository(access.db).add(
        memory_row.id,
        text,
        change_type=str(MemoryChangeType.UPDATED),
        actor_type=str(access.principal.actor_type),
        actor_id=access.principal.actor_id,
        change_reason="engine sync retry",
    )
    record(
        access.db,
        access.principal,
        action="memory.retry",
        resource_type="memory",
        resource_id=memory_row.id,
        workspace_id=access.workspace_id,
        details={},
    )
    access.db.commit()
    access.db.refresh(memory_row)
    return memory_row


def list_sources(access: WorkspaceAccess, memory_row: MemoryRecord) -> list[Any]:
    return MemorySourceRepository(access.db).list_for_record(memory_row.id)


def list_versions(access: WorkspaceAccess, memory_row: MemoryRecord, *, limit: int = 50) -> list[Any]:
    return MemoryVersionRepository(access.db).list_for_record(memory_row.id, limit=limit)


def search(access: WorkspaceAccess, *, query: str, limit: int = 10, project_id: uuid.UUID | None = None) -> list[Any]:
    """Semantic search, workspace-filtered *inside* the engine call.

    Section 8 requires the filter to travel with the query; post-filtering the
    results would let another tenant's candidates influence the ranking. The
    caller-facing list is then re-checked against the business table so a record
    deleted since indexing cannot leak.
    """
    scope = EngineScope(
        workspace_id=access.workspace_id,
        project_ids=(project_id,) if project_id else (),
    )
    hits = get_adapter().search(query, scope=scope, limit=limit)

    repository = MemoryRecordRepository(access.db)
    results = []
    for hit in hits:
        if not hit.id:
            continue
        row = repository.find_by_engine_id(access.workspace_id, hit.id)
        if row is None or row.status not in READABLE_MEMORY_STATUSES:
            continue
        results.append((row, hit))
        if len(results) >= limit:
            break
    return results


def projection_drift(access: WorkspaceAccess, memory_row: MemoryRecord) -> bool:
    """True when the engine text and `current_text` disagree.

    The two are written by different transactions, so drift is expected after a
    partial failure; this is the predicate the repair task will use.
    """
    if memory_row.engine_state != str(EngineState.READY):
        return False
    try:
        engine_text = get_adapter().get(memory_row.engine_memory_id, scope=_scope(access, memory_row.id)).text
    except Exception:  # noqa: BLE001 - an unreadable engine side is drift, not a crash
        return True
    return (engine_text or "").strip() != (memory_row.current_text or "").strip()
