"""Top-level `/projects/{id}` API tests.

The path carries no workspace, so these double as the tests for
"resolve the workspace, then prove the caller may act on it".
"""

import uuid

from envelope import envelope_error, envelope_ok
from ume_app.models.workspace import WorkspaceMember


class TestProjectCrud:
    def test_create_returns_201_with_default_fields(self, api, two_tenants):
        workspace_id = two_tenants["workspace_a"].id
        data = envelope_ok(
            api.as_user(0).client.post(
                f"/workspaces/{workspace_id}/projects", json={"name": "  Atlas  ", "tags": ["ml"]}
            ),
            expected_status=201,
        )
        assert data["name"] == "Atlas"
        assert data["tags"] == ["ml"]
        assert data["status"] == "active"
        assert data["workspace_id"] == str(workspace_id)
        assert data["last_activity_at"] is not None

    def test_get_project_by_id(self, api, two_tenants):
        data = envelope_ok(api.as_user(0).client.get(f"/projects/{two_tenants['project_a'].id}"))
        assert data["name"] == "Project A"

    def test_patch_updates_only_supplied_fields(self, api, two_tenants):
        data = envelope_ok(
            api.as_user(0).client.patch(f"/projects/{two_tenants['project_a'].id}", json={"name": "Renamed"})
        )
        assert data["name"] == "Renamed"
        assert data["tags"] == []

    def test_patch_can_archive(self, api, two_tenants):
        data = envelope_ok(
            api.as_user(0).client.patch(f"/projects/{two_tenants['project_a'].id}", json={"status": "archived"})
        )
        assert data["status"] == "archived"

    def test_unknown_status_is_rejected(self, api, two_tenants):
        response = api.as_user(0).client.patch(
            f"/projects/{two_tenants['project_a'].id}", json={"status": "deleted-ish"}
        )
        envelope_error(response, "VALIDATION_FAILED", 400)

    def test_delete(self, api, two_tenants):
        data = envelope_ok(api.as_user(0).client.delete(f"/projects/{two_tenants['project_a'].id}"))
        assert data["deleted"] is True
        envelope_error(api.as_user(0).client.get(f"/projects/{two_tenants['project_a'].id}"), "NOT_FOUND", 404)

    def test_unknown_project_is_404(self, api):
        envelope_error(api.as_user(0).client.get(f"/projects/{uuid.uuid4()}"), "NOT_FOUND", 404)

    def test_non_uuid_path_is_404(self, api):
        # The path parameter is a UUID; anything else cannot be a project.
        assert api.as_user(0).client.get("/projects/not-a-uuid").status_code in (404, 400)


class TestProjectIsolation:
    def test_reading_another_tenants_project_is_404(self, api, two_tenants):
        response = api.as_user(1).client.get(f"/projects/{two_tenants['project_a'].id}")
        envelope_error(response, "NOT_FOUND", 404)

    def test_patching_another_tenants_project_is_404(self, api, two_tenants):
        response = api.as_user(1).client.patch(f"/projects/{two_tenants['project_a'].id}", json={"name": "hijacked"})
        envelope_error(response, "NOT_FOUND", 404)

    def test_deleting_another_tenants_project_is_404(self, api, two_tenants):
        response = api.as_user(1).client.delete(f"/projects/{two_tenants['project_a'].id}")
        envelope_error(response, "NOT_FOUND", 404)

    def test_the_project_survives_a_cross_tenant_attempt(self, api, two_tenants):
        api.as_user(1).client.delete(f"/projects/{two_tenants['project_a'].id}")
        data = envelope_ok(api.as_user(0).client.get(f"/projects/{two_tenants['project_a'].id}"))
        assert data["name"] == "Project A"


class TestProjectRoles:
    def test_viewer_can_read_a_project(self, api, db, two_tenants):
        db.add(WorkspaceMember(workspace_id=two_tenants["workspace_a"].id, user_id=api.users[2].id, role="viewer"))
        db.commit()
        data = envelope_ok(api.as_user(2).client.get(f"/projects/{two_tenants['project_a'].id}"))
        assert data["name"] == "Project A"

    def test_viewer_cannot_patch_a_project(self, api, db, two_tenants):
        db.add(WorkspaceMember(workspace_id=two_tenants["workspace_a"].id, user_id=api.users[2].id, role="viewer"))
        db.commit()
        response = api.as_user(2).client.patch(f"/projects/{two_tenants['project_a'].id}", json={"name": "nope"})
        envelope_error(response, "PERMISSION_DENIED", 403)

    def test_viewer_cannot_create_a_project(self, api, db, two_tenants):
        db.add(WorkspaceMember(workspace_id=two_tenants["workspace_a"].id, user_id=api.users[2].id, role="viewer"))
        db.commit()
        response = api.as_user(2).client.post(
            f"/workspaces/{two_tenants['workspace_a'].id}/projects", json={"name": "nope"}
        )
        envelope_error(response, "PERMISSION_DENIED", 403)

    def test_member_can_create_and_patch(self, api, db, two_tenants):
        db.add(WorkspaceMember(workspace_id=two_tenants["workspace_a"].id, user_id=api.users[2].id, role="member"))
        db.commit()
        created = envelope_ok(
            api.as_user(2).client.post(
                f"/workspaces/{two_tenants['workspace_a'].id}/projects", json={"name": "Member project"}
            ),
            expected_status=201,
        )
        patched = envelope_ok(api.as_user(2).client.patch(f"/projects/{created['id']}", json={"name": "Edited"}))
        assert patched["name"] == "Edited"
