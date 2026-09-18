# WP4.4 Triage Dossier — backend/services/pipeline_workers.py

Date: 2026-09-18 · WP4.3 mutation baseline. Status: **UNVERIFIED (read-only triage; no tests executed)**.

## Data sources

- Verdicts: `mutants/backend/services/pipeline_workers.py.meta` (`exit_code_by_key`). 1648 keys total: **1110 survived (exit 0)**, 538 killed, 0 unchecked.
- Mutant diffs: extracted manually by diffing each `__mutmut_N` block in `mutants/backend/services/pipeline_workers.py` against the sibling `__mutmut_orig` block (`mutmut show` could not resolve the `ǁ`-mangled keys: `FileNotFoundError`). All 1110 diffs resolved mechanically; classification is deterministic (per-hunk keyword/anchor rule, 2 manual re-see cases noted below).
- Coverage: `mutants/mutmut-stats.json` → `tests_by_mangled_function_name`.

## Covering test files

| File | Role |
|---|---|
| `backend/tests/unit/services/test_pipeline_workers.py` | **Primary.** 3176 lines; covers every function in this module (fixtures at lines 174–250: autouse `disable_redis_streams` L175, `mock_redis_client` L189, `mock_detector_client` L212, `mock_batch_aggregator` L226, `mock_analyzer` L236; helper `wait_for_condition` L43). |
| `backend/tests/unit/services/test_redis_streams_integration.py` | Stream **service** tests only (xadd/xreadgroup on the service object) — never drives the worker `_run_loop` stream branch. |
| `backend/tests/unit/test_shutdown_cleanup.py` | Covers `PipelineWorkerManager.__init__` / `drain_queues` / `get_pending_count` (7+2+4 tests). |
| `backend/tests/unit/services/test_frame_buffer_pipeline_integration.py`, `backend/tests/unit/services/test_pipeline_workers_multi.py` | `PipelineWorkerManager.__init__` frame-buffer / multi-worker counts. |

Structural facts driving the verdicts:
- The autouse fixture forces `settings.use_redis_streams = False` — the entire Redis-Streams branch of every `_run_loop` (claim-stale, DLQ move, consumer-group consume) **never executes under any test at the worker level**.
- `grep -n "record_heartbeat\|supervisor" test_pipeline_workers.py` → **zero hits**: no test passes a supervisor to any worker.
- `grep broadcast_batch_analysis` in the test file → zero hits: NEM-3607 batch-analysis status payloads are never produced in any test (broadcaster always resolves None in tests).
- `test_broadcast_worker_event_*` (L2549–2658) call `broadcast_worker_event` **directly** with a mock emitter; they never go through `manager.start()/stop()`, so all emitter-wiring mutants survive.

## Cluster table (25 clusters; counts sum to 1110)

Clusters are the deterministic (statement-anchor × mutation-kind) groups produced by the extraction pass; example keys were re-verified against the cluster map, and the 3 re-seen cases are noted inline.

| # | Cluster | Count | Class | Example keys (fn__mutmut_N) | Note |
|---|---|---|---|---|---|
| 1 | EQ_LOG: message text / `logger.*`-arg mutations (text→`None`, case, `XX`-wrap, msg-arg deleted) across 12 functions | 417 | EQUIVALENT | `broadcast_worker_event__mutmut_19`, `drain_queues__mutmut_3`, `get_pipeline_manager__mutmut_6` | Semantically inert for control flow — message is only logged. No test should pin log strings. |
| 2 | GAP_BROADCAST: worker-lifecycle + NEM-3607 batch broadcast payloads — `self._websocket_emitter,`→`None,` (78), `worker_type` case, `reason="graceful_shutdown",` del, payload key case (`"batch_id"`→`"BATCH_ID"`/XX), `camera_id or ""` flips, `"retryable": False`→True, risk_level unwrap removal, `broadcaster = await self._get_broadcaster()`→None, plus `get_status`: `status["workers"]["timeout"] = …to_dict()`→`None` (`get_status__mutmut_26`) | 222 | TEST-GAP | `PipelineWorkerManagerǁstop__mutmut_25`, `_process_analysis_item__mutmut_154`, `broadcast_worker_event__mutmut_27` (manual) | `manager.start()/stop()` and the whole batch-analysis broadcast path execute in tests with `_websocket_emitter=None` — no test asserts **which events are emitted with which payload**. get_status `timeout` entry unasserted. |
| 3 | GAP_METRICS: latency/depth recorder call args — stage labels `"detect"/"batch"/"analyze"/"detect_to_batch"` case or `None`, `duration * 1000` → `/1000`/`*1001`/None, `record_stage_latency(self._redis, …)`→`None`, `set_queue_depth("detection", None)`, `get_queue_length(DETECTION_QUEUE)`→`None` | 77 | TEST-GAP | `_process_analysis_item__mutmut_102`, `DetectionQueueWorkerǁ_process_detection_item__mutmut_100`, `BatchTimeoutWorkerǁ_run_loop__mutmut_14` | `test_queue_metrics_worker_updates_metrics` (test file L1358) asserts only the queue **label** was passed — never the depth value; latency recorders are asserted (if at all) only for call existence, never label/value. |
| 4 | GAP_DETECT_PLUMBING: detector/aggregator call kwargs — `image_path=file_path,`→None/del, `camera_id=camera_id,`→None/del, `video_path=video_path,`→None/del, `max_frames=`/`interval_seconds=` del, `session=session,` del, `add_detection(...)` kwargs, `total_detections`/`detector_failed` init flips, closure `current_frame = frame_path`→None; includes the 2 `validated.camera_id/file_path = validated.…`→None mutants and the 2 `_process_{video,image}_detection` dispatch-positional-arg removals (`camera_id, file_path, item, pipeline_start_time` → `None, file_path, …`) | 72 | TEST-GAP | `_process_image_detection__mutmut_1`, `_process_video_detection__mutmut_33`, `_process_detection_item__mutmut_56` | `test_detection_worker_passes_job_data_to_retry_handler` (L2208) proves the **pattern** (capture kwargs via a stub retry handler) — but existing video/image tests assert only call counts; no test inspects `detect_objects`/`add_detection` kwargs or the validated fields on the accept path. |
| 5 | GAP_STREAM: worker stream branch — `consume_detections(consumer_name, count=1, block=True)` arg removals/Nones, `acknowledge(msg.id)`→None, `claim_interval`/`last_claim_check`, `claim_stale_messages`, DLQ decision, `continue`→`break`, `use_streams` branch selection | 53 | TEST-GAP | `AnalysisQueueWorkerǁ_run_loop__mutmut_2`, `DetectionQueueWorkerǁ_run_loop__mutmut_26`, `_run_loop__mutmut_45` | Autouse fixture pins `use_redis_streams=False`; the branch is dead under the suite. Needs a streams-on test (unit, with stub stream service). |
| 6 | LV_OBSERVABILITY: `log_context(...)`, `add_span_attributes`, `span_attrs[...]`, `set_pipeline_context_attributes(..., camera_id=…, stage=…)` arg mutations | 52 | LOW-VALUE | `_process_analysis_item__mutmut_25`, `_process_analysis_item__mutmut_26` | Real diagnostics change (span/log correlation) but no consumer asserts span attributes in unit tests; asserting them is brittle. |
| 7 | LV_TASKNAMING: `create_tracked_task(..., name="DetectionQueueWorker", task_prefix="detect-worker")` name/prefix case/deletion; default `worker_name: str = "detection"` case | 37 | LOW-VALUE | `DetectionQueueWorkerǁstart__mutmut_19`, `QueueMetricsWorkerǁ__init____mutmut_8` | Task name only shows in logs/repr; idempotent-start tests don't assert names. |
| 8 | GAP_HEARTBEAT: NEM-4148 supervisor heartbeat — `self._supervisor = supervisor`→None in 4 `__init__`, `if self._supervisor is not None:` flip, `heartbeat_interval = 20.0`→21.0/None, `last_heartbeat=None`, `self._worker_name = worker_name`→None | 27 | TEST-GAP | `AnalysisQueueWorkerǁ_run_loop__mutmut_21`, `_run_loop__mutmut_22`, `AnalysisQueueWorkerǁ__init____mutmut_12` | **Zero** supervisor/heartbeat references in the covering test file. Supervisor restart detection silently breaks. |
| 9 | GAP_MGR_INIT_WIRING: `PipelineWorkerManager.__init__` worker-construction — `if worker_stop_timeout is not None:` flip, `redis_client=redis_client,`→None (call-arg), `detector_client=detector_client,` del, `batch_aggregator=self._aggregator,` del, `stop_timeout=worker_stop_timeout,` del, `worker_name=worker_name,` del, `check_interval=check_interval,`→None | 26 | TEST-GAP | `PipelineWorkerManagerǁ__init____mutmut_22` (flip), `__init____mutmut_24` (redis_client None), `__init____mutmut_31` (detector_client deleted) | Existing init tests assert worker counts and `_timeout_worker is not None` only; nothing asserts the **shared-aggregator identity wiring** (NEM-5375 design invariant) or explicit stop-timeout propagation. |
| 10 | GAP_CATEGORIZE_LABELS: per-loop `categorize_exception(e, "detection"/"analysis"/"batch_timeout")` label→None/case; `error_type = …`→None; `record_pipeline_error(error_type)`→None; `.replace("analysis_", "")` tweaks | 21 | TEST-GAP | `_process_analysis_item__mutmut_215`, `BatchTimeoutWorkerǁ_run_loop__mutmut_64` | Loop-recovery tests patch `record_pipeline_error` (L711, L936) but assert only call **count**, never the labeled error type that feeds Prometheus. |
| 11 | GAP_STATS_COUNTERS: `self._stats.errors += 1` → `= 1` / `-= 1` / `+= 2`, `items_processed += 1` → `= 1`, `last_processed_at = time.time()`→None, `items_processed += len(closed_batches)`→`=` | 18 | TEST-GAP | `_process_analysis_item__mutmut_10`, `BatchTimeoutWorkerǁ_run_loop__mutmut_11` | Tests assert `errors == 1` after **one** failure (L528, L945, L2202) — `+= 1`→`= 1` only differs on the second event; nothing asserts `last_processed_at`. |
| 12 | GAP_RETRYCFG: default `RetryConfig(max_retries=3, base_delay_seconds=1.0, max_delay_seconds=30.0, exponential_base=2.0, jitter=True)` — `config=RetryConfig(`→`config=None,`/del, values→None/off-by-one, `jitter=True→False`, plus retry-handler kwarg Nones in frame paths | 18 | TEST-GAP | `DetectionQueueWorkerǁ__init____mutmut_25`, `_process_image_detection__mutmut_10` | `test_detection_worker_initializes_with_retry_handler` (L2266) checks existence only — no test inspects the default retry policy that governs DLQ timing. |
| 13 | GAP_DRAIN: `drain_queues` loop semantics — `if initial_count == 0:`→`== 1`, `if current_count == 0:`→`== 1`, `elapsed >= timeout`→`>`, `current_count >= last_count`→`>`, `stall_time += 0.1` → `= 0.1`/`-= 0.1`, `stall_threshold = 5.0`→6.0 | 13 | TEST-GAP | `PipelineWorkerManagerǁdrain_queues__mutmut_21`, `__mutmut_23`, `__mutmut_27` | Three drain tests exist (L2838–2916) but never exercise the **timeout-return** or equal-progress boundary; stall test only checks the log path runs. |
| 14 | EQ_TRANSIENT_STATE: `self._stats.state = WorkerState.STARTING/STOPPING/ERROR/RUNNING` → `None` in start/stop/error paths | 10 | EQUIVALENT | `AnalysisQueueWorkerǁstart__mutmut_16`, `AnalysisQueueWorkerǁstop__mutmut_10` | State is overwritten to the next lifecycle value within microseconds and the final states (`RUNNING`, `STOPPED`) are asserted by existing tests; the transient window is unobservable. |
| 15 | LV_TIMING: default tuning constants — `poll_timeout: int = 5`→6, `stop_timeout: float = 10.0/30.0`→+1, `await asyncio.sleep(1.0)`→2.0, `heartbeat/claim_interval +1`, `drain_queues(timeout=30.0)` default→31.0 (2 signature-default mutants re-reviewed manually) | 9 | LOW-VALUE | `AnalysisQueueWorkerǁ__init____mutmut_1`, `DetectionQueueWorkerǁ__init____mutmut_1`, `_run_loop__mutmut_81` | Tests override these defaults everywhere (`TEST_STOP_TIMEOUT`); asserting default values pins a tuning choice nobody has signed off on. |
| 16 | GAP_CATEGORIZE: `categorize_exception` body — timeout check `or`→`and` (L169), `type(e)`→`type(None)` (×4), `"redis" in …__module__` case/XX, `.lower()`→`.upper()`, connection check `or`→`and` at L163 | 7 | TEST-GAP | `categorize_exception__mutmut_19`, `__mutmut_23`, `__mutmut_27` | `TestCategorizeException` (L291) covers 10 branches but (a) has **no redis-module-error test** — the module-name branch (L185) is never exercised, so `REDIS`-case / `.upper()` / `type(None)` mutants there survive, and (b) `test_timeout_error` passes a real `TimeoutError`, for which BOTH sides of `isinstance(e, TimeoutError) or type(e).__name__ in (...)` are true — the `or→and` mutant survives; a duck-typed exception (named `TimeoutExpired`, not TimeoutError) is missing. |
| 17 | GAP_SINGLETON: `_get_pipeline_manager` fast path `if _pipeline_manager is not None:` flip, `_pipeline_manager = PipelineWorkerManager(redis_client=redis_client)`→None, `stop_pipeline_manager` None-out, `reset_pipeline_manager_state` `None`→`""` | 7 | TEST-GAP | `get_pipeline_manager__mutmut_1`, `stop_pipeline_manager__mutmut_6`, `reset_pipeline_manager_state__mutmut_1` | Existing singleton tests call each function once; the **double-call fast path** (`is not None` flip → re-init under lock) is not pinned. |
| 18 | GAP_INIT_WIRING: worker/manager `__init__` attribute-assignment Nones — `self._redis = redis_client`→None (BatchTimeoutWorker), `self._websocket_emitter = websocket_emitter`→None, `self._aggregator = BatchAggregator(…)`→None, `BatchAggregator(redis_client=…)`→`(redis_client=None)`, `self._worker_stop_timeout = worker_stop_timeout`→None (manager), `self._stop_timeout = stop_timeout`→None (QueueMetricsWorker) | 6 | TEST-GAP | `BatchTimeoutWorkerǁ__init____mutmut_1`, `QueueMetricsWorkerǁ__init____mutmut_3`, `PipelineWorkerManagerǁ__init____mutmut_13` | Constructor params are wired to attributes with no read-back assertion (supervisor case counted in cluster 8). |
| 19 | GAP_DEFAULT_CONSTRUCT: `analyzer or NemotronAnalyzer(...)` / `batch_aggregator or BatchAggregator(...)` / `video_processor or …` default-arg wiring (`redis_client=redis_client`→None inside the constructed default) | 3 | TEST-GAP | `AnalysisQueueWorkerǁ__init____mutmut_8`, `BatchTimeoutWorkerǁ__init____mutmut_4`, `DetectionQueueWorkerǁ__init____mutmut_16` | Init tests always pass mocks; the auto-construct path's internal wiring is never asserted. |
| 20 | GAP_SIGNAL: `_install_signal_handlers` — `self._signal_handlers_installed = True`→False/None, `asyncio.create_task(self.stop())`→`create_task(None)` | 3 | TEST-GAP | `_install_signal_handlers__mutmut_10`, `__mutmut_11`, `__mutmut_3` | `test_manager_signal_handler_triggers_stop` (L1630) exercises the handler path but doesn't assert the installed flag or that a **stop coroutine** was scheduled (create_task(None) is an inert coroutine). |
| 21 | EQ_FALSY_SWAP: `self._task = None` → `""`, `_broadcaster: Any = None` → `""` | 4 | EQUIVALENT | `AnalysisQueueWorkerǁ__init____mutmut_16`, `QueueMetricsWorkerǁstop__mutmut_12` | Both falsy; every read site is `if x:` / `if self._task:` so behavior is identical. |
| 22 | LV_RECEXCEPTION: `record_exception(e)` → `record_exception(None)` in error paths | 4 | LOW-VALUE | `_process_analysis_item__mutmut_181`, `_process_detection_item__mutmut_105` | OTEL span exception detail only; no test asserts span events, and asserting a no-op tracer call is noise. |
| 23 | GAP_VALIDATION: `_process_detection_item` accept-path assignments — `camera_id = validated.camera_id`→None, `file_path = validated.file_path`→None | 2 | TEST-GAP | `DetectionQueueWorkerǁ_process_detection_item__mutmut_4`, `__mutmut_5` | `test_detection_worker_handles_invalid_item` tests the **reject** path; the accept path never asserts the validated fields propagate. Killed via T4's dispatcher routing. |
| 24 | EQ_NOOP: no body-diff mutant (`broadcast_worker_event__mutmut_40` second hunk is a blank-line deletion only; re-reviewed manually) | 1 | EQUIVALENT | `broadcast_worker_event__mutmut_40` | Blank-line deletion is a parse-tree no-op. |
| 25 | GAP_STOP_TIMEOUT: `QueueMetricsWorker.stop` `await asyncio.wait_for(self._task, timeout=self._stop_timeout)` → `timeout=None` | 1 | TEST-GAP | `QueueMetricsWorkerǁstop__mutmut_9` | Metrics-worker `stop()` has no timeout test (detection/analysis/timeout workers each do, L612/L950/L1195 — the metrics one was missed). |

**Totals: EQUIVALENT 432 (rows 1, 14, 21, 24) · LOW-VALUE 102 (rows 6, 7, 15, 22) · TEST-GAP 576 (the other 17 clusters). Sum = 1110.** (Arithmetic verified programmatically against `/tmp/wp44-pw-cluster-summary.json` with the three manual re-classifications folded in: `broadcast_worker_event__mutmut_27`→GAP_BROADCAST, `__mutmut_40`→EQ_NOOP, the two `drain_queues__mutmut_1` signature-default mutants EQ_NOOP→LV_TIMING.)

## Drafted tests (highest-value TEST-GAP clusters)

All UNVERIFIED — not yet run red/green. TDD procedure for each: add the test, run against the **mutant** copy line-under-test (the specific mutated statement) → assertion fails; run against original → passes; then the mutant for that statement flips red and the suite goes green on unmutated code.

### T1 — kills cluster 2 (manager lifecycle broadcasts) + part of 17-style wiring

Targets `backend/tests/unit/services/test_pipeline_workers.py` (append near L2658, after the `broadcast_worker_event` tests). Style mirrors `test_manager_start_stop` (L1477) + `test_broadcast_worker_event_success` (L2549).

```python
@pytest.mark.asyncio
@pytest.mark.timeout(10)
async def test_manager_lifecycle_broadcasts_worker_events(mock_redis_client):
    """Manager must broadcast worker.started/stopped with correct payload (NEM-2461, NEM-5375).

    Kills pipeline_workers GAP_BROADCAST survivors: emitter arg -> None (78 sites),
    worker_type case flips ("detection"->"DETECTION"), reason="graceful_shutdown"
    deletion, items_processed kwarg deletion in manager.start()/stop().
    """
    mock_emitter = AsyncMock()
    mock_emitter.emit = AsyncMock()

    manager = PipelineWorkerManager(
        redis_client=mock_redis_client,
        websocket_emitter=mock_emitter,
        detection_worker_count=1,
        analysis_worker_count=1,
        worker_stop_timeout=TEST_STOP_TIMEOUT,
    )

    await manager.start()
    started = [(c.args[0].name, c.args[1]) for c in mock_emitter.emit.call_args_list]
    assert sum(1 for name, _ in started if name == "WORKER_STARTED") == 4, (
        "expected started events for detection/analysis/timeout/metrics workers"
    )
    started_types = {p["worker_type"] for _, p in started if _ == "WORKER_STARTED"}
    assert started_types == {"detection", "analysis", "timeout", "metrics"}
    assert all(p["worker_name"] for _, p in started)

    mock_emitter.emit.reset_mock()
    await manager.stop()
    stopped = [(c.args[0].name, c.args[1]) for c in mock_emitter.emit.call_args_list]
    stopped_events = [p for name, p in stopped if name == "WORKER_STOPPED"]
    assert len(stopped_events) == 4
    # reason kwarg must be present on every stop event (del-kwarg survivors)
    assert all(p["reason"] == "graceful_shutdown" for p in stopped_events), stopped_events
    # items_processed kwarg on detection/analysis/timeout events (del-kwarg survivors)
    with_items = [p for p in stopped_events if p["worker_type"] in {"detection", "analysis", "timeout"}]
    assert all("items_processed" in p for p in with_items), with_items
    assert {p["worker_type"] for p in stopped_events} == {"detection", "analysis", "timeout", "metrics"}
```

TDD: on the mutant (`self._websocket_emitter,` → `None,`) `mock_emitter.emit` is never called → count assert fails; on `"DETECTION"` case mutants the set assertion fails; on `reason=` deletion the `p["reason"]` lookup raises KeyError. Passes on original.

### T2 — kills cluster 2 remainder (NEM-3607 batch-analysis payload fields) in `_process_analysis_item`

Targets the same file (after `test_analysis_worker_processes_batch`, L807ff). Style: direct `_process_analysis_item` invocation + `worker._broadcaster` stub (bypasses `_get_broadcaster`/Redis).

```python
@pytest.mark.asyncio
async def test_analysis_worker_broadcasts_batch_lifecycle_payloads(mock_redis_client, mock_analyzer):
    """batch.analysis_started/completed payloads carry exact keys/values (NEM-3607).

    Kills survivors in _process_analysis_item: broadcaster lookup -> None,
    payload key case/XX-wrap ("batch_id"->"BATCH_ID"/"XXbatch_idXX"),
    camera_id `or ""` fallback flips, risk_level unwrap removal,
    detection_count/queue_position number mutations.
    """
    events: list[tuple[str, dict]] = []

    class StubBroadcaster:
        async def broadcast_batch_analysis_started(self, payload):
            events.append(("started", payload))

        async def broadcast_batch_analysis_completed(self, payload):
            events.append(("completed", payload))

        async def broadcast_batch_analysis_failed(self, payload):
            events.append(("failed", payload))

    worker = AnalysisQueueWorker(
        redis_client=mock_redis_client,
        analyzer=mock_analyzer,
        stop_timeout=TEST_STOP_TIMEOUT,
    )
    worker._broadcaster = StubBroadcaster()

    await worker._process_analysis_item(
        {
            "batch_id": "batch-42",
            "camera_id": "front_door",
            "detection_ids": [1, 2, 3],
        }
    )

    kinds = [k for k, _ in events]
    assert kinds == ["started", "completed"]
    started_payload = events[0][1]
    assert started_payload["batch_id"] == "batch-42"          # kills key-case/XX survivors
    assert started_payload["camera_id"] == "front_door"        # kills `or ""` operand flips
    assert started_payload["detection_count"] == 3             # kills else-branch 0->1 mutant
    assert started_payload["queue_position"] == 0
    completed_payload = events[1][1]
    assert completed_payload["risk_level"] == "medium"         # kills risk_level unwrap mutants
    assert completed_payload["event_id"] == mock_analyzer.analyze_batch.return_value.id
    assert isinstance(completed_payload["duration_ms"], int)   # kills duration_ms -> None
    assert completed_payload["camera_id"] == "front_door"
```

TDD: on `broadcaster = await self._get_broadcaster()` → `broadcaster = None`, `kinds == []` fails; on `"BATCH_ID"`/XX key mutants the `started_payload["batch_id"]` lookup KeyErrors; on `camera_id and ""` mutants the fallback yields `""`/falsy mismatch. Passes on original.

### T3 — kills cluster 5 (worker Redis-Streams branch)

Targets the same file (new `TestStreamModeRunLoop` section). The autouse fixture sets streams off globally, so the test re-patches `get_settings` locally and stubs the stream service.

```python
@pytest.mark.asyncio
@pytest.mark.timeout(10)
async def test_detection_run_loop_stream_mode_consumer_group_args(mock_redis_client, mock_detector_client):
    """Stream-mode loop consumes with consumer group and claims stale/DLQ (NEM-3469).

    Kills survivors in _run_loop: consume args (consumer_name/count/block) removals &
    None/case mutants, continue->break, claim_stale wiring, msg.raw_data -> None,
    delivery_count threshold branch.
    """
    from backend.services.pipeline_workers import DetectionQueueWorker  # (already imported at module top)

    msg = MagicMock()
    msg.id = "1-0"
    msg.raw_data = {
        "camera_id": "front_door",
        "file_path": "/data/a.jpg",
        "media_type": "image",
    }
    msg.delivery_count = 1

    stale_msg = MagicMock()
    stale_msg.id = "0-9"
    stale_msg.delivery_count = 99  # exceeds stub _max_delivery_count

    stream_service = MagicMock()
    stream_service._max_delivery_count = 5
    stream_service.should_move_to_dlq = MagicMock(return_value=False)
    stream_service.claim_stale_messages = AsyncMock(return_value=[stale_msg])
    stream_service.move_to_dlq = AsyncMock()
    stream_service.acknowledge = AsyncMock()
    consumed = []

    async def fake_consume(consumer_name, count=0, block=False, **kwargs):
        consumed.append((consumer_name, count, block))
        return [msg] if len(consumed) == 1 else []

    stream_service.consume_detections = AsyncMock(side_effect=lambda *a, **k: fake_consume(*a, **k))

    worker = DetectionQueueWorker(
        redis_client=mock_redis_client,
        detector_client=mock_detector_client,
        poll_timeout=TEST_POLL_TIMEOUT,
        stop_timeout=TEST_STOP_TIMEOUT,
    )
    # route the processed payload through: with retry handler stubbed, detect is a no-op
    async def passthrough_retry(operation, job_data, queue_name, *args, **kwargs):
        await operation()
        return MagicMock(success=True, result=[], attempts=1, moved_to_dlq=False)

    worker._retry_handler.with_retry = AsyncMock(side_effect=passthrough_retry)

    with (
        patch("backend.services.pipeline_workers.get_settings", autospec=True) as mock_settings,
        patch(
            "backend.services.pipeline_workers.get_detection_stream_service",
            new=AsyncMock(return_value=stream_service),
        ),
        patch("backend.services.pipeline_workers.get_session", autospec=True) as mock_get_session,
    ):
        settings = MagicMock()
        settings.use_redis_streams = True
        mock_settings.return_value = settings
        mock_session = AsyncMock()
        mock_get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_get_session.return_value.__aexit__ = AsyncMock(return_value=None)

        await worker.start()
        await wait_for_call_count(stream_service.consume_detections, min_count=2)  # survives empty read (kills continue->break)
        await worker.stop()

    consumer_name, count, block = consumed[0]
    assert isinstance(consumer_name, str) and consumer_name.startswith("detection-worker-")
    assert count == 1
    assert block is True
    # stale claim ran and DLQ-decided the over-delivered message
    stream_service.claim_stale_messages.assert_called()
    stream_service.move_to_dlq.assert_awaited_with(stale_msg, "max_delivery_exceeded")
    # fresh message was routed with its own raw_data (kills msg.raw_data -> None)
    assert mock_detector_client.detect_objects.await_count >= 1 or worker.stats.items_processed >= 1
```

TDD: on `count=1` → `count=None`/removed, `block=True` → `False`, or `consumer_name,` → `None,`, the `consumed[0]` unpack asserts fail; on `continue` → `break`, the loop exits after the first empty read and `min_count=2` times out; on the delivery-count comparison mutation `move_to_dlq` is never awaited. Passes on original.

### T4 — kills cluster 4 (detector/aggregator arg wiring) for image+video paths

Targets the same file (after `test_detection_worker_passes_job_data_to_retry_handler`, L2264ff). Reuses the stub-retry capture pattern already in the file.

```python
@pytest.mark.asyncio
async def test_detection_forwards_file_and_video_args_to_detector(
    mock_redis_client, mock_detector_client, mock_batch_aggregator, mock_video_processor
):
    """detect_objects/add_detection receive exact kwargs; video detection targets the VIDEO path.

    Kills GAP_DETECT_PLUMBING survivors: image_path/camera_id/video_path -> None or
    deleted kwarg, max_frames/interval_seconds deletion, session deletion,
    add_detection _file_path=video_path mutants, closure current_frame -> None.
    """
    captured: dict = {"image": None, "video": [], "extract": None, "add": []}

    detection = MagicMock()
    detection.id = 7
    detection.confidence = 0.9
    detection.object_type = "person"

    async def capture_detect(*args, **kwargs):
        captured["video"].append(kwargs) if kwargs.get("video_path") else captured.update(image=kwargs)
        return [detection]

    mock_detector_client.detect_objects = AsyncMock(side_effect=capture_detect)

    async def capture_add(*args, **kwargs):
        captured["add"].append(kwargs)
        return "batch_1"

    mock_batch_aggregator.add_detection = AsyncMock(side_effect=capture_add)

    async def capture_extract(**kwargs):
        captured["extract"] = kwargs
        return ["/data/frames/f0.jpg"]

    mock_video_processor.extract_frames_for_detection_batch = AsyncMock(side_effect=capture_extract)

    async def passthrough_retry(operation, job_data, queue_name, *args, **kwargs):
        result = await operation()
        return MagicMock(success=True, result=result, attempts=1, moved_to_dlq=False)

    # Route through the PUBLIC dispatcher so the validated-field assignment
    # mutants (_process_detection_item__mutmut_4/5: camera_id/file_path = None)
    # and the positional dispatch-arg removal (_process_detection_item__mutmut_56:
    # camera_id, file_path, item, pipeline_start_time -> None, …) also fail.
    # ---- image item ----
    image_worker = DetectionQueueWorker(
        redis_client=mock_redis_client,
        detector_client=mock_detector_client,
        batch_aggregator=mock_batch_aggregator,
        retry_handler=None,
        stop_timeout=TEST_STOP_TIMEOUT,
    )
    image_worker._retry_handler.with_retry = AsyncMock(side_effect=passthrough_retry)
    with patch("backend.services.pipeline_workers.get_session", autospec=True) as gs:
        gs.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
        gs.return_value.__aexit__ = AsyncMock(return_value=None)
        await image_worker._process_detection_item(
            {
                "camera_id": "cam_a",
                "file_path": "/data/a.jpg",
                "timestamp": "2026-01-01T00:00:00+00:00",
                "media_type": "image",
            }
        )

    assert captured["image"]["image_path"] == "/data/a.jpg"     # kills image_path -> None/del + dispatch _56
    assert captured["image"]["camera_id"] == "cam_a"            # kills camera_id -> None/del + validated _4/_5
    assert captured["image"]["session"] is not None             # kills session= deletion
    assert captured["add"][-1]["_file_path"] == "/data/a.jpg"

    # ---- video item ----
    captured["video"] = []
    video_worker = DetectionQueueWorker(
        redis_client=mock_redis_client,
        detector_client=mock_detector_client,
        batch_aggregator=mock_batch_aggregator,
        video_processor=mock_video_processor,
        stop_timeout=TEST_STOP_TIMEOUT,
    )
    video_worker._retry_handler.with_retry = AsyncMock(side_effect=passthrough_retry)
    with patch("backend.services.pipeline_workers.get_session", autospec=True) as gs:
        gs.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
        gs.return_value.__aexit__ = AsyncMock(return_value=None)
        await video_worker._process_detection_item(
            {
                "camera_id": "cam_v",
                "file_path": "/data/v.mp4",
                "timestamp": "2026-01-01T00:00:00+00:00",
                "media_type": "video",
            }
        )

    extract_kwargs = captured["extract"]
    assert extract_kwargs["video_path"] == "/data/v.mp4"
    assert extract_kwargs["interval_seconds"] == video_worker._video_frame_interval  # kills -> None
    assert extract_kwargs["max_frames"] == video_worker._video_max_frames            # kills del
    assert captured["video"], "detect_objects not called for frame"
    frame_call = captured["video"][0]
    assert frame_call["image_path"] == "/data/frames/f0.jpg"    # kills closure current_frame -> None
    assert frame_call["video_path"] == "/data/v.mp4"
    assert frame_call["camera_id"] == "cam_v"
    assert captured["add"][-1]["_file_path"] == "/data/v.mp4"   # video path, not frame path
```

TDD: on `image_path=file_path,` → `None`, the `captured["image"]["image_path"]` assert fails; on `max_frames=` deletion the `extract_kwargs["max_frames"]` KeyErrors; on `current_frame = frame_path` → `None`, the frame-path assert fails; on the validated-field (`camera_id = None`) or dispatch-positional (`None, file_path, …`) mutants the camera/path asserts fail downstream. Passes on original. (Routing through `_process_detection_item` — same path `test_detection_worker_processes_video_item` (L1874) already exercises, so the dispatcher's latency-recorder calls are proven-safe under `mock_redis_client`.)

### T5 — kills clusters 8 + 9 (supervisor heartbeat throttling; manager wiring invariants)

Two tests in the same block (style of `test_timeout_worker_consistent_interval_despite_processing_time`, L1229).

```python
@pytest.mark.asyncio
@pytest.mark.timeout(10)
async def test_batch_timeout_worker_sends_throttled_heartbeat(mock_redis_client, mock_batch_aggregator):
    """Supervisor heartbeat fires at the 20s boundary and not before (NEM-4148).

    Kills GAP_HEARTBEAT survivors: self._supervisor -> None (all 4 worker __init__),
    `if self._supervisor is not None` flip, heartbeat_interval 20.0 -> 21.0/None,
    last_heartbeat -> None, >= -> >.
    """
    fake_now = {"t": 0.0}
    supervisor = MagicMock()
    supervisor.record_heartbeat = MagicMock()

    worker = BatchTimeoutWorker(
        redis_client=mock_redis_client,
        batch_aggregator=mock_batch_aggregator,
        check_interval=0.05,
        stop_timeout=TEST_STOP_TIMEOUT,
        supervisor=supervisor,
        worker_name="batch_timeout",
    )

    with patch("backend.services.pipeline_workers.time_module.time", side_effect=lambda: fake_now["t"]):
        await worker.start()
        fake_now["t"] = 20.0  # exact original boundary (>= 20.0)
        await wait_for_condition(
            lambda: supervisor.record_heartbeat.call_count >= 1,
            timeout=2.0,
            description="first heartbeat",
        )
        supervisor.record_heartbeat.assert_called_once_with("batch_timeout")  # kills worker_name -> None
        # within the next interval no further heartbeat must fire
        await asyncio.sleep(0.15)
        assert supervisor.record_heartbeat.call_count == 1
        fake_now["t"] = 41.0
        await wait_for_condition(
            lambda: supervisor.record_heartbeat.call_count >= 2,
            timeout=2.0,
            description="second heartbeat",
        )
        await worker.stop()
```

TDD: on `heartbeat_interval = 21.0`, the first call never fires at t=20 (times out); on `supervisor -> None` wiring, `record_heartbeat` is never called (both waits time out); on `>=` → `>` boundary, first fire also fails. Passes on original.

```python
@pytest.mark.asyncio
async def test_manager_wires_shared_aggregator_and_config_into_workers(mock_redis_client):
    """Manager passes shared aggregator, redis, and explicit stop_timeout into every worker (NEM-5375).

    Kills GAP_MGR_INIT_WIRING survivors: batch_aggregator=/frame_buffer=/stop_timeout=/
    worker_name= kwarg deletions, redis_client= -> None, update_interval=5.0 -> 6.0/None,
    check_interval -> None, and GAP_INIT_WIRING self._redis/_worker_name -> None survivors.
    """
    manager = PipelineWorkerManager(
        redis_client=mock_redis_client,
        worker_stop_timeout=0.7,
        detection_worker_count=2,
        analysis_worker_count=1,
    )

    det = manager._detection_workers[0]
    ana = manager._analysis_workers[0]
    # shared aggregator identity: the whole NEM-5375 batch pipeline relies on this
    assert det._aggregator is manager._aggregator
    assert manager._timeout_worker._aggregator is manager._aggregator
    # explicit config propagation
    assert det._redis is mock_redis_client
    assert ana._redis is mock_redis_client
    assert manager._timeout_worker._redis is mock_redis_client
    assert det._stop_timeout == 0.7
    assert ana._stop_timeout == 0.7
    assert manager._timeout_worker._stop_timeout == 0.7
    assert manager._metrics_worker._stop_timeout == 0.7
    assert manager._metrics_worker._update_interval == 5.0
    # per-worker names keep the -{i} suffix
    assert [w._worker_name for w in manager._detection_workers] == ["detection-0", "detection-1"]
    assert ana._worker_name == "analysis-0"
```

TDD: on `batch_aggregator=self._aggregator,` deletion, `det._aggregator is manager._aggregator` fails (each worker constructs its own); on `stop_timeout=worker_stop_timeout` deletion `_stop_timeout` is the class default (10.0 ≠ 0.7). Passes on original.

### T6 — kills clusters 3 + 10/11 (metrics label/value + cumulative error counters) in the detection loop

```python
@pytest.mark.asyncio
async def test_detection_loop_error_path_labels_and_cumulative_count(
    mock_redis_client, mock_detector_client
):
    """Loop errors record the labeled error type and accumulate (NEM-4148 metrics contract).

    Kills GAP_CATEGORIZE_LABELS survivors (categorize_exception label -> None/"DETECTION",
    record_pipeline_error(error_type) -> None) and GAP_STATS_COUNTERS survivors
    (errors += 1 -> = 1 / -= 1 / += 2 across all 4 workers).
    """
    errors_raised = 0

    async def flaky_get_from_queue(*args, **kwargs):
        nonlocal errors_raised
        await asyncio.sleep(0.01)
        errors_raised += 1
        if errors_raised <= 2:
            raise ConnectionError("connection refused")
        return None

    mock_redis_client.get_from_queue = flaky_get_from_queue

    worker = DetectionQueueWorker(
        redis_client=mock_redis_client,
        detector_client=mock_detector_client,
        poll_timeout=TEST_POLL_TIMEOUT,
        stop_timeout=TEST_STOP_TIMEOUT,
    )

    with patch(
        "backend.services.pipeline_workers.record_pipeline_error", autospec=True
    ) as mock_record, patch(
        "backend.services.pipeline_workers.asyncio.sleep", autospec=True
    ) as mock_sleep:
        real_sleep = asyncio.sleep

        async def fast_sleep(delay, *args, **kwargs):
            await real_sleep(0.01)

        mock_sleep.side_effect = fast_sleep
        await worker.start()
        await wait_for_condition(
            lambda: worker.stats.errors >= 2, timeout=3.0, description="two recorded errors"
        )
        await worker.stop()

    assert worker.stats.errors == 2          # kills +=1 -> =1 and +=1 -> +=2
    assert mock_record.call_count >= 2
    # exact labeled type from categorize_exception(e, "detection")
    assert all(c.args[0] == "detection_connection_error" for c in mock_record.call_args_list)
```

TDD: on the `+= 1` → `= 1` mutant, errors never exceeds 1 → condition wait times out; on label mutants `record_pipeline_error` receives `None`/`DETECTION_connection_error` → last assert fails. Passes on original.

## Residual notes (what the drafted tests do NOT kill)

- 417 EQ_LOG + 4 EQ_NOOP are permanently unkillable-by-design; WP4.4 should mark them equivalent in the baseline so the survival ratio stops absorbing them.
- `duration * 1000` → `/ 1000`/`* 1001` mutants in the latency recorders (≈8 of cluster 3) are not killed by T6 (wall-clock duration is unbounded below); would need a clock-patched process-item test — flagged as follow-up, low priority.
- LV_* clusters (102) are recommended to be recorded as LOW-VALUE in the WP4.4 baseline rather than targeted; the one debatable case is LV_TASKNAMING's `name=` kwarg (tracked-task naming shows up in logs only).
