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
