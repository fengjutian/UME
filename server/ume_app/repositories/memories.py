"""Memory record, source and version persistence."""

import uuid
from typing import Any

from sqlalchemy import func, select
from ume_app.domain.enums import EngineState, MemoryStatus
from ume_app.domain.errors import ConflictError, NotFoundError
from ume_app.models.base import utcnow
from ume_app.models.memory import (
    MemoryProjectLink,
    MemoryRecord,
    MemorySource,
    MemoryVersion,
)
from ume_app.repositories.base import Page, ScopedRepository, clamp_page_size


class MemoryRecordRepository(ScopedRepository[MemoryRecord]):
    model = MemoryRecord

    def list_for_workspace(
        self,
        workspace_id: uuid.UUID,
        *,
        status: str | None = None,
        memory_type: str | None = None,
        project_id: uuid.UUID | None = None,
        include_deleted: bool = False,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> Page[MemoryRecord]:
        size = clamp_page_size(limit)
        stmt = self.db.query(MemoryRecord).filter(MemoryRecord.workspace_id == workspace_id)
        if not include_deleted:
            stmt = stmt.filter(MemoryRecord.status != str(MemoryStatus.DELETED))
        if status is not None:
            stmt = stmt.filter(MemoryRecord.status == status)
        if memory_type is not None:
            stmt = stmt.filter(MemoryRecord.memory_type == memory_type)
        if project_id is not None:
            # Filtered in the join rather than in Python: a memory linked to
            # two projects must not be duplicated.
            stmt = stmt.join(
                MemoryProjectLink,
                MemoryProjectLink.memory_record_id == MemoryRecord.id,
            ).filter(MemoryProjectLink.project_id == project_id)
        stmt = stmt.order_by(MemoryRecord.created_at.desc(), MemoryRecord.id.desc())
        return self._build_page(self.apply_cursor(stmt, cursor), size)

    def get_in_workspace(self, workspace_id: uuid.UUID, memory_id: uuid.UUID) -> MemoryRecord | None:
        return self.db.execute(
            select(MemoryRecord).where(MemoryRecord.workspace_id == workspace_id, MemoryRecord.id == memory_id)
        ).scalar_one_or_none()

    def require_in_workspace(self, workspace_id: uuid.UUID, memory_id: uuid.UUID) -> MemoryRecord:
        record = self.get_in_workspace(workspace_id, memory_id)
        if record is None:
            raise NotFoundError("Memory not found.")
        return record

    def workspace_id_of(self, memory_id: uuid.UUID) -> uuid.UUID | None:
        return self.db.execute(
            select(MemoryRecord.workspace_id).where(MemoryRecord.id == memory_id)
        ).scalar_one_or_none()

    def find_by_engine_id(self, workspace_id: uuid.UUID, engine_memory_id: str) -> MemoryRecord | None:
        return self.db.execute(
            select(MemoryRecord).where(
                MemoryRecord.workspace_id == workspace_id,
                MemoryRecord.engine_memory_id == engine_memory_id,
            )
        ).scalar_one_or_none()

    def create(self, workspace_id: uuid.UUID, **fields: Any) -> MemoryRecord:
        record = MemoryRecord(workspace_id=workspace_id, **fields)
        self.db.add(record)
        self.db.flush()
        return record

    def update(self, record: MemoryRecord, **fields: Any) -> MemoryRecord:
        for key, value in fields.items():
            if value is not None:
                setattr(record, key, value)
        record.updated_at = utcnow()
        self.db.flush()
        return record

    def set_engine_state(
        self,
        record: MemoryRecord,
        state: EngineState,
        *,
        error: str | None = None,
    ) -> MemoryRecord:
        record.engine_state = str(state)
        record.engine_error = error
        record.updated_at = utcnow()
        self.db.flush()
        return record

    def find_by_engine_state(self, engine_state: EngineState, *, limit: int = 100) -> list[MemoryRecord]:
        """Repair queue: records whose engine half never finished."""
        return list(
            self.db.query(MemoryRecord).filter(MemoryRecord.engine_state == str(engine_state)).limit(limit).all()
        )


class MemoryProjectLinkRepository(ScopedRepository[MemoryProjectLink]):
    model = MemoryProjectLink

    def add(self, memory_record_id: uuid.UUID, project_id: uuid.UUID) -> MemoryProjectLink:
        existing = self.get(memory_record_id, project_id)
        if existing is not None:
            return existing
        link = MemoryProjectLink(memory_record_id=memory_record_id, project_id=project_id)
        self.db.add(link)
        self.db.flush()
        return link

    def get(self, memory_record_id: uuid.UUID, project_id: uuid.UUID) -> MemoryProjectLink | None:
        return self.db.execute(
            select(MemoryProjectLink).where(
                MemoryProjectLink.memory_record_id == memory_record_id,
                MemoryProjectLink.project_id == project_id,
            )
        ).scalar_one_or_none()

    def project_ids_for(self, memory_record_id: uuid.UUID) -> list[uuid.UUID]:
        return [
            row.project_id
            for row in self.db.query(MemoryProjectLink)
            .filter(MemoryProjectLink.memory_record_id == memory_record_id)
            .all()
        ]

    def replace(self, memory_record_id: uuid.UUID, project_ids: list[uuid.UUID]) -> None:
        for link in (
            self.db.query(MemoryProjectLink).filter(MemoryProjectLink.memory_record_id == memory_record_id).all()
        ):
            self.db.delete(link)
        self.db.flush()
        for project_id in project_ids:
            self.add(memory_record_id, project_id)


class MemorySourceRepository(ScopedRepository[MemorySource]):
    model = MemorySource

    def add(self, memory_record_id: uuid.UUID, workspace_id: uuid.UUID, **fields: Any) -> MemorySource:
        source = MemorySource(memory_record_id=memory_record_id, workspace_id=workspace_id, **fields)
        self.db.add(source)
        self.db.flush()
        return source

    def list_for_record(self, memory_record_id: uuid.UUID) -> list[MemorySource]:
        return list(
            self.db.query(MemorySource)
            .filter(MemorySource.memory_record_id == memory_record_id)
            .order_by(MemorySource.created_at.asc(), MemorySource.id.asc())
            .all()
        )

    def count_for_record(self, memory_record_id: uuid.UUID) -> int:
        return self.db.execute(
            select(func.count(MemorySource.id)).where(MemorySource.memory_record_id == memory_record_id)
        ).scalar_one()


class MemoryVersionRepository(ScopedRepository[MemoryVersion]):
    model = MemoryVersion

    def next_version_no(self, memory_record_id: uuid.UUID) -> int:
        current = self.db.execute(
            select(func.max(MemoryVersion.version_no)).where(MemoryVersion.memory_record_id == memory_record_id)
        ).scalar_one()
        return int(current or 0) + 1

    def add(
        self,
        memory_record_id: uuid.UUID,
        text: str,
        *,
        change_type: str,
        actor_type: str,
        actor_id: uuid.UUID | None,
        change_reason: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryVersion:
        """Append a version, retrying once on a concurrent-insert collision.

        `max(version_no) + 1` is computed from the row set rather than from a
        counter column, so two writers racing on the same memory can both pick
        the same number. The unique constraint turns that into a single loser
        with an IntegrityError; rolling just this insert back and retrying is
        cheaper than locking the memory row for every append.
        """
        for attempt in range(2):
            version = MemoryVersion(
                memory_record_id=memory_record_id,
                version_no=self.next_version_no(memory_record_id),
                text=text,
                extra_metadata=metadata or {},
                change_type=change_type,
                change_reason=change_reason,
                actor_type=actor_type,
                actor_id=actor_id,
            )
            self.db.add(version)
            try:
                self.db.flush()
                return version
            except Exception as exc:  # noqa: BLE001 - narrowed immediately below
                if not _is_unique_violation(exc) or attempt == 1:
                    raise
                self.db.rollback()
        raise ConflictError("Could not allocate a version number.")  # pragma: no cover

    def list_for_record(self, memory_record_id: uuid.UUID, *, limit: int = 50) -> list[MemoryVersion]:
        return list(
            self.db.query(MemoryVersion)
            .filter(MemoryVersion.memory_record_id == memory_record_id)
            .order_by(MemoryVersion.version_no.asc())
            .limit(limit)
            .all()
        )

    def get_version(self, memory_record_id: uuid.UUID, version_no: int) -> MemoryVersion | None:
        return self.db.execute(
            select(MemoryVersion).where(
                MemoryVersion.memory_record_id == memory_record_id,
                MemoryVersion.version_no == version_no,
            )
        ).scalar_one_or_none()

    def count_for_record(self, memory_record_id: uuid.UUID) -> int:
        return self.db.execute(
            select(func.count(MemoryVersion.id)).where(MemoryVersion.memory_record_id == memory_record_id)
        ).scalar_one()


def _is_unique_violation(exc: Exception) -> bool:
    if type(exc).__name__ != "IntegrityError":
        return False
    orig = getattr(exc, "orig", None)
    return "unique" in str(orig).lower() or "duplicate" in str(orig).lower()
