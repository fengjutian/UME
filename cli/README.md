# ume CLI

The official command-line interface for [ume](https://ume.ai) — the memory layer for AI agents. Works with the UME Platform API. Available in Python and Node.js.

> **For AI agents:** pass `--agent` (or `--json`) on any command for structured JSON output purpose-built for tool loops — sanitized fields, no colors or spinners, errors as JSON. See [Agent mode](#agent-mode) below.

## Installation

```bash
npm install -g @ume/cli
```

```bash
pip install ume-cli
```

Both packages install a `ume` binary with identical behavior.

## Quick start

```bash
# Interactive setup wizard
ume init

# Or login via email (get a new API key)
ume init --email alice@company.com

# Or authenticate with an existing API key
ume init --api-key m0-xxx

# Add a memory
ume add "I prefer dark mode and use vim keybindings" --user-id alice

# Search memories
ume search "What are Alice's preferences?" --user-id alice

# List all memories for a user
ume list --user-id alice

# Update a memory
ume update <memory-id> "I switched to light mode"

# Delete a memory
ume delete <memory-id>
```

## Commands

| Command | Description |
|---------|-------------|
| `ume init` | Setup wizard — login via email or configure API key manually |
| `ume add` | Add a memory from text, JSON messages, a file, or stdin |
| `ume search` | Search memories using natural language |
| `ume list` | List memories with optional filters and pagination |
| `ume get` | Retrieve a specific memory by ID |
| `ume update` | Update the text or metadata of a memory |
| `ume delete` | Delete a memory, all memories for a scope, or an entity |
| `ume import` | Bulk import memories from a JSON file |
| `ume config` | View or modify CLI configuration |
| `ume entity` | List or delete entities (users, agents, apps, runs) |
| `ume event` | Inspect background processing events (bulk deletes, large add jobs) |
| `ume status` | Verify API connection and display current project |

Run `ume <command> --help` for detailed usage on any command, or `ume --version` to print the CLI version.

## Agent mode

Pass `--agent` (or its alias `--json`) as a **global flag** on any command to get output designed for AI agent tool loops:

```bash
ume --agent search "user preferences" --user-id alice
ume --agent add "User prefers dark mode" --user-id alice
ume --agent list --user-id alice
```

Every command returns the same envelope shape:

```json
{
  "status": "success",
  "command": "search",
  "duration_ms": 134,
  "scope": { "user_id": "alice" },
  "count": 2,
  "data": [
    { "id": "abc-123", "memory": "User prefers dark mode", "score": 0.97, "created_at": "2026-01-15", "categories": ["preferences"] }
  ]
}
```

What agent mode does differently from `--output json`:
- **Sanitized `data`**: only the fields an agent needs (id, memory, score, etc.) — no internal API noise
- **No human output**: spinners, colors, and banners are suppressed entirely
- **Errors as JSON**: errors go to stdout as `{"status": "error", "command": "...", "error": "..."}` with a non-zero exit code

Use `ume help --json` to get the full command tree as JSON — useful for agents that need to self-discover available commands.

## Output formats

Control how results are displayed with `--output`:

| Format | Description |
|--------|-------------|
| `text` | Human-readable with colors and formatting (default) |
| `json` | Structured JSON for piping to `jq` (raw API response) |
| `table` | Tabular format (default for `list`) |
| `quiet` | Minimal — just IDs or status codes |
| `agent` | Structured JSON envelope with sanitized fields (set by `--agent`/`--json`) |

## Environment variables

| Variable | Description |
|----------|-------------|
| `UME_API_KEY` | API key (overrides config file) |
| `UME_BASE_URL` | API base URL |
| `UME_USER_ID` | Default user ID |
| `UME_AGENT_ID` | Default agent ID |
| `UME_APP_ID` | Default app ID |
| `UME_RUN_ID` | Default run ID |
| `UME_ENABLE_GRAPH` | Enable graph memory (`true` / `false`) |

## Implementations

| Language | Directory | Package | Docs |
|----------|-----------|---------|------|
| TypeScript | [`node/`](./node/) | `@ume/cli` | [README](./node/README.md) |
| Python | [`python/`](./python/) | `ume-cli` | [README](./python/README.md) |

## Documentation

Full documentation is available at [docs.ume.ai/platform/cli](https://docs.ume.ai/platform/cli).

## License

Apache-2.0
