"""Conversation, message and import API tests (P1).

The two P1 exit conditions live here: repeated imports must not create
duplicate rows, and a cross-workspace id must never resolve.
"""

import uuid
from datetime import datetime, timezone

from envelope import envelope_error, envelope_ok

WS_A = "workspace-a"
WS_B = "workspace-b"


def _ts(minute: int) -> str:
    return f"2026-10-01T12:{minute:02d}:00Z"


def message(minute: int, *, content: str | None = None, external: str | None = None, role: str = "user"):
    return {
        "role": role,
        "content": content if content is not None else f"message {minute}",
        "timestamp": _ts(minute),
        "external_message_id": external,
    }


def idem(n=None):
    """A fresh Idempotency-Key. Pass n to reuse a specific one."""
    if n is None:
        _key_counter[0] += 1
        n = _key_counter[0]
    return {"Idempotency-Key": f"key-{n}"}


_key_counter = [0]


def import_payload(workspace_id, **overrides):
    payload = {
        "format_version": "1.0",
        "workspace_id": str(workspace_id),
        "source": "generic",
        "title": "Imported",
        "messages": [message(1, external="m1"), message(2, external="m2"), message(3, external="m3")],
    }
    payload.update(overrides)
    return payload


class TestConversations:
    def test_create_and_read_back(self, api, two_tenants):
        workspace_id = two_tenants["workspace_a"].id
        created = envelope_ok(
            api.as_user(0).client.post("/conversations", json={"workspace_id": str(workspace_id), "title": "Chat"}),
            201,
        )
        assert created["title"] == "Chat"
        assert created["status"] == "active"
        assert created["last_message_at"] is None

        fetched = envelope_ok(api.as_user(0).client.get(f"/conversations/{created['id']}"))
        assert fetched["id"] == created["id"]

    def test_list_is_workspace_scoped(self, api, two_tenants):
        workspace_id = two_tenants["workspace_a"].id
        api.as_user(0).client.post("/conversations", json={"workspace_id": str(workspace_id)})
        data = envelope_ok(api.as_user(0).client.get(f"/conversations?workspace_id={workspace_id}"))
        assert len(data["items"]) == 1
        assert all(item["workspace_id"] == str(workspace_id) for item in data["items"])

    def test_patch_and_delete(self, api, two_tenants):
        workspace_id = two_tenants["workspace_a"].id
        created = envelope_ok(
            api.as_user(0).client.post("/conversations", json={"workspace_id": str(workspace_id)}), 201
        )
        patched = envelope_ok(api.as_user(0).client.patch(f"/conversations/{created['id']}", json={"title": "Renamed"}))
        assert patched["title"] == "Renamed"
        envelope_ok(api.as_user(0).client.delete(f"/conversations/{created['id']}"))
        envelope_error(api.as_user(0).client.get(f"/conversations/{created['id']}"), "NOT_FOUND", 404)

    def test_workspace_id_is_required(self, api, two_tenants):
        response = api.as_user(0).client.post("/conversations", json={"title": "orphan"})
        envelope_error(response, "VALIDATION_FAILED", 400)

    def test_list_without_workspace_id_is_rejected(self, api):
        envelope_error(api.as_user(0).client.get("/conversations"), "VALIDATION_FAILED", 400)

    def test_unknown_conversation_is_404(self, api):
        envelope_error(api.as_user(0).client.get(f"/conversations/{uuid.uuid4()}"), "NOT_FOUND", 404)


class TestConversationIsolation:
    def test_reading_another_tenants_conversation_is_404(self, api, two_tenants):
        workspace_id = two_tenants["workspace_a"].id
        created = envelope_ok(
            api.as_user(0).client.post("/conversations", json={"workspace_id": str(workspace_id)}), 201
        )
        envelope_error(api.as_user(1).client.get(f"/conversations/{created['id']}"), "NOT_FOUND", 404)

    def test_writing_to_another_tenants_conversation_is_404(self, api, two_tenants):
        workspace_id = two_tenants["workspace_a"].id
        created = envelope_ok(
            api.as_user(0).client.post("/conversations", json={"workspace_id": str(workspace_id)}), 201
        )
        response = api.as_user(1).client.patch(f"/conversations/{created['id']}", json={"title": "hijacked"})
        envelope_error(response, "NOT_FOUND", 404)

    def test_messages_of_another_tenants_conversation_are_404(self, api, two_tenants):
        workspace_id = two_tenants["workspace_a"].id
        created = envelope_ok(
            api.as_user(0).client.post("/conversations", json={"workspace_id": str(workspace_id)}), 201
        )
        envelope_error(api.as_user(1).client.get(f"/conversations/{created['id']}/messages"), "NOT_FOUND", 404)

    def test_creating_in_another_workspace_is_404(self, api, two_tenants):
        workspace_id = two_tenants["workspace_a"].id
        response = api.as_user(1).client.post("/conversations", json={"workspace_id": str(workspace_id)})
        envelope_error(response, "NOT_FOUND", 404)

    def test_conversation_survives_a_cross_tenant_write_attempt(self, api, two_tenants):
        workspace_id = two_tenants["workspace_a"].id
        created = envelope_ok(
            api.as_user(0).client.post("/conversations", json={"workspace_id": str(workspace_id)}), 201
        )
        api.as_user(1).client.delete(f"/conversations/{created['id']}")
        assert envelope_ok(api.as_user(0).client.get(f"/conversations/{created['id']}"))["title"] == created["title"]


class TestMessages:
    def test_append_updates_conversation_bookmarks(self, api, two_tenants):
        workspace_id = two_tenants["workspace_a"].id
        created = envelope_ok(
            api.as_user(0).client.post("/conversations", json={"workspace_id": str(workspace_id)}), 201
        )
        envelope_ok(
            api.as_user(0).client.post(
                f"/conversations/{created['id']}/messages", json={"messages": [message(1), message(5)]}
            ),
            201,
        )
        fetched = envelope_ok(api.as_user(0).client.get(f"/conversations/{created['id']}"))
        assert fetched["last_message_at"].startswith("2026-10-01T12:05")
        assert fetched["started_at"].startswith("2026-10-01T12:01")

    def test_browse_is_oldest_first(self, api, two_tenants):
        workspace_id = two_tenants["workspace_a"].id
        created = envelope_ok(
            api.as_user(0).client.post("/conversations", json={"workspace_id": str(workspace_id)}), 201
        )
        api.as_user(0).client.post(
            f"/conversations/{created['id']}/messages",
            json={"messages": [message(3), message(1), message(2)]},
        )
        data = envelope_ok(api.as_user(0).client.get(f"/conversations/{created['id']}/messages"))
        assert [item["message_at"] for item in data["items"]] == sorted(item["message_at"] for item in data["items"])

    def test_message_requires_content_or_ref(self, api, two_tenants):
        workspace_id = two_tenants["workspace_a"].id
        created = envelope_ok(
            api.as_user(0).client.post("/conversations", json={"workspace_id": str(workspace_id)}), 201
        )
        response = api.as_user(0).client.post(
            f"/conversations/{created['id']}/messages",
            json={"messages": [{"role": "user", "timestamp": _ts(1)}]},
        )
        envelope_error(response, "VALIDATION_FAILED", 400)

    def test_naive_timestamp_is_rejected(self, api, two_tenants):
        workspace_id = two_tenants["workspace_a"].id
        created = envelope_ok(
            api.as_user(0).client.post("/conversations", json={"workspace_id": str(workspace_id)}), 201
        )
        response = api.as_user(0).client.post(
            f"/conversations/{created['id']}/messages",
            json={"messages": [{"role": "user", "content": "x", "timestamp": "2026-10-01T12:01:00"}]},
        )
        envelope_error(response, "VALIDATION_FAILED", 400)

    def test_unknown_role_is_rejected(self, api, two_tenants):
        workspace_id = two_tenants["workspace_a"].id
        created = envelope_ok(
            api.as_user(0).client.post("/conversations", json={"workspace_id": str(workspace_id)}), 201
        )
        response = api.as_user(0).client.post(
            f"/conversations/{created['id']}/messages",
            json={"messages": [{"role": "robot", "content": "x", "timestamp": _ts(1)}]},
        )
        envelope_error(response, "VALIDATION_FAILED", 400)

    def test_batch_append_is_idempotent_per_key(self, api, two_tenants):
        workspace_id = two_tenants["workspace_a"].id
        created = envelope_ok(
            api.as_user(0).client.post("/conversations", json={"workspace_id": str(workspace_id)}), 201
        )
        body = {"messages": [message(1), message(2)]}
        headers = {"Idempotency-Key": "append-1"}

        first = envelope_ok(
            api.as_user(0).client.post(f"/conversations/{created['id']}/messages", json=body, headers=headers), 201
        )
        assert first["inserted"] == 2

        replay = envelope_ok(
            api.as_user(0).client.post(f"/conversations/{created['id']}/messages", json=body, headers=headers), 201
        )
        assert replay["inserted"] == 2
        assert (
            envelope_ok(api.as_user(0).client.get(f"/conversations/{created['id']}/messages"))["items"].__len__() == 2
        )

    def test_same_key_different_body_conflicts(self, api, two_tenants):
        workspace_id = two_tenants["workspace_a"].id
        created = envelope_ok(
            api.as_user(0).client.post("/conversations", json={"workspace_id": str(workspace_id)}), 201
        )
        headers = {"Idempotency-Key": "append-2"}
        api.as_user(0).client.post(
            f"/conversations/{created['id']}/messages", json={"messages": [message(1)]}, headers=headers
        )
        response = api.as_user(0).client.post(
            f"/conversations/{created['id']}/messages", json={"messages": [message(2)]}, headers=headers
        )
        envelope_error(response, "CONFLICT", 409)


class TestImport:
    def test_preview_writes_nothing(self, api, two_tenants):
        workspace_id = two_tenants["workspace_a"].id
        data = envelope_ok(
            api.as_user(0).client.post("/conversations/imports/preview", json=import_payload(workspace_id))
        )
        assert data["valid"] is True
        assert data["message_count"] == 3
        assert data["duplicate_count"] == 0
        assert envelope_ok(api.as_user(0).client.get(f"/conversations?workspace_id={workspace_id}"))["items"] == []

    def test_import_creates_the_conversation_and_messages(self, api, two_tenants):
        workspace_id = two_tenants["workspace_a"].id
        job = envelope_ok(
            api.as_user(0).client.post("/conversations/imports", json=import_payload(workspace_id), headers=idem()),
            201,
        )
        assert job["status"] == "completed"
        assert job["result_summary"]["inserted"] == 3
        assert job["result_summary"]["conversation_action"] == "created"

        conversations = envelope_ok(api.as_user(0).client.get(f"/conversations?workspace_id={workspace_id}"))
        assert len(conversations["items"]) == 1
        messages = envelope_ok(api.as_user(0).client.get(f"/conversations/{conversations['items'][0]['id']}/messages"))
        assert len(messages["items"]) == 3

    def test_repeated_import_creates_no_duplicates(self, api, two_tenants):
        """P1 exit condition: importing the same payload twice is a no-op."""
        workspace_id = two_tenants["workspace_a"].id
        payload = import_payload(workspace_id, external_conversation_id="ext-1")
        first = envelope_ok(api.as_user(0).client.post("/conversations/imports", json=payload, headers=idem()), 201)
        second = envelope_ok(api.as_user(0).client.post("/conversations/imports", json=payload, headers=idem()), 201)

        assert first["result_summary"]["inserted"] == 3
        assert second["result_summary"]["inserted"] == 0
        assert second["result_summary"]["skipped_duplicates"] == 3

        conversations = envelope_ok(api.as_user(0).client.get(f"/conversations?workspace_id={workspace_id}"))
        assert len(conversations["items"]) == 1, "the external conversation id must resolve to one row"
        messages = envelope_ok(api.as_user(0).client.get(f"/conversations/{conversations['items'][0]['id']}/messages"))
        assert len(messages["items"]) == 3

    def test_same_idempotency_key_replays_the_first_job(self, api, two_tenants):
        workspace_id = two_tenants["workspace_a"].id
        headers = {"Idempotency-Key": "import-1"}
        payload = import_payload(workspace_id)
        first = envelope_ok(api.as_user(0).client.post("/conversations/imports", json=payload, headers=headers), 201)
        second = envelope_ok(api.as_user(0).client.post("/conversations/imports", json=payload, headers=headers), 201)
        assert second["id"] == first["id"]
        assert second["replayed"] is True

    def test_same_key_different_body_conflicts(self, api, two_tenants):
        workspace_id = two_tenants["workspace_a"].id
        headers = {"Idempotency-Key": "import-2"}
        api.as_user(0).client.post("/conversations/imports", json=import_payload(workspace_id), headers=headers)
        other = import_payload(workspace_id, title="different")
        response = api.as_user(0).client.post("/conversations/imports", json=other, headers=headers)
        envelope_error(response, "CONFLICT", 409)

    def test_content_hash_dedupes_messages_without_external_ids(self, api, two_tenants):
        workspace_id = two_tenants["workspace_a"].id
        payload = import_payload(
            workspace_id,
            external_conversation_id="ext-hash",
            messages=[message(1, content="same body"), message(1, content="same body")],
        )
        job = envelope_ok(api.as_user(0).client.post("/conversations/imports", json=payload, headers=idem()), 201)
        assert job["result_summary"]["inserted"] == 1
        assert job["result_summary"]["skipped_duplicates"] == 1

    def test_validation_failure_marks_the_job(self, api, two_tenants):
        workspace_id = two_tenants["workspace_a"].id
        payload = import_payload(workspace_id, messages=[message(1, external="dup"), message(2, external="dup")])
        job = envelope_ok(api.as_user(0).client.post("/conversations/imports", json=payload, headers=idem()), 201)
        assert job["status"] == "validation_failed"
        assert job["error_summary"]["code"] == "VALIDATION_FAILED"

    def test_validation_failure_writes_no_messages(self, api, two_tenants):
        workspace_id = two_tenants["workspace_a"].id
        payload = import_payload(workspace_id, messages=[message(1, external="dup"), message(2, external="dup")])
        api.as_user(0).client.post("/conversations/imports", json=payload, headers=idem())
        assert envelope_ok(api.as_user(0).client.get(f"/conversations?workspace_id={workspace_id}"))["items"] == []

    def test_foreign_project_id_fails_validation(self, api, two_tenants):
        payload = import_payload(two_tenants["workspace_a"].id, project_id=str(two_tenants["project_b"].id))
        job = envelope_ok(api.as_user(0).client.post("/conversations/imports", json=payload, headers=idem()), 201)
        assert job["status"] == "validation_failed"

    def test_unsupported_format_version_is_rejected(self, api, two_tenants):
        payload = import_payload(two_tenants["workspace_a"].id, format_version="2.0")
        envelope_error(
            api.as_user(0).client.post("/conversations/imports", json=payload, headers=idem()),
            "VALIDATION_FAILED",
            400,
        )

    def test_import_into_another_workspace_is_404(self, api, two_tenants):
        response = api.as_user(1).client.post(
            "/conversations/imports",
            json=import_payload(two_tenants["workspace_a"].id),
            headers=idem(),
        )
        envelope_error(response, "NOT_FOUND", 404)

    def test_import_without_an_idempotency_key_is_rejected(self, api, two_tenants):
        """The header is required: deriving it from the body would hide the dedup path."""
        response = api.as_user(0).client.post(
            "/conversations/imports", json=import_payload(two_tenants["workspace_a"].id)
        )
        envelope_error(response, "VALIDATION_FAILED", 400)

    def test_imported_conversation_is_invisible_to_another_tenant(self, api, two_tenants):
        workspace_id = two_tenants["workspace_a"].id
        api.as_user(0).client.post("/conversations/imports", json=import_payload(workspace_id), headers=idem())
        listed = envelope_ok(api.as_user(1).client.get(f"/conversations?workspace_id={two_tenants['workspace_b'].id}"))
        assert listed["items"] == []


class TestImportJobs:
    def test_job_is_readable_by_its_workspace(self, api, two_tenants):
        job = envelope_ok(
            api.as_user(0).client.post(
                "/conversations/imports", json=import_payload(two_tenants["workspace_a"].id), headers=idem()
            ),
            201,
        )
        fetched = envelope_ok(api.as_user(0).client.get(f"/import-jobs/{job['id']}"))
        assert fetched["status"] == "completed"

    def test_job_is_invisible_to_another_tenant(self, api, two_tenants):
        job = envelope_ok(
            api.as_user(0).client.post(
                "/conversations/imports", json=import_payload(two_tenants["workspace_a"].id), headers=idem()
            ),
            201,
        )
        envelope_error(api.as_user(1).client.get(f"/import-jobs/{job['id']}"), "NOT_FOUND", 404)

    def test_unknown_job_is_404(self, api):
        envelope_error(api.as_user(0).client.get(f"/import-jobs/{uuid.uuid4()}"), "NOT_FOUND", 404)

    def test_retry_of_a_failed_import(self, api, two_tenants):
        workspace_id = two_tenants["workspace_a"].id
        payload = import_payload(workspace_id, messages=[message(1, external="dup"), message(2, external="dup")])
        job = envelope_ok(api.as_user(0).client.post("/conversations/imports", json=payload, headers=idem()), 201)
        retried = envelope_ok(api.as_user(0).client.post(f"/import-jobs/{job['id']}/retry"))
        assert retried["status"] == "validating"
        assert retried["error_summary"] == {}

    def test_retry_of_a_completed_import_is_rejected(self, api, two_tenants):
        job = envelope_ok(
            api.as_user(0).client.post(
                "/conversations/imports", json=import_payload(two_tenants["workspace_a"].id), headers=idem()
            ),
            201,
        )
        envelope_error(api.as_user(0).client.post(f"/import-jobs/{job['id']}/retry"), "CONFLICT", 409)

    def test_retry_across_tenants_is_404(self, api, two_tenants):
        payload = import_payload(
            two_tenants["workspace_a"].id, messages=[message(1, external="d"), message(2, external="d")]
        )
        job = envelope_ok(api.as_user(0).client.post("/conversations/imports", json=payload, headers=idem()), 201)
        envelope_error(api.as_user(1).client.post(f"/import-jobs/{job['id']}/retry"), "NOT_FOUND", 404)
