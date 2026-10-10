# UME Vercel AI SDK Skill for Claude

Add persistent memory to any Vercel AI SDK application using [@ume/vercel-ai-provider](https://www.npmjs.com/package/@ume/vercel-ai-provider).

## What This Skill Does

When installed, Claude can:

- **Set up `@ume/vercel-ai-provider`** in your TypeScript or Next.js project
- **Generate working code** using the wrapped model (`createUME`) or standalone utilities (`retrieveMemories`, `addMemories`, etc.)
- **Configure multi-provider setups** (OpenAI, Anthropic, Google, Groq, Cohere)
- **Integrate memory** into streaming responses, structured output, and API routes

## Installation

### CLI (Claude Code, OpenCode, OpenClaw, or any tool that supports skills)

```bash
npx skills add https://github.com/fengjutian/UME --skill ume-vercel-ai-sdk
```

### Claude.ai

1. Download this `skills/ume-vercel-ai-sdk` folder as a ZIP
2. Go to **Settings > Capabilities > Skills**
3. Click **Upload skill** and select the ZIP

### Claude API (Skills API)

```bash
curl -X POST https://api.anthropic.com/v1/skills \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "ume-vercel-ai-sdk", "source": "https://github.com/fengjutian/UME/tree/main/skills/ume-vercel-ai-sdk"}'
```

### Prerequisites

- **Node.js 18+**
- **Vercel AI SDK v6** (`ai` package version 6.x)
- A UME Platform API key ([Get one here](https://app.ume.ai/dashboard/api-keys?utm_source=oss&utm_medium=skill-ume-vercel-ai-sdk-readme))
- An LLM provider API key (OpenAI, Anthropic, Google, Groq, or Cohere)
- Set environment variables:

  ```bash
  export UME_API_KEY="m0-xxx"
  export OPENAI_API_KEY="sk-xxx"  # or your chosen provider's key
  ```

## Quick Start

After installing, just ask Claude:

- "Add memory to my Vercel AI SDK app"
- "Set up ume with streamText in my Next.js API route"
- "Use retrieveMemories with Anthropic instead of the wrapped model"
- "Show me how to read the UME source from generateText with the Vercel AI provider"
- "Help me store conversation history with addMemories"

## What's Inside

```text
skills/ume-vercel-ai-sdk/
├── SKILL.md                          # Skill definition and instructions
├── README.md                         # This file
├── LICENSE                           # Apache-2.0
└── references/                       # Documentation (loaded on demand)
    ├── provider-api.md               # createUME, UMEProvider, types, config
    ├── memory-utilities.md           # addMemories, retrieveMemories, getMemories, searchMemories
    └── usage-patterns.md             # Working examples: streaming, Next.js, multi-provider
```

## Links

- [UME Platform Dashboard](https://app.ume.ai?utm_source=oss&utm_medium=skill-ume-vercel-ai-sdk-readme)
- [UME Documentation](https://docs.ume.ai)
- [UME GitHub](https://github.com/fengjutian/UME)
- [@ume/vercel-ai-provider on npm](https://www.npmjs.com/package/@ume/vercel-ai-provider)
- [Vercel AI SDK Documentation](https://ai-sdk.dev/docs)

## Skill Graph

This skill is part of the UME skill graph. The three UME skills (ume, ume-cli, ume-vercel-ai-sdk) each cover a different interface to the same UME Platform API.

## License

Apache-2.0
