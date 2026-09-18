# WP4.4 Triage Dossier — backend/services/redis_json.py

- **Run**: meta `mutants/backend/services/redis_json.py.meta` — 594 mutants checked, **108 survived**.
- **Diff source**: `uv run mutmut show <key>` (all 108 succeeded, ~0.8s each).
- **Sole covering test file**: `backend/tests/unit/services/test_redis_json.py` (all 108 mutants are executed by tests in this one file).
- **Root cause of most survivals**: tests mock `_client.execute_command` / `get` / `setex` / `scan_iter` as permissive `AsyncMock`s that accept any arguments and return canned values _independent of the key/path_, then assert only on return values. Any mutation of command names, keys, JSON paths or payloads is invisible. `pytest.raises(match=...)` uses `re.search`, so `XX...XX`-wrapped messages still substring-match.
- **Production note**: `batch_metadata_ttl` does not exist on real `Settings` (grep: only in redis_json.py), so the `hasattr` else-branch is the live path; unit tests patch `get_settings` with a `MagicMock`, hiding this.

Classification totals: **TEST-GAP 90, LOW-VALUE 14, EQUIVALENT 4** (sum 108).

## Cluster table

| #   | Function                    | Pattern                                                                                                                                                                                                                  | Count | Keys (all)                | Class      |
| --- | --------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----- | ------------------------- | ---------- |
| C1  | get_batch_metadata_service  | singleton guard `is None`→`is not None`; whole constructor replaced by `= None`                                                                                                                                          | 2     | 1, 3                      | TEST-GAP   |
| C2  | get_batch_metadata_service  | settings→TTL wiring broken (`settings=None`, `default_ttl=None`, kwarg dropped, `and False`/`or True` on `hasattr`, attr name cased/X-ed)                                                                                | 8     | 2, 5, 7, 8, 9, 10, 14, 15 | TEST-GAP   |
| C3  | get_batch_metadata_service  | constructor `redis_client=redis_client` → `redis_client=None`                                                                                                                                                            | 1     | 4                         | TEST-GAP   |
| C4  | append_detection_id         | `JSON.ARRAPPEND` call args mutated (cmd→None/removed/`XX..`/lowercase; key→None; `$.detection_ids`→None/`XX..`/upper; `str(detection_id)`→None/`str(None)`/removed)                                                      | 13    | 8–20                      | TEST-GAP   |
| C5  | append_detection_id         | `JSON.NUMINCRBY` call args mutated (same mutation families; `"1"`→None/`XX1XX`)                                                                                                                                          | 13    | 21–33                     | TEST-GAP   |
| C6  | append_detection_id         | `JSON.SET` last_activity call args mutated (`str(time.time())`→None/`str(None)`/removed)                                                                                                                                 | 13    | 34–46                     | TEST-GAP   |
| C7  | append_detection_id         | `JSON.GET` count-read call args mutated                                                                                                                                                                                  | 10    | 52–61                     | TEST-GAP   |
| C8  | append_detection_id         | `expire(key, self._default_ttl)` args → `expire(None,ttl)` / `expire(key,None)` / `expire(ttl)` / `expire(key,)`                                                                                                         | 4     | 47–50                     | TEST-GAP   |
| C9  | append_detection_id         | `key = self._get_key(batch_id)` → `key = None` / `_get_key(None)` (JSON path)                                                                                                                                            | 2     | 6, 7                      | TEST-GAP   |
| C10 | append_detection_id         | string-fallback path weakened: fetch under `None` key, `append(None)`, `last_activity=None`, store under `None` key, store `None` doc                                                                                    | 5     | 77, 81, 83, 84, 85        | TEST-GAP   |
| C11 | append_detection_id         | `RuntimeError("XXRedis client not connectedXX")` — pure message text; `match=` substring-search still matches                                                                                                            | 1     | 3                         | EQUIVALENT |
| C12 | get_batch_field             | `JSON.GET` call args mutated (cmd None/removed/`XX..`/lower; key→None/`_get_key(None)`; `json_path`→None/removed)                                                                                                        | 10    | 6, 7, 9–16                | TEST-GAP   |
| C13 | get_batch_field             | fallback fetches `get_batch_metadata(None)` (wrong key silently ignored)                                                                                                                                                 | 1     | 24                        | TEST-GAP   |
| C14 | get_batch_field             | fallback path split delimiter `.split(".")` → `.split(None)` / `.split("XX.XX")` — breaks _successful_ nested lookups (`$.a.b` becomes one part); only failing-nested case is tested, whose result (`None`) is identical | 2     | 28, 35                    | TEST-GAP   |
| C15 | get_batch_field             | `XX`-wrapped RuntimeError message                                                                                                                                                                                        | 1     | 3                         | EQUIVALENT |
| C16 | delete_batch_metadata       | `XX`-wrapped RuntimeError message                                                                                                                                                                                        | 1     | 3                         | EQUIVALENT |
| C17 | get_open_batches_for_camera | `scan_iter(match=f"{prefix}*", …)` → `match=None` / `match` kwarg removed — real client would scan **all** keys, not just batch metadata                                                                                 | 2     | 7, 9                      | TEST-GAP   |
| C18 | get_open_batches_for_camera | `count=100` tuning param → None / removed / 101 (server-side scan hint only; `count=None` == unspecified in redis-py)                                                                                                    | 3     | 8, 10, 11                 | LOW-VALUE  |
| C19 | get_open_batches_for_camera | decode guard `isinstance(key, bytes)` → `or True`: str keys (decode_responses client) then raise `AttributeError` per key, are silently swallowed → function returns `[]` forever; tests only yield `bytes` keys         | 1     | 14                        | TEST-GAP   |
| C20 | get_open_batches_for_camera | batch-id derivation broken: `batch_id = None`, `replace(prefix,"XXXX")`, fetch via `get_batch_metadata(None)` — permissive `get` side_effect list hides the wrong key                                                    | 3     | 15, 20, 22                | TEST-GAP   |
| C21 | get_open_batches_for_camera | `logger.debug` in the scan except-handler mutated: msg None/case/`XX`, `extra=None`, extra dict keys cased/X-ed, `str(None)`                                                                                             | 11    | 30–31, 33–41              | LOW-VALUE  |
| C22 | get_open_batches_for_camera | `XX`-wrapped RuntimeError message                                                                                                                                                                                        | 1     | 3                         | EQUIVALENT |

Sum: 2+8+1 +13+13+13+10+4+2+5+1 +10+1+2+1 +1 +2+3+1+3+11+1 = **108**.

### Why the existing tests miss these (per-cluster evidence, `backend/tests/unit/services/test_redis_json.py`)

- **C1–C3** — `TestGetBatchMetadataService::test_creates_singleton` (L685–701) only asserts `service1 is service2`; `None is None` satisfies that, so an inverted singleton guard or a constructor replaced by `None` passes. Nothing asserts the return is a `BatchMetadataService`, is wired to the client, or carries `settings.batch_metadata_ttl`. With a `MagicMock` settings stub, `hasattr` is always True, so TTL-selection flips are unobservable.
- **C4–C9** — `test_append_detection_id_with_json` (L538–553) drives `execute_command` with `side_effect=[None,None,None,"[5]"]` and asserts only `result == 5`. The value at position 4 is returned regardless of what command/key/path/payload was sent, and every mutation keeps the call count at 4. `expire` is never asserted in this test. Same for the -1/empty-list tests (L580, L1102).
- **C10** — `test_append_detection_id_fallback` (L556–577) asserts only `result == 3`; `get` uses `return_value` (key-agnostic) and the `setex` payload is never inspected — unlike `test_close_batch_fallback` (L612) which _does_ `json.loads` the stored payload, proving the pattern the append test skipped.
- **C12–C14** — `test_get_batch_field_with_json` (L412) asserts only the extracted value; `test_get_batch_field_fallback` (L432) only the extracted value; nested-path coverage exists only via _failing_ path `$.processing_metadata.nonexistent` (L788) — a successful nested fallback lookup (`$.processing_metadata.<present-key>`) is never exercised, which is exactly where `split(None)`/`split("XX.XX")` diverge (`'a.b'.split(None) == ['a.b']`, verified).
- **C17–C20** — both scan tests (L932, L971) replace `scan_iter` with a kwargs-ignoring async generator yielding only `bytes` keys, and give `get` a `side_effect` _value list_ consumed per call regardless of key — so pattern/count kwargs, str-key decoding, and batch-id→key derivation are all unobserved.
- **C11/C15/C16/C22** — `pytest.raises(match="Redis client not connected")` is `re.search`; `"XXRedis client not connectedXX"` contains the needle, so the guard itself _is_ verified and only message text changed → EQUIVALENT, leave as-is.
- **C21** — debug-log payload only; `logging.debug(None)` doesn't even raise (verified). Nobody should assert this → LOW-VALUE kill-suppression candidates if the baseline needs a score floor.

## Drafted tests (UNVERIFIED — not yet run red/green)

All go in `backend/tests/unit/services/test_redis_json.py`, following existing style (fixtures `mock_redis_client`/`metadata_service`, `@pytest.mark.asyncio`, `pytest.mark.asyncio` needs no import — already module-level import of `pytest`). Add `from types import SimpleNamespace` and `import time` is already present; add `from unittest.mock import ...` — `AsyncMock, MagicMock, patch` already imported.

**TDD procedure (same for all): apply the cluster's mutant diff → new test must FAIL (red); restore original → must PASS (green); then re-run mutmut on the cluster keys to confirm kills.**

### T1 — `test_factory_uses_settings_ttl_and_wires_client` → kills C1, C2 (except mutmut_9), C3

```python
class TestGetBatchMetadataService:
    """Tests for the service factory function."""

    # ... existing test_creates_singleton ...

    @pytest.mark.asyncio
    async def test_factory_uses_settings_ttl_and_wires_client(self, mock_redis_client):
        """Factory must construct a real service wired to the client and settings TTL."""
        import backend.services.redis_json as module

        module._batch_metadata_service = None

        try:
            with patch(
                "backend.services.redis_json.get_settings",
                autospec=True,
                return_value=SimpleNamespace(batch_metadata_ttl=1234),
            ):
                service = await get_batch_metadata_service(mock_redis_client)

            assert isinstance(service, BatchMetadataService)
            assert service._redis is mock_redis_client
            assert service._default_ttl == 1234
        finally:
            module._batch_metadata_service = None
```

Kills: 1, 3 (returns `None` → isinstance fails), 2/10/14/15 (settings attr lookup broken → 3600 ≠ 1234), 4 (`_redis` is None), 5 (`_default_ttl` None), 7 (kwarg dropped → 3600), 8 (`and False` → 3600).

### T2 — `test_factory_default_ttl_when_settings_lacks_attr` → kills C2 mutmut_9

```python
    @pytest.mark.asyncio
    async def test_factory_default_ttl_when_settings_lacks_attr(self, mock_redis_client):
        """When settings has no batch_metadata_ttl, factory falls back to the module default."""
        import backend.services.redis_json as module

        module._batch_metadata_service = None

        try:
            with patch(
                "backend.services.redis_json.get_settings",
                autospec=True,
                return_value=SimpleNamespace(),  # no batch_metadata_ttl attribute
            ):
                service = await get_batch_metadata_service(mock_redis_client)

            assert service._default_ttl == DEFAULT_BATCH_META_TTL
        finally:
            module._batch_metadata_service = None
```

Kills mutmut_9 (`or True` forces the `settings.batch_metadata_ttl` branch → `AttributeError` on the stub). Original passes (hasattr False → default). Also mirrors production reality (real Settings lacks the attr).

### T3 — `test_append_detection_id_with_json_issues_exact_command_sequence` → kills C4, C5, C6, C7, C8, C9 (51 mutants)

```python
class TestBatchMetadataServiceAppendDetectionId:
    """Tests for appending detection IDs."""

    # ... existing tests ...

    @pytest.mark.asyncio
    async def test_append_detection_id_with_json_issues_exact_command_sequence(
        self, metadata_service, mock_redis_client
    ):
        """Each RedisJSON command must carry the right command, key, path and payload."""
        metadata_service._json_available = True
        key = f"{BATCH_META_PREFIX}batch-append"
        mock_redis_client._client.execute_command = AsyncMock(
            side_effect=[
                None,  # JSON.ARRAPPEND
                None,  # JSON.NUMINCRBY
                None,  # JSON.SET last_activity
                "[5]",  # JSON.GET detection_count
            ]
        )
        mock_redis_client._client.expire = AsyncMock()

        result = await metadata_service.append_detection_id("batch-append", 42)

        assert result == 5
        calls = [entry.args for entry in mock_redis_client._client.execute_command.call_args_list]
        assert len(calls) == 4
        assert calls[0] == ("JSON.ARRAPPEND", key, "$.detection_ids", "42")
        assert calls[1] == ("JSON.NUMINCRBY", key, "$.detection_count", "1")
        assert calls[2][:3] == ("JSON.SET", key, "$.last_activity")
        assert float(calls[2][3]) == pytest.approx(time.time(), abs=60)
        assert calls[3] == ("JSON.GET", key, "$.detection_count")
        mock_redis_client._client.expire.assert_called_once_with(key, DEFAULT_BATCH_META_TTL)
```

Any command-name, key, path or payload mutation changes `calls[i]`; the `expire` assertion kills C8 (None key, None ttl, shifted/missing ttl); `key` fixes kill C9 (key would be `None` / `batch:meta:None`). `float("None")` raises, killing the `str(None)` payload mutants.

### T4 — `test_append_detection_id_fallback_stores_updated_document` → kills C10 (+ fallback half of C9)

```python
    @pytest.mark.asyncio
    async def test_append_detection_id_fallback_stores_updated_document(
        self, metadata_service, mock_redis_client
    ):
        """String fallback must read and re-store the batch under its real key, with the appended id."""
        metadata_service._json_available = False
        data = {
            "batch_id": "batch-append-fallback",
            "camera_id": "cam1",
            "status": "open",
            "detection_ids": [1, 2],
            "detection_count": 2,
            "started_at": 1700000000.0,
            "last_activity": 1700000000.0,
            "closed_at": None,
            "pipeline_start_time": None,
            "close_reason": None,
            "processing_metadata": {},
        }
        mock_redis_client._client.get = AsyncMock(return_value=json.dumps(data))
        mock_redis_client._client.setex = AsyncMock()

        result = await metadata_service.append_detection_id("batch-append-fallback", 3)

        assert result == 3
        expected_key = f"{BATCH_META_PREFIX}batch-append-fallback"
        mock_redis_client._client.get.assert_called_once_with(expected_key)
        stored_key, _ttl, payload = mock_redis_client._client.setex.call_args[0]
        assert stored_key == expected_key
        stored = json.loads(payload)
        assert stored["detection_ids"] == [1, 2, 3]
        assert stored["detection_count"] == 3
        assert stored["last_activity"] is not None
        assert stored["last_activity"] != 1700000000.0
```

Kills 77/84 (wrong fetch/store key), 81 (`detection_ids` ends in `None`), 83 (`last_activity` None), 85 (payload `"null"` → `json.loads` yields `None` → subscript TypeError). Pattern copied from `test_close_batch_fallback` L636–640.

### T5 — `test_get_batch_field_with_json_queries_batch_key_at_path` → kills C12 (10 mutants)

```python
class TestBatchMetadataServiceGetBatchField:
    """Tests for getting specific fields."""

    # ... existing tests ...

    @pytest.mark.asyncio
    async def test_get_batch_field_with_json_queries_batch_key_at_path(
        self, metadata_service, mock_redis_client
    ):
        """JSON.GET must be issued against the batch's key with the requested path."""
        metadata_service._json_available = True
        mock_redis_client._client.execute_command = AsyncMock(return_value='["closed"]')

        result = await metadata_service.get_batch_field("batch-field", "$.status")

        assert result == "closed"
        mock_redis_client._client.execute_command.assert_called_once_with(
            "JSON.GET", f"{BATCH_META_PREFIX}batch-field", "$.status"
        )
```

### T6 — `test_get_batch_field_fallback_extracts_nested_path` → kills C13, C14

```python
    @pytest.mark.asyncio
    async def test_get_batch_field_fallback_extracts_nested_path(
        self, metadata_service, mock_redis_client
    ):
        """String fallback must walk multi-segment $.a.b paths to an existing value."""
        metadata_service._json_available = False
        data = {
            "batch_id": "batch-nested-field",
            "camera_id": "cam1",
            "status": "open",
            "detection_ids": [],
            "detection_count": 0,
            "started_at": 1700000000.0,
            "last_activity": 1700000000.0,
            "closed_at": None,
            "pipeline_start_time": None,
            "close_reason": None,
            "processing_metadata": {"analyzed": True},
        }
        mock_redis_client._client.get = AsyncMock(return_value=json.dumps(data))

        result = await metadata_service.get_batch_field(
            "batch-nested-field", "$.processing_metadata.analyzed"
        )

        assert result is True
        mock_redis_client._client.get.assert_called_once_with(
            f"{BATCH_META_PREFIX}batch-nested-field"
        )
```

With `split(None)` or `split("XX.XX")` the path stays one unsplit segment (`'processing_metadata.analyzed'.split(None) == ['processing_metadata.analyzed']` — verified) → lookup misses → `None ≠ True` (red). Kills 28, 35; the key assertion kills 24 (fetches `batch:meta:None`).

### T7 — `test_get_open_batches_scans_prefixed_keys_and_fetches_by_batch_id` → kills C17, C19, C20 (+ C18 incidentally)

```python
class TestBatchMetadataServiceErrorHandling:
    """Additional tests for error handling and edge cases."""

    # ... existing tests ...

    @pytest.mark.asyncio
    async def test_get_open_batches_scans_prefixed_keys_and_fetches_by_batch_id(
        self, metadata_service, mock_redis_client
    ):
        """Scan must be prefix-bounded and fetch metadata by the id derived from each key."""
        metadata_service._json_available = False

        seen_kwargs: dict = {}

        async def gen(**kwargs):
            seen_kwargs.update(kwargs)
            yield "batch:meta:batch-a"  # str key (decode_responses client)
            yield b"batch:meta:batch-b"  # bytes key (binary client)

        scan_iter = MagicMock(side_effect=gen)
        mock_redis_client._client.scan_iter = scan_iter

        docs = {
            "batch:meta:batch-a": json.dumps(
                {
                    "batch_id": "batch-a",
                    "camera_id": "front_door",
                    "status": "open",
                }
            ),
            "batch:meta:batch-b": json.dumps(
                {
                    "batch_id": "batch-b",
                    "camera_id": "backyard",
                    "status": "open",
                }
            ),
        }

        async def fake_get(key):
            key_str = key.decode() if isinstance(key, bytes) else key
            return docs.get(key_str)

        mock_redis_client._client.get = AsyncMock(side_effect=fake_get)

        batches = await metadata_service.get_open_batches_for_camera("front_door")

        assert seen_kwargs == {"match": f"{BATCH_META_PREFIX}*", "count": 100}
        assert [b.batch_id for b in batches] == ["batch-a"]
```

- C17/C18: kwargs assertion kills 7, 9 (match gone/None) and incidentally 8, 10, 11 (count mutations).
- C19: with `or True`, the str key hits `key.decode()` → `AttributeError` → swallowed by the per-key handler → `batch-a` missing (red).
- C20: `fake_get` is key-sensitive, so a broken `batch_id` derivation (`None`, `"XXXXbatch-a"`) fetches nothing → empty list (red). This is the minimal fix to the value-list `side_effect` blind spot in the two existing scan tests.

## Kill math

| Cluster class                             | Mutants | Covered by drafts                                                                                                              |
| ----------------------------------------- | ------- | ------------------------------------------------------------------------------------------------------------------------------ |
| TEST-GAP (C1–C10, C12–C14, C17, C19, C20) | 90      | all 90 (T1–T7)                                                                                                                 |
| LOW-VALUE (C18, C21)                      | 14      | 3 incidentally via T7's kwargs assert; recommend kill-suppression pragma for C21 (11) rather than asserting debug-log payloads |
| EQUIVALENT (C11, C15, C16, C22)           | 4       | none needed — suppress or accept                                                                                               |

## Covering test file references

`backend/tests/unit/services/test_redis_json.py`:

- factory singleton test: **L685–701**
- append JSON path: **L538–553**; fallback **L556–577**; not-found **L580–587**; empty-count **L1102–1119**; raise **L1084–1090**
- get_batch_field JSON **L412–429**, nested **L422–429**, fallback **L432–452**, missing-nested (only failing case) **L788–813**
- scan tests: **L932–968** (decode error), **L971–1036** (filter); raise **L1039–1045**
- delete tests: **L657–674**, raise **L1048–1054**
