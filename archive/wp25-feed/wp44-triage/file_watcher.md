# WP4.4 Triage Dossier — backend/services/file_watcher.py

- **Source:** `backend/services/file_watcher.py` (1114 lines)
- **Meta:** `mutants/backend/services/file_watcher.py.meta` — 613 keys, all checked; **327 survived** (exit_code 0)
- **Diff method:** full-function difflib alignment of mutant copies vs. original in
  `mutants/backend/services/file_watcher.py` (validated byte-for-byte against
  `uv run mutmut show` for two keys); 4 MULTI-hunk keys (init#67, _get_camera_id_from_path#12,
  _queue_for_detection#124, _process_file#86) are extractor block-boundary artifacts — their
  real single-hunk diff was confirmed (adjacent-variant tail bleed-through; `_ensure_camera_exists#29`
  and `_debounced_process#3` verified clean via `mutmut show`).
- **Covering test files** (from `mutants/mutmut-stats.json` → `tests_by_mangled_function_name`):
  - `backend/tests/unit/services/test_file_watcher.py` (2245 lines; ~73 ctor tests, 16–22 per method)
  - `backend/tests/unit/services/test_video_support.py` (video size checks at :147–171)
  - `backend/tests/unit/services/test_redis_streams_integration.py` (`TestFileWatcherStreamPath.test_queue_detection_uses_xadd_when_streams_enabled` at :460–492 — **the only stream-path FileWatcher test; asserts call count only, never kwargs**)
  - `backend/tests/unit/services/test_async_context_managers.py` (ctor coverage only)

## Totals

| Classification | Count |
|---|---|
| TEST-GAP | 90 |
| LOW-VALUE | 8 |
| EQUIVALENT | 229 |
| **Total** | **327** |

Structural note: 216 of 327 survivors are `logger.<level>(...)` message / `extra={...}` dict mutations —
this module logs *profusely* (structured audit context nobody asserts). That single pattern is 66% of
all survivors. Everything behavioral that survives clusters into 15 TEST-GAP clusters.

## Cluster table

Counts sum to 327. Keys shown ≤3 per cluster.

| ID | Pattern (function / concern) | n | Class | Example keys (`file_watcher.` prefix omitted) |
|---|---|---|---|---|
| EQ-LOG-TEXT | Log message text, `extra={...}` dict keys/None-ing across `__init__`, `start`, `stop`, `_process_file`, `_queue_for_detection`, `_wait_for_file_stability`, `_ensure_camera_exists`, `_create_event_handler`, `is_valid_*` handlers (message → `None`, `XXfooXX`, `FOO` case flips, `and False`/`or True` guards inside f-strings) | 216 | EQUIVALENT | `_queue_for_detection__mutmut_2`, `_wait_for_file_stability__mutmut_22`, `_process_file__mutmut_13` |
| TG-STREAM-ARGS | `_queue_for_detection` Redis-Streams branch: `add_detection(camera_id=…, detection_id=0, file_path=…, extra_fields={…})` args → `None`/dropped/`detection_id=1`, `extra_fields` dict key renames (`"TIMESTAMP"`, `"PIPELINE_START_TIME"`), `.get("pipeline_start_time","")` default/lookup clobbers, file_hash spread `**({"file_hash": …} if …)` toggles, `get_detection_stream_service(self.redis_client→None)` | 27 | TEST-GAP | `_queue_for_detection__mutmut_50`, `_queue_for_detection__mutmut_52`, `_queue_for_detection__mutmut_55` |
| TG-LATENCY | `_process_file` duration math `int((time.time()-start)*1000)` (op flips `/`,`+`, `*1001`, `int(...)→None`) and `record_pipeline_stage_latency("watch_to_detect", float(duration_ms))` (call removal, arg `None`, stage-name case/XX) — **no test anywhere in the suite asserts this call for file_watcher** (grep: only `test_metrics.py`, `test_pipeline_workers.py` reference the function) | 12 | TEST-GAP | `_process_file__mutmut_65`, `_process_file__mutmut_70`, `_process_file__mutmut_73` |
| TG-STOP-CANCEL | `stop()`: `asyncio.gather(*self._pending_tasks.values(), …)` → `gather(return_exceptions=True)` (tasks not awaited on shutdown), `observer.join(timeout=5→None/6)`, `_hash_executor.shutdown(wait=True→None/False, cancel_futures=False→None/True/dropped)` | 10 | TEST-GAP | `stop__mutmut_13`, `stop__mutmut_21`, `stop__mutmut_32` |
| TG-MKDIR-ARGS | `start()` auto-create camera root: `mkdir(parents=True→None/False/dropped, exist_ok=True→None/False/dropped)` — test only covers *missing* root (`test_file_watcher.py:1011`), never missing *parents* nor *existing* root | 6 | TEST-GAP | `start__mutmut_43`, `start__mutmut_46`, `start__mutmut_48` |
| TG-EVENT-SCHED | `_create_event_handler._schedule_async_task`: `asyncio.run_coroutine_threadsafe(self.watcher._schedule_file_processing(file_path), self.watcher._loop)` — coroutine/loop/path args → `None`/dropped; the only loop test (`:921`) exercises the **else** branch | 5 | TEST-GAP | `_create_event_handler__mutmut_17`, `_create_event_handler__mutmut_18`, `_create_event_handler__mutmut_21` |
| TG-QUEUE-PAYLOAD | `_queue_for_detection` payload construction: `datetime.now(UTC)→now(None)` (naive timestamps in queue), `"media_type": media_type or get_media_type(...) or "image"` → `and "image"` / `"IMAGE"` casing — payload dict reaches redis mock in tests but these fields are never asserted (only `camera_id` at `:1402`) | 5 | TEST-GAP | `_queue_for_detection__mutmut_25`, `_queue_for_detection__mutmut_35`, `_queue_for_detection__mutmut_38` |
| TG-OBSERVER-SCHEDULE | `start()`: `observer.schedule(self._event_handler, str(camera_root_path), recursive=True)` — handler→`None`, path→`str(None)`, `recursive=True→None/False/dropped`; zero tests spy on `observer.schedule` | 5 | TEST-GAP | `start__mutmut_49`, `start__mutmut_51`, `start__mutmut_56` |
| TG-CTOR-WIRING | `__init__`: `DedupeService(redis_client=…→None)`, `PollingObserver(timeout=self._polling_interval→None)`, `get_cpu_executor(max_workers=4→None/5)` — tests assert isinstance/`_polling_interval` attribute, never the value handed to the constructor | 4 | TEST-GAP | `__init___mutmut_19`, `__init___mutmut_29`, `__init___mutmut_40` |
| TG-STABILITY-GATE | `_wait_for_file_stability`: disable gate `stability_time <= 0 → < 0` (0.0 must skip polling instantly); freshness `time.monotonic() - stable_since >= stability_time → +` / `>` | 3 | TEST-GAP | `_wait_for_file_stability__mutmut_3`, `_wait_for_file_stability__mutmut_27`, `_wait_for_file_stability__mutmut_28` |
| TG-FOLDER-PATH | `_ensure_camera_exists`: `folder_path = str(Path(self.camera_root)/folder_name)→None` → `Camera.from_folder_name(folder_name, folder_path→None)` — test asserts `camera.id`/`camera.name` only, never `camera.path` (`:1249–1267`) | 3 | TEST-GAP | `_ensure_camera_exists__mutmut_4`, `_ensure_camera_exists__mutmut_5`, `_ensure_camera_exists__mutmut_10` |
| TG-AUTO-CREATE-GATE | `_process_file`: `if auto_create_cameras and _camera_creator and folder_name:` → `and … or folder_name`, `_ensure_camera_exists(camera_id→None)` | 3 | TEST-GAP | `_process_file__mutmut_51`, `_process_file__mutmut_52`, `_process_file__mutmut_53` |
| LW-DEFAULT-TUNING | Constructor default tuning: `debounce_delay=0.5→1.5`, `stability_time=2.0→3.0`, `check_interval=0.5→1.5`, `max_checks=20→21` — perf knobs, every test overrides explicitly; asserting defaults locks tuning | 4 | LOW-VALUE | `__init___mutmut_1`, `__init___mutmut_3`, `_wait_for_file_stability__mutmut_11` |
| LW-QUEUE-DELAY | `_queue_delay_ms > 0 → >= 0 / > 1` (both copies, streams + legacy branch): delay sleep is a load-spreading knob; `>=0` adds one no-op `sleep(0)` per queue op | 4 | LOW-VALUE | `_queue_for_detection__mutmut_81`, `_queue_for_detection__mutmut_94` |
| EQ-SENTINEL | `None→""` on unused-before-set sentinels: `_queue_semaphore: … = None→""`, `file_hash: … = None→""`, `stable_since: … = None→""`, `self._loop = None→""` (stop tail; nothing reads after) | 3 | EQUIVALENT | `_queue_for_detection__mutmut_6`, `stop__mutmut_38` |
| EQ-SIZE-SENTINEL | `_wait_for_file_stability` `last_size: int = -1 → +1/-2` — first `stat()` size is ≥ 0, so `current_size == last_size` is False on iteration 1 for every value in this range (0-byte file: 0≠+1 too). Dead sentinel choice | 3 | EQUIVALENT | `_wait_for_file_stability__mutmut_6`, `_wait_for_file_stability__mutmut_7` |
| EQ-EMPTY-LOG-ONLY | `is_valid_image` / `is_valid_image_async` / `is_valid_video` `file_size == 0 → != 0 / == 1` inside the *already-rejected* (`size < MIN`) block — **both branches log a different warning then `return False`**; return value invariant (video variant: `size == 0` → `== 1` also falls through to `< 1024` reject). Only a log-text assertion could distinguish | 5 | EQUIVALENT | `is_valid_image__mutmut_7`, `is_valid_image__mutmut_8`, `is_valid_video__mutmut_7` |
| EQ-TAUTOLOGY-DECODE | `_create_event_handler` bytes-decode guard `isinstance(src_path, str) → (… ) or True` — `or True` makes str pass through and bytes-path unreachable *with identical observable behavior* for str input, and bytes input still decodes via else… (for bytes: `or True` → takes str branch → `.decode` skipped; watchdog src_path is str on Linux inotify; the decode branch is NFS/legacy defensive — no test feeds bytes) | 2 | EQUIVALENT | `_create_event_handler__mutmut_4`, `_create_event_handler__mutmut_11` |
| TG-EVENT-GATE | `_create_event_handler` on_created/on_modified gate `if not event.is_directory and is_supported_media_file(src):` → `or` — mutant processes **any non-media file** (a `.txt` write schedules processing, burning stability/validity cycles; a directory event with media-looking name schedules a dir) | 2 | TEST-GAP | `_create_event_handler__mutmut_5`, `_create_event_handler__mutmut_12` |
| TG-IMAGE-BOUNDARY | `is_valid_image`/`_async` `file_size < MIN_IMAGE_FILE_SIZE → <=` — a file of *exactly* 10240 bytes flips valid→rejected | 2 | TEST-GAP | `is_valid_image__mutmut_6`, `is_valid_image_async__mutmut_5` |
| TG-VIDEO-BOUNDARY | `is_valid_video` `file_size < 1024 → <= 1024 / < 1025` — 1024-byte file flips accepted→rejected | 2 | TEST-GAP | `is_valid_video__mutmut_10`, `is_valid_video__mutmut_11` |
| TG-RATE-LIMIT | `start()`: `self._queue_semaphore = asyncio.Semaphore(…) → None` — silently disables cross-queue rate limiting (per-call fallback semaphore restores it *within* one call, so bulk-upload connection protection is what erodes) | 1 | TEST-GAP | `start__mutmut_36` |

**Totals check:** EQ 216+3+3+5+2 = 229; LW 4+4 = 8; TG 27+12+10+6+5+5+5+4+3+3+3+2+2+2+1 = 90. **Sum = 327.**

## Why the big TEST-GAP clusters are gaps (evidence from the covering tests)

- **TG-STREAM-ARGS (27):** the single stream test
  (`test_redis_streams_integration.py:460`) asserts `add_detection.assert_awaited_once()` and
  `add_to_queue_safe.assert_not_awaited()` — zero kwargs inspection, so every arg mutation survives.
- **TG-LATENCY (12):** `_process_file` tests (`test_file_watcher.py:585–657, 1375–1402`) assert redis
  payload; `record_pipeline_stage_latency` is never patched/spied in the file_watcher suite.
- **TG-STOP-CANCEL (10):** `test_stop_uses_executor_for_blocking_join` (`:1688–1726`) mocks the loop
  and counts `run_in_executor` awaits (2) but never *invokes* the passed lambdas nor inspects their
  captured args; `test_stop_watcher_cancels_pending_tasks` (`:754`) doesn't verify the gather actually
  awaited cancellation completion.
- **TG-MKDIR-ARGS (6):** `test_start_creates_missing_camera_root` (`:1011`) pre-creates the *parent*
  and never re-starts onto an existing root — `parents=True` and `exist_ok=True` both unobservable.
- **TG-EVENT-SCHED (5):** `test_event_handler_without_running_loop` (`:921`) forces the failure branch
  (`_loop=None`); the happy thread-safe-schedule branch never runs.

## Drafted kill-tests (all UNVERIFIED — not run red/green; no tests were executed for this dossier)

### 1. `test_queue_for_detection_stream_call_contract` — kills TG-STREAM-ARGS (27/27)

Target: `backend/tests/unit/services/test_redis_streams_integration.py` (same imports/fixtures as
`TestFileWatcherStreamPath`). TDD: passes on original; fails on any arg/key mutation (e.g.
`detection_id=None`, `"TIMESTAMP"` key, `get_detection_stream_service(None)`).

```python
    @pytest.mark.asyncio
    async def test_queue_for_detection_stream_call_contract(self):
        """Streams path must call add_detection with the full durable-queue contract:
        camera_id, detection_id=0, file_path, and extra_fields carrying exactly
        timestamp/media_type/pipeline_start_time (+file_hash when dedupe produced one).
        """
        from backend.services.file_watcher import FileWatcher

        mock_redis = MagicMock()
        mock_redis.add_to_queue_safe = AsyncMock()
        mock_stream_service = AsyncMock(spec=DetectionStreamService)
        mock_stream_service.add_detection = AsyncMock(return_value="msg-1")

        mock_dedupe = AsyncMock(spec=DedupeService)
        mock_dedupe.is_duplicate_and_mark = AsyncMock(return_value=(False, "deadbeef" * 4))

        with (
            patch("backend.services.file_watcher.get_settings", autospec=True) as mock_settings,
            patch(
                "backend.services.file_watcher.get_detection_stream_service",
                return_value=mock_stream_service,
                autospec=True,
            ) as mock_get_stream,
        ):
            mock_settings.return_value.use_redis_streams = True
            mock_settings.return_value.foscam_base_path = "/export/foscam"
            mock_settings.return_value.file_watcher_polling = False
            mock_settings.return_value.file_watcher_max_concurrent_queue = 10
            mock_settings.return_value.file_watcher_queue_delay_ms = 0

            watcher = FileWatcher(
                camera_root="/export/foscam",
                redis_client=mock_redis,
                dedupe_service=mock_dedupe,
            )
            await watcher._queue_for_detection("front_door", "/path/img.jpg", "video")

        # Stream service must be built on the configured redis client (kills arg->None)
        assert mock_get_stream.call_args.args == (mock_redis,)

        kwargs = mock_stream_service.add_detection.await_args.kwargs
        assert kwargs["camera_id"] == "front_door"
        assert kwargs["detection_id"] == 0
        assert kwargs["file_path"] == "/path/img.jpg"

        extra = kwargs["extra_fields"]
        assert extra["media_type"] == "video"
        assert extra["timestamp"]  # ISO-8601 UTC string, non-empty
        assert extra["pipeline_start_time"]
        assert extra["file_hash"] == "deadbeef" * 4  # dedupe hash forwarded downstream
```

Without a dedupe service a companion assertion (`"file_hash" not in extra`) kills the
`or True`/always-include variant (`_queue_for_detection__mutmut_78`); fold it into the same test
by running a second `FileWatcher` with `dedupe_service=None` and asserting the key is absent.
(11/27 keys are `XX`/uppercase renames on `extra_fields` keys, 5 are call-arg clobbers, rest are
`.get()`/spread mutations — all caught by the exact-key/val asserts.)

### 2. `test_stop_awaits_pending_tasks_and_preserves_shutdown_args` — kills TG-STOP-CANCEL (10/10)

Target: `backend/tests/unit/services/test_file_watcher.py` (after `test_stop_uses_executor_for_blocking_join`, :1688).
TDD: fails on `gather(return_exceptions=True)` (task not yet `cancelled()` when stop returns) and on
every join/shutdown kwarg mutation; passes on original.

```python
@pytest.mark.asyncio
async def test_stop_awaits_pending_tasks_and_preserves_shutdown_args(file_watcher):
    """Bug-fix contract (wa0t.13): stop() must AWAIT cancellation of every pending debounce
    task (gather(*values)), join the observer with timeout=5, and shut the hash executor
    down with wait=True, cancel_futures=False — all via run_in_executor lambdas.
    """
    # Real pending debounce task that is mid-sleep when stop() runs
    async def _long_job() -> None:
        await asyncio.sleep(30)

    task = asyncio.create_task(_long_job())
    file_watcher._pending_tasks["/cam/camera1/x.jpg"] = task
    file_watcher.running = True
    # Replace the real executor so shutdown kwargs are observable and harmless
    file_watcher._hash_executor = MagicMock()

    mock_loop = AsyncMock()
    with (
        patch.object(file_watcher.observer, "stop", autospec=True),
        patch("asyncio.get_running_loop", autospec=True) as mock_get_loop,
    ):
        mock_get_loop.return_value = mock_loop
        await file_watcher.stop()

    # gather(*pending) contract: cancellation is COMPLETED, not just requested
    assert task.cancelled()
    assert file_watcher._pending_tasks == {}
    assert file_watcher._loop is None
    assert file_watcher.running is False

    # Two blocking calls deferred to the executor: observer.join + executor.shutdown
    assert mock_loop.run_in_executor.await_count == 2
    calls = [c.args for c in mock_loop.run_in_executor.await_args_list]
    assert all(executor is None for executor, _fn in calls)
    observer_join_fn, shutdown_fn = (fn for _e, fn in calls)

    with patch.object(file_watcher.observer, "join") as mock_join:
        observer_join_fn()
        mock_join.assert_called_once_with(timeout=5)

    shutdown_fn()
    file_watcher._hash_executor.shutdown.assert_called_once_with(
        wait=True, cancel_futures=False
    )
```

### 3. `test_process_file_records_watch_to_detect_latency` — kills TG-LATENCY (12/12)

Target: `backend/tests/unit/services/test_file_watcher.py` (near the pipeline-timing tests, :1851).
TDD: fails on any math op flip (`/`, `+`, `*1001`), call removal, stage-name case change, or arg
`None`; passes on original (2 `time.time()` calls, duration 1500.0).

```python
@pytest.mark.asyncio
async def test_process_file_records_watch_to_detect_latency(file_watcher, temp_camera_root):
    """The watch→detect stage latency must reach the pipeline-latency tracker with the
    stage name 'watch_to_detect' and int-millisecond duration ((end-start)*1000).
    """
    image_path = temp_camera_root / "camera1" / "latency.jpg"
    create_valid_test_image(image_path)

    # Exactly the two time.time() calls _process_file makes on the success path
    with (
        patch(
            "backend.services.file_watcher.time.time",
            side_effect=[1000.0, 1001.5],
            autospec=True,
        ),
        patch(
            "backend.services.file_watcher.record_pipeline_stage_latency",
            autospec=True,
        ) as mock_record,
    ):
        await file_watcher._process_file(str(image_path))

    mock_record.assert_called_once_with("watch_to_detect", 1500.0)
```

(1.5 s elapsed ⇒ `int(1.5*1000)=1500`; the `*1001` mutant yields 1501, `/1000` yields 0,
`+start_time` overflows to ~2.0e6 — all killed; `int(...)→None` raises TypeError inside the
try-block so the call never happens — also killed.)

### 4. `test_start_lifecycle_contracts` — kills TG-MKDIR-ARGS (6), TG-OBSERVER-SCHEDULE (5), TG-RATE-LIMIT (1) ⇒ 12

Target: `backend/tests/unit/services/test_file_watcher.py` (extend after `test_start_creates_missing_camera_root`, :1011).
TDD: fails on `parents/exist_ok/recursive` flips, handler/path clobbers, semaphore-`None`; passes on original.

```python
@pytest.mark.asyncio
async def test_start_lifecycle_contracts(temp_camera_root):
    """start() contract bundle:
    - rate-limit semaphore is materialized on start (not deferred to per-call fallback),
    - a MISSING camera root with MISSING parents is created recursively (parents=True),
    - an EXISTING camera root restarts without FileExistsError (exist_ok=True),
    - observer.schedule receives (handler, str(root)) with recursive=True.
    """
    mock_redis = AsyncMock()

    # --- missing, nested root ---
    root = temp_camera_root / "fresh" / "nested"
    watcher = FileWatcher(
        camera_root=str(root), redis_client=mock_redis, debounce_delay=0.1
    )
    assert watcher._queue_semaphore is None  # created by start(), not __init__

    with (
        patch.object(watcher.observer, "schedule", autospec=True) as mock_schedule,
        patch.object(watcher.observer, "start", autospec=True),
    ):
        await watcher.start()

    assert isinstance(watcher._queue_semaphore, asyncio.Semaphore)
    assert root.is_dir()  # parents=True survived the mkdir
    assert mock_schedule.call_args.args == (watcher._event_handler, str(root))
    assert mock_schedule.call_args.kwargs == {"recursive": True}
    assert watcher.running is True

    # --- existing root: exist_ok=True contract ---
    watcher2 = FileWatcher(
        camera_root=str(temp_camera_root), redis_client=mock_redis, debounce_delay=0.1
    )
    with (
        patch.object(watcher2.observer, "schedule", autospec=True),
        patch.object(watcher2.observer, "start", autospec=True),
    ):
        await watcher2.start()  # must NOT raise FileExistsError
    assert watcher2.running is True
```

### 5. `test_event_handler_uses_run_coroutine_threadsafe_with_loop` — kills TG-EVENT-SCHED (5/5)

Target: `backend/tests/unit/services/test_file_watcher.py` (after `test_event_handler_without_running_loop`, :921).
TDD: fails when the coroutine/loop args are `None`-ed or dropped; passes on original.

```python
def test_event_handler_uses_run_coroutine_threadsafe_with_loop(file_watcher):
    """Watchdog-thread contract: with a running loop captured, the handler must hand
    BOTH the _schedule_file_processing coroutine AND the captured loop to
    asyncio.run_coroutine_threadsafe (thread-safe hop from the observer thread).
    """
    fake_loop = MagicMock()
    fake_loop.is_running.return_value = True
    file_watcher._loop = fake_loop

    with patch(
        "backend.services.file_watcher.asyncio.run_coroutine_threadsafe",
        autospec=True,
    ) as mock_rcts:
        file_watcher._event_handler._schedule_async_task("/cam/camera1/img.jpg")

    mock_rcts.assert_called_once()
    coro, loop = mock_rcts.call_args.args
    assert coro is not None  # kills coroutine-arg -> None / dropped-arg mutants
    assert loop is fake_loop  # kills loop-arg -> None / dropped-arg mutants
    coro.close()  # silence un-awaited-coroutine warning
```

### 6. Size-boundary pair — kills TG-IMAGE-BOUNDARY (2) + TG-VIDEO-BOUNDARY (2)

Target: `backend/tests/unit/services/test_file_watcher.py` (after `test_is_valid_image_too_small`, :218;
add `is_valid_image_async` is already imported at :58; add `is_valid_video` to the import block, or
land the video case in `backend/tests/unit/services/test_video_support.py` near :162).
TDD: fails when `<=`/`< 1025` reject the exact-threshold file; passes on original.

```python
def test_is_valid_image_size_boundary_at_minimum(tmp_path):
    """MIN_IMAGE_FILE_SIZE is a STRICT lower bound: a file of exactly 10240 bytes is
    accepted (it is not 'smaller than the minimum'), 10239 bytes is rejected.
    """
    image_path = tmp_path / "edge.jpg"
    Image.new("RGB", (8, 8), color="blue").save(image_path, "JPEG", quality=50)
    raw = image_path.read_bytes()
    assert len(raw) < MIN_IMAGE_FILE_SIZE
    # Pad with zero bytes AFTER the JPEG EOI marker: still a loadable image
    image_path.write_bytes(raw + b"\x00" * (MIN_IMAGE_FILE_SIZE - len(raw)))
    assert image_path.stat().st_size == MIN_IMAGE_FILE_SIZE
    assert is_valid_image(str(image_path)) is True

    (tmp_path / "under.jpg").write_bytes(b"\x00" * (MIN_IMAGE_FILE_SIZE - 1))
    assert is_valid_image(str(tmp_path / "under.jpg")) is False


def test_is_valid_video_size_boundary(tmp_path):
    """1024-byte video is the inclusive minimum; 1023 is 'too small'."""
    ok = tmp_path / "edge.mp4"
    ok.write_bytes(b"\x00" * 1024)
    assert is_valid_video(str(ok)) is True

    small = tmp_path / "under.mp4"
    small.write_bytes(b"\x00" * 1023)
    assert is_valid_video(str(small)) is False
```

(The async twin `is_valid_image_async` can reuse the same fixture files inside an
`@pytest.mark.asyncio` variant to kill `is_valid_image_async__mutmut_5`.)

## Adjacent notes

- `_ensure_camera_exists__mutmut_29` (via `mutmut show`): `extra={"camera_id":…, "FOLDER_NAME":…}` — EQ-LOG-TEXT.
- `_debounced_process__mutmut_3`: `logger.debug(None)` in the CancelledError handler — EQ-LOG-TEXT (cancel
  contract itself is covered by `test_debounce_multiple_events` :660).
- `_schedule_file_processing__mutmut_10`: `.pop(file_path, None)` → `.pop(file_path,)` — pure keyword-syntax
  no-op (default None identical).
- If WP4.4 later adopts log-contract testing (caplog `record.extra` schema), 216 EQ-LOG-TEXT survivors
  become killable in one sweep — recommend as a separate decision, not per-mutant tests.
- **UNVERIFIED — none of the drafted tests above have been executed (red/green pending, run in the
  serial pytest lane).**
