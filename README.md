# UME — Unified Memory Engine

UME is a unified, persistent memory platform for AI assistants and agents. It is built on the UME memory engine and keeps the upstream SDK, CLI, and API identifiers compatible while UME-specific services and user interfaces are developed independently.

> Compatibility note: existing technical identifiers such as the `ume` package, `ume` imports and CLI commands remain unchanged for now. In this repository, **UME** refers to the product; **UME** refers to the upstream memory engine or a compatibility interface.

<p align="center" style="display: flex; justify-content: center; gap: 20px; align-items: center;">
  <a href="https://trendshift.io/repositories/11194" target="blank">
    <img src="https://trendshift.io/api/badge/repositories/11194" alt="ume%2Fume | Trendshift" width="250" height="55"/>
  </a>
</p>

<p align="center">
  <a href="https://ume.ai">Learn more</a>
  ·
  <a href="https://ume.dev/DiG">Join Discord</a>
  ·
  <a href="https://ume.dev/demo">Demo</a>
</p>

<p align="center">
  <a href="https://ume.dev/DiG">
    <img src="https://img.shields.io/badge/Discord-%235865F2.svg?&logo=discord&logoColor=white" alt="UME community Discord">
  </a>
  <a href="https://pepy.tech/project/ume">
    <img src="https://img.shields.io/pypi/dm/ume" alt="UME engine PyPI downloads">
  </a>
  <a href="https://github.com/fengjutian/UME">
    <img src="https://img.shields.io/github/commit-activity/m/ume/ume?style=flat-square" alt="GitHub commit activity">
  </a>
  <a href="https://pypi.org/project/ume" target="blank">
    <img src="https://img.shields.io/pypi/v/ume?color=%2334D058&label=pypi%20package" alt="Package version">
  </a>
  <a href="https://www.npmjs.com/package/ume" target="blank">
    <img src="https://img.shields.io/npm/v/ume" alt="Npm package">
  </a>
  <a href="https://www.ycombinator.com/companies/ume">
    <img src="https://img.shields.io/badge/Y%20Combinator-S24-orange?style=flat-square" alt="Y Combinator S24">
  </a>
</p>

<p align="center">
  <a href="https://ume.ai/research"><strong>📄 Benchmarking the underlying UME memory algorithm →</strong></a>
</p>

## New Memory Algorithm (April 2026)

| Benchmark | Old | New  | Tokens  | Latency p50  |
| --- | --- | --- | --- | --- |
| **LoCoMo** | 71.4 | **92.5** | 7.0K  | 0.88s  |
| **LongMemEval** | 67.8 | **94.4** | 6.8K  | 1.09s  |
| **BEAM (1M)** | — | **64.1** | 6.7K  | 1.00s  |
| **BEAM (10M)** | — | **48.6** | 6.9K  | 1.05s  |

These upstream UME benchmarks run on the same production-representative model stack. Single-pass retrieval (one call, no agentic loops) uses a top_200 retrieval budget. Scores reflect UME's managed platform, which includes proprietary optimizations not available in the open-source SDK; UME users of the open-source engine should expect directionally similar gains but not identical numbers.

**What changed:**
- **Single-pass ADD-only extraction** -- one LLM call, no UPDATE/DELETE. Memories accumulate; nothing is overwritten.
- **Agent-generated facts are first-class** -- when an agent confirms an action, that information is now stored with equal weight.
- **Entity linking** -- entities are extracted, embedded, and linked across memories for retrieval boosting.
- **Multi-signal retrieval** -- semantic, BM25 keyword, and entity matching scored in parallel and fused.
- **Temporal Reasoning** -- time-aware retrieval that ranks the right dated instance for queries about current state, past events, and upcoming plans.

See the [migration guide](https://docs.ume.ai/migration/oss-v2-to-v3) for upgrade instructions. The [evaluation framework](https://github.com/ume/memory-benchmarks) is open-sourced so anyone can reproduce the numbers.

## Research Highlights
- **92.5 on LoCoMo** -- +21 points over the previous algorithm
- **94.4 on LongMemEval** -- +27 points, with 98.2 on assistant memory recall
- **64.1 on BEAM (1M)** -- production-scale memory evaluation at 1M tokens
- [Read the full paper](https://ume.ai/research)

# Introduction

UME enhances AI assistants and agents with a unified memory layer for persistent, personalized interactions. It preserves UME as the underlying memory extraction and retrieval engine, then extends it with conversation archiving, source tracing, relationship views, connector management, and workspace-level authorization.

### Key Features & Use Cases

**Core Capabilities:**
- **Multi-Level Memory**: Seamlessly retains User, Session, and Agent state with adaptive personalization
- **Developer-Friendly**: Intuitive API, cross-platform SDKs, and a fully managed service option

**Applications:**
- **AI Assistants**: Consistent, context-rich conversations
- **Customer Support**: Recall past tickets and user history for tailored help
- **Healthcare**: Track patient preferences and history for personalized care
- **Productivity & Gaming**: Adaptive workflows and environments based on user behavior

## 🚀 Quickstart Guide <a name="quickstart"></a>

### Sign up as an agent

During the compatibility phase, AI agents use the existing UME-compatible API key and CLI flow. Four commands work end-to-end:

```bash
# 1. Install
npm install -g @ume/cli      # or: pip install ume-cli

# 2. Sign up as an agent (replace `claude-code` with your name)
ume init --agent --agent-caller claude-code

# 3. Add a memory
ume add "I am using ume"

# 4. Search
ume search "am I using ume"
```

The human owner can claim the account later with `ume init --email <their-email>` — same key, memories preserved. Full guide: [Sign up as an agent](https://docs.ume.ai/platform/agent-signup).

| | Library | Self-Hosted Server | Cloud Platform |
|---|---------|-------------------|----------------|
| **Best for** | Testing, prototyping | Teams running on their own infrastructure | Zero-ops production use |
| **Setup** | `pip install ume` | `docker compose up` | Sign up at [app.ume.ai](https://app.ume.ai?utm_source=oss&utm_medium=readme) |
| **Dashboard** | -- | [Yes](https://docs.ume.ai/open-source/setup) | Yes |
| **Auth & API Keys** | -- | Yes | Yes |
| **Advanced Features** | -- | Teasers | All included |

Just testing? Use the library. Building for a team? Self-hosted. Want zero ops? Cloud.

### Library (pip / npm)

```bash
pip install ume
```

For enhanced hybrid search with BM25 keyword matching and entity extraction, install with NLP support:

```bash
pip install ume[nlp]
python -m spacy download en_core_web_sm
```

Install sdk via npm:

```bash
npm install ume
```

### Self-Hosted Server

> **Note:** Self-hosted auth is on by default. Upgrading from a pre-auth build? Set `ADMIN_API_KEY`, register an admin through the wizard, or `AUTH_DISABLED=true` for local dev only. See [upgrade notes](https://docs.ume.ai/open-source/setup#upgrade-notes).

```bash
# Recommended: one command — start the stack, create an admin, issue the first API key.
cd server && make bootstrap

# Manual: start the stack and finish setup via the browser wizard.
cd server && docker compose up -d    # http://localhost:3000
```

See the [self-hosted docs](https://docs.ume.ai/open-source/overview) for configuration.

### Cloud Platform

1. Sign up on the [UME Platform](https://app.ume.ai?utm_source=oss&utm_medium=readme), currently used as UME's compatible hosted memory backend
2. Embed the memory layer via SDK or API keys
3. Using hosted Qdrant vectors? See the [Platform migration guide](https://docs.ume.ai/migration/oss-to-platform) to import them into UME Platform.

### CLI

Manage memories from your terminal:

```bash
npm install -g @ume/cli   # or: pip install ume-cli

ume init
ume add "Prefers dark mode and vim keybindings" --user-id alice
ume search "What does Alice prefer?" --user-id alice
```

See the [CLI documentation](https://docs.ume.ai/platform/cli) for the full command reference.

### Agent Skills

Teach your AI coding assistant (Claude Code, Codex, Cursor, Windsurf, OpenCode, OpenClaw, and any tool that supports the skills standard) how to build with UME through the compatible UME skills. Two categories:

**Reference skills — always on** (SDK knowledge loaded into the assistant's context):

```bash
npx skills add https://github.com/fengjutian/UME --skill ume
npx skills add https://github.com/fengjutian/UME --skill ume-cli
npx skills add https://github.com/fengjutian/UME --skill ume-vercel-ai-sdk
```

**Pipeline skills — run on demand** (execute an end-to-end workflow in an existing repo):

```bash
npx skills add https://github.com/fengjutian/UME --skill ume-integrate
npx skills add https://github.com/fengjutian/UME --skill ume-test-integration
npx skills add https://github.com/fengjutian/UME --skill ume-oss-to-platform
```

Use `/ume-integrate` to wire the UME-compatible engine into an existing repo via a test-first pipeline, then `/ume-test-integration` to verify it. Use `/ume-oss-to-platform` to migrate an existing engine deployment to the hosted Platform SDK. See the [skills catalog](./skills/) or the upstream [Vibecoding guide](https://docs.ume.ai/vibecoding) for the full picture.

### Basic Usage

UME's memory engine requires an LLM to function, with `gpt-5-mini` from OpenAI as the default. It supports multiple LLM providers; see the upstream [Supported LLMs documentation](https://docs.ume.ai/components/llms/overview).

UME uses the UME engine's default `text-embedding-3-small` embedding model. For best results with hybrid search (semantic + keyword + entity boosting), use at least [Qwen 600M](https://huggingface.co/Alibaba-NLP/gte-Qwen2-1.5B-instruct) or a comparable embedding model. See the upstream [Supported Embeddings](https://docs.ume.ai/components/embedders/overview) for configuration details.

First step is to instantiate the memory:

```python
from openai import OpenAI
from ume import Memory

openai_client = OpenAI()
memory = Memory()

def chat_with_memories(message: str, user_id: str = "default_user") -> str:
    # Retrieve relevant memories
    relevant_memories = memory.search(query=message, filters={"user_id": user_id}, top_k=3)
    memories_str = "\n".join(f"- {entry['memory']}" for entry in relevant_memories["results"])

    # Generate Assistant response
    system_prompt = f"You are a helpful AI. Answer the question based on query and memories.\nUser Memories:\n{memories_str}"
    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": message}]
    response = openai_client.chat.completions.create(model="gpt-5-mini", messages=messages)
    assistant_response = response.choices[0].message.content

    # Create new memories from the conversation
    messages.append({"role": "assistant", "content": assistant_response})
    memory.add(messages, user_id=user_id)

    return assistant_response

def main():
    print("Chat with AI (type 'exit' to quit)")
    while True:
        user_input = input("You: ").strip()
        if user_input.lower() == 'exit':
            print("Goodbye!")
            break
        print(f"AI: {chat_with_memories(user_input)}")

if __name__ == "__main__":
    main()
```

For detailed integration steps, see the [Quickstart](https://docs.ume.ai/quickstart) and [API Reference](https://docs.ume.ai/api-reference).

## 🔗 Integrations & Demos

- **ChatGPT with Memory**: Personalized chat powered by the UME-compatible engine ([upstream demo](https://ume.dev/demo))
- **Browser Extension**: Store memories across ChatGPT, Perplexity, and Claude ([Chrome Extension](https://chromewebstore.google.com/detail/onihkkbipkfeijkadecaafbgagkhglop?utm_source=item-share-cb))
- **Langgraph Support**: Build a customer bot with Langgraph + UME ([Guide](https://docs.ume.ai/integrations/langgraph))
- **CrewAI Integration**: Tailor CrewAI outputs with UME ([Example](https://docs.ume.ai/integrations/crewai))

## 📚 Documentation & Support

- Full docs: https://docs.ume.ai
- Community: [Discord](https://ume.dev/DiG) · [X (formerly Twitter)](https://x.com/ume)
- Contact: founders@ume.ai

## Citation

We now have a paper you can cite:

```bibtex
@article{ume,
  title={UME: Building Production-Ready AI Agents with Scalable Long-Term Memory},
  author={Chhikara, Prateek and Khant, Dev and Aryan, Saket and Singh, Taranjeet and Yadav, Deshraj},
  journal={arXiv preprint arXiv:2504.19413},
  year={2025}
}
```

## ⚖️ License

Apache 2.0 — see the [LICENSE](https://github.com/fengjutian/UME/blob/main/LICENSE) file for details.
