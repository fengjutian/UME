"""Shared fixtures for the UME business-layer tests.

`server/` is the import root inside the container (uvicorn runs `main:app` from
that directory), so the tests put it on `sys.path` the same way
`tests/test_api_keys_router.py` does.
"""

import sys
from pathlib import Path

import pytest

SERVER_DIR = Path(__file__).resolve().parents[2]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

import models  # noqa: E402,F401  (registers `users`, `api_keys`, ... on Base.metadata)
import ume_app.models  # noqa: E402,F401  (registers UME tables on Base.metadata)
from db import Base  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402
from ume_app.models.workspace import Workspace  # noqa: E402
from ume_app.repositories.projects import ProjectRepository  # noqa: E402
from ume_app.repositories.workspaces import (  # noqa: E402
    WorkspaceMemberRepository,
    WorkspaceRepository,
)


@pytest.fixture
def db():
    """In-memory SQLite session covering the existing server tables plus UME tables.

    The UME repository guarantees under test are WHERE-clause guarantees, which
    behave identically on SQLite and PostgreSQL. PostgreSQL-only behaviour
    (JSONB operators, row-value indexes) is covered separately by the migration
    tests.
    """
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def users(db):
    """Three real `users` rows so workspace foreign keys resolve.

    alice/bob own the two tenants; carol is a non-owner used to exercise
    role-based denials.
    """
    from models import User

    made = []
    for name in ("alice", "bob", "carol"):
        user = User(name=name, email=f"{name}@example.test", password_hash="x")
        db.add(user)
        made.append(user)
    db.commit()
    return made


@pytest.fixture
def repos(db):
    return {
        "db": db,
        "workspaces": WorkspaceRepository(db),
        "members": WorkspaceMemberRepository(db),
        "projects": ProjectRepository(db),
    }


@pytest.fixture
def two_tenants(db, users, repos):
    """Two workspaces with one project each, owned by different users.

    This is the fixture the section 16.3 security tests need: same resource
    shape, different tenant boundary.
    """
    alice, bob = users[0], users[1]
    ws_a = Workspace(name="Workspace A", owner_user_id=alice.id, status="active")
    ws_b = Workspace(name="Workspace B", owner_user_id=bob.id, status="active")
    db.add_all([ws_a, ws_b])
    db.commit()

    repos["members"].add(ws_a.id, alice.id, "owner")
    repos["members"].add(ws_b.id, bob.id, "owner")
    project_a = repos["projects"].create(ws_a.id, "Project A")
    project_b = repos["projects"].create(ws_b.id, "Project B")
    db.commit()

    return {
        "workspace_a": ws_a,
        "workspace_b": ws_b,
        "project_a": project_a,
        "project_b": project_b,
        "alice": alice,
        "bob": bob,
        "alice_id": alice.id,
        "bob_id": bob.id,
    }


class ApiHandle:
    """TestClient for the mounted UME app plus the switch that picks the caller."""

    def __init__(self, client, holder, users, db):
        self.client = client
        self._holder = holder
        self.users = users
        self.db = db

    def as_user(self, index: int) -> "ApiHandle":
        self._holder["index"] = index
        return self

    @property
    def user_id(self):
        return self.users[self._holder["index"]].id

    def audit_events(self, **filters):
        from ume_app.models.audit import AuditEvent

        stmt = db_query(self.db, AuditEvent)
        for column, value in filters.items():
            stmt = stmt.filter(getattr(AuditEvent, column) == value)
        return stmt.order_by(AuditEvent.created_at).all()


def db_query(db, model):
    return db.query(model)


@pytest.fixture
def api(db, users, monkeypatch):
    """UME API client wired to the in-memory database.

    `get_actor` is overridden so a test can choose its caller, and
    `db.SessionLocal` is repointed at the same engine because denial auditing
    opens its own short-lived session. The wrapper app reproduces the
    request-id middleware that `server/main.py` installs in production, so
    `request_id` is exercised end to end instead of falling back to "-".
    """
    import db as db_module
    from db import get_db
    from errors import new_request_id, request_id_var
    from fastapi.testclient import TestClient
    from starlette.applications import Starlette
    from starlette.middleware import Middleware
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.routing import Mount
    from ume_app.api.app import ume_api
    from ume_app.auth.dependencies import get_actor
    from ume_app.auth.permissions import Principal

    monkeypatch.setattr(
        db_module,
        "SessionLocal",
        sessionmaker(bind=db.get_bind(), autoflush=False, expire_on_commit=False),
    )

    holder = {"index": 0}

    def fake_actor() -> Principal:
        return Principal(actor_type="user", actor_id=users[holder["index"]].id, scopes=frozenset())

    class RequestIdMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            rid = new_request_id()
            token = request_id_var.set(rid)
            try:
                response = await call_next(request)
                response.headers["X-Request-ID"] = rid
                return response
            finally:
                request_id_var.reset(token)

    wrapper = Starlette(
        routes=[Mount("/", app=ume_api)],
        middleware=[Middleware(RequestIdMiddleware)],
    )

    ume_api.dependency_overrides[get_db] = lambda: db
    ume_api.dependency_overrides[get_actor] = fake_actor
    try:
        # raise_server_exceptions=False so the catch-all Exception handler's
        # envelope reaches the test instead of being re-raised.
        yield ApiHandle(TestClient(wrapper, raise_server_exceptions=False), holder, users, db)
    finally:
        ume_api.dependency_overrides.clear()


@pytest.fixture
def engine():
    """Swap the memory engine for a fake for the duration of one test.

    Lives here rather than in `fake_engine.py` because pytest only discovers
    fixtures from conftest.py.
    """
    from fake_engine import FakeEngine
    from ume_app.engine.memory_adapter import set_adapter

    fake = FakeEngine()
    set_adapter(fake)
    try:
        yield fake
    finally:
        set_adapter(None)
