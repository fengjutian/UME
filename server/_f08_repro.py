"""F-08 reproduction: does the real engine path work for writes, not just reads?

M0 recorded that `/memory-search` and `/context` return 500. Code reading says
the same guard also fires in `Memory.add`, which would mean `POST /memories`
never writes anything either. This probes both against a live server so the
conclusion rests on a response code rather than on reading the SDK.

Disposable database only. Not a test, not shipped.
"""

import json
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8889"
PREFIX = "/api/ume/v1"
EMAIL = "f08@ume.example.com"
PASSWORD = "f08-password-123"


def call(method, path, body=None, token=None):
    req = urllib.request.Request(f"{BASE}{path}", method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    req.data = json.dumps(body).encode() if body is not None else None
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            return response.status, json.loads(response.read().decode() or "{}")
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode() or "{}")


_, login = call("POST", "/auth/login", body={"email": EMAIL, "password": PASSWORD})
if "access_token" not in login:
    call("POST", "/auth/register", body={"name": "F08 Admin", "email": EMAIL, "password": PASSWORD})
    _, login = call("POST", "/auth/login", body={"email": EMAIL, "password": PASSWORD})
token = login["access_token"]

_, ws = call("POST", f"{PREFIX}/workspaces", body={"name": "f08-probe"}, token=token)
workspace_id = ws["data"]["id"]
print(f"workspace = {workspace_id}\n")

steps = [
    (
        "POST /memories (write)",
        "POST",
        f"{PREFIX}/memories",
        {
            "workspace_id": workspace_id,
            "messages": [{"role": "user", "content": "The deploy key rotates every 90 days."}],
            "infer": True,
        },
    ),
    (
        "GET /memories (read projection)",
        "GET",
        f"{PREFIX}/memories?workspace_id={workspace_id}",
        None,
    ),
    (
        "POST /memory-search (engine read)",
        "POST",
        f"{PREFIX}/memory-search",
        {"workspace_id": workspace_id, "query": "deploy key"},
    ),
    (
        "POST /context (engine read)",
        "POST",
        f"{PREFIX}/context",
        {"workspace_id": workspace_id, "query": "deploy key"},
    ),
]

for label, method, path, body in steps:
    status, parsed = call(method, path, body, token)
    error = parsed.get("error")
    detail = json.dumps(error, ensure_ascii=False)[:110] if error else "ok"
    print(f"{label:34s} -> {status}  {detail}")