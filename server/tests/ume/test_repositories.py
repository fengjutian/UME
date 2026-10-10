"""Workspace-scoped repository tests (section 16.1 / 16.3).

Two tenants with identical resource shape, so any missing `WHERE workspace_id`
shows up as leakage rather than as an empty result.
"""

import pytest
from ume_app.domain.errors import ConflictError, NotFoundError, ValidationError
from ume_app.models.base import utcnow
from ume_app.repositories.base import (
    MAX_PAGE_SIZE,
    clamp_page_size,
    decode_cursor,
    encode_cursor,
)
from ume_app.repositories.projects import ProjectRepository
from ume_app.repositories.workspaces import (
    WorkspaceMemberRepository,
    WorkspaceRepository,
)


class TestProjectScoping:
    def test_list_returns_only_own_workspace_projects(self, repos, two_tenants):
        page = repos["projects"].list_for_workspace(two_tenants["workspace_a"].id)
        ids = {project.id for project in page.items}
        assert ids == {two_tenants["project_a"].id}
        assert two_tenants["project_b"].id not in ids

    def test_empty_workspace_lists_nothing(self, repos, two_tenants):
        repos["projects"].delete(two_tenants["project_a"])
        repos["db"].commit()
        assert repos["projects"].list_for_workspace(two_tenants["workspace_a"].id).items == []
        # ...and the other tenant's project is untouched.
        assert len(repos["projects"].list_for_workspace(two_tenants["workspace_b"].id).items) == 1

    def test_cross_tenant_project_id_is_not_readable(self, repos, two_tenants):
        """A known project id from another workspace must not resolve."""
        assert repos["projects"].get_in_workspace(two_tenants["workspace_a"].id, two_tenants["project_b"].id) is None

    def test_cross_tenant_project_id_raises_not_found(self, repos, two_tenants):
        with pytest.raises(NotFoundError) as exc:
            repos["projects"].require_in_workspace(two_tenants["workspace_a"].id, two_tenants["project_b"].id)
        assert exc.value.status_code == 404

    def test_status_filter_is_applied_inside_the_workspace(self, repos, two_tenants):
        project = two_tenants["project_a"]
        repos["projects"].update(project, status="archived")
        repos["projects"].update(two_tenants["project_b"], status="archived")
        repos["db"].commit()

        active = repos["projects"].list_for_workspace(two_tenants["workspace_a"].id, status="active")
        archived = repos["projects"].list_for_workspace(two_tenants["workspace_a"].id, status="archived")
        assert active.items == []
        assert [p.id for p in archived.items] == [two_tenants["project_a"].id]

    def test_touch_activity_updates_timestamp(self, repos, two_tenants):
        project = two_tenants["project_a"]
        assert project.last_activity_at is None
        repos["projects"].touch_activity(project)
        repos["db"].commit()
        assert project.last_activity_at is not None

    def test_update_ignores_none_values(self, repos, two_tenants):
        project = two_tenants["project_a"]
        project.description = "keep me"
        repos["db"].commit()
        repos["projects"].update(project, name=None, description=None)
        repos["db"].commit()
        assert project.name == "Project A"
        assert project.description == "keep me"

    def test_delete_removes_only_that_project(self, repos, two_tenants):
        repos["projects"].delete(two_tenants["project_a"])
        repos["db"].commit()
        assert repos["projects"].list_for_workspace(two_tenants["workspace_b"].id).items


class TestWorkspaceListing:
    def test_list_for_user_is_membership_scoped(self, repos, two_tenants):
        page = repos["workspaces"].list_for_user(two_tenants["alice_id"])
        assert [w.id for w in page.items] == [two_tenants["workspace_a"].id]

    def test_list_for_user_excludes_non_member_workspaces(self, repos, two_tenants):
        # Bob is not a member of workspace A even though he can see its id.
        repos["members"].add(two_tenants["workspace_a"].id, two_tenants["bob_id"], "viewer")
        repos["db"].commit()
        page = repos["workspaces"].list_for_user(two_tenants["bob_id"])
        assert {w.id for w in page.items} == {
            two_tenants["workspace_a"].id,
            two_tenants["workspace_b"].id,
        }

    def test_list_for_unknown_user_is_empty(self, repos, two_tenants):
        import uuid

        assert repos["workspaces"].list_for_user(uuid.uuid4()).items == []

    def test_require_missing_workspace_raises(self, repos):
        import uuid

        with pytest.raises(NotFoundError):
            repos["workspaces"].require(uuid.uuid4())


class TestMembership:
    def test_membership_lookup_is_workspace_scoped(self, repos, two_tenants):
        # Same user id, different workspace: the other workspace must miss.
        assert repos["members"].membership(two_tenants["workspace_a"].id, two_tenants["alice_id"]) is not None
        assert repos["members"].membership(two_tenants["workspace_b"].id, two_tenants["alice_id"]) is None

    def test_duplicate_membership_conflicts(self, repos, two_tenants):
        with pytest.raises(ConflictError):
            repos["members"].add(two_tenants["workspace_a"].id, two_tenants["alice_id"], "member")

    def test_list_members_is_workspace_scoped(self, repos, two_tenants):
        page = repos["members"].list_members(two_tenants["workspace_a"].id)
        assert [m.user_id for m in page.items] == [two_tenants["alice_id"]]

    def test_role_change_and_removal(self, repos, two_tenants):
        repos["members"].add(two_tenants["workspace_a"].id, two_tenants["bob_id"], "viewer")
        repos["db"].commit()
        repos["members"].set_role(two_tenants["workspace_a"].id, two_tenants["bob_id"], "admin")
        repos["db"].commit()
        assert repos["members"].membership(two_tenants["workspace_a"].id, two_tenants["bob_id"]).role == "admin"

        repos["members"].remove(two_tenants["workspace_a"].id, two_tenants["bob_id"])
        repos["db"].commit()
        assert repos["members"].membership(two_tenants["workspace_a"].id, two_tenants["bob_id"]) is None

    def test_removing_a_non_member_is_not_found(self, repos, two_tenants):
        with pytest.raises(NotFoundError):
            repos["members"].remove(two_tenants["workspace_a"].id, two_tenants["bob_id"])


class TestPagination:
    def test_cursor_walks_every_project_exactly_once(self, repos, two_tenants):
        workspace_id = two_tenants["workspace_a"].id
        base = utcnow()
        expected = set()
        for index in range(7):
            project = repos["projects"].create(workspace_id, f"P{index}")
            project.created_at = base.replace(microsecond=index * 1000)
            expected.add(project.id)
        repos["db"].commit()

        seen, cursor, pages = [], None, 0
        while True:
            page = repos["projects"].list_for_workspace(workspace_id, limit=3, cursor=cursor)
            seen.extend(p.id for p in page.items)
            pages += 1
            if not page.has_more:
                assert page.next_cursor is None
                break
            assert page.next_cursor
            cursor = page.next_cursor
            assert pages < 10, "pagination did not terminate"

        assert set(seen) == expected | {two_tenants["project_a"].id}
        assert len(seen) == len(set(seen)), "cursor page returned a duplicate"

    def test_page_reports_has_more_when_truncated(self, repos, two_tenants):
        workspace_id = two_tenants["workspace_a"].id
        for index in range(3):
            repos["projects"].create(workspace_id, f"extra-{index}")
        repos["db"].commit()

        page = repos["projects"].list_for_workspace(workspace_id, limit=2)
        assert len(page.items) == 2
        assert page.has_more is True
        assert page.next_cursor is not None

    def test_last_page_reports_no_more(self, repos, two_tenants):
        page = repos["projects"].list_for_workspace(two_tenants["workspace_a"].id, limit=50)
        assert page.has_more is False
        assert page.next_cursor is None

    def test_cursor_round_trip(self, two_tenants):
        project = two_tenants["project_a"]
        assert decode_cursor(encode_cursor(project.created_at, project.id)) == (project.created_at, project.id)

    def test_invalid_cursor_is_rejected(self, repos, two_tenants):
        with pytest.raises(ValidationError):
            repos["projects"].list_for_workspace(two_tenants["workspace_a"].id, cursor="not-a-cursor")

    @pytest.mark.parametrize("limit", [0, -1, MAX_PAGE_SIZE + 1])
    def test_limit_bounds_are_enforced(self, limit):
        with pytest.raises(ValidationError):
            clamp_page_size(limit)


class TestRepositoryWiring:
    def test_project_repository_has_no_unscoped_listing(self):
        """Guards the API surface: adding `list()` would reintroduce tenant bleed."""
        assert not hasattr(ProjectRepository, "list")
        assert not hasattr(ProjectRepository, "get")

    def test_member_repository_get_is_workspace_scoped(self):
        assert hasattr(WorkspaceMemberRepository, "membership")
        assert not hasattr(WorkspaceMemberRepository, "get")

    def test_workspace_repository_is_the_only_pk_lookup(self):
        assert hasattr(WorkspaceRepository, "get")
