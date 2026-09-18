# WP4.4 Triage Dossier — `backend/services/redis_json.py`

- **Survivors:** 338 of 594 mutants (256 killed). Meta: `mutants/backend/services/redis_json.py.meta`.
- **Diff source:** `uv run mutmut show <key>` for all 338 keys (fast, no concurrent-cache failures).
- **Sole covering test file:** `backend/tests/unit/services/test_redis_json.py` (1143 lines; fixtures `mock_redis_client` @L152, `metadata_service` @L160). Every survivor's function maps to tests in this one file per `mutmut-stats.json`.
- **Verdict fold:** TEST-GAP 205 · EQUIVALENT 100 · LOW-VALUE 33 (= 338).

## Module character (drives the clustering)

This is a Redis-JSON storage facade. Nearly every behavior surfaces as (a) the exact
`execute_command("JSON.SET", key, "$", json.dumps(data))` wire argument and (b) the stored
JSON payload. The mock-based tests assert *some* wire args for `set_batch_metadata`/
`update_batch_field` but **not** for `append_detection_id`, `close_batch`, `get_batch_field`,
`get_batch_metadata`, and assert **never** the stored payload bytes on the JSON path. That gap
plus unasserted `from_dict` fields are the bulk of the real TEST-GAPs. Log text, the
`raise RuntimeError("…")` message (killed only via `match=`, which substring-matches), the
`_check_json_available` probe key, and error-classification literals are pure cosmetic /
dead-defensive noise.

## Per-cluster table

| # | Pattern | n | Class | Example keys (`…__mutmut_N`) |
|---|---------|---|-------|------------------------------|
| 1 | **wire-cmd-path-value** — `execute_command` command / `$`-JSONPath / `json.dumps(data)` value / `key` in `append_detection_id`,`close_batch`,`get_batch_field`,`get_batch_metadata`,`set_batch_metadata`,`update_batch_field` mutated to `None`/`XX…XX`/case/`'…'`-clobber | 120 | **TEST-GAP** | `…set_batch_metadata__mutmut_16/24`, `…get_batch_metadata__mutmut_34`, `…close_batch__mutmut_22` |
| 2 | **from_dict-field-defaults** — `BatchMetadata.from_dict` field default/key/value mutations (`time.time()`→`None`, `""`→`None`, key `XX…`/`STARTED_AT`, whole `data.get(...)`→`None`) | 34 | **TEST-GAP** | `…from_dict__mutmut_6`, `…from_dict__mutmut_7`, `…from_dict__mutmut_8` |
| 3 | **log-message-text** — logger.info/debug/warning message strings + `extra={…}` payload values + `str(e)`→`str(None)` | 90 | **EQUIVALENT** | `…_check_json_available__mutmut_23`, `…set_batch_metadata__mutmut_29`, `…close_batch__mutmut_54` |
| 4 | **fallback-call-state-args** — fallback-path orchestration: `get_batch_metadata(batch_id)`→`(None)`, `metadata.to_dict()`→`None`, `metadata.detection_ids.append(detection_id)`→`(None)`, `set_batch_metadata(batch_id, …)`→wrong args, `path_parts[:-1]` slice, `target[...]=value` assignment | 22 | **TEST-GAP** | `…get_batch_field__mutmut_24`, `…update_batch_field__mutmut_44`, `…append_detection_id__mutmut_81` |
| 5 | **wire-probe-args** — `_check_json_available` probe call `JSON.SET "_test_json" "$" "{}"` / `delete("_test_json")` args | 17 | **LOW-VALUE** | `…_check_json_available__mutmut_4`, `…_check_json_available__mutmut_5`, `…_check_json_available__mutmut_6` |
| 6 | **ttl-expire-setex-args** — `expire(key, effective_ttl)` / `expire(key, self._default_ttl)` / `setex(key, effective_ttl, …)` key/ttl arg mutations on the **JSON path** | 13 | **TEST-GAP** | `…set_batch_metadata__mutmut_25`, `…update_batch_field__mutmut_19`, `…append_detection_id__mutmut_47` |
| 7 | **error-classification-strings** — `"unknown command" in str(e).lower() or "ERR" in str(e)` / `"no such key" not in …` literals + `.lower()` + one `or`→`and` | 12 | **LOW-VALUE** | `…_check_json_available__mutmut_27`, `…get_batch_metadata__mutmut_20`, `…_check_json_available__mutmut_33` |
| 8 | **exception-message-text** — `raise RuntimeError("Redis client not connected")` message tweaks (`XX…XX`) | 8 | **EQUIVALENT** | `…set_batch_metadata__mutmut_3`, `…get_batch_metadata__mutmut_3`, `…close_batch__mutmut_3` |
| 9 | **ttl-config-hasattr** — `get_batch_metadata_service` default-ttl `hasattr(settings,"batch_metadata_ttl")` gate → `and False`/`or True`/clobber (`settings`→`None`) | 7 | **TEST-GAP** | `x_get_batch_metadata_service__mutmut_8`, `…__mutmut_9`, `…__mutmut_10` |
| 10 | **singleton-build** — `get_batch_metadata_service`: `is None`→`is not None`, `get_settings()`→`None`, `BatchMetadataService(redis_client=…)`→`None` | 4 | **TEST-GAP** | `x_get_batch_metadata_service__mutmut_1`, `…__mutmut_2`, `…__mutmut_4` |
| 11 | **scan-iter-args** — `scan_iter(match=f"{prefix}*", count=100)` kwargs, incl. `count=100`→`count=1` | 5 | **TEST-GAP** | `…get_open_batches_for_camera__mutmut_7`, `…__mutmut_8`, `…__mutmut_11` |
| 12 | **scan-decode-branch** — `key.decode() if isinstance(key, bytes) else key` → `if … or True else key` | 1 | **LOW-VALUE** | `…get_open_batches_for_camera__mutmut_14` |
| 13 | **exception/refresh-ttl EQUIVALENT** — `set_batch_metadata(batch_id, data, self._default_ttl if (refresh_ttl) and False/or True else None)`: `ttl=None` then falls back to `effective_ttl = ttl or default_ttl`, so value is unchanged → dead | 2 | **EQUIVALENT** | `…update_batch_field__mutmut_69`, `…update_batch_field__mutmut_70` |
| 14 | **pipeline-transaction-flag** — `pipeline(transaction=True)`→`transaction=None/False` in `close_batch` | 2 | **LOW-VALUE** | `…close_batch__mutmut_13`, `…close_batch__mutmut_14` |
| 15 | **exists-check-arg** — `exists = await self._redis._client.exists(key)`→`exists(None)` in `close_batch` | 1 | **LOW-VALUE** | `…close_batch__mutmut_10` |
|    | **TOTAL** | **338** | | |

### Cluster notes

- **#1 (120, TEST-GAP, dominant).** `test_set_batch_metadata_with_json` (L260) and
  `test_update_batch_field_with_json` (L469) *do* assert command/key/path positionally, so only a
  minority of #1 keys survive there; the mass is in `append_detection_id`, `close_batch`,
  `get_batch_field`, `get_batch_metadata` where no test asserts the `execute_command` /
  `pipe.execute_command` args at all. Killing needs per-method wire assertions.
- **#2 (34, TEST-GAP).** `test_from_dict` (L83) asserts only `batch_id/camera_id/status/detection_ids/
  detection_count/processing_metadata`; it never asserts `started_at`, `last_activity`, `closed_at`,
  `pipeline_start_time`, `close_reason`. `test_roundtrip_to_dict_from_dict` (L123) likewise omits the
  timestamps. So every mutation to those five field defaults survives. Fix: assert them.
- **#3 (90, EQUIVALENT).** Log strings and `extra` payloads never affect return values; `str(e)`→`str(None)`
  only changes a log detail. Unkillable without asserting on captured log records (not worth it).
- **#4 (22, TEST-GAP).** Real behavior: passing `None` as the batch id to `get_batch_metadata`, or
  `data=None`/`value=None` in the fallback update, changes what gets stored/returned. Existing
  fallback tests assert the *outcome* (`result`, or the stored `status`) but the wrong-arg path is
  masked because mocks are keyed loosely. Killing needs argument-level capture on the fallback path.
- **#5 (17, LOW-VALUE).** `_check_json_available` args mutate the throwaway `_test_json` probe key.
  The existing test drives the mock regardless of args, so all variants yield the same availability
  verdict — genuine change, but a probe-arg assertion nobody should own.
- **#6 (13, TEST-GAP).** JSON-path TTL is *never* asserted — `test_set_batch_metadata_custom_ttl` (L316)
  exercises the **fallback** `setex(key,7200,…)` path only, not the JSON-path `expire(key, ttl)`.
- **#7 (12, LOW-VALUE).** The `or`→`and` flip and literal/case `.lower()` tweaks: the mock's canned
  `"ERR unknown command …"` error keeps the branch's boolean outcome identical, and the
  `"no such key" not in` inversion changes only the *warning* branch (fall-through identical).
- **#12 (1, LOW-VALUE).** `if isinstance(key,bytes) or True` forces the decode branch — unreachable for
  non-bytes keys, so a str-key scan hits `AttributeError`→caught→key dropped. All existing fixtures
  yield `bytes`, so the branch is never exercised as intended.
- **#13 (2, EQUIVALENT).** Verified: `ttl=None` → `effective_ttl = ttl or self._default_ttl` collapses
  the ternary, so `and False` / `or True` are no-ops.

## Drafted tests (6) — one per highest-value TEST-GAP cluster

All target `backend/tests/unit/services/test_redis_json.py`; reuse the module's `metadata_service` /
`mock_redis_client` fixtures and `@pytest.mark.asyncio` style. **// UNVERIFIED — not yet run red/green.**
TDD procedure: add the test, confirm it FAILS on the mutant diff (the specific `__mutmut_N` key), then
PASSES on the unmutated `backend/services/redis_json.py`.

### T1 — `from_dict` must preserve timestamp/optional fields  (kills cluster #2)
File: `backend/tests/unit/services/test_redis_json.py` (append to `class TestBatchMetadata`)
```python
    def test_from_dict_preserves_timestamp_and_optional_fields(self):
        """from_dict must carry started_at/last_activity/closed_at/pipeline_start_time/close_reason."""
        data = {
            "batch_id": "b",
            "camera_id": "c",
            "started_at": 1700000000.0,
            "last_activity": 1700000030.0,
            "closed_at": 1700000060.0,
            "pipeline_start_time": "2025-01-01T00:00:00Z",
            "close_reason": "idle",
        }

        metadata = BatchMetadata.from_dict(data)

        assert metadata.started_at == 1700000000.0
        assert metadata.last_activity == 1700000030.0
        assert metadata.closed_at == 1700000060.0
        assert metadata.pipeline_start_time == "2025-01-01T00:00:00Z"
        assert metadata.close_reason == "idle"

    def test_from_dict_defaults_started_at_to_now_when_missing(self):
        """Missing started_at must default to a float timestamp (never None)."""
        metadata = BatchMetadata.from_dict({"batch_id": "b", "camera_id": "c"})

        assert isinstance(metadata.started_at, float)
        assert isinstance(metadata.last_activity, float)
```
Kills: `from_dict__mutmut_6/7` (`time.time()`→`None`), `_8/_9` (`data.get(...)`→`None`), `_24/_31`
(`""`→`None`), and the `XX…`/`STARTED_AT` key clobbers (they drop the value → assertion fails).

### T2 — `append_detection_id` JSON-path wire contract  (kills cluster #1, largest)
File: same file (append to `class TestBatchMetadataServiceAppendDetectionId`)
```python
    @pytest.mark.asyncio
    async def test_append_detection_id_json_wire_contract(self, metadata_service, mock_redis_client):
        """append_detection_id must issue ARRAPPEND/NUMINCRBY/SET/GET with exact cmd+key+path+value."""
        metadata_service._json_available = True
        mock_redis_client._client.execute_command = AsyncMock(
            side_effect=[None, None, None, "[5]"]
        )
        mock_redis_client._client.expire = AsyncMock()

        result = await metadata_service.append_detection_id("batch-wire", 42)

        assert result == 5
        calls = mock_redis_client._client.execute_command.call_args_list
        key = f"{BATCH_META_PREFIX}batch-wire"
        # 1) JSON.ARRAPPEND key "$.detection_ids" "42"
        assert calls[0][0][0] == "JSON.ARRAPPEND"
        assert calls[0][0][1] == key
        assert calls[0][0][2] == "$.detection_ids"
        assert calls[0][0][3] == "42"
        # 2) JSON.NUMINCRBY key "$.detection_count" "1"
        assert calls[1][0][0] == "JSON.NUMINCRBY"
        assert calls[1][0][1] == key
        assert calls[1][0][2] == "$.detection_count"
        assert calls[1][0][3] == "1"
        # 3) JSON.SET key "$.last_activity" <numeric str>
        assert calls[2][0][0] == "JSON.SET"
        assert calls[2][0][1] == key
        assert calls[2][0][2] == "$.last_activity"
        float(calls[2][0][3])  # must be a numeric timestamp string
        # 4) JSON.GET key "$.detection_count"
        assert calls[3][0][0] == "JSON.GET"
        assert calls[3][0][1] == key
        assert calls[3][0][2] == "$.detection_count"

    @pytest.mark.asyncio
    async def test_append_detection_id_refreshes_ttl(self, metadata_service, mock_redis_client):
        """The JSON append path must refresh TTL to the service default on the batch key."""
        metadata_service._json_available = True
        mock_redis_client._client.execute_command = AsyncMock(side_effect=[None, None, None, "[5]"])
        mock_redis_client._client.expire = AsyncMock()

        await metadata_service.append_detection_id("batch-wire", 42)

        mock_redis_client._client.expire.assert_called_once_with(
            f"{BATCH_META_PREFIX}batch-wire", DEFAULT_BATCH_META_TTL
        )
```
Kills: cluster #1 append subset (51) **and** cluster #6 append TTL keys — command, key, JSONPath, the
`"42"`/`"1"` string values, the `$.detection_count` GET, and the `expire(key, default_ttl)` call.

### T3 — `close_batch` JSON-path pipeline wire contract  (kills cluster #1 close subset)
File: same file (append to `class TestBatchMetadataServiceCloseBatch`)
```python
    @pytest.mark.asyncio
    async def test_close_batch_json_wire_contract(self, metadata_service, mock_redis_client):
        """close_batch must write status/closed_at/close_reason to the exact JSONPaths."""
        metadata_service._json_available = True
        mock_redis_client._client.exists = AsyncMock(return_value=1)

        mock_pipeline = MagicMock()
        mock_pipeline.execute_command = MagicMock()
        mock_pipeline.execute = AsyncMock()
        mock_pipeline.__aenter__ = AsyncMock(return_value=mock_pipeline)
        mock_pipeline.__aexit__ = AsyncMock()
        mock_redis_client._client.pipeline = MagicMock(return_value=mock_pipeline)

        result = await metadata_service.close_batch("batch-close", reason="manual")

        assert result is True
        cmds = mock_pipeline.execute_command.call_args_list
        key = f"{BATCH_META_PREFIX}batch-close"
        assert cmds[0][0] == ("JSON.SET", key, "$.status", '"closed"')
        assert cmds[1][0][0] == "JSON.SET"
        assert cmds[1][0][1] == key
        assert cmds[1][0][2] == "$.closed_at"
        float(cmds[1][0][3])  # closed_at is a numeric timestamp string
        assert cmds[2][0] == ("JSON.SET", key, "$.close_reason", '"manual"')
        # transactional pipeline, not autocommit
        mock_redis_client._client.pipeline.assert_called_once_with(transaction=True)
```
Kills: cluster #1 close subset (41) — command/key/JSONPath/value for all three writes — and
cluster #14 (`pipeline(transaction=True)`), and cluster #15 (`exists(key)`, see T3b below).

T3b (kill `close_batch__mutmut_10`):
```python
    @pytest.mark.asyncio
    async def test_close_batch_checks_correct_key(self, metadata_service, mock_redis_client):
        """close_batch must gate on the batch's own key, not None."""
        metadata_service._json_available = True
        mock_redis_client._client.exists = AsyncMock(return_value=1)
        mock_pipeline = MagicMock()
        mock_pipeline.execute_command = MagicMock()
        mock_pipeline.execute = AsyncMock()
        mock_pipeline.__aenter__ = AsyncMock(return_value=mock_pipeline)
        mock_pipeline.__aexit__ = AsyncMock()
        mock_redis_client._client.pipeline = MagicMock(return_value=mock_pipeline)

        await metadata_service.close_batch("batch-close", reason="timeout")

        mock_redis_client._client.exists.assert_called_once_with(f"{BATCH_META_PREFIX}batch-close")
```

### T4 — TTL is applied on the JSON path  (kills cluster #6)
File: same file (append to `class TestBatchMetadataServiceErrorHandling` or `…SetBatchMetadata`)
```python
    @pytest.mark.asyncio
    async def test_set_batch_metadata_json_applies_expire_with_effective_ttl(
        self, metadata_service, mock_redis_client
    ):
        """The RedisJSON path must set the key's TTL via expire(key, ttl), not just store."""
        metadata_service._json_available = True
        mock_redis_client._client.execute_command = AsyncMock()
        mock_redis_client._client.expire = AsyncMock()

        await metadata_service.set_batch_metadata(
            "batch-ttl", {"batch_id": "batch-ttl", "camera_id": "c"}, ttl=999
        )

        mock_redis_client._client.expire.assert_called_once_with(
            f"{BATCH_META_PREFIX}batch-ttl", 999
        )

    @pytest.mark.asyncio
    async def test_update_batch_field_json_applies_expire_with_default_ttl(
        self, metadata_service, mock_redis_client
    ):
        """update_batch_field(refresh_ttl=True) must expire(key, default_ttl) on the JSON path."""
        metadata_service._json_available = True
        mock_redis_client._client.execute_command = AsyncMock()
        mock_redis_client._client.expire = AsyncMock()

        await metadata_service.update_batch_field("batch-ttl", "$.status", "closing", refresh_ttl=True)

        mock_redis_client._client.expire.assert_called_once_with(
            f"{BATCH_META_PREFIX}batch-ttl", DEFAULT_BATCH_META_TTL
        )
```
Kills: cluster #6 (13) — `expire(key, effective_ttl)` / `expire(key, self._default_ttl)` key+ttl arg
mutations for `set_batch_metadata`, `update_batch_field`, `append_detection_id` (covered in T2).

### T5 — factory uses settings TTL, defaults, and builds a real client  (kills clusters #9, #10)
File: same file (append to `class TestGetBatchMetadataService`)
```python
    @pytest.mark.asyncio
    async def test_get_batch_metadata_service_uses_settings_ttl(self, mock_redis_client):
        """Factory must honor settings.batch_metadata_ttl when present."""
        import backend.services.redis_json as module

        module._batch_metadata_service = None
        with patch("backend.services.redis_json.get_settings", autospec=True) as mock_settings:
            mock_settings.return_value = MagicMock(batch_metadata_ttl=555)

            service = await get_batch_metadata_service(mock_redis_client)

            assert service._default_ttl == 555
        module._batch_metadata_service = None

    @pytest.mark.asyncio
    async def test_get_batch_metadata_service_defaults_when_attr_missing(self, mock_redis_client):
        """Missing settings.batch_metadata_ttl must fall back to DEFAULT_BATCH_META_TTL (not crash/None)."""
        import backend.services.redis_json as module

        module._batch_metadata_service = None
        with patch("backend.services.redis_json.get_settings", autospec=True) as mock_settings:
            # MagicMock without batch_metadata_ttl: hasattr(...) is False
            mock_settings.return_value = MagicMock(spec=[])

            service = await get_batch_metadata_service(mock_redis_client)

            assert service._default_ttl == DEFAULT_BATCH_META_TTL
        module._batch_metadata_service = None

    @pytest.mark.asyncio
    async def test_get_batch_metadata_service_stores_the_client(self, mock_redis_client):
        """The created service must bind the supplied redis_client (None-client must fail here)."""
        import backend.services.redis_json as module

        module._batch_metadata_service = None
        with patch("backend.services.redis_json.get_settings", autospec=True) as mock_settings:
            mock_settings.return_value = MagicMock(batch_metadata_ttl=60)

            service = await get_batch_metadata_service(mock_redis_client)

            assert service._redis is mock_redis_client
        module._batch_metadata_service = None
```
Kills: cluster #9 (`hasattr(...)`→`and False` → 555 becomes 3600 → fail; `settings`→`None` → TypeError;
`"batch_metadata_ttl"` clobber → both branches fail; `default_ttl=` clobber/`''`-drop) and cluster #10
(`get_settings()`→`None` → `None.batch_metadata_ttl` TypeError; `redis_client=redis_client`→
`redis_client=None` → `_redis is None` fail; `is not None` → second factory call returns a *stale*
global, and `_redis`/`_default_ttl` assertions expose the not-built service).

### T6 — `get_open_batches_for_camera` scan pattern + string-key handling  (kills clusters #11, #12)
File: same file (append to `class TestBatchMetadataServiceErrorHandling`)
```python
    @pytest.mark.asyncio
    async def test_get_open_batches_scans_with_prefix_glob(self, metadata_service, mock_redis_client):
        """The scan must use match=<prefix>* and keep the original batch-size hint, not count=1."""
        metadata_service._json_available = False

        seen_kwargs = {}

        async def mock_scan_iter(**kwargs):
            seen_kwargs.update(kwargs)
            return
            yield  # pragma: no cover  (empty async iterator)

        mock_redis_client._client.scan_iter = mock_scan_iter

        await metadata_service.get_open_batches_for_camera("front_door")

        assert seen_kwargs["match"] == f"{BATCH_META_PREFIX}*"
        assert seen_kwargs["count"] == 100

    @pytest.mark.asyncio
    async def test_get_open_batches_handles_str_keys(self, metadata_service, mock_redis_client):
        """String keys (non-bytes) must decode without AttributeError and still be returned."""
        metadata_service._json_available = False
        data = {
            "batch_id": "batch-str",
            "camera_id": "front_door",
            "status": "open",
            "detection_ids": [],
            "detection_count": 0,
        }

        async def mock_scan_iter(**kwargs):
            yield "batch:meta:batch-str"  # str, not bytes

        mock_redis_client._client.scan_iter = mock_scan_iter
        mock_redis_client._client.get = AsyncMock(return_value=json.dumps(data))

        batches = await metadata_service.get_open_batches_for_camera("front_door")

        assert len(batches) == 1
        assert batches[0].batch_id == "batch-str"
```
Kills: cluster #11 (`match=None`→kwargs fail; `count=100`→`1`→assert fails; drop of the kwarg) and
cluster #12 (`or True` on str key → `.decode()` AttributeError → exception swallowed → key dropped →
`len(batches)==0` fail).

## Kill-efficiency expectation

T1+T2+T3(+T3b)+T4+T5+T6 target clusters #1, #2, #4 (via #1's methods), #6, #9, #10, #11, #12 —
the 120+34+22+13+7+4+5+1 = **206** real-behavior survivors. Cluster #4's `fallback-call-state-args`
overlaps the wire path only partially; a follow-up test capturing the fallback
`set_batch_metadata`/`get_batch_metadata` call args (assert the stored dict payload via
`setex`/`execute_command` `call_args`) closes it. Clusters #3/#5/#7/#8/#13/#14 (log text, probe args,
error literals, exception msg, dead refresh_ttl ternary, transaction flag) are intentionally left unkilled.
