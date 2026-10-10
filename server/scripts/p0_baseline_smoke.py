"""P0 baseline smoke: exercise the running server over HTTP.

Run against a live `server/` on :8888 with PostgreSQL migrated to head.
Every step prints PASS/FAIL and the script exits non-zero if anything failed,
so the baseline report can quote it verbatim instead of a human summary.

One step needs a second identity, and `/auth/register` only ever creates the
first admin. That tenant is therefore provisioned straight through the server's
own models and signed with the server's own token helper — a harness action,
not an API path, and labelled as such in the output.
"""

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

BASE = os.environ.get("UME_BASELINE_URL", "http://127.0.0.1:8888")
ADMIN_EMAIL = "baseline@ume.example.com"
PASSWORD = "baseline-password-123"
OTHER_EMAIL = "baseline-tenant2@ume.example.com"

results = []


def call(method, path, *, body=None, headers=None, expect=None):
    url = f"{BASE}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    for key, value in (headers or {}).items():
        req.add_header(key, value)
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            status, raw = response.status, response.read().decode()
    except urllib.error.HTTPError as exc:
        status, raw = exc.code, exc.read().decode()
    try:
        parsed = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        parsed = {"_raw": raw[:200]}
    if expect is not None and status != expect:
        raise AssertionError(f"{method} {path} -> {status} (expected {expect}): {raw[:250]}")
    return status, parsed


def check(label, fn):
    try:
        detail = fn()
        results.append((True, label, detail))
        print(f"PASS  {label}" + (f" — {detail}" if detail else ""))
    except Exception as exc:  # noqa: BLE001 - the report needs every failure, not the first
        results.append((False, label, str(exc)))
        print(f"FAIL  {label} — {exc}")


def _token(login):
    token = login.get("access_token") or login.get("data", {}).get("access_token")
    if not token:
        raise AssertionError(f"login returned no access token: {list(login)}")
    return token


def ensure_admin():
    status, body = call("GET", "/auth/setup-status")
    register = call(
        "POST", "/auth/register", body={"name": "Baseline Admin", "email": ADMIN_EMAIL, "password": PASSWORD}
    )
    if register[0] in (200, 201):
        # The response carries live tokens; the label is all the report needs.
        return "registered first admin", {"outcome": "registered"}
    # 403 = registration closed, 409 = a different account got there first,
    # 429 = the 5/minute register limiter tripped because this script was re-run.
    if register[0] in (403, 409, 429):
        call("POST", "/auth/login", body={"email": ADMIN_EMAIL, "password": PASSWORD}, expect=200)
        return "admin already existed, logged in", {"outcome": "logged_in"}
    raise AssertionError(f"register returned {register[0]}")


def provision_second_tenant():
    """Create a user outside the API and mint its token with the server's helper."""
    from auth import create_access_token
    from db import SessionLocal
    from models import User
    from sqlalchemy import select

    with SessionLocal() as session:
        existing = session.scalar(select(User).where(User.email == OTHER_EMAIL))
        if existing is None:
            from passlib.context import CryptContext

            existing = User(
                name="Baseline Tenant 2",
                email=OTHER_EMAIL,
                password_hash=CryptContext(schemes=["bcrypt"]).hash(PASSWORD),
                # migration 004 enforces at-most-one-admin, so the second
                # identity must be an ordinary user.
                role="user",
            )
            session.add(existing)
            session.commit()
        token = create_access_token(str(existing.id), existing.role)
    return {"Authorization": f"Bearer {token}"}


def main():
    _, register_detail = ensure_admin()
    login = call("POST", "/auth/login", body={"email": ADMIN_EMAIL, "password": PASSWORD}, expect=200)[1]
    auth = {"Authorization": f"Bearer {_token(login)}"}
    other_auth = provision_second_tenant()
    state = {"workspace_id": None}

    def step_setup_status():
        _, body = call("GET", "/auth/setup-status")
        if body.get("needsSetup") is not False:
            raise AssertionError(f"needsSetup should be False after registration: {body}")
        return register_detail

    def step_api_keys():
        status, created = call("POST", "/api-keys", body={"label": "baseline"}, headers=auth)
        if status not in (200, 201):
            raise AssertionError(f"key create returned {status}: {created}")
        raw = created.get("key") or created.get("data", {}).get("key")
        if not raw:
            raise AssertionError(f"no key returned: {list(created)}")
        call("GET", "/api-keys", headers=auth, expect=200)
        return f"created + listed, prefix={raw[:8]}..."

    def step_legacy_search():
        status, _ = call("POST", "/search", body={"query": "hello", "user_id": "baseline"}, headers=auth)
        if status not in (200, 502):
            raise AssertionError(f"unexpected status {status}")
        return f"POST /search -> {status} (502 = upstream error, expected without a real LLM key)"

    def step_legacy_memory_shape():
        status, body = call("GET", "/memories/nonexistent-id", headers=auth)
        if status == 200:
            raise AssertionError("expected a non-200 for an unknown memory id")
        if "detail" not in body:
            raise AssertionError(f"legacy route lost its detail shape: {list(body)}")
        return f"status {status} still uses {{'detail': ...}}"

    def step_ume_unauthenticated():
        status, body = call("GET", "/api/ume/v1/workspaces")
        if status != 401 or "error" not in body:
            raise AssertionError(f"expected a UME envelope 401, got {status} {body}")
        return body["error"]["code"]

    def step_ume_crud():
        _, ws = call("POST", "/api/ume/v1/workspaces", body={"name": "Baseline"}, headers=auth, expect=201)
        workspace_id = ws["data"]["id"]
        state["workspace_id"] = workspace_id
        if not ws["request_id"]:
            raise AssertionError("response carried no request_id")

        call("PATCH", f"/api/ume/v1/workspaces/{workspace_id}", body={"description": "d"}, headers=auth, expect=200)
        _, project = call(
            "POST",
            f"/api/ume/v1/workspaces/{workspace_id}/projects",
            body={"name": "Smoke", "tags": ["p0"]},
            headers=auth,
            expect=201,
        )
        project_id = project["data"]["id"]
        _, listed = call("GET", f"/api/ume/v1/workspaces/{workspace_id}/projects", headers=auth, expect=200)
        if not listed["data"]["items"]:
            raise AssertionError("project list is empty")
        _, fetched = call("GET", f"/api/ume/v1/projects/{project_id}", headers=auth, expect=200)
        if fetched["data"]["name"] != "Smoke":
            raise AssertionError(f"project read back wrong: {fetched['data']['name']}")
        return f"workspace={workspace_id[:8]} project={project_id[:8]}"

    def step_ume_isolation():
        workspace_id = state["workspace_id"]
        for method, path in (
            ("GET", f"/api/ume/v1/workspaces/{workspace_id}"),
            ("GET", f"/api/ume/v1/workspaces/{workspace_id}/projects"),
            ("POST", f"/api/ume/v1/workspaces/{workspace_id}/projects"),
        ):
            status, body = call(method, path, body={"name": "x"} if method == "POST" else None, headers=other_auth)
            if status != 404 or body["error"]["code"] != "NOT_FOUND":
                raise AssertionError(f"{method} {path} returned {status} {body}")
        _, listed = call("GET", "/api/ume/v1/workspaces", headers=other_auth, expect=200)
        if listed["data"]["items"]:
            raise AssertionError("tenant 2 can see tenant 1 workspaces")
        return "3 routes -> 404, tenant list empty"

    def step_import_dedup():
        workspace_id = state["workspace_id"]
        payload = {
            "format_version": "1.0",
            "workspace_id": workspace_id,
            "external_conversation_id": "baseline-1",
            "messages": [
                {"role": "user", "content": "hello", "timestamp": "2026-10-01T12:00:00Z", "external_message_id": "m1"},
                {
                    "role": "assistant",
                    "content": "hi",
                    "timestamp": "2026-10-01T12:00:05Z",
                    "external_message_id": "m2",
                },
            ],
        }
        _, first = call(
            "POST",
            "/api/ume/v1/conversations/imports",
            body=payload,
            headers={**auth, "Idempotency-Key": "b1"},
            expect=201,
        )
        _, second = call(
            "POST",
            "/api/ume/v1/conversations/imports",
            body=payload,
            headers={**auth, "Idempotency-Key": "b2"},
            expect=201,
        )
        inserted = first["data"]["result_summary"]["inserted"]
        replay_inserted = second["data"]["result_summary"]["inserted"]
        if inserted != 2 or replay_inserted != 0:
            raise AssertionError(f"dedup failed: {inserted} then {replay_inserted}")

        _, preview = call("POST", "/api/ume/v1/conversations/imports/preview", body=payload, headers=auth, expect=200)
        if preview["data"]["duplicate_count"] != 2:
            raise AssertionError(f"preview missed duplicates: {preview['data']}")

        _, replay = call(
            "POST",
            "/api/ume/v1/conversations/imports",
            body=payload,
            headers={**auth, "Idempotency-Key": "b1"},
            expect=201,
        )
        if not replay["data"]["replayed"]:
            raise AssertionError("same idempotency key did not replay")

        conversation_id = first["data"]["result_summary"]["conversation_id"]
        _, messages = call("GET", f"/api/ume/v1/conversations/{conversation_id}/messages", headers=auth, expect=200)
        if len(messages["data"]["items"]) != 2:
            raise AssertionError(f"expected 2 archived messages, got {len(messages['data']['items'])}")
        return "2 imported -> 0 duplicates -> replayed -> 2 archived"

    def step_request_log():
        call("GET", "/requests", headers=auth, expect=200)
        return "GET /requests -> 200"

    check("auth setup-status", step_setup_status)
    check("auth register + login", lambda: "access token issued")
    check("API key create + list", step_api_keys)
    check("legacy /search reachable", step_legacy_search)
    check("legacy error shape unchanged", step_legacy_memory_shape)
    check("UME rejects unauthenticated", step_ume_unauthenticated)
    check("UME workspace/project CRUD", step_ume_crud)
    check("UME cross-workspace isolation", step_ume_isolation)
    check("UME import dedup + idempotency", step_import_dedup)
    check("request log query", step_request_log)

    failed = [row for row in results if not row[0]]
    print(f"\n{len(results) - len(failed)}/{len(results)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
