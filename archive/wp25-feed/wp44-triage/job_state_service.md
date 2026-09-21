# WP4.4 Triage Dossier — backend/services/job_state_service.py

- **Verdicts**: 147 mutants checked, 0 null — **42 survivors**, 105 killed (`mutants/backend/services/job_state_service.py.meta`).
- **Diffs**: all 42 via `uv run mutmut show <key>` (clean, no fallback needed).
- **Covering test file (unit — the only file in mutmut's selection)**:
  `backend/tests/unit/services/test_job_state_service.py` (mutmut `pytest_add_cli_args_test_selection = ["backend/tests/unit"]` in pyproject — the integration twin `backend/tests/integration/test_job_state_transitions.py` runs against real Postgres and CANNOT kill mutants in this baseline).
- **Kill-target line map (unit file)**: `test_job_to_dict` :199-216 · transitions :270-350 · invalid transitions :353-419 · transition history :422-463 · create_job :466-489 · module-level helpers :492-510 · timestamps :513-557.

## Totals

| Classification | Count |
|---|---|
| TEST-GAP | 16 (7 clusters: C5-C12) |
| LOW-VALUE | 18 (2 clusters: C1, C2) |
| EQUIVALENT | 8 (2 clusters: C3, C4) |
| **Total** | **42** |

## Cluster table

| # | Function / concern | Mutation pattern | N | Class | Example keys | Note |
|---|---|---|---|---|---|---|
| C1 | `JobStateService.transition` — success `logger.info("Job state transitioned")` | `extra=` dict: `extra=None`, whole kwarg deleted, keys `job_id`/`from_status`/`to_status`/`triggered_by` → `XX…XX`/UPPER | 10 | LOW-VALUE | `…transition__mutmut_61`, `_63`, `_67` | Happy-path operational log; the transition itself is asserted via return value; no test reads log records. House precedent: alert_service C2, audit_logger C5-C8. |
| C2 | `JobStateService.transition` — invalid-transition `logger.warning` | `extra=` dict: `extra=None` / kwarg deleted / 3 keys renamed XX/UPPER | 8 | LOW-VALUE | `…transition__mutmut_8`, `_10`, `_14` | Rejection signal is NOT lost — `InvalidStateTransition` carries from/to/job_id and TestExceptionDetails :560-601 asserts all three; log payload is duplicate observability. |
| C3 | same warning — message text | msg → `None` / `XX…XX` / lower / UPPER | 4 | EQUIVALENT | `…transition__mutmut_7`, `_11`, `_13` | Pure log text; `LogRecord.getMessage()` stringifies None, no crash. Precedent: ai_fallback C1, alert_service C1. |
| C4 | success `logger.info` — message text | msg → `None` / XX / lower / UPPER | 4 | EQUIVALENT | `…transition__mutmut_60`, `_64`, `_66` | Same reasoning as C3. |
| C5 | `JobData.to_dict` | output keys `"error"`→`"XXerrorXX"`/`"ERROR"`, `"metadata"`→`"XXmetadataXX"`/`"METADATA"` | 4 | **TEST-GAP** | `…to_dict__mutmut_17`, `_18`, `_19` | `test_job_to_dict` (:199-216) asserts id/job_type/status/created_at/started_at/completed_at but **never `data["error"]` or `data["metadata"]`** — wire key renames invisible. |
| C6 | `JobData.to_dict` — timestamp guards | `started_at` guard `(x) or True` (always-call isoformat); `completed_at` guard `(x) and False` (always None) | 2 | **TEST-GAP** | `…to_dict__mutmut_12`, `_15` | `_12` is a real crash path: `to_dict()` on a job with `started_at=None` → `None.isoformat()` AttributeError (fresh queued jobs!), never exercised — existing test always sets `started_at`. `_15` forces `completed_at`→None; test only has the completed_at-is-None case so can't see it. |
| C7 | `transition` + `create_job` — timestamp source | `datetime.now(UTC)` → `datetime.now(None)` (naive local time) | 2 | **TEST-GAP** | `…transition__mutmut_28`, `…create_job__mutmut_15` | All 8 timestamp tests + TestCreateJob assert only `is not None`; naive timestamps flow into `to_dict().isoformat()` payloads (missing `+00:00`) and DB columns. Integration file also lacks tz assertions (and is out of selection anyway). |
| C8 | `transition` — error-message gate | `new_status in ("failed","aborted") and error_message` → `… or error_message` | 1 | **TEST-GAP** | `…transition__mutmut_43` | Mutant sets `job.error = error_message` on ANY transition that passes a message (e.g. queued→running with a diagnostic message leaks into `error`), and clobbers a pre-existing `job.error` with None on message-less failure transitions. Line runs in tests but the negative case is never asserted. |
| C9 | `transition` — error-gate tuple element | `"aborted"` → `"XXabortedXX"` / `"ABORTED"` inside the gate tuple | 2 | **TEST-GAP** | `…transition__mutmut_47`, `_48` | Aborting→aborted with an `error_message` silently stops recording it. No test exists for `aborted` with a message: `test_aborting_to_aborted` (:312-318) passes no message and asserts no `error`. |
| C10 | `_record_transition` — metadata guard | `json.dumps(metadata) if metadata else None` → `… if (metadata) or True else None` → stores string `"null"` instead of SQL NULL when metadata omitted | 1 | **TEST-GAP** | `…_record_transition__mutmut_13` | `test_transition_records_metadata` (:453-463) only covers the metadata-present branch; the metadataless `metadata_json is None` branch is never asserted. `"null"`-vs-NULL is a real data-quality change for the audit column. |
| C11 | `get_valid_target_states` (module-level) | `.get(status, [])` default → `None` / default arg deleted | 2 | **TEST-GAP** | `x_get_valid_target_states__mutmut_2`, `_4` | Unknown status now returns None (caller iterating crashes). The service-method twin IS covered (`test_get_valid_transitions_unknown_status` :256-258 killed its mutants); the module-level convenience twin `test_get_valid_target_states` (:506-510) omits the unknown-status case. |
| C12 | `validate_transition` (module-level) | `.get(from_status, [])` default → `None` / default arg deleted → `to_status in None` raises TypeError | 2 | **TEST-GAP** | `x_validate_transition__mutmut_3`, `_5` | Unknown `from_status` raises TypeError instead of returning False. Tests (:495-504) only pass known statuses; twin method `test_is_valid_transition_unknown_status` (:241-244) kills the method's mutants — asymmetry proves the gap. |

Cluster count sum: 10+8+4+4+4+2+2+1+2+1+2+2 = **42** = survivors_total.

## Drafted tests (target file: `backend/tests/unit/services/test_job_state_service.py`)

Add `timedelta` to the existing `from datetime import UTC, datetime` import (line 10).
**// UNVERIFIED - not yet run red/green.**

### T1 — kills C5 + C6 (to_dict serialization contract, 6 mutants)

Append to `class TestJobData`:

```python
    def test_to_dict_full_serialization_contract(self) -> None:
        """to_dict() must emit every documented key and guard None timestamps."""
        job_id = str(uuid.uuid4())
        created = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
        completed = datetime(2026, 1, 1, 12, 5, 0, tzinfo=UTC)
        job = JobData(
            id=job_id,
            job_type="export",
            status="failed",
            created_at=created,
            started_at=None,          # fresh-queued style: never started
            completed_at=completed,    # completed_at present
            error="disk full",
            metadata={"attempt": 2},
        )
        data = job.to_dict()
        assert set(data) == {
            "id",
            "job_type",
            "status",
            "created_at",
            "started_at",
            "completed_at",
            "error",
            "metadata",
        }
        assert data["started_at"] is None
        assert data["completed_at"] == completed.isoformat()
        assert data["error"] == "disk full"
        assert data["metadata"] == {"attempt": 2}
```

TDD: on `to_dict__12` (`or True` guard) `to_dict()` raises `AttributeError: 'NoneType' has no attribute 'isoformat'`; on `_15` `data["completed_at"]` is None; on `_17/18/19/20` the key-set/`data["error"]`/`data["metadata"]` asserts fail. Passes on original.

### T2 — kills C7 (naive timestamps, 2 mutants)

Append to `class TestTimestampUpdates`:

```python
    @pytest.mark.asyncio
    async def test_created_and_transition_timestamps_are_utc_aware(
        self, job_state_service: JobStateService
    ) -> None:
        """create_job and transition must stamp timezone-aware UTC datetimes."""
        job = job_state_service.create_job("export")
        assert job.created_at is not None
        assert job.created_at.tzinfo is not None
        assert job.created_at.utcoffset() == timedelta(0)

        running = await job_state_service.transition(job, "running")
        assert running.started_at.utcoffset() == timedelta(0)

        done = await job_state_service.transition(running, "completed")
        assert done.completed_at.utcoffset() == timedelta(0)
```

TDD: on `create_job__15` / `transition__28` (`datetime.now(None)`) `utcoffset()` is None ≠ `timedelta(0)` → assert fails; original (UTC-aware) passes.

### T3 — kills C8 (error-gate `and`→`or`, 1 mutant)

Append to `class TestJobStateServiceTransitions`:

```python
    @pytest.mark.asyncio
    async def test_error_message_recorded_only_for_failure_states(
        self, job_state_service: JobStateService
    ) -> None:
        """error_message must not leak onto non-failure transitions, and a
        message-less failure transition must not clobber a pre-existing error."""
        job = JobData(
            id=str(uuid.uuid4()),
            job_type="export",
            status="queued",
            created_at=datetime.now(UTC),
            error="prior error",
        )
        # Non-failure target: error_message must be ignored entirely.
        running = await job_state_service.transition(job, "running", error_message="transient blip")
        assert running.status == "running"
        assert running.error == "prior error"

        # Failure target without a message: pre-existing error must be preserved.
        failed = await job_state_service.transition(running, "failed")
        assert failed.status == "failed"
        assert failed.error == "prior error"
```

TDD: on `transition__43` (`or error_message`) first assert fails (error overwritten with "transient blip") and second fails (error clobbered to None); original passes.

### T4 — kills C9 (aborted tuple clobber, 2 mutants)

Append to `class TestJobStateServiceTransitions`:

```python
    @pytest.mark.asyncio
    async def test_aborted_transition_records_error_message(
        self, job_state_service: JobStateService, aborting_job: JobData
    ) -> None:
        """Aborting -> aborted with an error_message must record it on the job."""
        result = await job_state_service.transition(
            aborting_job, "aborted", error_message="user cancelled via UI"
        )
        assert result.status == "aborted"
        assert result.error == "user cancelled via UI"
```

TDD: on `transition__47/48` the gate tuple no longer matches `"aborted"` → `error` stays None → assert fails; original passes.

### T5 — kills C10 (metadata "null" string, 1 mutant)

Append to `class TestTransitionHistory`:

```python
    @pytest.mark.asyncio
    async def test_transition_without_metadata_records_null(
        self, job_state_service: JobStateService, mock_db: AsyncMock, queued_job: JobData
    ) -> None:
        """Omitted metadata must store SQL NULL, not the JSON string "null"."""
        await job_state_service.transition(queued_job, "running")

        transition = mock_db.add.call_args[0][0]
        assert transition.metadata_json is None
```

TDD: on `_record_transition__13` (`or True` guard) `json.dumps(None)` == `"null"` is not None → assert fails; original passes.

### T6 — kills C11 + C12 (module-level unknown status, 4 mutants)

Append to `class TestModuleLevelFunctions`:

```python
    def test_module_level_helpers_unknown_status(self) -> None:
        """Convenience helpers must tolerate unknown statuses like the method twins."""
        assert get_valid_target_states("unknown") == []
        assert validate_transition("unknown", "running") is False
```

TDD: on `get_valid_target_states__2/4` return is None ≠ [] → fails; on `validate_transition__3/5` `to_status in None` raises TypeError → fails as error; originals pass.

## Drafted-test kill coverage

T1(6) + T2(2) + T3(1) + T4(2) + T5(1) + T6(4) = **16/16 TEST-GAP mutants**. Remaining 26 (C1-C4) are deliberate non-gaps (log payload/text per house precedent) — no tests drafted for them.

## Notes for the fix lane

- mutmut's test selection is `backend/tests/unit` only (pyproject `[tool.mutmut] pytest_add_cli_args_test_selection`), so the drafted tests MUST go into `backend/tests/unit/services/test_job_state_service.py` to count as kills; the integration file cannot contribute.
- `datetime.now(None)` (C7) survived a full unit sweep because every timestamp assert is `is not None` — this is the highest-severity survivor: naive local timestamps corrupt `to_dict().isoformat()` payloads and DB rows with no failure anywhere.
- `to_dict__12` (`or True`) is a latent crash for any caller serializing a not-yet-started job — the highest-severity survivor on the serialization path.
