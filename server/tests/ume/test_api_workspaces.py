"""Workspace API tests (Task 1.2).

Covers the unified envelope, CRUD, the membership rules, and the cross-workspace
denials required by section 16.3.
"""

import uuid

from envelope import envelope_error, envelope_ok
from ume_app.models.workspace import WorkspaceMember

BASE = ""


class TestEnvelope:
    def test_success_shape(self, api):
        response = api.as_user(0).client.get("/workspaces")
        data = envelope_ok(response)
        assert set(data) == {"items", "next_cursor", "has_more"}
        assert data["next_cursor"] is None
        assert data["has_more"] is False

    def test_request_id_header_matches_body(self, api):
        response = api.as_user(0).client.get("/workspaces")
        assert response.json()["request_id"] == response.headers["X-Request-ID"]

    def test_validation_error_shape(self, api):
        response = api.as_user(0).client.post("/workspaces", json={"description": "no name"})
        error = envelope_error(response, "VALIDATION_FAILED", 400)
        assert error["details"][0]["field"] == "name"

    def test_blank_name_is_rejected(self, api):
        response = api.as_user(0).client.post("/workspaces", json={"name": "   "})
        envelope_error(response, "VALIDATION_FAILED", 400)

    def test_not_found_shape(self, api, two_tenants):
        response = api.as_user(0).client.get(f"/workspaces/{uuid.uuid4()}")
        envelope_error(response, "NOT_FOUND", 404)

    def test_unknown_route_uses_the_envelope(self, api):
        response = api.as_user(0).client.get("/nope")
        envelope_error(response, "NOT_FOUND", 404)


class TestWorkspaceCrud:
    def test_create_returns_201_and_makes_the_caller_owner(self, api, db):
        data = envelope_ok(
            api.as_user(0).client.post("/workspaces", json={"name": "  Research  "}), expected_status=201
        )
        assert data["name"] == "Research"
        assert data["status"] == "active"
        assert data["default_memory_policy"] == {}

        membership = db.query(WorkspaceMember).filter_by(workspace_id=uuid.UUID(data["id"])).one()
        assert membership.user_id == api.users[0].id
        assert membership.role == "owner"

    def test_created_workspace_is_listed_for_its_owner(self, api):
        created = envelope_ok(api.as_user(0).client.post("/workspaces", json={"name": "Mine"}), 201)
        listed = envelope_ok(api.as_user(0).client.get("/workspaces"))
        assert created["id"] in [item["id"] for item in listed["items"]]

    def test_created_workspace_is_invisible_to_other_users(self, api):
        created = envelope_ok(api.as_user(0).client.post("/workspaces", json={"name": "Private"}), 201)
        listed = envelope_ok(api.as_user(1).client.get("/workspaces"))
        assert created["id"] not in [item["id"] for item in listed["items"]]

    def test_get_workspace(self, api, two_tenants):
        data = envelope_ok(api.as_user(0).client.get(f"/workspaces/{two_tenants['workspace_a'].id}"))
        assert data["name"] == "Workspace A"

    def test_patch_updates_only_supplied_fields(self, api, two_tenants):
        workspace_id = two_tenants["workspace_a"].id
        data = envelope_ok(api.as_user(0).client.patch(f"/workspaces/{workspace_id}", json={"description": "notes"}))
        assert data["description"] == "notes"
        assert data["name"] == "Workspace A"

    def test_patch_can_clear_a_nullable_field(self, api, two_tenants):
        workspace_id = two_tenants["workspace_a"].id
        api.as_user(0).client.patch(f"/workspaces/{workspace_id}", json={"description": "notes"})
        data = envelope_ok(api.as_user(0).client.patch(f"/workspaces/{workspace_id}", json={"description": None}))
        assert data["description"] is None

    def test_empty_patch_body_is_a_no_op(self, api, two_tenants):
        workspace_id = two_tenants["workspace_a"].id
        data = envelope_ok(api.as_user(0).client.patch(f"/workspaces/{workspace_id}", json={}))
        assert data["name"] == "Workspace A"

    def test_delete_removes_the_workspace(self, api):
        created = envelope_ok(api.as_user(0).client.post("/workspaces", json={"name": "Empty"}), 201)
        workspace_id = created["id"]
        data = envelope_ok(api.as_user(0).client.delete(f"/workspaces/{workspace_id}"))
        assert data["deleted"] is True
        envelope_error(api.as_user(0).client.get(f"/workspaces/{workspace_id}"), "NOT_FOUND", 404)

    def test_delete_is_refused_while_projects_exist(self, api, two_tenants):
        workspace_id = two_tenants["workspace_a"].id
        error = envelope_error(api.as_user(0).client.delete(f"/workspaces/{workspace_id}"), "CONFLICT", 409)
        assert error["details"]["project_count"] == 1

    def test_delete_succeeds_after_projects_are_removed(self, api, two_tenants):
        workspace_id = two_tenants["workspace_a"].id
        api.as_user(0).client.delete(f"/projects/{two_tenants['project_a'].id}")
        envelope_ok(api.as_user(0).client.delete(f"/workspaces/{workspace_id}"))


class TestCrossWorkspaceIsolation:
    def test_reading_another_workspace_returns_404(self, api, two_tenants):
        """404, not 403: a 403 would confirm that the id exists."""
        response = api.as_user(1).client.get(f"/workspaces/{two_tenants['workspace_a'].id}")
        envelope_error(response, "NOT_FOUND", 404)

    def test_patching_another_workspace_returns_404(self, api, two_tenants):
        response = api.as_user(1).client.patch(
            f"/workspaces/{two_tenants['workspace_a'].id}", json={"name": "hijacked"}
        )
        envelope_error(response, "NOT_FOUND", 404)

    def test_deleting_another_workspace_returns_404(self, api, two_tenants):
        response = api.as_user(1).client.delete(f"/workspaces/{two_tenants['workspace_a'].id}")
        envelope_error(response, "NOT_FOUND", 404)

    def test_listing_projects_of_another_workspace_returns_404(self, api, two_tenants):
        response = api.as_user(1).client.get(f"/workspaces/{two_tenants['workspace_a'].id}/projects")
        envelope_error(response, "NOT_FOUND", 404)

    def test_members_of_another_workspace_are_not_visible(self, api, two_tenants):
        workspace_id = two_tenants["workspace_a"].id
        response = api.as_user(1).client.get(f"/workspaces/{workspace_id}/members")
        envelope_error(response, "NOT_FOUND", 404)

    def test_adding_a_member_to_another_workspace_returns_404(self, api, two_tenants):
        response = api.as_user(1).client.post(
            f"/workspaces/{two_tenants['workspace_a'].id}/members",
            json={"user_id": str(api.users[2].id), "role": "admin"},
        )
        envelope_error(response, "NOT_FOUND", 404)


class TestRoleEnforcement:
    def test_viewer_cannot_rename_the_workspace(self, api, db, two_tenants):
        workspace_id = two_tenants["workspace_a"].id
        db.add(WorkspaceMember(workspace_id=workspace_id, user_id=api.users[2].id, role="viewer"))
        db.commit()
        response = api.as_user(2).client.patch(f"/workspaces/{workspace_id}", json={"name": "nope"})
        envelope_error(response, "PERMISSION_DENIED", 403)

    def test_viewer_can_read_the_workspace(self, api, db, two_tenants):
        workspace_id = two_tenants["workspace_a"].id
        db.add(WorkspaceMember(workspace_id=workspace_id, user_id=api.users[2].id, role="viewer"))
        db.commit()
        data = envelope_ok(api.as_user(2).client.get(f"/workspaces/{workspace_id}"))
        assert data["id"] == str(workspace_id)

    def test_member_cannot_add_members(self, api, db, two_tenants):
        workspace_id = two_tenants["workspace_a"].id
        db.add(WorkspaceMember(workspace_id=workspace_id, user_id=api.users[2].id, role="member"))
        db.commit()
        response = api.as_user(2).client.post(
            f"/workspaces/{workspace_id}/members", json={"user_id": str(api.users[0].id), "role": "admin"}
        )
        envelope_error(response, "PERMISSION_DENIED", 403)

    def test_admin_can_add_members(self, api, db, two_tenants):
        workspace_id = two_tenants["workspace_a"].id
        db.add(WorkspaceMember(workspace_id=workspace_id, user_id=api.users[2].id, role="admin"))
        db.commit()
        data = envelope_ok(
            api.as_user(2).client.post(
                f"/workspaces/{workspace_id}/members", json={"user_id": str(api.users[1].id), "role": "viewer"}
            ),
            expected_status=201,
        )
        assert data["role"] == "viewer"

    def test_admin_cannot_delete_a_workspace_with_projects(self, api, db, two_tenants):
        workspace_id = two_tenants["workspace_a"].id
        db.add(WorkspaceMember(workspace_id=workspace_id, user_id=api.users[2].id, role="admin"))
        db.commit()
        envelope_error(api.as_user(2).client.delete(f"/workspaces/{workspace_id}"), "CONFLICT", 409)


class TestMembership:
    def test_members_are_listed(self, api, two_tenants):
        data = envelope_ok(api.as_user(0).client.get(f"/workspaces/{two_tenants['workspace_a'].id}/members"))
        assert [m["role"] for m in data["items"]] == ["owner"]

    def test_duplicate_member_conflicts(self, api, two_tenants):
        workspace_id = two_tenants["workspace_a"].id
        api.as_user(0).client.post(
            f"/workspaces/{workspace_id}/members", json={"user_id": str(api.users[2].id), "role": "viewer"}
        )
        response = api.as_user(0).client.post(
            f"/workspaces/{workspace_id}/members",
            json={"user_id": str(api.users[2].id), "role": "member"},
        )
        envelope_error(response, "CONFLICT", 409)

    def test_unknown_role_is_a_validation_error(self, api, two_tenants):
        response = api.as_user(0).client.post(
            f"/workspaces/{two_tenants['workspace_a'].id}/members",
            json={"user_id": str(api.users[2].id), "role": "superuser"},
        )
        envelope_error(response, "VALIDATION_FAILED", 400)

    def test_role_can_be_changed(self, api, two_tenants):
        workspace_id = two_tenants["workspace_a"].id
        api.as_user(0).client.post(
            f"/workspaces/{workspace_id}/members", json={"user_id": str(api.users[2].id), "role": "viewer"}
        )
        data = envelope_ok(
            api.as_user(0).client.patch(
                f"/workspaces/{workspace_id}/members/{api.users[2].id}", json={"role": "member"}
            )
        )
        assert data["role"] == "member"

    def test_member_can_be_removed(self, api, two_tenants):
        workspace_id = two_tenants["workspace_a"].id
        api.as_user(0).client.post(
            f"/workspaces/{workspace_id}/members", json={"user_id": str(api.users[2].id), "role": "viewer"}
        )
        envelope_ok(api.as_user(0).client.delete(f"/workspaces/{workspace_id}/members/{api.users[2].id}"))
        envelope_error(api.as_user(2).client.get(f"/workspaces/{workspace_id}"), "NOT_FOUND", 404)

    def test_removing_an_unknown_member_is_404(self, api, two_tenants):
        workspace_id = two_tenants["workspace_a"].id
        response = api.as_user(0).client.delete(f"/workspaces/{workspace_id}/members/{uuid.uuid4()}")
        envelope_error(response, "NOT_FOUND", 404)

    def test_the_last_owner_cannot_be_demoted(self, api, two_tenants):
        workspace_id = two_tenants["workspace_a"].id
        response = api.as_user(0).client.patch(
            f"/workspaces/{workspace_id}/members/{api.users[0].id}", json={"role": "member"}
        )
        envelope_error(response, "CONFLICT", 409)

    def test_the_last_owner_cannot_be_removed(self, api, two_tenants):
        workspace_id = two_tenants["workspace_a"].id
        response = api.as_user(0).client.delete(f"/workspaces/{workspace_id}/members/{api.users[0].id}")
        envelope_error(response, "CONFLICT", 409)

    def test_owner_cannot_be_demoted_by_adding_a_different_role(self, api, two_tenants):
        workspace_id = two_tenants["workspace_a"].id
        response = api.as_user(0).client.post(
            f"/workspaces/{workspace_id}/members", json={"user_id": str(api.users[0].id), "role": "viewer"}
        )
        assert response.status_code in (400, 409)


class TestPagination:
    def test_cursor_walks_the_page_set(self, api, db, two_tenants):
        workspace_id = two_tenants["workspace_a"].id
        for index in range(5):
            api.as_user(0).client.post(f"/workspaces/{workspace_id}/projects", json={"name": f"P{index}"})

        first = envelope_ok(api.as_user(0).client.get(f"/workspaces/{workspace_id}/projects?limit=2"))
        assert first["has_more"] is True
        assert len(first["items"]) == 2

        second = envelope_ok(
            api.as_user(0).client.get(f"/workspaces/{workspace_id}/projects?limit=2&cursor={first['next_cursor']}")
        )
        names = [item["name"] for item in first["items"] + second["items"]]
        assert len(names) == len(set(names))

    def test_bad_cursor_is_a_validation_error(self, api, two_tenants):
        response = api.as_user(0).client.get(f"/workspaces/{two_tenants['workspace_a'].id}/projects?cursor=zzz")
        envelope_error(response, "VALIDATION_FAILED", 400)

    def test_limit_out_of_range_is_rejected(self, api, two_tenants):
        # Query-parameter validation is mapped into the same envelope as body
        # validation, so this is 400 VALIDATION_FAILED rather than FastAPI's
        # bare 422.
        response = api.as_user(0).client.get(f"/workspaces/{two_tenants['workspace_a'].id}/projects?limit=9999")
        envelope_error(response, "VALIDATION_FAILED", 400)

    def test_status_filter(self, api, two_tenants):
        workspace_id = two_tenants["workspace_a"].id
        api.as_user(0).client.post(f"/workspaces/{workspace_id}/projects", json={"name": "Second"})
        data = envelope_ok(api.as_user(0).client.get(f"/workspaces/{workspace_id}/projects?status=archived"))
        assert data["items"] == []
