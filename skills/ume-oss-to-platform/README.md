# ume-oss-to-platform — Pipeline Skill

Migrate a project from the UME Open Source (self-hosted) SDK to the UME Platform (hosted) SDK, end to end. The skill audits where UME is used, writes a reviewable migration plan, and executes it after you approve.

> **This is a pipeline skill, not a reference skill.** Invoke it when you want your agent to migrate an existing project's UME integration from OSS to the Platform. For day-to-day SDK coding help, install [`ume`](../ume/SKILL.md) instead.
>
> **Part of the UME Skill Graph:**
> - Reference: [ume](../ume/SKILL.md) · [ume-cli](../ume-cli/SKILL.md) · [ume-vercel-ai-sdk](../ume-vercel-ai-sdk/SKILL.md)
> - Pipeline: [ume-integrate](../ume-integrate/SKILL.md) → [ume-test-integration](../ume-test-integration/SKILL.md) · **ume-oss-to-platform** (this skill)

## What This Skill Does

When invoked, your assistant will:

- **Discover** every place UME is used in the project — imports, client init, config blocks, call sites, dependencies, env, and local infra
- **Verify** the exact API against the installed SDK rather than guessing
- **Map** each OSS `Memory` usage to its hosted `MemoryClient` equivalent (Python and TypeScript)
- **Flag** everything that isn't a clean 1:1 and needs a human decision
- **Write** a reviewable `UME_MIGRATION_PLAN.md`, then **execute it after you approve** — strictly scoped to the UME integration, with no unrelated refactors

## When to Use

Trigger phrases:

- "Migrate my UME setup to the Platform"
- "Switch from self-hosted UME to MemoryClient"
- "Use my UME API key instead of a local Qdrant"
- "Move UME to the hosted/managed service"

Do **not** use this skill for general SDK usage (install [`ume`](../ume/SKILL.md)), or to add UME to a repo that doesn't use it yet (use [`ume-integrate`](../ume-integrate/SKILL.md)).

## Installation

### CLI (Claude Code, Codex, OpenCode, OpenClaw, or any tool that supports skills)

```bash
npx skills add https://github.com/fengjutian/UME --skill ume-oss-to-platform
```

### Claude.ai

1. Download this `skills/ume-oss-to-platform` folder as a ZIP
2. Go to **Settings > Capabilities > Skills**
3. Click **Upload skill** and select the ZIP

### Claude API (Skills API)

```bash
curl -X POST https://api.anthropic.com/v1/skills \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "ume-oss-to-platform", "source": "https://github.com/fengjutian/UME/tree/main/skills/ume-oss-to-platform"}'
```

### Prerequisites

- A UME Platform API key ([get one](https://app.ume.ai/dashboard/api-keys))
- An existing project that uses the UME OSS SDK

## Workflow

```
(invoke skill)  →  audits the repo's UME usage,
                   writes UME_MIGRATION_PLAN.md,
                   stops for your review
(approve)       →  executes the plan and verifies
                   (compile/import, real-API smoke test)
```

## Links

- [UME Platform Dashboard](https://app.ume.ai)
- [UME Documentation](https://docs.ume.ai)
- [OSS → Platform migration guide](https://docs.ume.ai/migration/oss-to-platform)
- [Platform vs OSS comparison](https://docs.ume.ai/platform/platform-vs-oss)

## License

Apache-2.0
