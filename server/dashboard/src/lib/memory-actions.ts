import type { UmeMemory } from "@/types/ume";

/**
 * Which actions a memory row will accept, derived from its state.
 *
 * This mirrors — it does not replace — the server's guards, read off
 * `ume_app/services/memories.py`:
 *
 *   update   status in {active, archived}   (READABLE_MEMORY_STATUSES)
 *   archive  status == active
 *   restore  status == archived, and the target version differs from current
 *   forget   status != deleted
 *   retry    engine_state == failed
 *
 * The server rejects anything else with a 409, and remains the authority —
 * hiding a button is a courtesy, not a permission check. Keeping the mapping in
 * one place is the point: the page renders `allowedActions(memory)` instead of
 * re-deriving the rules inline, so the rules cannot drift per screen.
 *
 * `restore` is expressed as `restoreVersion(versionNo)` rather than a bare
 * flag because the server writes the old text forward as a *new* version; the
 * page has to name which one.
 */
export type MemoryAction =
  | "edit"
  | "archive"
  | "restoreVersion"
  | "forget"
  | "retryEngine";

export interface AllowedActions {
  edit: boolean;
  archive: boolean;
  restoreVersion: boolean;
  forget: boolean;
  retryEngine: boolean;
}

const ALL_DENIED: AllowedActions = {
  edit: false,
  archive: false,
  restoreVersion: false,
  forget: false,
  retryEngine: false,
};

export function allowedActions(
  memory: Pick<UmeMemory, "status" | "engine_state">,
): AllowedActions {
  const status = memory.status;
  const readable = status === "active" || status === "archived";

  return {
    edit: readable,
    archive: status === "active",
    restoreVersion: status === "archived",
    // A deleted row is the one state the server refuses outright.
    forget: status !== "deleted",
    // Only a failed engine write is retryable — retrying a `ready` record
    // would create a second engine memory for the same text.
    retryEngine: memory.engine_state === "failed",
  };
}

/** The states worth drawing attention to, with the copy to show for each. */
export function memoryStatusNote(
  memory: Pick<UmeMemory, "status" | "engine_state" | "engine_error">,
) {
  if (memory.status === "deleted") {
    return {
      tone: "destructive" as const,
      label: "Deleted",
      detail: "Tombstoned after a confirmed forget.",
    };
  }
  if (memory.engine_state === "failed") {
    return {
      tone: "destructive" as const,
      label: "Engine write failed",
      detail: memory.engine_error ?? "The engine never accepted this memory.",
    };
  }
  if (memory.engine_state === "pending") {
    return {
      tone: "muted" as const,
      label: "Engine write pending",
      detail: "Not yet acknowledged by the engine.",
    };
  }
  if (memory.engine_state === "deleting") {
    return {
      tone: "muted" as const,
      label: "Deleting",
      detail: "Engine deletion is resumable.",
    };
  }
  if (memory.status === "archived") {
    return {
      tone: "muted" as const,
      label: "Archived",
      detail: "Hidden from retrieval; still retained.",
    };
  }
  return null;
}

export { ALL_DENIED as NO_ACTIONS };
