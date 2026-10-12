"""Service-level graph tests.

The node and neighbour budgets are properties of the graph, not of the HTTP
route: a job or an importer that calls the service directly must get the same
cap. These bypass the route on purpose so the budget can only be enforced in
one place.
"""

import pytest
from ume_app.auth.dependencies import resolve_access
from ume_app.auth.permissions import Principal
from ume_app.domain.enums import EdgeStatus
from ume_app.models.base import utcnow
from ume_app.models.graph import MemoryEdge
from ume_app.models.memory import MemoryRecord, MemoryVersion
from ume_app.services.graph import (
    MAX_CONTEXT_TOKENS,
    MAX_INITIAL_NODES,
    MAX_NEIGHBORS_PER_NODE,
    GraphService,
)


@pytest.fixture
def workspace_access(db, users, two_tenants):
    """A `WorkspaceAccess` built without going through the route dependency."""
    principal = Principal(actor_type="user", actor_id=users[0].id, scopes=frozenset())
    return resolve_access(db, principal, two_tenants["workspace_a"].id)


def _insert_memory(db, workspace_id, index) -> MemoryRecord:
    row = MemoryRecord(
        workspace_id=workspace_id,
        engine_memory_id=f"eng-seed-{index}",
        memory_type="semantic",
        status="active",
        current_text=f"seeded fact {index}",
        tags=[],
        access_scope={},
        engine_state="ready",
        created_by_type="system",
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    db.add(row)
    db.flush()
    db.add(
        MemoryVersion(
            memory_record_id=row.id,
            version_no=1,
            text=row.current_text,
            change_type="created",
            actor_type="system",
        )
    )
    return row


def _insert_edge(db, workspace_id, source, target) -> MemoryEdge:
    edge = MemoryEdge(
        workspace_id=workspace_id,
        source_memory_id=source,
        target_memory_id=target,
        relation_type="related_to",
        status=str(EdgeStatus.ACTIVE),
        evidence_ref={},
        created_by_type="system",
    )
    db.add(edge)
    db.flush()
    return edge


class TestInitialWindowBudget:
    def test_the_service_clamps_even_when_asked_for_everything(self, db, workspace_access, two_tenants):
        for index in range(MAX_INITIAL_NODES + 20):
            _insert_memory(db, workspace_access.workspace_id, index)
        db.commit()

        page = GraphService(workspace_access).window(limit=10_000)
        assert len(page.nodes) == MAX_INITIAL_NODES

    def test_the_window_reports_more_when_truncated(self, db, workspace_access):
        for index in range(MAX_INITIAL_NODES + 5):
            _insert_memory(db, workspace_access.workspace_id, index)
        db.commit()

        page = GraphService(workspace_access).window(limit=MAX_INITIAL_NODES)
        assert page.has_more is True
        assert page.next_cursor is not None


class TestNeighbourBudget:
    def test_the_service_clamps_expansion(self, db, workspace_access):
        centre = _insert_memory(db, workspace_access.workspace_id, "centre")
        for index in range(MAX_NEIGHBORS_PER_NODE + 15):
            leaf = _insert_memory(db, workspace_access.workspace_id, f"leaf-{index}")
            _insert_edge(db, workspace_access.workspace_id, centre.id, leaf.id)
        db.commit()

        page = GraphService(workspace_access).neighbors(centre.id, limit=10_000)
        assert len(page.edges) == MAX_NEIGHBORS_PER_NODE

    def test_a_leaf_returns_itself_out_of_the_neighbour_set(self, db, workspace_access):
        a = _insert_memory(db, workspace_access.workspace_id, "a")
        b = _insert_memory(db, workspace_access.workspace_id, "b")
        _insert_edge(db, workspace_access.workspace_id, a.id, b.id)
        db.commit()

        page = GraphService(workspace_access).neighbors(a.id)
        assert [node.id for node in page.nodes] == [b.id]
        assert a.id not in [node.id for node in page.nodes]


class TestEdgeInvariants:
    def test_the_reverse_direction_is_the_same_edge(self, db, workspace_access):
        from ume_app.domain.errors import ConflictError

        a = _insert_memory(db, workspace_access.workspace_id, "a")
        b = _insert_memory(db, workspace_access.workspace_id, "b")
        db.commit()

        service = GraphService(workspace_access)
        service.create_edge(a.id, b.id, "supports")
        with pytest.raises(ConflictError):
            service.create_edge(b.id, a.id, "supports")

    def test_a_self_loop_is_refused(self, db, workspace_access):
        from ume_app.domain.errors import ValidationError

        a = _insert_memory(db, workspace_access.workspace_id, "a")
        db.commit()
        with pytest.raises(ValidationError):
            GraphService(workspace_access).create_edge(a.id, a.id, "related_to")

    def test_an_edge_cannot_reach_outside_the_workspace(self, db, workspace_access, two_tenants, users):
        from ume_app.domain.errors import NotFoundError

        mine = _insert_memory(db, workspace_access.workspace_id, "mine")
        theirs = MemoryRecord(
            workspace_id=two_tenants["workspace_b"].id,
            engine_memory_id="eng-foreign",
            memory_type="semantic",
            status="active",
            current_text="foreign",
            tags=[],
            access_scope={},
            engine_state="ready",
            created_by_type="system",
        )
        db.add(theirs)
        db.commit()

        with pytest.raises(NotFoundError):
            GraphService(workspace_access).create_edge(mine.id, theirs.id, "related_to")


class TestEdgeIsolation:
    def test_a_foreign_edge_is_not_readable(self, db, workspace_access, two_tenants):
        from ume_app.domain.errors import NotFoundError

        a = _insert_memory(db, two_tenants["workspace_b"].id, "a")
        b = _insert_memory(db, two_tenants["workspace_b"].id, "b")
        edge = _insert_edge(db, two_tenants["workspace_b"].id, a.id, b.id)
        db.commit()

        with pytest.raises(NotFoundError):
            GraphService(workspace_access).update_edge(edge.id, status="archived")

    def test_a_foreign_node_has_no_neighbours(self, db, workspace_access, two_tenants):
        from ume_app.domain.errors import NotFoundError

        a = _insert_memory(db, two_tenants["workspace_b"].id, "a")
        b = _insert_memory(db, two_tenants["workspace_b"].id, "b")
        _insert_edge(db, two_tenants["workspace_b"].id, a.id, b.id)
        db.commit()

        with pytest.raises(NotFoundError):
            GraphService(workspace_access).neighbors(a.id)


class TestBudgetConstants:
    def test_the_documented_limits_are_what_the_code_uses(self):
        # Section 15.3: 100 nodes on first load, 50 per expansion.
        assert MAX_INITIAL_NODES == 100
        assert MAX_NEIGHBORS_PER_NODE == 50
        assert MAX_CONTEXT_TOKENS > 0
