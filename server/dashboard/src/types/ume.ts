/** Wire types for the UME V1 business API (`/api/ume/v1`). */

export interface UmeWorkspace {
  id: string;
  name: string;
  description: string | null;
  owner_user_id: string;
  status: "active" | "archived" | "deleting";
  default_memory_policy: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface UmeWorkspaceMember {
  id: string;
  workspace_id: string;
  user_id: string;
  role: "owner" | "admin" | "member" | "viewer";
  created_at: string;
  updated_at: string;
}

export interface UmeProject {
  id: string;
  workspace_id: string;
  name: string;
  description: string | null;
  tags: string[];
  status: "active" | "archived";
  created_at: string;
  updated_at: string;
  last_activity_at: string | null;
}

export interface UmeConversation {
  id: string;
  workspace_id: string;
  project_id: string | null;
  title: string | null;
  source_type: string;
  retention_policy: string;
  status: "active" | "archived";
  started_at: string | null;
  last_message_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface UmeMessage {
  id: string;
  conversation_id: string;
  external_message_id: string | null;
  role: "user" | "assistant" | "system" | "tool";
  content_text: string | null;
  content_ref: Record<string, unknown> | null;
  sensitivity: "normal" | "sensitive" | "restricted";
  message_at: string;
  created_at: string;
}

export interface UmeImportPreview {
  valid: boolean;
  workspace_id: string;
  conversation_id: string | null;
  conversation_action: "created" | "reused" | "create";
  message_count: number;
  duplicate_count: number;
  new_message_count: number;
  first_message_at: string | null;
  last_message_at: string | null;
  problems: Array<Record<string, unknown>>;
}

export interface UmeImportJob {
  id: string;
  workspace_id: string;
  project_id: string | null;
  idempotency_key: string;
  status:
    | "pending"
    | "validating"
    | "importing"
    | "extracting"
    | "completed"
    | "validation_failed"
    | "import_failed"
    | "extraction_partial";
  input_summary: Record<string, unknown>;
  result_summary: {
    conversation_id?: string;
    inserted?: number;
    skipped_duplicates?: number;
    conversation_action?: string;
  };
  error_summary: Record<string, unknown>;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  replayed?: boolean;
}

/* ------------------------------------------------------------------ *
 * Memories (server/ume_app/schemas/memory.py)
 * ------------------------------------------------------------------ */

/**
 * `status` and `engine_state` are deliberately not narrowed to unions: the
 * server is the source of truth for both and a new state there must not
 * become a type error here. Narrow at the call site after you have handled
 * the unknown case.
 *
 * The values the server actually emits today, for reference
 * (`ume_app/domain/enums.py`):
 *   status:       active | archived | deleted
 *   engine_state: pending | ready | failed | deleting | deleted
 */
export interface UmeMemory {
  id: string;
  workspace_id: string;
  engine_memory_id: string;
  memory_type: string;
  status: string;
  current_text: string;
  tags: string[];
  engine_state: string;
  engine_error: string | null;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
}

export interface UmeMemorySource {
  id: string;
  conversation_id: string | null;
  message_id: string | null;
  source_type: string;
  extraction_method: string;
  evidence_excerpt: string | null;
  confidence: number | null;
  created_at: string;
}

export interface UmeMemoryVersion {
  id: string;
  version_no: number;
  text: string;
  extra_metadata: Record<string, unknown>;
  change_type: string;
  change_reason: string | null;
  actor_type: string;
  created_at: string;
}

export interface UmeMemorySearchHit {
  memory: UmeMemory;
  score: number | null;
  engine_id: string;
}

/* ------------------------------------------------------------------ *
 * Graph, timeline, context (server/ume_app/api/routes/graph.py)
 * ------------------------------------------------------------------ */

export interface UmeGraphNode {
  id: string;
  text: string;
  memory_type: string;
  status: string;
  engine_id: string;
  created_at: string;
}

export interface UmeGraphEdge {
  id: string;
  source_memory_id: string;
  target_memory_id: string;
  relation_type: string;
  status: string;
  created_at: string;
}

/** `/graph` and `/graph/nodes/{id}/neighbors` share one payload shape. */
export interface UmeGraphWindow {
  nodes: UmeGraphNode[];
  edges: UmeGraphEdge[];
  next_cursor: string | null;
  has_more: boolean;
}

export interface UmeTimelineEntry {
  kind: "message" | "memory";
  id: string;
  conversation_id: string | null;
  at: string;
  title: string;
  preview: string | null;
  /** Message entries only. */
  sensitivity?: string;
  /** Memory entries only. */
  status?: string;
}

export interface UmeContextItem {
  memory_id: string;
  text: string;
  memory_type: string;
  score: number;
  tokens: number;
  semantic_score: number;
  freshness_days: number;
  project_match: boolean;
  confirmed: boolean;
  engine_id: string;
}

export interface UmeContextDropped {
  memory_id: string;
  /** Truncated preview only — the server never returns the full body here. */
  text: string;
  score: number;
  tokens: number;
  reason: string;
}

export interface UmeContext {
  query: string;
  token_budget: number;
  estimated_tokens: number;
  items: UmeContextItem[];
  dropped: UmeContextDropped[];
  summarized: boolean;
}

/* ------------------------------------------------------------------ *
 * Connectors (server/ume_app/models/connector.py `as_dict`)
 * ------------------------------------------------------------------ */

/**
 * `credential` exists on the create response **only**. Every other route
 * returns the same row without it — see `UmeConnectorCreated`.
 */
export interface UmeConnector {
  id: string;
  workspace_id: string;
  project_id: string | null;
  name: string;
  connector_type: string;
  client_instance_id: string | null;
  credential_prefix: string;
  scopes: string[];
  capabilities: Record<string, unknown>;
  status: string;
  last_active_at: string | null;
  revoked_at: string | null;
  created_at: string;
}

/** The one response that carries the plaintext credential. */
export interface UmeConnectorCreated extends UmeConnector {
  credential: string;
}
