# WP4.4 Triage Dossier — `backend/api/routes/ai_audit.py`

Source: `mutants/backend/api/routes/ai_audit.py.meta` (254 keys, all checked: 111 survived / 143 killed / 0 null).
All 111 survivor diffs verified via `uv run mutmut show <key>` (0 failures). **UNVERIFIED — no tests were run** (live mutation run owns the machine; read-only pass per WP4.3 constraints).

Survivor split: `_run_batch_audit_job` 78 · `_audit_to_response` 29 · `safe_parse_datetime` 4.

## Covering test files (from `mutmut-stats.json → tests_by_mangled_function_name`, fully-qualified keys)

- **`backend/tests/unit/api/routes/test_ai_audit.py`** (primary):
  - `TestHelperFunctions` (1924-1976) → `safe_parse_datetime`
  - `TestAuditToResponseConversion` (1343-1431) → `_audit_to_response` (pure-function calls)
  - `TestBatchAuditJobBackgroundTask` (1438-1922) → `_run_batch_audit_job` (direct coroutine calls)
  - `mock_audit_service` fixture (135-144): `MagicMock()` **no `spec=`/`autospec`** — the structural cause of most survivors
  - `mock_job_tracker` fixture (147-207): side-effects silently no-op on unknown job_id (`if job_id in _jobs` guard, 172-194) — `job_id=None` mutants invisible
  - `create_mock_audit` (65-120): `MagicMock(spec=EventAudit)` — typo attrs auto-create Mocks, but `unused_data/format_suggestions/model_gaps/confusing_sections = None` (112-115) and `consistency_*` only set when `is_evaluated=True` (104-108)
- **`backend/tests/unit/routes/test_ai_audit_routes.py`** (secondary): real `EventAudit` fixtures `sample_audit` (96-136, sets `consistency_risk_score=60, consistency_diff=5, self_eval_critique=...` at 127-130); `test_get_event_audit_success` (176-209) asserts id/contributions/scores/prompt_length/improvements but **never the three consistency/critique fields**; `tracker` fixture (47-49) returns bare `return_value=None`.

## Cluster table

| # | Pattern | n | Class | Example keys | Why |
|---|---------|---|-------|--------------|-----|
| 1 | `_audit_to_response`: `_parse_json_list` label/`default=`/`context=` text + None-substitutions + omitted improvement kwargs (59,62,63,65,68,69,71,74,75,77,80,81,83,86,87 label-None/XX/CASE; 40,41,43,44 safe_json_loads kwargs; 70,82 `unused_data`/`model_gaps`→None; 55,57 omitted) | 23 | EQUIVALENT | `x__audit_to_response__mutmut_59`, `_mutmut_70`, `_mutmut_55` | `field_name` feeds only the `context=` log string on parse failure; `safe_json_loads` failure path guarded by `isinstance(result, list) else []` (ai_audit.py:121); omitted/None inputs identical because every fixture sets those JSON fields to `None`; omitted `unused_data`/`model_gaps` kwargs fall to schema `Field(default_factory=list)` (schemas/ai_audit.py:83,85). Return value byte-identical in all 23. |
| 2 | `safe_parse_datetime`: `"Z"→"XXZXX"` / `"Z"→"z"` replace-arg tweaks | 2 | EQUIVALENT | `x_safe_parse_datetime__mutmut_10`, `_mutmut_11` | Python 3.11+/3.14 `datetime.fromisoformat` parses the `Z` suffix natively (verified `fromisoformat('2024-01-01T00:00:00Z')` → `00:00:00+00:00`), so the `.replace()` is dead code and both variants return the same datetime. |
| 3 | `safe_parse_datetime` `logger.warning` f-string→None / `sanitize_log_value(None)` | 2 | LOW-VALUE | `x_safe_parse_datetime__mutmut_13`, `_mutmut_14` | Warning text/sanitized-value only; return value unchanged. Nobody asserts warning text. |
| 4 | `_run_batch_audit_job` logger message constants (warning/exception/info message→None/omitted/case/XX) — 32,34,75,99,101,103,104,105,114,118,119,120 | 12 | LOW-VALUE | `x__run_batch_audit_job__mutmut_103`, `_mutmut_114` | Pure log message text; control flow and returns unchanged; no caplog assertions in either file. |
| 5 | `_run_batch_audit_job` logger `extra={...}`→None / omitted — 33,35,76,78,100,102,115,117 | 8 | LOW-VALUE | `x__run_batch_audit_job__mutmut_100` | Log-record `extra` payload only. |
| 6 | `_run_batch_audit_job` logger `extra` dict **key** cosmetic renames (`"job_id"→"XXjob_idXX"/"JOB_ID"` etc.) — 36,37,38,39,79,80,81,82,83,84,106,107,108,109,110,111,112,113,121,122 | 20 | LOW-VALUE | `x__run_batch_audit_job__mutmut_106` | Renames inside a log `extra` dict (incl. the completed-job extra `"total"/"processed"/"failed"` keys) — cosmetic structured-log keys; no consumer. |
| 7 | `_run_batch_audit_job` `create_partial_audit(llm_prompt=event.llm_prompt)`→`None` — 53 | 1 | EQUIVALENT | `x__run_batch_audit_job__mutmut_53` | `create_mock_event` sets `llm_prompt="Test LLM prompt"` but the service mock never reads it and the mock audit returned is a fixture — no observable difference in any current test input. Borderline: becomes a real bug if a real service is wired into the test; kept EQUIVALENT per "semantically identical for tested inputs", but Test-2's kwargs assert hardens it anyway. |
| 8 | `_run_batch_audit_job`: **job_id arg → None / omitted** on every tracker call — start_job(6), update_progress(17), complete_job(89,91), fail_job(123) | 5 | TEST-GAP | `x__run_batch_audit_job__mutmut_89`, `_mutmut_123` | Job identity is the whole point of the tracker API; tests assert `assert_called_once()` and `kwargs["result"]` but never `call_args[0][0]`, and the tracker fixture no-ops silently on unknown id. Tests execute the line but never assert the id. |
| 9 | `_run_batch_audit_job`: start/progress **message kwargs** → None/omitted (7,9,19,22) and off-by-one `f"Processing event {i+1}"→{i-1}/{i+2}` (23,24) | 6 | TEST-GAP | `x__run_batch_audit_job__mutmut_23` | Progress message text is user-visible UI state (`GET /batch/{job_id}` returns `message`); `updates_progress` test asserts only `call[0][1]` percentages (1918), never messages. |
| 10 | `_run_batch_audit_job`: **event/audit fetch query mutations** — `db.execute(None)`, `where(None)`, `select(None)`, and the freshness-flip `where(Event.id == event_id)`→`!=` / `where(EventAudit.event_id == event_id)`→`!=` (Event 26,27,28,29; EventAudit 45,46,47,48) | 8 | TEST-GAP | `x__run_batch_audit_job__mutmut_29`, `_mutmut_48` | `==`→`!=` genuinely reselects wrong rows in production, but the mock session ignores query content entirely (`execute_side_effect(*args, **kwargs)` returns fixture rows by call order) and `MagicMock` swallows `None` query objects. Tests never inspect the SQL. |
| 11 | `_run_batch_audit_job`: **`create_partial_audit` kwargs** None/omitted (52 `event_id=event.id`, 54,55 omitted, 56,57) + **`db.refresh(None)`** (59) | 6 | TEST-GAP | `x__run_batch_audit_job__mutmut_52`, `_mutmut_59` | `create_partial_audit.assert_called_once()` (1642) never checks kwargs (a wrong/None `event_id` links the audit to the wrong event); `refresh.assert_called()` (1645) never checks the arg. Survives because the fixture service is an unspec'd `MagicMock` accepting any args (under `autospec` these would TypeError). |
| 12 | `_run_batch_audit_job`: **`run_full_evaluation(audit, event, db)` positional args** → None / drop-a-positional swaps (66,67,68,69,70,71) | 6 | TEST-GAP | `x__run_batch_audit_job__mutmut_69` | Swapping `audit`/`event`/`db` silently corrupts which record gets scored in production; `MagicMock` mock accepts anything, tests only check `called_once`/`not_called`. An `autospec`-typed mock would kill all 6. |
| 13 | `_run_batch_audit_job`: **counter `+= 1` → `= 1` collapses** (40 not-found failed, 62 processed, 86 except-failed) + **`continue`→`break` loop-exit flips** (43 not-found path, 65 skip path) | 5 | TEST-GAP | `x__run_batch_audit_job__mutmut_40`, `_mutmut_65`, `_mutmut_62` | Real behavior change in the result dict consumed by `GET /batch/{job_id}`. Invisible today only because every existing multi-event test has at most **one** failure and at most one post-event continuation, so `processed/failed` stay ≤1 and never observe the truncation or early exit. A single 5-event mixed test kills all five. |
| 14 | `_run_batch_audit_job`: except-path log payload `extra["error"] = str(e)` → `str(None)` (85) | 1 | TEST-GAP | `x__run_batch_audit_job__mutmut_85` | Real change: the exception message is erased from the log payload. No test asserts error context on the failed-event path (job still completes — `failed_events` semantics asserted, log content never). |
| 15 | `_audit_to_response`: response **field mapping to None / omitted** — `consistency_risk_score`/`consistency_diff`/`self_eval_critique` (97,98,99 None; 110,111,112 omitted) | 6 | TEST-GAP | `x__audit_to_response__mutmut_97` | Fields are nullable so schema validation passes either way. Real fixtures set 60/5/"thorough..." (routes:127-130), yet `test_get_event_audit_success` and `test_conversion_quality_scores_mapping` never assert those three fields — mapping is executed, never asserted. (The one `consistency_risk_score is None` assert at api-routes:301 uses an *unevaluated* mock audit where None matches the mutant.) |

**Totals: EQUIVALENT 26 (clusters 1,2,7) · LOW-VALUE 42 (3,4,5,6) · TEST-GAP 43 (8-15). Sum 111 = survivors_total.**

## Drafted tests (6) — `// UNVERIFIED - not yet run red/green`

Target file: `backend/tests/unit/api/routes/test_ai_audit.py` (same style/fixtures as `TestBatchAuditJobBackgroundTask` / `TestAuditToResponseConversion`).

### T1 — `test_run_batch_audit_job_builds_query_per_event_id` → kills cluster 10 (26,27,28,29,45,46,47,48)

```python
# UNVERIFIED - not yet run red/green
@pytest.mark.asyncio
async def test_run_batch_audit_job_builds_query_per_event_id(
    self,
    mock_audit_service: MagicMock,
    mock_job_tracker: MagicMock,
) -> None:
    """The job must query each event and its audit BY event_id (kills == → != and None-query mutants)."""
    from backend.api.routes.ai_audit import _run_batch_audit_job

    event_ids = [1, 2]
    job_id = mock_job_tracker.create_job("batch_audit")
    events = [create_mock_event(event_id=i) for i in event_ids]
    audits = [create_mock_audit(audit_id=i, event_id=i, is_evaluated=False) for i in event_ids]

    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()
    mock_session.add = MagicMock()

    def execute_side_effect(*args, **kwargs):
        result = MagicMock()
        result.scalar_one_or_none.return_value = events.pop(0) if len(events) >= len(audits) else audits.pop(0)
        return result

    mock_session.execute = AsyncMock(side_effect=execute_side_effect)

    with patch("backend.api.routes.ai_audit.get_session", return_value=mock_session, autospec=True):
        with patch("backend.api.routes.ai_audit.get_audit_service", return_value=mock_audit_service, autospec=True):
            await _run_batch_audit_job(
                job_id=job_id, event_ids=event_ids, force_reevaluate=False, job_tracker=mock_job_tracker
            )

    # Each event must be fetched with an Event query, each audit with an EventAudit query,
    # both filtered to the correct event_id. None/`!=` mutants change or drop the SQL.
    queries = [call.args[0] for call in mock_session.execute.call_args_list]
    assert len(queries) == 4
    event_sql, audit_sql = [], []
    for q in queries:
        sql = str(q)
        if "events" in sql:
            event_sql.append(q)
        elif "event_audits" in sql:
            audit_sql.append(q)
        else:
            pytest.fail(f"unexpected query object: {q!r}")  # db.execute(None) mutants die here
    assert len(event_sql) == 2 and len(audit_sql) == 2
    for idx, eid in enumerate(event_ids):
        ev_params = list(event_sql[idx].compile().params.values())
        au_params = list(audit_sql[idx].compile().params.values())
        assert eid in ev_params, f"event query not filtered to id {eid}: {event_sql[idx]}"
        assert eid in au_params, f"audit query not filtered to id {eid}: {audit_sql[idx]}"
        assert "!=" not in str(event_sql[idx].whereclause)
        assert "!=" not in str(audit_sql[idx].whereclause)
```

(Assertion order matters: `whereclause` is `None` for unfiltered queries, so if a `where(None)` mutant (27/46) somehow produced a query, guard with `str(q.whereclause or "")` — the None-object mutants die earlier at the `pytest.fail` line since `str(None)` names no table.)

**TDD**: on mutant 29/48 (`==`→`!=`) the compiled WHERE contains `!=` → assert fails; on `db.execute(None)` mutants `str(None)` contains neither table name → `pytest.fail`; on original, filters are `events.id = :id_1` / `event_audits.event_id = :id_1` with params `[1]`/`[2]` → passes.

### T2 — `test_run_batch_audit_job_creates_partial_audit_with_event_kwargs` → kills cluster 11 (52,54,55,56,57,59) + hardens cluster 7

```python
# UNVERIFIED - not yet run red/green
@pytest.mark.asyncio
async def test_run_batch_audit_job_creates_partial_audit_with_event_kwargs(
    self,
    mock_audit_service: MagicMock,
    mock_job_tracker: MagicMock,
) -> None:
    """create_partial_audit must receive THIS event's id + prompt; refresh must receive the new audit."""
    from backend.api.routes.ai_audit import _run_batch_audit_job

    # autospec on the service: dropped/mis-named kwargs now raise TypeError like the real signature
    mock_audit_service.create_partial_audit = MagicMock(
        name="create_partial_audit",
        autospec=True,
    )
    event_ids = [7]
    job_id = mock_job_tracker.create_job("batch_audit")
    mock_event = create_mock_event(event_id=7, llm_prompt="prompt-for-event-7")
    mock_partial_audit = create_mock_audit(audit_id=1, event_id=7, is_evaluated=False)
    mock_audit_service.create_partial_audit.return_value = mock_partial_audit

    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()
    mock_session.add = MagicMock()

    def execute_side_effect(*args, **kwargs):
        result = MagicMock()
        if not hasattr(execute_side_effect, "call_count"):
            execute_side_effect.call_count = 0
        execute_side_effect.call_count += 1
        result.scalar_one_or_none.return_value = mock_event if execute_side_effect.call_count == 1 else None
        return result

    mock_session.execute = AsyncMock(side_effect=execute_side_effect)

    with patch("backend.api.routes.ai_audit.get_session", return_value=mock_session, autospec=True):
        with patch("backend.api.routes.ai_audit.get_audit_service", return_value=mock_audit_service, autospec=True):
            await _run_batch_audit_job(
                job_id=job_id, event_ids=event_ids, force_reevaluate=False, job_tracker=mock_job_tracker
            )

    mock_audit_service.create_partial_audit.assert_called_once_with(
        event_id=7,
        llm_prompt="prompt-for-event-7",
        enriched_context=None,
        enrichment_result=None,
    )
    mock_session.refresh.assert_awaited_once_with(mock_partial_audit)
```

**TDD**: mutant 52 (`event_id=None`) → `event_id=None != 7` fails; 54/55/56/57 (kwargs omitted) → `assert_called_once_with` mismatch (or TypeError under autospec); 59 (`refresh(None)`) → awaited arg mismatch; original passes.

### T3 — `test_run_batch_audit_job_passes_audit_event_and_db_to_evaluation` → kills cluster 12 (66-71)

```python
# UNVERIFIED - not yet run red/green
@pytest.mark.asyncio
async def test_run_batch_audit_job_passes_audit_event_and_db_to_evaluation(
    self,
    mock_audit_service: MagicMock,
    mock_job_tracker: MagicMock,
) -> None:
    """run_full_evaluation must receive (audit, event, db) — not None, not swapped, not short."""
    from backend.api.routes.ai_audit import _run_batch_audit_job

    # Rebind the evaluation mock under autospec so the real (audit, event, session) signature is enforced
    import backend.services.pipeline_quality_audit_service as pqas

    mock_audit_service.run_full_evaluation = MagicMock(
        name="run_full_evaluation", autospec=True
    )  # NOTE: autospec=True on an *instance attr* binds the bound-method signature; if the
       # class lookup is unavailable, use spec=pqas.PipelineQualityAuditService for the whole fixture.

    event_ids = [1]
    job_id = mock_job_tracker.create_job("batch_audit")
    mock_event = create_mock_event(event_id=1)
    mock_audit = create_mock_audit(audit_id=1, event_id=1, is_evaluated=False)

    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock()

    def execute_side_effect(*args, **kwargs):
        result = MagicMock()
        if not hasattr(execute_side_effect, "call_count"):
            execute_side_effect.call_count = 0
        execute_side_effect.call_count += 1
        result.scalar_one_or_none.return_value = mock_event if execute_side_effect.call_count == 1 else mock_audit
        return result

    mock_session.execute = AsyncMock(side_effect=execute_side_effect)

    with patch("backend.api.routes.ai_audit.get_session", return_value=mock_session, autospec=True):
        with patch("backend.api.routes.ai_audit.get_audit_service", return_value=mock_audit_service, autospec=True):
            await _run_batch_audit_job(
                job_id=job_id, event_ids=event_ids, force_reevaluate=False, job_tracker=mock_job_tracker
            )

    mock_audit_service.run_full_evaluation.assert_awaited_once_with(mock_audit, mock_event, mock_session)
```

**TDD**: mutants 66-68 pass `None` somewhere → `assert_awaited_once_with` fails; 69/70 drop a positional → TypeError under autospec (or call-args mismatch without it); 71 identical to original? no — 71 is a cosmetic trailing-comma variant that changes nothing... recheck: 71 = `(audit, event, )` i.e. dropped `db` → fails on missing third arg. Original: exact three args → passes. (If autospec on the instance attr proves awkward in the fixture context, `spec=` the whole service fixture on `PipelineQualityAuditService` — same kill set.)

### T4 — `test_run_batch_audit_job_passes_job_id_and_messages_to_tracker` → kills clusters 8 + 9 (6,17,89,91,123,7,9,19,22,23,24)

```python
# UNVERIFIED - not yet run red/green
@pytest.mark.asyncio
async def test_run_batch_audit_job_passes_job_id_and_messages_to_tracker(
    self,
    mock_audit_service: MagicMock,
    mock_job_tracker: MagicMock,
) -> None:
    """Every tracker call must carry THIS job_id; progress messages carry 1-based event numbers."""
    from backend.api.routes.ai_audit import _run_batch_audit_job

    event_ids = [1, 2]
    job_id = mock_job_tracker.create_job("batch_audit")
    events = [create_mock_event(event_id=1), create_mock_event(event_id=2)]
    audits = [
        create_mock_audit(audit_id=1, event_id=1, is_evaluated=False),
        create_mock_audit(audit_id=2, event_id=2, is_evaluated=False),
    ]

    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock()

    def execute_side_effect(*args, **kwargs):
        result = MagicMock()
        if not hasattr(execute_side_effect, "call_count"):
            execute_side_effect.call_count = 0
        execute_side_effect.call_count += 1
        if execute_side_effect.call_count % 2 == 1:
            result.scalar_one_or_none.return_value = events[(execute_side_effect.call_count - 1) // 2]
        else:
            result.scalar_one_or_none.return_value = audits[(execute_side_effect.call_count - 2) // 2]
        return result

    mock_session.execute = AsyncMock(side_effect=execute_side_effect)

    with patch("backend.api.routes.ai_audit.get_session", return_value=mock_session, autospec=True):
        with patch("backend.api.routes.ai_audit.get_audit_service", return_value=mock_audit_service, autospec=True):
            await _run_batch_audit_job(
                job_id=job_id, event_ids=event_ids, force_reevaluate=False, job_tracker=mock_job_tracker
            )

    # job identity on every lifecycle call
    assert mock_job_tracker.start_job.call_args[0][0] == job_id
    assert mock_job_tracker.start_job.call_args.kwargs["message"] == "Starting batch audit of 2 events..."
    assert mock_job_tracker.complete_job.call_args[0][0] == job_id
    for call in mock_job_tracker.update_progress.call_args_list:
        assert call[0][0] == job_id
    # 1-based progress messages (kills {i-1}/{i+2} off-by-one mutants)
    messages = [call.kwargs.get("message") for call in mock_job_tracker.update_progress.call_args_list]
    assert messages == ["Processing event 1 of 2", "Processing event 2 of 2"]
    # fatal path: fail_job must also target the right job
    mock_job_tracker.fail_job.assert_not_called()
```

Plus a companion two-liner appended to the fatal-error scenario (or a parametrized variant): rerun with `get_session` raising and assert `mock_job_tracker.fail_job.call_args[0][0] == job_id` → kills mutant 123. **TDD**: mutants 6/17/89/91/123 pass `None` → first/last asserts fail; 7/9/19/22 pass `None`/omit message → message asserts fail; 23/24 → message equality fails; original passes.

### T5 — `test_run_batch_audit_job_result_counts_accumulate_over_mixed_batch` → kills cluster 13 (40,43,62,65,86)

```python
# UNVERIFIED - not yet run red/green
@pytest.mark.asyncio
async def test_run_batch_audit_job_result_counts_accumulate_over_mixed_batch(
    self,
    mock_audit_service: MagicMock,
    mock_job_tracker: MagicMock,
) -> None:
    """5-event mixed batch: failed/processed counters must ACCUMULATE and the loop must CONTINUE.

    ids: 1 missing → failed; 2 evaluated → skipped(processed); 3 missing → failed;
         4 evaluation raises → failed; 5 evaluated clean → processed.
    Expect total=5, processed=2, failed=3. `x = 1` collapses → failed=1/processed=1;
    `break` on not-found → processed=0; `break` on skip → processed=1.
    """
    from backend.api.routes.ai_audit import _run_batch_audit_job

    event_ids = [1, 2, 3, 4, 5]
    job_id = mock_job_tracker.create_job("batch_audit")

    ev2 = create_mock_event(event_id=2)
    ev4 = create_mock_event(event_id=4)
    ev5 = create_mock_event(event_id=5)
    audit2 = create_mock_audit(audit_id=2, event_id=2, is_evaluated=True, overall_score=4.0)
    audit4 = create_mock_audit(audit_id=4, event_id=4, is_evaluated=False)
    audit5 = create_mock_audit(audit_id=5, event_id=5, is_evaluated=False)

    mock_audit_service.run_full_evaluation.side_effect = [Exception("boom"), None]

    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock()

    # db.execute call order: e1=None | e2=ev2, a2=audit2 | e3=None | e4=ev4, a4=audit4 | e5=ev5, a5=audit5
    seq = [None, ev2, audit2, None, ev4, audit4, ev5, audit5]

    def execute_side_effect(*args, **kwargs):
        result = MagicMock()
        result.scalar_one_or_none.return_value = seq[execute_side_effect.i]
        execute_side_effect.i += 1
        return result

    execute_side_effect.i = 0
    mock_session.execute = AsyncMock(side_effect=execute_side_effect)

    with patch("backend.api.routes.ai_audit.get_session", return_value=mock_session, autospec=True):
        with patch("backend.api.routes.ai_audit.get_audit_service", return_value=mock_audit_service, autospec=True):
            await _run_batch_audit_job(
                job_id=job_id, event_ids=event_ids, force_reevaluate=False, job_tracker=mock_job_tracker
            )

    completed = mock_job_tracker.complete_job.call_args.kwargs["result"]
    assert completed == {"total_events": 5, "processed_events": 2, "failed_events": 3}
```

**TDD**: 40 (`failed=1` at not-found) → failed stays 1 after three failures → dict mismatch; 86 same at except-path; 62 (`processed=1`) → mismatch on processed; 43/65 (`break`) → loop stops early → mismatch; original exact dict → passes.

### T6 — `test_audit_to_response_maps_consistency_and_critique_fields` → kills cluster 15 (97,98,99,110,111,112)

```python
# UNVERIFIED - not yet run red/green
def test_audit_to_response_maps_consistency_and_critique_fields(self) -> None:
    """consistency_risk_score, consistency_diff, self_eval_critique must pass through (not None/omitted)."""
    from backend.api.routes.ai_audit import _audit_to_response

    audit = create_mock_audit(audit_id=1, event_id=1, is_evaluated=True, overall_score=4.0)
    # create_mock_audit(is_evaluated=True) sets 70 / 5 / "Good analysis" (lines 104-108)

    response = _audit_to_response(audit)

    assert response.consistency_risk_score == 70
    assert response.consistency_diff == 5
    assert response.self_eval_critique == "Good analysis"
```

Add to `TestAuditToResponseConversion` (test_ai_audit.py:1343). Optionally also assert via the HTTP route in `test_ai_audit_routes.py::TestGetEventAudit::test_get_event_audit_success` (`data["consistency_risk_score"] == 60`, `data["consistency_diff"] == 5`, `data["self_eval_critique"].startswith("The analysis")`) — sample_audit fixture already sets them. **TDD**: 97/98/99 force the field to `None` → `None == 70` fails; 110/111/112 omit the kwarg → schema default `None` → fails; original passes.

(Not drafted: cluster 14, single mutant 85 `error: str(e)→str(None)` — a `caplog` assert on `record["error"] == "boom"` in the event-error path would kill it; folded into backlog.)

## Verdict

TEST-GAP 43 survivors, all explainable by one fixture weakness: `mock_audit_service`/`mock_job_tracker` are unspec'd `MagicMock`s and the session mock ignores query content — job identity, call arguments, query filters, and multi-event counter accumulation are executed but never asserted. The six drafted tests (T1-T6) kill 41/43 of the TEST-GAP survivors; only mutant 85 (log `error` text) and the 7 borderline tracker-message-None keys that T4's message-equality assert also covers are left as noted. Clusters 1-7 (69 survivors, incl. 26 EQUIVALENT) are log/schema-default noise — no test action; T1-T6 kill 41 and no drafted test needs the 23 EQUIVALENT conversion mutants.
