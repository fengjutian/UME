---
name: ume-search
description: Searches memories and displays compact one-liner results, or looks up a specific memory by ID. Use for quick memory lookups, checking if a decision was recorded, resolving [ume:id] citations, or browsing memories without full category detail.
---

# UME Search

Quick search with compact output. Lighter than `/ume-tour`.

## Execution

### Step 1: Parse query

The user provides a search query: `/ume-search auth middleware`

If no query provided, ask: "What should I search for?"

**Memory ID detection:** If the query matches any of these patterns, treat it as a
direct memory ID lookup instead of a search:
- Bare hex: `^[a-f0-9]{8}$` (short ID) or `^[a-f0-9]{8}-[a-f0-9-]+$` (full UUID)
- Citation ref: `[ume:<hex>]` — extract the hex portion

When an ID is detected:
1. Call `get_memory(<id>)` directly (if short ID, try as prefix of full UUID)
2. If found, skip to Step 3 and display the single result
3. If not found, fall through to search using the ID as query text

### Step 2: Search

Call `search_memories` once with the user's question: `query=<user's query>`, `filters={"AND": [{"user_id": "<id>"}, {"app_id": "<pid>"}]}`, `top_k=10`.

### Step 3: Display

Show compact results:

```
## ume search: "<query>" (<N> results)

1. [decision] Auth module uses JWT with RS256 keys (2025-05-15) [ume:a3f8b2c1]
2. [anti_pattern] Don't use symmetric HS256 — leaked in env (2025-05-10) [ume:7e2d9f4a]
3. [convention] All middleware in src/middleware/ (2025-05-08) [ume:c4d5e6f7]
```

Format: `<number>. [<type>] <content, 80 chars> (<date>) [ume:<short_id>]`

If no results:
```
No memories matching "<query>" for project <project_id>.
```

## Output formatting

IMPORTANT: Do NOT use markdown in your output. OpenCode TUI renders text verbatim — markdown like **bold**, ## headers, and | table | syntax appears as raw characters. Use plain text with indentation for structure. Use dashes for lists. Use spaces to align columns instead of markdown tables.
