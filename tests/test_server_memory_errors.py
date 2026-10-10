"""Legacy engine route error classification.

Two defects found during the P0 baseline run, both reproduced against a live
server and both reported to a caller as something other than the truth:

1. `GET /memories/{id}` with a non-UUID id surfaced psycopg's
   `InvalidTextRepresentation`, which nothing in `errors.py` classifies, so the
   generic `except` reported a 502 "Upstream provider error". A client that
   mistyped an id was told to go debug their LLM provider.
2. `GET /memories/{id}` for a well-formed but unknown UUID returned 200 with a
   `null` body, so "this memory does not exist" was indistinguishable from a
   successful read at the status-code level.

These are pre-existing behaviours of the legacy `/memories` routes, which the
implementation doc keeps alive for backwards compatibility.
"""

import importlib
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("fastapi", reason="fastapi not installed")

from fastapi.testclient import TestClient  # noqa: E402

SERVER_DIR = Path(__file__).resolve().parents[1] / "server"
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

ENV = {
    "ADMIN_API_KEY": "",
    "OPENAI_API_KEY": "fake-key",
    "UME_TELEMETRY": "false",
    "AUTH_DISABLED": "true",
    "JWT_SECRET": "test-secret-for-memory-error-classification",
}

KNOWN_ID = "3f1c8a2e-1b4d-4c6e-9a7f-2d5e8b0c1a34"
UNKNOWN_ID = "00000000-0000-0000-0000-000000000000"


def _named(name: str, message: str = "invalid input syntax for type uuid"):
    """Build an exception whose class name matches a psycopg error class.

    A local stand-in rather than importing psycopg's classes so the test does
    not depend on which driver the test environment happens to have installed.
    `errors._classify` dispatches on `type(exc).__name__`, so the name is the
    whole contract.
    """
    return type(name, (Exception,), {})(message)


@pytest.fixture
def client_factory():
    """Build a TestClient over a freshly imported `server/main.py`.

    `main` re-executes its module body on every import, which is the only way to
    pick up the patched Memory instance; the previous copy is popped first so
    the import is genuinely re-run rather than served from sys.modules.
    """

    def _build(get_result, get_side_effect=None):
        mock_instance = MagicMock()
        mock_instance.get.return_value = get_result
        if get_side_effect is not None:
            mock_instance.get.side_effect = get_side_effect
        mock_instance.get_all.return_value = []
        mock_instance.search.return_value = []

        # `server/auth.py` reads AUTH_DISABLED / JWT_SECRET at import time and
        # caches them as module constants. Re-importing `main` does not re-run
        # `auth`, so patching os.environ alone leaves the cached value from
        # whichever test imported it first and `main` refuses to import.
        # Set the attributes directly as well as the environment.
        import auth

        for name, value in ENV.items():
            setattr(auth, name, value)
        auth.AUTH_DISABLED = True

        sys.modules.pop("main", None)
        with patch.dict(os.environ, ENV):
            with patch("ume.Memory.from_config", return_value=mock_instance):
                main = importlib.import_module("main")
        return TestClient(main.app)

    return _build


class TestMalformedMemoryId:
    def test_non_uuid_id_is_a_client_error_not_an_upstream_failure(self, client_factory):
        for name in ("InvalidTextRepresentation", "DataError"):
            client = client_factory(None, get_side_effect=_named(name))
            response = client.get("/memories/not-a-uuid")
            assert response.status_code == 400, f"{name} produced {response.status_code}"
            body = response.json()
            assert body.get("code") != "unknown"
            assert body.get("code") == "invalid_request"
            assert body["request_id"]

    def test_the_message_names_the_request_not_the_provider(self, client_factory):
        client = client_factory(None, get_side_effect=_named("InvalidTextRepresentation"))
        response = client.get("/memories/not-a-uuid")
        assert "upstream" not in response.json()["detail"].lower()


class TestUnknownMemoryId:
    def test_unknown_uuid_is_404(self, client_factory):
        client = client_factory(None)
        response = client.get(f"/memories/{UNKNOWN_ID}")
        assert response.status_code == 404
        assert response.json()["detail"]

    def test_known_id_still_returns_its_payload(self, client_factory):
        client = client_factory({"id": KNOWN_ID, "memory": "hello"})
        response = client.get(f"/memories/{KNOWN_ID}")
        assert response.status_code == 200
        assert response.json()["memory"] == "hello"


class TestRegressionGuard:
    def test_classifier_still_maps_real_upstream_errors(self):
        """The new 400 branch must not swallow genuine provider failures."""
        from errors import _classify

        code, _ = _classify(_named("OperationalError"))
        assert code in {"datastore_unavailable", "vector_store_unavailable", "unknown"}
        assert code != "invalid_request"