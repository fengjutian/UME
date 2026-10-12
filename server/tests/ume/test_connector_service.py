"""Connector service tests.

Scope checks and role checks are two independent guards. Over HTTP the scope
check usually fires first, which leaves the role gate untested — so these call
the service directly, the way a background job or an importer would.
"""

import pytest
from ume_app.auth.dependencies import resolve_access
from ume_app.auth.permissions import Principal
from ume_app.domain.enums import ActorType
from ume_app.domain.errors import ConflictError, PermissionDeniedError, ValidationError
from ume_app.models.base import utcnow
from ume_app.models.connector import Connector
from ume_app.repositories.connectors import ConnectorRepository
from ume_app.services import connectors as connector_service


@pytest.fixture
def user_access(db, users, two_tenants):
    from auth import create_access_token  # noqa: F401  (documents the auth surface used)

    principal = Principal(actor_type=ActorType.USER, actor_id=users[0].id, scopes=frozenset())
    return resolve_access(db, principal, two_tenants["workspace_a"].id)


@pytest.fixture
def connector_access(db, two_tenants):
    """A WorkspaceAccess for a connector bound to workspace A."""
    connector = Connector(
        workspace_id=two_tenants["workspace_a"].id,
        name="agent",
        connector_type="cli",
        credential_prefix="umec_abcdefgh",
        credential_hash="x",
        scopes=["memory:read", "memory:write"],
        capabilities={},
        status="active",
        created_by=two_tenants["alice_id"],
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    db.add(connector)
    db.flush()
    principal = Principal(
        actor_type=ActorType.CONNECTOR,
        actor_id=connector.id,
        scopes=frozenset(connector.scopes),
        workspace_id=connector.workspace_id,
    )
    return resolve_access(db, principal, connector.workspace_id)


class TestConnectorCannotAdminister:
    """The role gate, exercised where the scope check is not in the way."""

    def test_a_connector_cannot_create_a_credential(self, connector_access):
        with pytest.raises(PermissionDeniedError):
            connector_service.create(
                connector_access,
                name="escalate",
                connector_type="cli",
                scopes=["memory:read"],
                project_id=None,
                client_instance_id=None,
                capabilities=None,
            )

    def test_a_connector_cannot_revoke_a_credential(self, db, user_access, connector_access):
        connector, _ = connector_service.create(
            user_access,
            name="target",
            connector_type="cli",
            scopes=["memory:read"],
            project_id=None,
            client_instance_id=None,
            capabilities=None,
        )
        with pytest.raises(PermissionDeniedError):
            connector_service.revoke(connector_access, connector)

    def test_a_connector_cannot_update_a_credential(self, db, user_access, connector_access):
        connector, _ = connector_service.create(
            user_access,
            name="target",
            connector_type="cli",
            scopes=["memory:read"],
            project_id=None,
            client_instance_id=None,
            capabilities=None,
        )
        with pytest.raises(PermissionDeniedError):
            connector_service.update(connector_access, connector, name="renamed")

    def test_a_member_cannot_create_a_credential(self, db, users, two_tenants):
        from ume_app.models.workspace import WorkspaceMember

        db.add(WorkspaceMember(workspace_id=two_tenants["workspace_a"].id, user_id=users[2].id, role="member"))
        db.commit()
        principal = Principal(actor_type=ActorType.USER, actor_id=users[2].id, scopes=frozenset())
        access = resolve_access(db, principal, two_tenants["workspace_a"].id)
        with pytest.raises(PermissionDeniedError):
            connector_service.create(
                access,
                name="nope",
                connector_type="cli",
                scopes=["memory:read"],
                project_id=None,
                client_instance_id=None,
                capabilities=None,
            )


class TestScopeNarrowingAtServiceLevel:
    def test_narrowing_is_allowed(self, user_access):
        connector, _ = connector_service.create(
            user_access,
            name="a",
            connector_type="cli",
            scopes=["memory:read", "memory:write"],
            project_id=None,
            client_instance_id=None,
            capabilities=None,
        )
        updated = connector_service.update(user_access, connector, scopes=["memory:read"])
        assert updated.scopes == ["memory:read"]

    def test_widening_is_refused(self, user_access):
        connector, _ = connector_service.create(
            user_access,
            name="a",
            connector_type="cli",
            scopes=["memory:read"],
            project_id=None,
            client_instance_id=None,
            capabilities=None,
        )
        with pytest.raises(ConflictError):
            connector_service.update(user_access, connector, scopes=["memory:read", "memory:write"])

    def test_updating_a_revoked_connector_is_refused(self, user_access):
        connector, _ = connector_service.create(
            user_access,
            name="a",
            connector_type="cli",
            scopes=["memory:read"],
            project_id=None,
            client_instance_id=None,
            capabilities=None,
        )
        connector_service.revoke(user_access, connector)
        with pytest.raises(ConflictError):
            connector_service.update(user_access, connector, name="renamed")


class TestCredentialStorage:
    def test_only_the_hash_is_persisted(self, db, user_access):
        connector, plaintext = connector_service.create(
            user_access,
            name="a",
            connector_type="cli",
            scopes=["memory:read"],
            project_id=None,
            client_instance_id=None,
            capabilities=None,
        )
        stored = ConnectorRepository(db).require_in_workspace(user_access.workspace_id, connector.id)
        assert plaintext not in stored.credential_hash
        assert stored.credential_hash != plaintext
        assert stored.credential_prefix == plaintext[:16]
        assert "credential_hash" not in stored.as_dict()

    def test_two_connectors_get_distinct_prefixes(self, db, user_access):
        _, first = connector_service.create(
            user_access,
            name="a",
            connector_type="cli",
            scopes=["memory:read"],
            project_id=None,
            client_instance_id=None,
            capabilities=None,
        )
        _, second = connector_service.create(
            user_access,
            name="b",
            connector_type="cli",
            scopes=["memory:read"],
            project_id=None,
            client_instance_id=None,
            capabilities=None,
        )
        assert first[:16] != second[:16]

    def test_creating_with_a_foreign_project_is_refused(self, db, user_access, two_tenants):
        from ume_app.domain.errors import NotFoundError

        with pytest.raises(NotFoundError):
            connector_service.create(
                user_access,
                name="a",
                connector_type="cli",
                scopes=["memory:read"],
                project_id=two_tenants["project_b"].id,
                client_instance_id=None,
                capabilities=None,
            )


class TestConnectorProjectBinding:
    def test_a_project_bound_connector_is_confined_to_its_project(self, db, two_tenants):
        connector = Connector(
            workspace_id=two_tenants["workspace_a"].id,
            project_id=two_tenants["project_a"].id,
            name="scoped",
            connector_type="cli",
            credential_prefix="umec_projectbound",
            credential_hash="x",
            scopes=["memory:read"],
            capabilities={},
            status="active",
            created_by=two_tenants["alice_id"],
        )
        db.add(connector)
        db.flush()
        principal = Principal(
            actor_type=ActorType.CONNECTOR,
            actor_id=connector.id,
            scopes=frozenset(connector.scopes),
            workspace_id=connector.workspace_id,
            project_id=connector.project_id,
        )

        resolve_access(db, principal, two_tenants["workspace_a"].id, project_id=two_tenants["project_a"].id)
        with pytest.raises(PermissionDeniedError):
            resolve_access(db, principal, two_tenants["workspace_a"].id, project_id=two_tenants["project_b"].id)

    def test_a_workspace_wide_connector_is_not_confined(self, db, two_tenants):
        connector = Connector(
            workspace_id=two_tenants["workspace_a"].id,
            project_id=None,
            name="wide",
            connector_type="cli",
            credential_prefix="umec_workspacewide",
            credential_hash="x",
            scopes=["memory:read"],
            capabilities={},
            status="active",
            created_by=two_tenants["alice_id"],
        )
        db.add(connector)
        db.flush()
        principal = Principal(
            actor_type=ActorType.CONNECTOR,
            actor_id=connector.id,
            scopes=frozenset(connector.scopes),
            workspace_id=connector.workspace_id,
            project_id=None,
        )
        for project in (two_tenants["project_a"], two_tenants["project_b"]):
            resolve_access(db, principal, two_tenants["workspace_a"].id, project_id=project.id)


class TestScopeCeiling:
    def test_requesting_a_management_scope_is_refused(self):
        from ume_app.auth.credentials import normalise_scopes

        for scope in ("workspace:manage", "connector:manage", "export:read"):
            with pytest.raises(ValidationError):
                normalise_scopes([scope])

    def test_too_many_scopes_is_refused(self):
        from ume_app.auth.credentials import MAX_SCOPES_PER_CONNECTOR, normalise_scopes

        with pytest.raises(ValidationError):
            normalise_scopes(["memory:read"] * (MAX_SCOPES_PER_CONNECTOR + 1))
