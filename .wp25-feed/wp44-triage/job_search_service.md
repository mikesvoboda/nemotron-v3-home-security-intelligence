# WP4.4 Triage Dossier — backend/services/job_search_service.py

Generated: 2026-09-17 (WP4.3 survivors → WP4.4). READ-ONLY analysis; no tests were executed, no repo file modified.

## Verdict source

- `mutants/backend/services/job_search_service.py.meta`: 475 keys → **121 survived (exit_code 0)**, 131 killed, 223 unchecked (run still in progress — re-triage survivors when the run finishes; killed set only grows).
- All 121 diffs obtained via `uv run mutmut show <key>` (worked; no fallback needed).
- Covering tests: `mutants/mutmut-stats.json` → `tests_by_mangled_function_name`.
- **Single covering test file for the entire module: `backend/tests/unit/services/test_job_search_service.py`** (cited below as `TJS`, with line refs).
- All surviving mutants are one-line changes; the surviving set consists entirely of: log-payload mutations (32), call-argument removal/nullification (44), sort/filter wiring (19), defensive-fallback constants (9), boolean-operator flips (4), dead-default swaps (10), one dict-key swap (1), and the ternary→constant trio (plus dups, 6).

## Environment note

`python` is 3.14.4 — the module's `except ValueError, TypeError:` (job_search_service.py:111) parses fine under PEP 758. No anomaly, no mutant needed there.

## Semantic facts used for classification

1. `JobSearchFilters` (job*search_service.py:44-58) defaults: `statuses`/`job_types` default to `[]` via `field(default_factory=list)`, every other field defaults to `None`. → removing a kwarg or passing `None` is a **no-op only when the caller itself supplies None/[]** — which is exactly what every existing test does, hence G5/G10/G1 survive. When a test \_does* pass a real value, the same mutation is a real bug.
2. `filters.queue` is **never read** anywhere in the repo (grep-verified; docstring says "reserved for future use"). → all queue-argument mutations are no-ops.
3. `JobInfo` (job_tracker.py:65, TypedDict) requires `status`/`job_type` keys → `"unknown"` fallbacks in `_compute_aggregations` only fire on malformed tracker rows (the module's deliberate graceful-degradation style, cf. NEM-2540 comment).
4. `by_status.get(status, 0)` and `by_status[status]` assign the same key → `get(None, 0)` mutation mutates the wrong dict key but the right value: equivalent.
5. Removing/None-ing a keyword argument at a call site falls back to the callee's default (runtime-verified).
6. Dropped-kwarg mutants fall into two kinds: (a) kwarg whose call-site default differs from what the caller has when a test passes it → **killable by a delegation test** (TEST-GAP); (b) kwarg covered by the construction site's `X or []` default, or an unused param → **EQUIVALENT**.

## Cluster table (counts sum to 121)

Legend: SJ = `search_jobs`, SWA = `search_jobs_with_aggregations`, SVC = `JobSearchService.search`, CJ = `_calculate_job_duration`, CA = `_compute_aggregations`. Keys below are shortened as `<func>__mutmut_N` after stripping `backend.services.job_search_service.x`.

| #   | Pattern (cluster)                                                                                                                                                                                                                                                        | Fn         | Count | Class        | Example keys                |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------- | ----: | ------------ | --------------------------- |
| G1  | Delegation drops/nullifies every filter/sort/page argument (`kw=X` → `kw=None` / kwarg removed in the `search_jobs_with_aggregations(...)` call)                                                                                                                         | SVC        |    19 | **TEST-GAP** | SVC**2, SVC**9, SVC\_\_23   |
| G2  | Range-unpack ternary forced always-false: `X if X else (None,None)` → `X if (X) and False else (None,None)` — created/completed/duration ranges silently discarded                                                                                                       | SJ+SWA     |     6 | **TEST-GAP** | SJ**2, SJ**5, SWA\_\_8      |
| G3  | SWA sort-direction computation broken: `reverse = sort_order.lower() == "desc"` → `None` / `!=` / always-false comparisons — default output order flips to ascending                                                                                                     | SWA        |     5 | **TEST-GAP** | SWA**44, SWA**46, SWA\_\_47 |
| G4  | Sort call argument mutations: `_get_sort_key(j, sort_by)` → `(j, None)` (always sorts by created_at) and `reverse=reverse` → `reverse=None`/removed (ascending)                                                                                                          | SJ+SWA     |     4 | **TEST-GAP** | SJ**53, SWA**50, SWA\_\_52  |
| G5  | `JobSearchFilters(...)` construction: query / created*\* / completed*\* / has_error / min_duration / max_duration kwarg → `None` or removed — caller-supplied filters discarded                                                                                          | SJ+SWA     |    32 | **TEST-GAP** | SJ**11, SJ**16, SWA\_\_30   |
| G6  | `_calculate_job_duration` second-guard flip `if started_at and completed_at` → `or` — raises `TypeError` (None timestamp subtracted) when one timestamp string is present but unparseable, instead of returning None                                                     | CJ         |     1 | **TEST-GAP** | CJ\_\_16                    |
| G7  | `list or []` → `list and []` (always-empty when caller passes non-empty) on `job_types=` (SJ) / `statuses=` (SWA) — caller's filter list discarded                                                                                                                       | SJ+SWA     |     2 | **TEST-GAP** | SJ**34, SWA**33             |
| G8  | `_compute_aggregations` `"unknown"` fallback mutations (`None`/removed/`"XXunknownXX"`/`"UNKNOWN"`, status and type sides) — malformed job rows bucket under `"None"`/`""`/sentinel instead of `"unknown"`                                                               | CA         |     8 | **TEST-GAP** | CA**6, CA**23, CA\_\_11     |
| G9  | `by_status.get(status, 0)` → `by_status.get(None, 0)` — reads a permanently-absent key, so every status bucket is stuck at 1 whenever two jobs share a status                                                                                                            | CA         |     1 | **TEST-GAP** | CA\_\_15                    |
| G10 | `statuses=statuses or []` / `job_types=job_types or []` → explicit `None` — overrides the dataclass default with `None`, and `_matches_status_filter`/`_matches_type_filter` treat falsy as all-pass → caller's filter silently becomes no-op                            | SJ+SWA     |     2 | **TEST-GAP** | SJ**13, SWA**12             |
| E1  | `queue` kwarg → `None` / removed — `filters.queue` is never read (reserved param)                                                                                                                                                                                        | SJ+SWA+SVC |     6 | EQUIVALENT   | SJ**14, SVC**5, SWA\_\_25   |
| E2  | `statuses=statuses or []` / `job_types=job_types or []` kwarg **removed entirely** — dataclass default `field(default_factory=list)` already yields `[]`, identical to `[] or []`                                                                                        | SJ+SWA     |     2 | EQUIVALENT   | SJ**24, SWA**23             |
| E3  | `_calculate_job_duration` guard `not started or not completed` → `and` — redundant early-return: with exactly one timestamp missing, `_parse_datetime(None)` returns None and the second guard (`if started_at and completed_at`) already falls through to `return None` | CJ         |     1 | EQUIVALENT   | CJ\_\_9                     |
| L1  | Logger message text mutations (`"Job search [with aggregations] completed"` → None/`XX..XX`/lower/UPPER)                                                                                                                                                                 | SJ+SWA     |     8 | LOW-VALUE    | SJ**62, SJ**58, SWA\_\_64   |
| L2  | `extra=None` replacing the log `extra={...}` dict                                                                                                                                                                                                                        | SJ+SWA     |     2 | LOW-VALUE    | SJ**59, SWA**61             |
| L3  | Log call `extra={...}` kwarg removed entirely                                                                                                                                                                                                                            | SJ+SWA     |     2 | LOW-VALUE    | SJ**61, SWA**63             |
| L4  | Log `extra` dict **keys** renamed (`"total"`→`"XXtotalXX"`/`"TOTAL"` etc., 8 sites in SJ, 3+total in SWA)                                                                                                                                                                | SJ+SWA     |    20 | LOW-VALUE    | SJ**65, SJ**78, SWA\_\_71   |

**TEST-GAP 80 (G1-G10) · EQUIVALENT 9 (E1-E3) · LOW-VALUE 32 (L1-L4) · total 121.**

### Why each TEST-GAP cluster is a gap (with covering-test evidence)

All covering tests live in `backend/tests/unit/services/test_job_search_service.py` (TJS). Line refs to TJS; source refs to `backend/services/job_search_service.py` (JSS).

- **G1** (TJS:497-514, `TestJobSearchService.test_search_method` — the _only_ test reaching `JobSearchService.search`, JSS:619-633): it asserts only `result.total == 2` with `query` + `statuses` that happen to select the same 2 jobs as `query` alone. `limit`, `offset`, `sort_*`, `*_range`, `duration_range`, `has_error`, `job_types` never pass through the wrapper in any test. Killer: T1 below (behavioral forwarding assertions + optional kwargs-equality variant patching `search_jobs_with_aggregations`).
- **G2** (JSS:428-430 SJ / :517-519 SWA): no test ever passes `created_range`/`completed_range`/`duration_range` end-to-end; helper-level tests (`TestMatchesTimestampFilter` TJS:225, `TestMatchesDurationFilter` TJS:284) stop below the boundary. Killer: T2.
- **G3** (JSS:548): TJS sort tests (`test_sorting_asc/desc`, TJS:426-456) exercise **`search_jobs` only**; SWA's sort direction is never asserted (its two tests, TJS:459-494, take default order and don't check sequence). All five mutants flip SWA's default order to ascending — an unobservable-by-existing-tests bug. Killer: T3.
- **G4** (JSS:457 SJ / :549 SWA): SWA output order never asserted (see G3); SJ `sort_by` variation untested (both SJ sort tests use `sort_by="created_at"`, which equals the `None`-fallback behavior — JSS:389 defaults unknown/None keys to `created_at`). Killer: T3 (SWA side + non-created_at key) + T2's SJ sort assertion.
- **G5** (JSS:432-444 SJ / :521-533 SWA): `search_jobs` tests (TJS:391-456) never pass `query`/`has_error`/ranges; SWA tests never pass `created_range`/`completed_range`/`duration_range`/`has_error`. Each mutant zeroes exactly the parameter no test supplies. Same killer as G2 (T2 passes every one of these through both functions).
- **G6** (JSS:137): TJS:134-152 never feeds one valid + one unparseable timestamp; `and→or` then subtracts `None` → `TypeError` instead of the documented `None` return. Killer: T4. (The sibling `or`→`and` early-guard mutant is EQUIVALENT — see E3 — because `_parse_datetime(None)` → `None` and the second guard already returns `None`.)
- **G7/G10** (JSS:434-435 SJ statuses/job_types / :522-523 SWA): SJ tests never pass `job_types` at all; the sole SWA caller-with-statuses test (`test_search_method`, TJS:500-514) uses `statuses=["completed","running"]` redundant with its `query="export"` filter, so nullifying statuses keeps `total==2`. Killers: T2's `sj(job_types=["backup"])` → total 1 (SJ**34, SJ**13) and T3's `swa(statuses=["completed"])` → total 1 (SWA**33, SWA**12).
- **G8** (JSS:357,361): TJS `TestComputeAggregations` (TJS:342-364) always supplies status+job_type → fallback unexercised. Killer: T5.

### Why EQUIVALENT clusters need no tests

- **E1**: `filters.queue` unread in the whole repo (grep-verified) — the argument can hold anything.
- **E2**: `statuses`/`job_types` kwarg **removed** → dataclass default `field(default_factory=list)` yields `[]`, identical to the original's `X or []` → `[]` when the caller passes `None`/`[]`. Distinct from the `=None` override mutants (SJ**13/SWA**12), which defeat that default for non-empty callers — those are G10.
- **E3**: `_calculate_job_duration` guard `not started or not completed` → `and` (CJ\_\_9): any job that bypasses the mutant's early guard has at least one falsy timestamp, whose `_parse_datetime` is `None`, so the second guard `if started_at and completed_at` still returns `None`. Unreachable-difference equivalent.
  G9 note (not equivalent): `by_status.get(None, 0)` at JSS:358 reads a key that is never written, so the running count for every status is lost — each bucket stays stuck at 1 whenever two jobs share a status. `TestComputeAggregations` misses it only because its four sample jobs all have distinct statuses. Real behavior change → TEST-GAP, killed by T5's repeated-status assertion.

### Why LOW-VALUE clusters stay surviving

L1-L4 mutate only `logger.debug`/`logger.info` message text and `extra` payload keys/structure (JSS:462-474, :554-561). No production consumer parses these keys (they are stdlib-logging `extra` metadata; no test caplog assertion exists or is warranted). Recommend marking as baseline-acceptable (equivalent-for-scoring) in WP4.4 rather than writing tests.

## Drafted tests (UNVERIFIED — not yet run red/green)

All go in `backend/tests/unit/services/test_job_search_service.py`, matching its fixtures (`mock_job_tracker`, `sample_jobs`) and `@pytest.mark.anyio` style. TDD procedure for each: apply the cluster's mutant diff → the new assertion FAILS; revert diff → PASSES. (Run: `uv run pytest backend/tests/unit/services/test_job_search_service.py -k <new_test>` — not executed in this triage per WP4.4 constraints.)

### T1 — kills G1 (19 SVC mutants)

```python
class TestSearchDelegation:
    """search() must forward every argument to search_jobs_with_aggregations."""

    @pytest.mark.anyio
    async def test_delegation_forwards_every_argument(
        self, mock_job_tracker: MagicMock, sample_jobs: list[JobInfo]
    ) -> None:
        """Every filter/sort/pagination argument must reach the tracker query."""
        now = datetime.now(UTC)
        created_range = (now - timedelta(days=2), now - timedelta(minutes=5))
        completed_range = (now - timedelta(days=1), None)
        duration_range = (1.0, 7200.0)  # both completed jobs have duration 1740s

        mock_job_tracker.get_all_jobs.return_value = sample_jobs[:1]
        service = JobSearchService(job_tracker=mock_job_tracker)

        result = await service.search(
            query="export",
            statuses=["completed"],
            job_types=["export"],
            queue="default",
            created_range=created_range,
            completed_range=completed_range,
            has_error=False,
            duration_range=duration_range,
            limit=7,
            offset=3,
            sort_by="job_type",
            sort_order="asc",
        )

        assert isinstance(result, JobSearchResult)
        # sample_jobs[0] is the only job satisfying all constraints at once
        # (query matches job_type, status completed, no error, ~5400s duration
        # inside range, created/completed windows cover it). total is pre-pagination,
        # so limit=7/offset=3 must not shrink it.
        assert result.total == 1

        # Non-default sort must be honored: with one row we verify via kwargs --
        # force a second, differently-sortable row through the filters:
        mock_job_tracker.get_all_jobs.return_value = [sample_jobs[0], sample_jobs[3]]
        # job-4 (backup/pending) violates query/status/type/has_error filters, so
        # with full constraints still total == 1: proves query/statuses/job_types/
        # has_error were forwarded.
        result = await service.search(
            query="export",
            statuses=["completed"],
            job_types=["export"],
            created_range=created_range,
            completed_range=completed_range,
            has_error=False,
            duration_range=(1.0, _calculate_job_duration(sample_jobs[0]) + 60),
        )
        assert result.total == 1
        assert result.jobs[0]["job_id"] == "job-1"

        # Pagination must be forwarded: asc order is job-1,2,3,4 (oldest first);
        # offset=3/limit=1 must yield exactly the newest job, and total is
        # pre-pagination so it must stay 4.
        mock_job_tracker.get_all_jobs.return_value = sample_jobs
        result = await service.search(limit=1, offset=3, sort_order="asc")
        assert result.total == 4
        assert [j["job_id"] for j in result.jobs] == ["job-4"]

        # sort_by must be forwarded: sort by progress asc -> pending(0) first.
        result = await service.search(sort_by="progress", sort_order="asc")
        assert result.jobs[0]["job_id"] == "job-4"

        # duration_range forwarded: completed jobs job-1/job-2 both run 1740s
        # (start +1min, finish minus nothing: durations are exactly equal);
        # running/pending have no duration and never match duration filters.
        result = await service.search(duration_range=(1.0, 1800.0))
        assert result.total == 2
        assert {j["job_id"] for j in result.jobs} == {"job-1", "job-2"}
        result = await service.search(duration_range=(1800.0, None))
        assert result.total == 0

        # has_error forwarded.
        result = await service.search(has_error=True)
        assert [j["job_id"] for j in result.jobs] == ["job-2"]

        # created_range forwarded.
        result = await service.search(created_range=(now - timedelta(minutes=35), None))
        assert result.total == 2  # job-3, job-4 created inside window

        # completed_range forwarded.
        result = await service.search(completed_range=(now - timedelta(minutes=45), None))
        assert result.total == 1  # only job-2 completed recently
// UNVERIFIED - not yet run red/green
```

Kills every SVC\_\_N in G1: dropping/nullifying any single argument widens or reorders results so at least one assertion breaks. (Companion default-forwarding belt: `with patch("backend.services.job_search_service.search_jobs_with_aggregations", new=AsyncMock(return_value=JobSearchResult(jobs=[], total=0, aggregations=JobAggregations())))` … assert `mock.call_args.kwargs == {"job_tracker": mock_job_tracker, "query": None, "statuses": None, ..., "limit": 50, "offset": 0, "sort_by": "created_at", "sort_order": "desc"}` — kills G1 with zero behavioral coupling; pick either style in WP4.4.)

### T2 — kills G2 + G5 (38) + G7/G10 SJ side (SJ**34, SJ**13) + SJ\_\_53 sort_by

```python
class TestSearchEndToEndFilters:
    """Ranges/query/flags must survive from search_jobs args to JobSearchFilters."""

    @pytest.mark.anyio
    async def test_created_range_filtering(
        self, mock_job_tracker: MagicMock, sample_jobs: list[JobInfo]
    ) -> None:
        now = datetime.now(UTC)
        mock_job_tracker.get_all_jobs.return_value = sample_jobs
        jobs, total = await search_jobs(
            job_tracker=mock_job_tracker,
            created_range=(now - timedelta(minutes=35), None),
            sort_order="asc",
        )
        assert total == 2
        assert [j["job_id"] for j in jobs] == ["job-3", "job-4"]

    @pytest.mark.anyio
    async def test_completed_range_filtering(
        self, mock_job_tracker: MagicMock, sample_jobs: list[JobInfo]
    ) -> None:
        now = datetime.now(UTC)
        mock_job_tracker.get_all_jobs.return_value = sample_jobs
        _, total = await search_jobs(
            job_tracker=mock_job_tracker,
            completed_range=(now - timedelta(minutes=45), None),
        )
        assert total == 1

    @pytest.mark.anyio
    async def test_duration_range_filtering(
        self, mock_job_tracker: MagicMock, sample_jobs: list[JobInfo]
    ) -> None:
        mock_job_tracker.get_all_jobs.return_value = sample_jobs
        # both completed jobs have identical 1740s durations
        jobs, total = await search_jobs(
            job_tracker=mock_job_tracker, duration_range=(1.0, 1800.0)
        )
        assert total == 2
        assert {j["job_id"] for j in jobs} == {"job-1", "job-2"}

    @pytest.mark.anyio
    async def test_job_types_filter_on_search_jobs(
        self, mock_job_tracker: MagicMock, sample_jobs: list[JobInfo]
    ) -> None:
        """Kills SJ__34 (`job_types and []`) and SJ__13 (`job_types=None`)."""
        mock_job_tracker.get_all_jobs.return_value = sample_jobs
        _, total = await search_jobs(
            job_tracker=mock_job_tracker, job_types=["backup"]
        )
        assert total == 1  # only job-4; a nulled/emptied filter would give 4

    @pytest.mark.anyio
    async def test_search_jobs_sort_by_non_created_field(
        self, mock_job_tracker: MagicMock, sample_jobs: list[JobInfo]
    ) -> None:
        """Kills SJ sort-key mutants: sort_by must reach _get_sort_key."""
        mock_job_tracker.get_all_jobs.return_value = sample_jobs
        jobs, _ = await search_jobs(
            job_tracker=mock_job_tracker, sort_by="progress", sort_order="asc"
        )
        assert jobs[0]["job_id"] == "job-4"  # progress 0; created_at-first would say job-1

    @pytest.mark.anyio
    async def test_query_and_flags(
        self, mock_job_tracker: MagicMock, sample_jobs: list[JobInfo]
    ) -> None:
        mock_job_tracker.get_all_jobs.return_value = sample_jobs
        _, total = await search_jobs(job_tracker=mock_job_tracker, query="timeout")
        assert total == 1
        _, total = await search_jobs(job_tracker=mock_job_tracker, has_error=False)
        assert total == 3

    @pytest.mark.anyio
    async def test_same_filters_via_aggregations_entrypoint(
        self, mock_job_tracker: MagicMock, sample_jobs: list[JobInfo]
    ) -> None:
        """Same matrix through search_jobs_with_aggregations (kills SWA twins)."""
        now = datetime.now(UTC)
        mock_job_tracker.get_all_jobs.return_value = sample_jobs
        result = await search_jobs_with_aggregations(
            job_tracker=mock_job_tracker,
            query="timeout",
            created_range=(now - timedelta(hours=2), None),
            completed_range=(now - timedelta(minutes=45), None),
            has_error=True,
        )
        assert result.total == 1
        assert result.jobs[0]["job_id"] == "job-2"
        assert result.aggregations.by_status == {"failed": 1}

    @pytest.mark.anyio
    async def test_duration_and_created_range_via_aggregations(
        self, mock_job_tracker: MagicMock, sample_jobs: list[JobInfo]
    ) -> None:
        """Dedicated SWA calls so each range kills on its own (query can't dominate)."""
        now = datetime.now(UTC)
        mock_job_tracker.get_all_jobs.return_value = sample_jobs
        result = await search_jobs_with_aggregations(
            job_tracker=mock_job_tracker, duration_range=(1.0, 1800.0)
        )
        assert result.total == 2  # dropped filter -> 4
        result = await search_jobs_with_aggregations(
            job_tracker=mock_job_tracker,
            created_range=(None, now - timedelta(hours=1, minutes=30)),
        )
        assert result.total == 1  # only job-1 created 2h ago
// UNVERIFIED - not yet run red/green
```

TDD: with any SJ**{2,5,8}/SWA**{2,5,8} ternary or any G5 kwarg nullification/rollback-to-default applied, the range/query/flag no longer filters → `total` assertions fail; green on original.

### T3 — kills G3 + G4 + G7-SWA

```python
class TestAggregationSearchOrdering:
    """search_jobs_with_aggregations sorting is currently unasserted."""

    @pytest.mark.anyio
    async def test_default_sort_descending(
        self, mock_job_tracker: MagicMock, sample_jobs: list[JobInfo]
    ) -> None:
        mock_job_tracker.get_all_jobs.return_value = sample_jobs
        result = await search_jobs_with_aggregations(job_tracker=mock_job_tracker)
        assert [j["job_id"] for j in result.jobs] == ["job-4", "job-3", "job-2", "job-1"]

    @pytest.mark.anyio
    async def test_sort_ascending(
        self, mock_job_tracker: MagicMock, sample_jobs: list[JobInfo]
    ) -> None:
        mock_job_tracker.get_all_jobs.return_value = sample_jobs
        result = await search_jobs_with_aggregations(
            job_tracker=mock_job_tracker, sort_order="asc"
        )
        assert [j["job_id"] for j in result.jobs] == ["job-1", "job-2", "job-3", "job-4"]

    @pytest.mark.anyio
    async def test_sort_by_progress(
        self, mock_job_tracker: MagicMock, sample_jobs: list[JobInfo]
    ) -> None:
        mock_job_tracker.get_all_jobs.return_value = sample_jobs
        result = await search_jobs_with_aggregations(
            job_tracker=mock_job_tracker, sort_by="progress", sort_order="asc"
        )
        assert [j["job_id"] for j in result.jobs] == ["job-4", "job-2", "job-3", "job-1"]

    @pytest.mark.anyio
    async def test_statuses_filter_not_redundant_with_query(
        self, mock_job_tracker: MagicMock, sample_jobs: list[JobInfo]
    ) -> None:
        """Kills `statuses and []`: statuses must filter on their own."""
        mock_job_tracker.get_all_jobs.return_value = sample_jobs
        result = await search_jobs_with_aggregations(
            job_tracker=mock_job_tracker, statuses=["completed"]
        )
        assert result.total == 1
        assert result.aggregations.by_status == {"completed": 1}
// UNVERIFIED - not yet run red/green
```

All five SWA\_\_{44..48} reverse mutants flip the default order (jobs[0] becomes "job-1"); reverse=None/removed same. `_get_sort_key(j, None)` mutants sort by created_at — the progress-order assertion fails.

### T4 — kills G6 (CJ\_\_16)

```python
class TestCalculateJobDurationPartialTimestamps:
    """Duration guard: either timestamp missing/unparseable => None, never TypeError."""

    def test_missing_completed_at(self) -> None:
        job = JobInfo(
            job_id="j", job_type="export", status=JobStatus.RUNNING, progress=50,
            message=None, created_at="2024-01-15T10:00:00+00:00",
            started_at="2024-01-15T10:01:00+00:00", completed_at=None,
            result=None, error=None,
        )
        assert _calculate_job_duration(job) is None

    def test_unparseable_completed_at(self) -> None:
        """Kills `if started_at or completed_at`: one valid + one garbage => None."""
        job = JobInfo(
            job_id="j", job_type="export", status=JobStatus.FAILED, progress=50,
            message=None, created_at="2024-01-15T10:00:00+00:00",
            started_at="2024-01-15T10:01:00+00:00", completed_at="not-a-date",
            result=None, error=None,
        )
        assert _calculate_job_duration(job) is None
// UNVERIFIED - not yet run red/green
```

CJ**16 (`and`→`or`): the second test raises `TypeError` (subtracting `None` from a datetime, since `_parse_datetime("not-a-date")` → None) where the original returns None. The first test passes on both original and CJ**9-equivalent mutant — it is kept to pin the guard behavior documented in E3. (No existing test ever feeds an unparseable timestamp; TJS:128-131 tests `_parse_datetime` directly but never through `_calculate_job_duration`.)

### T5 — kills G8 + G9 (9)

```python
class TestComputeAggregationsFallback:
    """Malformed rows (missing status / job_type) bucket under 'unknown'; counts accumulate."""

    def test_missing_status_and_type_fall_back_to_unknown(self) -> None:
        jobs: list[JobInfo] = [
            JobInfo(job_id="a", job_type="export", status=JobStatus.COMPLETED,
                    progress=100, message=None, created_at="2024-01-15T10:00:00+00:00",
                    started_at=None, completed_at=None, result=None, error=None),
        ]
        # TypedDict is runtime-unenforced: simulate malformed tracker rows
        malformed = [{k: v for k, v in jobs[0].items() if k not in ("status", "job_type")}]
        aggs = _compute_aggregations(malformed)
        assert aggs.by_status == {"unknown": 1}
        assert aggs.by_type == {"unknown": 1}

    def test_repeated_status_accumulates(self) -> None:
        """Kills by_status.get(None, 0): every shared-status key must count up."""
        jobs: list[JobInfo] = [
            JobInfo(job_id="a", job_type="export", status=JobStatus.COMPLETED,
                    progress=100, message=None, created_at="2024-01-15T10:00:00+00:00",
                    started_at=None, completed_at=None, result=None, error=None),
            JobInfo(job_id="b", job_type="export", status=JobStatus.COMPLETED,
                    progress=100, message=None, created_at="2024-01-15T10:01:00+00:00",
                    started_at=None, completed_at=None, result=None, error=None),
        ]
        aggs = _compute_aggregations(jobs)
        assert aggs.by_status == {"completed": 2}
        assert aggs.by_type == {"export": 2}
// UNVERIFIED - not yet run red/green
```

## Recommended WP4.4 dispositions

1. **Write T1-T5** (5 new test bodies ≈ 79 survivors killed). T2+T3 are highest yield/effort.
2. E1-E2: skip (equivalent). Consider `mutmut` config exemptions if the baseline tooling supports per-mutant triage tags.
3. L1-L4 (32): mark LOW-VALUE/baseline-acceptable; do not test log `extra` payload.

## File references

- Source: `backend/services/job_search_service.py` (SJ :392-476, SWA :479-567, SVC.search :585-633, CJ :119-140, CA :343-364)
- Tests: `backend/tests/unit/services/test_job_search_service.py` (TJS; sole covering file per mutmut-stats `tests_by_mangled_function_name`)
- Meta: `mutants/backend/services/job_search_service.py.meta`
- Raw diff dump analyzed: `/tmp/wp25/wp44-triage/all_diffs.txt`
