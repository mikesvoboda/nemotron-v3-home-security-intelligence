# WP4.4 Triage Dossier — backend/services/file_service.py

**Survivors: 100 / 225 checked keys** (`mutants/backend/services/file_service.py.meta`, exit_code 0).
Diffs captured via `uv run mutmut show` (all 100, clean, no fallback needed) — working copy at `/tmp/wp25/wp44-triage/file_diffs.txt`.

Covering test files:

- `backend/tests/unit/services/test_file_service.py` (classes: TestFileDeletionJob L26, TestFileServiceScheduleDeletion L99, TestFileServiceCancelDeletion L214, TestFileServiceProcessQueue L278, TestFileServiceDeleteFile L352, TestFileServiceSingleton L383, TestFileServiceBackgroundWorker L404, TestFileServiceGetters L452)
- `backend/tests/unit/services/test_event_service.py` (TestFileServiceImmediateDeletion L425) — the only coverage for `delete_files_immediately`
- `backend/tests/unit/routes/test_restore_endpoints.py::TestRestoreEvent::test_restore_deleted_event_success` — indirect caller of `cancel_deletion_by_event_id` / singleton (route-level only)

**Root cause of the whole TEST-GAP block:** every `mock_redis` fixture uses bare `AsyncMock`s, so ANY arguments (None keys, dropped args, wrong offsets) are accepted silently. The tests call `assert_called_once()` / `call_count` but almost never `assert_called_once_with(...)`. The one place that DOES assert args (`test_get_queue_size`, L472: `zcard.assert_called_once_with(FILE_DELETION_QUEUE)`) has zero survivors — proof the fix works.

## Cluster table (counts sum to 100)

| #   | Pattern                                                                                                                                                                                                                                         | Count | Classification | Example keys (≤3)                                                                               |
| --- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----- | -------------- | ----------------------------------------------------------------------------------------------- |
| 1   | Logger message text clobbered (`logger.X(str)` → `None` / `"XX…XX"` / case flips) in schedule_deletion, cancel_deletion, cancel_deletion_by_event_id, process_deletion_queue, delete_file, delete_files_immediately, start, stop                | 32    | EQUIVALENT     | schedule_deletion\_\_4, cancel_deletion\_\_20, stop\_\_6                                        |
| 2   | Comparison operator mutated on **log-guard** `if` clauses (`cancelled_count > 0`→`>=0`/`>1`, `jobs_processed > 0`→`>=0`/`>1`, `files_deleted > 0 or files_failed > 0`→`and`/`>=0`/`>1`) — only gate a logger.info line, return values untouched | 9     | EQUIVALENT     | cancel_deletion_by_event_id\_\_31, process_deletion_queue\_\_36, delete_files_immediately\_\_15 |
| 3   | **`redis.zrange(FILE_DELETION_QUEUE, 0, -1)` argument mutation** (key→None, offsets→None/1/+1/-2, args dropped) in cancel_deletion, cancel_deletion_by_event_id, get_pending_jobs_for_event                                                     | 27    | TEST-GAP       | cancel_deletion\_\_4, cancel_deletion_by_event_id\_\_15, get_pending_jobs_for_event\_\_12       |
| 4   | **`redis.zrem(FILE_DELETION_QUEUE, job_json)` argument mutation** (key→None, member→None, arg dropped) in cancel_deletion, cancel_deletion_by_event_id, process_deletion_queue                                                                  | 12    | TEST-GAP       | cancel_deletion\_\_17, cancel_deletion_by_event_id\_\_23, process_deletion_queue\_\_29          |
| 5   | **`redis.zrangebyscore(...)` argument mutation + `current_time = time.time()`→None** in process_deletion_queue (key/min/max/start/num clobbered, `"-inf"`→`"-INF"`/`"XX-infXX"`, `start=1`)                                                     | 14    | TEST-GAP       | process_deletion_queue\_\_3, process_deletion_queue\_\_9, process_deletion_queue\_\_17          |
| 6   | `cancel_deletion_by_event_id`: redis-unavailable path `return 0` → `return 1` — caller sees "1 job cancelled" when nothing was                                                                                                                  | 1     | TEST-GAP       | cancel_deletion_by_event_id\_\_7                                                                |
| 7   | `process_deletion_queue`: `jobs_processed += 1` → `jobs_processed = 1` — batch count collapses to 1 with ≥2 due jobs (return value is consumed by background worker/callers)                                                                    | 1     | TEST-GAP       | process_deletion_queue\_\_32                                                                    |
| 8   | `start`: `asyncio.create_task(…, name="file-service-worker")` name clobbered/dropped (NEM-5057 diagnostic name; behaviorally inert)                                                                                                             | 4     | LOW-VALUE      | start\_\_9, start\_\_11, start\_\_12                                                            |

**Totals: EQUIVALENT 41, TEST-GAP 55, LOW-VALUE 4 = 100.**

### Cluster notes

- **Cluster 1 (EQUIVALENT):** log message content only; no control flow, no return value, no call arguments. Not worth asserting.
- **Cluster 2 (EQUIVALENT):** the mutated comparisons wrap only `logger.info(...)`; the function still returns the same tuple/int. A log-noise behavior change nobody should pin. (If a log-assertion convention ever lands in this repo these become killable for free, but that's out of scope.)
- **Cluster 3 (TEST-GAP):** against real Redis these change which jobs are scanned: key=None or dropped key raises TypeError → cancel/get returns nothing; `0,-2` drops the last queued job, `1,-1` drops the first (a delete never gets cancelled → the file is destroyed after an event restore). Tests run the line (they set `zrange.return_value`) but assert only the boolean/count result — the mock answers regardless of arguments. Kill: `zrange.assert_called_once_with(FILE_DELETION_QUEUE, 0, -1)` per method. Note `get_pending_jobs_for_event` also survives the same 9 because `test_get_pending_jobs_for_event` (L475) never checks zrange args.
- **Cluster 4 (TEST-GAP):** key→None / member→None / dropped member means real Redis deletes the wrong member or errors → the deletion job stays queued (file destroyed despite restore) or `zrem(FILE_DELETION_QUEUE)` raises. Tests assert `zrem.assert_called_once()` / `call_count == 2` — count only, never the payload. Kill: `zrem.assert_called_once_with(FILE_DELETION_QUEUE, job.to_json())`.
- **Cluster 5 (TEST-GAP):** the score window IS the due-job semantics. `current_time=None` or max dropped: with real redis-py, max=None raises (or with `-inf→"XX-infXX"`, ResponseError) — worker dies every poll; `num` dropped = unbounded batch (the DEFAULT_BATCH_SIZE=100 contract silently gone); `start=1` skips the oldest due job forever (starvation). `test_process_queue_with_due_jobs` (L304) stubs `zrangebyscore.return_value` and never inspects the call. Kill: `zrangebyscore.assert_called_once_with(FILE_DELETION_QUEUE, "-inf", FROZEN_NOW, start=0, num=N)`. (`"-INF"` itself would still work on real Redis — case-insensitive double parse — but dies to the same exactness assertion.)
- **Cluster 6 (TEST-GAP):** no test exercises the redis-unavailable branch of `cancel_deletion_by_event_id` at all (`schedule_deletion` has `test_schedule_deletion_no_redis` L173, this one has none). The restore endpoint uses the return count; a phantom `1` is a lie to callers/UI.
- **Cluster 7 (TEST-GAP):** `jobs_processed = 1` vs `+= 1` is invisible while every test feeds exactly ONE due job. With two, the worker under-reports and the `if jobs_processed > 0` log/metrics lie. Kill: two due jobs, assert `jobs_processed == 2`.
- **Cluster 8 (LOW-VALUE):** task name is a debugging convenience per NEM-5057; nothing consumes it. If cheap kill desired anyway: one line in `test_start_stop_background_worker` (L416): `assert service._task.get_name() == "file-service-worker"`. Not drafted as a test below.

## Drafted tests (UNVERIFIED — not yet run red/green)

Target file for D1–D3, D5–D7: `backend/tests/unit/services/test_file_service.py`.
TDD procedure for each: add test → run it against the mutant copy (`mutants/backend/services/file_service.py`) → assert fails (red) → run against `backend/services/file_service.py` → passes (green).

### D1 — kills Cluster 3, cancel_deletion (keys 4–12); append to `TestFileServiceCancelDeletion`

```python
    @pytest.mark.asyncio
    async def test_cancel_deletion_scans_full_queue_with_canonical_key(
        self, mock_redis: MagicMock
    ) -> None:
        """zrange must be (FILE_DELETION_QUEUE, 0, -1) — a wrong key or offset
        silently skips jobs and leaves a scheduled deletion armed."""
        job = FileDeletionJob(file_paths=["/tmp/test.jpg"], event_id=123, job_id="target-id")
        mock_redis.zrange.return_value = [job.to_json()]

        service = FileService(redis_client=mock_redis)
        assert await service.cancel_deletion("target-id") is True

        mock_redis.zrange.assert_called_once_with(FILE_DELETION_QUEUE, 0, -1)
```

### D2 — kills Cluster 3, cancel_deletion_by_event_id (keys 9–17) + Cluster 6 (key 7); same class

```python
    @pytest.mark.asyncio
    async def test_cancel_deletion_by_event_id_scans_full_queue_with_canonical_key(
        self, mock_redis: MagicMock
    ) -> None:
        """Kill zrange argument mutants: full range under the canonical key."""
        job = FileDeletionJob(file_paths=["/tmp/a.jpg"], event_id=123, job_id="job1")
        mock_redis.zrange.return_value = [job.to_json()]

        service = FileService(redis_client=mock_redis)
        assert await service.cancel_deletion_by_event_id(123) == 1

        mock_redis.zrange.assert_called_once_with(FILE_DELETION_QUEUE, 0, -1)

    @pytest.mark.asyncio
    async def test_cancel_deletion_by_event_id_no_redis_returns_zero(self) -> None:
        """Redis unavailable must report 0 cancelled — never a phantom count."""
        service = FileService(redis_client=None)

        with patch(
            "backend.services.file_service.get_redis_client_sync", return_value=None, autospec=True
        ):
            count = await service.cancel_deletion_by_event_id(123)

        assert count == 0
```

### D3 — kills Cluster 3, get_pending_jobs_for_event (keys 4–12); append to `TestFileServiceGetters`

```python
    @pytest.mark.asyncio
    async def test_get_pending_jobs_for_event_scans_full_queue_with_canonical_key(
        self, mock_redis: MagicMock
    ) -> None:
        """Full-range read under the canonical key, else pending jobs go unseen."""
        job = FileDeletionJob(file_paths=["/tmp/a.jpg"], event_id=123, job_id="job1")
        mock_redis.zrange.return_value = [job.to_json()]

        service = FileService(redis_client=mock_redis)
        assert len(await service.get_pending_jobs_for_event(123)) == 1

        mock_redis.zrange.assert_called_once_with(FILE_DELETION_QUEUE, 0, -1)
```

### D4 — kills Cluster 4, zrem at all three call sites (keys: cancel_deletion 16–19, cancel_deletion_by_event_id 23–26, process_deletion_queue 28–31); D4a/D4b appended to `TestFileServiceCancelDeletion`, D4c to `TestFileServiceProcessQueue`

```python
    @pytest.mark.asyncio
    async def test_cancel_deletion_removes_exact_queued_payload(self, mock_redis: MagicMock) -> None:
        """zrem must get (key, the exact job JSON) — anything else leaves the
        deletion queued against real Redis even though we returned True."""
        job = FileDeletionJob(file_paths=["/tmp/test.jpg"], event_id=123, job_id="target-id")
        payload = job.to_json()
        mock_redis.zrange.return_value = [payload]

        service = FileService(redis_client=mock_redis)
        assert await service.cancel_deletion("target-id") is True

        mock_redis.zrem.assert_called_once_with(FILE_DELETION_QUEUE, payload)

    @pytest.mark.asyncio
    async def test_cancel_deletion_by_event_id_removes_exact_queued_payloads(
        self, mock_redis: MagicMock
    ) -> None:
        """Every removed member must be the matching job JSON under the right key."""
        job1 = FileDeletionJob(file_paths=["/tmp/a.jpg"], event_id=123, job_id="job1")
        job2 = FileDeletionJob(file_paths=["/tmp/b.jpg"], event_id=123, job_id="job2")
        job3 = FileDeletionJob(file_paths=["/tmp/c.jpg"], event_id=456, job_id="job3")
        mock_redis.zrange.return_value = [job1.to_json(), job2.to_json(), job3.to_json()]

        service = FileService(redis_client=mock_redis)
        assert await service.cancel_deletion_by_event_id(123) == 2

        expected = {
            call(FILE_DELETION_QUEUE, job1.to_json()),
            call(FILE_DELETION_QUEUE, job2.to_json()),
        }
        assert set(mock_redis.zrem.call_args_list) == expected
```

(D4c: add the one-line strengthening to the existing `test_process_queue_with_due_jobs` at test_file_service.py:325 — replace `mock_redis.zrem.assert_called_once()` with `mock_redis.zrem.assert_called_once_with(FILE_DELETION_QUEUE, job.to_json())`. Needs `from unittest.mock import call` import added at line 13 for D4b.)

### D5 — kills Cluster 5, zrangebyscore arguments + frozen now (keys 3, 5–17); append to `TestFileServiceProcessQueue`

```python
    @pytest.mark.asyncio
    async def test_process_deletion_queue_queries_due_jobs_with_score_bounds(
        self, mock_redis: MagicMock
    ) -> None:
        """Due-window contract: (queue, '-inf', now, start=0, num=batch_size).

        Kills mutants that pass None as the upper bound (worker dies or grabs
        not-yet-due jobs), drop start/num (unbounded batch, oldest job skipped),
        or mangle the key / '-inf' sentinel.
        """
        fixed_now = 1_700_000_000.0

        with patch("backend.services.file_service.time.time", return_value=fixed_now):
            service = FileService(redis_client=mock_redis)
            await service.process_deletion_queue(batch_size=7)

        mock_redis.zrangebyscore.assert_called_once_with(
            FILE_DELETION_QUEUE, "-inf", fixed_now, start=0, num=7
        )
```

### D6 — kills Cluster 7, `jobs_processed = 1` (key 32); append to `TestFileServiceProcessQueue`

```python
    @pytest.mark.asyncio
    async def test_process_deletion_queue_counts_each_processed_job(self, mock_redis: MagicMock) -> None:
        """Two due jobs must report jobs_processed == 2, not a collapsed 1."""
        with (
            tempfile.NamedTemporaryFile(delete=False) as f1,
            tempfile.NamedTemporaryFile(delete=False) as f2,
            tempfile.NamedTemporaryFile(delete=False) as f3,
        ):
            p1, p2, p3 = f1.name, f2.name, f3.name

        try:
            job_a = FileDeletionJob(file_paths=[p1, p2], event_id=1, job_id="a")
            job_b = FileDeletionJob(file_paths=[p3], event_id=2, job_id="b")
            mock_redis.zrangebyscore.return_value = [job_a.to_json(), job_b.to_json()]

            service = FileService(redis_client=mock_redis)
            jobs_processed, files_deleted = await service.process_deletion_queue()

            assert jobs_processed == 2
            assert files_deleted == 3
            assert mock_redis.zrem.call_count == 2
        finally:
            for p in (p1, p2, p3):
                Path(p).unlink(missing_ok=True)
```

### Kill accounting for drafted tests

| Draft   | Cluster killed      | Mutant keys                                           | Count |
| ------- | ------------------- | ----------------------------------------------------- | ----- |
| D1      | 3 (cancel_deletion) | cancel_deletion\_\_4–12                               | 9     |
| D2      | 3 (cbei) + 6        | cancel_deletion_by_event_id\_\_9–17, \_\_7            | 10    |
| D3      | 3 (gpjfe)           | get_pending_jobs_for_event\_\_4–12                    | 9     |
| D4a/b/c | 4                   | cancel_deletion\_\_16–19, cbei\_\_23–26, pdq\_\_28–31 | 12    |
| D5      | 5                   | process_deletion_queue\_\_3, \_\_5–17                 | 14    |
| D6      | 7                   | process_deletion_queue\_\_32                          | 1     |

Potential kills: 55 (all TEST-GAP survivors). Clusters 1–2 (EQUIVALENT) and 8 (LOW-VALUE, optional one-liner) intentionally left surviving.

// UNVERIFIED — drafted against disk state 2026-09-17 (commit 99829f9c), no tests executed per WP4.3 run constraints.
