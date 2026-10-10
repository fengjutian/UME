# UME Skills for AI Coding Assistants

UME ships structured skill definitions for Claude Code, Codex, Cursor, OpenCode, OpenClaw, and any assistant that supports the [skills standard](https://github.com/anthropics/skills). Skills teach the assistant how to work with UME — either by loading SDK knowledge into context, or by executing an end-to-end workflow on demand.

## Two Categories

### Reference skills — always on

Installed once, loaded into context so the assistant writes correct UME code. Use these for day-to-day development.

| Skill | Surface | Install |
|-------|---------|---------|
| [`ume`](./ume/) | Python + TypeScript SDKs (Platform + OSS), framework integrations | `npx skills add https://github.com/fengjutian/UME --skill ume` |
| [`ume-cli`](./ume-cli/) | Terminal workflows (`ume` CLI, both Node and Python) | `npx skills add https://github.com/fengjutian/UME --skill ume-cli` |
| [`ume-vercel-ai-sdk`](./ume-vercel-ai-sdk/) | `@ume/vercel-ai-provider` and `createUME` | `npx skills add https://github.com/fengjutian/UME --skill ume-vercel-ai-sdk` |

### Pipeline skills — run on demand

Invoked as a slash command to execute a specific end-to-end workflow. These do real work: they create branches, write tests, run code.

| Skill | Trigger | Install |
|-------|---------|---------|
| [`ume-integrate`](./ume-integrate/) | `/ume-integrate` — wire UME into an existing repo via TDD | `npx skills add https://github.com/fengjutian/UME --skill ume-integrate` |
| [`ume-test-integration`](./ume-test-integration/) | `/ume-test-integration` — verify what `/ume-integrate` produced | `npx skills add https://github.com/fengjutian/UME --skill ume-test-integration` |
| [`ume-oss-to-platform`](./ume-oss-to-platform/) | `/ume-oss-to-platform` — migrate a project from UME OSS to the hosted Platform SDK | `npx skills add https://github.com/fengjutian/UME --skill ume-oss-to-platform` |

The `ume-integrate` and `ume-test-integration` skills are designed to run in sequence on the same workspace:

```
/ume-integrate          →  ume-integrate/<slug> branch + .ume-integration/ artifacts
/ume-test-integration   →  scorecard (compile + runtime verification, real API smoke test)
```

## Choosing a Skill

- **Writing UME code in a new or existing project?** → `ume`
- **Using the terminal CLI?** → `ume-cli`
- **Building with `@ai-sdk/*`?** → `ume-vercel-ai-sdk`
- **Want the assistant to wire UME into an existing repo for you?** → `ume-integrate`, then `ume-test-integration`
- **Already using UME OSS and want to move to the hosted Platform?** → `ume-oss-to-platform`

## Links

- [Vibecoding with UME](https://docs.ume.ai/vibecoding) — canonical landing page
- [Claude Code integration](https://docs.ume.ai/integrations/claude-code)
- [UME Platform Dashboard](https://app.ume.ai)
- [UME Documentation](https://docs.ume.ai)

## License

Apache-2.0
