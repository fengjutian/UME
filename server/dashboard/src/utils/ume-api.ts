import { AxiosError, AxiosRequestConfig } from "axios";
import { api } from "@/utils/api";
import {
  UME_ENDPOINTS,
  UME_LIMITS,
  query as buildQuery,
} from "@/utils/api-endpoints";
import type {
  UmeConnector,
  UmeConnectorCreated,
  UmeContext,
  UmeGraphEdge,
  UmeGraphWindow,
  UmeMemory,
  UmeMemorySearchHit,
  UmeMemorySource,
  UmeMemoryVersion,
  UmeTimelineEntry,
} from "@/types/ume";

/** Envelope every `/api/ume/v1` response is wrapped in. */
export interface UmeEnvelope<T> {
  data: T;
  request_id: string;
}

export interface UmeErrorEnvelope {
  error: {
    code: string;
    message: string;
    details: unknown;
  };
  request_id: string;
}

export interface UmePage<T> {
  items: T[];
  next_cursor: string | null;
  has_more: boolean;
}

/** A UME failure, carrying the server's machine code. */
export class UmeApiError extends Error {
  readonly code: string;
  readonly details: unknown;
  readonly status: number;
  readonly requestId: string | undefined;

  constructor(
    code: string,
    message: string,
    status: number,
    details: unknown,
    requestId?: string,
  ) {
    super(message);
    this.name = "UmeApiError";
    this.code = code;
    this.details = details;
    this.status = status;
    this.requestId = requestId;
  }

  /**
   * The server answers a cross-workspace or unknown id with the *same* 404 it
   * uses for a resource that does not exist, so a page cannot tell "forbidden"
   * from "missing" — and must not pretend to. Everything non-404 is a genuine
   * failure the user can act on.
   */
  get isNotFound(): boolean {
    return this.status === 404 || this.code === "NOT_FOUND";
  }

  get isUnauthorized(): boolean {
    return this.status === 401 || this.code === "UNAUTHENTICATED";
  }
}

/**
 * Unwrap a success envelope.
 *
 * Throws `UmeApiError` when the body is an error envelope rather than returning
 * `undefined` — a failed request that resolves to `undefined` is how a page
 * ends up rendering a convincing "no data yet" instead of showing the error.
 */
export function unwrap<T>(body: unknown): T {
  if (body && typeof body === "object" && "error" in body) {
    const envelope = body as UmeErrorEnvelope;
    throw new UmeApiError(
      envelope.error.code,
      envelope.error.message,
      0,
      envelope.error.details,
      envelope.request_id,
    );
  }
  return (body as UmeEnvelope<T>).data;
}

interface WireError {
  code?: unknown;
  message?: unknown;
  details?: unknown;
}

const isWireError = (value: unknown): value is WireError =>
  !!value && typeof value === "object" && "code" in value && "message" in value;

/**
 * Normalise anything axios rejects with into a `UmeApiError`.
 *
 * The shared response interceptor in `utils/api.ts` rejects with the *inner*
 * `{ code, message, details }` object whenever the body carries an `error` key,
 * which is every `/api/ume/v1` failure. That value is a plain object: it is not
 * an `AxiosError`, so `response.data` is unreachable and the status code is
 * gone by the time it lands here. Matching on its shape is what keeps the
 * server's message instead of collapsing every failure to "Request failed".
 *
 * Known limitation: the interceptor unwraps one level and drops the outer
 * envelope, so `request_id` cannot be recovered client-side. When a request_id
 * is needed for support, read it from the server log for that timestamp.
 */
function toUmeError(error: unknown): UmeApiError {
  if (error instanceof UmeApiError) return error;

  if (isWireError(error)) {
    return new UmeApiError(
      typeof error.code === "string" ? error.code : "REQUEST_FAILED",
      typeof error.message === "string" ? error.message : "Request failed",
      0,
      error.details ?? null,
    );
  }

  const axiosError = error as AxiosError<unknown>;
  const body = axiosError?.response?.data;
  if (body && typeof body === "object" && "error" in body) {
    const envelope = body as UmeErrorEnvelope;
    return new UmeApiError(
      envelope.error.code,
      envelope.error.message,
      axiosError.response?.status ?? 0,
      envelope.error.details,
      envelope.request_id,
    );
  }

  if (axiosError?.response?.status === 401) {
    return new UmeApiError(
      "UNAUTHENTICATED",
      "Your session has expired.",
      401,
      null,
    );
  }

  return new UmeApiError(
    "REQUEST_FAILED",
    error instanceof Error ? error.message : "Request failed",
    axiosError?.response?.status ?? 0,
    null,
  );
}

export interface UmeRequestOptions {
  /** Abort in-flight requests when a component unmounts or the filter changes. */
  signal?: AbortSignal;
  headers?: Record<string, string>;
}

const requestConfig = (
  params?: Record<string, string | number | boolean>,
  options: UmeRequestOptions = {},
): AxiosRequestConfig => ({
  params,
  signal: options.signal,
  headers: options.headers,
});

/**
 * `params` stays the second positional argument because pages already call
 * `umeGet(url, { limit })`; moving it into an options bag would break every one
 * of those call sites for no gain.
 */
export const umeGet = async <T>(
  url: string,
  params?: Record<string, string | number | boolean>,
  options: UmeRequestOptions = {},
) => {
  try {
    return unwrap<T>((await api.get(url, requestConfig(params, options))).data);
  } catch (error) {
    throw toUmeError(error);
  }
};

export const umePost = async <T>(
  url: string,
  body?: unknown,
  params?: Record<string, string | number | boolean>,
  options: UmeRequestOptions = {},
) => {
  try {
    return unwrap<T>(
      (await api.post(url, body, requestConfig(params, options))).data,
    );
  } catch (error) {
    throw toUmeError(error);
  }
};

export const umePatch = async <T>(
  url: string,
  body?: unknown,
  params?: Record<string, string | number | boolean>,
  options: UmeRequestOptions = {},
) => {
  try {
    return unwrap<T>(
      (await api.patch(url, body, requestConfig(params, options))).data,
    );
  } catch (error) {
    throw toUmeError(error);
  }
};

export const umeDelete = async <T>(
  url: string,
  params?: Record<string, string | number | boolean>,
  options: UmeRequestOptions = {},
) => {
  try {
    return unwrap<T>(
      (await api.delete(url, requestConfig(params, options))).data,
    );
  } catch (error) {
    throw toUmeError(error);
  }
};

export const umePut = async <T>(
  url: string,
  body?: unknown,
  params?: Record<string, string | number | boolean>,
  options: UmeRequestOptions = {},
) => {
  try {
    return unwrap<T>(
      (await api.put(url, body, requestConfig(params, options))).data,
    );
  } catch (error) {
    throw toUmeError(error);
  }
};

/**
 * Empty a `UmePage` into something a table can render.
 *
 * `/timeline` is the exception: it returns a plain array with no cursor, so it
 * gets `umeList` rather than being forced through the page shape. Do not invent
 * a cursor for it — the server has none to give.
 */
export const umePage = async <T>(
  url: string,
  params?: Record<string, string | number | boolean>,
  options: UmeRequestOptions = {},
): Promise<UmePage<T>> => umeGet<UmePage<T>>(url, params, options);

export const umeList = async <T>(
  url: string,
  params?: Record<string, string | number | boolean>,
  options: UmeRequestOptions = {},
): Promise<T[]> => umeGet<T[]>(url, params, options);

/* ------------------------------------------------------------------ *
 * Typed surface. One function per server route so no page has to build
 * a URL or remember which fields a route needs.
 * ------------------------------------------------------------------ */

/* Memories */

export interface MemoryListFilters {
  workspace_id: string;
  limit?: number;
  cursor?: string;
  status?: string;
  memory_type?: string;
  project_id?: string;
  include_deleted?: boolean;
}

export const listMemories = (
  filters: MemoryListFilters,
  options: UmeRequestOptions = {},
) =>
  umePage<UmeMemory>(
    UME_ENDPOINTS.MEMORIES,
    buildQuery({ ...filters }),
    options,
  );

export const getMemory = (memoryId: string, options: UmeRequestOptions = {}) =>
  umeGet<UmeMemory>(UME_ENDPOINTS.MEMORY(memoryId), undefined, options);

export const listMemorySources = (
  memoryId: string,
  options: UmeRequestOptions = {},
) =>
  umeList<UmeMemorySource>(
    UME_ENDPOINTS.MEMORY_SOURCES(memoryId),
    undefined,
    options,
  );

export const listMemoryVersions = (
  memoryId: string,
  limit = 50,
  options: UmeRequestOptions = {},
) =>
  umeList<UmeMemoryVersion>(
    UME_ENDPOINTS.MEMORY_VERSIONS(memoryId),
    buildQuery({ limit }),
    options,
  );

export interface MemoryCreateInput {
  workspace_id: string;
  messages: Array<{ role?: string; content: string }>;
  memory_type?: string;
  tags?: string[];
  project_ids?: string[];
  infer?: boolean;
  sources?: Array<Record<string, unknown>>;
}

export const createMemory = (
  input: MemoryCreateInput,
  options: UmeRequestOptions = {},
) => umePost<UmeMemory>(UME_ENDPOINTS.MEMORIES, input, undefined, options);

export const updateMemory = (
  memoryId: string,
  input: { text: string; change_reason?: string; tags?: string[] },
  options: UmeRequestOptions = {},
) =>
  umePatch<UmeMemory>(
    UME_ENDPOINTS.MEMORY(memoryId),
    input,
    undefined,
    options,
  );

export const archiveMemory = (
  memoryId: string,
  reason?: string,
  options: UmeRequestOptions = {},
) =>
  umePost<UmeMemory>(
    UME_ENDPOINTS.MEMORY_ARCHIVE(memoryId),
    { reason },
    undefined,
    options,
  );

export const restoreMemoryVersion = (
  memoryId: string,
  versionNo: number,
  options: UmeRequestOptions = {},
) =>
  umePost<UmeMemory>(
    UME_ENDPOINTS.MEMORY_RESTORE(memoryId),
    { version_no: versionNo },
    undefined,
    options,
  );

export const forgetMemory = (
  memoryId: string,
  reason?: string,
  options: UmeRequestOptions = {},
) =>
  umePost<UmeMemory>(
    UME_ENDPOINTS.MEMORY_FORGET(memoryId),
    { reason },
    undefined,
    options,
  );

export const retryMemoryWrite = (
  memoryId: string,
  messages: Array<{ role?: string; content: string }>,
  options: UmeRequestOptions = {},
) =>
  umePost<UmeMemory>(
    UME_ENDPOINTS.MEMORY_RETRY(memoryId),
    { messages },
    undefined,
    options,
  );

export interface MemorySearchInput {
  workspace_id: string;
  query: string;
  limit?: number;
  project_id?: string;
}

export const searchMemories = (
  input: MemorySearchInput,
  options: UmeRequestOptions = {},
) =>
  umePost<UmeMemorySearchHit[]>(
    UME_ENDPOINTS.MEMORY_SEARCH,
    { limit: UME_LIMITS.searchLimit, ...input },
    undefined,
    options,
  );

/* Graph, timeline, context */

export const loadGraph = (
  params: { workspace_id: string; project_id?: string; limit?: number },
  options: UmeRequestOptions = {},
) =>
  umeGet<UmeGraphWindow>(
    UME_ENDPOINTS.GRAPH,
    buildQuery({ limit: UME_LIMITS.graphInitialNodes, ...params }),
    options,
  );

export const loadNeighbors = (
  nodeId: string,
  limit: number = UME_LIMITS.graphNeighborsPerNode,
  options: UmeRequestOptions = {},
) =>
  umeGet<UmeGraphWindow>(
    UME_ENDPOINTS.GRAPH_NEIGHBORS(nodeId),
    buildQuery({ limit }),
    options,
  );

export interface EdgeCreateInput {
  workspace_id: string;
  source_memory_id: string;
  target_memory_id: string;
  relation_type: string;
  evidence_ref?: Record<string, unknown>;
}

export const createEdge = (
  input: EdgeCreateInput,
  options: UmeRequestOptions = {},
) =>
  umePost<UmeGraphEdge>(UME_ENDPOINTS.GRAPH_EDGES, input, undefined, options);

export const updateEdge = (
  edgeId: string,
  input: { status: string; relation_type?: string },
  options: UmeRequestOptions = {},
) =>
  umePatch<UmeGraphEdge>(
    UME_ENDPOINTS.GRAPH_EDGE(edgeId),
    input,
    undefined,
    options,
  );

export const deleteEdge = (edgeId: string, options: UmeRequestOptions = {}) =>
  umeDelete<{ id: string; deleted: boolean }>(
    UME_ENDPOINTS.GRAPH_EDGE(edgeId),
    undefined,
    options,
  );

export interface TimelineFilters {
  workspace_id: string;
  limit?: number;
  since?: string;
  until?: string;
  project_id?: string;
}

/** Returns a plain array — `/timeline` has no cursor to page with. */
export const loadTimeline = (
  filters: TimelineFilters,
  options: UmeRequestOptions = {},
) =>
  umeList<UmeTimelineEntry>(
    UME_ENDPOINTS.TIMELINE,
    buildQuery({ limit: 50, ...filters }),
    options,
  );

export interface ContextInput {
  workspace_id: string;
  query: string;
  limit?: number;
  token_budget?: number;
  project_id?: string;
}

/**
 * The server always returns `estimated_tokens <= token_budget`. Assert that
 * client-side too: a budget shown as exceeded is worse than no budget at all.
 */
export const buildContext = async (
  input: ContextInput,
  options: UmeRequestOptions = {},
): Promise<UmeContext> => {
  const result = await umePost<UmeContext>(
    UME_ENDPOINTS.CONTEXT,
    input,
    undefined,
    options,
  );
  if (result.estimated_tokens > result.token_budget) {
    throw new UmeApiError(
      "CONTEXT_BUDGET_EXCEEDED",
      `Server assembled ${result.estimated_tokens} tokens for a ${result.token_budget} budget.`,
      0,
      {
        estimated_tokens: result.estimated_tokens,
        token_budget: result.token_budget,
      },
    );
  }
  return result;
};

/* Connectors */

export interface ConnectorListFilters {
  workspace_id: string;
  include_revoked?: boolean;
  limit?: number;
  cursor?: string;
}

export const listConnectors = (
  filters: ConnectorListFilters,
  options: UmeRequestOptions = {},
) =>
  umePage<UmeConnector>(
    UME_ENDPOINTS.CONNECTORS,
    buildQuery({ ...filters }),
    options,
  );

export interface ConnectorCreateInput {
  workspace_id: string;
  name: string;
  connector_type: string;
  scopes?: string[];
  project_id?: string;
  client_instance_id?: string;
  capabilities?: Record<string, unknown>;
}

/**
 * The only call that returns a plaintext credential. Do not store it in
 * component state that outlives the dialog that shows it, and do not log it.
 */
export const createConnector = (
  input: ConnectorCreateInput,
  options: UmeRequestOptions = {},
) =>
  umePost<UmeConnectorCreated>(
    UME_ENDPOINTS.CONNECTORS,
    input,
    undefined,
    options,
  );

export const getConnector = (
  connectorId: string,
  options: UmeRequestOptions = {},
) =>
  umeGet<UmeConnector>(
    UME_ENDPOINTS.CONNECTOR(connectorId),
    undefined,
    options,
  );

export const updateConnector = (
  connectorId: string,
  input: {
    name?: string;
    scopes?: string[];
    capabilities?: Record<string, unknown>;
  },
  options: UmeRequestOptions = {},
) =>
  umePatch<UmeConnector>(
    UME_ENDPOINTS.CONNECTOR(connectorId),
    input,
    undefined,
    options,
  );

export const revokeConnector = (
  connectorId: string,
  options: UmeRequestOptions = {},
) =>
  umePost<UmeConnector>(
    UME_ENDPOINTS.CONNECTOR_REVOKE(connectorId),
    undefined,
    undefined,
    options,
  );

/**
 * Server-side scope allowlist, from the 400 the server returns for an unknown
 * scope. Shown so the picker never offers a scope the server will reject.
 */
export const CONNECTOR_SCOPES = [
  "context:read",
  "conversation:read",
  "conversation:write",
  "graph:read",
  "memory:read",
  "memory:write",
  "project:read",
  "workspace:read",
] as const;

export type UmeConnectorScope = (typeof CONNECTOR_SCOPES)[number];

export const errorLabel = (error: unknown): string => {
  if (error instanceof UmeApiError) return error.message;
  return error instanceof Error ? error.message : "Request failed";
};
