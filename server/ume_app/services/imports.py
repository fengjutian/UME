"""Conversation import pipeline (section 10).

State machine: `pending -> validating -> importing -> [extracting] -> completed`,
with `validation_failed`, `import_failed` and `extraction_partial` as failures.

The `extracting` stage is only entered when an extractor is bound. P1 ships no
extractor (memory extraction is P2), so a healthy import goes
`pending -> validating -> importing -> completed`. Archiving is never rolled
back by a later stage: section 10.2 forbids discarding messages that were
already written because a downstream step failed.
"""

import uuid
from typing import Any

from ume_app.auth.dependencies import WorkspaceAccess, require_writable
from ume_app.domain.enums import IMPORT_TRANSITIONS, ConversationStatus, ImportJobStatus
from ume_app.domain.errors import ConflictError, ValidationError
from ume_app.models.base import utcnow
from ume_app.models.import_job import ImportJob
from ume_app.repositories.conversations import ConversationRepository
from ume_app.repositories.imports import IdempotencyKeyRepository, ImportJobRepository
from ume_app.services.audit import record
from ume_app.services.conversations import append_messages
from ume_app.services.hashing import content_hash, request_hash

#: Set by P2 when the memory engine adapter lands. `None` means "archive only".
_EXTRACTOR: Any = None


def bind_extractor(extractor) -> None:
    global _EXTRACTOR
    _EXTRACTOR = extractor


def _job_payload(payload: dict[str, Any], messages: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "project_id": payload.get("project_id"),
        "connector_id": payload.get("connector_id"),
        "status": str(ImportJobStatus.PENDING),
        "input_summary": {
            "source": payload.get("source") or "generic",
            "format_version": payload.get("format_version") or "1.0",
            "external_conversation_id": payload.get("external_conversation_id"),
            "message_count": len(messages),
        },
        "result_summary": {},
        "error_summary": {},
        "created_by": None,
    }


def _assert_transition(current: str, target: ImportJobStatus) -> None:
    allowed = IMPORT_TRANSITIONS.get(ImportJobStatus(current), frozenset())
    if target not in allowed:
        raise ConflictError(
            f"Illegal import state transition {current} -> {target}.",
            details={"from": current, "to": str(target), "allowed": sorted(str(item) for item in allowed)},
        )


def _validate(access: WorkspaceAccess, payload: dict[str, Any]) -> None:
    """Reject input that would leave the archive half-written.

    Everything here is checkable without touching the database, which is what
    makes `imports/preview` able to reuse it.
    """
    if payload.get("project_id") is not None and not _project_in_workspace(access, payload["project_id"]):
        raise ValidationError("project_id does not belong to this workspace.")

    seen_external: set[str] = set()
    for index, message in enumerate(payload["messages"]):
        external_id = message.get("external_message_id")
        if external_id is None:
            continue
        if external_id in seen_external:
            raise ValidationError(
                "Duplicate external_message_id inside one import payload.",
                details={"index": index, "external_message_id": external_id},
            )
        seen_external.add(external_id)


def _project_in_workspace(access: WorkspaceAccess, project_id: uuid.UUID) -> bool:
    from ume_app.repositories.projects import ProjectRepository

    return ProjectRepository(access.db).get_in_workspace(access.workspace_id, project_id) is not None


def preview(access: WorkspaceAccess, payload: dict[str, Any]) -> dict[str, Any]:
    """Dry run: validate, resolve the conversation, count duplicates.

    Performs no writes, so the caller can show the operator exactly what a real
    import would do before committing to it.
    """
    _validate(access, payload)
    messages = payload["messages"]
    conversation, action = _resolve_conversation(access, payload, create_missing=False)

    duplicates = 0
    for message in messages:
        if _is_duplicate(access, conversation, message):
            duplicates += 1

    timestamps = [m.get("timestamp") for m in messages if m.get("timestamp")]
    return {
        "valid": True,
        "workspace_id": access.workspace_id,
        "conversation_id": conversation.id if conversation else None,
        "conversation_action": action,
        "message_count": len(messages),
        "duplicate_count": duplicates,
        "new_message_count": len(messages) - duplicates,
        "first_message_at": min(timestamps) if timestamps else None,
        "last_message_at": max(timestamps) if timestamps else None,
        "problems": [],
    }


def _resolve_conversation(access: WorkspaceAccess, payload: dict[str, Any], *, create_missing: bool):
    repository = ConversationRepository(access.db)
    external_id = payload.get("external_conversation_id")
    if external_id:
        existing = repository.find_by_external(access.workspace_id, payload.get("connector_id"), external_id)
        if existing is not None:
            return existing, "reused"
        if not create_missing:
            return None, "create"
        return repository.create(
            access.workspace_id,
            external_conversation_id=external_id,
            connector_id=payload.get("connector_id"),
            project_id=payload.get("project_id"),
            title=payload.get("title"),
            source_type=payload.get("source") or "generic",
            retention_policy=payload.get("retention_policy") or "retain",
            status=str(ConversationStatus.ACTIVE),
        ), "created"
    if not create_missing:
        return None, "create"
    return repository.create(
        access.workspace_id,
        project_id=payload.get("project_id"),
        title=payload.get("title"),
        source_type=payload.get("source") or "generic",
        retention_policy=payload.get("retention_policy") or "retain",
        status=str(ConversationStatus.ACTIVE),
    ), "created"


def _is_duplicate(access: WorkspaceAccess, conversation, message: dict[str, Any]) -> bool:
    """Section 10.3 dedup priority: external id first, then content hash.

    Without a conversation yet there is nothing to compare against, so a
    preview reports zero duplicates for a conversation it would create.
    """
    if conversation is None:
        return False
    from ume_app.repositories.conversations import MessageRepository

    repository = MessageRepository(access.db)
    external_id = message.get("external_message_id")
    if external_id is not None:
        return repository.find_by_external(conversation.id, external_id) is not None
    timestamp = message.get("timestamp") or utcnow()
    digest = content_hash(message.get("content"), message.get("content_ref"))
    return repository.find_by_hash(conversation.id, digest, timestamp) is not None


def run_import(
    access: WorkspaceAccess,
    payload: dict[str, Any],
    *,
    idempotency_key: str,
) -> tuple[ImportJob, bool]:
    """Execute an import. Returns `(job, replayed)`.

    `replayed=True` means the idempotency key had already been used with an
    identical body and the original job is returned untouched.
    """
    require_writable(access)
    messages = payload["messages"]
    digest = request_hash({"payload": payload, "workspace_id": str(access.workspace_id)})

    keys = IdempotencyKeyRepository(access.db)
    existing = keys.find(
        access.workspace_id, str(access.principal.actor_type), access.principal.actor_id, idempotency_key
    )
    if existing is not None:
        if existing.request_hash != digest:
            raise ConflictError(
                "Idempotency-Key was already used with a different request body.",
                details={"idempotency_key": idempotency_key},
            )
        job = ImportJobRepository(access.db).find_by_idempotency_key(access.workspace_id, idempotency_key)
        if job is not None:
            return job, True

    repository = ImportJobRepository(access.db)
    job_fields = _job_payload(payload, messages)
    job_fields["idempotency_key"] = idempotency_key
    job_fields["created_by"] = access.principal.actor_id
    job = repository.create(access.workspace_id, **job_fields)

    keys.create(
        access.workspace_id,
        str(access.principal.actor_type),
        access.principal.actor_id,
        idempotency_key,
        digest,
        {"import_job_id": str(job.id), "status": job.status},
    )

    _assert_transition(job.status, ImportJobStatus.VALIDATING)
    repository.transition(job, ImportJobStatus.VALIDATING, started_at=utcnow())
    try:
        _validate(access, payload)
    except ValidationError as exc:
        repository.transition(job, ImportJobStatus.VALIDATION_FAILED, completed_at=utcnow())
        repository.record_error(job, {"code": "VALIDATION_FAILED", "message": exc.message, "details": exc.details})
        access.db.commit()
        return job, False

    _assert_transition(job.status, ImportJobStatus.IMPORTING)
    repository.transition(job, ImportJobStatus.IMPORTING)
    try:
        conversation, action = _resolve_conversation(access, payload, create_missing=True)
        inserted, skipped = append_messages(access, conversation, messages, import_job_id=job.id)
    except Exception as exc:  # noqa: BLE001 - the summary is what callers read
        access.db.rollback()
        job = repository.get_in_workspace(access.workspace_id, job.id)
        _assert_transition(job.status, ImportJobStatus.IMPORT_FAILED)
        repository.transition(job, ImportJobStatus.IMPORT_FAILED, completed_at=utcnow())
        repository.record_error(job, {"code": "IMPORT_FAILED", "error_type": type(exc).__name__})
        access.db.commit()
        return job, False

    summary = {
        "conversation_id": str(conversation.id),
        "conversation_action": action,
        "inserted": inserted,
        "skipped_duplicates": skipped,
        "message_count": len(messages),
    }

    if _EXTRACTOR is None:
        _assert_transition(job.status, ImportJobStatus.COMPLETED)
        repository.transition(job, ImportJobStatus.COMPLETED, completed_at=utcnow())
        repository.record_result(job, summary)
        access.db.commit()
        access.db.refresh(job)
        return job, False

    _assert_transition(job.status, ImportJobStatus.EXTRACTING)
    repository.transition(job, ImportJobStatus.EXTRACTING)
    try:
        extracted, extraction_errors = _EXTRACTOR(conversation, messages)
    except Exception as exc:  # noqa: BLE001 - archived messages must survive
        access.db.rollback()
        job = repository.get_in_workspace(access.workspace_id, job.id)
        _assert_transition(job.status, ImportJobStatus.EXTRACTION_PARTIAL)
        repository.transition(job, ImportJobStatus.EXTRACTION_PARTIAL, completed_at=utcnow())
        repository.record_error(job, {"code": "EXTRACTION_PARTIAL", "error_type": type(exc).__name__})
        repository.record_result(job, summary)
        access.db.commit()
        return job, False

    summary.update({"extracted": extracted, "extraction_errors": len(extraction_errors)})
    if extraction_errors:
        _assert_transition(job.status, ImportJobStatus.EXTRACTION_PARTIAL)
        repository.transition(job, ImportJobStatus.EXTRACTION_PARTIAL, completed_at=utcnow())
        repository.record_error(job, {"code": "EXTRACTION_PARTIAL", "count": len(extraction_errors)})
        repository.record_result(job, summary)
    else:
        _assert_transition(job.status, ImportJobStatus.COMPLETED)
        repository.transition(job, ImportJobStatus.COMPLETED, completed_at=utcnow())
        repository.record_result(job, summary)
    access.db.commit()
    access.db.refresh(job)
    return job, False


def retry(access: WorkspaceAccess, job: ImportJob) -> ImportJob:
    """Re-enter a failed job at the stage that failed.

    The archived messages are not re-imported: the retry exists so a failed
    extraction can be re-run, and the dedup rules make a blind re-import a
    no-op anyway.
    """
    require_writable(access)
    repository = ImportJobRepository(access.db)
    failed_status = ImportJobStatus(job.status)

    if failed_status == ImportJobStatus.EXTRACTION_PARTIAL:
        if _EXTRACTOR is None:
            raise ConflictError("No extractor is bound; nothing to retry yet.")
        _assert_transition(job.status, ImportJobStatus.EXTRACTING)
        repository.transition(job, ImportJobStatus.EXTRACTING)
        _assert_transition(job.status, ImportJobStatus.COMPLETED)
        repository.transition(job, ImportJobStatus.COMPLETED, completed_at=utcnow())
        repository.record_error(job, {})
        repository.record_result(job, {**job.result_summary, "retried": True})
        access.db.commit()
        access.db.refresh(job)
        return job

    target = {
        ImportJobStatus.VALIDATION_FAILED: ImportJobStatus.VALIDATING,
        ImportJobStatus.IMPORT_FAILED: ImportJobStatus.IMPORTING,
    }.get(failed_status)
    if target is None:
        raise ConflictError("Only a failed import can be retried.", details={"status": job.status})

    _assert_transition(job.status, target)
    repository.transition(job, target, started_at=utcnow())
    repository.record_error(job, {})
    record(
        access.db,
        access.principal,
        action="import.retry",
        resource_type="import_job",
        resource_id=job.id,
        workspace_id=access.workspace_id,
        details={"from": str(failed_status)},
    )
    access.db.commit()
    access.db.refresh(job)
    return job
