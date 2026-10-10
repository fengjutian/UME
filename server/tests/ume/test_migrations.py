"""Migration tests for 007_create_workspaces_projects (section 6 / 16.2).

Two layers:

* Offline DDL generation runs everywhere — it proves the revision is wired into
  the chain after 006 and emits the PostgreSQL DDL the spec asks for (JSONB
  columns, the composite unique, the three project indexes).
* A live upgrade/downgrade/upgrade round trip needs a real PostgreSQL. It is
  skipped unless `UME_TEST_DATABASE_URL` points at a throwaway database, because
  silently running against a developer's working database would destroy their
  data. Compose's own database is the intended target.
"""

import contextlib
import io
import os
import uuid
from pathlib import Path

import pytest

alembic = pytest.importorskip("alembic", reason="alembic not installed")

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from alembic.script import ScriptDirectory  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

SERVER_DIR = Path(__file__).resolve().parents[2]
ALEMBIC_INI = SERVER_DIR / "alembic.ini"

TEST_DATABASE_URL = os.environ.get("UME_TEST_DATABASE_URL", "")

requires_postgres = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="set UME_TEST_DATABASE_URL to a disposable PostgreSQL database to run migration round trips",
)


@pytest.fixture
def live_postgres(in_server_dir, monkeypatch):
    """Point `alembic/env.py` at the database named by UME_TEST_DATABASE_URL.

    `env.py` overrides `sqlalchemy.url` with `_build_database_url()`, which is
    assembled from POSTGRES_* variables. So the URL is decomposed into those
    variables rather than passed through, and the reconstruction is asserted:
    without that check a mistyped variable would let the round-trip tests run
    against a *different* database and still report success.
    """
    if not TEST_DATABASE_URL:
        pytest.skip("UME_TEST_DATABASE_URL is not set")
    url = make_url(TEST_DATABASE_URL)
    assert url.drivername.startswith("postgresql"), "live tests need a PostgreSQL URL"
    monkeypatch.setenv("POSTGRES_HOST", url.host or "127.0.0.1")
    monkeypatch.setenv("POSTGRES_PORT", str(url.port or 5432))
    monkeypatch.setenv("POSTGRES_USER", url.username or "postgres")
    monkeypatch.setenv("POSTGRES_PASSWORD", url.password or "")
    monkeypatch.setenv("APP_DB_NAME", (url.database or "postgres").removeprefix("/"))

    from db import _build_database_url

    rebuilt = make_url(_build_database_url())
    assert rebuilt.host == url.host and rebuilt.port == url.port
    assert rebuilt.database == url.database, "env.py would redirect the test to a different database"
    return TEST_DATABASE_URL


def _config(url: str | None = None) -> Config:
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(SERVER_DIR / "alembic"))
    if url:
        config.set_main_option("sqlalchemy.url", url)
    return config


@pytest.fixture
def in_server_dir(monkeypatch):
    """alembic.ini uses `script_location = alembic` and `prepend_sys_path = .`."""
    monkeypatch.chdir(SERVER_DIR)
    yield


class TestRevisionChain:
    def test_007_follows_006(self, in_server_dir):
        script = ScriptDirectory.from_config(_config())
        revisions = {rev.revision: rev for rev in script.walk_revisions()}
        assert "007" in revisions
        assert revisions["007"].down_revision == "006"

    def test_008_follows_007(self, in_server_dir):
        script = ScriptDirectory.from_config(_config())
        revisions = {rev.revision: rev for rev in script.walk_revisions()}
        assert revisions["008"].down_revision == "007"

    def test_chain_has_a_single_head(self, in_server_dir):
        script = ScriptDirectory.from_config(_config())
        assert script.get_heads() == ["010"]

    def test_the_chain_is_linear_with_no_branches(self, in_server_dir):
        """Every UME migration extends the previous one.

        Linear is a hard requirement here: the spec schedules the tables phase
        by phase, and a branch would let two migrations create the same table.
        """
        script = ScriptDirectory.from_config(_config())
        heads = set(script.get_heads())
        seen = set()
        revision = script.get_current_head()
        while revision is not None:
            assert revision not in seen, f"cycle at {revision}"
            seen.add(revision)
            down = script.get_revision(revision).down_revision
            if down is None:
                revision = None
            elif isinstance(down, (tuple, list)):
                assert len(down) == 1, f"{revision} branches into {down}"
                revision = down[0]
            else:
                revision = down
        assert heads <= seen

    def test_earlier_revisions_are_untouched(self, in_server_dir):
        script = ScriptDirectory.from_config(_config())
        revisions = {rev.revision: rev for rev in script.walk_revisions()}
        for revision in ("001", "002", "003", "004", "005", "006"):
            assert revision in revisions, f"missing pre-existing revision {revision}"


class TestOfflineDDL:
    @pytest.fixture
    def ddl(self, in_server_dir):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            command.upgrade(_config(), "006:007", sql=True)
        return buffer.getvalue()

    def test_creates_the_three_business_tables(self, ddl):
        for table in ("ume_workspaces", "ume_workspace_members", "ume_projects"):
            assert f"CREATE TABLE {table}" in ddl

    def test_jsonb_columns_with_defaults(self, ddl):
        assert "default_memory_policy JSONB" in ddl
        assert "'{}'::jsonb" in ddl
        assert "tags JSONB" in ddl
        assert "'[]'::jsonb" in ddl

    def test_membership_uniqueness_is_composite(self, ddl):
        assert "uq_ume_workspace_members_workspace_user" in ddl
        assert "UNIQUE (workspace_id, user_id)" in ddl

    def test_project_indexes_from_the_spec(self, ddl):
        assert "CREATE INDEX ix_ume_projects_workspace_id" in ddl
        assert "CREATE INDEX ix_ume_projects_workspace_status" in ddl
        assert "CREATE INDEX ix_ume_projects_last_activity_at" in ddl

    def test_owner_fk_is_restrict_not_cascade(self, ddl):
        """Deleting a user must never silently delete the workspaces they own."""
        workspaces = ddl.split("CREATE TABLE ume_workspaces")[1].split(");")[0]
        assert "FOREIGN KEY(owner_user_id) REFERENCES users (id) ON DELETE RESTRICT" in workspaces

    def test_child_tables_cascade_from_the_workspace(self, ddl):
        projects = ddl.split("CREATE TABLE ume_projects")[1].split(");")[0]
        assert "FOREIGN KEY(workspace_id) REFERENCES ume_workspaces (id) ON DELETE CASCADE" in projects

    def test_no_ume_table_touches_existing_tables(self, ddl):
        """Migration 007 must be additive: no ALTER/DROP against 001-006 tables."""
        for statement in ("ALTER TABLE users", "DROP TABLE users", "ALTER TABLE api_keys", "DROP TABLE api_keys"):
            assert statement not in ddl

    def test_full_chain_generates_without_error(self, in_server_dir):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            command.upgrade(_config(), "base:head", sql=True)
        ddl = buffer.getvalue()
        for table in ("users", "ume_workspaces", "ume_workspace_members", "ume_projects", "ume_audit_events"):
            assert f"CREATE TABLE {table}" in ddl


class TestOfflineAuditDDL:
    @pytest.fixture
    def ddl(self, in_server_dir):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            command.upgrade(_config(), "007:008", sql=True)
        return buffer.getvalue()

    def test_creates_the_audit_table(self, ddl):
        assert "CREATE TABLE ume_audit_events" in ddl

    def test_workspace_fk_is_set_null(self, ddl):
        """An audit row must outlive the workspace it refers to."""
        audit = ddl.split("CREATE TABLE ume_audit_events")[1].split(");")[0]
        assert "FOREIGN KEY(workspace_id) REFERENCES ume_workspaces (id) ON DELETE SET NULL" in audit

    def test_actor_id_is_not_a_foreign_key(self, ddl):
        audit = ddl.split("CREATE TABLE ume_audit_events")[1].split(");")[0]
        assert "FOREIGN KEY(actor_id)" not in audit

    def test_query_indexes(self, ddl):
        for index in (
            "ix_ume_audit_events_workspace_created",
            "ix_ume_audit_events_resource",
            "ix_ume_audit_events_actor",
        ):
            assert f"CREATE INDEX {index}" in ddl

    def test_is_additive(self, ddl):
        assert "ALTER TABLE ume_workspaces" not in ddl
        assert "DROP TABLE" not in ddl


class TestOfflineConversationDDL:
    @pytest.fixture
    def ddl(self, in_server_dir):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            command.upgrade(_config(), "008:009", sql=True)
        return buffer.getvalue()

    def test_creates_both_tables(self, ddl):
        assert "CREATE TABLE ume_conversations" in ddl
        assert "CREATE TABLE ume_messages" in ddl

    def test_content_presence_check(self, ddl):
        assert (
            "CONSTRAINT ck_ume_messages_has_content CHECK (content_text IS NOT NULL OR content_ref IS NOT NULL)" in ddl
        )

    def test_external_uniqueness_is_partial(self, ddl):
        """A NULL external id must not collide with every other NULL."""
        assert "CREATE UNIQUE INDEX uq_ume_conversations_external" in ddl
        assert "external_conversation_id IS NOT NULL" in ddl
        assert "CREATE UNIQUE INDEX uq_ume_messages_external" in ddl
        assert "external_message_id IS NOT NULL" in ddl

    def test_browse_and_dedup_indexes(self, ddl):
        assert "CREATE INDEX ix_ume_messages_conversation_browse" in ddl
        assert "CREATE INDEX ix_ume_messages_conversation_dedup" in ddl

    def test_project_fk_does_not_cascade_history(self, ddl):
        conversations = ddl.split("CREATE TABLE ume_conversations")[1].split(");")[0]
        assert "FOREIGN KEY(project_id) REFERENCES ume_projects (id) ON DELETE SET NULL" in conversations

    def test_is_additive(self, ddl):
        assert "ALTER TABLE" not in ddl
        assert "DROP TABLE" not in ddl


class TestOfflineImportDDL:
    @pytest.fixture
    def ddl(self, in_server_dir):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            command.upgrade(_config(), "009:010", sql=True)
        return buffer.getvalue()

    def test_creates_both_tables(self, ddl):
        assert "CREATE TABLE ume_import_jobs" in ddl
        assert "CREATE TABLE ume_idempotency_keys" in ddl

    def test_import_job_idempotency_unique(self, ddl):
        assert "CONSTRAINT uq_ume_import_jobs_workspace_idem UNIQUE (workspace_id, idempotency_key)" in ddl

    def test_idempotency_key_is_scoped_to_the_actor(self, ddl):
        """Two callers must not collide on, or read each other's, replay records."""
        assert (
            "CONSTRAINT uq_ume_idempotency_scope_key UNIQUE (workspace_id, actor_type, actor_id, idempotency_key)"
            in ddl
        )

    def test_request_hash_is_stored(self, ddl):
        keys = ddl.split("CREATE TABLE ume_idempotency_keys")[1].split(");")[0]
        assert "request_hash VARCHAR(64) NOT NULL" in keys
        assert "expires_at TIMESTAMP WITH TIME ZONE NOT NULL" in keys

    def test_is_additive(self, ddl):
        assert "ALTER TABLE" not in ddl
        assert "DROP TABLE" not in ddl


@requires_postgres
class TestLiveRoundTrip:
    """Upgrade/downgrade/upgrade against a real PostgreSQL (section 6)."""

    def test_upgrade_downgrade_upgrade_on_empty_database(self, live_postgres):
        config = _config(TEST_DATABASE_URL)
        command.downgrade(config, "base", sql=False)
        command.upgrade(config, "head")

        from sqlalchemy import create_engine, inspect

        engine = create_engine(TEST_DATABASE_URL)
        tables = set(inspect(engine).get_table_names())
        assert {"ume_workspaces", "ume_workspace_members", "ume_projects"} <= tables
        assert {"users", "api_keys", "settings", "request_logs"} <= tables

        command.downgrade(config, "006")
        tables_after = set(inspect(engine).get_table_names())
        assert not ({"ume_workspaces", "ume_workspace_members", "ume_projects"} & tables_after)
        assert {"users", "api_keys", "settings", "request_logs"} <= tables_after

        command.upgrade(config, "head")
        assert {"ume_workspaces", "ume_projects"} <= set(inspect(engine).get_table_names())
        engine.dispose()

    def test_upgrade_on_a_database_already_at_006_keeps_existing_data(self, live_postgres):
        from sqlalchemy import create_engine, inspect, text

        config = _config(TEST_DATABASE_URL)
        engine = create_engine(TEST_DATABASE_URL)
        try:
            command.downgrade(config, "base", sql=False)
            command.upgrade(config, "006")

            with engine.begin() as connection:
                connection.execute(
                    text(
                        "INSERT INTO users (id, name, email, password_hash, role) "
                        "VALUES (:id, 'existing', 'existing@example.test', 'x', 'admin')"
                    ),
                    {"id": uuid.uuid4()},
                )

            command.upgrade(config, "head")
            with engine.begin() as connection:
                kept = connection.execute(
                    text("SELECT count(*) FROM users WHERE email = :email"), {"email": "existing@example.test"}
                ).scalar_one()
                assert kept == 1, "upgrade 007 must not drop or hide existing users"

            indexes = {index["name"] for index in inspect(engine).get_indexes("ume_projects")}
            assert "ix_ume_projects_workspace_status" in indexes
        finally:
            command.downgrade(config, "base", sql=False)
            engine.dispose()
