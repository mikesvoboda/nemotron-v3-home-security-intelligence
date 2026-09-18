# WP4.4 Triage Dossier — backend/services/job_history_service.py

**Run date:** 2026-09-17 · **Survivors:** 121 (from `mutants/backend/services/job_history_service.py.meta`, exit_code == 0)
**Method:** diffs extracted locally by parsing `mutants/backend/services/job_history_service.py` (each survivor function-copy diffed against its `__mutmut_orig` twin via `ast.get_source_segment` + `difflib`); spot-checked against `uv run mutmut show` (works). No test execution, no repo writes.
**Raw diff dump:** `/tmp/wp25/wp44-triage-work/jhs_diffs.json` (all 121 keys → unified-diff lines)

## Covering tests (from `mutants/mutmut-stats.json` tests_by_mangled_function_name)

| Function | Test file:region |
|---|---|
| `JobHistory.to_dict` | `backend/tests/unit/services/test_job_history_service.py:149` (`TestJobHistory::test_job_history_to_dict`) |
| `record_attempt_start` | `backend/tests/unit/services/test_job_history_service.py:443,461` |
| `record_attempt_end` | `backend/tests/unit/services/test_job_history_service.py:477,505` |
| `add_job_log` | `backend/tests/unit/services/test_job_history_service.py:529,549,565` + `backend/tests/unit/services/test_job_log_emitter.py:384,413` (`TestJobHistoryServiceIntegration`) |

Root cause shared by every TEST-GAP cluster: the tests use `AsyncMock(spec=AsyncSession)` and only assert **call-shape** (`add.assert_called_once()`, `flush` called, `result is not None`) or **one field** (`level`, `status`, `result`). The `JobAttempt(...)` / `JobLog(...)` objects are real models, so every field written into them is observable on `mock_session.add.call_args[0][0]` — the tests just never look. Likewise `to_dict` is asserted on 4 of ~19 keys, and `execute()` receives a real SQLAlchemy statement nobody inspects.

## Cluster table (121 = 55+6+4+8+15+7+26)

| # | Pattern (function → change) | n | Class | Example keys (of 121) | Evidence / verdict rationale |
|---|---|---|---|---|---|
| A | **Log-record text & `extra=` dict mutations** — every `logger.info`/`logger.warning` msg literal → `None`/`"XX…XX"`/`"lower"`/`"UPPER"`, and the `extra={"job_id": …, "attempt_number": …, …}` payload → `None`, dropped, key renamed (`XXjob_idXX`/`JOB_ID`), or `str(job_id)`→`str(None)` (record_attempt_end 24 · record_attempt_start 22 · add_job_log 9) | 55 | **EQUIVALENT** | `…record_attempt_end__mutmut_13`, `…record_attempt_start__mutmut_8`, `…add_job_log__mutmut_12` | Pure human-facing log text. Nothing in the test suite (or any consumer) reads `record.logmsg`/`extra`. Killing these would require asserting log messages — low-value test tax. Confirmed bodies of the `- )`-shaped diffs (`start_7`, `start_29`, `end_16`, `end_34`, `add_8`) = `extra=` dropped from the log call only. |
| B | **Truthiness branch weakened in `to_dict`** — `x.isoformat() if self.x else None` → `if (self.x) and False else None` (always None) / `if (self.x) or True else None` (crash when None), on `started_at`, `completed_at`, attempt `ended_at` | 6 | **TEST-GAP** | `…to_dict__mutmut_11`, `…to_dict__mutmut_15`, `…to_dict__mutmut_37` | Existing `test_job_history_to_dict` (test_job_history_service.py:149–191) builds a history with all timestamps set and never asserts the `started_at`/`completed_at`/attempt-`ended_at` values, nor the None-side. Killed by draft T4/T6. |
| C | **`add_job_log` → WebSocket emitter payload** — `emitter.emit_log(job_id=…, message=…, context=…)` kwargs → `None` (29, 31, 32) or dropped (36) | 4 | **TEST-GAP** | `…add_job_log__mutmut_29`, `…add_job_log__mutmut_32` | `test_job_log_emitter.py:384` runs the whole path through real Redis-publish mock and asserts only `publish.assert_called_once()` — never the channel or payload. WebSocket streaming is user-facing: a None job_id publishes to `job:None:logs`. Killed by draft T3. |
| D | **Model-constructor kwargs removed** — `JobAttempt(job_id=… / attempt_number=… / worker_id=… / status=…)` and `JobLog(job_id=… / attempt_number=… / message=… / context=…)` argument lines deleted | 8 | **TEST-GAP** | `…record_attempt_start__mutmut_19`, `…add_job_log__mutmut_21`, `…add_job_log__mutmut_24` | Real records get written to the DB missing the job FK / attempt number / message. Existing create-tests assert only that `add` was called. Killed by draft T1/T2. |
| E | **Record-field writes → None / constant tweaks** — `JobAttempt(job_id=None, attempt_number=None, worker_id=None, status=None, "XXstartedXX", "STARTED")`, `session.add(None)`, `attempt.ended_at = None` / `datetime.now(None)`, `attempt.error_message = None`, `attempt.error_traceback = None`, `JobLog(job_id=None, attempt_number=None, message=None, context=None)` (start 7 · end 4 · add 4) | 15 | **TEST-GAP** | `…record_attempt_start__mutmut_15`, `…record_attempt_end__mutmut_25`, `…add_job_log__mutmut_19` | Same one-line-assert blindness: `test_record_attempt_end_updates_attempt` (:477) checks only `status` + `result` (so `ended_at=None`, `error_message=None` sail through); `test_add_job_log_creates_entry` (:529) checks nothing on the record (only `test_add_job_log_normalizes_level` reads `add.call_args`). Killed by draft T1/T2/T5. |
| F | **`record_attempt_end` lookup query mutated** — `job_uuid = None`, whole `select(...).where(...)` → `None`, `select(None)`, `.where(None)`, `==`→`!=` on both job_id and attempt_number clauses | 7 | **TEST-GAP (weak killability — mock ceiling)** | `…record_attempt_end__mutmut_9`, `…record_attempt_end__mutmut_10` | `test_record_attempt_end_updates_attempt` stubs `session.execute` to return a canned attempt **before** calling, so the query content is irrelevant to the outcome. These are genuine wrong-attempt-match bugs (especially the `!=` flips) but unit-mock tests cannot observe SQL; a cheap `str(compiled)` assertion kills them, a real kill wants an integration test against a DB (integration tests run with `-n0` and may be outside this module's mutmut harness — that is why they survived). Draft T6a/T6b. |
| G | **`JobHistory.to_dict` JSON key renames** — output dict keys → `"XXkeyXX"` / `"KEY"` across top-level (`created_at`, `started_at`, `completed_at`) and every transitions-list (`at`, `triggered_by`, `details`) and attempts-list (`started_at`, `ended_at`, `status`, `error`, `worker_id`, `duration_seconds`, `result`) key | 26 | **TEST-GAP** | `…to_dict__mutmut_7`, `…to_dict__mutmut_23`, `…to_dict__mutmut_45` | `to_dict` is the job-history API response contract; renames silently reshape the frontend payload. Existing test asserts only `job_id/job_type/status/transitions[0].from/to/attempts[0].attempt_number` — so the first 6 top-level keys got killed but every timestamp/nested key survived. Killed by draft T4/T5/T6 set-equality + value asserts. |

## Drafted tests (6 — kill clusters E, C, D, and all of G/B; F drafted separately)

All UNVERIFIED — not yet run red/green. TDD procedure for each: apply the cluster's mutant diff to `backend/services/job_history_service.py` → run the new test → assertion must FAIL (or error); revert the diff → test must PASS.

### T1 — kills E(start-field)+D(start): attempt record fields — append to `TestJobHistoryServiceRecordAttempt` in `backend/tests/unit/services/test_job_history_service.py`

```python
    @pytest.mark.asyncio
    async def test_record_attempt_start_persists_parsed_fields(
        self,
        job_history_service: JobHistoryService,
        mock_session: AsyncMock,
        sample_job_uuid: UUID,
    ) -> None:
        """UNVERIFIED - not yet run red/green. Should persist parsed UUID, attempt number, worker and 'started' status."""
        result = await job_history_service.record_attempt_start(
            job_id=str(sample_job_uuid),
            attempt_number=3,
            worker_id="worker-7",
        )

        assert result is not None
        added = mock_session.add.call_args[0][0]
        assert added.job_id == sample_job_uuid          # kills start_15, start_19
        assert added.attempt_number == 3                # kills start_16, start_20
        assert added.worker_id == "worker-7"            # kills start_17, start_21
        assert added.status == "started"                # kills start_18, start_22, start_23, start_24
```

(`session.add` is a `MagicMock` so `call_args` is populated; SQLAlchemy models are created in-memory before the mocked `flush`, so field reads are valid. `status` mutants see the raw attribute — column defaults only apply at insert.)

### T2 — kills E(end-fields)+E(add-log-fields): attempt-end and log-entry fields — same file

```python
    @pytest.mark.asyncio
    async def test_record_attempt_end_stamps_ended_at_and_error_fields(
        self,
        job_history_service: JobHistoryService,
        mock_session: AsyncMock,
        sample_job_uuid: UUID,
    ) -> None:
        """UNVERIFIED - not yet run red/green. Should stamp ended_at and persist error fields on the attempt."""
        attempt = MagicMock(spec=JobAttempt)
        attempt.ended_at = None
        attempt.error_message = None
        attempt.error_traceback = None

        attempt_result = MagicMock()
        attempt_result.scalar_one_or_none.return_value = attempt
        mock_session.execute.return_value = attempt_result

        result = await job_history_service.record_attempt_end(
            job_id=str(sample_job_uuid),
            attempt_number=1,
            status="failed",
            error_message="boom",
            error_traceback="Traceback: …",
        )

        assert result is not None
        assert result.ended_at is not None                    # kills end_25
        assert result.ended_at.utcoffset() == timedelta(0)    # kills end_26 (naive/crash)
        assert result.error_message == "boom"                 # kills end_28
        assert result.error_traceback == "Traceback: …"       # kills end_29

    @pytest.mark.asyncio
    async def test_add_job_log_persists_all_fields(
        self,
        job_history_service: JobHistoryService,
        mock_session: AsyncMock,
        sample_job_uuid: UUID,
    ) -> None:
        """UNVERIFIED - not yet run red/green. Should persist job FK, attempt, message and context on the log record."""
        context = {"item_count": 100}
        result = await job_history_service.add_job_log(
            job_id=str(sample_job_uuid),
            level="WARNING",
            message="Disk almost full",
            context=context,
            attempt_number=2,
        )

        assert result is not None
        added = mock_session.add.call_args[0][0]
        assert added.job_id == sample_job_uuid       # kills add_16, add_21
        assert added.attempt_number == 2             # kills add_17, add_22
        assert added.message == "Disk almost full"   # kills add_19, add_24
        assert added.context == context              # kills add_20, add_25
```

(`start_25` `session.add(None)` is killed by T1 too: `added.job_id` raises `AttributeError` on `None` → test errors → mutant dies.)

### T3 — kills C: emitter payload fidelity — append to `TestJobHistoryServiceIntegration` in `backend/tests/unit/services/test_job_log_emitter.py`

```python
    @pytest.mark.asyncio
    async def test_add_job_log_emits_caller_job_id_message_and_context(
        self,
        mock_redis_client: MagicMock,
    ) -> None:
        """UNVERIFIED - not yet run red/green. Should forward the caller's job_id, message and context to the emitter."""
        await get_job_log_emitter(mock_redis_client)

        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()

        from backend.services.job_history_service import JobHistoryService

        service = JobHistoryService(mock_session)
        job_id = str(uuid.uuid4())

        await service.add_job_log(
            job_id=job_id,
            level="INFO",
            message="Test log entry",
            context={"test": True},
        )

        mock_redis_client.publish.assert_called_once()
        channel = mock_redis_client.publish.call_args[0][0]
        message = json.loads(mock_redis_client.publish.call_args[0][1])
        assert channel == f"job:{job_id}:logs"                # kills add_29 (None job_id -> job:None:logs)
        assert message["data"]["message"] == "Test log entry"  # kills add_31
        assert message["data"]["context"] == {"test": True}    # kills add_32, add_36 (dropped -> None)
```

### T4 — kills G(top)+B(top-branches): `to_dict` top-level contract — append to `TestJobHistory` in `test_job_history_service.py`

```python
    def test_job_history_to_dict_full_top_level_contract(self) -> None:
        """UNVERIFIED - not yet run red/green. Should expose the complete snake_case key set and ISO timestamps."""
        now = datetime.now(UTC)
        started = now + timedelta(seconds=1)
        completed = now + timedelta(minutes=5)
        result = JobHistory(
            job_id="job-123",
            job_type="export",
            status="completed",
            created_at=now,
            started_at=started,
            completed_at=completed,
        ).to_dict()

        assert set(result.keys()) == {
            "job_id", "job_type", "status", "created_at",
            "started_at", "completed_at", "transitions", "attempts",
        }  # kills to_dict_7/8/9/10/13/14 key renames
        assert result["created_at"] == now.isoformat()
        assert result["started_at"] == started.isoformat()      # kills to_dict_11 (and False)
        assert result["completed_at"] == completed.isoformat()

        minimal = JobHistory(
            job_id="job-456",
            job_type="cleanup",
            status="pending",
            created_at=now,
            started_at=None,
            completed_at=None,
        ).to_dict()
        assert minimal["started_at"] is None     # kills to_dict_12 (or True -> isoformat of None crashes)
        assert minimal["completed_at"] is None   # kills to_dict_16
```

### T5 — kills G(transitions): transitions-list contract — same class

```python
    def test_job_history_to_dict_transition_contract(self) -> None:
        """UNVERIFIED - not yet run red/green. Should serialize each transition with the full key contract."""
        now = datetime.now(UTC)
        result = JobHistory(
            job_id="job-123", job_type="export", status="completed",
            created_at=now, started_at=None, completed_at=None,
            transitions=[TransitionRecord(
                from_status=None, to_status="queued", at=now,
                triggered_by="api", details={"metadata": {"reason": "retry"}},
            )],
        ).to_dict()

        entry = result["transitions"][0]
        assert set(entry.keys()) == {"from", "to", "at", "triggered_by", "details"}  # kills to_dict_23/24/25/26/27/28
        assert entry["at"] == now.isoformat()
        assert entry["triggered_by"] == "api"
        assert entry["details"] == {"metadata": {"reason": "retry"}}
```

### T6 — kills G(attempts)+B(ended_at): attempts-list contract — same class

```python
    def test_job_history_to_dict_attempt_contract_and_optional_ended_at(self) -> None:
        """UNVERIFIED - not yet run red/green. Should serialize attempts fully; ended_at stays None when unset."""
        now = datetime.now(UTC)
        result = JobHistory(
            job_id="job-123", job_type="export", status="completed",
            created_at=now, started_at=now, completed_at=None,
            attempts=[
                AttemptRecord(attempt_number=2, started_at=now,
                              ended_at=now + timedelta(seconds=30), status="succeeded",
                              error=None, worker_id="worker-1",
                              duration_seconds=30.0, result={"items": 100}),
                AttemptRecord(attempt_number=3, started_at=now, ended_at=None,
                              status="running", error=None, worker_id=None,
                              duration_seconds=None, result=None),
            ],
        ).to_dict()

        attempts = result["attempts"]
        expected = {"attempt_number", "started_at", "ended_at", "status",
                    "error", "worker_id", "duration_seconds", "result"}
        for entry in attempts:
            assert set(entry.keys()) == expected   # kills to_dict_33–48 key renames
        assert attempts[0]["started_at"] == now.isoformat()
        assert attempts[0]["ended_at"] == (now + timedelta(seconds=30)).isoformat()  # kills to_dict_37 (and False)
        assert attempts[0]["status"] == "succeeded"
        assert attempts[0]["worker_id"] == "worker-1"
        assert attempts[0]["duration_seconds"] == 30.0
        assert attempts[0]["result"] == {"items": 100}
        assert attempts[1]["ended_at"] is None     # kills to_dict_38 (or True -> isoformat of None crashes)
```

### T6a/T6b — F cluster: query-content assertions (cheap kill) + integration note

```python
    # UNVERIFIED - not yet run red/green. Append to TestJobHistoryServiceRecordAttempt,
    # test_job_history_service.py. Needs: from sqlalchemy.dialects import postgresql
    @pytest.mark.asyncio
    async def test_record_attempt_end_query_binds_both_clauses(
        self,
        job_history_service: JobHistoryService,
        mock_session: AsyncMock,
        sample_job_uuid: UUID,
    ) -> None:
        """Should look the attempt up by BOTH job_id and attempt_number."""
        attempt_result = MagicMock()
        attempt_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = attempt_result

        await job_history_service.record_attempt_end(
            job_id=str(sample_job_uuid), attempt_number=7, status="failed",
        )

        stmt = mock_session.execute.call_args[0][0]
        sql = str(stmt.compile(dialect=postgresql.dialect()))
        assert "job_attempts.job_id" in sql and "attempt_number" in sql   # kills end_5/6/7/8 (None/None-where)
        params = list(stmt.compile(dialect=postgresql.dialect()).params.values()) \
            if hasattr(stmt.compile(dialect=postgresql.dialect()), "params") else []
        assert str(sample_job_uuid) in [str(p) for p in params] and 7 in params  # kills end_9/10 (== flipped to !=: bind params unchanged but WHERE polarity — see note)
```

**F caveat (honest killability ranking):** bind-param checks do NOT kill the `==`→`!=` flips (params identical; only operator differs — would need `str(stmt)` regex on `WHERE job_id !=`/`.where` repr, brittle). Robust kill for all 7 F mutants = an integration test (`backend/tests/integration/`, run `-n0` per CLAUDE.md) seeding two attempts for two jobs and asserting `record_attempt_end` updates the *right* row (job2/a1 untouched when ending job1/a2) — the `!=` flips and `None`-where variants then kill themselves. If integration harness cannot import this module in the mutmut run, F is a **harness-scoping finding** for WP4.4, not just a test gap.

## Notes for WP4.4

- A (55, EQUIVALENT): recommend suppressing via mutmut config (e.g. exclude `logger.*` string args) or accepting as permanent noise; killing them means asserting log text, which WP4.4 should not do.
- G+B+C+D+E (59 TEST-GAP) are all closed by drafts T1–T6 — six tests total, ~90 lines. Highest-value single test: T2 (covers 8 record-field survivors across three functions).
- F (7): draft T6a is the cheap path; integration kill is the durable one. Flag for harness scoping.
- Cluster arithmetic: 55 + 6 + 4 + 8 + 15 + 7 + 26 = 121 = survivors_total.
