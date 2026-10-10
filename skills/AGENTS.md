# Skills (`skills/`)

Claude Code skill definitions published from this repo. Agents fetch them by raw URL, so treat every file here as a public API.

## The two kinds

**Reference skills** carry SDK knowledge and are always available:

| Skill | Covers |
|-------|--------|
| `ume/` | Python + TypeScript SDKs, Platform and OSS, framework integrations |
| `ume-cli/` | Terminal workflows for `ume-cli` and `@ume/cli` |
| `ume-vercel-ai-sdk/` | The `@ume/vercel-ai-provider` package |

**Pipeline skills** run on demand and have side effects:

| Skill | Does |
|-------|------|
| `ume-integrate/` | Wires UME into an existing repo through a TDD pipeline. Writes a feature branch plus `.ume-integration/` artifacts. |
| `ume-test-integration/` | Verifies what the integrator produced, on the same branch. Read-only against the repo. |
| `ume-oss-to-platform/` | Migrates a project from OSS to the hosted Platform SDK. Plans first, executes on approval. |

`ume-integrate` and `ume-test-integration` are **loosely coupled**: they share state only through `.ume-integration/` files, never through conversation context.

## File layout

```
skills/<name>/
├── SKILL.md          entry point, always loaded when the skill triggers
├── README.md         human-facing, GitHub renders this
├── LICENSE           Apache-2.0
├── references/       loaded on demand, one file per topic
├── client/           optional, per-runtime call patterns
└── scripts/          optional executables
```

## Size budget

`SKILL.md` is loaded in full every time the skill fires, so it is the expensive file. Keep it **under 500 lines**. Everything past the decision-making core belongs in `references/`, which the agent loads only when it needs that topic.

Rule of thumb for what stays in `SKILL.md`:

- Frontmatter, including the trigger and do-not-trigger conditions.
- Anything the agent must honor on **every** run: non-negotiable principles, preconditions, gates.
- A one-line-per-step overview of the pipeline.
- Invocation, modes, exit codes.

Everything else, meaning full step mechanics, document templates, and verbatim subagent prompts, goes in `references/` with a link from the overview.

Current sizes, longest first:

```
ume-cli/references/command-reference.md  757   reference, on demand
ume/references/use-cases.md              721   reference, on demand
ume/client/python.md                     522   reference, on demand
ume/client/node.md                       507   reference, on demand
ume-cli/references/workflows.md          446   reference, on demand
ume/references/features.md               406   reference, on demand
ume/references/integration-patterns.md   403   reference, on demand
ume-test-integration/SKILL.md            386   entry point, under budget
ume-integrate/references/pipeline.md     380   reference, on demand
ume-integrate/SKILL.md                   220   entry point
ume-vercel-ai-sdk/SKILL.md               210   entry point
ume/SKILL.md                             194   entry point
ume-cli/SKILL.md                         170   entry point
ume-oss-to-platform/SKILL.md             132   entry point
```

`ume-integrate` is the one skill that needed splitting: it was 620 lines, now
220, with the ten-step mechanics in `references/pipeline.md` and the two
verbatim subagent system prompts in `references/subagent-prompts.md`. The
`SKILL.md` keeps only what every run must honor: canonical sources, the seven
integration principles, the delegation table, preconditions, a one-line-per-step
pipeline overview, artifacts, modes, invocation, and exit codes.

Reference files may run long. They are only read when the agent asks for that topic, so a 700-line `use-cases.md` costs nothing on a run that never opens it.

## Frontmatter

```yaml
---
name: <matches the directory name>
description: >
  What it does, then TRIGGER when: ... then DO NOT TRIGGER when: ...
  The trigger conditions are what routing depends on. Be specific and
  name the sibling skill to use instead.
license: Apache-2.0
metadata:
  author: ume
  version: "0.1.0"
  category: ai-memory
  tags: "comma, separated"
  ume_tested_versions: "ume (PyPI) >=2.0.0,<3.0.0; ume (npm) >=3.0.0,<4.0.0"
---
```

Bump `ume_tested_versions` whenever the SDK majors move. Skills that pin call shapes against a version that no longer exists produce code that fails at runtime, which is worse than a skill that declines to fire.

## Conventions

- Cite canonical sources by URL (`https://docs.ume.ai/llms.txt`, `openapi.json`, raw skill URLs). Skills must not rely on ambient model knowledge of the UME API.
- When one skill's territory is covered by another, delegate to it by raw URL rather than paraphrasing its patterns.
- Pipeline skills declare **exit codes** in a table and mean them.
- Cross-references between files use relative paths so the skill works when vendored into another repo.
