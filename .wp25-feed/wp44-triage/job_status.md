# WP4.4 Triage Dossier — backend/services/job_status.py

- **Run data:** `mutants/backend/services/job_status.py.meta` — 498 keys: 186 killed, **138 survived**, 174 still `null` (live run in progress; this dossier covers only the 138 judged survivors).
- **Covering test file (ALL drafts target this):** `/agents/agent-nemo2/workspace/backend/tests/unit/services/test_job_status.py` (1331 lines, class-based, `mock_redis` = all-`AsyncMock` fixture at L32-46, real `JobStatusService` fixture at L49-52).
- **Diffs captured:** `/tmp/wp25/wp44-triage/diffs_job_status.txt` (all 138 via `uv run mutmut show`; one key — `update_progress__mutmut_42` — hit a JSONDecodeError on the concurrently-written meta and was recovered by manual diff of `mutants/backend/services/job_status.py`: it drops `extra=` from the debug call).
- **Why so many survive:** the fixture's `AsyncMock` Redis returns `return_value` **regardless of arguments**, so every mutant that swaps a key/job-id/arg to `None` runs to completion — the payload assertions on `set.call_args[0][1]` still pass because the payload is untouched. And the tests assert stored _payload_ fields selectively (`status`, `progress`, `result`, `completed_at`) while never asserting `message`, timestamps' tz-awareness, or the _arguments_ to `get`/`set`/`zadd`/`zrangebyscore` (except in `TestJobStatusServiceRegistry`, L859-892, and `test_start_job_stores_metadata` L194-208 — the precedent to copy).

## Cluster table (counts sum to 138)

| #   | Cluster (pattern × concern)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               | Count | Class        | Example keys (≤3)                                                                                                                     | Kill site in covering test file                                                                   |
| --- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----- | ------------ | ------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| A   | `JobMetadata.from_dict`: each optional field expression collapses to `None` — either the value is replaced by literal `None` or its `data.get("key")` / `parse_datetime(...)` argument is replaced by `None`/junk key (`"XXerrorXX"`, `"ERROR"`, `data.get(None)`) so the lookup silently yields `None`. Fields hit: `message`(4), `created_at`(1), `started_at`(5), `completed_at`(5), `error`(4). Test `test_metadata_from_dict` (L136-158) round-trips all-non-default data but asserts only `job_id/job_type/status/progress/result/extra` — never `message`, timestamps, or `error`. | 19    | **TEST-GAP** | `...JobMetadata.from_dict__mutmut_7` (`message=None`), `_35` (`data.get("XXmessageXX")`), `_44` (`completed_at=parse_datetime(None)`) | L152-158                                                                                          |
| B   | Lifecycle methods address Redis with a `None`-mangled key — `key = self._get_job_key(job_id)` → `key = None` / `_get_job_key(None)` (→ `"job:None:status"`), or the call arg `get(key)`/`set(key,...)` → `get(None)`/`set(None,...)`. AsyncMock hides it; in prod every read hits the wrong key (KeyError / silent data loss). Spread: `get_job_status` ×3, `update_progress` ×4, `complete_job` ×4, `fail_job` ×4, `list_jobs` ×3.                                                                                                                                                       | 18    | **TEST-GAP** | `get_job_status__mutmut_1`, `complete_job__mutmut_4`, `list_jobs__mutmut_17`                                                          | L346-349, L381-383 (`set.call_args` used but `call_args[0][0]` never checked; precedent L205-208) |
| C   | `_add_to_completed_registry(job_id)` → `_add_to_completed_registry(None)`: wrong _member_ inserted into `jobs:completed` sorted set. `test_*_moves_to_completed_registry` (L799-856) asserts only that `JOBS_COMPLETED_KEY` appears as the _first positional_ (the key), never the member mapping.                                                                                                                                                                                                                                                                                        | 2     | **TEST-GAP** | `complete_job__mutmut_36`, `fail_job__mutmut_29`                                                                                      | L824-826                                                                                          |
| D   | `datetime.now(UTC)` → `datetime.now(None)` — naive local timestamps written to `completed_at`/`started_at` (breaks every consumer parsing tz-aware ISO strings). Tests assert only `is not None` (L387, L461, L350).                                                                                                                                                                                                                                                                                                                                                                      | 3     | **TEST-GAP** | `complete_job__mutmut_8`, `fail_job__mutmut_8`, `update_progress__mutmut_36`                                                          | L387, L461, L350                                                                                  |
| E   | `update_progress` message storage broken: guard flipped (`if message is None`), value clobbered (`data["message"] = None`), or stored under wrong dict key (`"XXmessageXX"`/`"MESSAGE"`). No test asserts the stored `message` at all.                                                                                                                                                                                                                                                                                                                                                    | 4     | **TEST-GAP** | `update_progress__mutmut_21`, `_22`, `_23`                                                                                            | L340-350 (message passed, never asserted)                                                         |
| F1  | `complete_job` stored `data["message"] = "Completed successfully"` dropped (`= None`) or re-keyed (`"XXmessageXX"`, `"MESSAGE"`) — user-visible status string lost from Redis.                                                                                                                                                                                                                                                                                                                                                                                                            | 3     | **TEST-GAP** | `complete_job__mutmut_23`, `_24`, `_25`                                                                                               | L381-387                                                                                          |
| F2  | `complete_job` message _copy_ variants (`"XXCompleted successfullyXX"`, lower/upper case) — real change to stored string but pinning UI copy in unit tests is brittle on its own; dies for free with F1's equality assert.                                                                                                                                                                                                                                                                                                                                                                | 3     | LOW-VALUE    | `complete_job__mutmut_26`, `_27`, `_28`                                                                                               | — (killed by F1 draft anyway)                                                                     |
| G   | `fail_job` stored `data["message"] = f"Failed: {error}"` dropped or re-keyed — failure context lost for API consumers.                                                                                                                                                                                                                                                                                                                                                                                                                                                                    | 3     | **TEST-GAP** | `fail_job__mutmut_19`, `_20`, `_21`                                                                                                   | L456-461                                                                                          |
| H   | Log **message text** mutants only (`logger.X("text"...)` → `None` / case flips / `XX`-wrap): formatting output changes, zero control-flow effect. Spread: `update_progress` ×4, `complete_job` ×4, `fail_job` ×4, `get_job_status` ×4, `cleanup_completed_jobs` ×4, `cleanup_stale_active_jobs` ×4.                                                                                                                                                                                                                                                                                       | 24    | EQUIVALENT   | `cleanup_completed_jobs__mutmut_14`, `fail_job__mutmut_34`, `get_job_status__mutmut_12`                                               | n/a                                                                                               |
| I   | Log `extra=` **payload** mutants (`extra=None`, extra arg dropped, structured keys renamed to `"XXjob_idXX"`/`"JOB_TYPE"`, value → `str(None)`): structured-log fields lost, return values and stored state identical. 6 functions (incl. `update_progress__mutmut_42`, recovered manually).                                                                                                                                                                                                                                                                                              | 39    | LOW-VALUE    | `complete_job__mutmut_38`, `fail_job__mutmut_43`, `update_progress__mutmut_48`                                                        | n/a — nobody asserts `record.<extra key>` in this module's tests                                  |
| J   | Cleanup log gates `if removed > 0:` → `>= 0` / `> 1`: only changes whether the info/warning line fires at the boundary.                                                                                                                                                                                                                                                                                                                                                                                                                                                                   | 4     | LOW-VALUE    | `cleanup_completed_jobs__mutmut_12`, `cleanup_stale_active_jobs__mutmut_13`                                                           | n/a                                                                                               |
| L   | `list_jobs` `zrangebyscore` query-argument mutants: set-key → `None`, `"-inf"`/`"+inf"` → `None`/case/`XX` variants, args dropped. AsyncMock returns its canned list regardless; real Redis would error or return the wrong window. Tests never assert this call's args (unlike `get_active_job_ids` at L868).                                                                                                                                                                                                                                                                            | 10    | **TEST-GAP** | `list_jobs__mutmut_2`, `_3`, `_9`                                                                                                     | L595-596                                                                                          |
| L2  | `list_jobs` status filter `continue` → `break` (backend/services/job_status.py:664): a non-matching job **stops the scan** instead of skipping it. `test_list_jobs_filters_by_status` (L604-643) happens to place the non-matching job last, so original and mutant return the same list — order-dependent blind spot.                                                                                                                                                                                                                                                                    | 1     | **TEST-GAP** | `list_jobs__mutmut_26`                                                                                                                | L608 (ID order)                                                                                   |
| M   | Registry getters' default `limit: int = 100` → `101`: only observable when a caller omits `limit` and >100 ids exist; both tests pass explicit limits.                                                                                                                                                                                                                                                                                                                                                                                                                                    | 2     | TEST-GAP     | `get_active_job_ids__mutmut_1`, `get_completed_job_ids__mutmut_1`                                                                     | L865-889                                                                                          |
| N   | `return job_ids[:limit] if job_ids else []` → `if (job_ids) or True else []`: `[][limit-none]` of an empty list is still `[]`, and redis-py never returns `None` — semantically identical.                                                                                                                                                                                                                                                                                                                                                                                                | 2     | EQUIVALENT   | `get_active_job_ids__mutmut_14`, `get_completed_job_ids__mutmut_14`                                                                   | n/a                                                                                               |
| O   | Singleton factory `get_job_status_service(redis_client)` → `JobStatusService(None)` (job_status.py:717): the service is built with no Redis. Tests assert only instance identity/cycling.                                                                                                                                                                                                                                                                                                                                                                                                 | 1     | **TEST-GAP** | `backend.services.job_status.x_get_job_status_service__mutmut_3`                                                                      | L712-723                                                                                          |

**Totals: 138 = TEST-GAP 66 (A19+B18+C2+D3+E4+F1 3+G3+L10+L2 1+M2+O1) + LOW-VALUE 46 (F2 3 + I 39 + J 4) + EQUIVALENT 26 (H 24 + N 2).**

## Drafted tests (append to `backend/tests/unit/services/test_job_status.py`)

All UNVERIFIED — TDD procedure for each: add the test, run it against the mutant (expect **red** on the exact assert below), then against `backend/services/job_status.py` original (expect **green**). `asyncio_mode=auto` is set in pyproject, but the file's house style keeps explicit `@pytest.mark.asyncio` — drafts follow the file.

### Draft 1 — kills cluster A (19 mutants)

```python
class TestJobMetadataRoundTrip:
    """Field-level round-trip (WP4.4: from_dict field-collapse mutants)."""

    def test_from_dict_restores_every_serialized_field(self) -> None:
        """Every field written by to_dict must survive from_dict unchanged."""
        now = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
        later = datetime(2026, 1, 2, 4, 5, 6, tzinfo=UTC)
        metadata = JobMetadata(
            job_id="job-rt",
            job_type="export",
            status=JobState.FAILED,
            progress=55,
            message="Failed: boom",
            created_at=now,
            started_at=now,
            completed_at=later,
            result={"rows": 3},
            error="boom",
            extra={"camera_id": "front_door"},
        )
        restored = JobMetadata.from_dict(metadata.to_dict())

        assert restored.job_id == "job-rt"
        assert restored.job_type == "export"
        assert restored.status == JobState.FAILED
        assert restored.progress == 55
        # The surviving mutants all zero out exactly one of these five:
        assert restored.message == "Failed: boom"          # kills _7/_34/_35/_36
        assert restored.created_at == now                  # kills _8
        assert restored.started_at == now                  # kills _9/_40/_41/_42/_43
        assert restored.completed_at == later              # kills _10/_44/_45/_46/_47
        assert restored.result == {"rows": 3}
        assert restored.error == "boom"                    # kills _12/_51/_52/_53
        assert restored.extra == {"camera_id": "front_door"}
```

### Draft 2 — kills clusters B (18), C (2), O (1)

```python
class TestRedisArgumentsUseJobId:
    """Wrong key/member identity is invisible through AsyncMock (WP4.4)."""

    @pytest.mark.asyncio
    async def test_get_job_status_reads_the_canonical_job_key(
        self, job_status_service: JobStatusService, mock_redis: AsyncMock
    ) -> None:
        """get_job_status must read exactly job:{job_id}:status."""
        mock_redis.get.return_value = None

        await job_status_service.get_job_status(job_id="job-123")

        mock_redis.get.assert_called_once_with("job:job-123:status")

    @pytest.mark.asyncio
    async def test_mutating_methods_write_the_canonical_job_key(
        self, job_status_service: JobStatusService, mock_redis: AsyncMock
    ) -> None:
        """update/complete/fail must get() and set() the canonical key, not None."""
        existing_job = {
            "job_id": "job-123",
            "job_type": "export",
            "status": "running",
            "progress": 50,
            "message": None,
            "created_at": datetime.now(UTC).isoformat(),
            "started_at": datetime.now(UTC).isoformat(),
            "completed_at": None,
            "result": None,
            "error": None,
            "extra": None,
        }
        mock_redis.get.return_value = existing_job

        await job_status_service.update_progress(job_id="job-123", progress=60, message=None)
        assert mock_redis.get.call_args[0][0] == "job:job-123:status"
        assert mock_redis.set.call_args[0][0] == "job:job-123:status"

        await job_status_service.complete_job(job_id="job-123", result=None)
        assert mock_redis.set.call_args[0][0] == "job:job-123:status"

        await job_status_service.fail_job(job_id="job-123", error="boom")
        assert mock_redis.set.call_args[0][0] == "job:job-123:status"

    @pytest.mark.asyncio
    async def test_list_jobs_fetches_each_job_under_its_canonical_key(
        self, job_status_service: JobStatusService, mock_redis: AsyncMock
    ) -> None:
        """Expired-entry sweep must look up the job's own key, not None."""
        mock_redis.zrangebyscore.return_value = ["job-1", "job-2"]
        mock_redis.get.return_value = None  # every job looks expired → sweep path

        await job_status_service.list_jobs(status_filter=None, limit=50)

        fetched_keys = [call[0][0] for call in mock_redis.get.call_args_list]
        assert fetched_keys == ["job:job-1:status", "job:job-2:status"]

    @pytest.mark.asyncio
    async def test_terminal_moves_register_the_job_id_as_sorted_set_member(
        self, job_status_service: JobStatusService, mock_redis: AsyncMock
    ) -> None:
        """The completed-registry member must be the job id, not None (cluster C)."""
        existing_job = {
            "job_id": "job-123",
            "job_type": "export",
            "status": "running",
            "progress": 50,
            "message": None,
            "created_at": datetime.now(UTC).isoformat(),
            "started_at": datetime.now(UTC).isoformat(),
            "completed_at": None,
            "result": None,
            "error": None,
            "extra": None,
        }
        mock_redis.get.return_value = existing_job

        await job_status_service.complete_job(job_id="job-123", result=None)

        members = [
            list(call[0][1].keys())
            for call in mock_redis.zadd.call_args_list
            if call[0][0] == JOBS_COMPLETED_KEY
        ]
        assert members == [["job-123"]]

    def test_singleton_stores_the_provided_redis_client(self, mock_redis: AsyncMock) -> None:
        """Cluster O: the factory must not build the service with None."""
        service = get_job_status_service(mock_redis)

        assert service._redis is mock_redis
```

### Draft 3 — kills cluster L (10)

```python
    @pytest.mark.asyncio
    async def test_list_jobs_queries_the_status_index_with_the_documented_range(
        self, job_status_service: JobStatusService, mock_redis: AsyncMock
    ) -> None:
        """zrangebyscore must be asked for (job:status:list, '-inf', '+inf')."""
        mock_redis.zrangebyscore.return_value = []

        await job_status_service.list_jobs(status_filter=None, limit=50)

        mock_redis.zrangebyscore.assert_called_once_with(JOB_STATUS_LIST_KEY, "-inf", "+inf")
```

(add as a method of `TestJobStatusServiceListJobs`; mirrors L868's precedent)

### Draft 4 — kills clusters E (4), F1 (3), G (3), and incidentally F2 (3)

```python
    @pytest.mark.asyncio
    async def test_progress_and_terminal_states_store_their_message(
        self, job_status_service: JobStatusService, mock_redis: AsyncMock
    ) -> None:
        """The human-readable message must land under the 'message' key."""
        existing_job = {
            "job_id": "job-123",
            "job_type": "export",
            "status": "running",
            "progress": 50,
            "message": None,
            "created_at": datetime.now(UTC).isoformat(),
            "started_at": datetime.now(UTC).isoformat(),
            "completed_at": None,
            "result": None,
            "error": None,
            "extra": None,
        }
        mock_redis.get.return_value = existing_job

        await job_status_service.update_progress(
            job_id="job-123", progress=60, message="Processing 60/100 items"
        )
        assert mock_redis.set.call_args[0][1]["message"] == "Processing 60/100 items"

        # A None message must not clobber the previous one (guard-flip mutant _21)
        mock_redis.get.return_value = existing_job
        await job_status_service.update_progress(job_id="job-123", progress=70, message=None)
        assert mock_redis.set.call_args[0][1]["message"] is None  # pre-existing value kept

        await job_status_service.complete_job(job_id="job-123", result=None)
        assert mock_redis.set.call_args[0][1]["message"] == "Completed successfully"

        await job_status_service.fail_job(job_id="job-123", error="boom")
        assert mock_redis.set.call_args[0][1]["message"] == "Failed: boom"
```

### Draft 5 — kills cluster D (3)

```python
    @pytest.mark.asyncio
    async def test_terminal_timestamps_written_to_redis_are_utc_aware(
        self, job_status_service: JobStatusService, mock_redis: AsyncMock
    ) -> None:
        """completed_at/started_at must be tz-aware ISO strings, not naive local time."""
        existing_job = {
            "job_id": "job-123",
            "job_type": "export",
            "status": "pending",
            "progress": 0,
            "message": None,
            "created_at": datetime.now(UTC).isoformat(),
            "started_at": None,
            "completed_at": None,
            "result": None,
            "error": None,
            "extra": None,
        }
        mock_redis.get.return_value = existing_job

        await job_status_service.update_progress(job_id="job-123", progress=1, message=None)
        started_at = mock_redis.set.call_args[0][1]["started_at"]
        assert datetime.fromisoformat(started_at).tzinfo == UTC

        await job_status_service.complete_job(job_id="job-123", result=None)
        completed_at = mock_redis.set.call_args[0][1]["completed_at"]
        assert datetime.fromisoformat(completed_at).tzinfo == UTC

        await job_status_service.fail_job(job_id="job-123", error="boom")
        completed_at = mock_redis.set.call_args[0][1]["completed_at"]
        assert datetime.fromisoformat(completed_at).tzinfo == UTC
```

### Draft 6 — kills cluster L2 (1)

```python
    @pytest.mark.asyncio
    async def test_list_jobs_filter_skips_non_matching_jobs_instead_of_stopping(
        self, job_status_service: JobStatusService, mock_redis: AsyncMock
    ) -> None:
        """A non-matching job must not end the scan (mutant turned continue into break)."""
        mock_redis.zrangebyscore.return_value = ["job-old", "job-new"]
        base = {
            "job_type": "export",
            "progress": 0,
            "message": None,
            "created_at": datetime.now(UTC).isoformat(),
            "started_at": None,
            "completed_at": None,
            "result": None,
            "error": None,
            "extra": None,
        }
        mock_redis.get.side_effect = [
            {**base, "job_id": "job-old", "status": "completed"},   # does NOT match, comes FIRST
            {**base, "job_id": "job-new", "status": "running", "progress": 40},
        ]

        jobs = await job_status_service.list_jobs(status_filter=JobState.RUNNING, limit=50)

        assert [j.job_id for j in jobs] == ["job-new"]
```

### Not drafted (documented kills)

- **Cluster M (2):** `mock_redis.zrangebyscore.return_value = [f"j{i}" for i in range(101)]`; `assert len(await service.get_active_job_ids()) == 100` (and same for `get_completed_job_ids`). One line each; deferred as marginal value.
- **Clusters H/I/J (67 log mutants):** EQUIVALENT/LOW-VALUE — do not test. If the team ever wants the cleanup log gate pinned (J), one `caplog.set_level(logging.INFO)` + `[r for r in caplog.records if r.levelno == logging.WARNING]`-style check (precedent: `backend/tests/unit/core/test_config_validation.py:281`) would kill them, but asserting log noise is out of scope for WP4.4.

## Covering-test file references

- All drafts: `/agents/agent-nemo2/workspace/backend/tests/unit/services/test_job_status.py` — fixtures L32-52; `test_metadata_from_dict` L136; `TestJobStatusServiceUpdateProgress` L211-350; `TestJobStatusServiceCompleteJob` L353-425; `TestJobStatusServiceFailJob` L428-497; `TestJobStatusServiceGetJobStatus` L500-541; `TestJobStatusServiceListJobs` L544-706; `TestJobStatusServiceSingleton` L709-723; `TestJobStatusServiceRegistry` L779-892; `TestJobStatusServiceCleanup` L1071-1217.
- Integration coverage also exists (`backend/tests/integration/test_job_status.py`) but `tests_by_mangled_function_name` attributes all surviving-mutant coverage to the unit file above.
