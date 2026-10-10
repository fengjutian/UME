# UME CLI Skill for Claude

Manage memories from the terminal using the [UME CLI](https://docs.ume.ai/platform/cli). This skill teaches Claude how to use every `ume` command, flag, and output mode -- for both the Node.js and Python implementations.

## What This Skill Does

When installed, Claude can:

- **Run ume commands** correctly in your terminal (add, search, list, get, update, delete, import, config, init, identify, whoami, status, entity, event, agent-rush, version, help)
- **Construct complex invocations** with the right flags, scoping, filters, and output formats
- **Pipe and script** ume commands in shell workflows, CI/CD pipelines, and agent loops
- **Debug issues** like missing API keys, entity scoping conflicts, and async processing delays

## Installation

### CLI (Claude Code, OpenCode, OpenClaw, or any tool that supports skills)

```bash
npx skills add https://github.com/fengjutian/UME --skill ume-cli
```

### Claude.ai

1. Download this `skills/ume-cli` folder as a ZIP
2. Go to **Settings > Capabilities > Skills**
3. Click **Upload skill** and select the ZIP

### Claude API (Skills API)

```bash
curl -X POST https://api.anthropic.com/v1/skills \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "ume-cli", "source": "https://github.com/fengjutian/UME/tree/main/skills/ume-cli"}'
```

## Prerequisites

- A UME Platform API key ([Get one here](https://app.ume.ai/dashboard/api-keys?utm_source=oss&utm_medium=skill-ume-cli-readme))
- **Node.js 18+** or **Python 3.10+**
- Install the CLI:

  ```bash
  # Node.js
  npm install -g @ume/cli

  # Python
  pip install ume-cli
  ```

- Set the environment variable:

  ```bash
  export UME_API_KEY="m0-your-api-key"
  ```

  Or run `ume init` for the interactive setup wizard.

## Quick Start

After installing, just ask Claude:

- "Add a memory for user alice that she prefers dark mode"
- "Search alice's memories for dietary preferences"
- "List all memories and output as JSON"
- "Delete all memories for user bob"
- "Set up ume CLI in my CI pipeline"
- "Pipe the output of my script into ume add"

## What's Inside

```text
skills/ume-cli/
├── SKILL.md                          # Skill definition and instructions
├── README.md                         # This file
├── LICENSE                           # Apache-2.0
└── references/                       # Documentation (loaded on demand)
    ├── command-reference.md           # Every command, flag, option, and example
    ├── configuration.md               # Config file, env vars, precedence, init wizard
    └── workflows.md                   # Piping, scripting, CI/CD, agent mode recipes
```

## Links

- [UME Platform Dashboard](https://app.ume.ai?utm_source=oss&utm_medium=skill-ume-cli-readme)
- [UME Documentation](https://docs.ume.ai)
- [UME CLI Docs](https://docs.ume.ai/platform/cli)
- [UME GitHub](https://github.com/fengjutian/UME)

## Skill Graph

This skill is part of the **UME skill graph** -- three interconnected skills for different interfaces to the UME platform:

| Skill | Purpose | Link |
|-------|---------|------|
| **ume** | Python/TypeScript SDK, REST API, framework integrations | [local](../ume/SKILL.md) / [GitHub](https://github.com/fengjutian/UME/tree/main/skills/ume) |
| **ume-cli** (this skill) | Terminal commands for memory operations | [local](./SKILL.md) / [GitHub](https://github.com/fengjutian/UME/tree/main/skills/ume-cli) |
| **ume-vercel-ai-sdk** | Vercel AI SDK provider with automatic memory | [local](../ume-vercel-ai-sdk/SKILL.md) / [GitHub](https://github.com/fengjutian/UME/tree/main/skills/ume-vercel-ai-sdk) |

## License

Apache-2.0
