# ume-integrate — Pipeline Skill

Wire [UME](https://ume.ai) into an existing repository end-to-end, using a goal-driven, test-first pipeline.

> **This is a pipeline skill, not a reference skill.** Invoke it as `/ume-integrate` when you want your assistant to do the work of integrating UME into a target repo. For day-to-day SDK coding help, install [`ume`](../ume/SKILL.md) instead.
>
> **Part of the UME Skill Graph:**
> - Reference: [ume](../ume/SKILL.md) · [ume-cli](../ume-cli/SKILL.md) · [ume-vercel-ai-sdk](../ume-vercel-ai-sdk/SKILL.md)
> - Pipeline: **ume-integrate** (this skill) → [ume-test-integration](../ume-test-integration/SKILL.md)

## What This Skill Does

When invoked, your assistant will:

- **Detect** the target repo's language and stack automatically
- **Ask** whether to integrate with UME Platform (managed) or UME Open Source (self-hosted)
- **Write failing tests first** — no implementation until tests exist
- **Keep the integration additive and feature-flagged** — existing behavior stays byte-for-byte identical when the flag is unset
- **Produce a local feature branch** (`ume-integrate/...`) and a `.ume-integration/` directory of artifacts (`goal.md`, `plan.md`, `product.json`) consumed by the companion verification skill

## When to Use

Trigger phrases:

- "Integrate UME into this repo"
- "Add UME to my project"
- "Wire UME into `<repo>`"
- "How do I add memory to an existing project?"

Do **not** use this skill for general SDK usage (install [`ume`](../ume/SKILL.md)), terminal workflows (install [`ume-cli`](../ume-cli/SKILL.md)), or Vercel AI SDK integration (install [`ume-vercel-ai-sdk`](../ume-vercel-ai-sdk/SKILL.md)).

## Installation

### CLI (Claude Code, Codex, OpenCode, OpenClaw, or any tool that supports skills)

```bash
npx skills add https://github.com/fengjutian/UME --skill ume-integrate
```

For verification on the same branch, also install the companion skill:

```bash
npx skills add https://github.com/fengjutian/UME --skill ume-test-integration
```

### Claude.ai

1. Download this `skills/ume-integrate` folder as a ZIP
2. Go to **Settings > Capabilities > Skills**
3. Click **Upload skill** and select the ZIP

### Claude API (Skills API)

```bash
curl -X POST https://api.anthropic.com/v1/skills \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "ume-integrate", "source": "https://github.com/fengjutian/UME/tree/main/skills/ume-integrate"}'
```

### Prerequisites

- A UME Platform API key ([get one](https://app.ume.ai/dashboard/api-keys)) *or* a working OSS setup (LLM + vector store)
- Python 3.10+ or Node.js 18+ in the target repo
- A clean working tree on the target repo's default branch

## Workflow

```
/ume-integrate          →  creates ume-integrate/<slug> branch,
                            writes .ume-integration/ artifacts,
                            implements against failing tests
/ume-test-integration   →  runs the repo's native test suite,
                            executes a real end-to-end smoke flow,
                            produces a scorecard
```

The two skills are loosely coupled — they share the same workspace and branch via `.ume-integration/`, but the verifier never modifies source.

## Links

- [UME Platform Dashboard](https://app.ume.ai)
- [UME Documentation](https://docs.ume.ai)
- [UME GitHub](https://github.com/fengjutian/UME)
- [Platform vs OSS comparison](https://docs.ume.ai/platform/platform-vs-oss)

## License

Apache-2.0
