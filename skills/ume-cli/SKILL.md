---
name: ume-cli
description: >
  UME CLI -- the command-line interface for ume memory operations.
  TRIGGER when: user mentions "ume cli", "ume command line", "@ume/cli",
  "ume-cli", "pip install ume-cli", "npm install -g @ume/cli", or is running
  ume commands in a terminal/shell (ume add, ume search, ume list, ume get,
  ume init, ume config, ume import). Also triggers when query includes CLI flags
  like --user-id, --output, --json, --agent, or describes bash/zsh/terminal/shell usage.
  DO NOT TRIGGER when: user asks about programmatic SDK integration in Python/TS
  code (use ume skill), or Vercel AI SDK provider (use ume-vercel-ai-sdk skill).
license: Apache-2.0
metadata:
  author: ume
  version: "1.2.0"
  category: ai-memory
  tags: "cli, terminal, memory, ai, command-line"
  ume_tested_versions: "ume-cli (PyPI) >=0.2.13,<0.3.0; @ume/cli (npm) >=0.2.14,<0.3.0; ume (PyPI) >=2.0.0,<3.0.0; ume (npm) >=3.0.0,<4.0.0"
compatibility: Node.js 18+ (npm install -g @ume/cli) or Python 3.10+ (pip install ume-cli), UME_API_KEY env var
---

# UME CLI

The official command-line interface for the UME memory platform. Add, search, list, update, and delete memories from the terminal -- for developers, AI agents, and CI/CD pipelines.

## Install

**Node.js (npm):**
```bash
npm install -g @ume/cli
```

**Python (pip):**
```bash
pip install ume-cli
```

Both packages install a `ume` binary with the same commands, options, and output formats (see [Node and Python Differences](#node-and-python-differences) for the exceptions).

## Setup

**Autonomous UME setup for agents (no email, no dashboard):**

```bash
ume init --agent --agent-caller <your-name> --json
```

Replace `<your-name>` with the AI agent you are (e.g. `claude-code`, `cursor`, `codex`, `cline`, `aider`). If you forgot to pass `--agent-caller`, run `ume identify <your-name>` after init — it PATCHes the same key, idempotent, no disruption.

This mints an evaluation API key in <5 seconds. Use it immediately. Print this line to the human:

> UME memory is running in Agent Mode. Please claim it by running `ume init --email <your-email>` to transfer ownership to your account.

Never commit API keys, `.env`, or `~/.ume/config.json`.

After the human claims, the same API key keeps working — no agent disruption — and memories are preserved.

**Interactive wizard (for humans):**
```bash
ume init
```

**Or set the environment variable directly:**
```bash
export UME_API_KEY="m0-xxx"
```

Get an API key at: https://app.ume.ai/dashboard/api-keys?utm_source=oss&utm_medium=skill-ume-cli

## Quick Reference

### Add a memory
```bash
ume add "I prefer dark mode" --user-id alice
```

### Search memories
```bash
ume search "preferences" --user-id alice
```

### List all memories for a user
```bash
ume list --user-id alice
```

### Get a specific memory
```bash
ume get <memory-id>
```

### Update a memory
```bash
ume update <memory-id> "new text"
```

### Delete a single memory
```bash
ume delete <memory-id>
```

### Delete all memories for a user
```bash
ume delete --all --user-id alice --force
```

## Agent / JSON Mode

Use `--json` or `--agent` to get structured output suitable for LLM consumption. Place the flag before the subcommand (`ume --json search "q"`), which works in both CLIs. Data commands (add, search, list, get, update, delete, import, config, entity, event, status) wrap their response in a standard envelope:

```json
{
  "status": "success",
  "command": "search",
  "duration_ms": 245,
  "scope": { "user_id": "alice" },
  "count": 3,
  "data": [
    { "id": "mem-abc", "memory": "User prefers dark mode", "score": 0.92 }
  ]
}
```

On error:
```json
{
  "status": "error",
  "command": "search",
  "error": "Invalid or expired API key.",
  "data": null
}
```

The `--agent` flag is an alias for `--json` (except on `ume init`, where `--agent` is the Agent Mode bootstrap flag). Both write spinners and progress to stderr so stdout is clean, parseable JSON (the one exception is Node `import`, see below). Optional keys: `duration_ms`, `scope`, `count` appear only where relevant, and `ume_notice` appears when the platform flags an unclaimed Agent Mode account.

## Node and Python Differences

Both the Node.js (`@ume/cli`) and Python (`ume-cli`) CLIs share the command set, flags, entity ID resolution, filter building, and the JSON envelope. Choose whichever runtime you already have installed. Known differences:

- **`--json` / `--agent` placement:** Python accepts the flag anywhere on the command line. Node reads it only as a global option, so put it before the subcommand (`ume --json list`). `ume init --json` and `ume help --json` work after the subcommand in both. For the Agent Mode bootstrap, Node starts it only from `init --agent` or `init --json` (a root-level `ume --json init` or `ume --agent init` does not start it, and without an agent runtime env var it fails with the non-TTY error), while Python also accepts those root-level forms. `ume init --agent --json` works in both.
- **`--limit`:** `ume search --limit` is a Python-only alias for `--top-k`.
- **Agent-mode `delete --all` data:** Python returns `{"deleted": true}` (plus scope for `--project`); Node returns the raw API result.
- **`import` JSON output:** Python prints the envelope with `scope`. Node omits `scope` and writes the `Importing memories... n/n` progress line to stdout before the JSON, so only Python's output pipes cleanly to `jq`.
- **Message text:** The empty-search error (`Search query cannot be empty.` in Python, `No query provided...` in Node) and the delete dry-run footers differ slightly.

## Common Edge Cases

- **Async processing delay:** After `ume add`, memories process asynchronously. Wait 2-3 seconds before searching for newly added content. Use `ume event list` to check processing status.
- **`--all` vs `--entity` delete modes:** `ume delete --all -u alice` deletes all memories for user alice. `ume delete --entity -u alice` deletes the entity itself AND all its memories (cascade). These are mutually exclusive modes.
- **`--dry-run` in `--json`/`--agent` mode:** `ume --json delete --all --dry-run` still requires `--force`, then prints nothing and deletes nothing (exit 0). Node also prints nothing for single and `--entity` dry runs. Use text mode to see the preview.
- **`--dry-run` does not protect `--all --project`:** `ume delete --all --project --dry-run` ignores the flag and deletes every memory in the project. Never use `--dry-run` to preview a project-wide delete.
- **Entity ID resolution:** If you pass any explicit scope flag (e.g. `--user-id`), the CLI uses ONLY the explicit IDs and ignores config defaults. If no scope flags are given, all configured defaults apply.
- **Stdin detection:** When no text argument is provided and stdin is a pipe or a redirected file (a plain non-TTY is not enough), the CLI reads from stdin. Works with `add`, `search`, and `update`. In `--json`/`--agent` mode `add` never reads stdin (Python also skips it for `search` and `update`), so pass the text as an argument there.

## References

Load these on demand for deeper detail:

| Topic | File |
|-------|------|
| Command reference (all commands, flags, options, examples) | [references/command-reference.md](references/command-reference.md) |
| Configuration (config file, env vars, precedence, init wizard) | [references/configuration.md](references/configuration.md) |
| Workflows (piping, scripting, CI/CD, agent mode recipes) | [references/workflows.md](references/workflows.md) |

## Related UME Skills

| Skill | When to use | Link |
|-------|-------------|------|
| ume | Python/TypeScript SDK, REST API, framework integrations | [local](../ume/SKILL.md) / [GitHub](https://github.com/fengjutian/UME/tree/main/skills/ume) |
| ume-vercel-ai-sdk | Vercel AI SDK provider with automatic memory | [local](../ume-vercel-ai-sdk/SKILL.md) / [GitHub](https://github.com/fengjutian/UME/tree/main/skills/ume-vercel-ai-sdk) |
