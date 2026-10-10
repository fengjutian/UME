"""Mount integration: `/api/ume/v1` inside the real `server/main.py` app.

Everything else in `server/tests/ume/` exercises the UME app in isolation. This
module proves the one thing isolation cannot: that mounting it on the production
app keeps both halves working — UME paths get the new envelope, and the legacy
engine routes and `/docs` are untouched.

`server/main.py` builds a real memory engine at import time, so `Memory.from_config`
is patched the same way `tests/test_server_auth.py` does it.
"""

import importlib
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("fastapi", reason="fastapi not installed")

from fastapi.testclient import TestClient  # noqa: E402

SERVER_DIR = Path(__file__).resolve().parents[2]

#: Auth is left ON: with no credentials `verify_auth` raises before it opens a
#: session, so this exercises the real auth chain without needing PostgreSQL.
#: AUTH_DISABLED would instead resolve the default user, which does hit the DB.
ENV = {
    "JWT_SECRET": "test-secret-for-mount-integration",
    "OPENAI_API_KEY": "fake-key",
    "UME_TELEMETRY": "false",
}


@pytest.fixture(scope="module")
def server_app():
    if str(SERVER_DIR) not in sys.path:
        sys.path.insert(0, str(SERVER_DIR))
    try:
        import auth

        import ume
    except Exception as exc:  # pragma: no cover - depends on the local env
        pytest.skip(f"memory SDK is not importable here: {exc}")

    # `server/auth.py` reads these at import time. In a full-suite run it is
    # already imported by the time this fixture runs, so patching os.environ
    # alone would leave the cached empty JWT_SECRET in place and `main` would
    # refuse to import. Set the module attributes directly as well.
    for name, value in ENV.items():
        setattr(auth, name, value)
    auth.AUTH_DISABLED = False

    mock_instance = MagicMock()
    mock_instance.get_all.return_value = []
    mock_instance.search.return_value = []
    mock_instance.get.return_value = {"id": "mem-1", "memory": "test"}

    with patch.dict("os.environ", ENV):
        with patch.object(ume.Memory, "from_config", return_value=mock_instance):
            sys.modules.pop("main", None)
            try:
                yield importlib.import_module("main")
            finally:
                sys.modules.pop("main", None)


class TestMountedRoutes:
    def test_ume_prefix_is_mounted(self, server_app):
        mounted = [route.path for route in server_app.app.routes if "ume" in str(getattr(route, "path", ""))]
        assert mounted == ["/api/ume/v1"]

    def test_ume_openapi_is_reachable_through_the_parent(self, server_app):
        response = TestClient(server_app.app).get("/api/ume/v1/openapi.json")
        assert response.status_code == 200
        assert "/workspaces" in response.json()["paths"]

    def test_ume_routes_use_the_envelope(self, server_app):
        response = TestClient(server_app.app).get("/api/ume/v1/workspaces")
        assert response.status_code == 401
        body = response.json()
        assert set(body) == {"error", "request_id"}
        assert body["error"]["code"] == "UNAUTHENTICATED"

    def test_ume_validation_errors_use_the_envelope(self, server_app):
        """A malformed path parameter is a UME error, not a bare 422."""
        response = TestClient(server_app.app).get("/api/ume/v1/workspaces/not-a-uuid")
        assert set(response.json()) == {"error", "request_id"}
        assert response.json()["error"]["code"] in {"UNAUTHENTICATED", "VALIDATION_FAILED"}

    def test_a_legacy_route_error_keeps_the_detail_shape(self, server_app):
        """Legacy routes must not inherit the UME envelope, even on failure."""
        response = TestClient(server_app.app).get("/memories/anything")
        assert response.status_code == 401
        assert "detail" in response.json()
        assert "error" not in response.json()

    def test_legacy_docs_still_served(self, server_app):
        """The parent app keeps serving its own routes after the mount."""
        response = TestClient(server_app.app).get("/docs")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_parent_openapi_still_lists_legacy_routes(self, server_app):
        paths = TestClient(server_app.app).get("/openapi.json").json()["paths"]
        assert "/memories" in paths
        assert "/search" in paths

    def test_ume_paths_are_not_duplicated_on_the_parent_schema(self, server_app):
        paths = TestClient(server_app.app).get("/openapi.json").json()["paths"]
        assert not any(path.startswith("/api/ume") for path in paths)
