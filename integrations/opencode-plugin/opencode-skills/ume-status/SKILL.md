---
name: ume-status
description: Diagnoses ume connectivity, API key validity, and memory read/write functionality. Use when memory operations fail, searches return empty, add_memory errors occur, or to verify the plugin is working correctly.
---

# UME Status

Run a diagnostic check on the ume plugin. Useful for troubleshooting.

## Execution

Run ALL checks, then display a single summary. Do not stop on the first failure.

### Check 1: API key

```bash
_KEY="${UME_API_KEY:-}"
[ -n "$_KEY" ] && echo "${_KEY:0:6}..." || echo "NOT_SET"
```

- If `NOT_SET`: FAIL — "No API key configured"
- If set: PASS — the command already prints only the first 6 chars

### Check 2: Identity resolution

Resolve identity from the `UME_*` environment variables set by the plugin's `shell.env` hook. These are the exact values the plugin uses to scope memories, so report them directly. Do NOT re-run `git` here: the plugin already resolved branch and project from git at session start, and re-shelling git can disagree with it — e.g. it prints an empty branch that renders as `(not a git repo)` while the Session check below shows `branch=main`. One source of truth keeps the two lines consistent.

```bash
echo "user_id=${UME_USER_ID:-${USER:-default}}"
echo "project_id=${UME_APP_ID:-}"
echo "branch=${UME_BRANCH:-main}"
_S="$HOME/.ume/settings.json"
_SCOPE="$(grep -o '"default_scope"[[:space:]]*:[[:space:]]*"[a-z]*"' "$_S" 2>/dev/null | grep -o '[a-z]*"$' | tr -d '"')"
echo "default_scope=${_SCOPE:-project}"
```

- `user_id`: from `UME_USER_ID`, falling back to `$USER`
- `project_id`: from `UME_APP_ID`
- `branch`: from `UME_BRANCH` (the plugin's resolved value; falls back to `main` outside a git repo)
- `default_scope`: from `~/.ume/settings.json` (`default_scope`), falling back to `project`. This is the scope memory tools use when none is given; change it with `/ume-scope`.

PASS if `user_id` and `project_id` are non-empty. WARN if `project_id` is empty — the `shell.env` hook may not have fired (restart OpenCode). Report the branch verbatim from `UME_BRANCH`; never invent a string like `(not a git repo)`.

### Check 3: Memory tool connectivity

Call `search_memories` with:
- `query="health check"`
- `filters={"AND": [{"user_id": "<active_user_id>"}, {"app_id": "<active_project_id>"}]}`
- `top_k=1`

- If returns successfully (even empty): PASS
- If errors: FAIL — show the error message

### Check 4: Memory write capability

Call `add_memory` with:
- `text="Health check probe — safe to delete."`
- `user_id=<active_user_id>`
- `app_id=<active_project_id>`
- `metadata={"type": "health_check", "probe": true}`
- `infer=False`

The response returns `event_id` (v3 writes are async). Call `get_event_status(event_id=<event_id>)` to check processing.

- If status is `SUCCEEDED`: PASS — extract the memory ID from the event result, then call `delete_memory` with that ID to clean up.
- If status is `PENDING` after 5 seconds: PASS (write accepted, processing delayed)
- If errors: FAIL — show the error.

### Check 5: Session context

Check that the plugin's `shell.env` hook has injected session context into the environment:

```bash
echo "session_id=${UME_SESSION_ID:-}"
echo "app_id=${UME_APP_ID:-}"
echo "branch=${UME_BRANCH:-}"
```

- If all three are non-empty: PASS — "Session active"
- If any are missing: WARN — "Plugin env vars not set; shell.env hook may not have fired"

### Display

```
## ume status

PASS  API Key         m0-dVe...
PASS  Identity        user=kartik, project=ume, branch=main
PASS  Default scope   project
PASS  Memory Tools    142ms
PASS  Write/Read      write + delete OK
PASS  Session         session_id=abc123, app_id=ume, branch=main

All checks passed.
```

If any check fails, add a `## Troubleshooting` section with specific fix steps for each failure.

## Extended mode: Memory Quality Analysis

When invoked with `--deep` (e.g., `/ume-status --deep`), run the standard 5 checks above **plus** a memory quality scan.

### Quality Check 1: Duplicates

Call `get_memories` with `filters={"AND": [{"user_id": "<active_user_id>"}, {"app_id": "<active_project_id>"}]}`, `page_size=200`. Compare all pairs within the same `metadata.type` group for high textual overlap (shared nouns/keywords > 60%). Report:

```
Potential duplicates: <N> pairs
  [ume:<id1>] ≈ [ume:<id2>] — both about "<shared topic>"
```

### Quality Check 2: Stale memories

Flag memories where:
- `metadata.type` is `session_state` or `compact_summary` AND older than 90 days
- `metadata.confidence` < 0.3 AND older than 30 days

```
Stale candidates: <N>
  [ume:<id>] — session_state, 142d old
```

### Quality Check 2b: Low-confidence memories

Flag memories where `metadata.confidence` < 0.5 (regardless of age). Report separately from stale:

```
Low-confidence memories: <N>
  [ume:<id>] — confidence=0.3, "<content preview>"
```

### Quality Check 3: Contradictions

Within each `metadata.type` group, flag pairs that assert opposing facts about the same topic. Use semantic judgment — look for negation patterns, conflicting tool/framework choices, or reversed decisions.

```
Possible contradictions: <N>
  [ume:<idA>] vs [ume:<idB>] — conflicting on "<topic>"
```

### Quality Check 4: Orphan memories

Memories with no `metadata.type` set, or with `metadata.type` not in the 17 known coding categories. These were likely written without proper tagging.

```
Untagged/orphan memories: <N>
```

### Quality summary

```
## Memory Quality

Duplicates: <N> · Stale: <N> · Contradictions: <N> · Orphans: <N>
```

If all counts are 0: `Memory quality: clean.`
If any non-zero, list the affected memory IDs so the user can review them with the normal search, update, and delete tools.

## Output formatting

IMPORTANT: Do NOT use markdown in your output. OpenCode TUI renders text verbatim — markdown like **bold**, ## headers, and | table | syntax appears as raw characters. Use plain text with indentation for structure. Use dashes for lists. Use spaces to align columns instead of markdown tables.
