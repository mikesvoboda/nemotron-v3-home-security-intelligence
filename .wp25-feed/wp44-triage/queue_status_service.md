# WP4.4 Triage Dossier — backend/services/queue_status_service.py

Date: 2026-09-18 · Wave: gen-2 NEW tier (triage only, nothing executed)
Meta: `mutants/backend/services/queue_status_service.py.meta` — 241 keys total, **69 SURVIVED**, 172 killed, 0 unchecked.
Mutant copy: `mutants/backend/services/queue_status_service.py` · Diffs captured verbatim via `uv run mutmut show` (69/69, no fallback needed) → `/tmp/wp25/wp44-triage/qs_diffs.txt`.
Survivor keys: `/tmp/wp25/wp44-triage/queue_status_surv_keys.txt`.

**Status: UNVERIFIED — no tests were run (live mutation run owns the machine). All drafted tests below are red/green-unproven.**

## Covering test files (from `mutants/mutmut-stats.json` → tests_by_mangled_function_name)

| File | What it is | Key line anchors |
|---|---|---|
| `backend/tests/unit/services/test_queue_status_service.py` | Primary, exclusively covers this module | `TestQueueThresholds:43`, `TestCalculateHealth:103`, `TestQueueStatusService:180`, `TestSummaryCalculation:361`, `TestOldestJobInfo:468`, `TestSingleton:569`, `TestThroughputAndWorkers:602` |
| `backend/tests/unit/api/routes/test_queues.py` | Route tests; **every endpoint test patches `backend.api.routes.queues.get_queue_status_service`** (first use :215), so the factory body + real service never run there. Only `TestGetQueueService.test_get_queue_service_returns_service:167` runs the real factory and asserts only `is not None` + `hasattr`. | :163-175, :215+ |

Core weakness pattern of the test file: **every Redis interaction goes through `AsyncMock` that ignores call arguments and returns canned values**, and value assertions are inequality-style (`> 0`, `>= 0`) instead of pinning the documented constants. That makes all call-argument mutants and all "tweak a magic number while staying >0" mutants silent.

## Cluster table (69 survivors, counts sum exactly)

Legend — loc lines refer to `backend/services/queue_status_service.py`.

| # | Pattern | Count | Class | Keys (fn-relative `__mutmut_N`) | Locus |
|---|---|---|---|---|---|
| 1 | `_get_oldest_job_info`: `peek_queue(queue, start=0, end=0)` call-arg mutated — name→None, name dropped, start/end→None, start→1, end→1, end dropped | 7 | TEST-GAP | oldest 2,3,4,5,6,8,9 | :257 |
| 2 | `_get_oldest_job_info`: `start=` kwarg dropped (redis default `start=0` → same real call) | 1 | EQUIVALENT | oldest 7 | :257 |
| 3 | `_get_oldest_job_info`: job-id chain `oldest.get("id")` first term → `None`/`"XXidXX"`/`"ID"` | 3 | TEST-GAP | oldest 20,21,22 | :268 |
| 4 | `_get_oldest_job_info`: `job_id = None` → `""` (falsy → final `id=None` unchanged on every path) | 1 | EQUIVALENT | oldest 13 | :262 |
| 5 | `_get_oldest_job_info`: timestamp fallback `oldest.get("queued_at")` → `None`/`"XXqueued_atXX"`/`"QUEUED_AT"` | 3 | TEST-GAP | oldest 34,35,36 | :269 |
| 6 | `_get_oldest_job_info`: `"Z"→"+00:00"` iso-normalization string tweaks (48 `XXZXX`, 49 `z`, 50 `XX+00:00XX`) | 3 | EQUIVALENT | oldest 48,49,50 | :278 |
| 7 | `_get_oldest_job_info`: naive-timestamp branch `tzinfo is None` → `is not None` | 1 | TEST-GAP | oldest 53 | :280 |
| 8 | `_get_oldest_job_info`: returned `OldestJobInfo.queued_at` nulled (57 `queued_at=None`) / kwarg dropped (60, pydantic default None) | 2 | TEST-GAP | oldest 57,60 | :292 |
| 9 | `_get_oldest_job_info`: `logger.debug(f"...")` → `logger.debug(None)` | 1 | EQUIVALENT | oldest 70 | :296 |
| 10 | `_get_throughput_metrics`: default-throughput **table** values nudged — DETECTION (10.0,2.5)→(11.0/3.5), ANALYSIS (5.0,8.0)→(6.0/9.0), **DLQ_ANALYSIS (0.0,0.0)→(1.0,0.0)/(0.0,1.0)** | 6 | TEST-GAP | throughput 2,3,4,5,8,9 | :314-318 |
| 11 | `_get_throughput_metrics`: unknown-queue fallback `.get(q, (0.0,0.0))` → `None`(12), dropped(14), `(1.0,0.0)`(15), `(0.0,1.0)`(16) | 4 | TEST-GAP | throughput 12,14,15,16 | :321 |
| 12 | `_get_worker_info`: `DLQ_ANALYSIS_QUEUE: 0` → `1` in worker table | 1 | TEST-GAP | worker 4 | :347 |
| 13 | `_get_worker_info`: unknown-queue default `.get(q, 1)` → `None`(7), dropped(9), `2`(10) | 3 | TEST-GAP | worker 7,9,10 | :350 |
| 14 | `_get_worker_info`: running formula broken — `if workers > 0` ∧ False (12), cap `min(workers,2)` (18), `workers > 1` (20) | 3 | TEST-GAP | worker 12,18,20 | :354 |
| 15 | `_get_worker_info`: running formula no-ops — `or True` (13, tautology ≡ original), `workers >= 0` (19, settings enforce `ge=1` so workers==0 only for DLQs) | 2 | EQUIVALENT | worker 13,19 | :354 |
| 16 | `get_queue_status`: display-name fallback `QUEUE_NAME_MAP.get(q, q)` default → None/dropped (3,4,5 — three spellings of one change) | 3 | TEST-GAP | qstatus 3,4,5 | :158 |
| 17 | `get_queue_status`: call-arg wiring `None`-swaps — `get_queue_length(None)`(7), `_get_oldest_job_info(None)`(9), `calculate_health(None, …)`(14), `_get_throughput_metrics(None)`(21) | 4 | TEST-GAP | qstatus 7,9,14,21 | :164,167,171,174 |
| 18 | `get_all_queues_status`: warning **message** text → None | 1 | EQUIVALENT | gallq 6 | :210 |
| 19 | `get_all_queues_status`: `extra={"queue_name":…,"error":…}` key/value string tweaks | 5 | LOW-VALUE | gallq 10,11,12,13,14 | :211 |
| 20 | `get_all_queues_status`: `extra=` kwarg set to None(7) / removed(9) | 2 | LOW-VALUE | gallq 7,9 | :211 |
| 21 | `get_all_queues_status`: degraded-status metrics nudged — depth/running/workers/jobs_per_min/avg_seconds 0→1 | 5 | TEST-GAP | gallq 34,35,36,41,42 | :219-224 |
| 22 | `get_all_queues_status`: degraded status `oldest_job=None` kwarg dropped (pydantic default) | 1 | EQUIVALENT | gallq 33 | :226 |
| 23 | `get_all_queues_status`: degraded display-name `QUEUE_NAME_MAP.get(q, q)` mutated (16 → falls back to *raw* name; 17,18,19 → None → pydantic ValidationError **inside the except handler**, crashes the whole endpoint) | 4 | TEST-GAP | gallq 16,17,18,19 | :214 |
| 24 | `__init__`: dead attrs seeded with garbage — `_job_counts: dict = None`(2), `_last_sample_time = ""`(3); **grep: neither attribute is ever read anywhere** | 2 | EQUIVALENT | init 2,3 | :146-147 |
| 25 | `get_queue_status_service`: singleton built `QueueStatusService(None)` instead of `(redis)` | 1 | TEST-GAP | x_get_queue_status_service 3 | :402 |

**Totals: TEST-GAP 50 (c1,3,5,7,8,10,11,12,13,14,16,17,21,23,25) · EQUIVALENT 12 (c2,4,6,9,15,18,22,24) · LOW-VALUE 7 (c19,20) · sum 69.**

## Why each TEST-GAP cluster is a gap (assertion autopsy)

- **1 / 17 (mock argument blindness):** `test_queue_status_service.py` fixtures give `AsyncMock` with canned `peek_queue`/`get_queue_length` returns and assert only the *returned* `QueueStatus` fields. Mocks answer identically for any arguments, so no test can see which queue name or what slice indices the service asked for. Nothing pins the documented contract "workers use unprefixed queue names" (comment at :159-161). `m14` differs observably (display `"dlq"` thresholds 10/50/86400 vs `None`→DEFAULT 50/100/300); `m21` (throughput lookup by `None` → (0,0) instead of (10.0,2.5)) differs observably — neither asserted.
- **3:** no test feeds a dict with `"id"` present — `test_oldest_job_with_file_path:478` and `test_oldest_job_with_batch_id:491` only use `file_path`/`batch_id`, where the mutated first term is `.get()`→None either way. The `id > batch_id > file_path` priority itself is also untested.
- **5:** no test uses `queued_at` as the only timestamp key; existing tests always provide `"timestamp"`.
- **7:** every test timestamp is `datetime.now(UTC).isoformat()` → always tz-aware → the naive-UTC-assumption branch body never executes. Under the mutant a naive timestamp triggers naive-aware subtraction TypeError → swallowed → `info=None` (a real production behavior change, unasserted).
- **8:** no test anywhere asserts `oldest_job.queued_at`; pydantic default None makes the drop silent.
- **10:** `test_throughput_detection_queue:611` / `test_throughput_analysis_queue:619` assert only `> 0`; `test_throughput_dlq_queue:628` pins `== 0` but **only for `DLQ_DETECTION_QUEUE`** — `DLQ_ANALYSIS_QUEUE` is imported nowhere in the test file, so its (0.0,0.0)→(1.0,·) mutants are invisible even with the strict DLQ assert.
- **11 / 13:** no caller or test ever passes an unknown queue, so both `.get()` fallbacks are dead-untested; the None-default variants crash only on unknown names (TypeError), the (1.0,·)/2 defaults change the fallback value.
- **12:** `test_worker_info_dlq_queue:645` covers `DLQ_DETECTION_QUEUE` only; DLQ_ANALYSIS (should be `(0, 0)`) is untouched.
- **14:** `test_worker_info_detection_queue:637` asserts `workers > 0, running >= 0` — cannot see `running` flip 1↔0↔2. (With settings defaults `detection_worker_count=2`, `ge=1`: m12→running 0, m18→2, m20 survives-at-2 so the kill test must also exercise `workers == 1`.)
- **16 / 23:** all monitored queues are in `QUEUE_NAME_MAP`, so the fallback second arg never fires in tests; m23's variants produce None → pydantic ValidationError *in the error path itself* (endpoint would 500), m16 (gallq) would emit raw `"detection_queue"` as the display name. `test_get_all_queues_status_handles_errors:325` asserts only `len == 4` and `statuses[0].status == CRITICAL`.
- **21:** same test — none of the six degraded fields (`depth/running/workers/jobs_per_minute/avg_processing_seconds/oldest_job`) is asserted, exactly the "test exists but asserts too weakly" case.
- **25:** `TestSingleton:569` asserts identity/re-creation only; `test_queues.py` route tests patch the factory everywhere else, so the constructed instance's `_redis` is never observed.

## EQUIVALENT / LOW-VALUE notes

- **2:** `RedisClient.peek_queue(self, queue_name, start: int = 0, end: int = 100, ...)` (`backend/core/redis.py:1033`) — dropping `start=0` reproduces the identical call. (A call-argument assert like Draft D kills it anyway; classified by real-client semantics.)
- **4:** `""` is falsy → `id=str(job_id) if job_id else None` → `None` on all paths.
- **6:** module runs on Python 3.14 (repo CI 3.14.2); `datetime.fromisoformat` accepts `Z` natively since 3.11 — the `.replace("Z", "+00:00")` is dead normalization, so its string mutants are unobservable. Verified locally: `fromisoformat('…Z')` parses.
- **9 / 18:** log-message text only (`logger.debug(None)` renders "None"; both at debug/warning level, message text not part of any contract).
- **19 / 20 (LOW-VALUE):** structured `extra` payload genuinely changes (a log aggregator keyed on `extra.queue_name` would miss), but asserting exact `extra` dicts in unit tests is low value; no test uses `caplog` for this module.
- **15:** `or True` is a tautology (true exactly where `workers > 0` is); `>= 0` only differs at `workers == 0`, unreachable because settings fields enforce `ge=1` and the table's zeros are the only 0 entries — where both conditions are False. (If a future settings field could be 0 this becomes a gap.)
- **22:** `oldest_job` pydantic default is `None` — explicit kwarg is redundant.
- **24:** `_job_counts` / `_last_sample_time` are write-once-never-read (grep: assignment sites in the whole `backend/` tree are the only hits); throughput docstring says real calculation is not implemented.

## Source observations while triaging (not mutant issues)

1. `backend/services/queue_status_service.py:284` reads `except ValueError, AttributeError:` — valid only under PEP 758 (Python ≥3.14 unparenthesized except). Parses here (3.14.4) but is a portability/lint tripwire for anything <3.14.
2. Parameter name `_get_oldest_job_info(prefixed_queue_name)` contradicts its only caller, which passes the *raw* queue name (`get_queue_status:167`, deliberate per comment :159-161). The cluster-1 mutants all mutate this exact call, so a call-arg test pins which convention wins.
3. Settings enforce `ge=1` on both worker counts, so `workers` is never 0 except DLQ table entries — basis for cluster 15 equivalence.

## Drafted tests (highest-value TEST-GAP clusters: 1+17, 3+5+7+8, 10+11, 12+13+14, 16, 21+23, 25)

All drafts target `backend/tests/unit/services/test_queue_status_service.py`, following its existing style (class-scoped fixtures, `@pytest.mark.asyncio`, `AsyncMock`). Add `DLQ_ANALYSIS_QUEUE` to the constants import (:23-27) — currently absent, and its absence *is* part of why cluster 10/12 survived.

`// UNVERIFIED - not yet run red/green.` TDD procedure for every test below: run against mutant build → assert fails (value/exception differs per the cluster diffs); run against original → passes. Prove each by `uv run pytest backend/tests/unit/services/test_queue_status_service.py -k <test_name>` against a manually applied mutant diff before adoption.

### Draft A — worker table, fallback and running formula (kills clusters 12, 13, 14 → keys worker 4,7,9,10,12,18,20)

```python
    @pytest.mark.asyncio
    async def test_worker_info_exact_contracts(self, service: QueueStatusService) -> None:
        """Pin worker counts for every queue class incl. DLQ_ANALYSIS and the unknown-queue fallback."""
        # UNVERIFIED - not yet run red/green
        from backend.core.config import get_settings

        settings = get_settings()
        for queue, expected in (
            (DETECTION_QUEUE, settings.detection_worker_count),
            (ANALYSIS_QUEUE, settings.analysis_worker_count),
            (DLQ_DETECTION_QUEUE, 0),
            (DLQ_ANALYSIS_QUEUE, 0),  # was never exercised by any test
        ):
            workers, running = await service._get_worker_info(queue)
            assert workers == expected
            assert running == (1 if expected > 0 else 0)

        # Unknown queues fall back to exactly one worker, running 1
        assert await service._get_worker_info("custom_queue") == (1, 1)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("configured", [1, 3])
    async def test_worker_running_estimate_is_capped_at_one(
        self, service: QueueStatusService, monkeypatch: pytest.MonkeyPatch, configured: int
    ) -> None:
        """running = min(workers, 1) for any workers > 0 — incl. the workers == 1 boundary.

        Kills min(workers, 2) (needs workers >= 2) and `workers > 1` (needs workers == 1).
        """
        # UNVERIFIED - not yet run red/green
        from types import SimpleNamespace

        import backend.core.config as config_module

        monkeypatch.setattr(
            config_module,
            "get_settings",
            lambda: SimpleNamespace(
                detection_worker_count=configured, analysis_worker_count=configured
            ),
        )
        assert await service._get_worker_info(DETECTION_QUEUE) == (configured, 1)
```

TDD: m12 fails both (running 0); m18 fails at configured=3 (2≠1); m20 fails at configured=1 (0≠1); m4 fails on DLQ_ANALYSIS; m7/m9 raise TypeError, m10 returns (2,1) on the fallback assert.

### Draft B — throughput table + fallback (kills clusters 10, 11 → throughput 2,3,4,5,8,9,12,14,15,16)

```python
    @pytest.mark.asyncio
    async def test_throughput_metrics_pinned_values(self, service: QueueStatusService) -> None:
        """The static default-throughput table is the /api/queues contract — pin every entry."""
        # UNVERIFIED - not yet run red/green
        expected = {
            DETECTION_QUEUE: (10.0, 2.5),
            ANALYSIS_QUEUE: (5.0, 8.0),
            DLQ_DETECTION_QUEUE: (0.0, 0.0),
            DLQ_ANALYSIS_QUEUE: (0.0, 0.0),
            "custom_queue": (0.0, 0.0),  # unconfigured queues fall back to zeros
        }
        for queue, (jpm, avg) in expected.items():
            throughput = await service._get_throughput_metrics(queue)
            assert throughput.jobs_per_minute == jpm, queue
            assert throughput.avg_processing_seconds == avg, queue
```

TDD: table nudges fail their row (and DLQ_ANALYSIS fails the previously-unimported row); None/dropped default raises TypeError on `custom_queue`; (1.0,·) fallbacks fail its zeros.

### Draft C — oldest-job identity + timestamp handling (kills clusters 3, 5, 7, 8 → oldest 20,21,22,34,35,36,53,57,60)

```python
    @pytest.mark.asyncio
    async def test_oldest_job_prefers_id_key_and_exposes_queued_at(self, service: QueueStatusService) -> None:
        """"id" wins the job_id chain and queued_at surfaces the parsed timestamp."""
        # UNVERIFIED - not yet run red/green
        ts = datetime.now(UTC).isoformat()
        service._redis.peek_queue.return_value = [
            {"id": "job-1", "batch_id": "b-1", "file_path": "/a.jpg", "timestamp": ts}
        ]

        info = await service._get_oldest_job_info("test_queue")

        assert info is not None
        assert info.id == "job-1"  # kills mutated first term -> falls through/None
        assert info.queued_at is not None  # kills queued_at=None / dropped kwarg

    @pytest.mark.asyncio
    async def test_oldest_job_falls_back_to_queued_at_key(self, service: QueueStatusService) -> None:
        """A job carrying only "queued_at" must still compute wait time."""
        # UNVERIFIED - not yet run red/green
        ts = (datetime.now(UTC) - timedelta(seconds=400)).isoformat()
        service._redis.peek_queue.return_value = [{"file_path": "/a.jpg", "queued_at": ts}]

        info = await service._get_oldest_job_info("test_queue")

        assert info is not None
        assert info.wait_seconds >= 395  # kills broken queued_at fallback -> 0.0

    @pytest.mark.asyncio
    async def test_oldest_job_assumes_utc_for_naive_timestamp(self, service: QueueStatusService) -> None:
        """Naive timestamps are treated as UTC instead of blowing up into info=None."""
        # UNVERIFIED - not yet run red/green
        ts = (datetime.now(UTC) - timedelta(seconds=400)).replace(tzinfo=None).isoformat()
        service._redis.peek_queue.return_value = [{"file_path": "/a.jpg", "timestamp": ts}]

        info = await service._get_oldest_job_info("test_queue")

        assert info is not None  # flipped tz branch -> TypeError swallowed -> None
        assert info.wait_seconds >= 395
```

### Draft D — get_queue_status redis/threshold wiring through the mock (kills clusters 1, 17 → oldest 2,3,4,5,6,8,9 + qstatus 7,9,14,21)

```python
    @pytest.mark.asyncio
    async def test_get_queue_status_queries_redis_with_raw_queue_name(
        self, service: QueueStatusService, mock_redis: AsyncMock
    ) -> None:
        """Depth + peek must be requested for the raw queue name with the first-item slice.

        Mocks answer any arguments, so assert the call shape itself — this pins the
        "workers use unprefixed queue names" contract at get_queue_status.
        """
        # UNVERIFIED - not yet run red/green
        mock_redis.peek_queue.return_value = [{"id": "job-1"}]

        status = await service.get_queue_status(DETECTION_QUEUE)

        mock_redis.get_queue_length.assert_called_once_with(DETECTION_QUEUE)
        mock_redis.peek_queue.assert_called_once_with(DETECTION_QUEUE, start=0, end=0)
        # throughput must be looked up under the real queue name, not None
        assert status.throughput.jobs_per_minute == 10.0
        assert status.throughput.avg_processing_seconds == 2.5

    @pytest.mark.asyncio
    async def test_get_queue_status_dlq_depth_uses_dlq_thresholds(
        self, service: QueueStatusService, mock_redis: AsyncMock
    ) -> None:
        """Depth 20: WARNING under dlq thresholds (warning=10), HEALTHY under defaults (warning=50).

        Proves calculate_health receives the display name, not None.
        """
        # UNVERIFIED - not yet run red/green
        mock_redis.get_queue_length.return_value = 20
        mock_redis.peek_queue.return_value = []

        status = await service.get_queue_status(DLQ_DETECTION_QUEUE)

        assert status.status == QueueHealthStatus.WARNING
```

TDD: every cluster-1 key changes the recorded `peek_queue` call (or, for name-drops, breaks the service itself); `qstatus` 7/9 fail the call asserts, 14 fails the DLQ threshold assert, 21 fails the throughput pin. (Cluster 2's `start`-drop is real-semantics-equivalent but is incidentally killed here too.)

### Draft E — degraded error-path status (kills clusters 21, 23 → gallq 16,17,18,19,34,35,36,41,42)

```python
    @pytest.mark.asyncio
    async def test_all_queues_error_statuses_are_degraded_and_named(
        self, service: QueueStatusService, mock_redis: AsyncMock
    ) -> None:
        """When every queue lookup fails, each degraded status must carry display name + zero metrics."""
        # UNVERIFIED - not yet run red/green
        mock_redis.get_queue_length.side_effect = Exception("Redis down")
        mock_redis.peek_queue.return_value = []

        statuses = await service.get_all_queues_status()

        assert [s.name for s in statuses] == ["detection", "ai_analysis", "dlq", "dlq"]
        for s in statuses:
            assert s.status == QueueHealthStatus.CRITICAL
            assert s.depth == 0
            assert s.running == 0
            assert s.workers == 0
            assert s.throughput.jobs_per_minute == 0.0
            assert s.throughput.avg_processing_seconds == 0.0
            assert s.oldest_job is None
```

TDD: each 0→1 nudge trips its assert; the None display-name mutants raise a pydantic ValidationError inside the except handler (test errors out = killed); the raw-name mutant fails the names list.

### Draft F — display-name fallback + singleton wiring (kills clusters 16, 25 → qstatus 3,4,5 + x_get_queue_status_service 3)

```python
    @pytest.mark.asyncio
    async def test_get_queue_status_unmapped_queue_falls_back_to_raw_name(
        self, service: QueueStatusService, mock_redis: AsyncMock
    ) -> None:
        """An unmapped queue keeps its raw name instead of None (and gets default metrics)."""
        # UNVERIFIED - not yet run red/green
        status = await service.get_queue_status("custom_queue")

        assert status.name == "custom_queue"  # None default -> pydantic ValidationError = killed
        assert status.throughput.jobs_per_minute == 0.0
        assert status.workers == 1
```

```python
class TestSingleton:  # additions inside the existing class (autouse reset_singleton applies)

    def test_singleton_stores_the_redis_client(self) -> None:
        """The factory must wire the passed redis client into the service."""
        # UNVERIFIED - not yet run red/green
        mock_redis = AsyncMock()

        service = get_queue_status_service(mock_redis)

        assert service._redis is mock_redis  # QueueStatusService(None) mutant -> None is not mock
```

## Drafted-test kill coverage

| Draft | Keys killed | Count |
|---|---|---|
| A | worker 4,7,9,10,12,18,20 | 7 |
| B | throughput 2,3,4,5,8,9,12,14,15,16 | 10 |
| C | oldest 20,21,22,34,35,36,53,57,60 | 9 |
| D | oldest 2,3,4,5,6,8,9 + qstatus 7,9,14,21 | 11 |
| E | gallq 16,17,18,19,34,35,36,41,42 | 9 |
| F | qstatus 3,4,5 + factory 3 | 4 |
| **Total** | | **50 = TEST-GAP total** |

Leftovers (19): 12 EQUIVALENT + 7 LOW-VALUE, by design.
