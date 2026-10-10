---
name: search
description: Searches memories and displays compact one-liner results, or looks up a specific memory by ID. Use for quick memory lookups, checking if something was recorded, resolving [ume:id] citations, or browsing memories without full category detail.
---

# Search / Peek

Quick semantic search with compact output. Lighter than `/ume-tour`.

## Execution

### Step 1: Parse query

The user provides a search query: `/ume-search favorite restaurants`

If no query provided, ask: "What should I search for?"

**Memory ID detection:** If the query matches a UUID pattern (`^[a-f0-9-]{20,}$`), treat it as a direct memory lookup instead of a search.

### Step 2: Search

Use `ume_memory` tool with `action="search"`, `query=<user's query>`.

### Step 3: Display

Show compact results:

```
## ume search: "<query>" (<N> results)

1. [preferences] Prefers window seats on flights (2026-05-15) [ume:a3f8b2c1]
2. [goals] Wants to visit Japan in 2027 (2026-05-10) [ume:7e2d9f4a]
3. [identity] Lives in San Francisco (2026-05-08) [ume:c4d5e6f7]
```

Format: `<number>. [<category>] <content, 80 chars> (<date>) [ume:<short_id>]`

If no results:
```
No memories matching "<query>".
```
