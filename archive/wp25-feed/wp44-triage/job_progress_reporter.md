# WP4.4 Triage Dossier — backend/services/job_progress_reporter.py

**Wave**: gen-2 (WP4.3 surviving-mutant feed)
**Date**: 2026-09-18
**Status**: UNVERIFIED (read-only triage; no tests executed, per live-mutation-run constraint)

## Provenance

- Verdict source: `mutants/backend/services/job_progress_reporter.py.meta` — 206 keys, **50 survived** (exit 0), 156 killed, 0 unchecked.
- Diffs: extracted from `mutants/backend/services/job_progress_reporter.py` clobber-variant defs (`xǁ<Fn>ǁ__mutmut_N`), diffed against each `__mutmut_orig` twin (same-file AST-equivalent baseline). All 50 diffs recovered; each diff was additionally located **before/after the `emitter = await self._get_emitter()` line** to separate logger-only mutations from WebSocket-payload mutations — this is the load-bearing distinction for classification.
- Covering tests (from `mutants/mutmut-stats.json` → `tests_by_mangled_function_name`):
  - `backend/tests/unit/services/test_job_progress_reporter.py` (NEM-2743 file; fixture `job_type="test_job"`, `total_items=100`)
  - `backend/tests/unit/test_job_progress_reporter.py` (older suite, freezegun-based; fixture `job_type="export"`, `total_items=100`)
  - Both files mock the emitter (`emitter.emit = AsyncMock()`) and assert payload keys `job_id`, `progress`, `status`, `message`, `error`, `retryable`, `error_code`, `result`, `duration_seconds` — **but never `job_type` in the JOB_PROGRESS payload, never exact-throttle timing, never non-integer percentage truncation, and never any logging output.**

## Classification method

A mutation is **log-only** if its first differing line sits inside the `logger.info/debug(...)` call (message arg, `extra={...}` dict, `extra=None`, key string in that dict) — the logger output is never asserted by either test file (no `caplog`, no log capture anywhere in either suite) and no consumer reads `record["extra"]`. A mutation is **payload/behavioral** if it lands in the dict passed to `emitter.emit(...)`, the throttle condition, the percent formula, or init sentinels that feed them.

## Cluster table (counts sum to 50)

| # | Pattern | Count | Class | Example keys (suffix) | Covering test → miss |
|---|---------|-------|-------|----------------------|----------------------|
| 1 | logger message arg → `None` in all 4 lifecycle methods (`f"Job started: ..."` → `None`) | 4 | EQUIVALENT | `start__7`, `complete__9`, `fail__13` | No test captures log records (both suites mock only the emitter) → log text never asserted |
| 2 | `extra={...}` → `extra=None` on logger call | 4 | EQUIVALENT | `start__8`, `complete__10`, `fail__14` | same — log `extra` unasserted |
| 3 | `extra={...},\n )` folded to `,)` (extra dropped, trailing comma valid Python) | 4 | EQUIVALENT | `start__10`, `complete__12`, `report_progress__34` | same |
| 4 | Key-string rename (`"job_id"→"XXjob_idXX"/"JOB_ID"` etc.) inside logger `extra` dict — start×6, complete×6, fail×6, report_progress×10 | 28 | EQUIVALENT | `start__11`, `complete__13`, `report_progress__44` | same — pure log-structure text |
| 5 | **`"job_type"` key renamed inside the `JOB_PROGRESS` `emitter.emit` payload dict** (`XXjob_typeXX`/`JOB_TYPE`) | 2 | **TEST-GAP** | `report_progress__52`, `report_progress__53` | `services/…:397 test_report_progress_emits_event` asserts `job_id`/`progress`/`status`/`message` but omits `job_type`; unit-root `…:227` likewise |
| 6 | Percent formula `* 100` → `* 101` (`int((items/total)*101)`) | 1 | **TEST-GAP** | `report_progress__14` | every % assertion uses exact/round values (`progress==50`, `==100`, `==100` cap) — no test exercises fractional truncation; `unit-root:290` throttle test runs at delta≥10 anyway |
| 7 | Throttle boundary `time_since_last >= PROGRESS_THROTTLE_INTERVAL` → `>` | 1 | **TEST-GAP** | `report_progress__24` | `unit-root:290 test_report_progress_emits_after_throttle_interval` offsets by `INTERVAL + 0.1` (strictly-past boundary); `services:421` sleeps `+0.01` — no exact-boundary case |
| 8 | Init sentinel `_last_progress_time = 0.0` → `None` / `1.0` — dead value: `start()` always overwrites before first read; guard raises if `report_progress` skips start | 2 | EQUIVALENT | `__init___12`, `__init___13` | unreachable-at-read (dead defensive tweak per EQUIVALENT definition) |
| 9 | Init sentinel `_last_progress_percent = -1` → `-2` — shifts first-emit delta threshold from ≥9% to ≥8% of progress (only reachable path: first `report_progress(<9%)` within 1 s of `start()`, no force) | 1 | **TEST-GAP** | `__init___16` | `services:487 test_report_progress_9_percent_jump_throttled` establishes baseline at 10% first, so the `-1` sentinel itself is never probed at the boundary |
| 10 | `create_job_progress_reporter` passes `None` instead of `job_id` to `JobProgressReporter.create` | 1 | **TEST-GAP** | `x_create_job_progress_reporter__1` | `services:168 test_create_convenience_function` asserts only `isinstance` + `job_type`; `unit-root:146` asserts only `job_type`+`total_items` — nobody asserts `reporter.job_id` |
| 11 | `datetime.now(UTC)` → `datetime.now(None)` for `completed_at` / `failed_at` (naive local time emitted in payload) | 2 | LOW-VALUE | `complete__7`, `fail__8` | `unit-root:365`/`…:423` assert only `"completed_at" in payload` existence; naive-vs-aware is a real payload change but timestamp tz of these event fields is not a behavior worth pinning for a 30-day local single-user deployment |

**Totals**: 50 = EQUIVALENT 42 + TEST-GAP 6 + LOW-VALUE 2. TEST-GAP clusters: 5 (#5,6,7,9,10) → 5 drafted tests below.

Sum-check: 4+4+4+28+2+1+1+2+1+1+2 = **50** ✓ (equals meta survivor count 50)

## Drafted tests

All five target `backend/tests/unit/services/test_job_progress_reporter.py` (fixture: `reporter` = job_type `"test_job"`, total_items 100, `mock_emitter`; already imports `AsyncMock, MagicMock, patch`, `uuid4`, `pytest`; **needs one new module-level import: `import time`** for draft T3). TDD procedure for each: add test → run red against the mutant copy's variant (assert fails on mutant diff) → run green against `backend/services/job_progress_reporter.py` original.

### T1 — kills cluster 5 (emit-payload `job_type` key rename, `report_progress__52/53`)

```python
# UNVERIFIED - not yet run red/green
class TestProgressReporting:
    ...
    @pytest.mark.asyncio
    async def test_report_progress_payload_includes_job_type(self, reporter, mock_emitter):
        """Verify JOB_PROGRESS payload includes job_type (contract consumed by frontend).

        Given: A started reporter
        When: report_progress() emits
        Then: Payload carries the job_type key with the configured job type
        """
        await reporter.start()
        mock_emitter.emit.reset_mock()

        await reporter.report_progress(50)

        payload = mock_emitter.emit.call_args[0][1]
        assert payload["job_type"] == "test_job"
```

Red path: mutant renames key → `payload["job_type"]` raises KeyError (mutant also renames it to `XXjob_typeXX`/`JOB_TYPE`, so original key absent). Green on original.

### T2 — kills cluster 6 (percent scale `*101`, `report_progress__14`)

```python
# UNVERIFIED - not yet run red/green
    @pytest.mark.asyncio
    async def test_report_progress_truncates_fractional_percentage(self, mock_emitter):
        """Verify fractional progress truncates down (int semantics), not scales.

        Given: A reporter with total_items=200
        When: 195/200 items are processed (97.5%)
        Then: Progress payload reports 97 (truncated), not a re-scaled value
        """
        reporter = JobProgressReporter(
            job_id=str(uuid4()),
            job_type="export",
            total_items=200,
            emitter=mock_emitter,
        )
        await reporter.start()
        mock_emitter.emit.reset_mock()

        await reporter.report_progress(195, force=True)

        payload = mock_emitter.emit.call_args[0][1]
        assert payload["progress"] == 97
```

Red path: mutant computes `int(195/200 * 101) = int(98.475) = 98` ≠ 97. Original: `int(97.5…) = 97`. (Chosen values are the *only* cheap kill: any mutant-vs-orig divergence requires orig pct < 100 with frac headroom ≥ 1% under ×1.01 — 195/200 is minimal.)

### T3 — kills cluster 7 (throttle `>=` → `>`, `report_progress__24`)

```python
# UNVERIFIED - not yet run red/green
    @pytest.mark.asyncio
    async def test_report_progress_emits_at_exact_throttle_interval(self, reporter, mock_emitter):
        """Verify the throttle fires AT exactly 1.0s (>= boundary), not strictly after.

        Given: A started reporter whose last progress was exactly PROGRESS_THROTTLE_INTERVAL ago
        When: report_progress() runs with monotonic time frozen
        Then: The event is emitted (>= boundary), not throttled (> boundary)
        """
        await reporter.start()
        mock_emitter.emit.reset_mock()

        frozen = time.monotonic()
        with patch("backend.services.job_progress_reporter.time.monotonic", return_value=frozen):
            reporter._last_progress_time = frozen - PROGRESS_THROTTLE_INTERVAL
            emitted = await reporter.report_progress(5)

        assert emitted is True
        assert mock_emitter.emit.call_count == 1
```

Red path: mutant needs `time_since_last > 1.0`; frozen clock makes delta exactly `1.0` (float-exact: ulp(frozen) ≪ 1.0), delta-vs-sentinel is 6 < 10 → mutant throttles → `emitted` False. Original `>=` fires. (Requires adding `import time` to the module header. `patch` already imported.)

### T4 — kills cluster 9 (`_last_progress_percent` sentinel −1→−2, `__init___16`)

```python
# UNVERIFIED - not yet run red/green
    @pytest.mark.asyncio
    async def test_first_progress_at_8_percent_is_throttled(self, reporter, mock_emitter):
        """Verify the -1 progress sentinel makes the first-emit delta threshold 9%, not 8%.

        Given: A just-started reporter (no progress emitted yet, sentinel -1)
        When: First report_progress(8) runs well within the throttle window
        Then: It is throttled (delta = 8 - (-1) = 9 < 10)
        """
        await reporter.start()
        mock_emitter.emit.reset_mock()

        emitted = await reporter.report_progress(8)

        assert emitted is False
        assert mock_emitter.emit.call_count == 0
```

Red path: mutant sentinel −2 → delta = 10 → `>= 10` branch fires immediately (test runs within µs of start, time branch cold) → returns True. Original returns False.

### T5 — kills cluster 10 (convenience fn passes `None` job_id, `x_create_job_progress_reporter__1`)

```python
# UNVERIFIED - not yet run red/green
class TestJobProgressReporterInitialization:
    ...
    @pytest.mark.asyncio
    async def test_create_convenience_function_preserves_job_id(self, job_id):
        """Verify create_job_progress_reporter forwards the real job_id (not None).

        Given: A job_id
        When: create_job_progress_reporter() is called
        Then: The created reporter carries that job_id
        """
        mock_emitter = MagicMock()
        mock_emitter.emit = AsyncMock()

        with patch(
            "backend.services.websocket_emitter.get_websocket_emitter",
            return_value=mock_emitter,
            autospec=True,
        ):
            reporter = await create_job_progress_reporter(
                job_id=job_id,
                job_type="backup",
                total_items=50,
            )

            assert reporter.job_id == job_id
```

Red path: mutant passes `None` → `str(None) == "None"` ≠ fixture `str(uuid4())`. Green on original. (Cheaper alternative: append the single assert to existing `test_create_convenience_function` at `services/…:168` — drafted as a sibling to keep the diff reviewable.)

## Notes for the fix lane

- Cluster 4 (28 mutants) is the module's dominant survivor population; it is **not** worth log-record assertions (structlog capture) — the house verdict is EQUIVALENT pure-log-text, consistent with prior waves.
- Clusters 1–3 share the fix-lane answer with 4: no action.
- Drafts T1/T5 are one-line-assert additions to an existing test's scenario; T2/T3/T4 need the new tests as written (T3 requires `import time` added to the services test file header).
- Mutant keys are given as function-level suffixes; full key prefix is `backend.services.job_progress_reporter.xǁJobProgressReporterǁ<fn>__mutmut_<n>` (module fn: `x_create_job_progress_reporter__mutmut_1`).
