"""Memory API tests (P2).

Covers the engine-sync state machine, the version history, provenance, and the
tenant boundary on the memory routes. Every test runs against the fake engine,
so nothing here needs a live LLM.
"""

import uuid

from envelope import envelope_error, envelope_ok
from fake_engine import seed_engine_memory
from ume_app.engine.memory_adapter import EngineMemory


def create_body(workspace_id, **overrides):
    body = {
        "workspace_id": str(workspace_id),
        "messages": [{"role": "user", "content": "I prefer dark mode"}],
        "tags": ["ui"],
    }
    body.update(overrides)
    return body


def find_version(api, memory_id, change_type):
    versions = envelope_ok(api.as_user(0).client.get(f"/memories/{memory_id}/versions"))
    return [v for v in versions if v["change_type"] == change_type]


class TestCreate:
    def test_create_returns_a_ready_record(self, api, two_tenants, engine):
        workspace_id = two_tenants["workspace_a"].id
        data = envelope_ok(api.as_user(0).client.post("/memories", json=create_body(workspace_id)), 201)
        assert data["status"] == "active"
        assert data["engine_state"] == "ready"
        assert data["current_text"] == "I prefer dark mode"
        assert data["engine_memory_id"].startswith("eng-")
        assert data["tags"] == ["ui"]

    def test_create_writes_version_one(self, api, two_tenants, engine):
        data = envelope_ok(
            api.as_user(0).client.post("/memories", json=create_body(two_tenants["workspace_a"].id)), 201
        )
        versions = envelope_ok(api.as_user(0).client.get(f"/memories/{data['id']}/versions"))
        assert len(versions) == 1
        assert versions[0]["version_no"] == 1
        assert versions[0]["change_type"] == "created"

    def test_create_passes_the_workspace_scope_into_the_engine(self, api, two_tenants, engine):
        """The filter must travel with the query, not be applied to the results."""
        workspace_id = two_tenants["workspace_a"].id
        envelope_ok(api.as_user(0).client.post("/memories", json=create_body(workspace_id)), 201)
        scope = engine.scopes_for("add")[0]
        assert scope.workspace_id == workspace_id

    def test_create_links_projects(self, api, two_tenants, engine):
        workspace_id = two_tenants["workspace_a"].id
        project_id = two_tenants["project_a"].id
        envelope_ok(
            api.as_user(0).client.post("/memories", json=create_body(workspace_id, project_ids=[str(project_id)])),
            201,
        )
        listed = envelope_ok(
            api.as_user(0).client.get(f"/memories?workspace_id={workspace_id}&project_id={project_id}")
        )
        assert len(listed["items"]) == 1

    def test_project_from_another_workspace_is_rejected(self, api, two_tenants, engine):
        response = api.as_user(0).client.post(
            "/memories",
            json=create_body(two_tenants["workspace_a"].id, project_ids=[str(two_tenants["project_b"].id)]),
        )
        envelope_error(response, "VALIDATION_FAILED", 400)

    def test_empty_messages_are_rejected(self, api, two_tenants, engine):
        response = api.as_user(0).client.post("/memories", json=create_body(two_tenants["workspace_a"].id, messages=[]))
        envelope_error(response, "VALIDATION_FAILED", 400)

    def test_creation_into_another_workspace_is_404(self, api, two_tenants, engine):
        response = api.as_user(1).client.post("/memories", json=create_body(two_tenants["workspace_a"].id))
        envelope_error(response, "NOT_FOUND", 404)


class TestEngineFailure:
    def test_a_failed_engine_write_marks_the_record_failed(self, api, two_tenants, engine):
        engine.fail_on.add("add")
        response = api.as_user(0).client.post("/memories", json=create_body(two_tenants["workspace_a"].id))
        envelope_error(response, "INTERNAL_ERROR", 500)

        # The business row survives in `failed` so the write is retryable.
        listed = envelope_ok(
            api.as_user(0).client.get(f"/memories?workspace_id={two_tenants['workspace_a'].id}&include_deleted=true")
        )
        assert listed["items"][0]["engine_state"] == "failed"
        assert listed["items"][0]["engine_error"]

    def test_the_stored_error_does_not_leak_the_engine_message(self, api, two_tenants, engine):
        engine.fail_on.add("add")
        api.as_user(0).client.post("/memories", json=create_body(two_tenants["workspace_a"].id))
        listed = envelope_ok(
            api.as_user(0).client.get(f"/memories?workspace_id={two_tenants['workspace_a'].id}&include_deleted=true")
        )
        stored = listed["items"][0]["engine_error"]
        assert "very long message" not in stored
        assert "RuntimeError" in stored

    def test_a_failed_record_can_be_retried(self, api, two_tenants, engine):
        engine.fail_on.add("add")
        api.as_user(0).client.post("/memories", json=create_body(two_tenants["workspace_a"].id))
        listed = envelope_ok(
            api.as_user(0).client.get(f"/memories?workspace_id={two_tenants['workspace_a'].id}&include_deleted=true")
        )
        failed_id = listed["items"][0]["id"]

        engine.fail_on.clear()
        retried = envelope_ok(
            api.as_user(0).client.post(
                f"/memories/{failed_id}/retry",
                json={"messages": [{"role": "user", "content": "I prefer dark mode"}]},
            )
        )
        assert retried["engine_state"] == "ready"
        assert retried["engine_error"] is None

    def test_retrying_a_ready_record_is_refused(self, api, two_tenants, engine):
        created = envelope_ok(
            api.as_user(0).client.post("/memories", json=create_body(two_tenants["workspace_a"].id)), 201
        )
        response = api.as_user(0).client.post(
            f"/memories/{created['id']}/retry",
            json={"messages": [{"role": "user", "content": "x"}]},
        )
        envelope_error(response, "CONFLICT", 409)


class TestUpdate:
    def test_update_creates_a_new_version(self, api, two_tenants, engine):
        created = envelope_ok(
            api.as_user(0).client.post("/memories", json=create_body(two_tenants["workspace_a"].id)), 201
        )
        updated = envelope_ok(
            api.as_user(0).client.patch(
                f"/memories/{created['id']}",
                json={"text": "I prefer light mode", "change_reason": "user corrected it"},
            )
        )
        assert updated["current_text"] == "I prefer light mode"
        versions = envelope_ok(api.as_user(0).client.get(f"/memories/{created['id']}/versions"))
        assert [v["version_no"] for v in versions] == [1, 2]
        assert versions[1]["change_type"] == "updated"
        assert versions[1]["change_reason"] == "user corrected it"

    def test_update_reaches_the_engine(self, api, two_tenants, engine):
        created = envelope_ok(
            api.as_user(0).client.post("/memories", json=create_body(two_tenants["workspace_a"].id)), 201
        )
        api.as_user(0).client.patch(f"/memories/{created['id']}", json={"text": "changed"})
        assert engine.calls_named("update")[0]["text"] == "changed"

    def test_updating_another_tenants_memory_is_404(self, api, two_tenants, engine):
        created = envelope_ok(
            api.as_user(0).client.post("/memories", json=create_body(two_tenants["workspace_a"].id)), 201
        )
        response = api.as_user(1).client.patch(f"/memories/{created['id']}", json={"text": "hijacked"})
        envelope_error(response, "NOT_FOUND", 404)


class TestArchiveAndRestore:
    def test_archive_then_restore_produces_a_new_version(self, api, two_tenants, engine):
        created = envelope_ok(
            api.as_user(0).client.post("/memories", json=create_body(two_tenants["workspace_a"].id)), 201
        )
        api.as_user(0).client.patch(f"/memories/{created['id']}", json={"text": "second text"})
        api.as_user(0).client.post(f"/memories/{created['id']}/archive", json={"reason": "stale"})

        archived = envelope_ok(api.as_user(0).client.get(f"/memories/{created['id']}"))
        assert archived["status"] == "archived"

        restored = envelope_ok(api.as_user(0).client.post(f"/memories/{created['id']}/restore", json={"version_no": 1}))
        assert restored["status"] == "active"
        assert restored["current_text"] == "I prefer dark mode"

        versions = envelope_ok(api.as_user(0).client.get(f"/memories/{created['id']}/versions"))
        # History is append-only: the restore is version 4, not a truncation.
        assert [v["version_no"] for v in versions] == [1, 2, 3, 4]
        assert versions[3]["change_type"] == "restored"

    def test_restoring_the_current_version_is_refused(self, api, two_tenants, engine):
        created = envelope_ok(
            api.as_user(0).client.post("/memories", json=create_body(two_tenants["workspace_a"].id)), 201
        )
        api.as_user(0).client.post(f"/memories/{created['id']}/archive", json={})
        envelope_error(
            api.as_user(0).client.post(f"/memories/{created['id']}/restore", json={"version_no": 1}), "CONFLICT", 409
        )

    def test_restoring_an_unknown_version_is_404(self, api, two_tenants, engine):
        created = envelope_ok(
            api.as_user(0).client.post("/memories", json=create_body(two_tenants["workspace_a"].id)), 201
        )
        api.as_user(0).client.post(f"/memories/{created['id']}/archive", json={})
        envelope_error(
            api.as_user(0).client.post(f"/memories/{created['id']}/restore", json={"version_no": 99}), "NOT_FOUND", 404
        )

    def test_restoring_an_active_memory_is_refused(self, api, two_tenants, engine):
        created = envelope_ok(
            api.as_user(0).client.post("/memories", json=create_body(two_tenants["workspace_a"].id)), 201
        )
        envelope_error(
            api.as_user(0).client.post(f"/memories/{created['id']}/restore", json={"version_no": 1}), "CONFLICT", 409
        )

    def test_archiving_twice_is_refused(self, api, two_tenants, engine):
        created = envelope_ok(
            api.as_user(0).client.post("/memories", json=create_body(two_tenants["workspace_a"].id)), 201
        )
        api.as_user(0).client.post(f"/memories/{created['id']}/archive", json={})
        envelope_error(api.as_user(0).client.post(f"/memories/{created['id']}/archive", json={}), "CONFLICT", 409)


class TestForget:
    def test_forget_deletes_from_the_engine_and_tombstones_the_row(self, api, two_tenants, engine):
        created = envelope_ok(
            api.as_user(0).client.post("/memories", json=create_body(two_tenants["workspace_a"].id)), 201
        )
        forgotten = envelope_ok(
            api.as_user(0).client.post(f"/memories/{created['id']}/forget", json={"reason": "gdpr"})
        )
        assert forgotten["status"] == "deleted"
        assert forgotten["engine_state"] == "deleted"
        assert forgotten["deleted_at"] is not None
        assert engine.calls_named("delete")[0]["memory_id"] == created["engine_memory_id"]

    def test_a_deleted_memory_is_hidden_from_the_default_listing(self, api, two_tenants, engine):
        created = envelope_ok(
            api.as_user(0).client.post("/memories", json=create_body(two_tenants["workspace_a"].id)), 201
        )
        api.as_user(0).client.post(f"/memories/{created['id']}/forget", json={})
        listed = envelope_ok(api.as_user(0).client.get(f"/memories?workspace_id={two_tenants['workspace_a'].id}"))
        assert listed["items"] == []

    def test_forget_writes_a_version_entry(self, api, two_tenants, engine):
        created = envelope_ok(
            api.as_user(0).client.post("/memories", json=create_body(two_tenants["workspace_a"].id)), 201
        )
        api.as_user(0).client.post(f"/memories/{created['id']}/forget", json={"reason": "gdpr"})
        assert find_version(api, created["id"], "deleted")

    def test_forgetting_twice_is_refused(self, api, two_tenants, engine):
        created = envelope_ok(
            api.as_user(0).client.post("/memories", json=create_body(two_tenants["workspace_a"].id)), 201
        )
        api.as_user(0).client.post(f"/memories/{created['id']}/forget", json={})
        envelope_error(api.as_user(0).client.post(f"/memories/{created['id']}/forget", json={}), "CONFLICT", 409)

    def test_a_failed_engine_delete_leaves_a_resumable_state(self, api, two_tenants, engine):
        created = envelope_ok(
            api.as_user(0).client.post("/memories", json=create_body(two_tenants["workspace_a"].id)), 201
        )
        engine.fail_on.add("delete")
        response = api.as_user(0).client.post(f"/memories/{created['id']}/forget", json={})
        envelope_error(response, "INTERNAL_ERROR", 500)

        # Still readable, still not reported as deleted.
        still = envelope_ok(api.as_user(0).client.get(f"/memories/{created['id']}"))
        assert still["status"] == "active"
        assert still["engine_state"] == "deleting"

    def test_forgetting_another_tenants_memory_is_404(self, api, two_tenants, engine):
        created = envelope_ok(
            api.as_user(0).client.post("/memories", json=create_body(two_tenants["workspace_a"].id)), 201
        )
        envelope_error(api.as_user(1).client.post(f"/memories/{created['id']}/forget", json={}), "NOT_FOUND", 404)


class TestSources:
    def test_provenance_is_recorded(self, api, two_tenants, engine):
        workspace_id = two_tenants["workspace_a"].id
        conversation = envelope_ok(
            api.as_user(0).client.post("/conversations", json={"workspace_id": str(workspace_id)}), 201
        )
        created = envelope_ok(
            api.as_user(0).client.post(
                "/memories",
                json=create_body(
                    workspace_id,
                    sources=[
                        {
                            "conversation_id": conversation["id"],
                            "source_type": "conversation",
                            "extraction_method": "llm",
                            "evidence_excerpt": "I prefer dark mode",
                            "confidence": 0.9,
                        }
                    ],
                ),
            ),
            201,
        )
        sources = envelope_ok(api.as_user(0).client.get(f"/memories/{created['id']}/sources"))
        assert len(sources) == 1
        assert sources[0]["conversation_id"] == conversation["id"]
        assert sources[0]["confidence"] == 0.9

    def test_forgetting_clears_the_evidence_but_keeps_provenance(self, api, two_tenants, engine):
        workspace_id = two_tenants["workspace_a"].id
        created = envelope_ok(
            api.as_user(0).client.post(
                "/memories",
                json=create_body(
                    workspace_id,
                    sources=[{"source_type": "conversation", "extraction_method": "llm", "evidence_excerpt": "x"}],
                ),
            ),
            201,
        )
        api.as_user(0).client.post(f"/memories/{created['id']}/forget", json={})
        sources = envelope_ok(api.as_user(0).client.get(f"/memories/{created['id']}/sources"))
        assert len(sources) == 1
        assert sources[0]["evidence_excerpt"] is None

    def test_sources_of_another_tenants_memory_are_404(self, api, two_tenants, engine):
        created = envelope_ok(
            api.as_user(0).client.post("/memories", json=create_body(two_tenants["workspace_a"].id)), 201
        )
        envelope_error(api.as_user(1).client.get(f"/memories/{created['id']}/sources"), "NOT_FOUND", 404)


class TestSearch:
    def test_search_returns_projections(self, api, two_tenants, engine):
        workspace_id = two_tenants["workspace_a"].id
        api.as_user(0).client.post("/memories", json=create_body(workspace_id))
        hits = envelope_ok(
            api.as_user(0).client.post("/memory-search", json={"workspace_id": str(workspace_id), "query": "dark mode"})
        )
        assert len(hits) == 1
        assert hits[0]["memory"]["current_text"] == "I prefer dark mode"
        assert hits[0]["engine_id"].startswith("eng-")

    def test_search_scope_travels_into_the_engine_call(self, api, two_tenants, engine):
        workspace_id = two_tenants["workspace_a"].id
        api.as_user(0).client.post("/memories", json=create_body(workspace_id))
        api.as_user(0).client.post("/memory-search", json={"workspace_id": str(workspace_id), "query": "dark"})
        assert engine.scopes_for("search")[0].workspace_id == workspace_id

    def test_search_never_returns_another_tenants_memories(self, api, two_tenants, engine):
        """An engine hit whose workspace differs is dropped, not rendered."""
        workspace_id = two_tenants["workspace_a"].id
        api.as_user(0).client.post("/memories", json=create_body(workspace_id))
        foreign_id = seed_engine_memory(engine, "secret from another tenant", uuid.uuid4())
        engine.search_result = [EngineMemory(id=foreign_id, text="secret from another tenant")]
        hits = envelope_ok(
            api.as_user(0).client.post("/memory-search", json={"workspace_id": str(workspace_id), "query": "secret"})
        )
        assert hits == []

    def test_search_hides_a_forgotten_memory(self, api, two_tenants, engine):
        """A deleted record must not come back through search.

        The engine still holds the row, so only the business-side status check
        can keep it out of the results.
        """
        workspace_id = two_tenants["workspace_a"].id
        created = envelope_ok(api.as_user(0).client.post("/memories", json=create_body(workspace_id)), 201)
        api.as_user(0).client.post(f"/memories/{created['id']}/forget", json={})

        engine.search_result = [EngineMemory(id=created["engine_memory_id"], text=created["current_text"])]
        hits = envelope_ok(
            api.as_user(0).client.post("/memory-search", json={"workspace_id": str(workspace_id), "query": "dark mode"})
        )
        assert hits == []

    def test_search_still_returns_an_archived_memory(self, api, two_tenants, engine):
        """Archiving is business-only, so the memory is still readable."""
        workspace_id = two_tenants["workspace_a"].id
        created = envelope_ok(api.as_user(0).client.post("/memories", json=create_body(workspace_id)), 201)
        api.as_user(0).client.post(f"/memories/{created['id']}/archive", json={})

        engine.search_result = [EngineMemory(id=created["engine_memory_id"], text=created["current_text"])]
        hits = envelope_ok(
            api.as_user(0).client.post("/memory-search", json={"workspace_id": str(workspace_id), "query": "dark mode"})
        )
        assert len(hits) == 1
        assert hits[0]["memory"]["status"] == "archived"

    def test_search_in_another_workspace_is_404(self, api, two_tenants, engine):
        response = api.as_user(1).client.post(
            "/memory-search",
            json={"workspace_id": str(two_tenants["workspace_a"].id), "query": "dark"},
        )
        envelope_error(response, "NOT_FOUND", 404)


class TestMemoryIsolation:
    def test_listing_is_workspace_scoped(self, api, two_tenants, engine):
        api.as_user(0).client.post("/memories", json=create_body(two_tenants["workspace_a"].id))
        api.as_user(1).client.post("/memories", json=create_body(two_tenants["workspace_b"].id))
        mine = envelope_ok(api.as_user(0).client.get(f"/memories?workspace_id={two_tenants['workspace_a'].id}"))
        assert len(mine["items"]) == 1
        assert mine["items"][0]["workspace_id"] == str(two_tenants["workspace_a"].id)

    def test_unknown_memory_is_404(self, api):
        envelope_error(api.as_user(0).client.get(f"/memories/{uuid.uuid4()}"), "NOT_FOUND", 404)

    def test_viewer_cannot_write(self, api, db, two_tenants, engine):
        from ume_app.models.workspace import WorkspaceMember

        db.add(WorkspaceMember(workspace_id=two_tenants["workspace_a"].id, user_id=api.users[2].id, role="viewer"))
        db.commit()
        response = api.as_user(2).client.post("/memories", json=create_body(two_tenants["workspace_a"].id))
        envelope_error(response, "PERMISSION_DENIED", 403)
