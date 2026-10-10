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
  CONVERSATION: (conversationId: string) => `${UME_PREFIX}/conversations/${conversationId}`,
  MESSAGES: (conversationId: string) =>
    `${UME_PREFIX}/conversations/${conversationId}/messages`,
  IMPORT_PREVIEW: `${UME_PREFIX}/conversations/imports/preview`,
  IMPORT: `${UME_PREFIX}/conversations/imports`,
  IMPORT_JOB: (jobId: string) => `${UME_PREFIX}/import-jobs/${jobId}`,
} as const;
