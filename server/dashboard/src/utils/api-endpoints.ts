export const AUTH_ENDPOINTS = {
  SETUP_STATUS: "/auth/setup-status",
  REGISTER: "/auth/register",
  LOGIN: "/auth/login",
  REFRESH: "/auth/refresh",
  ME: "/auth/me",
  CHANGE_PASSWORD: "/auth/change-password",
  ONBOARDING_COMPLETE: "/auth/onboarding-complete",
} as const;

export const MEMORY_ENDPOINTS = {
  BASE: "/memories",
  BY_ID: (memoryId: string) => `/memories/${memoryId}`,
  HISTORY: (memoryId: string) => `/memories/${memoryId}/history`,
  CONFIGURE: "/configure",
  CONFIGURE_PROVIDERS: "/configure/providers",
  RESET: "/reset",
  GENERATE_INSTRUCTIONS: "/generate-instructions",
} as const;

export const API_KEY_ENDPOINTS = {
  BASE: "/api-keys",
  BY_ID: (keyId: string) => `/api-keys/${keyId}`,
} as const;

export const REQUEST_ENDPOINTS = {
  BASE: "/requests",
} as const;

export const ENTITY_ENDPOINTS = {
  BASE: "/entities",
  BY_ID: (type: string, id: string) =>
    `/entities/${type}/${encodeURIComponent(id)}`,
} as const;

/**
 * UME V1 business API.
 *
 * Every one of these responses is wrapped in `{ data, request_id }` or
 * `{ error: { code, message, details }, request_id }` — use `unwrap` /
 * `umeFetch` from `@/utils/ume-api` rather than reading `response.data`
 * directly, or a failed request will silently look like an empty payload.
 *
 * The collection routes carry `workspace_id` as a query parameter: the server
 * defines no workspace path segment for them, and membership is still checked
 * server-side before any query runs.
 */
export const UME_PREFIX = "/api/ume/v1";

export const UME_ENDPOINTS = {
  WORKSPACES: `${UME_PREFIX}/workspaces`,
  WORKSPACE: (workspaceId: string) => `${UME_PREFIX}/workspaces/${workspaceId}`,
  WORKSPACE_MEMBERS: (workspaceId: string) =>
    `${UME_PREFIX}/workspaces/${workspaceId}/members`,
  WORKSPACE_MEMBER: (workspaceId: string, userId: string) =>
    `${UME_PREFIX}/workspaces/${workspaceId}/members/${userId}`,
  WORKSPACE_PROJECTS: (workspaceId: string) =>
    `${UME_PREFIX}/workspaces/${workspaceId}/projects`,
  PROJECT: (projectId: string) => `${UME_PREFIX}/projects/${projectId}`,

  CONVERSATIONS: `${UME_PREFIX}/conversations`,
  CONVERSATION: (conversationId: string) =>
    `${UME_PREFIX}/conversations/${conversationId}`,
  MESSAGES: (conversationId: string) =>
    `${UME_PREFIX}/conversations/${conversationId}/messages`,
  IMPORT_PREVIEW: `${UME_PREFIX}/conversations/imports/preview`,
  IMPORT: `${UME_PREFIX}/conversations/imports`,
  IMPORT_JOB: (jobId: string) => `${UME_PREFIX}/import-jobs/${jobId}`,

  MEMORIES: `${UME_PREFIX}/memories`,
  MEMORY: (memoryId: string) => `${UME_PREFIX}/memories/${memoryId}`,
  MEMORY_SOURCES: (memoryId: string) =>
    `${UME_PREFIX}/memories/${memoryId}/sources`,
  MEMORY_VERSIONS: (memoryId: string) =>
    `${UME_PREFIX}/memories/${memoryId}/versions`,
  MEMORY_ARCHIVE: (memoryId: string) =>
    `${UME_PREFIX}/memories/${memoryId}/archive`,
  MEMORY_RESTORE: (memoryId: string) =>
    `${UME_PREFIX}/memories/${memoryId}/restore`,
  MEMORY_FORGET: (memoryId: string) =>
    `${UME_PREFIX}/memories/${memoryId}/forget`,
  MEMORY_RETRY: (memoryId: string) =>
    `${UME_PREFIX}/memories/${memoryId}/retry`,
  MEMORY_SEARCH: `${UME_PREFIX}/memory-search`,

  GRAPH: `${UME_PREFIX}/graph`,
  GRAPH_NEIGHBORS: (nodeId: string) =>
    `${UME_PREFIX}/graph/nodes/${nodeId}/neighbors`,
  GRAPH_EDGE: (edgeId: string) => `${UME_PREFIX}/graph/edges/${edgeId}`,
  GRAPH_EDGES: `${UME_PREFIX}/graph/edges`,
  TIMELINE: `${UME_PREFIX}/timeline`,
  CONTEXT: `${UME_PREFIX}/context`,

  CONNECTORS: `${UME_PREFIX}/connectors`,
  CONNECTOR: (connectorId: string) => `${UME_PREFIX}/connectors/${connectorId}`,
  CONNECTOR_REVOKE: (connectorId: string) =>
    `${UME_PREFIX}/connectors/${connectorId}/revoke`,
} as const;

/**
 * Server-side caps, mirrored so a UI can disable an input instead of letting a
 * request fail validation. The server remains the authority — these exist to
 * avoid asking users for something that will be rejected.
 *
 * `memories` is `Query(ge=1, le=200)`, `graph` caps at MAX_INITIAL_NODES and
 * neighbors at MAX_NEIGHBORS_PER_NODE, `versions` at 200, `timeline` at 200,
 * `context.token_budget` at 64000.
 */
export const UME_LIMITS = {
  pageSize: 200,
  graphInitialNodes: 100,
  graphNeighborsPerNode: 50,
  contextTokenBudget: 64000,
  contextLimit: 100,
  searchLimit: 100,
} as const;

/**
 * Drop `undefined` / `null` / `""` entries so an unset filter never reaches the
 * server as `?status=` — which the server would treat as a real, empty filter.
 */
export const query = (
  params: Record<string, string | number | boolean | null | undefined>,
): Record<string, string | number | boolean> => {
  const out: Record<string, string | number | boolean> = {};
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    out[key] = value;
  }
  return out;
};
