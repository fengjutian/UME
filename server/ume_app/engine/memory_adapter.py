"""Memory engine adapter.

The business layer never imports `ume.Memory` directly. Everything that reaches
the engine goes through this module, for three reasons:

* the workspace scope is injected here and nowhere else, so it cannot be
  forgotten at a call site;
* the engine's return shapes are normalised once, instead of every service
  learning them;
* tests can substitute a fake engine without patching SDK internals.

Scope is passed to the engine as `ume_workspace_id` / `ume_project_ids` /
`ume_memory_record_id` metadata, matching section 8.
"""

import uuid
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from ume_app.domain.errors import NotFoundError
from ume_app.models.base import utcnow


@dataclass(frozen=True)
class EngineScope:
    """The UME binding an engine call must carry."""

    workspace_id: uuid.UUID
    project_ids: tuple[uuid.UUID, ...] = ()
    memory_record_id: uuid.UUID | None = None

    def as_metadata(self) -> dict[str, Any]:
        metadata: dict[str, Any] = {
            "ume_workspace_id": str(self.workspace_id),
            "ume_project_ids": [str(pid) for pid in self.project_ids],
        }
        if self.memory_record_id is not None:
            metadata["ume_memory_record_id"] = str(self.memory_record_id)
        return metadata


@dataclass(frozen=True)
class EngineMemory:
    """One engine memory, normalised."""

    id: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    score: float | None = None
    raw: Any = None


@dataclass(frozen=True)
class EngineHistoryItem:
    memory_id: str
    text: str
    event: str | None = None
    created_at: Any = None
    raw: Any = None


@runtime_checkable
class MemoryEngineAdapter(Protocol):
    """Section 8 interface."""

    def add(
        self, messages: list[dict[str, Any]], *, scope: EngineScope, metadata: dict[str, Any], infer: bool = True
    ) -> list[EngineMemory]: ...

    def search(
        self, query: str, *, scope: EngineScope, filters: dict[str, Any] | None = None, limit: int = 10
    ) -> list[EngineMemory]: ...

    def get(self, memory_id: str, *, scope: EngineScope) -> EngineMemory: ...

    def update(
        self, memory_id: str, text: str, *, scope: EngineScope, metadata: dict[str, Any] | None = None
    ) -> EngineMemory: ...

    def delete(self, memory_id: str, *, scope: EngineScope) -> None: ...

    def history(self, memory_id: str, *, scope: EngineScope) -> list[EngineHistoryItem]: ...


def _normalise_memory(raw: Any, *, score: float | None = None) -> EngineMemory:
    """Accept the several shapes the SDK returns and produce one.

    The SDK has returned `{"id", "memory"}`, `{"id", "data"}` and object-like
    rows over its history; normalising here keeps that history out of the
    services.
    """
    if raw is None:
        raise NotFoundError("Memory not found.")
    if isinstance(raw, str):
        return EngineMemory(id="", text=raw)

    if isinstance(raw, dict):
        memory_id = raw.get("id") or raw.get("memory_id") or ""
        text = raw.get("memory")
        if text is None:
            text = raw.get("data")
        if text is None:
            payload = raw.get("payload") or {}
            text = payload.get("data") or ""
        metadata = raw.get("metadata")
        if metadata is None:
            payload = raw.get("payload") or {}
            metadata = payload.get("metadata") or {}
        return EngineMemory(
            id=str(memory_id), text=str(text or ""), metadata=dict(metadata or {}), score=score, raw=raw
        )

    payload = getattr(raw, "payload", None) or {}
    memory_id = getattr(raw, "id", "") or ""
    text = payload.get("data") if isinstance(payload, dict) else None
    return EngineMemory(
        id=str(memory_id),
        text=str(text or ""),
        metadata=dict(payload.get("metadata", {})) if isinstance(payload, dict) else {},
        score=score,
        raw=raw,
    )


class SdkMemoryAdapter:
    """Adapter over the installed `ume.Memory` singleton."""

    def __init__(self, memory_factory=None) -> None:
        # Imported lazily: importing ume at module scope would make every
        # business-layer unit test pull in the whole SDK dependency tree.
        if memory_factory is None:
            from server_state import get_memory_instance

            memory_factory = get_memory_instance
        self._factory = memory_factory

    def _metadata(self, scope: EngineScope, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        metadata = scope.as_metadata()
        if extra:
            metadata.update(extra)
        return metadata

    def add(
        self,
        messages: list[dict[str, Any]],
        *,
        scope: EngineScope,
        metadata: dict[str, Any] | None = None,
        infer: bool = True,
    ) -> list[EngineMemory]:
        result = self._factory().add(messages=messages, metadata=self._metadata(scope, metadata), infer=infer)
        return [_normalise_memory(item) for item in _iter_results(result)]

    def search(
        self,
        query: str,
        *,
        scope: EngineScope,
        filters: dict[str, Any] | None = None,
        limit: int = 10,
    ) -> list[EngineMemory]:
        # The workspace filter goes *into* the query. Filtering afterwards would
        # let another tenant's candidates influence the ranking.
        engine_filters = dict(filters or {})
        engine_filters.update(self._metadata(scope))
        results = self._factory().search(query=query, filters=engine_filters, top_k=limit)
        return [_normalise_memory(item, score=_score_of(item)) for item in _iter_results(results)]

    def get(self, memory_id: str, *, scope: EngineScope) -> EngineMemory:
        raw = self._factory().get(memory_id)
        memory = _normalise_memory(raw)
        # Belt and braces: the engine is not trusted to have filtered for us.
        owner = memory.metadata.get("ume_workspace_id")
        if owner is not None and str(owner) != str(scope.workspace_id):
            raise NotFoundError("Memory not found.")
        return memory

    def update(
        self, memory_id: str, text: str, *, scope: EngineScope, metadata: dict[str, Any] | None = None
    ) -> EngineMemory:
        return _normalise_memory(
            self._factory().update(memory_id=memory_id, data=text, metadata=self._metadata(scope, metadata))
        )

    def delete(self, memory_id: str, *, scope: EngineScope) -> None:
        self._factory().delete(memory_id=memory_id)

    def history(self, memory_id: str, *, scope: EngineScope) -> list[EngineHistoryItem]:
        rows = self._factory().history(memory_id=memory_id) or []
        items = []
        for row in rows:
            if isinstance(row, dict):
                text = row.get("new_memory") or row.get("memory") or row.get("data") or ""
                items.append(
                    EngineHistoryItem(
                        memory_id=str(row.get("id") or memory_id),
                        text=str(text),
                        event=row.get("event"),
                        created_at=row.get("created_at") or row.get("updated_at") or utcnow(),
                        raw=row,
                    )
                )
            else:  # pragma: no cover - the SDK currently returns dicts
                items.append(EngineHistoryItem(memory_id=memory_id, text=str(row), raw=row))
        return items


def _iter_results(result: Any) -> list[Any]:
    if result is None:
        return []
    if isinstance(result, dict):
        rows = result.get("results", [])
    elif isinstance(result, list):
        rows = result
    else:
        rows = [result]
    # The SDK sometimes nests one extra list level.
    if len(rows) == 1 and isinstance(rows[0], list):
        rows = rows[0]
    return list(rows or [])


def _score_of(item: Any) -> float | None:
    if isinstance(item, dict):
        score = item.get("score")
        if score is None:
            score = item.get("similarity")
        return float(score) if score is not None else None
    score = getattr(item, "score", None)
    return float(score) if score is not None else None


_ADAPTER: MemoryEngineAdapter | None = None


def get_adapter() -> MemoryEngineAdapter:
    """The process-wide adapter. Swappable so tests can inject a fake."""
    global _ADAPTER
    if _ADAPTER is None:
        _ADAPTER = SdkMemoryAdapter()
    return _ADAPTER


def set_adapter(adapter: MemoryEngineAdapter | None) -> None:
    global _ADAPTER
    _ADAPTER = adapter
