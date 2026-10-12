"""Graph, timeline and context use cases (P3).

Three read-mostly surfaces over the P2 tables:

* the graph, loaded incrementally — an initial node budget plus a bounded
  neighbour expansion per click, never the whole workspace;
* the timeline, a merged chronological view of messages and memories;
* context assembly, a deterministic scoring and budgeting pipeline that needs no
  LLM summary step.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import or_, select
from ume_app.auth.dependencies import WorkspaceAccess
from ume_app.domain.enums import (
    READABLE_MEMORY_STATUSES,
    EdgeStatus,
    MemoryStatus,
)
from ume_app.domain.errors import ConflictError, NotFoundError, ValidationError
from ume_app.models.base import as_utc, utcnow
from ume_app.models.conversation import Conversation, Message
from ume_app.models.graph import MemoryEdge
from ume_app.models.memory import MemoryRecord
from ume_app.repositories.memories import MemoryRecordRepository
from ume_app.services import memories as memory_service
from ume_app.services.audit import record

#: Section 15.3 budgets: 100 nodes on first load, 50 per neighbour expansion.
MAX_INITIAL_NODES = 100
MAX_NEIGHBORS_PER_NODE = 50

#: Rough token estimate for budget maths. Deliberately crude: an exact count
#: needs a tokenizer, and the assembly is a heuristic, not a billing surface.
CHARS_PER_TOKEN = 4

MAX_CONTEXT_TOKENS = 8000


@dataclass
class GraphPage:
    nodes: list[MemoryRecord] = field(default_factory=list)
    edges: list[MemoryEdge] = field(default_factory=list)
    next_cursor: str | None = None
    has_more: bool = False


def _edge_exists(db, workspace_id: uuid.UUID, source: uuid.UUID, target: uuid.UUID, relation: str) -> bool:
    """Unordered-pair lookup, mirroring the migration's partial unique index.

    `least`/`greatest` are PostgreSQL-only, so the canonical ordering is done
    here instead. Only the rows touching either endpoint are considered, so this
    stays cheap on a large graph.
    """
    wanted = sorted([str(source), str(target)])
    candidates = (
        db.query(MemoryEdge)
        .filter(
            MemoryEdge.workspace_id == workspace_id,
            MemoryEdge.relation_type == relation,
            MemoryEdge.status == str(EdgeStatus.ACTIVE),
            or_(MemoryEdge.source_memory_id == source, MemoryEdge.target_memory_id == source),
            or_(MemoryEdge.source_memory_id == target, MemoryEdge.target_memory_id == target),
        )
        .all()
    )
    return any(sorted([str(edge.source_memory_id), str(edge.target_memory_id)]) == wanted for edge in candidates)


class GraphService:
    def __init__(self, access: WorkspaceAccess) -> None:
        self.access = access
        self.db = access.db

    def window(self, *, project_id: uuid.UUID | None = None, limit: int = MAX_INITIAL_NODES) -> GraphPage:
        # Clamped here as well as in the route's Query bound: this method is
        # callable from jobs and importers that never pass through FastAPI, and
        # the budget is a property of the graph, not of one route.
        repository = MemoryRecordRepository(self.db)
        page = repository.list_for_workspace(
            self.access.workspace_id,
            project_id=project_id,
            status=str(MemoryStatus.ACTIVE),
            limit=min(limit, MAX_INITIAL_NODES),
        )
        node_ids = [node.id for node in page.items]
        edges = self._edges_among(node_ids)
        return GraphPage(nodes=page.items, edges=edges, next_cursor=page.next_cursor, has_more=page.has_more)

    def neighbors(self, node_id: uuid.UUID, *, limit: int = MAX_NEIGHBORS_PER_NODE) -> GraphPage:
        # Workspace scoping, not authorisation: the route dependency answers
        # "may this caller act here?", this answers "is this node even in the
        # workspace whose edges we are about to read?". Without it a non-HTTP
        # caller gets a silently empty page instead of a wrong-node error.
        if MemoryRecordRepository(self.db).get_in_workspace(self.access.workspace_id, node_id) is None:
            raise NotFoundError("Memory not found.")

        bounded = min(limit, MAX_NEIGHBORS_PER_NODE)
        edges = (
            self.db.query(MemoryEdge)
            .filter(
                MemoryEdge.workspace_id == self.access.workspace_id,
                MemoryEdge.status == str(EdgeStatus.ACTIVE),
                or_(MemoryEdge.source_memory_id == node_id, MemoryEdge.target_memory_id == node_id),
            )
            .order_by(MemoryEdge.created_at.desc(), MemoryEdge.id.desc())
            .limit(bounded)
            .all()
        )
        neighbor_ids = {
            (edge.target_memory_id if edge.source_memory_id == node_id else edge.source_memory_id) for edge in edges
        }
        neighbor_ids.discard(node_id)

        nodes = (
            self.db.query(MemoryRecord)
            .filter(
                MemoryRecord.workspace_id == self.access.workspace_id,
                MemoryRecord.id.in_(neighbor_ids),
                MemoryRecord.status.in_(tuple(READABLE_MEMORY_STATUSES)),
            )
            .all()
            if neighbor_ids
            else []
        )
        return GraphPage(nodes=list(nodes), edges=edges)

    def _edges_among(self, node_ids: list[uuid.UUID]) -> list[MemoryEdge]:
        if len(node_ids) < 2:
            return []
        return list(
            self.db.query(MemoryEdge)
            .filter(
                MemoryEdge.workspace_id == self.access.workspace_id,
                MemoryEdge.status == str(EdgeStatus.ACTIVE),
                MemoryEdge.source_memory_id.in_(node_ids),
                MemoryEdge.target_memory_id.in_(node_ids),
            )
            .all()
        )

    def create_edge(
        self,
        source_id: uuid.UUID,
        target_id: uuid.UUID,
        relation_type: str,
        *,
        evidence_ref: dict[str, Any] | None = None,
    ) -> MemoryEdge:
        repository = MemoryRecordRepository(self.db)
        for endpoint in (source_id, target_id):
            if repository.get_in_workspace(self.access.workspace_id, endpoint) is None:
                raise NotFoundError("Memory not found.")
        if source_id == target_id:
            raise ValidationError("A memory cannot be related to itself.")

        if _edge_exists(self.db, self.access.workspace_id, source_id, target_id, relation_type):
            raise ConflictError(
                "This relation already exists.",
                details={
                    "source_memory_id": str(source_id),
                    "target_memory_id": str(target_id),
                    "relation_type": relation_type,
                },
            )

        edge = MemoryEdge(
            workspace_id=self.access.workspace_id,
            source_memory_id=source_id,
            target_memory_id=target_id,
            relation_type=relation_type,
            status=str(EdgeStatus.ACTIVE),
            evidence_ref=evidence_ref or {},
            created_by_type=str(self.access.principal.actor_type),
            created_by_id=self.access.principal.actor_id,
        )
        self.db.add(edge)
        self.db.flush()
        record(
            self.db,
            self.access.principal,
            action="graph.edge.create",
            resource_type="memory_edge",
            resource_id=edge.id,
            workspace_id=self.access.workspace_id,
            details={"relation_type": relation_type},
        )
        self.db.commit()
        self.db.refresh(edge)
        return edge

    def update_edge(self, edge_id: uuid.UUID, *, status: str, relation_type: str | None = None) -> MemoryEdge:
        edge = self._require_edge(edge_id)
        edge.status = status
        if relation_type is not None:
            edge.relation_type = relation_type
        from ume_app.models.base import utcnow as _now

        edge.updated_at = _now()
        record(
            self.db,
            self.access.principal,
            action="graph.edge.update",
            resource_type="memory_edge",
            resource_id=edge.id,
            workspace_id=self.access.workspace_id,
            details={"status": status},
        )
        self.db.commit()
        self.db.refresh(edge)
        return edge

    def delete_edge(self, edge_id: uuid.UUID) -> None:
        edge = self._require_edge(edge_id)
        self.db.delete(edge)
        record(
            self.db,
            self.access.principal,
            action="graph.edge.delete",
            resource_type="memory_edge",
            resource_id=edge_id,
            workspace_id=self.access.workspace_id,
            details={},
        )
        self.db.commit()

    def _require_edge(self, edge_id: uuid.UUID) -> MemoryEdge:
        edge = self.db.execute(
            select(MemoryEdge).where(MemoryEdge.workspace_id == self.access.workspace_id, MemoryEdge.id == edge_id)
        ).scalar_one_or_none()
        if edge is None:
            raise NotFoundError("Edge not found.")
        return edge


# ---------------------------------------------------------------------------
# Timeline
# ---------------------------------------------------------------------------


def timeline(
    access: WorkspaceAccess,
    *,
    limit: int = 50,
    since: datetime | None = None,
    until: datetime | None = None,
    project_id: uuid.UUID | None = None,
) -> list[dict[str, Any]]:
    """One chronological stream of messages and memories.

    Merged in Python rather than SQL: two different tables with different time
    columns produce a UNION ALL that is far harder to page than a merge of two
    already-bounded lists.
    """
    db = access.db

    message_stmt = (
        db.query(Message)
        .join(Conversation, Conversation.id == Message.conversation_id)
        .filter(
            Message.workspace_id == access.workspace_id,
            Message.deleted_at.is_(None),
        )
    )
    if project_id is not None:
        message_stmt = message_stmt.filter(Conversation.project_id == project_id)
    if since is not None:
        message_stmt = message_stmt.filter(Message.message_at >= since)
    if until is not None:
        message_stmt = message_stmt.filter(Message.message_at <= until)

    memory_stmt = db.query(MemoryRecord).filter(
        MemoryRecord.workspace_id == access.workspace_id,
        MemoryRecord.status.in_(tuple(READABLE_MEMORY_STATUSES)),
    )
    if project_id is not None:
        from ume_app.models.memory import MemoryProjectLink

        memory_stmt = memory_stmt.join(MemoryProjectLink, MemoryProjectLink.memory_record_id == MemoryRecord.id).filter(
            MemoryProjectLink.project_id == project_id
        )
    if since is not None:
        memory_stmt = memory_stmt.filter(MemoryRecord.created_at >= since)
    if until is not None:
        memory_stmt = memory_stmt.filter(MemoryRecord.created_at <= until)

    entries: list[dict[str, Any]] = []
    for message in message_stmt.limit(limit).all():
        entries.append(
            {
                "kind": "message",
                "id": str(message.id),
                "conversation_id": str(message.conversation_id),
                "at": message.message_at,
                "title": f"{message.role} message",
                "preview": (message.content_text or "")[:280],
                "sensitivity": message.sensitivity,
            }
        )
    for row in memory_stmt.limit(limit).all():
        entries.append(
            {
                "kind": "memory",
                "id": str(row.id),
                "conversation_id": None,
                "at": row.updated_at,
                "title": row.current_text[:120],
                "preview": None,
                "status": row.status,
            }
        )

    entries.sort(key=lambda item: as_utc(item["at"]), reverse=True)
    return entries[:limit]


# ---------------------------------------------------------------------------
# Context assembly (section 12)
# ---------------------------------------------------------------------------


@dataclass
class ContextCandidate:
    record: MemoryRecord
    semantic_score: float
    project_match: bool
    confirmed: bool
    freshness_days: float
    score: float = 0.0

    @property
    def tokens(self) -> int:
        return max(1, len(self.record.current_text) // CHARS_PER_TOKEN)


TYPE_WEIGHTS = {
    "decision": 1.15,
    "procedure": 1.10,
    "project": 1.05,
    "semantic": 1.0,
}


def assemble_context(
    access: WorkspaceAccess,
    *,
    query: str,
    limit: int = 10,
    token_budget: int = MAX_CONTEXT_TOKENS,
    project_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """Score, rank and trim memories into a prompt budget.

    Deterministic and explainable by construction: every returned item carries
    the components that produced its score, so a caller can see why something
    was dropped.
    """
    if token_budget < 1:
        raise ValidationError("token_budget must be positive.")

    hits = memory_service.search(access, query=query, limit=limit * 3, project_id=project_id)
    links = _confirmed_memory_types(access, project_id)
    now = utcnow()

    candidates: list[ContextCandidate] = []
    for row, hit in hits:
        semantic = float(hit.score or 0.0)
        candidates.append(
            ContextCandidate(
                record=row,
                semantic_score=semantic,
                project_match=project_id is not None and project_id in links.get(row.id, set()),
                confirmed=row.id in links.get(row.id, set())
                and row.memory_type in {"decision", "procedure", "project"},
                freshness_days=(as_utc(now) - as_utc(row.updated_at)).total_seconds() / 86400.0,
            )
        )

    for candidate in candidates:
        candidate.score = _score(candidate)

    candidates.sort(key=lambda c: c.score, reverse=True)

    included, dropped = [], []
    spent = 0
    for candidate in candidates:
        if len(included) >= limit:
            dropped.append(_reason(candidate, "over_limit"))
            continue
        if spent + candidate.tokens > token_budget:
            dropped.append(_reason(candidate, "over_budget"))
            continue
        spent += candidate.tokens
        included.append(_item(candidate, None))

    return {
        "query": query,
        "token_budget": token_budget,
        "estimated_tokens": spent,
        "items": included,
        "dropped": dropped,
        "summarized": False,
    }


def _confirmed_memory_types(access: WorkspaceAccess, project_id: uuid.UUID | None) -> dict[uuid.UUID, set[uuid.UUID]]:
    from ume_app.models.memory import MemoryProjectLink

    stmt = access.db.query(MemoryProjectLink.memory_record_id, MemoryProjectLink.project_id)
    if project_id is not None:
        stmt = stmt.filter(MemoryProjectLink.project_id == project_id)
    result: dict[uuid.UUID, set[uuid.UUID]] = {}
    for record_id, linked_project in stmt.all():
        result.setdefault(record_id, set()).add(linked_project)
    return result


def _score(candidate: ContextCandidate) -> float:
    # Freshness decays over a week rather than linearly forever, so a very old
    # but very relevant memory is not permanently outranked by a fresh one.
    freshness = 1.0 / (1.0 + candidate.freshness_days / 7.0)
    score = candidate.semantic_score * 0.6 + freshness * 0.2 + TYPE_WEIGHTS.get(candidate.record.memory_type, 1.0) * 0.2
    if candidate.project_match:
        score += 0.15
    if candidate.confirmed:
        score += 0.1
    return round(score, 6)


def _reason(candidate: ContextCandidate, reason: str) -> dict[str, Any]:
    return {
        "memory_id": str(candidate.record.id),
        "text": candidate.record.current_text[:120],
        "score": candidate.score,
        "tokens": candidate.tokens,
        "reason": reason,
    }


def _item(candidate: ContextCandidate, dropped_reason: str | None) -> dict[str, Any]:
    return {
        "memory_id": str(candidate.record.id),
        "text": candidate.record.current_text,
        "memory_type": candidate.record.memory_type,
        "score": candidate.score,
        "tokens": candidate.tokens,
        "semantic_score": candidate.semantic_score,
        "freshness_days": round(candidate.freshness_days, 3),
        "project_match": candidate.project_match,
        "confirmed": candidate.confirmed,
        "engine_id": candidate.record.engine_memory_id,
    }
