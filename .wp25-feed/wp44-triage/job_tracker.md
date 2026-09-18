# WP4.4 Triage Dossier — backend/services/job_tracker.py

- **Survivors:** 109 of 742 checked mutants (`mutants/backend/services/job_tracker.py.meta`, exit_code 0).
- **Verdict/diff sourcing:** `uv run mutmut show` spot-checked (init #2/#10/#11/#12, cleanup #5) and cross-verified against span-based manual diffing of `mutants/backend/services/job_tracker.py` vs `backend/services/job_tracker.py` (all 109 diffs generated; manual == cache on every spot-check).
- **Covering test file (all functions):** `backend/tests/unit/services/test_job_tracker.py` —
  - `get_job_from_redis` → `TestJobTrackerRedisIntegration` (L621-782); the reconstruction round-trip is `test_get_job_from_redis_fallback` **L702-726** and it asserts only 3 of 10 fields (`job_id`, `job_type`, `status`, L723-726) on a **fully populated** payload.
  - `cleanup_completed_jobs` → `TestJobTrackerCleanup` **L357-387** (asserts return count + `get_job()` presence only; never touches `_last_broadcast_progress`).
  - `set_redis_client` → `test_set_redis_client` **L629-634** (identity assert; survives all 4 survivors trivially).
  - `create_websocket_broadcast_callback` → `TestJobTrackerWebSocketIntegration.test_create_websocket_broadcast_callback` **L1067-1083** (`assert_called_once()` — asserts _that_ the broadcaster was called, never _with what_).
  - `init_job_tracker_websocket` → `test_init_job_tracker_websocket` **L1086-1099** (singleton always fresh → the not-None guard clause is never False in the suite) and `test_init_job_tracker_websocket_already_configured` **L1102-1117** (covers the _callback_ no-overwrite contract; the _redis_ mirror of that contract was never written).
- No test in the file uses `caplog` — no log payload is asserted anywhere (confirmed by grep).

Source under test: `backend/services/job_tracker.py` — `set_redis_client` L152-162, `get_job_from_redis` L246-289 (guard L269, JobInfo reconstruction L271-282, warning L283-287), `cleanup_completed_jobs` L574-594 (pop L589, log L591-592), `create_websocket_broadcast_callback` L862-891 (send L885, debug log L886-889), `init_job_tracker_websocket` L894-918 (L906, L909, L912, L915).

## Cluster table (counts sum to 109)

| ID  | Pattern (function / mutation kind)                                                                                                                                                                                                                                                                        |   n | Class        | Example keys (≤3)                                              | Notes                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| --- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --: | ------------ | -------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| C1  | `get_job_from_redis` JobInfo reconstruction (L271-282): field `.get()` key renames (`"progress"`→`"PROGRESS"`/`None`), default removal (`data.get("job_id")`), default changes (`"unknown"`→None, `0`→None/1, `""`→None/`"XXXX"`, `"pending"`→None/`"PENDING"`), field-kwarg drops, field-value `:= None` |  56 | **TEST-GAP** | `...get_job_from_redis__mutmut_52`, `_mutmut_56`, `_mutmut_45` | `test_get_job_from_redis_fallback` (L702) feeds a _complete_ payload and asserts only `job_id`/`job_type`/`status`; the other 7 fields flow through unasserted, and no test ever feeds a _sparse_ payload (missing keys → wrong default or `JobStatus(...)` ValueError). Killed by drafted tests **D1+D2** (both needed: D1 catches key renames on full payloads, D2 catches default changes). Residual after both: `_mutmut_29/_33/_34` (stored `job_id` renamed) only differ when a stored record's id ≠ its lookup key — corrupt-data territory, accept as equivalent. `_mutmut_51` (`"PENDING"`): StrEnum `auto()` values are lowercase, so mutant raises → killed by D2's status assert. |
| C2  | `get_job_from_redis` guard L269 `data is not None and isinstance(data, dict)` → `or`                                                                                                                                                                                                                      |   1 | EQUIVALENT   | `_mutmut_7`                                                    | With a non-dict, non-None payload the mutant raises `AttributeError` inside the `try`, which the broad `except Exception` (L283) swallows → falls to `return None` — same observable outcome as the original for every input.                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| C3  | `get_job_from_redis` warning-log (L283-287) message text / `extra` key & value mutations                                                                                                                                                                                                                  |  11 | EQUIVALENT   | `_mutmut_81`, `_mutmut_82`, `_mutmut_92`                       | Pure log text/`extra` payload; exception-swallowing behavior itself is asserted (`test_get_job_from_redis_handles_exception` L748). No log contract exists anywhere in the suite (no `caplog`).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| C4  | `cleanup_completed_jobs` L589 `self._last_broadcast_progress.pop(job_id, None)` → `pop(None, None)`                                                                                                                                                                                                       |   1 | **TEST-GAP** | `...cleanup_completed_jobs__mutmut_5`                          | Mutant silently stops clearing the per-job throttle bookkeeping: every cleanup leaks one dict entry forever, and a _reused_ job_id resurrects stale last-broadcast progress. No test reads `_last_broadcast_progress`. Killed by **D5**.                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| C5  | `cleanup_completed_jobs` L589 `pop(job_id, None)` → `pop(job_id)` (default dropped)                                                                                                                                                                                                                       |   1 | EQUIVALENT   | `...cleanup_completed_jobs__mutmut_7`                          | `_jobs` entries are only ever created by `create_job`, which always initializes `_last_broadcast_progress[job_id]` — the default is unreachable dead defense; no KeyError is possible.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| C6  | `cleanup_completed_jobs` info-log (L591-592) text / `extra` mutations                                                                                                                                                                                                                                     |   8 | EQUIVALENT   | `_mutmut_8`, `_mutmut_9`, `_mutmut_11`                         | Log text only; removal count is asserted via return value in existing tests.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| C7  | `create_websocket_broadcast_callback` L885 `broadcaster._send_to_local_clients(data)` → `(None)`                                                                                                                                                                                                          |   1 | **TEST-GAP** | `x_create_websocket_broadcast_callback__mutmut_2`              | Every WebSocket client would receive `None` instead of the job event — a real production break. The covering test (L1083) asserts `assert_called_once()` but never the argument. Killed by **D3** (one-line assertion strengthening).                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| C8  | `create_websocket_broadcast_callback` debug-log (L886-889) text / `extra` key/default mutations                                                                                                                                                                                                           |  18 | EQUIVALENT   | `_mutmut_3`, `_mutmut_10`, `_mutmut_16`                        | Pure `logger.debug` text and `extra` payload. (Note: `_mutmut_16`/`_18` make `data.get("data", None)` — but only feed the log line, and would `AttributeError` inside `logger` extras… no: evaluated at call site. `data.get("data", None).get(...)` on a payload _without_ `"data"` → AttributeError → broadcast callback raises → in production the caller `_broadcast` swallows it. Only observable when log-extra evaluation crashes on payloads lacking `"data"`, which never occurs — every caller passes `{"type":..., "data":...}`. Kept EQUIVALENT.)                                                                                                                                 |
| C9  | `init_job_tracker_websocket` L906 `get_job_tracker(redis_client=redis_client)` → `(redis_client=None)` **and** L915 guard `redis_client is not None and tracker._redis_client is None` → `... and tracker._redis_client is None` (first-clause flip to `is None`)                                         |   2 | **TEST-GAP** | `x_init_job_tracker_websocket__mutmut_2`, `_mutmut_11`         | Both encode the same startup-ordering bug: if the singleton already exists **without** redis (e.g. some code called `get_job_tracker()` first), `init_job_tracker_websocket(redis)` silently drops the passed client. Never exercised — the existing init test starts from a fresh singleton, where `redis_client is not None` short-circuits indistinguishably. Killed by **D4a**.                                                                                                                                                                                                                                                                                                           |
| C10 | `init_job_tracker_websocket` L915 guard `... and tracker._redis_client is None` → `or ...` / → `... is not None` (second-clause flips)                                                                                                                                                                    |   2 | **TEST-GAP** | `_mutmut_10`, `_mutmut_12`                                     | Mutants make init _unconditionally_ replace an already-configured Redis client — the clobber contract its docstring states ("if provided and not already set"). The suite has the exact mirror test for callbacks (`test_init_job_tracker_websocket_already_configured` L1102); the redis half was never written. Killed by **D4b**. (Confirmed SURVIVED in cache: the fresh-singleton path makes both clauses equivalent there.)                                                                                                                                                                                                                                                             |
| C11 | `init_job_tracker_websocket` info-log (L912) text mutations                                                                                                                                                                                                                                               |   4 | EQUIVALENT   | `_mutmut_6`, `_mutmut_7`, `_mutmut_8`                          | Log text only.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| C12 | `set_redis_client` info-log (L162) text mutations                                                                                                                                                                                                                                                         |   4 | EQUIVALENT   | `x.JobTracker.set_redis_client__mutmut_2`, `_3`, `_4`          | Log text only; the setter's real behavior (identity assignment) is asserted at L634.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |

**Totals:** TEST-GAP = 56+1+1+2+2 = **62** · EQUIVALENT = 1+11+1+8+18+4+4 = **47** · LOW-VALUE = 0 · **Σ = 109**.

## Drafted tests (UNVERIFIED — not yet run red/green)

TDD procedure, one line: run each new test against the mutant source copy (must FAIL on the one-line diff above) and against `backend/services/job_tracker.py` original (must PASS) before it joins the baseline.

All five drop into the existing file `backend/tests/unit/services/test_job_tracker.py` (no new imports needed — `JobTracker`, `JobStatus`, `create_websocket_broadcast_callback`, `init_job_tracker_websocket`, `get_job_tracker`, `AsyncMock`, `patch`, `pytest` are already imported there; the `cleanup_singleton` autouse fixture at L35 already resets the singleton).

### D1 — full-payload round-trip through Redis reconstruction → kills C1 (key renames, drops, value:=None)

Add as a method of `class TestJobTrackerRedisIntegration` (uses its `mock_redis_client` fixture, L624):

```python
    @pytest.mark.asyncio
    async def test_get_job_from_redis_round_trips_every_field(self, mock_redis_client: AsyncMock) -> None:
        """Should reconstruct every JobInfo field from a stored payload."""
        tracker = JobTracker(redis_client=mock_redis_client)
        mock_redis_client.get.return_value = {
            "job_id": "full-1",
            "job_type": "export",
            "status": "completed",
            "progress": 55,
            "message": "Halfway",
            "created_at": "2024-01-01T00:00:00",
            "started_at": "2024-01-01T00:00:01",
            "completed_at": "2024-01-01T00:00:10",
            "result": {"count": 5},
            # Non-None on purpose: the error field mutants
            # (_mutmut_78/79/80) are invisible when the fixture's
            # error is None, since every mutated lookup also yields None.
            "error": "transient-warning",
        }

        job = await tracker.get_job_from_redis("full-1")

        assert job is not None
        assert job["job_id"] == "full-1"
        assert job["job_type"] == "export"
        assert job["status"] == JobStatus.COMPLETED
        assert job["progress"] == 55
        assert job["message"] == "Halfway"
        assert job["created_at"] == "2024-01-01T00:00:00"
        assert job["started_at"] == "2024-01-01T00:00:01"
        assert job["completed_at"] == "2024-01-01T00:00:10"
        assert job["result"] == {"count": 5}
        assert job["error"] == "transient-warning"
```

// UNVERIFIED - not yet run red/green. Red drivers: any `data.get("progress"|"message"|"created_at"|"started_at"|"completed_at"|"result"|"error", ...)` key rename, the `_mutmut_12..18` `:= None` drops, and the `_mutmut_22..28` kwarg drops (KeyError on the missing field) all diverge here; green on the original line-by-line at job_tracker.py L271-282.

### D2 — sparse-payload defaults → kills C1's default-change members (with D1)

Same class:

```python
    @pytest.mark.asyncio
    async def test_get_job_from_redis_applies_documented_defaults_for_sparse_payload(
        self, mock_redis_client: AsyncMock
    ) -> None:
        """Should apply per-field defaults when a stored payload omits keys."""
        tracker = JobTracker(redis_client=mock_redis_client)
        # Only job_type present: every other key must fall back per L271-282.
        mock_redis_client.get.return_value = {"job_type": "export"}

        job = await tracker.get_job_from_redis("sparse-1")

        assert job is not None  # _mutmut_45/47/50/51: JobStatus(None/"PENDING") raises -> None
        assert job["job_id"] == "sparse-1"  # lookup-key fallback (L272)
        assert job["job_type"] == "export"
        assert job["status"] == JobStatus.PENDING  # default "pending" (L274)
        assert job["progress"] == 0  # default 0, not None/1 (L275)
        assert job["message"] is None
        assert job["created_at"] == ""  # default "", not None/"XXXX" (L277)
        assert job["started_at"] is None
        assert job["completed_at"] is None
        assert job["result"] is None
        assert job["error"] is None
```

// UNVERIFIED - not yet run red/green. Kills `_mutmut_30/32` (job_id default→None), `_36/38/41/42` (job_type default None/"XXunknownXX"/"UNKNOWN"), `_45/47/50/51` (status default None/"XXpendingXX"/"PENDING" → ValueError path), `_53/55/58` (progress default None/missing/1), `_63/65/68` (created_at default None/missing/"XXXX"). Together D1+D2 leave only `_29/_33/_34` (equivalent-on-sane-data residual, see C1 note).

### D3 — broadcaster payload assertion → kills C7

Replace the final line of `test_create_websocket_broadcast_callback` (L1083) — kept here as a standalone new test so the baseline diff is additive:

```python
    @pytest.mark.asyncio
    async def test_create_websocket_broadcast_callback_forwards_payload(self) -> None:
        """Should forward the full event payload to local WebSocket clients."""
        with patch(
            "backend.services.system_broadcaster.get_system_broadcaster", autospec=True
        ) as mock_get_broadcaster:
            mock_broadcaster = AsyncMock()
            mock_get_broadcaster.return_value = mock_broadcaster

            callback = create_websocket_broadcast_callback()
            payload = {"type": "job_completed", "data": {"job_id": "test-123"}}
            await callback("job_completed", payload)

            mock_broadcaster._send_to_local_clients.assert_called_once_with(payload)
```

// UNVERIFIED - not yet run red/green. Red on `_mutmut_2` (`_send_to_local_clients(None)`); green on L885 as written.

### D4a — init wires redis into an existing redis-less singleton → kills C9

Add to `class TestJobTrackerWebSocketIntegration`:

```python
    @pytest.mark.asyncio
    async def test_init_job_tracker_websocket_wires_redis_into_existing_singleton(self) -> None:
        """Should configure Redis on a singleton that was created without one."""
        pre_existing = get_job_tracker()  # singleton created without redis
        assert pre_existing._redis_client is None
        mock_redis = AsyncMock()

        with patch(
            "backend.services.system_broadcaster.get_system_broadcaster", autospec=True
        ) as mock_get_broadcaster:
            mock_get_broadcaster.return_value = AsyncMock()

            tracker = await init_job_tracker_websocket(redis_client=mock_redis)

        assert tracker is pre_existing
        assert tracker._redis_client is mock_redis
```

// UNVERIFIED - not yet run red/green. Red on `_mutmut_2` (redis dropped at L906) and `_mutmut_11` (guard first clause `redis_client is None` false → never set); green on original L906+L915.

### D4b — init never clobbers an already-configured redis client → kills C10

Same class:

```python
    @pytest.mark.asyncio
    async def test_init_job_tracker_websocket_keeps_existing_redis_client(self) -> None:
        """Should not override an already-configured Redis client."""
        existing_redis = AsyncMock()
        get_job_tracker(redis_client=existing_redis)
        new_redis = AsyncMock()

        with patch(
            "backend.services.system_broadcaster.get_system_broadcaster", autospec=True
        ) as mock_get_broadcaster:
            mock_get_broadcaster.return_value = AsyncMock()

            result = await init_job_tracker_websocket(redis_client=new_redis)

        assert result._redis_client is existing_redis
```

// UNVERIFIED - not yet run red/green. Red on `_mutmut_10` (`or` → calls `set_redis_client(None)` on the else branch) and `_mutmut_12` (guard becomes "set iff already set" → replaces with `new_redis`); green on original L915. Mirrors `test_init_job_tracker_websocket_already_configured` (L1102) for redis.

### D5 — cleanup clears throttle bookkeeping → kills C4

Add to `class TestJobTrackerCleanup`:

```python
    def test_cleanup_clears_broadcast_progress_tracking(self, job_tracker: JobTracker) -> None:
        """Should drop last-broadcast progress entries for removed jobs."""
        job1 = job_tracker.create_job("export")
        job2 = job_tracker.create_job("export")  # stays active
        job_tracker.update_progress(job1, 30)
        job_tracker.update_progress(job2, 40)
        job_tracker.complete_job(job1)

        removed = job_tracker.cleanup_completed_jobs()

        assert removed == 1
        # Throttle bookkeeping for the removed job must not leak, and the
        # still-active job's entry must survive untouched.
        assert job1 not in job_tracker._last_broadcast_progress
        assert job_tracker._last_broadcast_progress[job2] == 40
```

// UNVERIFIED - not yet run red/green. Red on `_mutmut_5` (`pop(None, None)` → `job1` key leaks → first assert fails); green on L589.

## Residual after drafting

- **EQUIVALENT, no action (47):** C2, C3, C5, C6, C8, C11, C12 — log text/`extra` payloads, unreachable dead defaults, and one guard whose mutated path the surrounding `except Exception` already swallowed. Recommend marking killed-equivalents out of the score target with mutmut config / baseline notes rather than writing log-assertion tests (asserting `logger` record text is an anti-pattern this suite deliberately avoids — zero `caplog` usage in this file).
- **TEST-GAP residual inside C1 (3 keys):** `_mutmut_29/_33/_34` — stored-record `job_id` key mutations, only observable for payloads whose stored id contradicts their lookup key. Accept as equivalent-corruption.
- If the finding feed wants a per-cluster kill-rate line: D1+D2 kill 53/56 of C1, D3 1/1 C7, D4a 2/2 C9, D4b 2/2 C10, D5 1/1 C4 → 59/62 of the TEST-GAP mass, with the remaining 3 argued above.
