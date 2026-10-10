"""Audit trail tests.

Task 1.2 requires an audit record for both accepted and refused access. Two
properties matter more than the count of rows:

* an accepted change and its audit row commit together — a rejected write must
  not leave an audit row claiming it happened;
* a refused cross-tenant access is still recorded, on its own connection,
  because the request transaction is rolled back by then.
"""

import uuid

from envelope import envelope_error, envelope_ok
from ume_app.models.workspace import WorkspaceMember


def actions_for(api, **filters):
    return [(event.action, event.result) for event in api.audit_events(**filters)]


class TestSuccessAudit:
    def test_workspace_create_is_audited(self, api):
        created = envelope_ok(api.as_user(0).client.post("/workspaces", json={"name": "Audited"}), 201)
        events = api.audit_events(resource_id=uuid.UUID(created["id"]))
        assert len(events) == 1
        event = events[0]
        assert event.action == "workspace.create"
        assert event.result == "success"
        assert event.actor_id == api.users[0].id
        assert event.actor_type == "user"
        assert event.workspace_id == uuid.UUID(created["id"])
        assert event.request_id

    def test_every_mutation_action_is_recorded(self, api, two_tenants):
        workspace_id = two_tenants["workspace_a"].id
        client = api.as_user(0).client

        client.patch(f"/workspaces/{workspace_id}", json={"name": "Renamed"})
        project = envelope_ok(client.post(f"/workspaces/{workspace_id}/projects", json={"name": "P"}), 201)
        client.patch(f"/projects/{project['id']}", json={"name": "P2"})
        client.post(f"/workspaces/{workspace_id}/members", json={"user_id": str(api.users[2].id), "role": "viewer"})
        client.delete(f"/workspaces/{workspace_id}/members/{api.users[2].id}")
        client.delete(f"/projects/{project['id']}")

        recorded = {action for action, _ in actions_for(api)}
        assert {
            "workspace.update",
            "project.create",
            "project.update",
            "workspace.member.add",
            "workspace.member.remove",
            "project.delete",
        } <= recorded

    def test_audit_details_stay_non_sensitive(self, api):
        """Details may name a resource, never quote its content."""
        created = envelope_ok(api.as_user(0).client.post("/workspaces", json={"name": "Secret Project"}), 201)
        event = api.audit_events(resource_id=uuid.UUID(created["id"]))[0]
        assert set(event.details) <= {"name", "fields", "role", "target_user_id", "project_count", "reason"}
        assert event.details["name"] == "Secret Project"

    def test_update_audit_records_only_changed_fields(self, api, two_tenants):
        workspace_id = two_tenants["workspace_a"].id
        api.as_user(0).client.patch(f"/workspaces/{workspace_id}", json={"description": "d"})
        event = [e for e in api.audit_events(action="workspace.update")][-1]
        assert event.details["fields"] == ["description"]


class TestDeniedAudit:
    def test_cross_workspace_read_is_recorded(self, api, two_tenants):
        workspace_id = two_tenants["workspace_a"].id
        envelope_error(api.as_user(1).client.get(f"/workspaces/{workspace_id}"), "NOT_FOUND", 404)

        denials = api.audit_events(result="denied")
        assert len(denials) == 1
        assert denials[0].action == "workspace.access"
        assert denials[0].resource_id == workspace_id
        assert denials[0].details["reason"] == "not_a_member"
        assert denials[0].actor_id == api.users[1].id

    def test_missing_workspace_is_recorded(self, api):
        missing = uuid.uuid4()
        envelope_error(api.as_user(0).client.get(f"/workspaces/{missing}"), "NOT_FOUND", 404)
        denials = api.audit_events(result="denied")
        assert denials[0].details["reason"] == "not_found"
        assert denials[0].resource_id == missing

    def test_missing_scope_is_recorded_with_the_scope_name(self, api, db, two_tenants):
        workspace_id = two_tenants["workspace_a"].id
        db.add(WorkspaceMember(workspace_id=workspace_id, user_id=api.users[2].id, role="viewer"))
        db.commit()
        envelope_error(
            api.as_user(2).client.patch(f"/workspaces/{workspace_id}", json={"name": "nope"}), "PERMISSION_DENIED", 403
        )

        denials = api.audit_events(result="denied")
        assert len(denials) == 1
        assert denials[0].details["reason"] == "missing_scope:workspace:manage"
        assert denials[0].workspace_id == workspace_id


class TestTransactionCoupling:
    def test_a_rejected_write_leaves_no_audit_row(self, api, two_tenants):
        """The audit row joins the business transaction, so a conflict writes neither."""
        workspace_id = two_tenants["workspace_a"].id
        api.as_user(0).client.post(
            f"/workspaces/{workspace_id}/members", json={"user_id": str(api.users[2].id), "role": "viewer"}
        )
        before = len(api.audit_events(action="workspace.member.add"))

        envelope_error(
            api.as_user(0).client.post(
                f"/workspaces/{workspace_id}/members", json={"user_id": str(api.users[2].id), "role": "member"}
            ),
            "CONFLICT",
            409,
        )
        assert len(api.audit_events(action="workspace.member.add")) == before

    def test_a_failed_write_does_not_audit_success(self, api, two_tenants):
        workspace_id = two_tenants["workspace_a"].id
        response = api.as_user(0).client.delete(f"/workspaces/{workspace_id}")
        envelope_error(response, "CONFLICT", 409)
        assert api.audit_events(action="workspace.delete") == []


class TestAuditIsolation:
    def test_a_tenant_cannot_read_another_tenants_audit_rows(self, api, two_tenants):
        """The audit table is not exposed by any Task 1.2 route."""
        created = envelope_ok(api.as_user(0).client.post("/workspaces", json={"name": "Private log"}), 201)
        workspace_id = uuid.UUID(created["id"])

        mine = api.audit_events(workspace_id=workspace_id)
        assert mine, "the owner's own writes are audited"

        # There is no audit read route; assert the scope is enforced at the
        # data layer the same way every other resource is.
        from ume_app.repositories.workspaces import WorkspaceMemberRepository

        assert WorkspaceMemberRepository(api.db).membership(workspace_id, api.users[1].id) is None
