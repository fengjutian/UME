# ume CLI (Python)

The official command-line interface for [ume](https://ume.ai) — the memory layer for AI agents. Python implementation.

> **Built for AI agents.** Pass `--agent` (or `--json`) as a global flag on any command to get structured JSON output optimized for programmatic consumption — sanitized fields, no colors or spinners, and errors as JSON too.

## Prerequisites

- Python **3.10+**

## Installation

### Using pipx (recommended)

```bash
pipx install ume-cli
```

### Using pip

```bash
pip install ume-cli
```

> **Note:** On macOS with Homebrew Python, `pip install` outside a virtual environment will fail with an `externally-managed-environment` error ([PEP 668](https://peps.python.org/pep-0668/)). Use `pipx` instead, or install inside a virtual environment.

## Quick start

```bash
# Interactive setup wizard
ume init

# Or login via email
ume init --email alice@company.com

# Or authenticate with an existing API key
ume init --api-key m0-xxx

# Add a memory
ume add "I prefer dark mode and use vim keybindings" --user-id alice

# Search memories
ume search "What are Alice's preferences?" --user-id alice

# List all memories for a user
ume list --user-id alice

# Get a specific memory
ume get <memory-id>

# Update a memory
ume update <memory-id> "I switched to light mode"

# Delete a memory
ume delete <memory-id>
```

## Commands

### `ume init`

Interactive setup wizard. Prompts for your API key and default user ID.

```bash
ume init
ume init --api-key m0-xxx --user-id alice
ume init --email alice@company.com
```

If an existing configuration is detected, the CLI asks for confirmation before overwriting. Use `--force` to skip the prompt (useful in CI/CD).

```bash
ume init --api-key m0-xxx --user-id alice --force
```

| Flag | Description |
|------|-------------|
| `--api-key` | API key (skip prompt) |
| `-u, --user-id` | Default user ID (skip prompt) |
| `--email` | Login via email verification code |
| `--code` | Verification code (use with `--email` for non-interactive login) |
| `--force` | Overwrite existing config without confirmation |

### `ume add`

Add a memory from text, a JSON messages array, a file, or stdin.

```bash
ume add "I prefer dark mode" --user-id alice
ume add --file conversation.json --user-id alice
echo "Loves hiking on weekends" | ume add --user-id alice
```

| Flag | Description |
|------|-------------|
| `-u, --user-id` | Scope to a user |
| `--agent-id` | Scope to an agent |
| `--messages` | Conversation messages as JSON |
| `-f, --file` | Read messages from a JSON file |
| `-m, --metadata` | Custom metadata as JSON |
| `--categories` | Categories (JSON array or comma-separated) |
| `--graph / --no-graph` | Enable or disable graph memory extraction |
| `-o, --output` | Output format: `text`, `json`, `quiet` |

### `ume search`

Search memories using natural language.

```bash
ume search "dietary restrictions" --user-id alice
ume search "preferred tools" --user-id alice --output json --top-k 5
```

| Flag | Description |
|------|-------------|
| `-u, --user-id` | Filter by user |
| `-k, --top-k` | Number of results (default: 10) |
| `--threshold` | Minimum similarity score (default: 0.3) |
| `--rerank` | Enable reranking |
| `--keyword` | Use keyword search instead of semantic |
| `--filter` | Advanced filter expression (JSON) |
| `--graph / --no-graph` | Enable or disable graph in search |
| `-o, --output` | Output format: `text`, `json`, `table` |

### `ume list`

List memories with optional filters and pagination.

```bash
ume list --user-id alice
ume list --user-id alice --category preferences --output json
ume list --user-id alice --after 2024-01-01 --page-size 50
```

| Flag | Description |
|------|-------------|
| `-u, --user-id` | Filter by user |
| `--page` | Page number (default: 1) |
| `--page-size` | Results per page (default: 100) |
| `--category` | Filter by category |
| `--after` | Created after date (YYYY-MM-DD) |
| `--before` | Created before date (YYYY-MM-DD) |
| `-o, --output` | Output format: `text`, `json`, `table` |

### `ume get`

Retrieve a specific memory by ID.

```bash
ume get 7b3c1a2e-4d5f-6789-abcd-ef0123456789
ume get 7b3c1a2e-4d5f-6789-abcd-ef0123456789 --output json
```

### `ume update`

Update the text or metadata of an existing memory.

```bash
ume update <memory-id> "Updated preference text"
ume update <memory-id> --metadata '{"priority": "high"}'
echo "new text" | ume update <memory-id>
```

### `ume delete`

Delete a single memory, all memories for a scope, or an entire entity.

```bash
# Delete a single memory
ume delete <memory-id>

# Delete all memories for a user
ume delete --all --user-id alice --force

# Delete all memories project-wide
ume delete --all --project --force

# Preview what would be deleted
ume delete --all --user-id alice --dry-run
```

| Flag | Description |
|------|-------------|
| `--all` | Delete all memories matching scope filters |
| `--entity` | Delete the entity and all its memories |
| `--project` | With `--all`: delete all memories project-wide |
| `--dry-run` | Preview without deleting |
| `--force` | Skip confirmation prompt |

### `ume import`

Bulk import memories from a JSON file.

```bash
ume import data.json --user-id alice
```

The file should be a JSON array where each item has a `memory` (or `text` or `content`) field and optional `user_id`, `agent_id`, and `metadata` fields.

### `ume config`

View or modify the local CLI configuration.

```bash
ume config show              # Display current config (secrets redacted)
ume config get api_key       # Get a specific value
ume config set user_id bob   # Set a value
```

### `ume entity`

List or delete entities (users, agents, apps, runs).

```bash
ume entity list users
ume entity list agents --output json
ume entity delete --user-id alice --force
```

### `ume event`

Inspect background processing events created by async operations (e.g. bulk deletes, large add jobs).

```bash
# List recent events
ume event list

# Check the status of a specific event
ume event status <event-id>
```

| Flag | Description |
|------|-------------|
| `-o, --output` | Output format: `text`, `json` |

### `ume status`

Verify your API connection and display the current project.

```bash
ume status
```

## Agent mode

Pass `--agent` (or its alias `--json`) as a **global flag** on any command to get output designed for AI agent tool loops:

```bash
ume --agent search "user preferences" --user-id alice
ume --agent add "User prefers dark mode" --user-id alice
ume --agent list --user-id alice
ume --agent delete --all --user-id alice --force
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

## Global flags

These flags are available on all commands:

| Flag | Description |
|------|-------------|
| `--json` | Enable agent mode: structured JSON envelope output, no colors or spinners |
| `--agent` | Alias for `--json` |
| `--api-key` | Override the configured API key for this request |
| `--base-url` | Override the configured API base URL for this request |
| `-o, --output` | Set the output format |

`ume --version` prints the CLI version. It is only valid before a subcommand, not after one.

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

Environment variables take precedence over values in the config file, which take precedence over defaults.

## Development

```bash
cd cli/python
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Run during development
python -m ume_cli --help
ume add "test memory" --user-id alice
```

## Releasing

1. Update `version` in `pyproject.toml`
2. Create a GitHub Release with tag `cli-v<version>` (e.g. `cli-v0.2.1`)

For a pre-release, use a beta version like `0.2.1b1` and check the **pre-release** checkbox.

## Documentation

Full documentation is available at [docs.ume.ai/platform/cli](https://docs.ume.ai/platform/cli).

## License

Apache-2.0
