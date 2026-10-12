"""Graph, timeline and context tests (P3).

Covers the incremental-load budgets from section 15.3, the edge invariants, the
tenant boundary, and the context budget arithmetic.
"""

import uuid

from envelope import envelope_error, envelope_ok
from ume_app.engine.memory_adapter import EngineMemory


def make_memory(api, workspace_id, text="a fact", *, tags=None, projects=None, as_user=0):
    """Create a memory as the given caller.

    `as_user` matters: tenant B's memories have to be created by B, or the
    membership check answers 404 and the test would be asserting the wrong
    thing.
    """
    body = {
        "workspace_id": str(workspace_id),
        "messages": [{"role": "user", "content": text}],
    }
    if tags:
        body["tags"] = tags
    if projects:
        body["project_ids"] = [str(p) for p in projects]
    return envelope_ok(api.as_user(as_user).client.post("/memories", json=body), 201)


def seed_search(engine, memory, score=0.9):
    """Make the fake engine return a memory that already exists in the business table.

    A made-up engine id would be dropped by the post-search ownership check,
    which is the whole point of that check — so the tests link to the real
    engine id the create route produced.
    """
    engine_id = memory["engine_memory_id"]
    engine.search_result = [EngineMemory(id=engine_id, text=memory["current_text"], score=score)]
    return engine_id


class TestGraphWindow:
    def test_initial_load_returns_nodes_and_edges(self, api, two_tenants, engine):
        workspace_id = two_tenants["workspace_a"].id
        data = envelope_ok(api.as_user(0).client.get(f"/graph?workspace_id={workspace_id}"))
        assert "nodes" in data and "edges" in data
        assert data["has_more"] is False

    def test_initial_load_is_capped_at_100_nodes(self, api, two_tenants, engine):
        workspace_id = two_tenants["workspace_a"].id
        for index in range(105):
            make_memory(api, workspace_id, f"fact {index}")
        data = envelope_ok(api.as_user(0).client.get(f"/graph?workspace_id={workspace_id}"))
        assert len(data["nodes"]) == 100
        assert data["has_more"] is True

    def test_graph_nodes_carry_no_message_bodies(self, api, two_tenants, engine):
        workspace_id = two_tenants["workspace_a"].id
        make_memory(api, workspace_id, "the fact itself")
        data = envelope_ok(api.as_user(0).client.get(f"/graph?workspace_id={workspace_id}"))
        assert set(data["nodes"][0]) == {"id", "text", "memory_type", "status", "engine_id", "created_at"}

    def test_graph_is_workspace_scoped(self, api, two_tenants, engine):
        make_memory(api, two_tenants["workspace_a"].id, "tenant a fact")
        make_memory(api, two_tenants["workspace_b"].id, "tenant b fact", as_user=1)
        mine = envelope_ok(api.as_user(0).client.get(f"/graph?workspace_id={two_tenants['workspace_a'].id}"))
        assert [n["text"] for n in mine["nodes"]] == ["tenant a fact"]
        theirs = envelope_ok(api.as_user(1).client.get(f"/graph?workspace_id={two_tenants['workspace_b'].id}"))
        assert [n["text"] for n in theirs["nodes"]] == ["tenant b fact"]

    def test_graph_in_another_workspace_is_404(self, api, two_tenants, engine):
        envelope_error(
            api.as_user(1).client.get(f"/graph?workspace_id={two_tenants['workspace_a'].id}"), "NOT_FOUND", 404
        )


class TestEdges:
    def test_create_and_read_an_edge(self, api, two_tenants, engine):
        workspace_id = two_tenants["workspace_a"].id
        a = make_memory(api, workspace_id, "first")
        b = make_memory(api, workspace_id, "second")
        edge = envelope_ok(
            api.as_user(0).client.post(
                "/graph/edges",
                json={
                    "workspace_id": str(workspace_id),
                    "source_memory_id": a["id"],
                    "target_memory_id": b["id"],
                    "relation_type": "supports",
                },
            ),
            201,
        )
        assert edge["relation_type"] == "supports"

        data = envelope_ok(api.as_user(0).client.get(f"/graph?workspace_id={workspace_id}"))
        assert len(data["edges"]) == 1

    def test_the_pair_is_unordered(self, api, two_tenants, engine):
        """(a,b) and (b,a) are the same relation, so the reverse write conflicts."""
        workspace_id = two_tenants["workspace_a"].id
        a = make_memory(api, workspace_id, "first")
        b = make_memory(api, workspace_id, "second")
        api.as_user(0).client.post(
            "/graph/edges",
            json={
                "workspace_id": str(workspace_id),
                "source_memory_id": a["id"],
                "target_memory_id": b["id"],
                "relation_type": "supports",
            },
        )
        response = api.as_user(0).client.post(
            "/graph/edges",
            json={
                "workspace_id": str(workspace_id),
                "source_memory_id": b["id"],
                "target_memory_id": a["id"],
                "relation_type": "supports",
            },
        )
        envelope_error(response, "CONFLICT", 409)

    def test_a_different_relation_type_is_allowed(self, api, two_tenants, engine):
        workspace_id = two_tenants["workspace_a"].id
        a = make_memory(api, workspace_id, "first")
        b = make_memory(api, workspace_id, "second")
        for relation in ("supports", "contradicts"):
            envelope_ok(
                api.as_user(0).client.post(
                    "/graph/edges",
                    json={
                        "workspace_id": str(workspace_id),
                        "source_memory_id": a["id"],
                        "target_memory_id": b["id"],
                        "relation_type": relation,
                    },
                ),
                201,
            )

    def test_self_loops_are_rejected(self, api, two_tenants, engine):
        workspace_id = two_tenants["workspace_a"].id
        a = make_memory(api, workspace_id, "first")
        response = api.as_user(0).client.post(
            "/graph/edges",
            json={
                "workspace_id": str(workspace_id),
                "source_memory_id": a["id"],
                "target_memory_id": a["id"],
                "relation_type": "related_to",
            },
        )
        envelope_error(response, "VALIDATION_FAILED", 400)

    def test_an_edge_to_a_foreign_memory_is_404(self, api, two_tenants, engine):
        workspace_id = two_tenants["workspace_a"].id
        a = make_memory(api, workspace_id, "first")
        foreign = make_memory(api, two_tenants["workspace_b"].id, "other tenant", as_user=1)
        response = api.as_user(0).client.post(
            "/graph/edges",
            json={
                "workspace_id": str(workspace_id),
                "source_memory_id": a["id"],
                "target_memory_id": foreign["id"],
                "relation_type": "related_to",
            },
        )
        envelope_error(response, "NOT_FOUND", 404)

    def test_unknown_relation_type_is_rejected(self, api, two_tenants, engine):
        workspace_id = two_tenants["workspace_a"].id
        a = make_memory(api, workspace_id, "first")
        b = make_memory(api, workspace_id, "second")
        response = api.as_user(0).client.post(
            "/graph/edges",
            json={
                "workspace_id": str(workspace_id),
                "source_memory_id": a["id"],
                "target_memory_id": b["id"],
                "relation_type": "vibes",
            },
        )
        envelope_error(response, "VALIDATION_FAILED", 400)

    def test_oversized_evidence_is_rejected(self, api, two_tenants, engine):
        """Evidence stores a reference, never a body."""
        workspace_id = two_tenants["workspace_a"].id
        a = make_memory(api, workspace_id, "first")
        b = make_memory(api, workspace_id, "second")
        response = api.as_user(0).client.post(
            "/graph/edges",
            json={
                "workspace_id": str(workspace_id),
                "source_memory_id": a["id"],
                "target_memory_id": b["id"],
                "relation_type": "related_to",
                "evidence_ref": {"body": "x" * 9000},
            },
        )
        envelope_error(response, "VALIDATION_FAILED", 400)


class TestNeighbors:
    def test_expand_returns_the_far_node_and_the_edge(self, api, two_tenants, engine):
        workspace_id = two_tenants["workspace_a"].id
        a = make_memory(api, workspace_id, "first")
        b = make_memory(api, workspace_id, "second")
        api.as_user(0).client.post(
            "/graph/edges",
            json={
                "workspace_id": str(workspace_id),
                "source_memory_id": a["id"],
                "target_memory_id": b["id"],
                "relation_type": "supports",
            },
        )
        data = envelope_ok(api.as_user(0).client.get(f"/graph/nodes/{a['id']}/neighbors"))
        assert [n["id"] for n in data["nodes"]] == [b["id"]]
        assert len(data["edges"]) == 1

    def test_expansion_is_capped_at_50(self, api, two_tenants, engine):
        workspace_id = two_tenants["workspace_a"].id
        centre = make_memory(api, workspace_id, "centre")
        for index in range(55):
            other = make_memory(api, workspace_id, f"leaf {index}")
            api.as_user(0).client.post(
                "/graph/edges",
                json={
                    "workspace_id": str(workspace_id),
                    "source_memory_id": centre["id"],
                    "target_memory_id": other["id"],
                    "relation_type": "related_to",
                },
            )
        data = envelope_ok(api.as_user(0).client.get(f"/graph/nodes/{centre['id']}/neighbors"))
        assert len(data["edges"]) == 50

    def test_expanding_a_foreign_node_is_404(self, api, two_tenants, engine):
        foreign = make_memory(api, two_tenants["workspace_b"].id, "other tenant", as_user=1)
        envelope_error(api.as_user(0).client.get(f"/graph/nodes/{foreign['id']}/neighbors"), "NOT_FOUND", 404)

    def test_expanding_an_unknown_node_is_404(self, api, two_tenants, engine):
        envelope_error(api.as_user(0).client.get(f"/graph/nodes/{uuid.uuid4()}/neighbors"), "NOT_FOUND", 404)


class TestTimeline:
    def test_merges_messages_and_memories_newest_first(self, api, two_tenants, engine):
        workspace_id = two_tenants["workspace_a"].id
        conversation = envelope_ok(
            api.as_user(0).client.post("/conversations", json={"workspace_id": str(workspace_id)}), 201
        )
        api.as_user(0).client.post(
            f"/conversations/{conversation['id']}/messages",
            json={"messages": [{"role": "user", "content": "archived text", "timestamp": "2026-10-01T12:00:00Z"}]},
        )
        make_memory(api, workspace_id, "a fact")

        entries = envelope_ok(api.as_user(0).client.get(f"/timeline?workspace_id={workspace_id}"))
        kinds = [entry["kind"] for entry in entries]
        assert "message" in kinds and "memory" in kinds
        assert kinds[0] == "memory", "newest first"

    def test_message_preview_is_truncated(self, api, two_tenants, engine):
        workspace_id = two_tenants["workspace_a"].id
        conversation = envelope_ok(
            api.as_user(0).client.post("/conversations", json={"workspace_id": str(workspace_id)}), 201
        )
        api.as_user(0).client.post(
            f"/conversations/{conversation['id']}/messages",
            json={"messages": [{"role": "user", "content": "x" * 900, "timestamp": "2026-10-01T12:00:00Z"}]},
        )
        entries = envelope_ok(api.as_user(0).client.get(f"/timeline?workspace_id={workspace_id}"))
        message = [e for e in entries if e["kind"] == "message"][0]
        assert len(message["preview"]) <= 280

    def test_timeline_is_workspace_scoped(self, api, two_tenants, engine):
        make_memory(api, two_tenants["workspace_a"].id, "tenant a fact")
        # Bob owns workspace B and has no memories in it.
        entries = envelope_ok(api.as_user(1).client.get(f"/timeline?workspace_id={two_tenants['workspace_b'].id}"))
        assert entries == []
        # Alice is not a member of workspace B at all.
        envelope_error(
            api.as_user(0).client.get(f"/timeline?workspace_id={two_tenants['workspace_b'].id}"), "NOT_FOUND", 404
        )

    def test_deleted_memories_are_absent_from_the_timeline(self, api, two_tenants, engine):
        workspace_id = two_tenants["workspace_a"].id
        memory = make_memory(api, workspace_id, "a fact")
        api.as_user(0).client.post(f"/memories/{memory['id']}/forget", json={})
        entries = envelope_ok(api.as_user(0).client.get(f"/timeline?workspace_id={workspace_id}"))
        assert entries == []


class TestContext:
    def test_context_returns_scored_items(self, api, two_tenants, engine):
        workspace_id = two_tenants["workspace_a"].id
        memory = make_memory(api, workspace_id, "the user prefers dark mode")
        seed_search(engine, memory, score=0.8)

        data = envelope_ok(
            api.as_user(0).client.post("/context", json={"workspace_id": str(workspace_id), "query": "dark mode"})
        )
        assert len(data["items"]) == 1
        item = data["items"][0]
        assert item["semantic_score"] == 0.8
        assert item["tokens"] > 0
        assert data["summarized"] is False

    def test_budget_trims_and_explains(self, api, two_tenants, engine):
        workspace_id = two_tenants["workspace_a"].id
        memories = [make_memory(api, workspace_id, "filler " * 100 + str(i)) for i in range(4)]
        engine.search_result = [
            EngineMemory(id=m["engine_memory_id"], text=m["current_text"], score=0.9 - index / 100)
            for index, m in enumerate(memories)
        ]

        data = envelope_ok(
            api.as_user(0).client.post(
                "/context",
                json={"workspace_id": str(workspace_id), "query": "filler", "token_budget": 60},
            )
        )
        assert data["estimated_tokens"] <= 60
        assert data["dropped"], "dropped items must carry a reason"
        assert all(item["reason"] in {"over_budget", "over_limit"} for item in data["dropped"])

    def test_limit_trims_before_budget(self, api, two_tenants, engine):
        workspace_id = two_tenants["workspace_a"].id
        memories = [make_memory(api, workspace_id, f"fact {index}") for index in range(3)]
        engine.search_result = [
            EngineMemory(id=m["engine_memory_id"], text=m["current_text"], score=0.9 - index / 100)
            for index, m in enumerate(memories)
        ]

        data = envelope_ok(
            api.as_user(0).client.post(
                "/context", json={"workspace_id": str(workspace_id), "query": "fact", "limit": 1}
            )
        )
        assert len(data["items"]) == 1
        assert [d["reason"] for d in data["dropped"]] == ["over_limit"] * 2

    def test_project_match_raises_the_score(self, api, two_tenants, engine):
        workspace_id = two_tenants["workspace_a"].id
        project_id = two_tenants["project_a"].id
        memory = make_memory(api, workspace_id, "linked fact", projects=[project_id])
        engine_id = seed_search(engine, memory, score=0.5)

        without = envelope_ok(
            api.as_user(0).client.post("/context", json={"workspace_id": str(workspace_id), "query": "fact"})
        )
        with_project = envelope_ok(
            api.as_user(0).client.post(
                "/context",
                json={"workspace_id": str(workspace_id), "query": "fact", "project_id": str(project_id)},
            )
        )
        assert with_project["items"][0]["score"] > without["items"][0]["score"]
        assert with_project["items"][0]["project_match"] is True
        assert without["items"][0]["project_match"] is False
        assert engine_id

    def test_deleted_memories_never_enter_context(self, api, two_tenants, engine):
        workspace_id = two_tenants["workspace_a"].id
        memory = make_memory(api, workspace_id, "secret fact")
        api.as_user(0).client.post(f"/memories/{memory['id']}/forget", json={})
        seed_search(engine, memory, score=0.99)

        data = envelope_ok(
            api.as_user(0).client.post("/context", json={"workspace_id": str(workspace_id), "query": "secret"})
        )
        assert data["items"] == []

    def test_context_in_another_workspace_is_404(self, api, two_tenants, engine):
        response = api.as_user(1).client.post(
            "/context",
            json={"workspace_id": str(two_tenants["workspace_a"].id), "query": "x"},
        )
        envelope_error(response, "NOT_FOUND", 404)

    def test_zero_budget_is_rejected(self, api, two_tenants, engine):
        response = api.as_user(0).client.post(
            "/context",
            json={"workspace_id": str(two_tenants["workspace_a"].id), "query": "x", "token_budget": 0},
        )
        envelope_error(response, "VALIDATION_FAILED", 400)
