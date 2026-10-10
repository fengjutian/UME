"""Route-table and handler-isolation contract for the UME API.

Section 9.3 lists the endpoints V1.0 must expose. Pinning the table means a
renamed route, a silently dropped verb or an accidental extra endpoint fails a
test instead of a client.
"""

from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from ume_app.api.app import create_ume_app
from ume_app.api.router import build_router
from ume_app.domain.errors import UmeError

#: Exactly the workspace/project surface Task 1.2 delivers. The conversation,
#: memory, graph, connector and export routes arrive with their own phases.
EXPECTED_ROUTES = {
    ("GET", "/workspaces"),
    ("POST", "/workspaces"),
    ("GET", "/workspaces/{workspace_id}"),
    ("PATCH", "/workspaces/{workspace_id}"),
    ("DELETE", "/workspaces/{workspace_id}"),
    ("GET", "/workspaces/{workspace_id}/members"),
    ("POST", "/workspaces/{workspace_id}/members"),
    ("PATCH", "/workspaces/{workspace_id}/members/{user_id}"),
    ("DELETE", "/workspaces/{workspace_id}/members/{user_id}"),
    ("GET", "/workspaces/{workspace_id}/projects"),
    ("POST", "/workspaces/{workspace_id}/projects"),
    ("GET", "/projects/{project_id}"),
    ("PATCH", "/projects/{project_id}"),
    ("DELETE", "/projects/{project_id}"),
}


def _actual_routes(router) -> set[tuple[str, str]]:
    verbs = {"GET", "POST", "PATCH", "PUT", "DELETE"}
    return {((route.methods & verbs).pop(), route.path) for route in router.routes if isinstance(route, APIRoute)}


class TestRouteTable:
    def test_router_exposes_exactly_the_documented_surface(self):
        assert _actual_routes(build_router()) == EXPECTED_ROUTES

    def test_no_legacy_engine_route_leaked_into_ume(self):
        paths = {route.path for route in build_router().routes}
        assert not {"/memories", "/search", "/configure"} & paths

    def test_router_prefix_is_the_ume_v1_path(self):
        from ume_app.api.router import API_PREFIX

        assert API_PREFIX == "/api/ume/v1"


class TestHandlerIsolation:
    def test_ume_handlers_are_registered_on_the_ume_app_only(self):
        ume = create_ume_app()
        legacy = FastAPI()
        # FastAPI pre-registers three defaults; the UME app must add to that set
        # without the parent app gaining any of them.
        defaults = set(legacy.exception_handlers)
        ume_handlers = set(ume.exception_handlers)
        assert defaults < ume_handlers
        assert set(legacy.exception_handlers) == defaults
        assert {UmeError, IntegrityError, Exception} <= ume_handlers

    def test_a_legacy_route_keeps_the_detail_shape(self):
        """The mounted app must not reshape responses on the parent app."""
        ume = create_ume_app()
        legacy = FastAPI()
        legacy.mount("/api/ume/v1", ume)

        @legacy.get("/memories/{memory_id}")
        def get_memory(memory_id: str):
            return {"id": memory_id, "memory": "legacy shape"}

        response = TestClient(legacy).get("/memories/abc")
        assert response.status_code == 200
        assert response.json() == {"id": "abc", "memory": "legacy shape"}
        assert "data" not in response.json()

    def test_ume_route_inside_the_parent_still_uses_the_envelope(self):
        ume = create_ume_app()
        legacy = FastAPI()
        legacy.mount("/api/ume/v1", ume)

        response = TestClient(legacy).get("/api/ume/v1/workspaces")
        body = response.json()
        assert set(body) == {"error", "request_id"}
        assert body["error"]["code"] == "UNAUTHENTICATED"
