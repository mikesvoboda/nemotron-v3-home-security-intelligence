# WP4.4 Triage Dossier — `backend/services/pipeline_workers.py`

Generated: 2026-09-18 (WP4.3 finding feed → WP4.4). UNVERIFIED: no tests were run; this is read-only triage.

## Data provenance

- Verdicts: `mutants/backend/services/pipeline_workers.py.meta` (`exit_code_by_key`).
  **1648 keys total: 282 survived (exit 0, triaged here), 75 killed, 1291 null (not yet checked).**
- Diffs: `uv run mutmut show <key>` for all 282 survivors (all fetched; one key re-fetched once — `process_video_detection__mutmut_99`).
- Survivor keys cached: `/tmp/wp25/wp44-triage/.pw_survivors.txt`; parsed diffs `.pw_parsed.json`; cluster→key map `.pw_clusters.json` (verified: 282 assigned, 0 dupes, 0 unassigned).
- Survivors live in 4 functions: `_process_analysis_item` (195), `_process_video_detection` (79), `x_drain_queues` module-level (5), `AnalysisQueueWorker._get_broadcaster` (3).

## Covering test files (from `mutants/mutmut-stats.json` → `tests_by_mangled_function_name`)

| Function                      | File (tests)                                                                                                                                                                                                                                                                                              |
| ----------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `_process_analysis_item`      | `backend/tests/unit/services/test_pipeline_workers.py` (7 tests: `test_analysis_worker_processes_batch` :807, `test_analysis_worker_handles_value_error` :846, `test_analysis_worker_handles_invalid_item` :878, `test_analysis_worker_general_exception_handling` :914, latency tests :2398/:2450/:2495) |
| `_get_broadcaster`            | same file (same 7 tests)                                                                                                                                                                                                                                                                                  |
| `_process_video_detection`    | same file (`test_detection_worker_processes_video_item` :1874, `..._handles_video_with_no_frames` :1936, `..._detector_unavailable_during_frames` :2662, `..._frame_exception_continues` :2751, `..._with_detector_unavailable_exception` :3063)                                                          |
| `drain_queues` (module-level) | `backend/tests/unit/test_shutdown_cleanup.py` (:128–241, manager-level only — the module-level wrapper's `if _pipeline_manager is None` branch is what executes; the `timeout=30.0` default line runs but is never asserted)                                                                              |

Root causes of the gaps: (a) no test injects a broadcaster, so the entire NEM-3607 `broadcast_batch_analysis_{started,completed,failed}` payload region (lines ~1022–1186) executes only under `broadcaster=None` and payload dicts are never inspected; (b) latency is asserted only as `latency_ms >= 0` and stage labels are filtered but never equality-checked; (c) existing video tests mock the retry handler **without invoking the operation closure** and never assert `add_detection`/`detect_objects` kwargs; (d) counters asserted only via `>= min_count` waits + `== 1` on a single item.

## Cluster table (counts sum to 282)

Key prefix `P.` = `backend.services.pipeline_workers.`; `AI` = `xǁAnalysisQueueWorkerǁ_process_analysis_item`, `GB` = `xǁAnalysisQueueWorkerǁ_get_broadcaster`, `VD` = `xǁDetectionQueueWorkerǁ_process_video_detection`, `DQ` = `x_drain_queues`. Example keys ≤3 per cluster; full lists in `.pw_clusters.json`.

| ID              | Pattern                                                                                                                                                                                                                                                                                                                   | N   | Class      | Examples (P.…\__mutmut_) | Notes                                                                                                                                                                                                                                                      |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --- | ---------- | ------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| PW-STATS        | stats counter arithmetic `errors += 1`→`-=1/+=2/=1`, `items_processed +=1`→`=1`, `last_processed_at=time.time()`→`None`                                                                                                                                                                                                   | 6   | TEST-GAP   | AI.8, AI.9, AI.83        | existing tests use `wait_for_errors(min_count=1)` + `== 1`; assign-to-1 survives single-item runs → need 2+ items on same branch (test 5). `last_processed_at=None` never asserted. Kill: test 5.                                                          |
| PW-METRIC-LABEL | `record_pipeline_error("invalid_analysis_payload")` label→None/XX/UPPERCASE                                                                                                                                                                                                                                               | 3   | TEST-GAP   | AI.11, AI.12, AI.13      | :914 asserts the sibling label `"analysis_batch_error"` but the invalid-payload label is never asserted. Kill: test 5.                                                                                                                                     |
| PW-LOGMSG       | analysis-path log message text → `None`/`""` (9 log/exception msg sites)                                                                                                                                                                                                                                                  | 9   | EQUIVALENT | AI.14, AI.52, AI.141     | pure human-readable text; behavior identical.                                                                                                                                                                                                              |
| PW-LOGEXTRA     | `extra={...}` dict→None/removed, `exc_info=True`→False/None                                                                                                                                                                                                                                                               | 11  | LOW-VALUE  | AI.15, AI.142, AI.211    | log enrichment only; no consumer asserts it.                                                                                                                                                                                                               |
| PW-LOGKEY       | log `extra` dict keys renamed XX/UPPERCASE (16 sites)                                                                                                                                                                                                                                                                     | 16  | LOW-VALUE  | AI.18, AI.145, AI.149    | structured-log key names; no test inspects record.extra.                                                                                                                                                                                                   |
| PW-LOGVAL       | log extra value clobber (`str(None)`, `[:500]`→`[:501]`)                                                                                                                                                                                                                                                                  | 3   | LOW-VALUE  | AI.20, AI.21, AI.24      | truncation bound is only a log-injection guard (log-only).                                                                                                                                                                                                 |
| PW-LOGCTX       | `log_context(batch_id=…, camera_id=…, operation="analysis")` kwargs clobbered                                                                                                                                                                                                                                             | 8   | LOW-VALUE  | AI.25, AI.27, AI.31      | log correlation enrichment.                                                                                                                                                                                                                                |
| PW-SPANNAME     | `tracer.start_as_current_span("analysis_processing")` name clobber                                                                                                                                                                                                                                                        | 3   | LOW-VALUE  | AI.33, AI.34, AI.35      | otel span name; no span-name assertion anywhere.                                                                                                                                                                                                           |
| PW-SPANATTR     | `span_attrs` dict (batch_id/detection_count/pipeline_stage/camera conditional) keys/values flipped                                                                                                                                                                                                                        | 14  | LOW-VALUE  | AI.37, AI.41, AI.48      | `if camera_id is not None`→`is None` changes only which attributes land on the trace; low external visibility.                                                                                                                                             |
| WS-A            | NEM-3607 broadcaster **acquisition + emission gating**: `broadcaster = await self._get_broadcaster()`→`None`, whole payload dict→`None` (started/completed/failed), `_get_broadcaster` lazy-init flips (`is None`→`is not None`, cache-assign→None, `get_broadcaster(self._redis)`→`(None)`)                              | 8   | TEST-GAP   | GB.1, GB.2, AI.57        | no test injects a broadcaster; whole region runs unobserved. GB.1 survives only because lazy-cache 2nd-call path is never exercised — test 1 calls the item twice. Kill: test 1.                                                                           |
| WS-B            | NEM-3607 payload **key names** renamed/UPPERCASE across all three broadcast dicts (48 sites)                                                                                                                                                                                                                              | 48  | TEST-GAP   | AI.59, AI.170, AI.232    | wire-format contract with the UI (event_broadcaster consumers); one `set(payload) == {...}` test kills the whole family. Kill: test 1 (key-set asserts).                                                                                                   |
| WS-C            | NEM-3607 payload **values**: `risk_level_str` default/enum-`.value`/`str()` chain, `error_type`/`retryable` categorization (`categorize_exception` args, `.replace("analysis_","")`, `in (...)`→`not in`), `camera_id or ""`→`and ""`, `retryable: False`→`True`, `str(e)[:500]` truncation, `datetime.now(UTC)`→`(None)` | 50  | TEST-GAP   | AI.151, AI.199, AI.230   | UI decides retry affordance from `retryable`/`error_type` — real behavior, zero assertions. Kill: test 2. Residue: `datetime.now(None)` sites (naive dt still isoformats), `categorize_exception(None, …)` (AI.220 — returns identical default).           |
| LAT-A           | latency stage labels `"batch_to_analyze"` / `"analyze"` clobbered (None/XX/UPPERCASE)                                                                                                                                                                                                                                     | 6   | TEST-GAP   | AI.90, AI.94, AI.97      | :2398 filters `total_pipeline` calls but never asserts the other two labels — the labels are the API contract of `/api/system/pipeline-latency` + telemetry. Kill: test 3.                                                                                 |
| LAT-B           | duration arithmetic: `time()-start`→`time()+start`, `int(d*1000)`→`/1000`/`*1001`/`None`, total sec→ms `/1000`, values→None                                                                                                                                                                                               | 8   | TEST-GAP   | AI.85, AI.88, AI.117     | existing assertion is only `latency_ms >= 0`; range-bounded asserts (sleep-20ms floor, 5s-floor) kill the sign/scale clobbers. Residue: `×1001` (AI.89/AI.120) differ by 0.1% — undetectable without clock mocking. Kill: tests 3 (+ total_pipeline part). |
| LAT-C           | `pipeline_start_time.replace("Z", "+00:00")` — Z-suffix (Zulu) ISO normalization                                                                                                                                                                                                                                          | 3   | TEST-GAP   | AI.110, AI.111, AI.112   | every latency test feeds `datetime.now().isoformat()` (no `Z`) so the `replace` never fires. Kill: test 4 kills AI.112; AI.110/111 are runtime-equivalents on py≥3.11 (`fromisoformat` accepts `Z` natively) — note for the ledger.                        |
| PW-RECEX        | `record_exception(e)`→`record_exception(None)` (telemetry, 2 sites)                                                                                                                                                                                                                                                       | 2   | LOW-VALUE  | AI.181, AI.209           | otel exception attribute only.                                                                                                                                                                                                                             |
| WS-B→ note      | (folded into WS-B above)                                                                                                                                                                                                                                                                                                  |     |            |                          |                                                                                                                                                                                                                                                            |
| VD-EXTRACT      | `extract_frames_for_detection_batch(video_path=…, interval_seconds=self._video_frame_interval, max_frames=self._video_max_frames)` kwargs→None/removed                                                                                                                                                                    | 6   | TEST-GAP   | VD.10, VD.11, VD.12      | existing tests assert `assert_called_once()` only — extraction interval/max-frames config silently ignored is a real behavior change. Kill: test 6.                                                                                                        |
| VD-DETECT       | per-frame `detect_objects(image_path=fp, camera_id=…, session=…, video_path=…, video_metadata=…)` kwargs clobbered incl. **closure binding** `current_frame = frame_path`→`None`; `get_video_metadata(video_path)`→None                                                                                                   | 13  | TEST-GAP   | VD.31, VD.32, VD.29      | the loop-closure fix ("capture frame_path in a closure") is unasserted: mock retry handler never invokes `operation`. Test 6 calls the captured `operation()` and asserts `image_path == frame[i]`. Kill: test 6.                                          |
| VD-RETRY        | `with_retry(job_data=job_data, queue_name=self._queue_name)`→None                                                                                                                                                                                                                                                         | 2   | TEST-GAP   | VD.44, VD.45             | DLQ routing metadata for failed video jobs. Kill: test 6.                                                                                                                                                                                                  |
| VD-AGG          | `add_detection(camera_id=…, detection_id=…, _file_path=video_path, confidence=…, object_type=…, pipeline_start_time=…)` kwargs→None/removed + `detections = result.result or []`→`None`/`and []` (forwards nothing / crashes per frame)                                                                                   | 14  | TEST-GAP   | VD.71, VD.77, VD.67      | video tests :2662/:2751 assert only cleanup+raise, never `add_detection` kwargs; `_file_path` must be the VIDEO path not frame (comment in source). Full-kwargs equality assert kills the family. Kill: test 6.                                            |
| VD-LOGMSG       | video-path log/exception message text→None/`""` (incl. the `raise DetectorUnavailableError(f"…")` message and the 2-line success f-string)                                                                                                                                                                                | 5   | EQUIVALENT | VD.1, VD.87, VD.88       | messages only; error type/raise unchanged.                                                                                                                                                                                                                 |
| VD-LOGEXTRA     | video-path `extra=` payload clobbered (8 sites)                                                                                                                                                                                                                                                                           | 8   | LOW-VALUE  | VD.2, VD.51, VD.89       | log enrichment.                                                                                                                                                                                                                                            |
| VD-LOGKEY       | video-path log extra keys XX/UPPERCASE (26 sites incl. final `"detection_count"`→`"DETECTION_COUNT"`)                                                                                                                                                                                                                     | 26  | LOW-VALUE  | VD.5, VD.93, VD.99       | no log-schema test exists for this module.                                                                                                                                                                                                                 |
| VD-TOTAL        | `total_detections` / `detector_failed` init arithmetic (`0`→`1`/`None`, `+=`→`=`/`-=`) — visible only in the final log line                                                                                                                                                                                               | 4   | LOW-VALUE  | VD.25, VD.26, VD.81      | no functional consumer of the tally.                                                                                                                                                                                                                       |
| VD-EQ           | `detector_failed = False`→`None` (both falsy; the `if detector_failed:` gate unchanged)                                                                                                                                                                                                                                   | 1   | EQUIVALENT | VD.27                    |                                                                                                                                                                                                                                                            |
| DQ-DEFAULT      | module-level `drain_queues(timeout: float = 30.0)`→`31.0`                                                                                                                                                                                                                                                                 | 1   | LOW-VALUE  | DQ.1                     | the only caller (shutdown) passes an explicit timeout; default never asserted. Candidate for kill via signature test if the 30s shutdown budget is considered contractual.                                                                                 |
| DQ-LOGMSG       | `logger.debug("Pipeline manager not initialized…")` text clobber (4 variants)                                                                                                                                                                                                                                             | 4   | EQUIVALENT | DQ.3, DQ.4, DQ.5, DQ.6   | `test_shutdown_cleanup.py:221` runs the wrapper but asserts only return value.                                                                                                                                                                             |

**Classification totals: TEST-GAP 167 / LOW-VALUE 96 / EQUIVALENT 19.**

## Drafted tests (6) — target file `backend/tests/unit/services/test_pipeline_workers.py`

TDD procedure (same for all six): apply the cluster's mutant diff → the named asserts below fail (red); revert to the original source → they pass (green).
**// UNVERIFIED - not yet run red/green** (per WP4.3 constraints, nothing was executed).

All tests reuse existing fixtures (`mock_redis_client`, `mock_analyzer`) and the file's local-import style. They call `worker._process_analysis_item(...)` / `worker._process_video_detection(...)` directly (pattern established at :2662/:2751), so no event-loop waits are needed.

### Test 1 — kills WS-A + WS-B (and several WS-C key/value sites)

```python
# =============================================================================
# WP4.4 mutant-killing candidates (pipeline_workers)  // UNVERIFIED - not yet run red/green
# =============================================================================


@pytest.mark.asyncio
async def test_analysis_worker_broadcasts_batch_analysis_events_with_full_payload(
    mock_redis_client, mock_analyzer
):
    """NEM-3607: started/completed broadcasts must fire with the exact payload schema.

    Kills WS-A (broadcaster acquisition + emission gating) and WS-B (payload key
    renames). No existing test injects a broadcaster, so this whole region ran
    unobserved.
    """
    mock_broadcaster = MagicMock()
    mock_broadcaster.broadcast_batch_analysis_started = AsyncMock(return_value=1)
    mock_broadcaster.broadcast_batch_analysis_completed = AsyncMock(return_value=1)
    mock_broadcaster.broadcast_batch_analysis_failed = AsyncMock(return_value=1)

    worker = AnalysisQueueWorker(redis_client=mock_redis_client, analyzer=mock_analyzer)
    item = {"batch_id": "batch_ws1", "camera_id": "front_door", "detection_ids": [1, 2, 3]}

    with patch(
        "backend.services.event_broadcaster.get_broadcaster",
        new=AsyncMock(return_value=mock_broadcaster),
    ) as mock_get_bc:
        await worker._process_analysis_item(item)
        # Second item exercises the lazy cache: get_broadcaster fetched once,
        # broadcasts still fire per item (kills the is-None-flip lazy-init mutants).
        await worker._process_analysis_item(item)

    mock_get_bc.assert_called_once_with(worker._redis)
    assert mock_broadcaster.broadcast_batch_analysis_failed.call_count == 0

    assert mock_broadcaster.broadcast_batch_analysis_started.call_count == 2
    started = mock_broadcaster.broadcast_batch_analysis_started.call_args.args[0]
    assert set(started) == {
        "batch_id", "camera_id", "detection_count", "queue_position", "started_at",
    }
    assert started["batch_id"] == "batch_ws1"
    assert started["camera_id"] == "front_door"
    assert started["detection_count"] == 3
    assert started["queue_position"] == 0
    datetime.fromisoformat(started["started_at"])

    assert mock_broadcaster.broadcast_batch_analysis_completed.call_count == 2
    completed = mock_broadcaster.broadcast_batch_analysis_completed.call_args.args[0]
    assert set(completed) == {
        "batch_id", "camera_id", "event_id", "risk_score", "risk_level",
        "duration_ms", "completed_at",
    }
    assert completed["batch_id"] == "batch_ws1"
    assert completed["event_id"] == 1
    assert completed["risk_score"] == 50
    assert completed["risk_level"] == "medium"  # mock_analyzer event risk_level
    assert isinstance(completed["duration_ms"], int)
    datetime.fromisoformat(completed["completed_at"])
```

TDD: on WS-A mutants (broadcaster→None / dict→None) the `call_count == 2` asserts fail; on every WS-B rename the `set(...)` equality fails; original passes.

### Test 2 — kills WS-C (payload values: risk_level chain, error_type/retryable, truncation)

```python
@pytest.mark.asyncio
async def test_analysis_worker_broadcast_payloads_classify_risk_level_and_errors(
    mock_redis_client, mock_analyzer
):
    """NEM-3607 payload VALUES: risk_level default/enum chain, error_type, retryable.

    Kills WS-C: risk_level_str chain (AI.151-162), categorize/replace chain
    (AI.215-230), validation-vs-analysis failed payloads (AI.183-202, 236-241).
    """
    mock_broadcaster = MagicMock()
    mock_broadcaster.broadcast_batch_analysis_started = AsyncMock(return_value=1)
    mock_broadcaster.broadcast_batch_analysis_completed = AsyncMock(return_value=1)
    mock_broadcaster.broadcast_batch_analysis_failed = AsyncMock(return_value=1)

    enum_like = MagicMock()
    enum_like.value = "high"
    event_enum = MagicMock()
    event_enum.id = 41
    event_enum.risk_score = 90
    event_enum.risk_level = enum_like

    event_nolvl = MagicMock()
    event_nolvl.id = 42
    event_nolvl.risk_score = 10
    event_nolvl.risk_level = None  # -> default "low"

    long_error = RuntimeError("analysis blew up: " + ("x" * 600))

    mock_analyzer.analyze_batch = AsyncMock(
        side_effect=[
            event_enum,                       # completed, risk_level from .value
            event_nolvl,                      # completed, risk_level default "low"
            ValueError("Batch not found"),    # validation failed payload
            long_error,                       # processing_error, truncated error
            RuntimeError("boom retry"),       # second generic -> errors == 2
        ]
    )
    worker = AnalysisQueueWorker(redis_client=mock_redis_client, analyzer=mock_analyzer)
    item = {"batch_id": "b_ws", "camera_id": "cam1", "detection_ids": [1]}

    with patch(
        "backend.services.event_broadcaster.get_broadcaster",
        new=AsyncMock(return_value=mock_broadcaster),
    ):
        for _ in range(5):
            await worker._process_analysis_item(item)

    completed = mock_broadcaster.broadcast_batch_analysis_completed.call_args_list
    assert [c.args[0]["risk_level"] for c in completed] == ["high", "low"]
    assert [c.args[0]["event_id"] for c in completed] == [41, 42]

    failed = mock_broadcaster.broadcast_batch_analysis_failed.call_args_list
    assert len(failed) == 3
    validation = failed[0].args[0]
    assert set(validation) == {
        "batch_id", "camera_id", "error", "error_type", "retryable", "failed_at",
    }
    assert validation["error"] == "Batch not found"
    assert validation["error_type"] == "validation"
    assert validation["retryable"] is False

    processing = failed[1].args[0]
    assert processing["error_type"] == "processing_error"
    assert processing["retryable"] is False
    assert len(processing["error"]) == 500  # str(e)[:500] truncation contract

    assert worker.stats.errors == 2  # exactly one per generic exception (kills =1 mutants)
```

TDD: `risk_level` list assert fails on 151-162 chain mutants (incl. the `is not None` flip); `error_type`/`retryable` asserts fail on 215-230 (incl. `not in` flip → `True`); `len(error) == 500` fails on `[:501]` (241) and `str(None)` (240); `errors == 2` fails on `errors = 1` (203).

### Test 3 — kills LAT-A + LAT-B

```python
@pytest.mark.asyncio
async def test_analysis_worker_records_stage_latency_values(mock_redis_client, mock_analyzer):
    """batch_to_analyze/analyze stage labels and duration_ms arithmetic values.

    Kills LAT-A (label clobbers) and LAT-B (sub->add, *1000 -> /1000/None).
    Existing tests filter by label but never equality-check the other two stages
    and assert only latency >= 0.
    """
    async def slow_analyze(*args, **kwargs):
        await asyncio.sleep(0.02)
        return mock_analyzer.analyze_batch.return_value

    mock_analyzer.analyze_batch = AsyncMock(side_effect=slow_analyze)
    worker = AnalysisQueueWorker(redis_client=mock_redis_client, analyzer=mock_analyzer)

    from datetime import UTC, timedelta

    start_iso = (datetime.now(UTC) - timedelta(seconds=5)).isoformat()
    item = {
        "batch_id": "b_lat",
        "camera_id": "cam1",
        "detection_ids": [1],
        "pipeline_start_time": start_iso,
    }

    with (
        patch(
            "backend.services.pipeline_workers.record_pipeline_stage_latency",
            autospec=True,
        ) as mock_rpsl,
        patch(
            "backend.services.pipeline_workers.record_stage_latency", autospec=True
        ) as mock_rsl,
    ):
        await worker._process_analysis_item(item)

    stages = [c.args[0] for c in mock_rpsl.call_args_list]
    assert stages.count("batch_to_analyze") == 1
    assert "total_pipeline" in stages

    b2a = mock_rpsl.call_args_list[stages.index("batch_to_analyze")].args[1]
    assert isinstance(b2a, int)
    assert 20 <= b2a < 5000  # sleep(0.02) floor in ms; *1000 scale; +start explodes it

    total = mock_rpsl.call_args_list[stages.index("total_pipeline")].args[1]
    assert 4000 <= total <= 30000  # ~5000ms; /1000 lands at ~5

    mock_rsl.assert_called_once()
    assert mock_rsl.call_args.args[0:2] == (worker._redis, "analyze")
    assert isinstance(mock_rsl.call_args.args[2], int)
```

TDD: label renames fail `stages.count`/`args[0:2]`; `time()+start` gives b2a ≈ 3.5e12 → fails upper bound; `/1000` gives 0 → fails floor; `None` fails isinstance/range. (Residue noted: `×1001` survives — 0.1% delta, undetectable without clock mocking.)

### Test 4 — kills LAT-C (Z-suffix normalization)

```python
@pytest.mark.asyncio
async def test_analysis_worker_parses_zulu_pipeline_start_time(mock_redis_client, mock_analyzer):
    """pipeline_start_time with 'Z' suffix must parse via replace('Z', '+00:00') and
    record total_pipeline latency. Kills LAT-C (AI.110-112): every existing latency
    test feeds a naive timestamp, so the Zulu branch never executed.
    """
    from datetime import UTC, timedelta

    start_iso = (
        (datetime.now(UTC) - timedelta(seconds=5)).strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"
    )
    item = {
        "batch_id": "b_z",
        "camera_id": "cam1",
        "detection_ids": [1],
        "pipeline_start_time": start_iso,
    }
    worker = AnalysisQueueWorker(redis_client=mock_redis_client, analyzer=mock_analyzer)

    with patch(
        "backend.services.pipeline_workers.record_pipeline_stage_latency", autospec=True
    ) as mock_rpsl:
        await worker._process_analysis_item(item)

    assert worker.stats.items_processed == 1
    assert worker.stats.errors == 0
    total_calls = [c for c in mock_rpsl.call_args_list if c.args[0] == "total_pipeline"]
    assert len(total_calls) == 1
    assert 4000 <= total_calls[0].args[1] <= 30000
```

TDD: AI.112 (replacement → `"XX+00:00XX"`) makes `fromisoformat` raise ValueError → zero total_pipeline calls → red. Ledger note: AI.110/111 (needle/other-case no-ops) are runtime-equivalent on py ≥ 3.11 where `fromisoformat` accepts `Z` natively — mark them as such rather than chasing a test.

### Test 5 — kills PW-STATS + PW-METRIC-LABEL

```python
@pytest.mark.asyncio
async def test_analysis_worker_invalid_payloads_count_errors_exactly(
    mock_redis_client, mock_analyzer
):
    """Two invalid payloads -> errors increments by exactly 1 each, with the exact
    metric label; one valid item -> items_processed increments by exactly 1.
    Kills PW-STATS (+= -> =1/-=1/+=2, last_processed_at) + PW-METRIC-LABEL.
    """
    worker = AnalysisQueueWorker(redis_client=mock_redis_client, analyzer=mock_analyzer)
    invalid = {"camera_id": "cam1"}  # missing batch_id -> validation ValueError
    valid = {"batch_id": "b_stats", "camera_id": "cam1", "detection_ids": [1, 2]}

    with patch(
        "backend.services.pipeline_workers.record_pipeline_error", autospec=True
    ) as mock_record:
        await worker._process_analysis_item(invalid)
        await worker._process_analysis_item(invalid)
        await worker._process_analysis_item(valid)
        await worker._process_analysis_item(valid)

    mock_record.assert_called_with("invalid_analysis_payload")
    assert mock_record.call_count == 2
    assert worker.stats.errors == 2       # kills -=1 (-> -2), +=2 (-> 4), =1 (-> 1)
    assert worker.stats.items_processed == 2  # kills =1 assignment
    assert isinstance(worker.stats.last_processed_at, float)
    assert mock_analyzer.analyze_batch.call_count == 2  # valid items only (kills =1)
```

### Test 6 — kills VD-AGG + VD-DETECT + VD-RETRY + VD-EXTRACT

```python
@pytest.mark.asyncio
async def test_detection_worker_video_forwards_per_frame_detection_results(
    mock_redis_client,
):
    """Video path must forward each frame's detections to the aggregator with the
    VIDEO file path, bind the retryable op's frame via closure, and pass DLQ
    routing metadata. Kills VD-AGG/VD-DETECT/VD-RETRY/VD-EXTRACT: existing video
    tests mock with_retry WITHOUT invoking the operation and never assert kwargs.
    """
    from backend.services.retry_handler import RetryResult

    mock_detector = AsyncMock()
    mock_aggregator = AsyncMock(spec=BatchAggregator)
    mock_video_processor = AsyncMock()
    frames = ["/data/frames/f1.jpg", "/data/frames/f2.jpg"]
    metadata = {"duration": 10.0, "fps": 30}
    mock_video_processor.extract_frames_for_detection_batch = AsyncMock(return_value=frames)
    mock_video_processor.get_video_metadata = AsyncMock(return_value=metadata)
    mock_video_processor.cleanup_extracted_frames = MagicMock()

    detections = []
    for i in (1, 2):
        d = MagicMock()
        d.id = i
        d.confidence = 0.51 if i == 1 else 0.52
        d.object_type = "person"
        detections.append(d)

    retry_calls: list[dict] = []

    async def mock_with_retry(*args, **kwargs):
        retry_calls.append(kwargs)
        return RetryResult(
            success=True,
            result=[detections[len(retry_calls) - 1]],
            attempts=1,
            error=None,
            moved_to_dlq=False,
        )

    mock_retry_handler = AsyncMock()
    mock_retry_handler.with_retry = mock_with_retry

    worker = DetectionQueueWorker(
        redis_client=mock_redis_client,
        detector_client=mock_detector,
        batch_aggregator=mock_aggregator,
        video_processor=mock_video_processor,
        retry_handler=mock_retry_handler,
    )
    job_data = {"camera_id": "front_door", "file_path": "/videos/v.mp4", "media_type": "video"}

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    with patch(
        "backend.services.pipeline_workers.get_session",
        return_value=mock_session,
        autospec=True,
    ):
        await worker._process_video_detection(
            camera_id="front_door",
            video_path="/videos/v.mp4",
            job_data=job_data,
            pipeline_start_time="2025-12-28T10:00:00.000000",
        )

    mock_video_processor.extract_frames_for_detection_batch.assert_called_once_with(
        video_path="/videos/v.mp4",
        interval_seconds=worker._video_frame_interval,
        max_frames=worker._video_max_frames,
    )
    mock_video_processor.get_video_metadata.assert_called_once_with("/videos/v.mp4")

    # DLQ routing metadata must reach the retry handler per frame
    assert len(retry_calls) == 2
    for call in retry_calls:
        assert call["job_data"] is job_data
        assert call["queue_name"] == worker._queue_name

    # Each frame's detections forwarded, tagged with the VIDEO path (not frame path)
    assert mock_aggregator.add_detection.call_count == 2
    assert mock_aggregator.add_detection.call_args_list[0].kwargs == {
        "camera_id": "front_door",
        "detection_id": 1,
        "_file_path": "/videos/v.mp4",
        "confidence": 0.51,
        "object_type": "person",
        "pipeline_start_time": "2025-12-28T10:00:00.000000",
    }

    # The retryable op's default arg must be bound to the CURRENT frame (closure fix)
    mock_detector.detect_objects = AsyncMock(return_value=[])
    await retry_calls[1]["operation"]()
    detect_kwargs = mock_detector.detect_objects.call_args.kwargs
    assert detect_kwargs["image_path"] == frames[1]
    assert detect_kwargs["camera_id"] == "front_door"
    assert detect_kwargs["session"] is mock_session
    assert detect_kwargs["video_path"] == "/videos/v.mp4"
    assert detect_kwargs["video_metadata"] == metadata
```

TDD: `detections=None`/`and []` mutants → `add_detection.call_count == 0` red; any `add_detection` kwarg clobber → kwargs-equality red; `current_frame=None`/`image_path=fp` removal → `image_path` assert red (`None`/KeyError); `job_data=None`/`queue_name=None` → identity assert red; extract kwargs clobbers → `assert_called_once_with` red.

## Draft → cluster kill map

| Test                                                    | Primary clusters                        |
| ------------------------------------------------------- | --------------------------------------- |
| 1 `…broadcasts_batch_analysis_events_with_full_payload` | WS-A, WS-B                              |
| 2 `…classify_risk_level_and_errors`                     | WS-C                                    |
| 3 `…records_stage_latency_values`                       | LAT-A, LAT-B                            |
| 4 `…parses_zulu_pipeline_start_time`                    | LAT-C                                   |
| 5 `…invalid_payloads_count_errors_exactly`              | PW-STATS, PW-METRIC-LABEL               |
| 6 `…forwards_per_frame_detection_results`               | VD-AGG, VD-DETECT, VD-RETRY, VD-EXTRACT |

If WP4.4 accepts all six, the six drafted tests target an estimated kill of ~150 of the 167 TEST-GAP survivors; documented residue: WS-C `datetime.now(None)` sites (equivalent), AI.220 `categorize_exception(None,…)` (default path identical), `×1001` latency sites, LAT-C AI.110/111 (py≥3.11 native `Z` support).
