# WP4.3 Survivor Triage — backend/services/batch_aggregator.py

- **Module:** `backend/services/batch_aggregator.py`
- **Survivors:** 710 of 1150 keys (exit_code 0 in `mutants/backend/services/batch_aggregator.py.meta`)
- **Triaged:** 2026-09-18 (read-only; no tests executed)
- **Diffs:** `uv run mutmut show` failed on mangled keys (`FileNotFoundError`), so diffs were recovered manually from `mutants/backend/services/batch_aggregator.py` by difflib-comparing each `__mutmut_N` def block against `__mutmut_orig`. Cluster keys in this dossier are real meta keys.
- **Covering tests** from `mutants/mutmut-stats.json` → `tests_by_mangled_function_name`.

## Covering test files

| File | Key line anchors |
| --- | --- |
| `backend/tests/unit/services/test_batch_aggregator.py` | fixtures `mock_redis_client`:50, `mock_redis_instance`:106, `batch_aggregator`:131; `create_mock_pipeline`:60; recording `MockPipeline.set` (records `("set", key, value, ex)` but `ex` never asserted):159-171; timeout tests :322 (95s window), :372 (35s idle), :419 (no-timeout 30s/5s); delete assertions — only `pipeline_start_time`:1539 and `closing`:3535 are ever checked (5 of 7 deleted keys never asserted); closing-flag TTL tests :3598, :3646 (assert key + `ex==300`, never the value `"1"`); threat dispatch test :3908-3923 (asserts only `assert_called_once()`, no kwargs); threat fast-path params test :3986 (`assert_called_once()`, no kwargs); smoke/fire params test :4494 (asserts kwargs); size-limit bytes test :1955 (asserts summary fields; `lrange` args and delete list unvalidated); already-closed test :1744/:1772 (checks `summary.get("already_closed") is True` only) |
| `backend/tests/unit/services/test_orphan_recovery.py` | :39-148; session `execute` is mocked so the SQL `stmt` is never inspected; re-injection kwargs asserted only for `camera_id`/`detection_id` :91-94 (`_file_path`, `confidence`, `object_type` never asserted) |
| `backend/tests/unit/services/test_memory_pressure.py` | GPU-pressure semantics live here, but the module-level `_gpu_monitor` wiring in batch_aggregator is covered only by two tests in test_batch_aggregator.py (:1647, :1668) |

## Cluster table (710 total)

| # | Pattern | n | Class | Example keys (≤3) | Covering test / verdict rationale |
|---|---|---|---|---|---|
| 1 | logging `extra={...}` dicts mutated (key names, values→None/XX) in every method | 278 | EQUIVALENT | `xǁBatchAggregatorǁadd_detection__mutmut_22` | Log `extra` never asserted anywhere (caplog tests assert message only, e.g. tb:1116-1148). Not worth gating. |
| 2 | logger message string mutations (`"Batch created"`→`"XXBatch createdXX"`, case flips) | 138 | EQUIVALENT | `xǁBatchAggregatorǁclose_batch__mutmut_27` | No test asserts log message text for these events; operator grep-ability is a lint concern, not a test gap. |
| 3 | WebSocket broadcast payload dicts `detection_data`/`batch_data` (key renames, value→None, `label or "unknown"` flips, `get_broadcaster` args) | 81 | TEST-GAP | `xǁBatchAggregatorǁ_broadcast_detection_new__mutmut_11` | **No tests exist at all** for `_broadcast_detection_new`/`_broadcast_detection_batch` (grep: zero hits). Draft test 6. |
| 4 | `self._redis.delete(...)` of the 7 batch keys in `close_batch` (:998-1006) and `_close_batch_for_size_limit` (:1142-1150) — args →None or dropped | 24 | TEST-GAP | `xǁBatchAggregatorǁ_close_batch_for_size_limit__mutmut_118` | Tests assert only 2 of 7 keys ever (tb:1539, tb:3535); size-limit delete never asserted. Real leak: orphaned `:detections`/`:current` keys. Draft tests 1+2. |
| 5 | `pipe.set(..., ex=ttl)` in `_create_batch_metadata_atomic` (:385; 5 sets) — `ex` dropped/None/changed | 20 | TEST-GAP | `xǁBatchAggregatorǁ_create_batch_metadata_atomic__mutmut_9` | `MockPipeline` records `ex` (tb:161) but no test asserts `ex == BATCH_KEY_TTL_SECONDS`. Missing TTL = permanent-key leak. Draft test 3. |
| 6 | orphan-recovery SQLAlchemy `stmt` mutations: `outerjoin` args, `where(...)` clause drops, `Detection.id,` select columns, `.order_by(detected_at.asc())`, `.limit(ORPHAN_RECOVERY_LIMIT)`→None | 20 | TEST-GAP | `x_recover_orphaned_detections__mutmut_11` | `test_orphan_recovery.py` mocks `session.execute`; the statement object is never inspected. Wrong join/where recovers already-linked rows or unbounded rows. Fix: assert `str(stmt.compile())` contains the join, `event_id IS NULL`, `detected_at <` cutoff, ORDER BY and LIMIT 500. (Covered by the same new-test file as draft 5.) |
| 7 | `add_detection` dispatch kwargs to `_process_threat_fast_path`/`_process_smoke_fire_fast_path` (:522-528, :546-552) — each kwarg →None/dropped | 16 | TEST-GAP | `xǁBatchAggregatorǁadd_detection__mutmut_30` | Dispatch tests (tb:3908, tb:3923) mock the fast path and assert only `assert_called_once()`. Wrong `threat_type`/`confidence` forwarded = wrong alert severity. Draft test 4. |
| 8 | `check_batch_timeouts` plumbing: `batch_id_pipe.get(key)`→None, `metadata_pipe.get(started_at/last_activity)`→None, `zip(..., strict=True)`→False, `batch_keys.append(None)`, bytes-decode branches, `camera_id_for_log` get | 20 | TEST-GAP | `xǁBatchAggregatorǁcheck_batch_timeouts__mutmut_46` | Tests build pipelines via `create_mock_pipeline` which returns recorded values for ANY key, so key mutations are invisible. Draft test 4 adds phase-pipe key assertions; `strict=` variants stay unkillable under equal-length mocks (note). |
| 9 | `lrange(detections_key, 0, -1)` args →None/dropped in size-limit path | 9 | EQUIVALENT | `xǁBatchAggregatorǁ_close_batch_for_size_limit__mutmut_27` | `mock_redis_client.lrange` is `AsyncMock(return_value=[...])` — returns the list for any args (EQUIVALENT-under-mock). Draft test 2 adds `assert_called_with(key, 0, -1)` so a real-Redis suite would also kill these; not worth a dedicated fake. |
| 10 | service-construction/kwargs in fast paths: `ThreatMonitorService(redis_client=self._redis)`→None, `service.process_*` kwargs (`smoke_fire_type or "unknown"` case-changes, `confidence or 0.0`→`1.0`) | 8 | TEST-GAP | `xǁBatchAggregatorǁ_process_smoke_fire_fast_path__mutmut_30` | tb:4494 asserts smoke/fire kwargs but tb:3986 (threat) asserts only call-count; `"UNKNOWN"` variants of the `or`-default survive. Minor gap: extend tb:4494-style kwargs to the threat service call and pin `redis_client=` identity. (No draft — lower value than the 6 below.) |
| 11 | `with log_context(batch_id=..., camera_id=...)` mutations | 8 | LOW-VALUE | `xǁBatchAggregatorǁclose_batch__mutmut_10` | Log-context only affects log correlation, never behavior; assertable only via caplog plumbing for zero functional value. |
| 12 | `batch_duration_ms = (ended_at - started_at) * 1000` arithmetic mutations | 8 | LOW-VALUE | `xǁBatchAggregatorǁ_close_batch_for_size_limit__mutmut_95` | `duration_ms` lands only in the summary/log; existing summary tests (tb:1955) don't read it. Marginal: could assert `duration_ms >= 0` if desired. |
| 13 | `ttl = self.BATCH_KEY_TTL_SECONDS` →None in `add_detection`, `self._redis.set(..., expire=ttl)` for `last_activity` (:637) | 7 | TEST-GAP | `xǁBatchAggregatorǁadd_detection__mutmut_134` | `expire=` kwarg never asserted (MockPipeline records `ex` only for pipeline sets). Killed by draft test 3. |
| 14 | `raise RuntimeError("Redis client not initialized")` message mutations in `_atomic_list_append`/`_atomic_list_get_all` | 6 | EQUIVALENT | `xǁBatchAggregatorǁ_atomic_list_append__mutmut_5` | Tests use bare `pytest.raises(RuntimeError)` without `match=`. Matching text would be near-zero-cost but changes no behavior. |
| 15 | re-injection kwargs in `recover_orphaned_detections` → `add_detection(_file_path=..., confidence=..., object_type=...)` →None/dropped | 6 | TEST-GAP | `x_recover_orphaned_detections__mutmut_42` | test_orphan_recovery.py asserts only `camera_id`/`detection_id` kwargs (:91-94). Recovered detections would lose file path/confidence silently. Draft test 5. |
| 16 | closing-flag value: `set(f"batch:{id}:closing", "1", ex=300)` → value None/dropped | 6 | LOW-VALUE | `xǁBatchAggregatorǁ_close_batch_for_size_limit__mutmut_19` | Flag existence is what gates re-entry; the literal `"1"` is never read by any code path (existence check only). Existing TTL tests (tb:3598, :3646) already pin key + `ex==300`. |
| 17 | key/state wiring in size-limit path: `detections_key = None`, `started_at_str = await self._redis.get(...)`→None / `get(None)` | 6 | TEST-GAP | `xǁBatchAggregatorǁ_close_batch_for_size_limit__mutmut_25` | Same mock-blind-spot as #8; draft test 2's `lrange`/delete assertions kill the observable half. |
| 18 | `_atomic_list_append(detections_key, detection_id_int, ttl)` arg mutations in `add_detection` (:634) | 6 | TEST-GAP | `xǁBatchAggregatorǁadd_detection__mutmut_150` | rpush/expire args unvalidated today; killed by draft test 3 (`rpush.assert_called_with`, `expire.assert_called_with`). |
| 19 | `should_close = False→True/None` and `close_reason` init/f-string →None in timeout loop (:773-786) | 6 | TEST-GAP | `xǁBatchAggregatorǁcheck_batch_timeouts__mutmut_93` | `should_close=True` means every scanned batch closes; no test runs a healthy batch through the same loop as a closing one. `should_close=True` variant survived the existing no-timeout test (:419) per meta — treat meta as ground truth. Killed by draft test 4's healthy-batch-C assertion; the 4 `close_reason`-string variants are log-only residue. |
| 20 | already-closed summary dict keys in `close_batch` (:866-874): `"detections"/"started_at"/"closed_at"` renames | 6 | TEST-GAP | `xǁBatchAggregatorǁclose_batch__mutmut_37` | tb:1772 only does `summary.get("already_closed") is True`; renamed sibling keys pass. Fix (cheap): `assert set(summary) == {...}` in the already-closed test. No separate draft. |
| 21 | `__init__`: `getattr(settings, "use_redis_streams", False)` default mutations | 4 | EQUIVALENT | `xǁBatchAggregatorǁ__init____mutmut_16` | `settings` always defines `use_redis_streams` in the test env and the fixture force-overrides `_use_redis_streams = False` (tb:134), so the `getattr` default is unreachable in unit scope. |
| 22 | `should_bypass_batch(object_type=object_type, ...)` argument dropped at the two dispatch sites | 4 | EQUIVALENT | `xǁBatchAggregatorǁadd_detection__mutmut_12` | `should_bypass_batch` never reads `object_type` (param marked `# noqa: ARG002`, :1273-1330). Truly equivalent. |
| 23 | metadata result indexing: `metadata_results[i * 2]`→`i*3`, `metadata_results[i * 2 + 1]`→None/`+0` (:735-736) | 4 | TEST-GAP | `xǁBatchAggregatorǁcheck_batch_timeouts__mutmut_52` | All timeout tests run exactly ONE batch, so interleaved-index mutations are invisible. Killed by draft test 4's three-batch phase-2 results. |
| 24 | misc equivalences: `int(item.decode("utf-8"))`→`"UTF-8"`, `if not a or not b`→`and` (both-falsy branch), etc. | 3 | EQUIVALENT | `xǁBatchAggregatorǁ_close_batch_for_size_limit__mutmut_41` | Decode alias is a no-op; boolean-flip only differs when `_client` is None while `_redis` is truthy — not constructible under fixtures. |
| 25 | local-init mutations in `close_batch` (`detections: list[int] = []`→None, `started_at_str: str | None = ""`) before TaskGroup overwrite | 3 | EQUIVALENT | `xǁBatchAggregatorǁclose_batch__mutmut_46` | Values are unconditionally overwritten by the TaskGroup fetchers before any read on the happy path. |
| 26 | module-level GPU monitor wiring: `if _gpu_monitor is None:` flip, `_gpu_monitor = monitor`→None (`set_gpu_monitor`/`get_memory_pressure_level`) | 2 | LOW-VALUE | `x_get_memory_pressure_level__mutmut_1` | Wiring-only test would assert global plumbing; production callers are integration territory. If wanted: one test asserting pressure follows a registered fake monitor. |
| 27 | `self._get_camera_lock(camera_id)`→`get(None)` in `add_detection`/`close_batch` | 2 | EQUIVALENT | `xǁBatchAggregatorǁadd_detection__mutmut_91` | Under mock, lock identity is unobservable and behavior identical; real deadlock behavior is integration-test scope. |
| 28 | boundary flips: `if window_elapsed >= self._batch_window:` → `>`, `elif idle_time >= self._idle_timeout:` → `>` (:776/:781) | 2 | TEST-GAP | `xǁBatchAggregatorǁcheck_batch_timeouts__mutmut_96` | Tests use 95s vs 90s and 35s vs 30s — never the exact boundary. Killed by draft test 4 (frozen clock at exact elapsed). |
| 29 | `current_time - started_at`→`+`, `current_time - last_activity`→`+` (:768-770) | 2 | TEST-GAP | `xǁBatchAggregatorǁcheck_batch_timeouts__mutmut_89` | `+` yields a huge elapsed that closes even healthy batches — invisible without a healthy batch in the same run. Killed by draft test 4. |
| 30 | queue push in size-limit path: `overflow_policy=QueueOverflowPolicy.DLQ`→None/dropped (:1090-1105) | 2 | TEST-GAP | `xǁBatchAggregatorǁ_close_batch_for_size_limit__mutmut_74` | Existing tests assert queue data payload but never the `overflow_policy` kwarg; DLQ-on-overflow is the anti-loss contract. Killed by draft test 2. |
| 31 | smoke/fire handler `exc_info=True`→False in exception log | 1 | EQUIVALENT | `xǁBatchAggregatorǁ_process_smoke_fire_fast_path__mutmut_62` | Exception-log detail only. |
| 32 | `self._atomic_list_get_all(f"batch:{id}:detections")`→`get_all(None)` in `close_batch` | 1 | LOW-VALUE | `xǁBatchAggregatorǁclose_batch__mutmut_50` | AsyncMock lrange ignores the key (EQUIVALENT-under-mock); would be covered by any real-Redis smoke test. |
| 33 | `started_at = float(s) if s else time.time()` fallback suppressed (`if (s) and False`) | 1 | TEST-GAP | `xǁBatchAggregatorǁclose_batch__mutmut_70` | No test closes a batch whose `started_at` key is missing; mutant always uses now() (duration silently 0). Cheap add to draft test 2's sibling: close with `started_at=None` and assert duration≈0 on original too — or accept LOW-VALUE. |

Classification rollup: TEST-GAP 237 / EQUIVALENT 448 / LOW-VALUE 25 (sum 710).

## Drafted tests (6) — UNVERIFIED, not yet run red/green

Style follows the existing file: module-level `@pytest.mark.asyncio` tests using the `batch_aggregator` / `mock_redis_instance` fixtures (test_batch_aggregator.py:106-138), `create_async_generator`/`create_mock_pipeline` helpers, inline recording `MockPipeline` (pattern at :159-171).

### TDD procedure (one line)

Add the test, run it against the ORIGINAL module to confirm GREEN, then run it against each example mutant copy (or re-`mutmut run` the region in the serial lane) and confirm the survivor flips to KILLED.

### Draft 1 — `test_close_batch_deletes_all_batch_keys` → kills DEL-KEYS (close_batch half, 12)

Target file: `backend/tests/unit/services/test_batch_aggregator.py` (near the existing cleanup test at :1511).

```python
@pytest.mark.asyncio
async def test_close_batch_deletes_all_batch_keys(batch_aggregator, mock_redis_instance):
    """close_batch must delete every batch-scoped Redis key (NEM-2013).

    // UNVERIFIED - not yet run red/green
    """
    batch_id = "batch_del_all"
    camera_id = "front_door"

    async def mock_get(key):
        if key == f"batch:{batch_id}:camera_id":
            return camera_id
        elif key == f"batch:{batch_id}:started_at":
            return str(time.time() - 60)
        return None

    mock_redis_instance.get.side_effect = mock_get
    mock_redis_instance._client.lrange.return_value = ["1", "2"]

    await batch_aggregator.close_batch(batch_id)

    deleted = set()
    for call in mock_redis_instance.delete.call_args_list:
        deleted.update(call.args)

    # Exact set from close_batch's cleanup block — every entry is load-bearing:
    # dropping any one leaks a key past the batch's life.
    assert deleted == {
        f"batch:{camera_id}:current",
        f"batch:{batch_id}:camera_id",
        f"batch:{batch_id}:detections",
        f"batch:{batch_id}:started_at",
        f"batch:{batch_id}:last_activity",
        f"batch:{batch_id}:pipeline_start_time",
        f"batch:{batch_id}:closing",
    }
```

### Draft 2 — `test_close_batch_for_size_limit_deletes_all_batch_keys_and_pins_lrange` → kills DEL-KEYS (size half, 12), SIZE-QUEUE (2), SIZE-STATE / LRANGE-ARGS observable halves

Same target file, near the size-limit tests (:1955+).

```python
@pytest.mark.asyncio
async def test_close_batch_for_size_limit_deletes_all_batch_keys_and_pins_lrange(
    batch_aggregator, mock_redis_instance
):
    """Size-limit close must read via lrange(key,0,-1), push with DLQ overflow, delete all keys.

    // UNVERIFIED - not yet run red/green
    """
    batch_id = "batch_size_del"
    camera_id = "side_yard"

    async def mock_get(key):
        if key == f"batch:{batch_id}:camera_id":
            return camera_id
        elif key == f"batch:{batch_id}:started_at":
            return str(time.time() - 60)
        return None

    mock_redis_instance.get.side_effect = mock_get
    mock_redis_instance._client.lrange.return_value = [b"4", b"5"]

    summary = await batch_aggregator._close_batch_for_size_limit(batch_id)

    assert summary is not None
    # Raw read: full-list window, keyed on the batch's detections key.
    mock_redis_instance._client.lrange.assert_called_with(f"batch:{batch_id}:detections", 0, -1)

    # Queue handoff must retain the DLQ overflow policy (anti-loss contract).
    assert mock_redis_instance.add_to_queue_safe.called
    queue_kwargs = mock_redis_instance.add_to_queue_safe.call_args.kwargs
    assert queue_kwargs["overflow_policy"] is QueueOverflowPolicy.DLQ

    deleted = set()
    for call in mock_redis_instance.delete.call_args_list:
        deleted.update(call.args)
    assert deleted == {
        f"batch:{camera_id}:current",
        f"batch:{batch_id}:camera_id",
        f"batch:{batch_id}:detections",
        f"batch:{batch_id}:started_at",
        f"batch:{batch_id}:last_activity",
        f"batch:{batch_id}:pipeline_start_time",
        f"batch:{batch_id}:closing",
    }
```

### Draft 3 — `test_new_batch_sets_all_metadata_keys_with_ttl` → kills PIPE-TTL (20), TTL2 (7), ADD-STATE (6)

Same target file, after the existing pipeline-tracking test (:150-207).

```python
@pytest.mark.asyncio
async def test_new_batch_sets_all_metadata_keys_with_ttl(batch_aggregator, mock_redis_instance):
    """Every batch metadata SET must carry BATCH_KEY_TTL_SECONDS, and RPUSH/expire too (NEM-2014).

    // UNVERIFIED - not yet run red/green
    """
    camera_id = "front_door"
    detection_id = 7
    file_path = "/export/foscam/front_door/image_007.jpg"
    ttl = BatchAggregator.BATCH_KEY_TTL_SECONDS

    mock_redis_instance.get.return_value = None
    mock_redis_instance._client.rpush.return_value = 1

    pipeline_ops: list[tuple] = []

    class MockPipeline:
        def set(self, key, value, ex=None):
            pipeline_ops.append(("set", key, value, ex))
            return self

        async def execute(self):
            return [True] * len(pipeline_ops)

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            return False

    mock_redis_instance._client.pipeline = MagicMock(return_value=MockPipeline())

    with patch("backend.services.batch_aggregator.generate_batch_id", autospec=True) as mock_gen:
        mock_gen.return_value = "batch-ttlcheck"
        await batch_aggregator.add_detection(camera_id, detection_id, file_path)

    # 1) atomic metadata pipeline: each of the 4 sets must carry the TTL
    expected_keys = {
        f"batch:{camera_id}:current",
        "batch:batch-ttlcheck:camera_id",
        "batch:batch-ttlcheck:started_at",
        "batch:batch-ttlcheck:last_activity",
    }
    recorded = {op[1]: op[3] for op in pipeline_ops if op[0] == "set"}
    assert expected_keys <= set(recorded), f"missing metadata keys: {expected_keys - set(recorded)}"
    for key, ex in recorded.items():
        assert ex == ttl, f"pipeline set for {key!r} lost its TTL (ex={ex!r})"

    # 2) RPUSH targets the batch's detections key
    mock_redis_instance._client.rpush.assert_called_with(
        "batch:batch-ttlcheck:detections", str(detection_id)
    )
    # 3) TTL refresh on the detections list
    mock_redis_instance._client.expire.assert_called_with(
        "batch:batch-ttlcheck:detections", ttl
    )
    # 4) last_activity update keeps expire=
    last_calls = [
        c for c in mock_redis_instance.set.call_args_list
        if c.args and c.args[0] == "batch:batch-ttlcheck:last_activity"
    ]
    assert last_calls, "last_activity was never written"
    assert all(c.kwargs.get("expire") == ttl for c in last_calls), "last_activity lost its TTL"
```

### Draft 4 — `test_check_batch_timeouts_exact_boundaries_and_healthy_batch` → kills TB-OPFLIP (2), TB-NEG (2), TB-IDX (4), TB-DEAD (`should_close` pair), TB-WIRE (pipe-key subset of 20)

Same target file, after the timeout tests (:322-450).

```python
@pytest.mark.asyncio
async def test_check_batch_timeouts_exact_boundaries_and_healthy_batch(
    batch_aggregator, mock_redis_instance
):
    """Exact 90s-window / 30s-idle boundaries must close; a healthy batch in the same scan must not.

    Kills >= vs > flips (only observable AT the boundary), - vs + arithmetic (a healthy
    batch in the same scan proves it), and the i*2 / i*2+1 metadata indexing (three
    batches make the interleave observable). Frozen clock makes == elapsed exact.

    // UNVERIFIED - not yet run red/green
    """
    window = batch_aggregator._batch_window   # 90s
    idle = batch_aggregator._idle_timeout     # 30s
    now = time.time()

    a_id, b_id, c_id = "batch_win_edge", "batch_idle_edge", "batch_healthy"
    a_start = str(now - window)  # window_elapsed == window exactly
    a_last = str(now - 5)
    b_start = str(now - 10)      # window not elapsed
    b_last = str(now - idle)     # idle_time == idle exactly
    c_start = str(now - 10)
    c_last = str(now - 2)        # healthy on both axes

    mock_redis_instance._client.scan_iter = MagicMock(
        return_value=create_async_generator(["batch:front_door:current"])
    )
    phase1_pipe = create_mock_pipeline([a_id, b_id, c_id])
    phase2_pipe = create_mock_pipeline([a_start, a_last, b_start, b_last, c_start, c_last])

    call_count = [0]

    def mock_pipeline():
        call_count[0] += 1
        return phase1_pipe if call_count[0] == 1 else phase2_pipe

    mock_redis_instance._client.pipeline = MagicMock(side_effect=mock_pipeline)

    async def mock_get(key):
        if key == f"batch:{a_id}:camera_id":
            return "front_door"
        return None

    mock_redis_instance.get.side_effect = mock_get
    mock_redis_instance._client.lrange.return_value = ["1"]
    batch_aggregator.close_batch = AsyncMock(return_value={"batch_id": "x"})

    with patch("backend.services.batch_aggregator.time.time", return_value=now):
        closed = await batch_aggregator.check_batch_timeouts()

    assert closed == [a_id, b_id], f"expected only the two boundary batches to close, got {closed}"
    assert c_id not in closed
    close_ids = [c.args[0] for c in batch_aggregator.close_batch.call_args_list]
    assert close_ids == [a_id, b_id]

    # Pipe keys are load-bearing: phase 1 reads the camera cursor,
    # phase 2 interleaves started_at/last_activity per batch.
    assert [c.args[0] for c in phase1_pipe.get.call_args_list] == ["batch:front_door:current"]
    assert [c.args[0] for c in phase2_pipe.get.call_args_list] == [
        f"batch:{a_id}:started_at", f"batch:{a_id}:last_activity",
        f"batch:{b_id}:started_at", f"batch:{b_id}:last_activity",
        f"batch:{c_id}:started_at", f"batch:{c_id}:last_activity",
    ]
```

Note: the existing per-batch `except Exception: continue` (batch_aggregator.py:801-807) means an indexing mutant silently drops batch C/B from `closed` rather than raising — the `closed == [a_id, b_id]` assertion still kills it.

### Draft 5 — `test_recover_orphans_forwards_full_kwargs` → kills ORPHAN-KW (6)

Target file: `backend/tests/unit/services/test_orphan_recovery.py` (append to `TestRecoverOrphanedDetections`).

```python
    @pytest.mark.asyncio
    async def test_recover_orphans_forwards_full_kwargs(self) -> None:
        """Re-injection must forward file path, confidence and object type, not just ids.

        // UNVERIFIED - not yet run red/green
        """
        orphan = _make_detection(9, "cam_front", minutes_ago=10)

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [orphan]
        mock_session.execute = AsyncMock(return_value=mock_result)

        mock_aggregator = AsyncMock()
        mock_aggregator.add_detection = AsyncMock(return_value="batch-orphan")

        with patch(
            "backend.core.database.get_session",
            return_value=_mock_session_ctx(mock_session),
            autospec=True,
        ):
            count = await recover_orphaned_detections(mock_aggregator)

        assert count == 1
        kwargs = mock_aggregator.add_detection.call_args.kwargs
        assert kwargs["camera_id"] == "cam_front"
        assert kwargs["detection_id"] == 9
        assert kwargs["_file_path"] == orphan.file_path
        assert kwargs["confidence"] == orphan.confidence
        assert kwargs["object_type"] == orphan.object_type
```

Companion (ORPHAN-Q, 20) — in the same file, assert the statement shape instead of only executing it:

```python
    @pytest.mark.asyncio
    async def test_orphan_query_shape(self) -> None:
        """The recovery query must left-join events, filter unlinked + stale rows, order oldest-first, cap 500.

        // UNVERIFIED - not yet run red/green
        """
        captured: dict = {}

        mock_session = AsyncMock()

        async def fake_execute(stmt):
            captured["sql"] = str(stmt.compile(compile_kwargs={"literal_binds": False}))
            result = MagicMock()
            result.scalars.return_value.all.return_value = []
            return result

        mock_session.execute = AsyncMock(side_effect=fake_execute)

        with patch(
            "backend.core.database.get_session",
            return_value=_mock_session_ctx(mock_session),
            autospec=True,
        ):
            await recover_orphaned_detections(AsyncMock())

        sql = " ".join(captured["sql"].split()).lower()
        assert "left outer join" in sql and "event_detections" in sql
        assert "event_id is null" in sql
        assert "detected_at <" in sql
        assert "order by" in sql and "detected_at asc" in sql
        assert "limit" in sql  # ORPHAN_RECOVERY_LIMIT=500
```

### Draft 6 — `test_broadcast_detection_new_and_batch_payload_contents` → kills PAYLOAD (81)

Target file: `backend/tests/unit/services/test_batch_aggregator.py` (new `TestBroadcastEvents` class at end of file).

```python
class TestBroadcastEvents:
    """Payload contract for the WebSocket broadcast helpers (NEM-2506).

    No tests existed for _broadcast_detection_new / _broadcast_detection_batch;
    the whole payload dict was unmutated territory.

    // UNVERIFIED - not yet run red/green
    """

    @pytest.mark.asyncio
    async def test_broadcast_detection_new_payload_contents(self, batch_aggregator, mock_redis_instance):
        """detection.new payload carries exact keys, 'unknown' label and 0.0 confidence fallbacks."""
        mock_broadcaster = MagicMock()
        mock_broadcaster.broadcast_detection_new = AsyncMock()
        mock_get_broadcaster = AsyncMock(return_value=mock_broadcaster)

        with patch("backend.services.event_broadcaster.get_broadcaster", mock_get_broadcaster):
            await batch_aggregator._broadcast_detection_new(
                detection_id=55, batch_id="batch-bc1", camera_id="front_door",
                label=None, confidence=None,
            )

        mock_get_broadcaster.assert_awaited_once_with(mock_redis_instance)
        payload = mock_broadcaster.broadcast_detection_new.call_args.args[0]
        assert payload["detection_id"] == 55
        assert payload["batch_id"] == "batch-bc1"
        assert payload["camera_id"] == "front_door"
        assert payload["label"] == "unknown"
        assert payload["confidence"] == 0.0
        assert {"detection_id", "batch_id", "camera_id", "label", "confidence", "timestamp"} == set(payload)

    @pytest.mark.asyncio
    async def test_broadcast_detection_batch_payload_contents(self, batch_aggregator, mock_redis_instance):
        """detection.batch payload carries exact keys incl. ISO timestamps and close_reason."""
        mock_broadcaster = MagicMock()
        mock_broadcaster.broadcast_detection_batch = AsyncMock()
        mock_get_broadcaster = AsyncMock(return_value=mock_broadcaster)

        now = time.time()
        with patch("backend.services.event_broadcaster.get_broadcaster", mock_get_broadcaster):
            await batch_aggregator._broadcast_detection_batch(
                batch_id="batch-bc2", camera_id="front_door",
                detection_ids=[1, 2, 3], started_at=now - 90, closed_at=now,
                close_reason="timeout",
            )

        payload = mock_broadcaster.broadcast_detection_batch.call_args.args[0]
        assert payload["batch_id"] == "batch-bc2"
        assert payload["camera_id"] == "front_door"
        assert payload["detection_ids"] == [1, 2, 3]
        assert payload["detection_count"] == 3
        assert payload["close_reason"] == "timeout"
        assert {"batch_id", "camera_id", "detection_ids", "detection_count",
                "started_at", "closed_at", "close_reason"} == set(payload)
        # started_at/closed_at are tz-aware ISO strings
        from datetime import datetime
        datetime.fromisoformat(payload["started_at"])
        datetime.fromisoformat(payload["closed_at"])

    @pytest.mark.asyncio
    async def test_broadcast_skipped_without_redis(self):
        """No broadcaster is touched when the aggregator has no redis client."""
        agg = BatchAggregator(redis_client=None)
        mock_get_broadcaster = AsyncMock()
        with patch("backend.services.event_broadcaster.get_broadcaster", mock_get_broadcaster):
            await agg._broadcast_detection_new(1, "b", "cam")
            await agg._broadcast_detection_batch("b", "cam", [1], 0.0, 1.0)
        mock_get_broadcaster.assert_not_awaited()
```

TDD: on the original module these assertions hold (payload literals match `batch_aggregator.py:243-250` and `:321-329`); each PAYLOAD mutant changes one key/value and turns the corresponding `payload[...]`/`set(payload)` assertion red.

## Recommended-but-undrafted (cheap follow-ups)

- ORPHAN-Q companion test is drafted above as `test_orphan_query_shape` in the same file (counts toward draft 5's cluster).
- SERVICE-ARGS (8): extend the threat-side params test (test_batch_aggregator.py:3986) from `assert_called_once()` to kwargs, and pin `"unknown"` (lowercase) in the smoke/fire defaults.
- CLOSE-ALREADY-DICT (6): change `summary.get("already_closed") is True` (tb:1772) to a full `assert set(summary) == {...}`.
- RAISEMSG (6): add `match="Redis client not initialized"` to the two existing `pytest.raises(RuntimeError)` sites (optional).
