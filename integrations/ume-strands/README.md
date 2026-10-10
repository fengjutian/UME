<div align="center">
  <h1>ume-strands</h1>
  <h3>Persistent long-term memory for Strands Agents, backed by UME</h3>
  <p>
    A community <a href="https://strandsagents.com/">Strands Agents</a> integration that plugs
    <a href="https://ume.ai">UME</a> in as a first-class <code>MemoryStore</code>.
  </p>
</div>

---

`ume-strands` gives [Strands](https://github.com/strands-agents/sdk-python) agents durable memory
that survives across sessions, backed by [UME](https://ume.ai). Where the
`ume_memory` tool is called explicitly by the model, `UMEMemoryStore` plugs into the **agent loop**
directly: the manager recalls context and injects it automatically, and writes new memories, either
verbatim or by extracting facts from the conversation.

- **Automatic recall + injection** — relevant memories are searched and prepended to the prompt every turn, no tool call required.
- **Server-side extraction** — raw conversation turns are handed to UME, which distills and de-duplicates facts on its own pipeline (no extra client-side model call).
- **Hosted or self-hosted** — the managed [UME Platform](https://app.ume.ai) by default, or your own UME OSS backend via a config dict.

## Install

```bash
pip install ume-strands
```

## Usage

```python
from strands import Agent
from strands.memory import MemoryManager
from ume_strands import UMEMemoryStore

# Recall + write, distilling facts from the conversation via UME's server-side extraction.
store = UMEMemoryStore(user_id="alex", writable=True, extraction=True)
agent = Agent(memory_manager=MemoryManager(stores=[store]))

# The agent now recalls from and writes to UME without any explicit tool call.
agent("Remember that I prefer dark-mode dashboards and only drink oat milk.")
agent("How do I like my dashboards?")  # recalls the stored preference
```

Set `UME_API_KEY` for the hosted platform (get one at [app.ume.ai](https://app.ume.ai)), or pass
`api_key=...`. For a self-hosted UME OSS backend, pass a `config=...` dict instead.

## How it works

`UMEMemoryStore` implements all three `MemoryStore` hooks:

| Method | Maps to | When it runs |
|---|---|---|
| `search(query)` | `ume.search(query, filters={...})` | Every turn, to recall and inject context |
| `add(content)` | `ume.add(content, infer=False)` | The `add_memory` tool / a client-side extractor — stores a fact verbatim |
| `add_messages(messages)` | `ume.add(rendered_turns, infer=True)` | Extraction — renders conversation turns to text, then hands them to UME's **server-side** extraction |

Because `add_messages` is implemented, enabling `extraction` routes conversation turns straight to UME's own
extraction pipeline. A store that only implemented `add` would instead need a client-side `ModelExtractor`
(an extra model call) to distill facts first.

### Configuration

| Argument | Default | Description |
|---|---|---|
| `user_id` / `agent_id` / `run_id` / `app_id` | _(at least one required)_ | UME entity scope that owns the memories |
| `name` | `"ume"` | Store identifier, used to target it from memory tools |
| `writable` | `True` | Whether the manager may write to the store |
| `extraction` | `None` | Automatic extraction (`bool` or `ExtractionConfig`) |
| `max_search_results` | `None` | Default result cap per search (falls back to 5) |
| `metadata` | `None` | Default metadata merged into every write |
| `api_key` / `host` | env | UME platform key / base URL (`api_key` defaults to `$UME_API_KEY`) |
| `config` | `None` | UME OSS config dict for a self-hosted backend |

## The explicit tool

For the model-called tool (`store` / `retrieve` / `get` / `delete`), use the
[`ume_memory`](https://github.com/strands-agents/tools) tool from `strands-agents-tools`. The store and
the tool share one UME backend and namespace.

## Telemetry

The store sends usage events (store configuration, operation, duration, result
counts, coarse failure kind) over the UME SDK's existing telemetry client,
tagged `source="STRANDS"`. These are **not anonymous**: when an API key is
configured they are sent under your UME account email, the same way the SDK
attributes its own. Queries, memory text, message content, entity ids, and
metadata are never sent. Turn it off with `UME_TELEMETRY=false`.

## Development

The package lives under [`python/`](python/) (monorepo-style layout matching the
[Strands extension-template](https://github.com/strands-agents/extension-template)).

```bash
cd python
pip install hatch
hatch run test        # pytest (no live server required — mocked client)
hatch run prepare     # format + lint + typecheck + test
```

## License

[Apache-2.0](LICENSE). UME is a trademark of its respective owner. Strands Agents is a project of its respective authors.
