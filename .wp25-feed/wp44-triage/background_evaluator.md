# WP4.4 Triage Dossier — `backend/services/background_evaluator.py`

- **Source**: `backend/services/background_evaluator.py` (576 lines)
- **Covering test file (only one)**: `backend/tests/unit/services/test_background_evaluator.py` (1290 lines)
- **Verdict state** (`mutants/backend/services/background_evaluator.py.meta`): 392 keys → **161 survived**, 91 killed, 140 still unchecked (run in flight; only checked survivors triaged).
- **Diffs**: all 161 retrieved via `uv run mutmut show <key>` (0 failures), parsed from hunk headers to original line numbers. Parsed data: `/tmp/wp25/wp44-triage/parsed.json`, `/tmp/wp25/wp44-triage/all_diffs.txt`.
- **Cluster totals verified**: 23 clusters, counts sum to exactly 161.

## Why so many survive (root cause, one sentence)

The suite drives `process_one()` through fully-mocked `get_session`/`MagicMock` job trackers but asserts only _return values_ (`is True`), _call counts_ (`call_count >= 3`, `assert_called_once()`), and _one substring_ (`"AI service error" in call_args[0][1]`) — it never pins **which job id / progress percent / message / payload** a call carried, nor the **SQL executed** on the mocked session. Key existing weak-assert sites: `test_background_evaluator.py:311-314, 349-350, 381-382, 421-422, 997-998, 1041-1042, 1084-1086, 1113, 1138-1142`.

## Cluster table

Counts sum = 161. "Src" = original file lines. "Killed by draft" = which drafted test below flips the cluster's keys red→green.

| #   | Pattern (function @ src lines)                                                                                                                                                                                                     |   N | Example keys        | Class      | Killed by                                                               |
| --- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --: | ------------------- | ---------- | ----------------------------------------------------------------------- |
| C01 | `get_background_evaluator` (src 559-569): config kwarg forwarded→`None`, or kwarg omitted (→silent default)                                                                                                                        |  12 | \_3, \_7, \_15      | TEST-GAP   | Draft C                                                                 |
| C02 | `_update_job_progress` (150-151): tracker call args clobbered (`id/progress/message`→None, args dropped)                                                                                                                           |   6 | \_2, \_4, \_5       | TEST-GAP   | Draft A (tracker)                                                       |
| C03 | `_update_job_progress` (152-153): legacy-service call args clobbered (same shapes) — legacy branch has **zero** assertions                                                                                                         |   6 | \_9, \_11, \_12     | TEST-GAP   | Draft A (legacy)                                                        |
| C04 | `_complete_job` (170-173): completion call args clobbered (id→None, result→None, args dropped)                                                                                                                                     |   7 | \_2, \_8, \_10      | TEST-GAP   | Draft A/E/B; **\_6 guard survives (LOW-VALUE)**                         |
| C05 | `_fail_job` (190-193): failure call args clobbered (id→None, error→None, args dropped)                                                                                                                                             |   6 | \_2, \_8, \_9       | TEST-GAP   | Draft B; **\_6 guard survives (LOW-VALUE)**                             |
| C06 | Delegation guards `and`→`or` in `_update_job_progress`/`_complete_job`/`_fail_job` (150,152,172,192) + `process_one` L284                                                                                                          |   5 | \_1, \_8, \_71      | LOW-VALUE  | \_71 by Draft A; \_1/\_8×3,comp \_6 unkillable (see note)               |
| C07 | `_is_job_cancelled` (131): `is_cancelled(job_id)`→`is_cancelled(None)`                                                                                                                                                             |   1 | \_5                 | TEST-GAP   | not drafted (1 key; add `assert_called_with(tracker_id)` to L1113 test) |
| C08 | `process_one` progress constants +1 (305, 349, 381): 10→11, 25→26, 40→41                                                                                                                                                           |   3 | \_46, \_103, \_141  | TEST-GAP   | Draft A                                                                 |
| C09 | `process_one` tracker `start_job` args (286-288) clobbered/dropped                                                                                                                                                                 |   4 | \_17, \_19, \_20    | TEST-GAP   | Draft A (tracker)                                                       |
| C10 | `process_one` legacy `start_job` kwargs (290-295): `job_id=f"evaluation-{event_id}"`/`job_type`/`metadata` →None/omitted/retyped; whole call →`job_id=None`                                                                        |  11 | \_22, \_24, \_31    | TEST-GAP   | Draft A (legacy)                                                        |
| C11 | `process_one` `_update_job_progress` call sites (304-306, 348-350, 380-382): `job_service`/`job_id`/`progress`/`message` arg→None                                                                                                  |  12 | \_37, \_39, \_134   | TEST-GAP   | Draft A                                                                 |
| C12 | `process_one` event-not-found `_fail_job` args (342-344) clobbered/dropped                                                                                                                                                         |   7 | \_85, \_88, \_91    | TEST-GAP   | Draft B (legacy)                                                        |
| C13 | `process_one` no-audit-record `_fail_job` args (363-368) clobbered/dropped                                                                                                                                                         |   8 | \_120, \_123, \_127 | TEST-GAP   | Draft B (legacy+tracker)                                                |
| C14 | `process_one` except-path `_fail_job` args (438) →None                                                                                                                                                                             |   2 | \_185, \_186        | TEST-GAP   | Draft B (legacy)                                                        |
| C15 | `process_one` Session-1 Event query (321-325): `execute(None)`, `select(None)`, `where(None)`, `==`→`!=`                                                                                                                           |   4 | \_53, \_59, \_60    | TEST-GAP   | Draft D                                                                 |
| C16 | `process_one` `undefer(Event.llm_prompt/reasoning)` removal (324) — NEM-3902 fix line, deferred cols silently regress to lazy-load                                                                                                 |   2 | \_56, \_57          | TEST-GAP   | Draft D (undefer spy)                                                   |
| C17 | `process_one` EventAudit query (353-355): same clobber family as C15                                                                                                                                                               |   4 | \_108, \_110, \_111 | TEST-GAP   | Draft D                                                                 |
| C18 | `run_evaluation_llm_calls(audit, event)` → `(None, event)` (394)                                                                                                                                                                   |   1 | \_145               | TEST-GAP   | Draft E                                                                 |
| C19 | Session-2 write `write_session.merge(audit)` → `merge(None)` (404) — persistence silently lost                                                                                                                                     |   1 | \_150               | TEST-GAP   | Draft E                                                                 |
| C20 | `process_one` `_complete_job` call (411-419): `job_service`/`job_id`→None, result payload→None                                                                                                                                     |   3 | \_152, \_153, \_154 | TEST-GAP   | Draft A/E/B                                                             |
| C21 | Sentinel inits `= None` → `= ""` for locals `tracker_job_id/job_id/job_service/event/audit` (280-282, 314-315) — value always reassigned/truthy-equivalent before any read                                                         |   5 | \_10, \_50, \_51    | EQUIVALENT | n/a                                                                     |
| C22 | Progress message string tweaks (305, 349, 381): case/`XX` wrap (human-facing UI text)                                                                                                                                              |   9 | \_47, \_105, \_144  | LOW-VALUE  | incidentally by Draft A (exact tuples)                                  |
| C23 | `logger.*` message text →None/removed, `extra` payload →None/keys retyped (`event_id`→`EVENT_ID`/`XX..`), `exc_info=True`→False/omitted (273-276, 329-332, 359-362, 421-427, 432-436) — no `caplog` anywhere in the module's tests |  42 | \_5, \_164, \_183   | EQUIVALENT | n/a                                                                     |

**Totals: TEST-GAP 100, LOW-VALUE 14, EQUIVALENT 47.**

### Classification notes

- **C23 (42, EQUIVALENT)**: every survivor changes only log-record cosmetics (message text, `extra` dict keys, `exc_info`). The covering suite contains no `caplog`/`LogCapture` usage for this module, and log `extra` is write-only (nothing reads it back). Semantically inert for behavior the team asserts.
- **C21 (5, EQUIVALENT)**: `tracker_job_id/job_id/job_service/event/audit = None → ""`. All five locals are unconditionally overwritten on the branch that executes (`create_job`/`start_job`/two `scalar_one_or_none()`), and where the guard `elif job_service and job_id:` reads them, `""` is only reachable when the other operand is already falsy → no observable path. (The `event`/`audit` sentinels exist purely for the NEM-3505 MissingGreenlet pattern's type-narrowing.)
- **C06 (5, LOW-VALUE, mixed)**: `and`→`or` in the two-operand delegation guards. In the JobTracker branch the guard is _reachable-false_ (`if self._job_tracker` L284 guarantees `tracker_job_id` was created) and in the legacy branch `job_service` and `job_id` are always set together — so 4 of the 5 keys (helper guards `upd_progress _1/_8`, `complete_job _6`, `fail_job _6`) cannot be killed by any test that keeps the public API honest, and killing them would require calling private helpers with invalid inconsistent state (not worth it). Exception: `process_one` L284 `_71` IS behavior-affecting (`if self._job_tracker or tracker_job_id:` would call `create_job` on a None tracker → TypeError) and Draft A kills it; the cluster's classification stays LOW-VALUE with that one key noted as gap-adjacent.
- **C22 (9, LOW-VALUE)**: real change (UI-visible progress wording), but string equality on human text is a weak contract. Kept LOW-VALUE even though Draft A pins it incidentally — if the team dislikes message pinning, relax Draft A's expected tuples to `(id, pct)` pairs; the percent pin (C08) still lands.

## Drafted tests (5 drafts kill 12 TEST-GAP clusters ≈ 81 of the 100 gap keys)

`// UNVERIFIED - not yet run red/green`

**TDD procedure (one line)**: apply the cluster's one-line diff to `backend/services/background_evaluator.py`, run the named test → the pinned assertion must FAIL (red); restore the original → PASS (green); then re-run the module's `mutmut run` scope and confirm those keys flip `survived → killed`.

Fixture note: `mock_job_tracker` / `evaluator_with_job_tracker` are **class-scoped** inside `TestJobTrackingIntegration` (`test_background_evaluator.py:942-972`), so the drafted classes below redefine them locally (verbatim copies) — or hoist them to module scope once, which is the cleaner refactor. New import needed at file top (line 16): `call` → `from unittest.mock import AsyncMock, MagicMock, call, patch`.

### Draft A — exact progress ladder + job-start contract (kills C08, C09, C10, C11, C02, C03; pins C08 percents; incidentally C22)

```python
class TestProgressLadderContract:
    """WP4.4: pin the job-progress contract — exact (job_id, percent, message) per step.

    Kills C08 (percent +1), C09 (tracker start_job args), C10 (legacy start_job kwargs),
    C11 (call-site arg clobbers), and the _update_job_progress helper clobbers (C02/C03).
    // UNVERIFIED - not yet run red/green
    """

    @pytest.mark.asyncio
    async def test_tracker_progress_ladder_exact_calls(
        self, evaluator_with_job_tracker, mock_evaluation_queue, mock_job_tracker
    ):
        """Tracker path: each progress step is (test-job-123, exact pct, exact message)."""
        mock_evaluation_queue.dequeue.return_value = 123

        mock_event = MagicMock()
        mock_event.id = 123
        mock_audit = MagicMock()
        mock_audit.id = 1
        mock_audit.event_id = 123
        mock_audit.overall_quality_score = 85.0

        with patch(
            "backend.services.background_evaluator.get_session", autospec=True
        ) as mock_get_session:
            mock_session = AsyncMock()
            mock_session.expunge = MagicMock()  # expunge is sync
            mock_session.merge = AsyncMock(return_value=mock_audit)

            mock_event_result = MagicMock()
            mock_event_result.scalar_one_or_none.return_value = mock_event
            mock_audit_result = MagicMock()
            mock_audit_result.scalar_one_or_none.return_value = mock_audit
            mock_session.execute.side_effect = [mock_event_result, mock_audit_result]

            mock_ctx_manager = AsyncMock()
            mock_ctx_manager.__aenter__.return_value = mock_session
            mock_ctx_manager.__aexit__.return_value = None
            mock_get_session.return_value = mock_ctx_manager

            await evaluator_with_job_tracker.process_one()

            mock_job_tracker.start_job.assert_called_once_with(
                "test-job-123", "Processing evaluation for event 123"
            )
            assert mock_job_tracker.update_progress.call_args_list == [
                call("test-job-123", 10, "Fetching event data"),
                call("test-job-123", 25, "Fetching audit record"),
                call("test-job-123", 40, "Running AI evaluation"),
            ]
            mock_job_tracker.complete_job.assert_called_once_with(
                "test-job-123",
                result={"event_id": 123, "overall_quality_score": 85.0},
            )

    @pytest.mark.asyncio
    async def test_legacy_progress_ladder_exact_calls(
        self, background_evaluator, mock_evaluation_queue, mock_job_status_service
    ):
        """Legacy JobStatusService path: same ladder, pinned against mock-job-id.

        Also pins start_job kwargs (job_id=f\"evaluation-{event_id}\", job_type,
        metadata) — no existing test touches this branch at all (C10).
        """
        mock_evaluation_queue.dequeue.return_value = 123

        mock_event = MagicMock()
        mock_event.id = 123
        mock_audit = MagicMock()
        mock_audit.id = 1
        mock_audit.event_id = 123
        mock_audit.overall_quality_score = 85.0

        with patch(
            "backend.services.background_evaluator.get_session", autospec=True
        ) as mock_get_session:
            mock_session = AsyncMock()
            mock_session.expunge = MagicMock()
            mock_session.merge = AsyncMock(return_value=mock_audit)

            mock_event_result = MagicMock()
            mock_event_result.scalar_one_or_none.return_value = mock_event
            mock_audit_result = MagicMock()
            mock_audit_result.scalar_one_or_none.return_value = mock_audit
            mock_session.execute.side_effect = [mock_event_result, mock_audit_result]

            mock_ctx_manager = AsyncMock()
            mock_ctx_manager.__aenter__.return_value = mock_session
            mock_ctx_manager.__aexit__.return_value = None
            mock_get_session.return_value = mock_ctx_manager

            await background_evaluator.process_one()

            mock_job_status_service.start_job.assert_awaited_once_with(
                job_id="evaluation-123",
                job_type="background_evaluation",
                metadata={"event_id": 123},
            )
            assert mock_job_status_service.update_progress.await_args_list == [
                call("mock-job-id", 10, "Fetching event data"),
                call("mock-job-id", 25, "Fetching audit record"),
                call("mock-job-id", 40, "Running AI evaluation"),
            ]
```

Kill math spot-checks: C08#46 `11 != 10` ✓; C11#39 `progress=None` ✓; C11#37 (`job_service`→None) survives the tracker test but dies in the legacy test (dispatch falls to `elif`, zero update calls ≠ expected ladder) ✓; C10#22 (whole `start_job` → `job_id = None`) → `assert_awaited_once` fails ✓; C06#71 (`start_job` called on None tracker → TypeError, except-path) → `create_job` never called ✓.

### Draft B — failure paths must fail the _right_ job with the _right_ error (kills C12, C13, C14 + helper mutants in C04/C05)

```python
class TestFailurePathJobIdentity:
    """WP4.4: every skip/failure path fails the correct job id with the correct message.

    Existing coverage checks only process_one's return value (test file L349-350,
    L381-382, L421-422) or only the error *substring* on the tracker path
    (L1084-1086) — job id and legacy dispatch are never asserted.
    // UNVERIFIED - not yet run red/green
    """

    # class-scoped fixtures hoisted from TestJobTrackingIntegration (L942-972)
    @pytest.fixture
    def mock_job_tracker(self):
        tracker = MagicMock()
        tracker.create_job = MagicMock(return_value="test-job-123")
        tracker.start_job = MagicMock()
        tracker.update_progress = MagicMock()
        tracker.complete_job = MagicMock()
        tracker.fail_job = MagicMock()
        tracker.is_cancelled = MagicMock(return_value=False)
        return tracker

    @pytest.fixture
    def evaluator_with_job_tracker(
        self, mock_redis, mock_gpu_monitor, mock_evaluation_queue, mock_audit_service,
        mock_job_tracker,
    ):
        from backend.services.background_evaluator import BackgroundEvaluator

        return BackgroundEvaluator(
            redis_client=mock_redis,
            gpu_monitor=mock_gpu_monitor,
            evaluation_queue=mock_evaluation_queue,
            audit_service=mock_audit_service,
            job_tracker=mock_job_tracker,
        )

    @staticmethod
    def _event_found_audit_missing_session(mock_event):
        mock_event_result = MagicMock()
        mock_event_result.scalar_one_or_none.return_value = mock_event
        mock_audit_result = MagicMock()
        mock_audit_result.scalar_one_or_none.return_value = None
        return [mock_event_result, mock_audit_result]

    @pytest.mark.asyncio
    async def test_legacy_missing_event_fails_job(
        self, background_evaluator, mock_evaluation_queue, mock_job_status_service
    ):
        mock_evaluation_queue.dequeue.return_value = 999

        with patch(
            "backend.services.background_evaluator.get_session", autospec=True
        ) as mock_get_session:
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_session.execute = AsyncMock(return_value=mock_result)

            mock_ctx_manager = AsyncMock()
            mock_ctx_manager.__aenter__.return_value = mock_session
            mock_ctx_manager.__aexit__.return_value = None
            mock_get_session.return_value = mock_ctx_manager

            result = await background_evaluator.process_one()

            assert result is True
            mock_job_status_service.fail_job.assert_awaited_once_with(
                "mock-job-id", "Event 999 not found"
            )
            mock_job_status_service.complete_job.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_legacy_missing_audit_fails_job(
        self, background_evaluator, mock_evaluation_queue, mock_job_status_service
    ):
        mock_evaluation_queue.dequeue.return_value = 123
        mock_event = MagicMock()
        mock_event.id = 123

        with patch(
            "backend.services.background_evaluator.get_session", autospec=True
        ) as mock_get_session:
            mock_session = AsyncMock()
            mock_session.expunge = MagicMock()
            mock_session.execute.side_effect = self._event_found_audit_missing_session(mock_event)

            mock_ctx_manager = AsyncMock()
            mock_ctx_manager.__aenter__.return_value = mock_session
            mock_ctx_manager.__aexit__.return_value = None
            mock_get_session.return_value = mock_ctx_manager

            result = await background_evaluator.process_one()

            assert result is True
            mock_job_status_service.fail_job.assert_awaited_once_with(
                "mock-job-id", "No audit record for event 123"
            )

    @pytest.mark.asyncio
    async def test_tracker_missing_audit_fails_job(
        self, evaluator_with_job_tracker, mock_evaluation_queue, mock_job_tracker
    ):
        mock_evaluation_queue.dequeue.return_value = 123
        mock_event = MagicMock()
        mock_event.id = 123

        with patch(
            "backend.services.background_evaluator.get_session", autospec=True
        ) as mock_get_session:
            mock_session = AsyncMock()
            mock_session.expunge = MagicMock()
            mock_session.execute.side_effect = self._event_found_audit_missing_session(mock_event)

            mock_ctx_manager = AsyncMock()
            mock_ctx_manager.__aenter__.return_value = mock_session
            mock_ctx_manager.__aexit__.return_value = None
            mock_get_session.return_value = mock_ctx_manager

            await evaluator_with_job_tracker.process_one()

            mock_job_tracker.fail_job.assert_called_once_with(
                "test-job-123", "No audit record for event 123"
            )

    @pytest.mark.asyncio
    async def test_legacy_evaluation_exception_fails_job(
        self, background_evaluator, mock_evaluation_queue, mock_audit_service,
        mock_job_status_service,
    ):
        """Except-path _fail_job(tracker_job_id, job_service, job_id, str(e)) —
        clobbering job_service/job_id (C14) silently drops the job failure."""
        mock_evaluation_queue.dequeue.return_value = 123
        mock_audit_service.run_evaluation_llm_calls.side_effect = RuntimeError("AI service error")

        mock_event = MagicMock()
        mock_event.id = 123
        mock_audit = MagicMock()
        mock_audit.id = 1
        mock_audit.event_id = 123

        with patch(
            "backend.services.background_evaluator.get_session", autospec=True
        ) as mock_get_session:
            mock_session = AsyncMock()
            mock_session.expunge = MagicMock()

            mock_event_result = MagicMock()
            mock_event_result.scalar_one_or_none.return_value = mock_event
            mock_audit_result = MagicMock()
            mock_audit_result.scalar_one_or_none.return_value = mock_audit
            mock_session.execute.side_effect = [mock_event_result, mock_audit_result]

            mock_ctx_manager = AsyncMock()
            mock_ctx_manager.__aenter__.return_value = mock_session
            mock_ctx_manager.__aexit__.return_value = None
            mock_get_session.return_value = mock_ctx_manager

            await background_evaluator.process_one()

            mock_job_status_service.fail_job.assert_awaited_once_with(
                "mock-job-id", "AI service error"
            )
            mock_job_status_service.complete_job.assert_not_awaited()
```

### Draft C — singleton factory forwards configuration (kills C01)

```python
class TestSingletonWiring:
    """WP4.4: get_background_evaluator must forward deps + non-default config.

    Existing singleton tests (test file L888-931) only assert isinstance and
    identity, so every config kwarg could be clobbered to None or dropped
    (silently reverting to __init__ defaults) unnoticed.
    // UNVERIFIED - not yet run red/green
    """

    def test_get_background_evaluator_forwards_deps_and_config(
        self, mock_redis, mock_gpu_monitor, mock_evaluation_queue, mock_audit_service
    ):
        from backend.services.background_evaluator import (
            get_background_evaluator,
            reset_background_evaluator,
        )

        reset_background_evaluator()
        try:
            evaluator = get_background_evaluator(
                redis_client=mock_redis,
                gpu_monitor=mock_gpu_monitor,
                evaluation_queue=mock_evaluation_queue,
                audit_service=mock_audit_service,
                gpu_idle_threshold=33,
                idle_duration_required=7,
                poll_interval=1.25,
                enabled=False,
            )

            assert evaluator._redis is mock_redis
            assert evaluator._gpu_monitor is mock_gpu_monitor
            assert evaluator._evaluation_queue is mock_evaluation_queue
            assert evaluator._audit_service is mock_audit_service
            assert evaluator.gpu_idle_threshold == 33
            assert evaluator.idle_duration_required == 7
            assert evaluator.poll_interval == 1.25
            assert evaluator.enabled is False
        finally:
            reset_background_evaluator()
```

(`enabled=False` vs default `True`, and 33/7/1.25 vs 20/5/5.0 defaults, kill both the `=None` and the drop-the-kwarg mutants; identity asserts kill the dep→None ones.)

### Draft D — Session-1 queries target the dequeued event id + undefer deferred columns (kills C15, C17, C16)

```python
class TestSessionOneQueryShape:
    """WP4.4: the mocked-session tests never looked at the executed SQL, so
    ==->!= / where(None) / execute(None) mutants on both SELECTs survived.
    // UNVERIFIED - not yet run red/green
    """

    @pytest.mark.asyncio
    async def test_both_selects_filter_on_dequeued_event_id(
        self, background_evaluator, mock_evaluation_queue
    ):
        mock_evaluation_queue.dequeue.return_value = 123

        mock_event = MagicMock()
        mock_event.id = 123
        captured = []

        def capture_execute(stmt):
            captured.append(stmt)
            result = MagicMock()
            if len(captured) == 1:
                result.scalar_one_or_none.return_value = mock_event  # event found
            else:
                result.scalar_one_or_none.return_value = None  # audit missing -> stop
            return result

        with patch(
            "backend.services.background_evaluator.get_session", autospec=True
        ) as mock_get_session:
            mock_session = AsyncMock()
            mock_session.expunge = MagicMock()
            mock_session.execute.side_effect = capture_execute

            mock_ctx_manager = AsyncMock()
            mock_ctx_manager.__aenter__.return_value = mock_session
            mock_ctx_manager.__aexit__.return_value = None
            mock_get_session.return_value = mock_ctx_manager

            result = await background_evaluator.process_one()

        assert result is True
        assert len(captured) == 2, f"expected 2 SELECTs, captured {captured!r}"

        event_sql = str(captured[0].compile(compile_kwargs={"literal_binds": True}))
        assert "FROM events" in event_sql
        assert "events.id = 123" in event_sql  # kills !=, where(None), select(None)

        audit_sql = str(captured[1].compile(compile_kwargs={"literal_binds": True}))
        assert "FROM event_audits" in audit_sql
        assert "event_audits.event_id = 123" in audit_sql

    @pytest.mark.asyncio
    async def test_event_query_undefer_defers_deferred_columns(
        self, background_evaluator, mock_evaluation_queue, monkeypatch
    ):
        """NEM-3902 regression lock: llm_prompt/reasoning undefer must stay (C16).

        The existing deferred-columns test (L1176-1242) mocks the session, so
        removing undefer() never triggers DetachedInstanceError there — pin the
        call itself instead.
        """
        from sqlalchemy.orm import undefer as real_undefer

        mock_evaluation_queue.dequeue.return_value = 123
        undefered = []

        def spy_undefer(column):
            undefered.append(getattr(column, "key", str(column)))
            return real_undefer(column)

        monkeypatch.setattr("backend.services.background_evaluator.undefer", spy_undefer)

        with patch(
            "backend.services.background_evaluator.get_session", autospec=True
        ) as mock_get_session:
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None  # stop at event-not-found
            mock_session.execute = AsyncMock(return_value=mock_result)

            mock_ctx_manager = AsyncMock()
            mock_ctx_manager.__aenter__.return_value = mock_session
            mock_ctx_manager.__aexit__.return_value = None
            mock_get_session.return_value = mock_ctx_manager

            await background_evaluator.process_one()

        assert any("llm_prompt" in key for key in undefered), undefered
        assert any("reasoning" in key for key in undefered), undefered
```

### Draft E — LLM call / merge / completion payload identity (kills C18, C19, C20)

```python
class TestEvaluationPayloadIdentity:
    """WP4.4: the evaluated audit object must reach run_evaluation_llm_calls and
    write_session.merge, and the completion payload must carry event + score.
    // UNVERIFIED - not yet run red/green
    """

    # mock_job_tracker / evaluator_with_job_tracker: same copies as Draft B

    @pytest.mark.asyncio
    async def test_llm_calls_and_merge_receive_fetched_objects(
        self, evaluator_with_job_tracker, mock_evaluation_queue, mock_audit_service
    ):
        mock_evaluation_queue.dequeue.return_value = 123

        mock_event = MagicMock()
        mock_event.id = 123
        mock_audit = MagicMock()
        mock_audit.id = 1
        mock_audit.event_id = 123
        mock_audit.overall_quality_score = 85.0

        with patch(
            "backend.services.background_evaluator.get_session", autospec=True
        ) as mock_get_session:
            mock_session = AsyncMock()
            mock_session.expunge = MagicMock()
            mock_session.merge = AsyncMock(return_value=mock_audit)

            mock_event_result = MagicMock()
            mock_event_result.scalar_one_or_none.return_value = mock_event
            mock_audit_result = MagicMock()
            mock_audit_result.scalar_one_or_none.return_value = mock_audit
            mock_session.execute.side_effect = [mock_event_result, mock_audit_result]

            mock_ctx_manager = AsyncMock()
            mock_ctx_manager.__aenter__.return_value = mock_session
            mock_ctx_manager.__aexit__.return_value = None
            mock_get_session.return_value = mock_ctx_manager

            await evaluator_with_job_tracker.process_one()

            # C18: evaluation must receive the fetched audit, not None
            llm_call = mock_audit_service.run_evaluation_llm_calls.await_args
            assert llm_call is not None
            assert llm_call.args[0] is mock_audit
            assert llm_call.args[1] is mock_event

            # C19: Session-2 write path must merge the evaluated audit, not None
            merge_call = mock_session.merge.await_args
            assert merge_call is not None
            assert merge_call.args[0] is mock_audit

    @pytest.mark.asyncio
    async def test_legacy_complete_job_receives_id_and_result(
        self, background_evaluator, mock_evaluation_queue, mock_job_status_service
    ):
        mock_evaluation_queue.dequeue.return_value = 123

        mock_event = MagicMock()
        mock_event.id = 123
        mock_audit = MagicMock()
        mock_audit.id = 1
        mock_audit.event_id = 123
        mock_audit.overall_quality_score = 85.0

        with patch(
            "backend.services.background_evaluator.get_session", autospec=True
        ) as mock_get_session:
            mock_session = AsyncMock()
            mock_session.expunge = MagicMock()
            mock_session.merge = AsyncMock(return_value=mock_audit)

            mock_event_result = MagicMock()
            mock_event_result.scalar_one_or_none.return_value = mock_event
            mock_audit_result = MagicMock()
            mock_audit_result.scalar_one_or_none.return_value = mock_audit
            mock_session.execute.side_effect = [mock_event_result, mock_audit_result]

            mock_ctx_manager = AsyncMock()
            mock_ctx_manager.__aenter__.return_value = mock_session
            mock_ctx_manager.__aexit__.return_value = None
            mock_get_session.return_value = mock_ctx_manager

            await background_evaluator.process_one()

            mock_job_status_service.complete_job.assert_awaited_once_with(
                "mock-job-id",
                result={"event_id": 123, "overall_quality_score": 85.0},
            )
```

## Residual after drafts (acceptable)

- C06 ×4 guard keys + C04#6/C05#6 elif-guard keys: unreachable-inconsistent-state guards → document as LOW-VALUE survivors (candidates for a future `# pragma: no mutate` review, out of WP4.4 scope).
- C07#1: one-line addition to existing `test_process_one_checks_cancellation` — change `assert_called()` (L1113) to `assert_called_with("test-job-123")`.
- C21/C22/C23 (56 keys): EQUIVALENT/LOW-VALUE, no action.

## Covering-test map (file:line)

All coverage: `backend/tests/unit/services/test_background_evaluator.py` — fixtures 29-118; `TestGPUIdleDetection` 126; `TestDetectionPipelinePriority` 208; `TestEvaluationProcessing` 266; `TestLifecycleManagement` 430; `TestConfiguration` 506; `TestProcessingLoop` 593; `TestSingletonPattern` 885; `TestJobTrackingIntegration` 939 (fixtures 942-972); `TestDeferredColumnAccess` 1172. Weak-assert anchors listed in the root-cause paragraph above.
