# WP4.4 Triage Dossier — backend/services/batch_aggregator.py

- **Survivors:** 203 of 203 classified (74 TEST-GAP, 125 EQUIVALENT, 4 LOW-VALUE). Cluster counts sum to 203 (verified programmatically, no overlap/gaps: `/tmp/wp25/wp44-triage/_clusters_final.json`).
- **Verdict source:** `mutants/backend/services/batch_aggregator.py.meta` (`exit_code_by_key`, exit 0 = survived).
- **Diff source:** per-survivor AST extraction from the mutant copy (`mutants/backend/services/batch_aggregator.py`, clobbered defs `x<FN>__mutmut_N` diffed against the original defs via `difflib`). `mutmut show` spot-checks agreed; full `mutmut show` sweep abandoned mid-run due to the live `mutmut run` owning the cache. Extractor: `/tmp/wp25/wp44-triage/_difflib_extract.py`; raw diffs: `/tmp/wp25/wp44-triage/_diffs_batch_agg.json`.
- **Covering test files (from `mutants/mutmut-stats.json` tests_by_mangled_function_name):**
  - `backend/tests/unit/services/test_batch_aggregator.py` (set_gpu_monitor :1632, get_memory_pressure_level :1647/:1668, should_apply_backpressure :1693-1735, close_batch_for_size_limit :1942-2106, :3539-3700; split flow :2981-3224)
  - `backend/tests/unit/services/test_memory_pressure.py` (TestBatchAggregatorBackpressure :584-608)
  - `backend/tests/unit/services/test_orphan_recovery.py` (TestRecoverOrphanedDetections :39-149)

## Why so many survive (root causes)

1. **The entire orphan-recovery SELECT is unobservable.** All 4 tests in `test_orphan_recovery.py` stub `session.execute` with an AsyncMock — the built `stmt` is never compiled or inspected. Predicate, LIMIT, ORDER BY, load_only projection, join condition: every mutation passes.
2. **Call-args of Redis collaborators go unasserted for `_close_batch_for_size_limit`** (lrange range args, delete key-list). The tests that DO assert delete-keys (:1533, :3531) exercise `close_batch`, not this method; the only lrange-args assertion (:1228) is a generic redis-client test.
3. **Log payloads are mutated but only substring-lowercase log asserts exist** (`test_batch_aggregator.py:2106`: `"overflow" in record.message.lower()`), which survive XX-wrapping, case flips, and even message→None (mutants still emit a log record at the right level, and `str(None)`-style fallbacks keep substrings alive) — so the 50+17+45+9 message-text mutants ride through. This is by-design noise for `--no-mutation` style baselining: pure message text.
4. **Happy paths never exercised:** `get_memory_pressure_level` with a *working* monitor and the backpressure WARNING log payload tests only assert the returned bool.

## Cluster table

Example keys abbreviated as `<fn>__mutmut_N`; full survivor keys are `backend.services.batch_aggregator.x<fn>__mutmut_N` (class methods: `xǁBatchAggregatorǁ<method>__mutmut_N`).

| # | Pattern | Count | Classification | Example keys |
|---|---------|-------|----------------|--------------|
| C1 | `set_gpu_monitor`: assignment `_gpu_monitor = monitor` → `= None` | 1 | **TEST-GAP** | `x_set_gpu_monitor__mutmut_1` |
| C2 | `set_gpu_monitor`: debug-message text (None/lower/upper/XX) | 4 | EQUIVALENT | `x_set_gpu_monitor__mutmut_2,3,5` |
| C3 | `get_memory_pressure_level`: guard `if _gpu_monitor is None` → `is not None` (happy path untested) | 1 | **TEST-GAP** | `x_get_memory_pressure_level__mutmut_1` |
| C4 | `get_memory_pressure_level`: except-branch debug-log payload (msg→None, extra→None/dropped, key XX/case, `str(None)`, `type(None)`) | 9 | EQUIVALENT | `x_get_memory_pressure_level__mutmut_3,6,11` |
| C5 | `should_apply_backpressure`: all survivors are logger message/extra payload text (CRITICAL branch + except branch) | 17 | EQUIVALENT | `xǁBatchAggregatorǁshould_apply_backpressure__mutmut_4,5,13` |
| C6 | `recover_orphaned_detections`: WHERE/join predicate & cutoff operators (`-`→`+` timedelta, `now(UTC)`→`now(None)`, join cond→None/`!=`, `is_(None)`→None/dropped, `<` dropped, `<`→`<=`) | 10 | **TEST-GAP** | `x_recover_orphaned_detections__mutmut_2,10,19` |
| C7 | `recover`: SELECT pipeline structural (stmt→None, `select(None)`, `.limit(None)`, `.order_by(None)`, `execute(None)`) | 5 | **TEST-GAP** | `x_recover_orphaned_detections__mutmut_6,7,31` |
| C8 | `recover`: `load_only(...)` projection entries dropped (id/camera_id/file_path/confidence/object_type) | 5 | **TEST-GAP** | `x_recover_orphaned_detections__mutmut_25,27,29` |
| C9 | `recover`: `add_detection(...)` kwargs clobbered (`_file_path/confidence/object_type`→None or dropped) | 6 | **TEST-GAP** | `x_recover_orphaned_detections__mutmut_42,44,49` |
| C10 | `recover`: logger message/extra text + `exc_info` across 3 log sites | 45 | EQUIVALENT | `x_recover_orphaned_detections__mutmut_57,67,91` |
| C11 | `_close_batch_for_size_limit`: `lrange(detections_key, 0, -1)` args mutated (key→None/dropped; 0→None/1; -1→None/+1/-2/dropped) | 10 | **TEST-GAP** | `xǁBatchAggregatorǁ_close_batch_for_size_limit__mutmut_25,28,34` |
| C12 | `_close_batch_for_size_limit`: `delete(...)` 7-key cleanup list entries →None/dropped | 14 | **TEST-GAP** | `xǁ...ǁ_close_batch_for_size_limit__mutmut_118,124,131` |
| C13 | `_close_batch_for_size_limit`: closing-flag stored value `"1"`→None/dropped/`"XX1XX"` | 3 | **TEST-GAP** | `xǁ...ǁ_close_batch_for_size_limit__mutmut_19,22,24` |
| C14 | `_close_batch_for_size_limit`: summary dict keys `started_at`/`ended_at` renamed (XX/case) | 4 | **TEST-GAP** | `xǁ...ǁ_close_batch_for_size_limit__mutmut_60,61,63` |
| C15 | `_close_batch_for_size_limit`: `started_at` fetch/truthiness (get→None, key→None, `if (s) and False` / `if (s) or True`) | 4 | **TEST-GAP** | `xǁ...ǁ_close_batch_for_size_limit__mutmut_44,49,50` |
| C16 | `_close_batch_for_size_limit`: queue identity/policy (`self._analysis_queue`→None, `overflow_policy=QueueOverflowPolicy.DLQ`→None/dropped) | 3 | **TEST-GAP** | `xǁ...ǁ_close_batch_for_size_limit__mutmut_72,74,77` |
| C17 | `_close_batch_for_size_limit`: `_broadcast_detection_batch` kwargs (batch_id/camera_id/started_at/closed_at→None, close_reason→None/dropped/XX/MAX_SIZE) | 8 | **TEST-GAP** | `xǁ...ǁ_close_batch_for_size_limit__mutmut_136,141,148` |
| C18 | `_close_batch_for_size_limit`: `log_context(batch_id=, camera_id=)` correlation args →None/dropped | 4 | LOW-VALUE | `xǁ...ǁ_close_batch_for_size_limit__mutmut_14,16,17` |
| C19 | `_close_batch_for_size_limit`: bytes decode `"utf-8"`→`"UTF-8"` | 1 | EQUIVALENT | `xǁ...ǁ_close_batch_for_size_limit__mutmut_41` |
| C20 | `_close_batch_for_size_limit`: `batch_duration_ms` arithmetic (None, /1000, +-swap, *1001) — feeds only a logger extra | 4 | EQUIVALENT | `xǁ...ǁ_close_batch_for_size_limit__mutmut_95,96,98` |
| C21 | `_close_batch_for_size_limit`: logger message/extra text across 5 log sites (camera-not-found, queue-overflow, Batch closed, no-detections, cleanup) | 45 | EQUIVALENT | `xǁ...ǁ_close_batch_for_size_limit__mutmut_9,82,103` |

Totals: TEST-GAP 74 (C1,C3,C6–C9,C11–C17) · EQUIVALENT 125 (C2,C4,C5,C10,C19,C20,C21) · LOW-VALUE 4 (C18).

## Classification notes (evidence)

- **C1/C3** — `test_set_gpu_monitor` (test_batch_aggregator.py:1632) literally comments "we can't directly access _gpu_monitor... function should complete without error" — zero asserts. `get_memory_pressure_level` has tests only for `_gpu_monitor=None` (:1647) and raises (:1668); no test with a *working* monitor, so inverted guard C3 returns NORMAL on a path nothing exercises.
- **C5/C2/C4/C10/C21** — verified every key in these buckets mutates only string/extra/exc_info inside `logger.*(...)` calls; the decision-bearing lines (`== MemoryPressureLevel.CRITICAL`, `return should_throttle/False`, return counts) all have *killed* siblings (e.g. `should_apply_backpressure__mutmut_1,3` were killed), proving the bool contract is asserted while payloads aren't. Existing log tests use case-insensitive substring checks (`test_batch_aggregator.py:2106`, :3120) that case/XX mutants pass.
- **C13** — no code anywhere reads `batch:<id>:closing` (grep: only the set + the delete-list entry). Kept TEST-GAP *narrowly* because the adjacent TTL test (:3646) already asserts `call_args[0]`/`ex` — the *value* is the same call's unasserted `call_args[1]`, a one-line fix. If the team prefers "behavior nobody should assert", reclassify LOW-VALUE; the drafted test covers it either way.
- **C14/C15/C16** — the summary dict is pushed to the analysis queue (Redis) and consumed by the analyzer; payload-contract mutants renamed/zeroed keys nobody asserts. Closest tests assert `batch_id/camera_id/detection_ids/reason/pipeline_start_time` (:1955-2039) — `started_at`/`ended_at`, queue name, and `overflow_policy=DLQ` are never checked.
- **C12** — strongest real bug: dropping `f"batch:{camera_id}:current"` from the delete list leaves a stale pointer that blocks new batches for the camera; existing delete-key assertions (:1533, :3531) hit `close_batch`, not `_close_batch_for_size_limit`.
- **C17** — `grep -r "_broadcast_detection_batch" backend/tests/` → zero hits; WS payload entirely unasserted.
- **C18** — log_context feeds only later records' correlation fields; no functional consumer → LOW-VALUE (not worth a contextvar-peeking test).
- **C20** — `batch_duration_ms` appears only in the `logger.info("Batch closed", extra=...)` payload; not in summary, not in a metric.

## Drafted tests (6) — UNVERIFIED - not yet run red/green

TDD procedure for each: run the new test against the mutant copy for an example key of its cluster → expect FAIL (assertion mismatch on the mutated line); run against original `backend/services/batch_aggregator.py` → expect PASS.

### T1 — `test_recover_orphaned_detections_forwards_all_detection_fields` (kills C9, 6 mutants)

Target file: `backend/tests/unit/services/test_orphan_recovery.py`

```python
    @pytest.mark.asyncio
    async def test_recover_orphaned_detections_forwards_all_detection_fields(self) -> None:
        """NEM-orphan-fields: re-injection must forward the full detection record.

        add_detection receives _file_path/confidence/object_type from the
        Detection row; clobbering any of them to None (mutants 42-44, 47-49)
        silently degrades downstream enrichment/batch metadata.
        """
        orphans = [
            _make_detection(7, "cam_front", minutes_ago=10),
        ]

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = orphans
        mock_session.execute = AsyncMock(return_value=mock_result)

        mock_aggregator = AsyncMock()
        mock_aggregator.add_detection = AsyncMock(return_value="batch-abc12345")

        with patch(
            "backend.core.database.get_session",
            return_value=_mock_session_ctx(mock_session),
            autospec=True,
        ):
            count = await recover_orphaned_detections(mock_aggregator)

        assert count == 1
        kwargs = mock_aggregator.add_detection.call_args.kwargs
        assert kwargs["camera_id"] == "cam_front"
        assert kwargs["detection_id"] == 7
        # The fields mutants 42/43/44 set to None and 47/48/49 drop entirely:
        assert kwargs["_file_path"] == orphans[0].file_path
        assert kwargs["confidence"] == orphans[0].confidence
        assert kwargs["object_type"] == orphans[0].object_type
```

### T2 — `test_recover_orphaned_query_targets_orphans_with_limit_and_order` (kills C6 [2,3,9,10,11,12,14,16,18,19] + C7 [5,6,7,17,31], 15 mutants)

Target file: `backend/tests/unit/services/test_orphan_recovery.py` (needs `from sqlalchemy.dialects import postgresql`, `import re`)

```python
    @pytest.mark.asyncio
    async def test_recover_orphaned_query_targets_orphans_with_limit_and_order(self) -> None:
        """NEM-orphan-query: the orphan SELECT must be an outer-join to event_detections
        with IS NULL, a strict cutoff, oldest-first order and a LIMIT.

        All sibling tests stub session.execute, so the built statement is never
        observed. This test captures the statement and compiles it with literal
        binds, pinning the orphan-set contract (mutants 2,3,5,6,7,9-12,14,16-19,31).
        """
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch(
            "backend.core.database.get_session",
            return_value=_mock_session_ctx(mock_session),
            autospec=True,
        ):
            await recover_orphaned_detections(AsyncMock())

        stmt = mock_session.execute.call_args[0][0]
        sql = str(
            stmt.compile(
                dialect=postgresql.dialect(),
                compile_kwargs={"literal_binds": True},
            )
        )

        # Orphan set: detections LEFT JOIN event_detections ON id = detection_id
        assert "OUTER JOIN event_detections" in sql
        assert "detections.id = event_detections.detection_id" in sql
        assert "event_id IS NULL" in sql
        # Freshness cutoff, strict <, evaluated against a time in the PAST
        assert "detected_at < " in sql
        ts = re.search(r"detected_at < '?(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", sql)
        assert ts is not None, f"no cutoff literal in: {sql}"
        cutoff = datetime.fromisoformat(ts.group(1))
        naive_now = datetime.now(UTC).replace(tzinfo=None)
        assert cutoff < naive_now, "cutoff must be before now (mutant flips - to +)"
        assert cutoff > naive_now - timedelta(minutes=2 * ORPHAN_MIN_AGE_MINUTES), (
            "cutoff must be timezone-aware-derived (now(None) mutant yields naive drift guard)"
        )
        # Oldest first, capped
        assert "ORDER BY detections.detected_at ASC" in sql
        assert f"LIMIT {ORPHAN_RECOVERY_LIMIT}" in sql
```

### T3 — `test_close_batch_for_size_limit_redis_interaction_contract` (kills C11 [10] + C12 [14] + C13 [3], 27 mutants)

Target file: `backend/tests/unit/services/test_batch_aggregator.py`

```python
@pytest.mark.asyncio
async def test_close_batch_for_size_limit_redis_interaction_contract(
    batch_aggregator, mock_redis_instance
):
    """NEM-1726/NEM-2013/NEM-2507: pin the Redis interaction contract of the size-limit
    close path — full-list lrange, closing flag value "1", and the complete
    7-key cleanup delete (mutants 25-35, 118-131, 19/22/24 leak keys or skip reads).
    """
    batch_id = "batch_redis_contract"
    camera_id = "front_door"

    async def mock_get(key):
        if key == f"batch:{batch_id}:camera_id":
            return camera_id
        elif key == f"batch:{batch_id}:started_at":
            return str(time.time() - 60)
        return None

    mock_redis_instance.get.side_effect = mock_get
    mock_redis_instance._client.lrange.return_value = [b"1", b"2"]

    await batch_aggregator._close_batch_for_size_limit(batch_id)

    # Read the whole detections list (key + full range 0..-1), not a prefix.
    mock_redis_instance._client.lrange.assert_called_once_with(
        f"batch:{batch_id}:detections", 0, -1
    )

    # Closing flag carries value "1" alongside the TTL already asserted elsewhere.
    closing_calls = [
        call
        for call in mock_redis_instance._client.set.call_args_list
        if f"batch:{batch_id}:closing" in str(call)
    ]
    assert closing_calls
    assert closing_calls[0].args[1] == "1"

    # Cleanup deletes exactly the batch key set — any dropped/None entry leaks keys.
    deleted = set()
    for call in mock_redis_instance.delete.call_args_list:
        deleted.update(k for k in call.args if k)
    assert {
        f"batch:{camera_id}:current",
        f"batch:{batch_id}:camera_id",
        f"batch:{batch_id}:detections",
        f"batch:{batch_id}:started_at",
        f"batch:{batch_id}:last_activity",
        f"batch:{batch_id}:pipeline_start_time",
        f"batch:{batch_id}:closing",
    } <= deleted
```

### T4 — `test_close_batch_for_size_limit_queue_payload_contract` (kills C14 [4] + C15 [4] + C16 [3], 11 mutants)

Target file: `backend/tests/unit/services/test_batch_aggregator.py`

```python
@pytest.mark.asyncio
async def test_close_batch_for_size_limit_queue_payload_contract(
    batch_aggregator, mock_redis_instance
):
    """NEM-1726: the analysis-queue payload is a contract with the analyzer —
    correct queue, DLQ overflow policy, and full summary schema (started_at
    resolved from Redis, ended_at present, keys un-renamed).
    Mutants 44/45/49/50 drop the stored start; 60-63 rename keys; 72/74/77 reroute.
    """
    batch_id = "batch_payload_contract"
    camera_id = "front_door"
    started_at = time.time() - 60

    async def mock_get(key):
        if key == f"batch:{batch_id}:camera_id":
            return camera_id
        elif key == f"batch:{batch_id}:started_at":
            return str(started_at)
        return None

    mock_redis_instance.get.side_effect = mock_get
    mock_redis_instance._client.lrange.return_value = ["1", "2"]

    await batch_aggregator._close_batch_for_size_limit(batch_id)

    queue_call = mock_redis_instance.add_to_queue_safe.call_args
    assert queue_call.args[0] == batch_aggregator._analysis_queue, "must target the analysis queue"
    assert queue_call.kwargs["overflow_policy"] == QueueOverflowPolicy.DLQ

    summary = queue_call.args[1]
    assert summary["started_at"] == started_at, "stored started_at must be used, not time.time()"
    assert "ended_at" in summary and summary["ended_at"] >= summary["started_at"]
    assert set(summary) >= {
        "batch_id",
        "camera_id",
        "detection_ids",
        "started_at",
        "ended_at",
        "reason",
    }
```

### T5 — `test_close_batch_for_size_limit_broadcasts_complete_batch_event` (kills C17, 8 mutants)

Target file: `backend/tests/unit/services/test_batch_aggregator.py`

```python
@pytest.mark.asyncio
async def test_close_batch_for_size_limit_broadcasts_complete_batch_event(
    batch_aggregator, mock_redis_instance
):
    """NEM-2506: the WebSocket detection.batch event must carry real batch fields;
    None/garbage payload (mutants 136,137,139,140,141,147,148,149) corrupts the live UI.
    """
    batch_id = "batch_ws_contract"
    camera_id = "front_door"

    async def mock_get(key):
        if key == f"batch:{batch_id}:camera_id":
            return camera_id
        elif key == f"batch:{batch_id}:started_at":
            return str(time.time() - 60)
        return None

    mock_redis_instance.get.side_effect = mock_get
    mock_redis_instance._client.lrange.return_value = [b"5", b"6"]

    with patch.object(
        batch_aggregator, "_broadcast_detection_batch", autospec=True
    ) as broadcast:
        await batch_aggregator._close_batch_for_size_limit(batch_id)

    broadcast.assert_called_once()
    kwargs = broadcast.call_args.kwargs
    assert kwargs["batch_id"] == batch_id
    assert kwargs["camera_id"] == camera_id
    assert kwargs["detection_ids"] == [5, 6]
    assert isinstance(kwargs["started_at"], float)
    assert isinstance(kwargs["closed_at"], float)
    assert kwargs["close_reason"] == "max_size"
```

### T6 — `test_set_gpu_monitor_wires_global` + `test_get_memory_pressure_level_queries_monitor_when_set` (kills C1 + C3, 2 mutants)

Target file: `backend/tests/unit/services/test_batch_aggregator.py`

```python
@pytest.mark.asyncio
async def test_set_gpu_monitor_wires_global():
    """set_gpu_monitor must actually wire the module-level monitor (mutant 1 sets None)."""
    import backend.services.batch_aggregator as module
    from backend.services.batch_aggregator import set_gpu_monitor

    original = module._gpu_monitor
    try:
        module._gpu_monitor = None
        monitor = MagicMock()
        set_gpu_monitor(monitor)
        assert module._gpu_monitor is monitor
    finally:
        module._gpu_monitor = original


@pytest.mark.asyncio
async def test_get_memory_pressure_level_queries_monitor_when_set():
    """With a working monitor attached, the check must be awaited and its level
    returned — the inverted guard (mutant 1) skips the monitor and forces NORMAL.
    """
    import backend.services.batch_aggregator as module
    from backend.services.batch_aggregator import get_memory_pressure_level
    from backend.services.gpu_monitor import MemoryPressureLevel

    monitor = MagicMock()
    monitor.check_memory_pressure = AsyncMock(return_value=MemoryPressureLevel.CRITICAL)
    original = module._gpu_monitor
    try:
        module._gpu_monitor = monitor
        pressure = await get_memory_pressure_level()
        assert pressure == MemoryPressureLevel.CRITICAL
        monitor.check_memory_pressure.assert_awaited_once()
    finally:
        module._gpu_monitor = original
```

## Kill coverage of drafts

T1–T6 target all 74 TEST-GAP mutants: T1→C9(6), T2→C6+C7(15), T3→C11+C12+C13(27), T4→C14+C15+C16(11), T5→C17(8), T6→C1+C3(2). T2's cutoff-sign asserts (regex on literal-bound SQL) are the only draft assertions I'd flag as potentially needing a dialect tweak at red/green time; everything else asserts plain mock call-args or module globals.
