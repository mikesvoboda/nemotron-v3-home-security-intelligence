# WP4.4 Triage Dossier — backend/services/stream_manager.py

- Verdict source: `mutants/backend/services/stream_manager.py.meta` (`exit_code_by_key`)
- Survivors: **211** / 361 keys (86 killed, 64 unchecked at read time)
- Diff extraction: `uv run mutmut show` worked but was CPU-starved by a concurrent triage agent (`xargs -P 8` batch); switched to AST diffing of the `xǁStreamManagerǁ<fn>__mutmut_N` variant defs in `mutants/backend/services/stream_manager.py` against the original (`ast.unparse` + unified diff). All 211 diffs obtained: `/tmp/wp25/wp44-triage/stream_manager_astdiffs.txt`.
- Covering test file (only one): `backend/tests/unit/services/test_stream_manager.py`

## Why so many survive (structural cause)

The suite asserts liveness and call-counts, never payloads:
- `test_add_stream_updates_health_in_redis` (:320) asserts only `hset.assert_called()` + expected key **substring inside `str(call_args_list)`** — the key is checked as a substring of the whole repr, never as the actual argument, and the `mapping` dict is never inspected.
- `test_remove_stream_deletes_redis_health_key` (:402) asserts `delete.assert_called()` with no key argument.
- `test_health_tracking_updates_periodically` (:486) asserts `hset.call_count > 1` only.
- `test_reconnection_uses_exponential_backoff` (:585) asserts only the **first** backoff delay == 5; the 5→10→20 sequence and the stored `retry_count` are never asserted.
- `test_successful_reconnection_resets_backoff` (:637) wraps its assertion in `if "camera1" in manager._streams:` — a timing-dependent conditional assert that silently skips.
- `test_add_stream_uses_tcp_transport` (:300) asserts `assert_called()` on the patched `cv2.VideoCapture` with **no argument matchers**, and it is the only test reaching `_create_capture_sync` (all other tests inject `capture_factory`, which bypasses it entirely).
- Connection-loop state writes are asserted only inside the conditional test above.
- Broad `except Exception` in `_connection_loop` / `_health_monitoring_loop` swallows TypeErrors from clobbered interior call args, so broken-argument mutants still look like "reconnect loop kept running" to the liveness-style tests.

## Cluster table (21 clusters, sum = 211)

| # | Cluster | Count | Class | Example keys (fn__mutmut_N) | Note |
|---|---------|-------|-------|------------------------------|------|
| 1 | E-LOG: logger message/extra clobbered (msg→None, extra dropped, extra dict keys → `XXxXX`/`UPPER`, `str(e)`→`str(None)`) in add/remove_stream, _connection_loop, _handle_connection_failure, _health_monitoring_loop, _update_health | 45 | EQUIVALENT | add_stream__3, _handle_connection_failure__16, _health_monitoring_loop__41 | Pure log payload; no test reads log records. Semantically identical for behavior. |
| 2 | E-CTXKEY: `add_stream` initial stream-context dict key renames (`rtsp_url`/`capture`/`last_error`/`connection_time` → `XXxXX`/`UPPER`) | 8 | EQUIVALENT | add_stream__12, add_stream__14, add_stream__21 | Initial values are None; `_connection_loop` overwrites via original keys, `_update_health` `.get()` returns None (falsy) → same omitted-field outcome as original. |
| 3 | E-FALL: defensive arg / fallback tweaks with no observable value change (pop() default removal under guard, `.get(k, default)` tweaks where default never used or value identical, `_update_health` kwarg omissions that fall through to the just-written identical value, fps ternary boundary `>=`/`>` / `or True` / `>=0` unreachable paths, tail `break`→`return`) | 21 | EQUIVALENT | remove_stream__7, _cleanup_stream__5, _handle_connection_failure__36 | Reachable paths produce byte-identical state and payloads. |
| 4 | L-FALLRACE: `_update_health` fallback lookups (`stream.get('retry_count',0)` → `.get('retry_count',1)` / `.get(None,0)`) that differ only in a deleted-camera race window (retry_count field `'0'` vs `'1'`) | 2 | LOW-VALUE | _update_health__19, _update_health__24 | Real diff only when camera removed between membership check and `.get` — behavior nobody should pin. (`.get(None,0)` at __18 differs on the reachable missing-key path → T-REDBODY.) |
| 5 | L-CAPSENT: `_cleanup_stream` capture-reset sentinel tweaks (`capture` = None → `''` / key renames) | 3 | LOW-VALUE | _cleanup_stream__13, _cleanup_stream__14, _cleanup_stream__15 | A re-release of a stale value on double-cleanup; only lands in a warning log. |
| 6 | L-CAPTIMEVAL: `_create_capture_sync` timeout constants nudged ±1ms (10000→10001, 5000→5001) | 2 | LOW-VALUE | _create_capture_sync__10, _create_capture_sync__15 | Real but pinning exact ms values is brittle; only the dropped-arg mutants matter (cluster 14). |
| 7 | T-REDBODY: `_update_health` payload construction clobbered — Redis field-name renames (`status`/`connection_time`/`retry_count`/`last_error` → `XXxXX`/`UPPER`), lookup-key clobbers that silently drop fields (`stream.get(None)`, renames), gate inversions (`is None` ↔ `is not None`), `last_error=None` value drop, `str(None)`, and `hset(key, mapping=None)` / `hset(key)` dropping the whole payload | 24 | TEST-GAP | _update_health__3, _update_health__16, _update_health__44 | Tests run these lines every test but only assert key-substring in `str(call_args_list)` (:320). The persisted Redis hash schema (docstring: status/connection_time/fps/retry_count/last_error) is entirely unasserted. |
| 8 | T-FPS: `_health_monitoring_loop` FPS pipeline clobbered — `frame_count` init/increment/reset (`0→None/1`, `+=1 → =1/-=1/+=2`), `elapsed = current - last` → `+`, fps expression `/`→`*`, `fps=None` / `frame_count=None` TypeError-crash paths, cadence `sleep(0.033)`→None/1.033, fps kwarg dropped from the update call, and `health_data['fps']` field renames | 23 | TEST-GAP | _health_monitoring_loop__13, _health_monitoring_loop__23, _update_health__32 | `test_health_tracking_updates_periodically` (:486) counts hset calls; never parses the `fps` field. TypeError variants funnel into the generic except (release+break) and look like normal disconnects. |
| 9 | T-STATEWRITE: `_connection_loop` success-path stream-context writes clobbered — `retry_count` reset → None / key renames / `1`, `last_error` clear → `''` / wrong key (stale error persists), `connection_time` → None / wrong key / `datetime.now(None)` (naive, no UTC offset) | 11 | TEST-GAP | _connection_loop__17, _connection_loop__21, _connection_loop__27 | The only reset assertion (:637) is inside `if "camera1" in manager._streams:` and its global AsyncMock sleep patch makes the ordering non-deterministic — it skips or passes without observing the write. |
| 10 | T-STATUS: health status literals clobbered (`None`, `'XXxXX'`, UPPER) in the `_update_health('connecting'/'connected'/'reconnecting')` calls from add_stream / _connection_loop / _handle_connection_failure / monitoring loop | 12 | TEST-GAP | add_stream__31, _connection_loop__32, _handle_connection_failure__38 | The `status` field in the hset mapping is never read by any test (:320). |
| 11 | T-MONITOR-BROKEN: `_health_monitoring_loop` control flow broken — loop-continue `and`→`or`, `isOpened()`/read-success checks inverted, frame-read call clobbered (TypeError→except), `capture.read` dropped, release args → None (capture leak) | 10 | TEST-GAP | _health_monitoring_loop__4, _health_monitoring_loop__6, _health_monitoring_loop__12 | All funnel into the generic except + release + break; `_connection_loop` then reconnects, so the hset-count and `running=True` tests see normal behavior. Note `isOpened` inversion releases without ever reading a frame. |
| 12 | T-CONNCALL: interior call-arg clobbers that raise TypeError and get swallowed by the broad except (positional `camera_id`/`status` dropped in `_update_health` / `_health_monitoring_loop` calls) — the intended status update never happens; the failure/reconnect path takes over instead | 8 | TEST-GAP | _connection_loop__30, _connection_loop__36, _health_monitoring_loop__34 | Tests only observe "loop kept running / some hset happened" (:536, :724). |
| 13 | T-HEALTHKEY: Redis health key composed from wrong camera_id (`key = None`, or the `camera_id` argument to `_update_health`/`_delete_health_key`/`hgetall` clobbered → key `hsi:stream:health:None`) — health written/read/deleted at the wrong Redis key | 9 | TEST-GAP | add_stream__30, _delete_health_key__1, get_stream_health__1 | :320 greps the key inside `str(call_args_list)` (the camera_id string also appears in the mapping repr elsewhere? No — the mapping has no camera_id, but `assert_called()` never checks the key argument itself); :402 checks nothing. Real Redis would silently orphan every health key. |
| 14 | T-CAPTIMEOUT: `_create_capture_sync` timeout `capture.set(...)` calls clobbered — property arg → None, value arg → None, single-arg calls (TypeError swallowed by `_create_capture`'s except → returns None → reconnect churn) so the 10s open / 5s read timeouts are never applied | 8 | TEST-GAP | _create_capture_sync__6, _create_capture_sync__9, _create_capture_sync__13 | `capture.set` is a bare MagicMock in :300's fixture; never asserted. Note the TypeError variants change `VideoCapture()` construction outcomes too (capture=None → silent failure loop). |
| 15 | T-COUNTER: `_handle_connection_failure` retry counter write clobbered — `retry_count + 1` stored under renamed key / `retry_count - 1` / `+ 2`, and the `retry_count=` kwarg passed to `_update_health` offset ∓1 | 6 | TEST-GAP | _handle_connection_failure__7, _handle_connection_failure__9, _handle_connection_failure__40 | :585 asserts only `backoff_delays[0] == 5`; the escalating 5→10→20 sequence and persisted retry_count are never asserted, so −1/+2 both pass. |
| 16 | T-LASTERRSTORE: connection-failure error text clobbered at source or storage — `_handle_connection_failure(camera_id, None)` / case-variants of `'Failed to open stream'` (stored verbatim into `last_error`), `last_error` stored → None / wrong key — persisted health `last_error` missing, wrong, or stale | 7 | TEST-GAP | _handle_connection_failure__11, _handle_connection_failure__12, _connection_loop__39 | Failure tests (:536, :724) never read the stored/persisted `last_error` value. |
| 17 | T-CAPARGS: `VideoCapture` construction args clobbered — `rtsp_url` → None / dropped, `cv2.CAP_FFMPEG` backend arg → None / dropped in `_create_capture` executor lambda / `_create_capture_sync` | 5 | TEST-GAP | _create_capture_sync__2, _create_capture_sync__4, _create_capture__9 | :300 accepts any call args; the "TCP transport" acceptance criterion (FFmpeg backend) is unenforced. Dropping the url shifts `cv2.CAP_FFMPEG` into the url slot. |
| 18 | T-ADDGUARD: `add_stream` existing-stream cleanup guard inverted (`in` → `not in`) / cleanup target → None — replacing a camera_id no longer tears down the old connection task (orphaned loop + capture leak) | 2 | TEST-GAP | add_stream__1, add_stream__2 | :351 only asserts the dict has one entry; the old `connection_camera1` task is never checked for cancellation. |
| 19 | T-CLEANUP-TASK: `_cleanup_stream` task-name → None / registry entry never popped — connection task not cancelled on removal, `_background_tasks` dict grows stale entries | 2 | TEST-GAP | _cleanup_stream__1, _cleanup_stream__3 | stop/remove tests assert `_streams` empty, never `_background_tasks`. |
| 20 | T-DECODE: `get_stream_health` bytes-decoding disabled (`isinstance(k, bytes) and False`) — byte keys/values from real Redis clients returned undecoded | 2 | TEST-GAP | get_stream_health__5, get_stream_health__7 | Both health tests (:444, :468) stub `hgetall` with str keys; the decode branch is executed only vacuously. |
| 21 | T-REMOVEPOP: `remove_stream` `self._streams.pop(None, None)` — camera stays registered after removal | 1 | TEST-GAP | remove_stream__5 | :402 asserts only `delete.assert_called()`, never `'camera1' not in manager._streams`. |

Class totals: TEST-GAP 130, EQUIVALENT 74, LOW-VALUE 7.

## Drafted tests (6 — UNVERIFIED, not yet run red/green)

All follow the existing file's style (module `backend/tests/unit/services/test_stream_manager.py`, fixtures `mock_redis_client`, `mock_capture_factory` idiom, `patch("backend.services.stream_manager...")`). TDD procedure for each: apply the cluster's mutant → run test → assert must FAIL; run on original → must PASS.

### 1. `test_add_stream_writes_expected_redis_key_and_status` → kills T-HEALTHKEY (add path), T-STATUS (connecting), T-REDBODY (status key, mapping clobbers 44/46)

```python
@pytest.mark.asyncio
async def test_add_stream_writes_expected_redis_key_and_status(mock_redis_client):
    """ACCEPTANCE: add_stream persists status='connecting' at the exact health key.

    Kills: key=clobbered-to-None mutants, status literal clobbers, field-name
    renames in health_data, hset(mapping=None)/hset(key) payload drops.
    """
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    mock_cap.read.return_value = (True, MagicMock())
    manager = StreamManager(redis_client=mock_redis_client, capture_factory=lambda _url: mock_cap)
    await manager.start()

    await manager.add_stream("camera1", "rtsp://example.com/stream1")

    # No real await between create_task and hset (AsyncMock never suspends),
    # so exactly the add_stream health write has happened at this point.
    expected_key = f"{REDIS_HEALTH_KEY_PREFIX}camera1"
    mock_redis_client.hset.assert_called_once_with(
        expected_key, mapping={"status": "connecting", "retry_count": "0"}
    )

    await manager.stop()
```

### 2. `test_connection_success_resets_state_and_publishes_connected_health` → kills T-STATEWRITE (all 11), T-REDBODY members observable on the connected payload (3,4,6,10,11,12,13,14,15,16,17,20,34,35,37,38,39), T-STATUS (connected)

```python
@pytest.mark.asyncio
async def test_connection_success_resets_state_and_publishes_connected_health(mock_redis_client):
    """ACCEPTANCE: successful connect resets retry state and publishes UTC
    connection_time with retry_count '0'.

    Kills: retry_count reset clobbers, stale-key last_error/connection_time
    writes, naive datetime.now(None), and connected-payload field clobbers in
    _update_health.
    """
    import contextlib

    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    mock_cap.read.return_value = (True, MagicMock())

    manager = StreamManager(redis_client=mock_redis_client, capture_factory=lambda _url: mock_cap)
    await manager.start()
    # Seed a stream with a dirty prior-failure state
    manager._streams["camera1"] = {
        "rtsp_url": "rtsp://example.com/stream1",
        "capture": None,
        "retry_count": 3,
        "last_error": "boom",
        "connection_time": None,
    }

    with patch(
        "backend.services.stream_manager.StreamManager._health_monitoring_loop",
        new=AsyncMock(),
    ):
        task = asyncio.create_task(
            manager._connection_loop("camera1", "rtsp://example.com/stream1")
        )
        await asyncio.sleep(0.1)
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    state = manager._streams["camera1"]
    assert state["retry_count"] == 0
    assert state["last_error"] is None
    assert state["connection_time"] is not None
    assert "+00:00" in state["connection_time"]  # UTC-aware ISO, not naive

    connected_maps = [
        c.kwargs.get("mapping", {})
        for c in mock_redis_client.hset.call_args_list
        if c.kwargs.get("mapping", {}).get("status") == "connected"
    ]
    assert connected_maps, "no 'connected' health update published to Redis"
    assert connected_maps[0]["connection_time"] == state["connection_time"]
    assert connected_maps[0]["retry_count"] == "0"

    await manager.stop()
```

### 3. `test_repeated_failures_escalate_retry_counter_and_persist_error` → kills T-COUNTER (all 6), T-LASTERRSTORE (11,12,13), T-REDBODY gate members (16/34/39 on the reconnecting payload)

```python
@pytest.mark.asyncio
async def test_repeated_failures_escalate_retry_counter_and_persist_error(mock_redis_client):
    """ACCEPTANCE: each failure increments the stored AND published retry
    counter, and the error text persists; backoff follows the documented
    5s -> 10s sequence.

    Kills: retry_count write key/offset clobbers, last_error storage clobbers,
    and _update_health gate inversions on the 'reconnecting' payload.
    """
    manager = StreamManager(redis_client=mock_redis_client)
    await manager.start()
    manager._streams["camera1"] = {
        "rtsp_url": "rtsp://example.com/stream1",
        "capture": None,
        "retry_count": 0,
        "last_error": None,
        "connection_time": None,
    }

    with patch("backend.services.stream_manager.asyncio.sleep", new_callable=AsyncMock):
        await manager._handle_connection_failure("camera1", "boom-1")
        await manager._handle_connection_failure("camera1", "boom-2")

    state = manager._streams["camera1"]
    assert state["retry_count"] == 2
    assert state["last_error"] == "boom-2"

    maps = [c.kwargs.get("mapping", {}) for c in mock_redis_client.hset.call_args_list]
    reconnecting = [m for m in maps if m.get("status") == "reconnecting"]
    assert [m["retry_count"] for m in reconnecting] == ["1", "2"]
    assert reconnecting[-1]["last_error"] == "boom-2"

    # Backoff sequence must escalate: _calculate_backoff uses the PREVIOUS count
    assert manager._calculate_backoff(0) == 5
    assert manager._calculate_backoff(1) == 10
    assert manager._calculate_backoff(2) == 20

    await manager.stop()
```

### 4. `test_duplicate_add_stream_cancels_previous_connection_task` → kills T-ADDGUARD (both), T-CLEANUP-TASK, T-REMOVEPOP

```python
@pytest.mark.asyncio
async def test_duplicate_add_stream_cancels_previous_connection_task(mock_redis_client):
    """ACCEPTANCE: re-adding a camera_id tears down the old connection task.

    Kills: inverted membership guard in add_stream, cleanup(None), the
    un-popped/None task registry in _cleanup_stream, and the remove_stream
    pop(None, None) that leaves the camera registered.
    """
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    mock_cap.read.return_value = (True, MagicMock())
    manager = StreamManager(redis_client=mock_redis_client, capture_factory=lambda _url: mock_cap)
    await manager.start()

    await manager.add_stream("camera1", "rtsp://example.com/stream1")
    await asyncio.sleep(0.05)  # let the connection task start
    first_task = manager._background_tasks["connection_camera1"]

    await manager.add_stream("camera1", "rtsp://example.com/stream2")
    await asyncio.sleep(0.05)

    assert first_task.cancelled(), "old connection task was not cancelled on replace"
    assert manager._streams["camera1"]["rtsp_url"] == "rtsp://example.com/stream2"
    # registry holds exactly one live connection task for the camera
    assert manager._background_tasks["connection_camera1"] is not first_task

    await manager.remove_stream("camera1")
    assert "camera1" not in manager._streams
    assert "connection_camera1" not in manager._background_tasks
    mock_redis_client.delete.assert_called_with(f"{REDIS_HEALTH_KEY_PREFIX}camera1")

    await manager.stop()
```

### 5. `test_health_monitoring_loop_reads_frames_then_releases_on_drop` → kills T-MONITOR-BROKEN core (4,6,7,8,9,10,11,12,40,50), T-FPS value members (13,14,15,16,17,18,23,26), T-HEALTHKEY/T-STATUS on the fps update call

```python
@pytest.mark.asyncio
async def test_health_monitoring_loop_reads_frames_then_releases_on_drop(mock_redis_client):
    """ACCEPTANCE: while connected the loop reads frames, publishes numeric fps,
    and on a read failure releases the capture EXACTLY ONCE and returns.

    Kills: inverted isOpened/read-success checks (release with zero frames
    read), clobbered read/loop calls (TypeError before any frame), release(None)
    capture leaks, and fps arithmetic clobbers (* instead of /, wrong counts).
    """
    reads_done = 0

    class OkThenDrop:
        def isOpened(self):
            return True

        def read(self):
            nonlocal reads_done
            reads_done += 1
            return (False, None) if reads_done > 3 else (True, MagicMock())

        def release(self):
            self.released = getattr(self, "released", 0) + 1

    capture = OkThenDrop()
    manager = StreamManager(
        redis_client=mock_redis_client, health_update_interval=0.05
    )
    await manager.start()
    manager._streams["camera1"] = {
        "rtsp_url": "rtsp://x",
        "capture": capture,
        "retry_count": 0,
        "last_error": None,
        "connection_time": None,
    }

    # Must terminate on its own (read drop), not hang or spin forever
    await asyncio.wait_for(
        manager._health_monitoring_loop("camera1", capture), timeout=5
    )

    assert reads_done >= 2, "loop exited without ever reading frames"
    assert capture.released == 1, "capture not released exactly once"

    fps_maps = [
        c.kwargs.get("mapping", {})
        for c in mock_redis_client.hset.call_args_list
        if "fps" in c.kwargs.get("mapping", {})
    ]
    assert fps_maps, "no fps health update published"
    fps_value = float(fps_maps[-1]["fps"])  # kills fps=None / renames / str(None)
    assert 5.0 <= fps_value <= 200.0  # ~33ms cadence; kills frame_count=/fps=* clobbers
    assert fps_maps[-1]["status"] == "connected"

    await manager.stop()
```

### 6. `test_get_stream_health_decodes_bytes_keys_and_uses_exact_key` → kills T-DECODE (both), T-HEALTHKEY read path (get_stream_health__1/3)

```python
@pytest.mark.asyncio
async def test_get_stream_health_decodes_bytes_keys_and_uses_exact_key(mock_redis_client):
    """ACCEPTANCE: health reads from the exact camera key and decodes byte
    keys/values.

    Kills: key=None / hgetall(None) mutants and the disabled isinstance-decode.
    """
    mock_redis_client.hgetall.return_value = {
        b"status": b"connected",
        b"retry_count": b"0",
    }
    manager = StreamManager(redis_client=mock_redis_client)
    await manager.start()

    health = await manager.get_stream_health("camera1")

    mock_redis_client.hgetall.assert_awaited_once_with(f"{REDIS_HEALTH_KEY_PREFIX}camera1")
    assert health == {"status": "connected", "retry_count": "0"}

    await manager.stop()
```

## Covering-test references

- `backend/tests/unit/services/test_stream_manager.py` — the only test file exercising this module. Key weak spots by line: :320 (key as substring of repr, mapping never parsed), :351 (no task-cancellation assert), :402 (no delete-key assert), :486 (call_count only, fps never parsed), :585 (only first backoff delay), :637 (conditional `if camera1 in _streams` assert), :300 (VideoCapture.assert_called with no arg matchers; only test reaching `_create_capture_sync`), :676/:699/:724 (running=True liveness only).
- Drafts are UNVERIFIED — not yet run red/green (mutation run owns the machine; no pytest executed here per harness constraints).
