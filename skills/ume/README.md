# UME Skill for Claude

Add persistent memory to any AI application in minutes using [UME Platform](https://app.ume.ai?utm_source=oss&utm_medium=skill-ume-readme) or the open-source self-hosted SDK.

> **Part of the UME Skill Graph:** See also [ume-cli](../ume-cli/SKILL.md) (terminal) and [ume-vercel-ai-sdk](../ume-vercel-ai-sdk/SKILL.md) (Vercel AI SDK).

## What This Skill Does

When installed, Claude can:

- **Set up UME** in your Python or TypeScript project (Platform or OSS)
- **Integrate memory** into your existing AI app (LangChain, CrewAI, OpenAI Agents, LangGraph, LlamaIndex, etc.)
- **Generate working code** using real API references and tested patterns
- **Search live docs** on demand for the latest UME documentation

## Installation

### CLI (Claude Code, OpenCode, OpenClaw, or any tool that supports skills)

```bash
npx skills add https://github.com/fengjutian/UME --skill ume
```

### Claude.ai

1. Download this `skills/ume` folder as a ZIP
2. Go to **Settings > Capabilities > Skills**
3. Click **Upload skill** and select the ZIP

### Claude API (Skills API)

```bash
curl -X POST https://api.anthropic.com/v1/skills \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "ume", "source": "https://github.com/fengjutian/UME/tree/main/skills/ume"}'
```

### Prerequisites

- A UME Platform API key ([Get one here](https://app.ume.ai/dashboard/api-keys?utm_source=oss&utm_medium=skill-ume-readme))
- Python 3.10+ or Node.js 18+
- Set the environment variable:

  ```bash
  export UME_API_KEY="m0-your-api-key"
  ```

## Quick Start

After installing, just ask Claude:

- "Set up ume in my project"
- "Add memory to my chatbot"
- "Help me search user memories with filters"
- "Integrate ume with my LangChain app"
- "Add graph memory to track entity relationships"

## What's Inside

```text
skills/ume/
├── SKILL.md                    # Skill definition and instructions
├── README.md                   # This file
├── LICENSE                     # Apache-2.0
├── client/                     # Language-specific SDK references (Platform + OSS)
│   ├── python.md               # Python SDK (MemoryClient + Memory OSS)
│   ├── node.md                 # TypeScript SDK (MemoryClient + Memory OSS)
│   └── differences.md          # Python vs TypeScript comparison
├── scripts/
│   └── ume_doc_search.py      # Search live UME docs on demand
└── references/                 # Documentation (loaded on demand)
    ├── quickstart.md           # Full quickstart (Python, TS, cURL)
    ├── sdk-guide.md            # All SDK methods (Python + TypeScript)
    ├── api-reference.md        # REST endpoints, filters, memory object
    ├── architecture.md         # Processing pipeline, lifecycle, scoping, performance
    ├── features.md             # Retrieval, graph, categories, MCP, webhooks, multimodal
    ├── integration-patterns.md # LangChain, CrewAI, OpenAI Agents, LangGraph, LlamaIndex, etc.
    └── use-cases.md            # 7 real-world patterns with Python + TypeScript code
```

## Links

- [UME Platform Dashboard](https://app.ume.ai?utm_source=oss&utm_medium=skill-ume-readme)
- [UME Documentation](https://docs.ume.ai)
- [UME GitHub](https://github.com/fengjutian/UME)
- [API Reference](https://docs.ume.ai/api-reference)

## License

Apache-2.0
