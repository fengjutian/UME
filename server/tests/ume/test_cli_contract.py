"""CLI contract against the self-hosted API (Task 0.2).

`cli/cli-spec.json` is the shared behaviour contract, but it currently describes
the hosted platform's `/v1` and `/v2` routes. The self-hosted server in
`server/` exposes none of them. Until P4 lands the profile rewrite, these tests
stay red on purpose: they are the executable proof of the gap, and `strict=True`
means that fixing the CLI turns each one into a failure that forces the marker to
be removed.

The minimal compatibility design is recorded in
`docs/specs/UME-P0-BASELINE-REPORT.md`.
"""

import json
from pathlib import Path

import pytest
from ume_app.api.router import build_router

CLI_SPEC = Path(__file__).resolve().parents[2].parent / "cli" / "cli-spec.json"

#: The self-hosted routes the CLI operations would have to target, taken from
#: `server/main.py` and `server/routers/entities.py`.
LOCAL_SERVER_ROUTES = {
    ("POST", "/memories"),
    ("GET", "/memories"),
    ("GET", "/memories/{memory_id}"),
    ("PUT", "/memories/{memory_id}"),
    ("DELETE", "/memories/{memory_id}"),
    ("DELETE", "/memories"),
    ("POST", "/search"),
    ("GET", "/entities"),
    ("DELETE", "/entities/{entity_type}/{entity_id}"),
}

#: Which self-hosted route each CLI operation should map onto.
CLI_OPERATION_TO_LOCAL_ROUTE = {
    "add": ("POST", "/memories"),
    "search": ("POST", "/search"),
    "get": ("GET", "/memories/{memory_id}"),
    "list": ("GET", "/memories"),
    "update": ("PUT", "/memories/{memory_id}"),
    "delete": ("DELETE", "/memories/{memory_id}"),
    "deleteAll": ("DELETE", "/memories"),
    "entities": ("GET", "/entities"),
    "deleteEntities": ("DELETE", "/entities/{entity_type}/{entity_id}"),
}

xfail_reason = "P0.2: the CLI still targets the hosted /v1 and /v2 routes; fixed in P4"


@pytest.fixture(scope="module")
def cli_api() -> dict:
    return json.loads(CLI_SPEC.read_text(encoding="utf-8"))["api"]


class TestRouteAlignment:
    @pytest.mark.xfail(strict=True, reason=xfail_reason)
    @pytest.mark.parametrize("operation", sorted(CLI_OPERATION_TO_LOCAL_ROUTE))
    def test_cli_endpoint_matches_the_local_route(self, cli_api, operation):
        endpoint = cli_api["endpoints"][operation]
        assert (endpoint["method"], endpoint["path"]) == CLI_OPERATION_TO_LOCAL_ROUTE[operation]

    @pytest.mark.xfail(strict=True, reason=xfail_reason)
    def test_cli_spec_targets_no_hosted_version_prefix(self, cli_api):
        offenders = {
            name: endpoint["path"]
            for name, endpoint in cli_api["endpoints"].items()
            if endpoint["path"].startswith(("/v1/", "/v2/"))
        }
        assert offenders == {}

    def test_local_routes_are_not_claimed_to_be_covered(self, cli_api):
        """Guards the *other* direction: the spec must not silently grow a
        hosted-only endpoint that no local route can ever serve."""
        local_paths = {path for _, path in LOCAL_SERVER_ROUTES}
        for name, endpoint in cli_api["endpoints"].items():
            if endpoint["path"] in local_paths:
                continue
            assert endpoint["path"].startswith(("/v1/", "/v2/")), (
                f"{name} points at {endpoint['path']}, which is neither a local route nor a known hosted prefix"
            )


class TestAuthAlignment:
    @pytest.mark.xfail(strict=True, reason=xfail_reason)
    def test_auth_scheme_matches_the_local_server(self, cli_api):
        """The server accepts `Authorization: Bearer <jwt>` or `X-API-Key`.

        The CLI sends `Authorization: Token <key>`, which the server's
        `HTTPBearer` scheme never parses.
        """
        assert cli_api["authScheme"] in {"Bearer", "api-key"}

    def test_the_compatibility_mapping_is_complete_and_consistent(self):
        """The proposed local mapping must cover every CLI operation and every
        target must actually be a route the self-hosted server declares."""
        assert set(CLI_OPERATION_TO_LOCAL_ROUTE) == set(
            json.loads(CLI_SPEC.read_text(encoding="utf-8"))["api"]["endpoints"]
        )
        assert set(CLI_OPERATION_TO_LOCAL_ROUTE.values()) <= LOCAL_SERVER_ROUTES


class TestUmeSurfaceIsNotOnTheCliYet:
    def test_cli_spec_has_no_ume_v1_endpoints(self):
        """P4 will add these; until then nothing should pretend to serve them."""
        api = json.loads(CLI_SPEC.read_text(encoding="utf-8"))["api"]
        ume_paths = [e["path"] for e in api["endpoints"].values() if "/api/ume" in e["path"]]
        assert ume_paths == []

    def test_ume_routes_exist_on_the_server(self):
        """Sanity: the surface the CLI will eventually target really is there."""
        ume_paths = {route.path for route in build_router().routes if hasattr(route, "path")}
        assert {"/workspaces", "/projects/{project_id}"} <= ume_paths
