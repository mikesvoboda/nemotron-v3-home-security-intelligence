# WP4.4 Triage Dossier — backend/services/file_watcher.py

- **Source**: `backend/services/file_watcher.py` (1114 lines)
- **Meta**: `mutants/backend/services/file_watcher.py.meta` — 613 keys, **104 survived** (exit_code 0)
- **Diffs**: obtained via `uv run mutmut show <key>` (all 104 succeeded, no cache conflicts)
- **Covering tests**: `backend/tests/unit/services/test_file_watcher.py` (2245 lines) and
  `backend/tests/unit/services/test_video_support.py` (683 lines), per `mutants/mutmut-stats.json`
  `tests_by_mangled_function_name`.

## Cluster table

| # | Cluster | Count | Class | Example keys (suffix) |
|---|---------|-------|-------|----------------------|
| E1 | Validation/retry helpers: logger message args clobbered (`f"..."` → `None`) — pure log text | 9 | EQUIVALENT | `x_is_valid_image__mutmut_9`, `x_is_valid_image__mutmut_17`, `x__retry_validation_async__mutmut_5` |
| E2 | `_ensure_camera_exists`: log text + `extra={...}` dict keys clobbered (XXwrapsXX, CASE flips, `extra=None`) | 14 | EQUIVALENT | `xǁFileWatcherǁ_ensure_camera_exists__mutmut_13`, `__mutmut_17`, `__mutmut_28` |
| E3 | `FileWatcher.start()`: log text + `extra` dict keys clobbered (incl. mutmut_8 error-msg text — raised `RuntimeError` still matches the `pytest.raises(match=...)` substring) | 32 | EQUIVALENT | `xǁFileWatcherǁstart__mutmut_1`, `__mutmut_8`, `__mutmut_27` |
| E4 | `FileWatcher.stop()`: log text clobbered (case flips, XXwraps, `None`) | 16 | EQUIVALENT | `xǁFileWatcherǁstop__mutmut_2`, `__mutmut_9`, `__mutmut_44` |
| E5 | Keyword-default removals that keep semantics: `pop(p, None)`→`pop(p,)`; `shutdown(cancel_futures=None)` (falsy == False), omitted `wait=`/`cancel_futures=` (defaults equal original values); `self._loop = ""` (falsy, and the only `is None` check runs after reassignment) — NOTE `wait=None` is falsy→does-not-wait, classified G9 not here | 5 | EQUIVALENT | `xǁFileWatcherǁ_schedule_file_processing__mutmut_10`, `xǁFileWatcherǁstop__mutmut_30`, `__mutmut_38` |
| E6 | Validation size-branch log *selection* flipped (`if file_size == 0` → `!= 0` / `== 1`) — return value identical (still `False`), only which warning fires changes | 3 | LOW-VALUE | `x_is_valid_image__mutmut_7`, `x_is_valid_image__mutmut_8`, `x_is_valid_video__mutmut_7` |
| G1 | `is_valid_image`: `file_size < MIN_IMAGE_FILE_SIZE` → `<=` — a file of exactly 10240 bytes flips True→False. Existing tests only probe `>=MIN` (15–30 KB image) and `<MIN` (tiny image), never the exact boundary | 1 | TEST-GAP | `x_is_valid_image__mutmut_6` |
| G2 | `is_valid_video`: 1 KB boundary `< 1024` → `<= 1024` / `< 1025` — a 1024-byte video flips True→False. Tests cover 2048 B (valid) and 500 B (invalid), never 1023/1024 | 2 | TEST-GAP | `x_is_valid_video__mutmut_10`, `__mutmut_11` |
| G3 | `_ensure_camera_exists`: `folder_path` content destroyed (`str(Path(root)/folder)` → `None`, `str(None)`, or `from_folder_name(folder, None)`) — `camera.folder_path` written to the DB would be garbage. `test_ensure_camera_exists_creates_camera` (test_file_watcher.py:1249) asserts `camera.id`/`camera.name` but **never `camera.folder_path`** | 3 | TEST-GAP | `xǁFileWatcherǁ_ensure_camera_exists__mutmut_4`, `__mutmut_5`, `__mutmut_10` |
| G4 | `start()` mkdir robustness: `mkdir(parents=True, exist_ok=True)` args mutated (`parents=None/False`, arg dropped). Test `test_start_creates_missing_camera_root` (:1011) uses a **single-level** missing dir whose parent exists, so `parents=False` is invisible. With `parents=False`, a nested root (`/a/b/c` with `/a` missing) raises `FileNotFoundError` and `start()` crashes | 6 | TEST-GAP | `xǁFileWatcherǁstart__mutmut_43`, `__mutmut_45`, `__mutmut_47` |
| G5 | `start()` observer wiring: `observer.schedule(self._event_handler, str(root), recursive=True)` mutated — handler→`None`, path→`"None"`, `recursive=True`→`None`/`False`/dropped (recursive=False silently misses every camera subfolder — new uploads are never detected). No test asserts `schedule` arguments; `test_start_watcher` (:725) patches only `observer.start` | 5 | TEST-GAP | `xǁFileWatcherǁstart__mutmut_49`, `__mutmut_51`, `__mutmut_56` |
| G6 | `start()`: `self._queue_semaphore = asyncio.Semaphore(...)` → `= None` — the shared rate-limiter is lost; `_queue_for_detection` falls back to a *fresh per-call* semaphore, so bulk-upload connection limiting silently stops working. Tests set `watcher._queue_semaphore` manually and never assert `start()` created it | 1 | TEST-GAP | `xǁFileWatcherǁstart__mutmut_36` |
| G7 | `stop()`: `await asyncio.gather(*self._pending_tasks.values(), return_exceptions=True)` → `await asyncio.gather(return_exceptions=True)` — stop() returns **without waiting** for cancelled debounce tasks to finish unwinding. `test_stop_watcher_cancels_pending_tasks` (:754) sleeps 0.05 s afterward and checks only `running`, masking the missing await | 1 | TEST-GAP | `xǁFileWatcherǁstop__mutmut_13` |
| G8 | `stop()`: `observer.join(timeout=5)` → `timeout=None`/`6` — the wa0t.13 bounded-shutdown contract. The lambda body is opaque to `test_stop_uses_executor_for_blocking_join` (:1688), which counts `run_in_executor` calls but never invokes the captured lambda | 2 | TEST-GAP | `xǁFileWatcherǁstop__mutmut_21`, `__mutmut_22` |
| G9 | `stop()`: hash-executor shutdown destroyed — lambda body → `None` (executor **never** shut down: thread leak), `wait=True`→`None`/`False` (stop returns before worker threads exit), `cancel_futures=False`→`True` (queued hash jobs silently cancelled during shutdown) | 4 | TEST-GAP | `xǁFileWatcherǁstop__mutmut_27`, `__mutmut_28`, `__mutmut_33` |

**Totals**: EQUIVALENT 76 + LOW-VALUE 3 + TEST-GAP 25 = **104** ✓

## Drafted tests (highest-value TEST-GAP clusters)

TDD procedure (all): apply the draft, run against the **mutant** source — the new assert fails; run against the **original** `backend/services/file_watcher.py` — it passes; then `mutmut run` should mark the cluster killed. // UNVERIFIED - not yet run red/green

### T1 — kills G1: image minimum-size boundary (`backend/tests/unit/services/test_file_watcher.py`)

```python
def test_is_valid_image_exactly_at_minimum_size_is_valid(tmp_path):
    """A file of exactly MIN_IMAGE_FILE_SIZE bytes must be accepted (threshold is exclusive).

    Kills `<` -> `<=` boundary mutants: with `<=` a boundary-size image is rejected.
    """
    image_path = tmp_path / "boundary.jpg"
    create_valid_test_image(image_path)
    exact_size = image_path.stat().st_size

    with patch("backend.services.file_watcher.MIN_IMAGE_FILE_SIZE", exact_size):
        assert is_valid_image(str(image_path)) is True
```

### T2 — kills G2: video 1 KB boundary (`backend/tests/unit/services/test_video_support.py`)

```python
    def test_is_valid_video_at_1kb_boundary(self, tmp_path: Path) -> None:
        """is_valid_video boundary is exclusive: exactly 1024 bytes is valid, 1023 is not.

        Kills `< 1024` -> `<= 1024` / `< 1025` mutants that reject a 1024-byte file.
        """
        at_min = tmp_path / "at_min.mp4"
        at_min.write_bytes(b"x" * 1024)
        assert is_valid_video(str(at_min)) is True

        below = tmp_path / "below.mp4"
        below.write_bytes(b"x" * 1023)
        assert is_valid_video(str(below)) is False
```

### T3 — kills G3: camera folder_path content (`backend/tests/unit/services/test_file_watcher.py`, appended to the Camera auto-creation section; uses existing `file_watcher_with_auto_create` / `mock_camera_creator` fixtures)

```python
@pytest.mark.asyncio
async def test_ensure_camera_exists_passes_full_folder_path(
    file_watcher_with_auto_create, mock_camera_creator
):
    """The auto-created Camera must carry the resolved folder_path (contract with DB records).

    Kills folder_path destruction mutants (None / "None"): test_ensure_camera_exists_creates_camera
    checks id/name only, so folder_path was never asserted.
    """
    await file_watcher_with_auto_create._ensure_camera_exists(
        camera_id="front_door",
        folder_name="Front Door",
    )

    camera = mock_camera_creator.call_args[0][0]
    assert camera.folder_path == str(
        Path(file_watcher_with_auto_create.camera_root) / "Front Door"
    )
```

### T4 — kills G4 (parents variants): nested camera root creation (`test_file_watcher.py`)

```python
@pytest.mark.asyncio
async def test_start_creates_deeply_nested_missing_camera_root(temp_camera_root):
    """start() must create a camera root whose intermediate parents are missing (parents=True).

    Kills mkdir parents=True -> False/None mutants: with parents=False the nested mkdir
    raises FileNotFoundError and start() crashes. (exist_ok variants stay alive — unobservable
    without a TOCTOU race; the `if not exists` guard prevents them firing.)
    """
    mock_redis = AsyncMock()
    nested_root = temp_camera_root / "a" / "b" / "cameras"

    watcher = FileWatcher(
        camera_root=str(nested_root),
        redis_client=mock_redis,
        debounce_delay=0.1,
    )

    with patch.object(watcher.observer, "start", autospec=True):
        await watcher.start()

    assert nested_root.exists()
    assert watcher.running is True
```

### T5 — kills G5: recursive schedule wiring (`test_file_watcher.py`)

```python
@pytest.mark.asyncio
async def test_start_schedules_recursive_watch_with_event_handler(file_watcher, temp_camera_root):
    """start() must schedule the watcher's own handler recursively on the camera root.

    Kills schedule(handler=None), str(None) path, and recursive=True -> None/False/dropped
    mutants — a non-recursive watch silently misses every camera subfolder upload.
    """
    with (
        patch.object(file_watcher.observer, "start", autospec=True),
        patch.object(file_watcher.observer, "schedule", autospec=True) as mock_schedule,
    ):
        await file_watcher.start()

    mock_schedule.assert_called_once_with(
        file_watcher._event_handler,
        str(temp_camera_root),
        recursive=True,
    )
```

### T6 — kills G7: stop() waits for task cancellation (`test_file_watcher.py`)

```python
@pytest.mark.asyncio
async def test_stop_waits_for_pending_task_cancellation(file_watcher):
    """stop() must await gather() over the pending debounce tasks before returning.

    Kills the gather(*tasks) -> gather() mutant: without the task arguments stop() returns
    while cancelled tasks are still unwinding (task.done() is False at return time).
    """
    with patch.object(file_watcher.observer, "start", autospec=True):
        await file_watcher.start()

    started = asyncio.Event()

    async def long_running() -> None:
        started.set()
        await asyncio.sleep(10)

    task = asyncio.create_task(long_running())
    file_watcher._pending_tasks["/fake/file.jpg"] = task
    await started.wait()

    with (
        patch.object(file_watcher.observer, "stop", autospec=True),
        patch.object(file_watcher.observer, "join", autospec=True),
    ):
        await file_watcher.stop()

    # stop() awaited the cancellation: the task is fully done, not just cancel-requested
    assert task.done()
    assert str("/fake/file.jpg") not in file_watcher._pending_tasks
```

## Notes

- **G6 (semaphore=None) and G8/G9 (join timeout, executor shutdown args)** remain TEST-GAP but were not drafted (drafting cap). G8/G9 are killable by capturing the lambda passed to `run_in_executor` from `test_stop_uses_executor_for_blocking_join`'s mock and invoking it against a recording `MagicMock` observer/executor — the existing :1688 test is 90% of the way there; adding `call_args[0][1]()` + a `mock_join.assert_called_once_with(timeout=5)` closes it.
- **G4 exist_ok sub-variants** (mutmut_44, _46, _48) stay live after T4 — the `if not camera_root_path.exists()` guard means `exist_ok` only matters in a TOCTOU race; not worth a contrived test.
- E3 mutmut_8 (`error_msg` text XX-wrapped) is EQUIVALENT because `test_start_without_event_loop` uses `pytest.raises(match="MUST be started within an async context")` — a substring search that the XX prefix does not break.
- All log-clobber clusters (E1–E4, 71 mutants) assume log content is not a behavioral contract for this codebase (structlog records but no test asserts message text in file_watcher).

## Covering test file inventory

| Function | Test file |
|---|---|
| `is_valid_image`, `_retry_validation_*`, `_debounced_process`, `_ensure_camera_exists`, `_schedule_file_processing`, `start`, `stop` | `backend/tests/unit/services/test_file_watcher.py` |
| `is_valid_video`, `is_valid_image` | `backend/tests/unit/services/test_video_support.py` |
