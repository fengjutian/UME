"""Connector tests (P4).

The exit condition for P4 is that two clients share a project's memories and
that a revoke refuses the very next request, so both are asserted here over
HTTP with two different connector credentials.
"""

import pytest
from envelope import envelope_error, envelope_ok
from ume_app.auth.credentials import (
    TOKEN_PREFIX,
    looks_like_connector_token,
    normalise_scopes,
)
from ume_app.domain.errors import ValidationError


def create_connector(api, workspace_id, *, name="agent", scopes=None, project_id=None, as_user=0):
    body = {
        "workspace_id": str(workspace_id),
        "name": name,
        "connector_type": "cli",
    }
    if scopes is not None:
        body["scopes"] = scopes
    if project_id is not None:
        body["project_id"] = str(project_id)
    data = envelope_ok(api.as_user(as_user).client.post("/connectors", json=body), 201)
    return data


class TestCredentialIssuing:
    def test_create_returns_a_one_time_credential(self, api, two_tenants):
        data = create_connector(api, two_tenants["workspace_a"].id)
        assert data["credential"].startswith(TOKEN_PREFIX)
        assert data["credential_prefix"] == data["credential"][:16]

    def test_the_hash_is_never_returned(self, api, two_tenants):
        data = create_connector(api, two_tenants["workspace_a"].id)
        assert "credential_hash" not in data

    def test_read_back_never_exposes_the_hash(self, api, two_tenants):
        data = create_connector(api, two_tenants["workspace_a"].id)
        fetched = envelope_ok(api.as_user(0).client.get(f"/connectors/{data['id']}"))
        assert "credential_hash" not in fetched
        assert "credential" not in fetched

    def test_default_scopes_are_the_connector_ceiling(self, api, two_tenants):
        data = create_connector(api, two_tenants["workspace_a"].id)
        assert "workspace:manage" not in data["scopes"]
        assert "export:read" not in data["scopes"]
        assert "memory:write" in data["scopes"]

    def test_administrative_scopes_are_refused(self, api, two_tenants):
        response = api.as_user(0).client.post(
            "/connectors",
            json={
                "workspace_id": str(two_tenants["workspace_a"].id),
                "name": "greedy",
                "connector_type": "cli",
                "scopes": ["memory:write", "workspace:manage"],
            },
        )
        envelope_error(response, "VALIDATION_FAILED", 400)

    def test_a_member_cannot_create_a_credential(self, api, db, two_tenants):
        from ume_app.models.workspace import WorkspaceMember

        db.add(WorkspaceMember(workspace_id=two_tenants["workspace_a"].id, user_id=api.users[2].id, role="member"))
        db.commit()
        response = api.as_user(2).client.post(
            "/connectors",
            json={
                "workspace_id": str(two_tenants["workspace_a"].id),
                "name": "x",
                "connector_type": "cli",
            },
        )
        envelope_error(response, "PERMISSION_DENIED", 403)


class TestScopeNarrowing:
    def test_scopes_can_be_narrowed(self, api, two_tenants):
        data = create_connector(api, two_tenants["workspace_a"].id, scopes=["memory:read", "memory:write"])
        updated = envelope_ok(
            api.as_user(0).client.patch(f"/connectors/{data['id']}", json={"scopes": ["memory:read"]})
        )
        assert updated["scopes"] == ["memory:read"]

    def test_scopes_cannot_be_widened(self, api, two_tenants):
        """Otherwise creating then editing would be a privilege escalation."""
        data = create_connector(api, two_tenants["workspace_a"].id, scopes=["memory:read"])
        response = api.as_user(0).client.patch(
            f"/connectors/{data['id']}",
            json={"scopes": ["memory:read", "memory:write", "conversation:write"]},
        )
        envelope_error(response, "CONFLICT", 409)


class TestRevocation:
    def test_revoke_marks_the_connector(self, api, two_tenants):
        data = create_connector(api, two_tenants["workspace_a"].id)
        revoked = envelope_ok(api.as_user(0).client.post(f"/connectors/{data['id']}/revoke"))
        assert revoked["status"] == "revoked"
        assert revoked["revoked_at"] is not None

    def test_revoking_twice_is_refused(self, api, two_tenants):
        data = create_connector(api, two_tenants["workspace_a"].id)
        api.as_user(0).client.post(f"/connectors/{data['id']}/revoke")
        envelope_error(api.as_user(0).client.post(f"/connectors/{data['id']}/revoke"), "CONFLICT", 409)

    def test_a_revoked_connector_disappears_from_the_default_list(self, api, two_tenants):
        data = create_connector(api, two_tenants["workspace_a"].id)
        api.as_user(0).client.post(f"/connectors/{data['id']}/revoke")
        workspace_id = two_tenants["workspace_a"].id
        listed = envelope_ok(api.as_user(0).client.get(f"/connectors?workspace_id={workspace_id}"))
        assert data["id"] not in [item["id"] for item in listed["items"]]
        with_revoked = envelope_ok(
            api.as_user(0).client.get(f"/connectors?workspace_id={workspace_id}&include_revoked=true")
        )
        assert data["id"] in [item["id"] for item in with_revoked["items"]]

    def test_another_tenant_cannot_revoke(self, api, two_tenants):
        data = create_connector(api, two_tenants["workspace_a"].id)
        envelope_error(api.as_user(1).client.post(f"/connectors/{data['id']}/revoke"), "NOT_FOUND", 404)


class TestTokenShape:
    def test_connector_tokens_are_distinguishable(self):
        assert looks_like_connector_token(f"{TOKEN_PREFIX}abc")
        assert not looks_like_connector_token("eyJhbGciOi...")  # a user JWT
        assert not looks_like_connector_token("")

    def test_scope_normalisation_rejects_administrative_scopes(self):
        with pytest.raises(ValidationError):
            normalise_scopes(["workspace:manage"])

    def test_scope_normalisation_defaults_to_the_ceiling(self):
        assert normalise_scopes(None)
        assert "workspace:manage" not in normalise_scopes(None)

    def test_scope_normalisation_deduplicates_and_sorts(self):
        assert normalise_scopes(["memory:write", "memory:read", "memory:write"]) == [
            "memory:read",
            "memory:write",
        ]


class TestConnectorAccess:
    """Two clients, one project, and a revoke that bites immediately."""

    def _as_connector(self, api, credential: str, method: str, path: str, **kwargs):
        """Call a UME route as a connector.

        The override delegates to the real `_resolve_connector_actor`, so a
        forged or revoked token fails the same way it would in production
        rather than through a re-implementation in the test.
        """
        from ume_app.api.app import ume_api
        from ume_app.auth.dependencies import _resolve_connector_actor, get_actor

        def fake_actor():
            return _resolve_connector_actor(api.db, credential)

        # Saved and restored, not popped: the shared `api` fixture installs its
        # own override, and dropping it would leave later requests in this test
        # hitting the real auth stack and answering 401.
        previous = ume_api.dependency_overrides.get(get_actor)
        ume_api.dependency_overrides[get_actor] = fake_actor
        try:
            return getattr(api.client, method)(path, **kwargs)
        finally:
            if previous is None:
                ume_api.dependency_overrides.pop(get_actor, None)
            else:
                ume_api.dependency_overrides[get_actor] = previous

    def test_two_connectors_share_a_project(self, api, two_tenants, engine):
        """P4 exit condition: two clients see the same project's memories."""
        workspace_id = two_tenants["workspace_a"].id
        project_id = two_tenants["project_a"].id

        a = create_connector(api, workspace_id, name="client-a", scopes=["memory:write", "memory:read"])
        b = create_connector(api, workspace_id, name="client-b", scopes=["memory:read"])

        created = envelope_ok(
            api.as_user(0).client.post(
                "/memories",
                json={
                    "workspace_id": str(workspace_id),
                    "messages": [{"role": "user", "content": "shared fact"}],
                    "project_ids": [str(project_id)],
                },
            ),
            201,
        )

        read_a = self._as_connector(
            api, a["credential"], "get", f"/memories?workspace_id={workspace_id}&project_id={project_id}"
        )
        assert read_a.status_code == 200, read_a.text
        assert created["id"] in [item["id"] for item in read_a.json()["data"]["items"]]

        read_b = self._as_connector(
            api, b["credential"], "get", f"/memories?workspace_id={workspace_id}&project_id={project_id}"
        )
        assert read_b.status_code == 200, read_b.text
        assert read_a.json()["data"] == read_b.json()["data"]

    def test_a_connector_can_write_within_its_scope(self, api, two_tenants, engine):
        workspace_id = two_tenants["workspace_a"].id
        writer = create_connector(api, workspace_id, name="writer", scopes=["memory:write"])
        response = self._as_connector(
            api,
            writer["credential"],
            "post",
            "/memories",
            json={"workspace_id": str(workspace_id), "messages": [{"role": "user", "content": "from a connector"}]},
        )
        assert response.status_code == 201, response.text
        assert response.json()["data"]["engine_state"] == "ready"

    def test_a_read_only_connector_cannot_write(self, api, two_tenants, engine):
        workspace_id = two_tenants["workspace_a"].id
        read_only = create_connector(api, workspace_id, name="reader", scopes=["memory:read"])
        response = self._as_connector(
            api,
            read_only["credential"],
            "post",
            "/memories",
            json={"workspace_id": str(workspace_id), "messages": [{"role": "user", "content": "x"}]},
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "PERMISSION_DENIED"

    def test_revocation_refuses_the_next_request(self, api, two_tenants, engine):
        workspace_id = two_tenants["workspace_a"].id
        connector = create_connector(api, workspace_id, name="temp", scopes=["memory:read"])

        before = self._as_connector(api, connector["credential"], "get", f"/memories?workspace_id={workspace_id}")
        assert before.status_code == 200, before.text

        api.as_user(0).client.post(f"/connectors/{connector['id']}/revoke")

        after = self._as_connector(api, connector["credential"], "get", f"/memories?workspace_id={workspace_id}")
        assert after.status_code == 401
        assert after.json()["error"]["code"] == "UNAUTHENTICATED"

    def test_a_connector_cannot_administer_the_workspace(self, api, two_tenants, engine):
        workspace_id = two_tenants["workspace_a"].id
        connector = create_connector(api, workspace_id, name="agent", scopes=["memory:read"])
        response = self._as_connector(api, connector["credential"], "get", f"/connectors?workspace_id={workspace_id}")
        assert response.status_code == 403

    def test_a_connector_cannot_reach_another_workspace(self, api, two_tenants, engine):
        """404, not 403: the binding must not confirm the workspace exists."""
        connector = create_connector(api, two_tenants["workspace_a"].id, name="agent", scopes=["memory:read"])
        response = self._as_connector(
            api, connector["credential"], "get", f"/memories?workspace_id={two_tenants['workspace_b'].id}"
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "NOT_FOUND"

    def test_a_forged_token_is_refused(self, api, two_tenants, engine):
        response = self._as_connector(
            api, f"{TOKEN_PREFIX}not-a-real-token", "get", f"/memories?workspace_id={two_tenants['workspace_a'].id}"
        )
        assert response.status_code == 401

    def test_the_last_active_stamp_is_written(self, api, two_tenants, engine):
        workspace_id = two_tenants["workspace_a"].id
        connector = create_connector(api, workspace_id, name="agent", scopes=["memory:read"])
        assert connector["last_active_at"] is None
        self._as_connector(api, connector["credential"], "get", f"/memories?workspace_id={workspace_id}")
        fetched = envelope_ok(api.as_user(0).client.get(f"/connectors/{connector['id']}"))
        assert fetched["last_active_at"] is not None
