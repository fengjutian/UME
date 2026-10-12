"""Memory engine adapter tests.

The adapter is the only place UME metadata reaches the SDK, so these assert the
mapping itself rather than the service behaviour built on top of it.
"""

import uuid

import pytest
from ume_app.domain.errors import NotFoundError
from ume_app.engine.memory_adapter import (
    EngineScope,
    SdkMemoryAdapter,
    _iter_results,
    _normalise_memory,
)


class TestEngineScope:
    def test_metadata_carries_the_workspace_id(self):
        scope = EngineScope(workspace_id=uuid.uuid4())
        assert scope.as_metadata()["ume_workspace_id"] == str(scope.workspace_id)

    def test_metadata_carries_every_project_id(self):
        ids = (uuid.uuid4(), uuid.uuid4())
        scope = EngineScope(workspace_id=uuid.uuid4(), project_ids=ids)
        assert scope.as_metadata()["ume_project_ids"] == [str(pid) for pid in ids]

    def test_memory_record_id_is_omitted_when_unset(self):
        assert "ume_memory_record_id" not in EngineScope(workspace_id=uuid.uuid4()).as_metadata()

    def test_memory_record_id_is_included_when_set(self):
        record_id = uuid.uuid4()
        scope = EngineScope(workspace_id=uuid.uuid4(), memory_record_id=record_id)
        assert scope.as_metadata()["ume_memory_record_id"] == str(record_id)

    def test_project_ids_default_to_an_empty_list_not_none(self):
        """A `None` would be dropped by the SDK's metadata filter."""
        assert EngineScope(workspace_id=uuid.uuid4()).as_metadata()["ume_project_ids"] == []


class TestNormalisation:
    @pytest.mark.parametrize(
        "raw",
        [
            {"id": "m1", "memory": "hello"},
            {"id": "m1", "data": "hello"},
            {"id": "m1", "payload": {"data": "hello"}},
        ],
    )
    def test_known_shapes_all_yield_the_same_memory(self, raw):
        assert _normalise_memory(raw).text == "hello"

    def test_memory_id_is_always_a_string(self):
        assert _normalise_memory({"id": 42, "memory": "x"}).id == "42"

    def test_missing_text_becomes_empty_not_none(self):
        assert _normalise_memory({"id": "m1"}).text == ""

    def test_a_none_result_is_a_not_found(self):
        with pytest.raises(NotFoundError):
            _normalise_memory(None)

    def test_metadata_survives_a_payload_shape(self):
        raw = {"id": "m1", "payload": {"data": "hello", "metadata": {"tag": "x"}}}
        assert _normalise_memory(raw).metadata == {"tag": "x"}


class TestResultUnwrapping:
    def test_results_key_is_unwrapped(self):
        assert _iter_results({"results": [1, 2]}) == [1, 2]

    def test_a_bare_list_is_passed_through(self):
        assert _iter_results([1, 2]) == [1, 2]

    def test_a_nested_list_is_flattened(self):
        assert _iter_results({"results": [[1, 2]]}) == [1, 2]

    def test_none_becomes_an_empty_list(self):
        assert _iter_results(None) == []

    def test_an_empty_results_key_is_an_empty_list(self):
        assert _iter_results({"results": []}) == []


class FakeSdk:
    def __init__(self):
        self.kwargs = None

    def add(self, **kwargs):
        self.kwargs = kwargs
        return {"results": [{"id": "eng-1", "memory": "hello"}]}

    def search(self, **kwargs):
        self.kwargs = kwargs
        return [{"id": "eng-1", "memory": "hello", "score": 0.7}]

    def get(self, memory_id):
        workspace = self.kwargs["filters"]["ume_workspace_id"] if self.kwargs and self.kwargs.get("filters") else None
        return {"id": memory_id, "memory": "hello", "metadata": {"ume_workspace_id": workspace}}

    def update(self, **kwargs):
        self.kwargs = kwargs
        return {"id": kwargs["memory_id"], "memory": kwargs["data"]}

    def delete(self, **kwargs):
        self.kwargs = kwargs

    def history(self, **kwargs):
        self.kwargs = kwargs
        return [{"id": kwargs["memory_id"], "new_memory": "old", "event": "UPDATE"}]


ENTITY_ID_KEYS = ("user_id", "agent_id", "run_id")


class GuardedSdk(FakeSdk):
    """A fake that enforces the SDK's own precondition.

    `ume.Memory.add` and `ume.Memory.search` both refuse to run without at least
    one of user_id / agent_id / run_id — `add` raises
    `ValidationError("At least one of 'user_id', 'agent_id', or 'run_id' must be
    provided.")`, `search` raises `ValueError("filters must contain at least one
    of: user_id, agent_id, run_id")`. `FakeSdk` above accepted anything, which is
    how 348 passing tests coexisted with every real write and every real search
    returning 500.

    Reproducing the guard here is the point: a fake that is more permissive than
    the thing it stands in for cannot fail on the bug it was written to catch.
    """

    def __init__(self):
        super().__init__()
        self.seen_filters = {}
        self.entity_ids_seen = []

    @staticmethod
    def _require_entity_id(filters):
        if not any(filters.get(key) for key in ENTITY_ID_KEYS):
            raise ValueError("filters must contain at least one of: user_id, agent_id, run_id")

    def add(self, **kwargs):
        # `add` takes the entity ids as keyword arguments, not inside metadata.
        provided = {key: kwargs.get(key) for key in ENTITY_ID_KEYS}
        if not any(provided.values()):
            raise ValueError("At least one of 'user_id', 'agent_id', or 'run_id' must be provided.")
        self.entity_ids_seen.append(provided)
        return super().add(**kwargs)

    def search(self, **kwargs):
        filters = kwargs.get("filters") or {}
        self.seen_filters = filters
        self._require_entity_id(filters)
        self.entity_ids_seen.append({key: filters.get(key) for key in ENTITY_ID_KEYS})
        return super().search(**kwargs)


class TestSdkEntityIdContract:
    """The adapter is UME's only boundary with the SDK, so it owns this mapping."""

    def test_add_passes_an_entity_id_the_sdk_accepts(self):
        sdk = GuardedSdk()
        adapter = SdkMemoryAdapter(lambda: sdk)
        adapter.add(
            [{"role": "user", "content": "hi"}],
            scope=EngineScope(workspace_id=uuid.uuid4()),
        )

    def test_search_passes_an_entity_id_the_sdk_accepts(self):
        sdk = GuardedSdk()
        adapter = SdkMemoryAdapter(lambda: sdk)
        adapter.search("query", scope=EngineScope(workspace_id=uuid.uuid4()))

    def test_the_entity_id_is_derived_from_the_workspace(self):
        """Two workspaces must not be able to read each other's engine memories."""
        sdk = GuardedSdk()
        adapter = SdkMemoryAdapter(lambda: sdk)
        first = EngineScope(workspace_id=uuid.uuid4())
        second = EngineScope(workspace_id=uuid.uuid4())

        adapter.search("query", scope=first)
        adapter.search("query", scope=second)

        assert [ids[ENTITY_ID_KEYS[0]] for ids in sdk.entity_ids_seen] == [
            first.as_entity_id()[ENTITY_ID_KEYS[0]],
            second.as_entity_id()[ENTITY_ID_KEYS[0]],
        ]

    def test_a_caller_cannot_forge_the_entity_id(self):
        """The scope owns the tenant id; caller filters may not override it."""
        sdk = GuardedSdk()
        adapter = SdkMemoryAdapter(lambda: sdk)
        scope = EngineScope(workspace_id=uuid.uuid4())

        adapter.search("query", scope=scope, filters={ENTITY_ID_KEYS[0]: "someone-elses"})

        assert sdk.seen_filters[ENTITY_ID_KEYS[0]] == str(scope.workspace_id)

    def test_the_workspace_metadata_is_still_forwarded(self):
        """The entity id is an addition, not a replacement for the UME metadata."""
        sdk = GuardedSdk()
        adapter = SdkMemoryAdapter(lambda: sdk)
        scope = EngineScope(workspace_id=uuid.uuid4(), project_ids=(uuid.uuid4(),))

        adapter.search("query", scope=scope)

        assert sdk.seen_filters["ume_workspace_id"] == str(scope.workspace_id)
        assert sdk.seen_filters["ume_project_ids"] == [str(pid) for pid in scope.project_ids]


class TestSdkAdapter:
    def test_add_forwards_the_scope_as_metadata(self):
        sdk = FakeSdk()
        adapter = SdkMemoryAdapter(lambda: sdk)
        scope = EngineScope(workspace_id=uuid.uuid4(), project_ids=(uuid.uuid4(),))
        adapter.add([{"role": "user", "content": "hi"}], scope=scope)
        assert sdk.kwargs["metadata"]["ume_workspace_id"] == str(scope.workspace_id)

    def test_search_puts_the_scope_in_the_filters(self):
        """Post-filtering the results would let another tenant rank first."""
        sdk = FakeSdk()
        adapter = SdkMemoryAdapter(lambda: sdk)
        scope = EngineScope(workspace_id=uuid.uuid4())
        adapter.search("query", scope=scope)
        assert sdk.kwargs["filters"]["ume_workspace_id"] == str(scope.workspace_id)

    def test_search_merges_caller_filters_with_the_scope(self):
        sdk = FakeSdk()
        adapter = SdkMemoryAdapter(lambda: sdk)
        scope = EngineScope(workspace_id=uuid.uuid4())
        adapter.search("query", scope=scope, filters={"memory_type": "semantic"})
        assert sdk.kwargs["filters"]["memory_type"] == "semantic"
        assert sdk.kwargs["filters"]["ume_workspace_id"] == str(scope.workspace_id)

    def test_a_caller_cannot_override_the_tenant_id(self):
        """Contract change: the workspace now *is* the SDK tenant id.

        The previous version merged a caller-supplied `user_id` and asserted
        `"alice"` survived. `user_id` is now the key the engine isolates on, so a
        caller that could set it would point the search at a tenant other than
        the one membership was resolved for — exactly the "another tenant's
        candidates influence the ranking" failure the surrounding comment warns
        about. No production caller passes `filters` today
        (`services/memories.py:499` is the only one, without it), so nothing that
        ships depends on the old behaviour.
        """
        sdk = FakeSdk()
        adapter = SdkMemoryAdapter(lambda: sdk)
        scope = EngineScope(workspace_id=uuid.uuid4())
        adapter.search("query", scope=scope, filters={"user_id": "alice"})
        assert sdk.kwargs["filters"]["user_id"] == str(scope.workspace_id)

    def test_a_caller_cannot_forge_the_workspace_filter(self):
        """A caller-supplied `ume_workspace_id` must be overwritten, not merged."""
        sdk = FakeSdk()
        adapter = SdkMemoryAdapter(lambda: sdk)
        scope = EngineScope(workspace_id=uuid.uuid4())
        adapter.search("query", scope=scope, filters={"ume_workspace_id": "somebody-elses"})
        assert sdk.kwargs["filters"]["ume_workspace_id"] == str(scope.workspace_id)

    def test_search_passes_the_score_through(self):
        sdk = FakeSdk()
        adapter = SdkMemoryAdapter(lambda: sdk)
        hits = adapter.search("query", scope=EngineScope(workspace_id=uuid.uuid4()))
        assert hits[0].score == 0.7

    def test_history_is_normalised(self):
        sdk = FakeSdk()
        adapter = SdkMemoryAdapter(lambda: sdk)
        items = adapter.history("eng-1", scope=EngineScope(workspace_id=uuid.uuid4()))
        assert items[0].text == "old"
        assert items[0].event == "UPDATE"
