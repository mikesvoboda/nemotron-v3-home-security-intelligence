# WP4.4 Triage Dossier — backend/services/job_timeout_service.py

Generated 2026-09-17 from the live mutmut run (read-only triage: no tests executed, no repo files modified).

- **Module:** `backend/services/job_timeout_service.py` (518 lines)
- **Mutants generated:** 304 · **Surviving (exit_code 0):** **133** · null = not yet checked (ignored)
- **Verdict source:** `mutants/backend/services/job_timeout_service.py.meta`
- **Diff source:** `uv run mutmut show <key>` for all 133 survivors, zero failures. Raw dumps: `/tmp/wp25/wp44-triage/jts_diffs_raw.txt` (full diffs), `/tmp/wp25/wp44-triage/jts_clusters.json` (cluster → every key; partition machine-verified disjoint + complete against the meta file).
- **Covering tests:** `backend/tests/unit/services/test_job_timeout_service.py` — the **only** test file exercising this module's logic (`AsyncMock` fixtures `mock_redis`, `mock_job_status_service = AsyncMock(spec=JobStatusService)`). Singleton/init paths additionally touched by `backend/tests/unit/jobs/test_timeout_checker_job.py`.
- **Key structural fact:** the covering file **never asserts on logging** (zero `caplog` hits) and **never asserts Redis-call arguments** beyond a handful of `set`/`delete` key checks. `get_logger()` (backend/core/logging.py:1107–1131) returns a plain propagating `logging.getLogger`, so `caplog` works if tests adopt it. `freezegun>=1.5.0` is already a dev dep (pyproject.toml:121; usage style in `backend/tests/unit/test_job_progress_reporter.py`).

## Headline

**94 / 133 (71%) survivors are EQUIVALENT** — mutmut's string-case/`XX`-prefix mutants on log messages and log-`extra` dict keys (82 keys, C1–C3), redis-py-equivalent zrange bound clobbers (10, C4), a log-only isoformat flip (1, C5) and a dead-code-equivalent `continue→break` (1, C7). **2 are LOW-VALUE** (default-branch error-message arithmetic, C8). **37 are TEST-GAP** in 9 clusters: a 13-key "nulled-key" family (C6) — real Redis-key/contract mutations surviving purely because AsyncMocks return canned values for *any* arguments — an 8-key mutation of the *real* retry `metadata` payload dict (`XX`-cased key names + off-by-one `attempt`, C16, distinct from the *log-copy* mutants in C2), plus 16 keys of genuine logic gaps: log-record counter arithmetic (7), retry-metadata whole-drop (2), boundary `>=→>` (3), retry-budget boundary (1), naive-deadline tz guard (1), default-fallback condition (1), result-contract `job_type=None` (1).

Classification totals: **EQUIVALENT 94 · LOW-VALUE 2 · TEST-GAP 37** (sums to 133 exactly).

## Cluster table

Key prefix `backend.services.job_timeout_service.x` elided; `ǁ` = class/method separator; `#N` = `__mutmut_N` in that method. Source lines refer to `backend/services/job_timeout_service.py`.

| # | Pattern (function / concern) | n | Class | Example keys (≤3) | What a killing test needs |
|---|---|---|---|---|---|
| C1 | Log **message string** case-flipped / `XX`-prefixed across all 4 logging callsites — check_for_timeouts (:443, :468) #18,19,20,35,36,37; cleanup_timeout_data (:490) #11,12,13; handle_timeout (:358, :391, :403) #22,23,24,64,65,66,83,84,85; set_timeout_config (:203) #13,14,15 | 21 | EQUIVALENT | `check_for_timeouts__mutmut_18`, `handle_timeout__mutmut_22`, `set_timeout_config__mutmut_13` | caplog message-text asserts (see rec 2 caveat re: log-DB consumers) |
| C2 | Log **`extra` dict key names** case-flipped / `XX`-prefixed, same 4 logging callsites (only the logger `extra={...}` dicts — the real start_job payload mutants live in C16). `check_for_timeouts` #21,22,38,39,40,41; `cleanup` #14,15; `handle_timeout` #25–30,33,34,67–72,75,76,86–91,94,95; `set_timeout_config` #16–21,24,25 | 40 | EQUIVALENT | `set_timeout_config__mutmut_16`, `handle_timeout__mutmut_69`, `check_for_timeouts__mutmut_38` | caplog `extra` key-name asserts — *or* confirm a log consumer reads these keys (then becomes TEST-GAP; see rec 2) |
| C3 | Log **msg→None / extra→None / extra kwarg dropped** at the same logging callsites: `check_for_timeouts` #14,15,17,31,32,34; `cleanup` #7,8,10; `handle_timeout` #18,19,21,60,61,63,79,80,82; `set_timeout_config` #9,10,12. Logging a None msg raises inside the handler chain only if records are actually emitted/asserted; no test looks at records | 21 | EQUIVALENT | `cleanup_timeout_data__mutmut_7`, `handle_timeout__mutmut_19` | any caplog handler asserting these records exist with text |
| C4 | `check_for_timeouts` (:434–438) **zrangebyscore bounds clobbered**: `JOBS_ACTIVE_KEY`/`"-inf"`/`"+inf"` → None, arg removed, `XX`-padded, or case-flipped `"-INF"`/`"+INF"` (#3–12). redis-py casts scores case-insensitively (`-INF` == `-inf`) and no test inspects the zrange call args — production behavior unchanged under a real client | 10 | EQUIVALENT | `check_for_timeouts__mutmut_10`, `check_for_timeouts__mutmut_3` | `mock_redis.zrangebyscore.assert_called_once_with(JOBS_ACTIVE_KEY, "-inf", "+inf")` |
| C5 | `set_timeout_config` (:208) **log field** `deadline` value → `isoformat() if (config.deadline) and False else None` (#22) — alters only the debug record | 1 | EQUIVALENT | `set_timeout_config__mutmut_22` | caplog on a deadline-configured job |
| C6 | **Arguments nulled → wrong Redis key / contract breach, invisible under weak mocks** (real behavior change): `get_timeout_config(None)` handle_timeout #2, is_job_timed_out #7 (reads `job:None:timeout` → config silently lost → wrong max_attempts, wrong error msg, retry-config copy lost); `is_job_timed_out` #6 `config = None` after fetch (ignores any stored config); `get_attempt_count(None)` handle_timeout #7 + increment_attempt_count #4 (counter never actually increments in prod → retry loop); `get_job_status(None)` check_for_timeouts #24 (every job lookup → None → scan silently does nothing); `set_timeout_config(None, …)` handle_timeout #56 (retry config written to `job:None:timeout`); `get_default_timeout(None)` is_job_timed_out #29 (wrong default type lookup); singleton `JobTimeoutService(None)` `x_get_job_timeout_service__mutmut_3` (singleton built for a None client). AsyncMock(spec=…) does **not** enforce call signatures (that's autospec) and returns canned values for any args | 13 | TEST-GAP | `handle_timeout__mutmut_2`, `check_for_timeouts__mutmut_24`, `handle_timeout__mutmut_56` | key-aware fake (`side_effect = lambda key: store[key]`) + `assert_called_once_with` (rec 3, drafted T2 covers the start_job trio) |
| C7 | `check_for_timeouts` (:455) **`continue`→`break`** (#26) — the only test reaching the `job is None` branch (`test_check_for_timeouts_handles_missing_jobs`, both jobs None) has identical semantics under break; the loop ends right after either way | 1 | EQUIVALENT | `check_for_timeouts__mutmut_26` | one mixed scan `["gone-job","timed-out-job"]` → second job still handled |
| C8 | `handle_timeout` (:349–350) **default-branch timeout message** `default_timeout = None` (#11) / `get_default_timeout(None)` (#12) → error string becomes `"Job timed out after None seconds (default timeout)"`. Real string change, but the default-branch wording is diagnostic cosmetics nobody should pin; only the explicit-seconds variant is asserted today (:597) | 2 | LOW-VALUE | `handle_timeout__mutmut_11` | (optional) assert `"default timeout"` present when no config |
| C9 | **Log-record numeric attempt counters off-by-one**: warning `"Job timed out"` `attempt: current_attempts + 1 → ±Δ` (#31,32); reschedule-log `attempt: new_attempt + 1 → ±Δ` (#73,74); permanent-fail-log `attempts` (#92,93); **plus one real compute**: `check_for_timeouts` summary log `"rescheduled_count": sum(1 …) → sum(2 …)` (#43) — operations-facing metric doubles | 7 | TEST-GAP | `handle_timeout__mutmut_31`, `check_for_timeouts__mutmut_43` | caplog asserts on `extra["attempt"]` / `extra["attempts"]` / `extra["rescheduled_count"]` values (drafted T6) |
| C10 | `handle_timeout` (:377–385) **retry job metadata → None** (#44) **or dict dropped** (#47) in the real `start_job` call — retry job loses `retry_of`/`attempt`/`original_extra` lineage in prod; `test_handle_timeout_reschedules_with_retries_remaining` (:499) only asserts `start_job.assert_called()` | 2 | TEST-GAP | `handle_timeout__mutmut_44` | assert exact `start_job` kwargs incl. metadata (drafted T2) |
| C11 | `handle_timeout` (:413–420) **returned `TimeoutResult.job_type = None`** (#97 — return construction, *not* the start_job kwarg) — result contract field silently None for every caller of `check_for_timeouts`/`handle_timeout` | 1 | TEST-GAP | `handle_timeout__mutmut_97` | `assert result.job_type == "export"` after handle_timeout (drafted T2) |
| C12 | **Freshness boundary `>=`→`>`** on all three comparisons: duration (:303 #15), deadline (:312 #21), default-type timeout (:319 #33) — a job exactly at its deadline is no longer timed out (silent one-tick grace). Existing tests use minutes-sized margins | 3 | TEST-GAP | `is_job_timed_out__mutmut_15` | `freeze_time` at exactly `started_at + timeout` → still True (drafted T3, T4) |
| C13 | `is_job_timed_out` (:310) **naive-deadline tz guard inverted**: `if deadline.tzinfo is None:` → `is not None` (#20) — naive deadlines never get UTC (then `now >= naive` raises TypeError, swallowed by check_for_timeouts' broad except → job silently never times out); tz-aware deadlines in other zones get clobbered to UTC → early/late timeout. All existing deadline tests pass `tzinfo=UTC` | 1 | TEST-GAP | `is_job_timed_out__mutmut_20` | naive-past deadline must time out; foreign-tz deadline must not be mangled (drafted T4) |
| C14 | `is_job_timed_out` (:316) **default-timeout fallback condition** `ts is None and dl is None` → `ts is not None and dl is None` (#26). Divergence point: **timeout-seconds-only configs** — original: no fallback (explicit timeout honored); mutant: fallback engages for every ts-only config → an explicit long timeout (e.g. 10 000 s) gets clobbered by the job-type default (export 1800 s) → job killed early. `test_job_uses_default_timeout_when_no_config` only tests fallback *firing*, never *suppression* | 1 | TEST-GAP | `is_job_timed_out__mutmut_26` | ts=10 000 config, started 40 min ago, export type → False (drafted T5) |
| C15 | `handle_timeout` (:370) **retry-budget boundary** `current_attempts + 1 < max_attempts` → `+ 2 <` (#38) — max off-by-one: one fewer retry ever scheduled; at the boundary attempt (attempts = max−2) the job permanently fails instead of rescheduling. `…no_reschedule_at_max_attempts` (:529) sits at attempts=max−1 where both versions say False; `…uses_custom_max_attempts` (:560) at 0 vs max=1 likewise | 1 | TEST-GAP | `handle_timeout__mutmut_38` | attempts = max−2, default max=3 → must reschedule (drafted T1) |

| C16 | `handle_timeout` (:380–383) **real retry `metadata` payload dict mutated** — distinct from C2's log copies: key names `XX`-cased (`XXretry_ofXX` #48 / `RETRY_OF` #49, `XXattemptXX` #50 / `ATTEMPT` #51, `XXoriginal_extraXX` #54 / `ORIGINAL_EXTRA` #55) and value arithmetic `new_attempt + 1 → −1/+2` (#52,53). In prod the retry job is persisted to Redis with mangled metadata keys — anything reading `metadata["retry_of"]`/`["attempt"]` (retry lineage, attempt accounting) silently gets nothing/wrong data. Survives because the mock `start_job` swallows any payload | 8 | TEST-GAP | `handle_timeout__mutmut_48`, `handle_timeout__mutmut_52` | exact-metadata assert on the `start_job` call (drafted T2) |

**Sum check: 21+40+21+10+1+13+1+2+7+2+1+3+1+1+1+8 = 133 ✓**

## Covering test files (file:line)

- `backend/tests/unit/services/test_job_timeout_service.py` — **all clusters**. Classes/anchors: `TestJobTimeoutServiceSetGetConfig` :161 (set-key :165, ttl :177), `…AttemptCount` :224 (:250 increment, :262 ttl), `…IsJobTimedOut` :282 (:330 ts-timeout, :384 deadline-timeout, :411 not-before-deadline, :438 default-when-no-config), `…HandleTimeout` :464 (:468 fail-marked, :499 reschedules, :529 at-max, :560 custom-max, :597 msg-contains-seconds), `…CheckForTimeouts` :629 (:633 empty, :644 handles, :680 skips, :712 missing-jobs), `…Cleanup` :727, `…Singleton` :743.
- `backend/tests/unit/jobs/test_timeout_checker_job.py` — singleton/init touchpoints only (C6's `get_job_timeout_service__mutmut_3` context).

## What the covering tests miss (per TEST-GAP cluster)

- **C1–C3, C9:** zero `caplog` usage in the file — log calls *execute* on every test (mutmut sees coverage) but no record is ever read. C9's counter arithmetic is the one where a record value is a real ops metric.
- **C6:** mocks return canned values regardless of key; `assert_called()` without args. Only 6 sites in the whole file assert call args (`mock_redis.set.call_args`, delete-call keys). A null-key mutant reads/writes `job:None:timeout` and the mock happily answers.
- **C10/C16/C11:** `:499` asserts `was_rescheduled`, `attempt_count`, `start_job.assert_called()` — never the metadata *contents* (whole dict or any key inside it) nor `result.job_type`. T2's single `assert_called_once_with` kills all 11 of C10+C16+C11 plus the C6 start_job trio.
- **C12:** margins (10 min vs 300 s; deadline 1 h ago) never hit the exact-boundary instant.
- **C13:** deadlines always tz-aware UTC (`:403`, `:430`); naive/foreign-tz untested.
- **C14:** fallback *firing* is tested (`:438`, no config); fallback *suppression* by an explicit config is not.
- **C15:** both max-attempts tests land on sides where the mutant agrees; the last-permitted-retry side (attempts = max−2) is never constructed.

## Drafted tests (6) — ALL `// UNVERIFIED — not yet run red/green`

TDD procedure (one line): apply each mutant's diff to a scratch copy of `backend/services/job_timeout_service.py`, run the drafted test → it must fail; run against the original → it must pass; only then commit.

Append to `backend/tests/unit/services/test_job_timeout_service.py`. Imports to add: `from freezegun import freeze_time` and `from datetime import timezone` (T4). Reuses existing fixtures.

### T1 — kills C15 → add to `TestJobTimeoutServiceHandleTimeout`

```python
    @pytest.mark.asyncio
    async def test_handle_timeout_reschedules_on_last_permitted_attempt(
        self,
        job_timeout_service: JobTimeoutService,
        mock_job_status_service: AsyncMock,
        mock_redis: AsyncMock,
    ) -> None:
        """Attempt count of max-2 must still reschedule: (max-2) + 1 < max.

        // UNVERIFIED - not yet run red/green
        Kills handle_timeout__mutmut_38 (retry condition
        'current_attempts + 1 < max_attempts' -> '+ 2 <', which silently drops
        one retry at the boundary attempt).
        """
        mock_redis.get.return_value = {"count": DEFAULT_MAX_RETRY_ATTEMPTS - 2}

        started_at = datetime.now(UTC) - timedelta(minutes=10)
        job = JobMetadata(
            job_id="job-123",
            job_type="export",
            status=JobState.RUNNING,
            progress=50,
            message=None,
            created_at=started_at,
            started_at=started_at,
            completed_at=None,
            result=None,
            error=None,
        )

        result = await job_timeout_service.handle_timeout(job)

        assert result.was_rescheduled is True
        assert result.attempt_count == DEFAULT_MAX_RETRY_ATTEMPTS - 1
        mock_job_status_service.start_job.assert_called_once()
```

Red/green: on the `+ 2 <` mutant, `(max-2) + 2 < max` is False → no reschedule → first assert fails; original reschedules → passes.

### T2 — kills C10 + C11; collateral-kills C6 #43/#45/#46 → add to `TestJobTimeoutServiceHandleTimeout`

```python
    @pytest.mark.asyncio
    async def test_handle_timeout_retry_contract_exact_start_job_call_and_result(
        self,
        job_timeout_service: JobTimeoutService,
        mock_job_status_service: AsyncMock,
        mock_redis: AsyncMock,
    ) -> None:
        """Retry job must carry job_type + lineage metadata; result keeps job_type.

        // UNVERIFIED - not yet run red/green
        Kills handle_timeout__mutmut_44 (metadata=None), _47 (metadata kwarg
        dropped), the whole C16 payload-dict family _48-_55 (XX/UPPER key
        names, attempt +/- off-by-one), _97 (TimeoutResult.job_type=None),
        and start_job kwarg mutants _43 (job_type=None) / _45 (job_id kwarg
        removed) / _46 (job_type kwarg removed) via exact-call assertion.
        """
        mock_redis.get.return_value = {"count": 0}  # First attempt

        started_at = datetime.now(UTC) - timedelta(minutes=10)
        job = JobMetadata(
            job_id="job-123",
            job_type="export",
            status=JobState.RUNNING,
            progress=50,
            message=None,
            created_at=started_at,
            started_at=started_at,
            completed_at=None,
            result=None,
            error=None,
            extra={"source": "motion-detection"},
        )

        result = await job_timeout_service.handle_timeout(job)

        mock_job_status_service.start_job.assert_called_once_with(
            job_id=None,
            job_type="export",
            metadata={
                "retry_of": "job-123",
                # increment_attempt_count returns current+1 = 1; metadata logs
                # new_attempt + 1 = 2 (the retry is *attempt 2* of the job)
                "attempt": 2,
                "original_extra": {"source": "motion-detection"},
            },
        )
        assert result.job_type == "export"
```

Red/green: #44 passes `metadata=None` → kwargs inequality → fails; #47 omits the kwarg → fails; #97 → `result.job_type is None` → last assert fails; original exact-matches.

### T3 — kills C12 #15 (+#33 via sibling) → add to `TestJobTimeoutServiceIsJobTimedOut`

```python
    @pytest.mark.asyncio
    async def test_job_exactly_at_timeout_boundary_is_timed_out(
        self, job_timeout_service: JobTimeoutService, mock_redis: AsyncMock
    ) -> None:
        """now == started_at + timeout must time out (inclusive >=), both explicit
        and default-type branches.

        // UNVERIFIED - not yet run red/green
        Kills is_job_timed_out__mutmut_15 (duration 'now >= timeout_at' -> '>')
        and _33 (default branch 'now >= timeout_at' -> '>').
        """
        with freeze_time("2026-01-15 12:00:00"):
            started_at = datetime.now(UTC) - timedelta(seconds=300)
            job = JobMetadata(
                job_id="job-123",
                job_type="export",
                status=JobState.RUNNING,
                progress=50,
                message=None,
                created_at=started_at,
                started_at=started_at,
                completed_at=None,
                result=None,
                error=None,
            )

            assert (
                await job_timeout_service.is_job_timed_out(
                    job, TimeoutConfig(timeout_seconds=300)
                )
                is True
            )

            # Default branch: export default is 1800s; frozen now == boundary.
            mock_redis.get.return_value = None
            default_job = JobMetadata(
                job_id="job-default",
                job_type="export",
                status=JobState.RUNNING,
                progress=50,
                message=None,
                created_at=started_at,
                started_at=datetime.now(UTC) - timedelta(seconds=1800),
                completed_at=None,
                result=None,
                error=None,
            )
            assert await job_timeout_service.is_job_timed_out(default_job) is True
```

Red/green: `freeze_time` pins `datetime.now(UTC)` to exactly the boundary → original `>=` True; mutant `>` False → assert fails.

### T4 — kills C13 #20 (+ C12 #21 deadline leg) → add to `TestJobTimeoutServiceIsJobTimedOut`

```python
    @pytest.mark.asyncio
    async def test_naive_deadline_treated_as_utc_aware_deadline_preserved(
        self, job_timeout_service: JobTimeoutService
    ) -> None:
        """Naive deadlines are interpreted as UTC; tz-aware ones must not be clobbered.

        // UNVERIFIED - not yet run red/green
        Kills is_job_timed_out__mutmut_20 (tz guard 'deadline.tzinfo is None'
        -> 'is not None') and _21 (deadline 'now >= deadline' -> '>') via an
        exact-instant naive boundary plus a foreign-tz deadline whose naive
        wall-clock would falsely read as elapsed.
        """
        started_at = datetime.now(UTC) - timedelta(hours=2)
        job = JobMetadata(
            job_id="job-123",
            job_type="export",
            status=JobState.RUNNING,
            progress=50,
            message=None,
            created_at=started_at,
            started_at=started_at,
            completed_at=None,
            result=None,
            error=None,
        )

        with freeze_time("2026-01-15 12:00:00"):
            # Naive deadline at exactly the frozen instant -> UTC-interpreted -> timed out.
            naive_deadline = datetime(2026, 1, 15, 12, 0, 0)  # no tzinfo
            assert (
                await job_timeout_service.is_job_timed_out(
                    job, TimeoutConfig(deadline=naive_deadline)
                )
                is True
            )

            # Same wall-clock instant but -05:00 (= 17:00 UTC, in the future):
            # must NOT be timed out, i.e. its tzinfo must be preserved.
            foreign_deadline = datetime(
                2026, 1, 15, 12, 0, 0, tzinfo=timezone(timedelta(hours=-5))
            )
            assert (
                await job_timeout_service.is_job_timed_out(
                    job, TimeoutConfig(deadline=foreign_deadline)
                )
                is False
            )
```

Red/green: mutant #20 skips the UTC fix for the naive case → `now >= naive` raises TypeError (bare `>` variant would too) → first assert errors/fails; and it clobbers the `-05:00` zone to UTC → 12:00 <= now → second assert fails. Original: naive→12:00Z == now → True (`>=`; mutant #21 `>` would also fail here); foreign stays 17:00Z > now → False.

### T5 — kills C14 #26 (+ collateral C6 #29) → add to `TestJobTimeoutServiceIsJobTimedOut`

```python
    @pytest.mark.asyncio
    async def test_explicit_timeout_seconds_suppresses_default_timeout_fallback(
        self, job_timeout_service: JobTimeoutService
    ) -> None:
        """An explicit long timeout must not be clobbered by the job-type default.

        // UNVERIFIED - not yet run red/green
        Kills is_job_timed_out__mutmut_26 (fallback condition
        'timeout_seconds is None and deadline is None' -> 'is not None and ...'):
        the mutant engages the export default (1800s) for any config with
        timeout_seconds set, so a 10000s config on a 40-minute-old export job
        wrongly times out.
        """
        started_at = datetime.now(UTC) - timedelta(minutes=40)  # > export default 1800s
        job = JobMetadata(
            job_id="job-123",
            job_type="export",
            status=JobState.RUNNING,
            progress=50,
            message=None,
            created_at=started_at,
            started_at=started_at,
            completed_at=None,
            result=None,
            error=None,
        )

        is_timed_out = await job_timeout_service.is_job_timed_out(
            job, TimeoutConfig(timeout_seconds=10_000)
        )

        assert is_timed_out is False
```

Red/green: original → 40 min < 10 000 s and fallback suppressed by ts-not-None… (original fallback needs ts *is None* and dl is None → False) → passes; mutant's fallback (`ts is not None and dl is None` → True) checks default 1800 s < elapsed 2400 s → returns True → assert fails.

### T6 — kills C9 (9 keys); opportunistic partial kills of C1/C3 at asserted records → add to `TestJobTimeoutServiceHandleTimeout` and `…CheckForTimeouts`

```python
    @pytest.mark.asyncio
    async def test_timeout_logs_carry_accurate_attempt_counters(
        self,
        job_timeout_service: JobTimeoutService,
        mock_job_status_service: AsyncMock,
        mock_redis: AsyncMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Structured log counters must match reality (attempt = current + 1).

        // UNVERIFIED - not yet run red/green
        Kills handle_timeout__mutmut_31/_32 (warning 'attempt' off-by-one/two),
        _73/_74 (reschedule-log 'attempt'), _92/_93 (permanent-fail 'attempts')
        and check_for_timeouts__mutmut_43 (rescheduled_count sum(1 -> 2)),
        plus exact-message asserts kill C1 message mutants at these records.

        NOTE (verify at red/green time): the project logger passes structured
        fields via `extra=`; depending on backend/core/logging.py's
        ContextFilter, values surface as record.extra[...] — if they land as
        top-level record attrs use getattr(record, "attempt") instead. The
        value assertions are what kill the mutants either way.
        """
        started_at = datetime.now(UTC) - timedelta(minutes=10)
        job = JobMetadata(
            job_id="job-123",
            job_type="export",
            status=JobState.RUNNING,
            progress=50,
            message=None,
            created_at=started_at,
            started_at=started_at,
            completed_at=None,
            result=None,
            error=None,
        )

        logger_name = "backend.services.job_timeout_service"
        with caplog.at_level("DEBUG", logger=logger_name):
            mock_redis.get.return_value = {"count": 0}
            await job_timeout_service.handle_timeout(job)
            warning = next(
                r for r in caplog.records if r.getMessage() == "Job timed out"
            )
            assert warning.extra["attempt"] == 1  # mutant: 0 or 2
            resched = next(
                r for r in caplog.records
                if r.getMessage() == "Job rescheduled for retry after timeout"
            )
            assert resched.extra["attempt"] == 2  # new_attempt+1; mutant: 1 or 3

        caplog.clear()
        with caplog.at_level("DEBUG", logger=logger_name):
            mock_redis.get.return_value = {"count": DEFAULT_MAX_RETRY_ATTEMPTS - 1}
            await job_timeout_service.handle_timeout(job)
            fail = next(
                r for r in caplog.records
                if r.getMessage() == "Job permanently failed after max timeout attempts"
            )
            assert fail.extra["attempts"] == DEFAULT_MAX_RETRY_ATTEMPTS
```

```python
    @pytest.mark.asyncio
    async def test_check_for_timeouts_summary_counts_accurate(
        self,
        job_timeout_service: JobTimeoutService,
        mock_job_status_service: AsyncMock,
        mock_redis: AsyncMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Summary log must count rescheduled jobs correctly (1 per rescheduled).

        // UNVERIFIED - not yet run red/green
        Kills check_for_timeouts__mutmut_43 (rescheduled_count sum(1 -> 2)).
        """
        mock_redis.zrangebyscore.return_value = ["job-123", "job-456"]
        started_at = datetime.now(UTC) - timedelta(minutes=40)  # past export default
        mock_job_status_service.get_job_status.side_effect = [
            JobMetadata(
                job_id="job-123", job_type="export", status=JobState.RUNNING,
                progress=50, message=None, created_at=started_at,
                started_at=started_at, completed_at=None, result=None, error=None,
            ),
            JobMetadata(
                job_id="job-456", job_type="export", status=JobState.RUNNING,
                progress=50, message=None, created_at=started_at,
                started_at=started_at, completed_at=None, result=None, error=None,
            ),
        ]
        mock_redis.get.return_value = {"count": 0}  # retries available

        logger_name = "backend.services.job_timeout_service"
        with caplog.at_level("DEBUG", logger=logger_name):
            results = await job_timeout_service.check_for_timeouts()

        assert len(results) == 2
        summary = next(
            r for r in caplog.records if r.getMessage() == "Handled timed-out jobs"
        )
        assert summary.extra["timed_out_count"] == 2
        assert summary.extra["rescheduled_count"] == 2  # mutant: 4
```

(If C7 #26 is ever promoted, kill it with a mixed scan: `zrangebyscore → ["gone","job-456"]` with `get_job_status.side_effect = [None, <timed-out metadata>]` → `len(results) == 1` under continue, 0 under break. Fold into this test's setup by making the first lookup return None.)

## Recommendations for WP4.4

1. **Land T1–T6** (all pure-mock, no infra). Kills all 24 non-C6 TEST-GAP keys (C9–C16) + collateral C6 start_job trio (#43/#45/#46) and a slice of C1 at asserted records.
2. **Kill C6 (13 keys) by fixing the harness, not with 13 tests**: give `mock_redis` a key-aware store —
   ```python
   store: dict[str, Any] = {}
   redis.get.side_effect = lambda key: store.get(key)
   async def _set(key, value, expire=None): store[key] = value
   redis.set.side_effect = _set
   ```
   Null-key mutants then read/write `job:None:timeout`, miss the store, and flip observable outcomes (config lost, counter never increments). `assert_called_once_with` (as in T2) covers the rest.
3. **Do not chase the 82-key C1/C2/C3 log-string population with per-message tests.** One caplog smoke test per logging callsite (level + exact msg, T6-style) opportunistically kills most of C1/C3. **Before scoring C2 as final-EQUIVALENT, grep the log-DB/admin-UI consumers (backend/core/logging.py PostgreSQL handler) for reads of `active_job_count`/`job_id`/`attempt`/`max_attempts` — if any consumer queries those keys, C2 (40 keys) is actually TEST-GAP and one key-name assert kills all 40.**
4. C4: optional one-liner `zrangebyscore.assert_called_once_with(JOBS_ACTIVE_KEY, "-inf", "+inf")` — redis-py is case-insensitive on infinities, so this is convention-locking, not defect-catching. Keep as-is otherwise.
5. Scoring guidance for the rollup: C6's verdict is *harness-relative* — under a key-aware fake several flip to killable logic mutants (wrong Redis key read/write). Recommend annotating them "equivalent-under-current-harness" rather than plain EQUIVALENT… they are already counted TEST-GAP here since the behavior change is real and the line executes.

## Appendix — full key assignment

`/tmp/wp25/wp44-triage/jts_clusters.json` — cluster id → classification → every one of the 133 mutant keys (partition verified disjoint+complete against the meta file). Raw diffs: `/tmp/wp25/wp44-triage/jts_diffs_raw.txt`.
