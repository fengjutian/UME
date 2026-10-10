# Plan template — `UME_MIGRATION_PLAN.md`

Write the plan to `UME_MIGRATION_PLAN.md` at the repo root using the structure below. Keep it
concrete enough to execute from and honest about the gaps. Fill every section from the actual
findings — don't leave placeholders. Drop a section only if it genuinely doesn't apply (and say so).

```markdown
# ume OSS → Platform Migration Plan

## Summary
- One paragraph: what's moving (self-hosted `Memory` → hosted `MemoryClient`) and why.
- Detected language(s) and the installed `ume` version.
- Counts: N files touched, M call sites, plus config/deps/env changes.

## Prerequisites
- `UME_API_KEY` must be set in the environment before execution/verification (https://app.ume.ai).
- Note where it should live (`.env`, secrets manager, CI, deploy config).

## Inventory
A table of every ume touchpoint found, so the developer can see the full footprint:

| File:line | Current (OSS) usage | Category | Maps to |
|-----------|--------------------|----------|---------|
| path:LN   | `Memory.from_config({...})` | client init | `MemoryClient()` |
| path:LN   | `memory.search(q, user_id=...)` | call site | `search(q, filters={...}, top_k=...)` |
| ...       | ...                | config / dep / env / infra | ... |

## Change set
Grouped by file. For each, a short before → after with the actual surrounding code, so the edits are
unambiguous. Example:

### `path/to/file.py`
- Replace import `from ume import Memory` → `from ume import MemoryClient`.
- Replace the `Memory.from_config({...})` block with `MemoryClient()` (drops local vector_store/
  llm/embedder/history config).
- `search(...)`: move `user_id` into `filters={"user_id": ...}`; keep `top_k`.
  ```
  # before
  ...
  # after
  ...
  ```

## Dependencies & config
- `requirements.txt` / `pyproject.toml` / `package.json`: keep `ume`; remove now-unused local-
  infra deps (list them, with the reason each is safe to remove).
- Env: add `UME_API_KEY`; remove env vars only used by the old local embedder/LLM if now unused.
- Infrastructure: local services that existed only for ume (e.g. a Qdrant docker-compose service)
  can be retired — listed for the developer's confirmation, not auto-deleted.

## Concerns & decisions needed
The non-1:1 items from the gotchas that apply here, each phrased as a decision for the developer.
Cover, where relevant: data not migrating, self-hosting/data-residency, local models moving server-
side, graph memory, custom prompts (now project-level `custom_instructions`), network/latency/cost on
hot paths, return-shape changes (`add` is async and returns an `event_id` (`eventId` on TS), `get_all` pagination,
default `top_k` 20 vs 10), metadata filters that need rewriting, and any `reset()` usage. Be specific
about which file/line each concern affects.

## Out of scope
- Existing memory **data** is not migrated (code only). If wanted, it's a separate opt-in task
  (for hosted Qdrant + Python OSS, `scripts/oss-to-platform-migrate.sh`; otherwise export from the
  OSS store and re-add to the hosted client).
- No unrelated refactors, renames, or behavior changes.

## Verification plan
How execution will be confirmed end-to-end:
- Imports / type-checks / byte-compiles cleanly.
- Smoke test against the hosted API with a real `UME_API_KEY`: `add` a fact → `search`/`get_all`
  returns it → `delete_all` clears it. Plus: the app's own entry point still runs.
- Confirm no local OSS storage is created anymore (e.g. `~/.ume/history.db`, a local Qdrant path).
  The client still creates `~/.ume/config.json`, so the bare `.ume/` directory is not the check.

## Rollback
- All changes are in version control; revert with git if needed. Note the branch/commit strategy.
```
