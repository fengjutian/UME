import { beforeEach, describe, expect, it, vi } from "vitest";

/**
 * The shared axios instance is replaced wholesale. `utils/api.ts` installs a
 * response interceptor that unwraps the outer envelope and rejects with the
 * *inner* `{ code, message, details }` object; reproducing that here is the
 * whole point, because it is the shape the UME layer actually receives.
 */
const api = {
  get: vi.fn(),
  post: vi.fn(),
  patch: vi.fn(),
  put: vi.fn(),
  delete: vi.fn(),
};

vi.mock("@/utils/api", () => ({ api }));

const {
  UmeApiError,
  buildContext,
  createConnector,
  listMemories,
  loadGraph,
  loadTimeline,
  revokeConnector,
  searchMemories,
  unwrap,
} = await import("@/utils/ume-api");

const ok = (data: unknown) => ({ data: { data, request_id: "req_1" } });

beforeEach(() => {
  vi.clearAllMocks();
});

describe("unwrap", () => {
  it("returns the payload of a success envelope", () => {
    expect(unwrap<{ id: string }>({ data: { id: "m1" }, request_id: "r" })).toEqual({
      id: "m1",
    });
  });

  it("throws rather than resolving undefined on an error envelope", () => {
    // A failed request that resolves to `undefined` renders as "no data yet",
    // which is how a broken endpoint looks like an empty workspace.
    expect(() =>
      unwrap({ error: { code: "NOT_FOUND", message: "gone", details: null }, request_id: "r" }),
    ).toThrow(UmeApiError);
  });

  it("carries the server code and message onto the thrown error", () => {
    try {
      unwrap({ error: { code: "PERMISSION_DENIED", message: "nope", details: null }, request_id: "r" });
      expect.unreachable();
    } catch (error) {
      expect(error).toBeInstanceOf(UmeApiError);
      expect((error as UmeApiError).code).toBe("PERMISSION_DENIED");
      expect((error as UmeApiError).message).toBe("nope");
    }
  });
});

describe("error mapping", () => {
  /**
   * Regression test. With the previous matcher this failed with the literal
   * "Request failed" and code "REQUEST_FAILED": the rejected value is a plain
   * object, so `axiosError.response` is undefined and the server's own message
   * was unreachable. Every UME failure surfaced as the same useless string.
   */
  it("keeps the server code and message when the interceptor rejects the inner error object", async () => {
    api.get.mockRejectedValue({
      code: "VALIDATION_FAILED",
      message: "One or more scopes are not available to connectors.",
      details: { rejected: ["memories:read"], allowed: ["memory:read"] },
    });

    await expect(listMemories({ workspace_id: "w1" })).rejects.toMatchObject({
      name: "UmeApiError",
      code: "VALIDATION_FAILED",
      message: "One or more scopes are not available to connectors.",
    });
  });

  it("still preserves the details payload", async () => {
    api.get.mockRejectedValue({
      code: "VALIDATION_FAILED",
      message: "bad scope",
      details: { rejected: ["memories:read"] },
    });

    await expect(listMemories({ workspace_id: "w1" })).rejects.toMatchObject({
      details: { rejected: ["memories:read"] },
    });
  });

  it("maps a 404 to isNotFound", async () => {
    api.get.mockRejectedValue({
      code: "NOT_FOUND",
      message: "Memory not found.",
      details: null,
    });

    const error = await listMemories({ workspace_id: "w1" }).catch((e) => e as UmeApiError);
    expect(error.isNotFound).toBe(true);
  });

  it("does not call a 400 a not-found", async () => {
    // A validation failure on a real resource must stay distinguishable from
    // "this resource is hidden from you".
    api.get.mockRejectedValue({
      code: "VALIDATION_FAILED",
      message: "bad cursor",
      details: null,
    });

    const error = await listMemories({ workspace_id: "w1" }).catch((e) => e as UmeApiError);
    expect(error.isNotFound).toBe(false);
  });

  it("falls back to a readable message when the body is not an error envelope", async () => {
    api.get.mockRejectedValue(new Error("Network Error"));
    await expect(listMemories({ workspace_id: "w1" })).rejects.toThrow("Network Error");
  });
});

describe("request construction", () => {
  /** The client hands axios one config object; the query string lives in `params`. */
  const paramsOf = (call: unknown[]) =>
    (call[1] as { params: Record<string, unknown> }).params;

  it("sends the workspace filter on the memories list", async () => {
    api.get.mockResolvedValue(ok({ items: [], next_cursor: null, has_more: false }));

    await listMemories({ workspace_id: "w1", limit: 25, status: "ready" });

    const [url, config] = api.get.mock.calls[0];
    expect(url).toBe("/api/ume/v1/memories");
    expect(paramsOf([url, config])).toEqual({
      workspace_id: "w1",
      limit: 25,
      status: "ready",
    });
  });

  it("omits an unset filter instead of sending it empty", async () => {
    api.get.mockResolvedValue(ok({ items: [], next_cursor: null, has_more: false }));

    await listMemories({ workspace_id: "w1", status: undefined, project_id: "" });

    expect(paramsOf(api.get.mock.calls[0])).toEqual({ workspace_id: "w1" });
  });

  it("defaults the graph window to the server's initial-node cap", async () => {
    api.get.mockResolvedValue(ok({ nodes: [], edges: [], next_cursor: null, has_more: false }));

    await loadGraph({ workspace_id: "w1" });

    expect(paramsOf(api.get.mock.calls[0])).toEqual({
      limit: 100,
      workspace_id: "w1",
    });
  });

  it("passes the cursor through when paging", async () => {
    api.get.mockResolvedValue(ok({ items: [], next_cursor: "c2", has_more: true }));

    await listMemories({ workspace_id: "w1", cursor: "c1" });

    expect(paramsOf(api.get.mock.calls[0])).toEqual({
      workspace_id: "w1",
      cursor: "c1",
    });
  });

  it("sends the search limit default in the request body, not the URL", async () => {
    api.post.mockResolvedValue(ok([]));

    await searchMemories({ workspace_id: "w1", query: "hello" });

    const [url, body] = api.post.mock.calls[0];
    expect(url).toBe("/api/ume/v1/memory-search");
    expect(body).toEqual({ limit: 100, workspace_id: "w1", query: "hello" });
  });

  it("lets an explicit limit override the default", async () => {
    api.post.mockResolvedValue(ok([]));

    await searchMemories({ workspace_id: "w1", query: "hello", limit: 5 });

    expect(api.post.mock.calls[0][1].limit).toBe(5);
  });
});

describe("buildContext", () => {
  it("returns the assembly when the budget is respected", async () => {
    api.post.mockResolvedValue(
      ok({ query: "q", token_budget: 100, estimated_tokens: 42, items: [], dropped: [], summarized: false }),
    );

    const result = await buildContext({ workspace_id: "w1", query: "q", token_budget: 100 });

    expect(result.estimated_tokens).toBe(42);
  });

  it("throws when the server reports more tokens than the budget", async () => {
    // The page would otherwise render a budget that was visibly exceeded.
    api.post.mockResolvedValue(
      ok({ query: "q", token_budget: 100, estimated_tokens: 180, items: [], dropped: [], summarized: false }),
    );

    await expect(buildContext({ workspace_id: "w1", query: "q", token_budget: 100 })).rejects.toThrow(
      /180 tokens for a 100 budget/,
    );
  });
});

describe("connectors", () => {
  it("asks the server for a fresh credential on create", async () => {
    api.post.mockResolvedValue(ok({ id: "c1", credential: "umec_x" }));

    await createConnector({ workspace_id: "w1", name: "cli", connector_type: "mcp" });

    expect(api.post.mock.calls[0][0]).toBe("/api/ume/v1/connectors");
  });

  it("revokes without inventing a request body", async () => {
    api.post.mockResolvedValue(ok({ id: "c1", status: "revoked" }));

    await revokeConnector("c1");

    const [url, body] = api.post.mock.calls[0];
    expect(url).toBe("/api/ume/v1/connectors/c1/revoke");
    expect(body).toBeUndefined();
  });
});

describe("loadTimeline", () => {
  /**
   * `/timeline` answers with a bare array — the server has no cursor to give.
   * The client must not fabricate one; asserting the shape here is what stops
   * someone "fixing" it into a page envelope that the server does not send.
   */
  it("reads a plain array rather than a page envelope", async () => {
    api.get.mockResolvedValue(ok([{ kind: "message", id: "m1" }]));

    const entries = await loadTimeline({ workspace_id: "w1" });

    expect(Array.isArray(entries)).toBe(true);
    expect(entries).toHaveLength(1);
  });
});