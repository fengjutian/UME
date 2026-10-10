"""Permission matrix tests (section 16.1).

The matrix is the first thing a route and a repository both consult, so it gets
tested as data: which role holds which scope, how the roles nest, and what a
Principal actually refuses.
"""

import uuid

import pytest
from ume_app.auth.permissions import (
    ADMIN_ONLY_SCOPES,
    ADMIN_SCOPES,
    ALL_SCOPES,
    CONNECTOR_SCOPES,
    MEMBER_SCOPES,
    READ_SCOPES,
    ROLE_SCOPES,
    WRITE_SCOPES,
    Scope,
    role_at_least,
    scopes_for_role,
    system_principal,
    user_principal,
)
from ume_app.domain.enums import ActorType, WorkspaceRole
from ume_app.domain.errors import PermissionDeniedError

#: Scopes added beyond the section 7.3 list, kept here so a test can assert the
#: extension set is exactly what the delivery notes claim.
EXTENSION_SCOPES = frozenset({Scope.WORKSPACE_MANAGE, Scope.PROJECT_WRITE, Scope.CONNECTOR_MANAGE, Scope.IMPORT_WRITE})


def _all_declared_scopes() -> set[str]:
    return {value for name, value in vars(Scope).items() if not name.startswith("_") and isinstance(value, str)}


class TestScopeVocabulary:
    def test_section_7_3_scopes_are_declared(self):
        declared = _all_declared_scopes()
        for scope in (
            "workspace:read",
            "project:read",
            "conversation:read",
            "conversation:write",
            "memory:read",
            "memory:write",
            "context:read",
            "graph:read",
            "graph:write",
            "export:read",
        ):
            assert scope in declared

    def test_read_and_write_sets_are_disjoint(self):
        assert READ_SCOPES.isdisjoint(WRITE_SCOPES)

    def test_every_role_is_defined_for_every_enum_member(self):
        assert set(ROLE_SCOPES) == set(WorkspaceRole)


class TestRoleMatrix:
    @pytest.mark.parametrize("role", list(WorkspaceRole))
    def test_roles_nest_from_viewer_to_owner(self, role):
        rank = role_at_least(role, WorkspaceRole.VIEWER)
        assert rank, f"{role} must be at least a viewer"

    def test_hierarchy_is_a_chain(self):
        assert READ_SCOPES <= MEMBER_SCOPES
        assert MEMBER_SCOPES <= ADMIN_SCOPES
        assert ADMIN_SCOPES <= ALL_SCOPES

    def test_viewer_cannot_write(self):
        viewer = scopes_for_role(WorkspaceRole.VIEWER)
        assert viewer == READ_SCOPES
        assert viewer.isdisjoint(WRITE_SCOPES)
        assert Scope.MEMORY_WRITE not in viewer

    def test_member_can_write_but_not_administer(self):
        member = scopes_for_role(WorkspaceRole.MEMBER)
        assert WRITE_SCOPES <= member
        assert Scope.PROJECT_WRITE in member
        assert member.isdisjoint(ADMIN_ONLY_SCOPES)

    def test_admin_can_administer(self):
        admin = scopes_for_role(WorkspaceRole.ADMIN)
        assert ADMIN_ONLY_SCOPES <= admin

    def test_owner_holds_every_declared_scope(self):
        assert scopes_for_role(WorkspaceRole.OWNER) == _all_declared_scopes()

    def test_the_extension_set_is_exactly_the_documented_one(self):
        """Guards the deviation note: these four scopes are the whole extension."""
        assert EXTENSION_SCOPES == _all_declared_scopes() - (READ_SCOPES | WRITE_SCOPES)

    def test_admin_and_owner_differ_only_by_convenience(self):
        # Admin is the highest non-owner role; owner adds nothing new yet, which
        # is intentional: new management scopes must be added to ADMIN_SCOPES.
        assert ADMIN_SCOPES == ALL_SCOPES

    def test_role_rank_order(self):
        assert role_at_least(WorkspaceRole.OWNER, WorkspaceRole.ADMIN)
        assert role_at_least(WorkspaceRole.MEMBER, WorkspaceRole.VIEWER)
        assert not role_at_least(WorkspaceRole.VIEWER, WorkspaceRole.MEMBER)
        assert not role_at_least(WorkspaceRole.ADMIN, WorkspaceRole.OWNER)

    def test_unknown_role_is_rejected(self):
        with pytest.raises(ValueError):
            scopes_for_role("superuser")


class TestConnectorScopes:
    def test_connector_never_gets_management_scopes(self):
        assert CONNECTOR_SCOPES.isdisjoint(EXTENSION_SCOPES)

    def test_connector_cannot_export(self):
        # Export is a bulk data-egress capability; a connector credential must
        # not be able to walk a whole workspace out of the platform.
        assert Scope.EXPORT_READ not in CONNECTOR_SCOPES

    def test_connector_is_bounded_by_a_plain_member(self):
        assert CONNECTOR_SCOPES <= MEMBER_SCOPES


class TestPrincipal:
    def test_require_scope_allows_granted(self):
        principal = user_principal(uuid.uuid4(), MEMBER_SCOPES)
        principal.require_scope(Scope.MEMORY_WRITE)

    def test_require_scope_denies_ungranted(self):
        principal = user_principal(uuid.uuid4(), READ_SCOPES)
        with pytest.raises(PermissionDeniedError) as exc:
            principal.require_scope(Scope.MEMORY_WRITE)
        assert exc.value.status_code == 403
        assert exc.value.code == "PERMISSION_DENIED"

    def test_require_workspace_allows_matching_binding(self):
        workspace_id = uuid.uuid4()
        principal = user_principal(uuid.uuid4(), MEMBER_SCOPES, workspace_id=workspace_id)
        principal.require_workspace(workspace_id)

    def test_require_workspace_denies_foreign_binding(self):
        principal = user_principal(uuid.uuid4(), MEMBER_SCOPES, workspace_id=uuid.uuid4())
        with pytest.raises(PermissionDeniedError):
            principal.require_workspace(uuid.uuid4())

    def test_unbound_user_principal_passes_workspace_check(self):
        principal = user_principal(uuid.uuid4(), MEMBER_SCOPES)
        principal.require_workspace(uuid.uuid4())

    def test_has_all_scopes_is_all_or_nothing(self):
        principal = user_principal(uuid.uuid4(), READ_SCOPES)
        assert principal.has_all_scopes({"workspace:read", "memory:read"})
        assert not principal.has_all_scopes({"workspace:read", "memory:write"})

    def test_system_principal_requires_an_explicit_action(self):
        with pytest.raises(ValueError):
            system_principal(uuid.uuid4(), "", MEMBER_SCOPES)

    def test_system_principal_records_its_action(self):
        principal = system_principal(uuid.uuid4(), "import.retry", ALL_SCOPES)
        assert principal.actor_type == ActorType.SYSTEM
        assert principal.system_action == "import.retry"
        assert principal.is_system

    def test_principal_is_frozen(self):
        principal = user_principal(uuid.uuid4(), READ_SCOPES)
        with pytest.raises(Exception):
            principal.scopes = ALL_SCOPES
