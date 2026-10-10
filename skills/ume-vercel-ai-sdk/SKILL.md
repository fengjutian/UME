---
name: ume-vercel-ai-sdk
description: >
  UME provider for Vercel AI SDK (@ume/vercel-ai-provider).
  TRIGGER when: user mentions "vercel ai sdk", "@ume/vercel-ai-provider",
  "createUME", "retrieveMemories", "addMemories", "getMemories",
  "searchMemories", "ume vercel", "AI SDK provider", "AI SDK memory",
  or is using generateText/streamText with ume. Also triggers for Next.js
  apps needing memory-augmented AI.
  DO NOT TRIGGER when: user asks about direct Python/TS SDK calls without Vercel
  (use ume skill), or CLI terminal commands (use ume-cli skill).
license: Apache-2.0
metadata:
  author: ume
  version: "2.0.0"
  category: ai-memory
  tags: "vercel, ai-sdk, memory, nextjs, typescript, provider"
  ume_tested_versions: "@ume/vercel-ai-provider (npm) >=3.0.0,<4.0.0; ai (npm) >=6.0.0,<7.0.0; ume (npm) >=3.0.0,<4.0.0"
compatibility: Node.js 18+, npm install @ume/vercel-ai-provider, Vercel AI SDK v6 (ai package ^6), UME_API_KEY + LLM provider API key
---

# UME Vercel AI SDK Provider

Memory-enhanced AI provider for Vercel AI SDK. Automatically retrieves and stores memories during LLM calls.

## Step 1: Install

```bash
npm install @ume/vercel-ai-provider ai@^6
```

`ai` and the `@ai-sdk/*` provider packages ship as regular dependencies of `@ume/vercel-ai-provider`, so nothing else needs installing. The only peer dependency is `zod` (optional, `^3.0.0`).

## Step 2: Set up environment variables

```bash
export UME_API_KEY="m0-xxx"
export OPENAI_API_KEY="sk-xxx"   # or ANTHROPIC_API_KEY, GOOGLE_API_KEY, etc.
```

Get a UME API key at: https://app.ume.ai/dashboard/api-keys?utm_source=oss&utm_medium=skill-ume-vercel-ai-sdk

## Pattern 1: Wrapped Model

The wrapped model approach is the simplest. `createUME` returns a provider that wraps any supported LLM with automatic memory retrieval and storage.

```typescript
import { generateText } from "ai";
import { createUME } from "@ume/vercel-ai-provider";

const ume = createUME();
const { text } = await generateText({
  model: ume("gpt-5-mini", { user_id: "alice" }),
  prompt: "Recommend a restaurant",
});
```

What happens under the hood:
1. The prompt is stored to UME (`POST /v3/memories/add/`), awaited before the LLM call (a failed write is logged and ignored)
2. The prompt is sent to UME search (`POST /v3/memories/search/`) to retrieve relevant memories
3. If any memories are found, they are injected as a system message at the start of the prompt
4. The underlying LLM (e.g., OpenAI gpt-5-mini) generates a response using the enriched prompt

For `generateText`, the retrieved memories are also attached to the result as a source:

```typescript
const { text, sources } = await generateText({
  model: ume("gpt-5-mini", { user_id: "alice" }),
  prompt: "Recommend a restaurant",
});

console.log(sources.find((s) => s.title === "UME Memories")?.providerMetadata?.ume);
```

The source has `title: "UME Memories"` and `providerMetadata.ume` holds `memories` (array of memory objects) and `memoriesText`. It is only present when at least one memory was retrieved.

## Pattern 2: Standalone Utilities

Use standalone utilities when you want full control over the memory retrieve/store cycle, or you want to use a provider that is already configured separately.

```typescript
import { openai } from "@ai-sdk/openai";
import { generateText } from "ai";
import { retrieveMemories, addMemories } from "@ume/vercel-ai-provider";

const prompt = "Recommend a restaurant";

// Retrieve memories -- returns a formatted system prompt string
const memories = await retrieveMemories(prompt, {
  user_id: "alice",
  umeApiKey: "m0-xxx",
});

// Generate using any provider with injected memories
const { text } = await generateText({
  model: openai("gpt-5-mini"),
  prompt,
  system: memories,
});

// Optionally store the conversation back
await addMemories(
  [
    { role: "user", content: [{ type: "text", text: prompt }] },
    { role: "assistant", content: [{ type: "text", text }] },
  ],
  { user_id: "alice", umeApiKey: "m0-xxx" }
);
```

## Pattern 3: Streaming

Use `streamText` for streaming responses with memory augmentation:

```typescript
import { streamText } from "ai";
import { createUME } from "@ume/vercel-ai-provider";

const ume = createUME();
const result = streamText({
  model: ume("gpt-5-mini", { user_id: "alice" }),
  prompt: "What should I cook for dinner?",
});

for await (const chunk of result.textStream) {
  process.stdout.write(chunk);
}
```

The wrapped model stores the conversation and retrieves memories before streaming begins.

## Supported Providers

| Provider | Config value | Required env var |
|----------|-------------|------------------|
| OpenAI (default) | `"openai"` | `OPENAI_API_KEY` |
| Anthropic | `"anthropic"` | `ANTHROPIC_API_KEY` |
| Google | `"google"` (alias `"gemini"`) | `GOOGLE_GENERATIVE_AI_API_KEY` |
| Groq | `"groq"` | `GROQ_API_KEY` |
| Cohere | `"cohere"` | `COHERE_API_KEY` |

Select a provider when creating the UME instance:

```typescript
const ume = createUME({ provider: "anthropic" });
const { text } = await generateText({
  model: ume("claude-sonnet-4-20250514", { user_id: "alice" }),
  prompt: "Hello!",
});
```

## How It Works Internally

### Wrapped model flow

```
User prompt
  --> processMemories: addMemories (POST /v3/memories/add/, awaited)
  --> processMemories: getMemories (POST /v3/memories/search/)
  --> memories (if any) injected as system message at start of prompt
  --> underlying LLM generates response (doGenerate or doStream)
  --> response returned to caller (doGenerate also attaches a "UME Memories" source)
```

### Standalone flow

```
User controls each step:
  1. retrieveMemories / getMemories / searchMemories -> fetch memories
  2. inject into system prompt manually
  3. call generateText / streamText with any provider
  4. addMemories -> store new conversation to UME
```

## Key Differences Between the 4 Utility Functions

| Function | Returns | Use when |
|----------|---------|----------|
| `retrieveMemories` | Formatted system prompt **string** | Injecting directly into `system` parameter |
| `getMemories` | Raw memory **array** | Processing memories programmatically |
| `searchMemories` | Raw search **response** (as returned by the API) | Need scores and full metadata |
| `addMemories` | API response | Storing new messages to UME |

`retrieveMemories`, `getMemories`, and `searchMemories` accept `LanguageModelV3Prompt | string` as the first argument; `addMemories` is typed as `LanguageModelV3Prompt` (a string also works at runtime). All four take optional `UMEConfigSettings` as the second argument.

## Common Edge Cases and Tips

- **Always provide `user_id`** (or `agent_id`/`app_id`/`run_id`) for consistent memory retrieval. The search endpoint requires at least one entity ID in `filters`; the provider places these IDs there for you.
- **Standalone utilities require explicit API key**: pass `umeApiKey` in the config object, or set the `UME_API_KEY` environment variable.
- **This uses Vercel AI SDK v6** (LanguageModelV3 / ProviderV3 interfaces, `@ume/vercel-ai-provider` 3.x). Provider 2.x targeted AI SDK v5. It is not compatible with AI SDK v4 or earlier.
- **`processMemories` awaits `addMemories`** before searching and calling the LLM, so each wrapped call includes one memory write and one memory search. If either request fails, the error is logged and the LLM call proceeds without memories.
- **`"google"` and `"gemini"`** are both accepted and map to `@ai-sdk/google`.
- **Removed in 3.0.0**: `org_id`, `project_id`, `org_name`, `project_name`, `output_format`, `filter_memories`, `async_mode`, `enable_graph`, `version`, `api_version`. Graph memory is now a UME Platform project setting, not a provider option.
- **Default `top_k` is 10.** `threshold` and `rerank` are only sent when set (the API default for `rerank` is `false`; `threshold` is a server-side cutoff, not a floor on the returned score).
- **Custom host**: set `host` in the config to point to a different UME API endpoint (default: `https://api.ume.ai`).

## References

| Topic | File |
|-------|------|
| Provider API (`createUME`, `UMEProvider`, types) | [local](references/provider-api.md) / [GitHub](https://github.com/fengjutian/UME/tree/main/skills/ume-vercel-ai-sdk/references/provider-api.md) |
| Memory utilities (`addMemories`, `retrieveMemories`, etc.) | [local](references/memory-utilities.md) / [GitHub](https://github.com/fengjutian/UME/tree/main/skills/ume-vercel-ai-sdk/references/memory-utilities.md) |
| Usage patterns and examples | [local](references/usage-patterns.md) / [GitHub](https://github.com/fengjutian/UME/tree/main/skills/ume-vercel-ai-sdk/references/usage-patterns.md) |

## Related UME Skills

| Skill | When to use | Link |
|-------|-------------|------|
| ume | Python/TypeScript SDK, REST API, framework integrations | [local](../ume/SKILL.md) / [GitHub](https://github.com/fengjutian/UME/tree/main/skills/ume) |
| ume-cli | Terminal commands, scripting, CI/CD, agent tool loops | [local](../ume-cli/SKILL.md) / [GitHub](https://github.com/fengjutian/UME/tree/main/skills/ume-cli) |
