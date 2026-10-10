# UME AI SDK Provider

The **UME AI SDK Provider** is a community-maintained library developed by [UME](https://ume.ai/) to integrate with the Vercel AI SDK. This library brings enhanced AI interaction capabilities to your applications by introducing persistent memory functionality. With UME, language model conversations gain memory, enabling more contextualized and personalized responses based on past interactions.

Discover more of **UME** on [GitHub](https://github.com/fengjutian/UME).
Explore the [UME Documentation](https://docs.ume.ai/overview) to gain deeper control and flexibility in managing your memories.

For detailed information on using the Vercel AI SDK, refer to Vercel’s [API Reference](https://sdk.vercel.ai/docs/reference) and [Documentation](https://sdk.vercel.ai/docs).

## Features

- 🧠 Persistent memory storage for AI conversations
- 🔄 Seamless integration with Vercel AI SDK
- 🚀 Support for multiple LLM providers
- 📝 Rich message format support
- ⚡ Streaming capabilities
- 🔍 Context-aware responses

## Installation

```bash
npm install @ume/vercel-ai-provider
```

## Before We Begin

### Setting Up UME

1. Obtain your [UME API Key](https://app.ume.ai/dashboard/api-keys?utm_source=oss&utm_medium=vercel-ai-sdk-readme) from the UME dashboard.

2. Initialize the UME Client:

```typescript
import { createUME } from "@ume/vercel-ai-provider";

const ume = createUME({
  provider: "openai",
  umeApiKey: "m0-xxx",
  apiKey: "openai-api-key",
  config: {
    compatibility: "strict",
    // Additional model-specific configuration options can be added here.
  },
});
```

### Note
By default, the `openai` provider is used, so specifying it is optional:
```typescript
const ume = createUME();
```
For better security, consider setting `UME_API_KEY` and `OPENAI_API_KEY` as environment variables.

3. Add Memories to Enhance Context:

```typescript
import { LanguageModelV1Prompt } from "ai";
import { addMemories } from "@ume/vercel-ai-provider";

const messages: LanguageModelV1Prompt = [
  {
    role: "user",
    content: [
      { type: "text", text: "I love red cars." },
      { type: "text", text: "I like Toyota Cars." },
      { type: "text", text: "I prefer SUVs." },
    ],
  },
];

await addMemories(messages, { user_id: "borat" });
```

These memories are now stored in your profile. You can view and manage them on the [UME Dashboard](https://app.ume.ai/dashboard/users?utm_source=oss&utm_medium=vercel-ai-sdk-readme).

### Note:

For standalone features, such as `addMemories` and `retrieveMemories`,
you must either set `UME_API_KEY` as an environment variable or pass it directly in the function call.

Example:

```typescript
await addMemories(messages, { user_id: "borat", umeApiKey: "m0-xxx", org_id: "org_xx", project_id: "proj_xx" });
await retrieveMemories(prompt, { user_id: "borat", umeApiKey: "m0-xxx", org_id: "org_xx", project_id: "proj_xx" });
await getMemories(prompt, { user_id: "borat", umeApiKey: "m0-xxx", org_id: "org_xx", project_id: "proj_xx" });
```

### Note:

`retrieveMemories` enriches the prompt with relevant memories from your profile, while `getMemories` returns the memories in array format which can be used for further processing.

## Usage Examples

### 1. Basic Text Generation with Memory Context

```typescript
import { generateText } from "ai";
import { createUME } from "@ume/vercel-ai-provider";

const ume = createUME();

const { text } = await generateText({
  model: ume("gpt-4-turbo", {
    user_id: "borat",
  }),
  prompt: "Suggest me a good car to buy!",
});
```

### 2. Combining OpenAI Provider with Memory Utils

```typescript
import { generateText } from "ai";
import { openai } from "@ai-sdk/openai";
import { retrieveMemories } from "@ume/vercel-ai-provider";

const prompt = "Suggest me a good car to buy.";
const memories = await retrieveMemories(prompt, { user_id: "borat" });

const { text } = await generateText({
  model: openai("gpt-4-turbo"),
  prompt: prompt,
  system: memories,
});
```

### 3. Structured Message Format with Memory

```typescript
import { generateText } from "ai";
import { createUME } from "@ume/vercel-ai-provider";

const ume = createUME();

const { text } = await generateText({
  model: ume("gpt-4-turbo", {
    user_id: "borat",
  }),
  messages: [
    {
      role: "user",
      content: [
        { type: "text", text: "Suggest me a good car to buy." },
        { type: "text", text: "Why is it better than the other cars for me?" },
        { type: "text", text: "Give options for every price range." },
      ],
    },
  ],
});
```

### 4. Advanced Memory Integration with OpenAI

```typescript
import { generateText, LanguageModelV1Prompt } from "ai";
import { openai } from "@ai-sdk/openai";
import { retrieveMemories } from "@ume/vercel-ai-provider";

// New format using system parameter for memory context
const messages: LanguageModelV1Prompt = [
  {
    role: "user",
    content: [
      { type: "text", text: "Suggest me a good car to buy." },
      { type: "text", text: "Why is it better than the other cars for me?" },
      { type: "text", text: "Give options for every price range." },
    ],
  },
];

const memories = await retrieveMemories(messages, { user_id: "borat" });

const { text } = await generateText({
  model: openai("gpt-4-turbo"),
  messages: messages,
  system: memories,
});
```

### 5. Streaming Responses with Memory Context

```typescript
import { streamText } from "ai";
import { createUME } from "@ume/vercel-ai-provider";

const ume = createUME();

const { textStream } = await streamText({
  model: ume("gpt-4-turbo", {
    user_id: "borat",
  }),
  prompt:
    "Suggest me a good car to buy! Why is it better than the other cars for me? Give options for every price range.",
});

for await (const textPart of textStream) {
  process.stdout.write(textPart);
}
```

## Core Functions

- `createUME()`: Initializes a new ume provider instance with optional configuration
- `retrieveMemories()`: Enriches prompts with relevant memories
- `addMemories()`: Add memories to your profile
- `getMemories()`: Get memories from your profile in array format

## Configuration Options

```typescript
const ume = createUME({
  config: {
    ...
    // Additional model-specific configuration options can be added here.
  },
});
```

## Best Practices

1. **User Identification**: Always provide a unique `user_id` identifier for consistent memory retrieval
2. **Context Management**: Use appropriate context window sizes to balance performance and memory
3. **Error Handling**: Implement proper error handling for memory operations
4. **Memory Cleanup**: Regularly clean up unused memory contexts to optimize performance

We also have support for `agent_id`, `app_id`, and `run_id`. Refer [Docs](https://docs.ume.ai/api-reference/memory/add-memories).

## Notes

- Requires proper API key configuration for underlying providers (e.g., OpenAI)
- Memory features depend on proper user identification via `user_id`
- Supports both streaming and non-streaming responses
- Compatible with all Vercel AI SDK features and patterns
