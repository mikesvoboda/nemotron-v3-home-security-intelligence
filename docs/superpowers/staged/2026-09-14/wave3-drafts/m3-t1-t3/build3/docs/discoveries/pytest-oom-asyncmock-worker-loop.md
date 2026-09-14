# Discovery: pytest OOM — AsyncMock call accumulation in pipeline worker loops

**Issue:** none filed (diagnosed ad hoc after repeated sandbox OOM kills)
**Date:** 2026-09-13
**Diagnosed in:** `sbx` sandbox `agent-nemo2` (62.7 GiB RAM, 16 CPU, **no swap**)

## Summary

Any test whose fixture starts the full FastAPI app via `TestClient(app)` with `AsyncMock`-patched
lifespan dependencies leaks roughly **300 MB/s** and hangs. The app's lifespan starts pipeline
worker loops; those loops call `AsyncMock`s in a tight `continue` path with no sleep, and
`unittest.mock` permanently records **every** call. Measured growth: **0.43 GiB → 17.42 GiB in
60 seconds**, thread count flat at 7.

This is the cause of the repeated OOM kills in the sandbox (64 total, 60 of them on 2026-09-13),
with `pytest` and `[pytest-xdist runner]` processes reaped at 20–60 GiB each.

## Root cause

Call chain, captured from a live `faulthandler` + `tracemalloc` dump of the hung process:

```
backend/core/async_context.py:349          return await coro
backend/services/pipeline_workers.py:410   messages = await stream_service.consume_detections(...)
backend/services/redis_streams.py:382      for _stream_name, stream_messages in result:
unittest/mock.py:1175                      self._increment_mock_call(*args, **kwargs)
unittest/mock.py:1220                      this_mock_call = _Call((mock_call_name, args, kwargs))
unittest/mock.py:2613                      self._mock_name = name
```

Step by step:

1. The fixture patches lifespan deps with `AsyncMock` (`_get_common_lifespan_mocks()`,
   `test_websocket_auth_flow.py:35`) and then starts the whole app —
   `client = stack.enter_context(TestClient(app))` (`:149`, `:280`, `:514`, …).
2. App startup launches `DetectionQueueWorker._run_loop`
   (`backend/services/pipeline_workers.py:363`), a `while self._running:` loop at `:909`-style
   structure, first instance at `:412`.
3. `pipeline_workers.py:410` calls `stream_service.consume_detections(...)` — now an `AsyncMock`.
4. In `redis_streams.py:377` (`if not result:`) and `:382` (`for _stream_name, ... in result:`),
   `result` is a Mock. Mock truthiness is `True` and iteration yields **another Mock**, never an
   empty list.
5. Back in the loop, `pipeline_workers.py:413-414`:

   ```python
   if not messages:
       continue        # <-- no sleep, no yield: spins as fast as the event loop allows
   ```

   The 1-second backoff at `pipeline_workers.py:446` lives only in the `except` branch, which is
   **never reached** — a mock does not raise.
6. `unittest.mock` records every call forever in `mock_calls` / `call_args_list`. Each iteration
   allocates a `_Call` tuple that is never released. This is by design: call recording is what
   makes `assert_called_with` work.

**Mocks are unsafe in any unbounded loop.** That is the generalizable lesson here.

## Why it also hangs

The hang is in the **fixture**, not the test body. Thread dump of the main thread:

```
starlette/testclient.py:688 in __enter__      <- waiting on app lifespan startup
anyio/from_thread.py:326 in call
test_websocket_auth_flow.py:514 in detections_auth_client
```

`TestClient.__enter__` waits for startup that never settles, so the test never reaches its
WebSocket assertions. The body of the test is irrelevant — **any** test using these fixtures is
affected.

Compounding factor: the configured timeout never fires. `pyproject.toml` sets `timeout = 5`, but
an affected test was observed running **2m28s**. With `timeout_method = "thread"` +
`timeout_func_only = true` under xdist, hung tests are not being reaped. A working timeout would
cap the damage at ~1.5 GiB instead of 17 GiB.

## Blast radius

Worker classes containing the same `_run_loop` pattern (`backend/services/pipeline_workers.py`):

| Class | `class` line | `_run_loop` line |
|---|---|---|
| `DetectionQueueWorker` | 221 | 363 |
| `AnalysisQueueWorker` | 764 | 885 |
| `BatchTimeoutWorker` | 1186 | 1286 |
| `QueueMetricsWorker` | 1366 | 1451 |

`AnalysisQueueWorker._run_loop` has the identical unthrottled shape at `:935-936`
(`if not messages: continue`) with its backoff isolated at `:967`.

Test files using the `TestClient(app)` + lifespan-mock pattern:

- `backend/tests/integration/test_websocket_auth_flow.py` (6 `TestClient(app)` sites)
- `backend/tests/integration/test_websocket_auth.py`
- `backend/tests/integration/test_websocket.py`

With `addopts = "-n 8 --dist=worksteal"`, several workers can land on affected tests
simultaneously and exhaust the 62.7 GiB VM.

## Ruled out — do not re-investigate

These were each checked and measured; none is the cause:

| Hypothesis | Verdict |
|---|---|
| `backend/tests/load/` perf tests | Measured **0.86 GiB** peak — innocent |
| Model loading into CPU RAM | `torch` not installed in sandbox; no `/dev/nvidia*` |
| Thread leak | Thread count **flat at 7** while RSS went 0.43 → 17.42 GiB |
| Large allocations in tests | Largest found: 100×100×3 images, 512-float arrays |
| Network policy blocking the model endpoint | 1103 `net:cidr:192.168.1.186` denials are logged but **not enforced**; `curl` from inside the sandbox returns HTTP 200 |
| Host resource exhaustion | Host had 352 GiB RAM free, load ~2.9, `sbx diagnose` 12/12 pass |

Note the frame-buffer "memory limit" tests in `backend/tests/load/test_performance.py` provide
**no protection**: they assert `estimated_memory = frame_count * frame_size < 500MB`, which is
arithmetic on two constants and passes regardless of real process memory.

## Reproduction

```bash
# inside the sandbox workspace
.venv/bin/python -m pytest \
  "backend/tests/integration/test_websocket_auth_flow.py::TestWebSocketDetectionsAuthFlow::test_websocket_detections_with_cookie_auth" \
  -n 0 -q --timeout=0

# in another shell, watch it climb ~300 MB/s and never finish:
watch -n2 'ps -eo pid,rss,etime,args | grep pytest | grep -v grep'
```

Confirmed measurement (watchdog sampling RSS and `threading.active_count()`):

```
   t(s)  RSS(GiB)  threads
    3.0      0.43        3
   15.2      3.50        7
   30.7      8.29        7
   45.3     11.44        7
   60.5     17.42        7
```

## Recommended fixes

1. **Do not start pipeline workers under `TestClient`** (root cause). Gate worker startup in the
   lifespan, or patch it in `_apply_common_lifespan_patches`
   (`test_websocket_auth_flow.py:77`):

   ```python
   stack.enter_context(patch(
       "backend.services.pipeline_workers.DetectionQueueWorker.start", AsyncMock()
   ))
   ```

2. **Close the unthrottled path** in every `_run_loop` — latent hazard beyond tests:

   ```python
   if not messages:
       await asyncio.sleep(0)   # always yield; consider a short poll delay
       continue
   ```

   Apply at `pipeline_workers.py:413` and `:935`, and audit `BatchTimeoutWorker` /
   `QueueMetricsWorker` for the same shape.

3. **If a mock must back a loop**, make it terminate the fast path and bound its memory:
   `AsyncMock(return_value=[])` so `if not messages:` is genuinely true, plus periodic
   `mock.reset_mock()`.

4. **Make the 5s timeout actually fire.** Drop `timeout_func_only = true` or switch to
   `timeout_method = "signal"`, then verify with a deliberately hanging test.

5. **Give the sandbox headroom.** Memory is fixed at create time:
   `sbx create --name <n> -m 256g --cpus 16 claude <workspace>`. Host has 494 GiB; the VM had
   62.7 GiB and **no swap**, so the OOM killer fires with no reclaim runway.

6. **Make the memory tests real** — assert on `resource.getrusage(...).ru_maxrss`, not on a
   recomputation of the inputs.

## Confidence and open gap

The call path is confirmed directly from the process's own stack and a `tracemalloc`
snapshot diff (`compare_to` against a post-startup baseline), and the leak reproduces on demand.

One honest gap: `tracemalloc` accounted for only ~125 MiB of the 1.2 GiB RSS growth observed in
the instrumented run — `unittest.mock` sites dominated the *tracked* growth (5 separate
`mock.py` sites, ~290k blocks in 35s), and the mock path is the only application-code path that
appears in the growth list, but the absolute byte attribution is incomplete. `tracemalloc` also
slows the loop roughly 10–15×, so instrumented numbers understate real-world growth rate.
