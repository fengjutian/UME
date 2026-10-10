import { SEARCH_WHEN } from "../../agent-plugin-core/typescript/src/prompts.ts";

export const MEMORY_POLICY = `<ume-memory-policy>
You have persistent semantic memory via the ume_memory tool, powered by UME. Relevant memories may be auto-injected under <ume-relevant-memories>.

Use ume_memory with action "search" ${SEARCH_WHEN}.

Be proactive about saving:
- Save important facts, preferences, goals, decisions, lessons learned, identity, relationships, and routines the user shares.

Scope (do not change unless explicitly asked):
- "project" (default): memories for this project — use for all normal queries
- "session": memories from this session only
- "global": all memories across projects — ONLY when the user explicitly asks for cross-project search

Memory persists across sessions and devices via UME's cloud.
</ume-memory-policy>`;
