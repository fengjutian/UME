import { describe, expect, it } from "vitest";
import {
  UME_ENDPOINTS,
  UME_LIMITS,
  UME_PREFIX,
  query,
} from "@/utils/api-endpoints";

describe("UME_PREFIX", () => {
  it("is the path technical doc §9.3 defines", () => {
    expect(UME_PREFIX).toBe("/api/ume/v1");
  });
});

describe("query", () => {
  it("drops undefined, null and empty string", () => {
    // A filter sent as `?status=` is a real empty filter to the server, not an
    // absent one, so an unset filter must never reach the wire at all.
    expect(
      query({
        workspace_id: "w1",
        status: undefined,
        memory_type: null,
        project_id: "",
        limit: 50,
      }),
    ).toEqual({ workspace_id: "w1", limit: 50 });
  });

  it("keeps false, which is a meaningful value and not an absent one", () => {
    expect(query({ include_deleted: false })).toEqual({
      include_deleted: false,
    });
  });

  it("keeps zero", () => {
    expect(query({ limit: 0 })).toEqual({ limit: 0 });
  });

  it("returns an empty object for an all-absent set", () => {
    expect(query({ a: undefined, b: null })).toEqual({});
  });
});

describe("endpoint builders", () => {
  it("scopes every business route under the v1 prefix", () => {
    const paths = [
      UME_ENDPOINTS.MEMORIES,
      UME_ENDPOINTS.MEMORY("m1"),
      UME_ENDPOINTS.MEMORY_SOURCES("m1"),
      UME_ENDPOINTS.MEMORY_VERSIONS("m1"),
      UME_ENDPOINTS.MEMORY_ARCHIVE("m1"),
      UME_ENDPOINTS.MEMORY_RESTORE("m1"),
      UME_ENDPOINTS.MEMORY_FORGET("m1"),
      UME_ENDPOINTS.MEMORY_RETRY("m1"),
      UME_ENDPOINTS.MEMORY_SEARCH,
      UME_ENDPOINTS.GRAPH,
      UME_ENDPOINTS.GRAPH_NEIGHBORS("n1"),
      UME_ENDPOINTS.GRAPH_EDGES,
      UME_ENDPOINTS.GRAPH_EDGE("e1"),
      UME_ENDPOINTS.TIMELINE,
      UME_ENDPOINTS.CONTEXT,
      UME_ENDPOINTS.CONNECTORS,
      UME_ENDPOINTS.CONNECTOR("c1"),
      UME_ENDPOINTS.CONNECTOR_REVOKE("c1"),
    ];
    for (const path of paths) {
      expect(path.startsWith(`${UME_PREFIX}/`)).toBe(true);
    }
  });

  it("interpolates the id into the path", () => {
    expect(UME_ENDPOINTS.MEMORY("abc")).toBe("/api/ume/v1/memories/abc");
    expect(UME_ENDPOINTS.GRAPH_NEIGHBORS("n7")).toBe(
      "/api/ume/v1/graph/nodes/n7/neighbors",
    );
    expect(UME_ENDPOINTS.CONNECTOR_REVOKE("c9")).toBe(
      "/api/ume/v1/connectors/c9/revoke",
    );
  });

  it("has no trailing slash, which the CLI contract test also requires", () => {
    for (const path of Object.values(UME_ENDPOINTS)) {
      if (typeof path !== "string") continue;
      expect(path.endsWith("/")).toBe(false);
    }
  });
});

describe("UME_LIMITS", () => {
  it("mirrors the server caps instead of inventing new ones", () => {
    // graph.py: limit=Query(ge=1, le=MAX_INITIAL_NODES), neighbors le=MAX_NEIGHBORS_PER_NODE
    // memory.py:  limit=Query(ge=1, le=100) on MemorySearchRequest
    // graph.py:  token_budget=Field(ge=1, le=64000)
    expect(UME_LIMITS.graphInitialNodes).toBe(100);
    expect(UME_LIMITS.graphNeighborsPerNode).toBe(50);
    expect(UME_LIMITS.searchLimit).toBe(100);
    expect(UME_LIMITS.contextTokenBudget).toBe(64000);
  });
});
