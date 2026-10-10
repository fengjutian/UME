"""A fake memory engine for the P2 tests.

Real extraction needs a live LLM, so the adapter is swapped for this in every
memory test. It records the scope it was called with, which is how the tests
prove the workspace filter travels *into* the engine call instead of being
applied to the results afterwards.
"""

import uuid

from ume_app.engine.memory_adapter import EngineHistoryItem, EngineMemory


class FakeEngine:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.fail_on: set[str] = set()
        self.remembered: dict[str, EngineMemory] = {}
        self._counter = 0
        self.search_result: list[EngineMemory] | None = None

    def _next_id(self) -> str:
        self._counter += 1
        return f"eng-{self._counter}"

    def _maybe_fail(self, op: str) -> None:
        if op in self.fail_on:
            raise RuntimeError(f"fake engine failure during {op} with a very long message " * 40)

    def add(self, messages, *, scope, metadata=None, infer=True):
        self.calls.append(("add", {"scope": scope, "metadata": metadata, "infer": infer}))
        self._maybe_fail("add")
        memory_id = self._next_id()
        text = " ".join(str(m.get("content", "")) for m in messages)
        memory = EngineMemory(
            id=memory_id,
            text=text,
            metadata={**(metadata or {}), "ume_workspace_id": str(scope.workspace_id)},
        )
        self.remembered[memory_id] = memory
        return [memory]

    def search(self, query, *, scope, filters=None, limit=10):
        self.calls.append(("search", {"query": query, "scope": scope, "filters": filters, "limit": limit}))
        self._maybe_fail("search")
        if self.search_result is not None:
            return self.search_result[:limit]
        return [m for m in self.remembered.values() if query.lower() in m.text.lower()][:limit]

    def get(self, memory_id, *, scope):
        self.calls.append(("get", {"memory_id": memory_id, "scope": scope}))
        self._maybe_fail("get")
        return self.remembered.get(memory_id) or EngineMemory(id=memory_id, text="")

    def update(self, memory_id, text, *, scope, metadata=None):
        self.calls.append(("update", {"memory_id": memory_id, "text": text, "scope": scope}))
        self._maybe_fail("update")
        updated = EngineMemory(id=memory_id, text=text, metadata={"ume_workspace_id": str(scope.workspace_id)})
        self.remembered[memory_id] = updated
        return updated

    def delete(self, memory_id, *, scope):
        self.calls.append(("delete", {"memory_id": memory_id, "scope": scope}))
        self._maybe_fail("delete")
        self.remembered.pop(memory_id, None)

    def history(self, memory_id, *, scope):
        self.calls.append(("history", {"memory_id": memory_id, "scope": scope}))
        return [EngineHistoryItem(memory_id=memory_id, text="old", event="UPDATE")]

    # -- assertions helpers -------------------------------------------------
    def scopes_for(self, op: str):
        return [payload["scope"] for name, payload in self.calls if name == op]

    def calls_named(self, op: str):
        return [payload for name, payload in self.calls if name == op]


def seed_engine_memory(engine: FakeEngine, text: str, workspace_id: uuid.UUID) -> str:
    """Put a memory straight into the fake engine, bypassing the service."""
    memory_id = f"eng-{engine._counter + 1}"
    engine._counter += 1
    engine.remembered[memory_id] = EngineMemory(
        id=memory_id, text=text, metadata={"ume_workspace_id": str(workspace_id)}
    )
    return memory_id
