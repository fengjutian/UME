"""Import job and idempotency-key persistence."""

import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import delete, select
from ume_app.domain.enums import ImportJobStatus
from ume_app.domain.errors import NotFoundError
from ume_app.models.base import utcnow
from ume_app.models.import_job import IdempotencyKey, ImportJob
from ume_app.repositories.base import ScopedRepository

IDEMPOTENCY_TTL = timedelta(hours=24)


class ImportJobRepository(ScopedRepository[ImportJob]):
    model = ImportJob

    def get_in_workspace(self, workspace_id: uuid.UUID, job_id: uuid.UUID) -> ImportJob | None:
        return self.db.execute(
            select(ImportJob).where(ImportJob.workspace_id == workspace_id, ImportJob.id == job_id)
        ).scalar_one_or_none()

    def require_in_workspace(self, workspace_id: uuid.UUID, job_id: uuid.UUID) -> ImportJob:
        job = self.get_in_workspace(workspace_id, job_id)
        if job is None:
            raise NotFoundError("Import job not found.")
        return job

    def find_by_idempotency_key(self, workspace_id: uuid.UUID, key: str) -> ImportJob | None:
        return self.db.execute(
            select(ImportJob).where(ImportJob.workspace_id == workspace_id, ImportJob.idempotency_key == key)
        ).scalar_one_or_none()

    def workspace_id_of(self, job_id: uuid.UUID) -> uuid.UUID | None:
        return self.db.execute(select(ImportJob.workspace_id).where(ImportJob.id == job_id)).scalar_one_or_none()

    def create(self, workspace_id: uuid.UUID, **fields: Any) -> ImportJob:
        job = ImportJob(workspace_id=workspace_id, **fields)
        self.db.add(job)
        self.db.flush()
        return job

    def transition(
        self,
        job: ImportJob,
        status: ImportJobStatus,
        *,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
    ) -> ImportJob:
        """Move the job to `status` without validating the transition.

        The legal-transition table lives in `domain.enums` and is enforced by
        the import service, which is the only caller that knows the stage
        sequence. Keeping the check out of the repository means a future
        out-of-band status fix can still write a terminal state.
        """
        job.status = str(status)
        if started_at is not None:
            job.started_at = started_at
        if completed_at is not None:
            job.completed_at = completed_at
        self.db.flush()
        return job

    def record_result(self, job: ImportJob, summary: dict[str, Any]) -> ImportJob:
        job.result_summary = summary
        self.db.flush()
        return job

    def record_error(self, job: ImportJob, summary: dict[str, Any]) -> ImportJob:
        job.error_summary = summary
        self.db.flush()
        return job


class IdempotencyKeyRepository(ScopedRepository[IdempotencyKey]):
    model = IdempotencyKey

    def find(
        self,
        workspace_id: uuid.UUID,
        actor_type: str,
        actor_id: uuid.UUID | None,
        key: str,
    ) -> IdempotencyKey | None:
        """Look up a replay record, ignoring expired ones.

        An expired key is treated as absent so the caller may reuse it; the
        stale row is left for `prune` rather than deleted here, because the
        lookup must not mutate.
        """
        record = self.db.execute(
            select(IdempotencyKey).where(
                IdempotencyKey.workspace_id == workspace_id,
                IdempotencyKey.actor_type == actor_type,
                IdempotencyKey.actor_id == actor_id if actor_id is not None else IdempotencyKey.actor_id.is_(None),
                IdempotencyKey.idempotency_key == key,
            )
        ).scalar_one_or_none()
        if record is not None and record.expires_at <= utcnow():
            return None
        return record

    def create(
        self,
        workspace_id: uuid.UUID,
        actor_type: str,
        actor_id: uuid.UUID | None,
        key: str,
        request_hash: str,
        response_summary: dict[str, Any],
        *,
        ttl: timedelta = IDEMPOTENCY_TTL,
    ) -> IdempotencyKey:
        record = IdempotencyKey(
            workspace_id=workspace_id,
            actor_type=actor_type,
            actor_id=actor_id,
            idempotency_key=key,
            request_hash=request_hash,
            response_summary=response_summary,
            expires_at=utcnow() + ttl,
        )
        self.db.add(record)
        self.db.flush()
        return record

    def prune(self, *, now: datetime | None = None) -> int:
        result = self.db.execute(delete(IdempotencyKey).where(IdempotencyKey.expires_at <= (now or utcnow())))
        return result.rowcount or 0
