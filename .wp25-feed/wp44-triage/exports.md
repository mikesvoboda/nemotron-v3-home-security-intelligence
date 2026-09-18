# WP4.4 Triage Dossier — `backend/api/routes/exports.py`

Source of truth: `mutants/backend/api/routes/exports.py.meta` → `exit_code_by_key`.
178 total mutants; **78 killed / 100 survived / 0 unchecked**. All 100 survivors triaged below.

Diffs were produced by locally diffing each `x_<fn>__mutmut_N` body in the mutant copy against
`backend/api/routes/exports.py` (`/tmp/wp44-exports/extract2.py`), cross-verified byte-identical
against `uv run mutmut show` for a sample of keys. No tests were executed; nothing in the repo was modified.

## Covering test file (single file for all three functions)

`backend/tests/unit/api/routes/test_exports.py` — 1477 lines.

| Function                 | Covering tests (mutmut-stats `tests_by_mangled_function_name`)                                                                                                | Weak-assertion sites                                                                                                                     |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| `_model_to_response`     | `TestModelToResponse::test_model_to_response_{pending_job,completed_job,with_progress}` (L124/L139/L153), plus `TestListExports::*`, `TestGetExportStatus::*` | L130-137, L145-151 — only 8 of the 13 `ExportJobResponse` fields are ever read                                                           |
| `_get_export_job`        | `TestGetExportJob::test_get_export_job_{found,not_found}` (L190/L208) + 24 endpoint tests via DI                                                              | L205 `assert_called_once()` (no arg check); L220 `"not found" in detail.lower()`                                                         |
| `run_export_job_with_db` | `TestRunExportJobWithDb::test_run_export_job_{success,with_filters,not_found,failure,failure_db_update_fails}` (L227-L374)                                    | L256-265, L334, L369-371, L409 — `assert_called_once()` everywhere; `job.total_items` / `job.current_step` / `job.started_at` never read |

**Why the 78 killed mutants died**: the tests do assert `job.status`, `job.progress_percent`,
`job.output_path`, `job.output_size_bytes`, `job.processed_items`, `job.error_message`, the
`camera_id`/`risk_level`/`start_date`/`end_date`/`reviewed` kwargs, and that each tracker/service
method was called _once_. Every surviving mutant sits in a value/argument the tests never read.

## Cluster table (counts sum to 100)

| #   | Cluster                                                                                                                                              | Fn                | Mutants (n)                                  | Cnt     | Class                                      | Evidence / rationale                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| --- | ---------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------- | -------------------------------------------- | ------- | ------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | `R-LOG-COMPLETED` — "Export job completed" `logger.info` msg + `extra` dict keys/`get()` key cosmetic                                                | run               | 82,83,85,86,87,88,89,90,91,92,93,94,95,96,97 | 15      | **EQUIVALENT**                             | pure observability text. All variants compile (verified) — `n=85` is a valid keyword-drop leaving `logger.info("Export job completed", )`, `n=82` a valid `msg=None`, so each only changes rendered log text/fields                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| 2a  | `R-LOG-NOTFOUND` — `logger.error("Export job not found in database", extra=...)` msg/key cosmetic                                                    | run               | 8,9,11,12,13,14,15,16                        | 8       | **EQUIVALENT**                             | log text + `extra` key spelling + valid `extra`-dropped forms; no behaviour change                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| 2b  | `R-LOG-SWALLOWED` — `logger.error(extra=...)` (msg keyword dropped) → `TypeError` swallowed by the broad `except Exception`                          | run               | 10                                           | 1       | **TEST-GAP**                               | Verified `logging.Logger.error()` with no msg raises `TypeError` (project logger is a plain `logging.Logger`). At L155 the TypeError is caught by the L202 `except`, so the not-found path stops being a bare `return` and ends in **`fail_job(job_id, "Logger.error() missing 1 required positional argument: 'msg'")`** — a spurious failure broadcast for a job that never existed. `test_run_export_job_not_found` passes anyway because it asserts only `export_events_with_progress.assert_not_called()`. One-line kill: add `mock_job_tracker.fail_job.assert_not_called()` to that test. (Contrast the _killed_ `R-LOG-EXC n=100`: the same drop at L204 sits inside the except block, so its TypeError escapes and fails the test — the mutation score here is partly an artifact of try/except placement, not of assertion strength) |
| 3   | `R-LOG-EXC` — `logger.exception("Export job failed", extra=...)` msg/key cosmetic                                                                    | run               | 98,99,101-106                                | 8       | **EQUIVALENT**                             | log text + `extra` key spelling only; `extra=None` is accepted by stdlib logging (verified). The _killed_ `n=100` (msg keyword dropped at L204) differs for a placement reason, not an assertion-strength one: a `TypeError` raised inside an `except` handler is not catchable by that same handler, so it reaches the test — whereas the identical drop inside the `try` (cluster 2b, L155) is swallowed                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| 4   | `R-LOG-UPDFAIL` — `logger.exception("Failed to update job failure status")` msg cosmetic                                                             | run               | 113-116                                      | 4       | **EQUIVALENT**                             | message string only                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| 5   | `M-RESULT-Guard` — `if status == COMPLETED and output_path:` → `or`                                                                                  | model_to_response | 13                                           | 1       | **TEST-GAP**                               | `or` is not equivalent to `and`: it diverges whenever exactly one operand is true. For a RUNNING/CANCELLED job that has an `output_path` (partial write, or a re-run), the mutant sets `response.result`, so the UI would offer a download for a job that is not complete. Both existing fixtures pair `COMPLETED`↔path and `PENDING`↔`None`, so the discriminating row is never generated. (The sibling flip `n=14` `!=` _is_ killed because the `COMPLETED`+path fixture inverts it.) Killed by Test D's added RUNNING-with-output_path block                                                                                                                                                                                                                                                                                              |
| 6   | `M-METAFIELDS` — `started_at` / `completed_at` / `filter_params` / `error_message` set to `None` or dropped from `ExportJobResponse(...)`            | model_to_response | 30,31,32,34,41,42,43,45                      | 8       | **TEST-GAP**                               | the sibling fields `id`/`status`/`export_type`/`export_format`/`progress`/`result` are all asserted (mutants n=24-29, 33, 35-40, 44 all **killed**); these four are never read. `error_message=None` silently blanks the failure reason that `ExportPanel.tsx:211` shows the user; `started_at`/`completed_at` drive the elapsed-time display at `ExportProgress.tsx:298-302`. Verified pydantic 2.13.5 preserves datetime identity, so an `is` assertion is valid                                                                                                                                                                                                                                                                                                                                                                             |
| 7   | `G-DETAIL` — 404 `detail=f"Export job not found: {job_id}"` → `None` / dropped                                                                       | get_export_job    | 9, 11                                        | 2       | **TEST-GAP**                               | `starlette.HTTPException` maps `detail=None` → `http.HTTPStatus(404).phrase == "Not Found"`, which **still satisfies** `test_exports.py:220` `"not found" in str(detail).lower()`. So the assertion passes on the mutant: a textbook weak assertion. The `{job_id}` echo is also entirely unasserted. (`n=11` drops the `detail=` keyword entirely — a valid trailing-comma call leaving the default `detail=None` — so it is killed by the same exact-equality assertion as `n=9`)                                                                                                                                                                                                                                                                                                                                                            |
| 8   | `G-SELECT` — `db.execute(select(ExportJob).where(ExportJob.id == job_id))` argument clobbered (`execute(None)`, `where(None)`, `select(None)`, `!=`) | get_export_job    | 2, 3, 4, 5                                   | 4       | **TEST-GAP**                               | `db` is an `AsyncMock`, so none of these raise; the test asserts only `assert_called_once()` (L205). The entire lookup predicate is unasserted — a `!=` lookup is a wrong-row bug that no test can see                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| 9   | `R-SELECT` — same `db.execute(select(...).where(...))` clobber in the background task                                                                | run               | 2, 3, 4, 5                                   | 4       | **TEST-GAP**                               | identical mechanism, identical `assert_called_once` blind spot (the run-job tests never inspect `db.execute.call_args` at all)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| 10  | `R-COUNTS` — `job.processed_items` / `job.total_items` = `export_result.get("event_count", 0)` key/default/whole-assignment clobbered                | run               | 64,66,69,70,71,72,73,74,75,76,77             | 11      | **TEST-GAP**                               | `test_exports.py:260` asserts `job.processed_items == 100` (kills n=62/63/65/67/68), but `job.total_items` is **never read by any test** and `response.progress.total_items` only ever comes from fixtures. `= None` (70) and default `0→None` (64,72) would raise a pydantic `ValidationError` downstream (`processed_items: int = Field(0, ge=0)`); `0→1` (69,77) and `get(0)` (73) corrupt the displayed count silently                                                                                                                                                                                                                                                                                                                                                                                                                     |
| 11  | `R-FAILJOB` — `job_tracker.fail_job(job_id, str(e))` identity/message clobbered                                                                      | run               | 117-121                                      | 5       | **TEST-GAP**                               | `fail_job.assert_called_once()` (L371, L409) checks arity, never args — so `fail_job(None, ...)` (wrong job → broadcast to nobody) and `fail_job(job_id, str(None))` (user sees `"None"` instead of the error) both pass. **Not an arity limitation**: verified a `MagicMock(spec=JobTracker)` silently accepts the dropped-positional forms `n=119`/`n=120`, which is exactly why they survived                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| 12  | `R-COMPLETEJOB` — `job_tracker.complete_job(job_id, result=export_result)` identity/payload clobbered                                                | run               | 78-81                                        | 4       | **TEST-GAP**                               | `complete_job.assert_called_once()` (L264) never checks that the broadcast carries `job_id` or the export result payload (the download path the UI consumes). `spec=` mock likewise tolerates the dropped-arg forms 80/81                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| 13  | `R-EXPORT-IDENT` — `export_events_with_progress(job_id=…, job_tracker=…, export_format=…)` clobbered/dropped                                         | run               | 27,28,29,36,37,38                            | 6       | **TEST-GAP**                               | `test_run_export_job_with_filters` (L298-302) asserts exactly five kwargs and **omits these three**; `test_run_export_job_success` only asserts `assert_called_once()`. `export_format=None` reaches the real service and breaks format dispatch; `job_id=None`/`job_tracker=None` break progress broadcasting                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| 14  | `R-STARTJOB-GAP` — `job_tracker.start_job(job_id, message=…)` identity clobbered/dropped                                                             | run               | 21, 23                                       | 2       | **TEST-GAP**                               | `start_job.assert_called_once()` (L263) — job_id identity is the routing key of the whole WS broadcast, never asserted                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| 15  | `R-CURRENTSTEP-DONE` — `job.current_step = "Complete"` → `None`/`XX…XX`/`"complete"`/`"COMPLETE"`                                                    | run               | 50-53                                        | 4       | **TEST-GAP**                               | `job.current_step` is **never read** in the run-job tests; `"Complete"` is the contract literal (it is what the fixtures at L108/L958/L1042… hand to the UI, and `ExportProgress.tsx` renders it)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| 16  | `R-CURRENTSTEP-RUN` — `job.current_step = f"Starting {export_format.upper()} export..."` → `None` / `.lower()`                                       | run               | 19, 20                                       | 2       | **TEST-GAP**                               | same unasserted field; the `.upper()` normalization is real user-visible text ("Starting CSV export...")                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| 17  | `R-EXPORT-COLUMNS` — `columns=columns` → `None` / dropped in the service call                                                                        | run               | 35, 44                                       | 2       | **LOW-VALUE**                              | real behaviour change, but the existing suite's own contract treats `columns` as out of scope: `test_run_export_job_with_filters` passes `columns=None` and asserts only the five filter kwargs (`camera_id`, `risk_level`, `start_date`, `end_date`, `reviewed`). Column selection is the service's contract (`test_export_service.py`), not this route's                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| 18  | `R-STARTJOB-MSG` — `start_job(message=…)` cosmetic (`None` / dropped / `.lower()`)                                                                   | run               | 22, 24, 25                                   | 3       | **LOW-VALUE**                              | a transient human-readable status string, never asserted anywhere. Asserting the exact wording would just freeze copy                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| 19  | `R-RUNNING-STATE` — `job.status = ExportJobStatus.RUNNING` / `job.started_at = utc_now()` set to `None` in the _early_ (pre-export) write            | run               | 17, 18                                       | 2       | **LOW-VALUE**                              | not dead exactly, but never observable in a unit test: both are overwritten by `job.status = COMPLETED` / never re-asserted, and `AsyncMock`'s `commit()` does not flush. Only reachable via a mid-flight observer or integration test                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| 20  | `R-REFRESH` — `await db.refresh(job)` → `db.refresh(None)` (L180 success path, L208 failure path)                                                    | run               | 45, 107                                      | 2       | **LOW-VALUE**                              | `db` is an `AsyncMock`, so the call is a no-op in both original and mutant; observable only against a real session (integration layer). Note `n=46`/`n=109` (`job.status` after the refresh) _are_ killed, so the post-refresh effect is covered                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| 21  | `R-COMPLETED-AT` — `job.completed_at = utc_now()` → `None` (L182 and L211)                                                                           | run               | 47, 110                                      | 2       | **LOW-VALUE**                              | the test's own `completed_export_job` fixture sets `completed_at=now`, so a naive `job.completed_at is not None` would be a **false-green**. Killable only by pinning the pre-value to `None` and asserting freshness + `<= utc_now()`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
|     | **TOTAL**                                                                                                                                            |                   |                                              | **100** | 35 EQUIVALENT / 54 TEST-GAP / 11 LOW-VALUE |                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |

### Killed-survivor asymmetry worth recording for WP4.4

- `run` L185-187 `export_result.get(...)`: `file_path`/`file_size`/`processed_items` key mutants are
  **killed**, `total_items` key mutants **survive** → the tests read `processed_items` but never `total_items`.
- `model_to_response` L80-90: every field mutant is **killed** except L86/87/88/90 → those four fields are the gap.
- `run` L155 vs L204 — the same mutation (`logger.<method>(extra=...)`, msg dropped) **survives** at
  L155 (`n=10`, inside the `try` → the broad `except Exception` swallows the `TypeError` and the
  not-found path silently gains a `fail_job` broadcast) but is **killed** at L204 (`n=100`, inside
  the `except` → the `TypeError` has no enclosing handler and reaches the test). Part of this
  module's mutation score is try/except placement, not assertion strength; cluster 2b is the one
  survivor in that pair with a real, cheaply-assertable behaviour change.
- `_get_export_job` L112 `status_code` mutants are **killed** while L113 `detail` mutants **survive** →
  status is asserted, detail is only substring-matched against a value that degrades to `"Not Found"`.

## Drafted tests (seven tests A-G, covering the highest-value TEST-GAP clusters)

All target `backend/tests/unit/api/routes/test_exports.py` and reuse its existing fixtures
(`mock_db`, `mock_job_tracker`, `mock_export_service`, `sample_export_job`, `completed_export_job`).
Every assertion below was mechanically validated against the project venv
(`sqlalchemy 2.0.53`, `pydantic 2.13.5`) for the mutant/`!=`/`None` forms.

### Test A — kills `G-SELECT` + `R-SELECT` (8 survivors)

Adds `_assert_job_lookup(stmt, job_id)`; the same predicate must be asserted for both functions because
`_get_export_job` and `run_export_job_with_db` build their own copies of the query.

```python
def _assert_job_lookup(stmt: object, job_id: str) -> None:
    """Assert `stmt` is `select(ExportJob).where(ExportJob.id == job_id)`.

    `db` is an AsyncMock in these tests, so a clobbered `db.execute(...)` argument
    never raises — the only way to kill select/where clobber mutants is to inspect
    the statement that was actually handed to the session.
    """
    import operator

    from sqlalchemy import Select
    from sqlalchemy.sql.elements import BinaryExpression

    from backend.models.export_job import ExportJob

    assert isinstance(stmt, Select), f"expected a Select, got {type(stmt).__name__}"
    # `select(None)` survives the isinstance check but loses the entity and the FROM.
    assert stmt.column_descriptions[0]["entity"] is ExportJob
    assert [f.name for f in stmt.get_final_froms()] == ["export_jobs"]

    where = getattr(stmt, "whereclause", None)  # `where(None)` => Null, not BinaryExpression
    assert isinstance(where, BinaryExpression), f"no WHERE predicate: {where!r}"
    assert where.left.name == "id"
    assert where.operator is operator.eq, "lookup predicate is no longer equality"
    assert where.right.value == job_id


class TestGetExportJob:
    """... existing tests ..."""

    @pytest.mark.asyncio
    async def test_get_export_job_queries_by_id(
        self,
        mock_db: AsyncMock,
        sample_export_job: ExportJob,
    ) -> None:
        """The 404-vs-found decision must come from an `id == job_id` lookup.

        TDD: `where`/`select`/`execute` argument clobbers (mutmut_2-5) fail the
        assertions below; the original passes.
        """
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_export_job
        mock_db.execute.return_value = mock_result

        await _get_export_job(sample_export_job.id, mock_db)

        _assert_job_lookup(mock_db.execute.call_args.args[0], sample_export_job.id)
```

and inside `TestRunExportJobWithDb`:

```python
    @pytest.mark.asyncio
    async def test_run_export_job_loads_job_by_id(
        self,
        mock_db: AsyncMock,
        mock_export_service: MagicMock,
        mock_job_tracker: MagicMock,
        sample_export_job: ExportJob,
    ) -> None:
        """The background task must re-load its own row by `id == job_id`.

        TDD: kills run_export_job_with_db mutmut_2-5 (execute/where/select clobbers),
        green on the original.
        """
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_export_job
        mock_db.execute.return_value = mock_result

        await run_export_job_with_db(
            job_id=sample_export_job.id,
            export_format="csv",
            camera_id=None,
            risk_level=None,
            start_date=None,
            end_date=None,
            reviewed=None,
            columns=None,
            export_service=mock_export_service,
            job_tracker=mock_job_tracker,
            db=mock_db,
        )

        _assert_job_lookup(mock_db.execute.call_args_list[0].args[0], sample_export_job.id)
```

### Test B — kills `R-COUNTS` (11 survivors)

```python
    @pytest.mark.asyncio
    async def test_run_export_job_records_event_counts_on_job(
        self,
        mock_db: AsyncMock,
        mock_export_service: MagicMock,
        mock_job_tracker: MagicMock,
        sample_export_job: ExportJob,
    ) -> None:
        """Both item counts must be persisted from `event_count`, defaulting to 0.

        `total_items` is a distinct assignment (exports.py:188) that no test read, so
        all of its key/default clobbers survived; `processed_items` only survived its
        default-value clobbers. A missing `event_count` key must land on 0, not `None`
        (ExportJobProgress.processed_items is a non-null int, so `None` breaks the
        response schema).

        TDD: kills run_export_job_with_db mutmut_64/66/69/70/71/72/73/74/75/76/77;
        green on the original.
        """
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_export_job
        mock_db.execute.return_value = mock_result
        mock_export_service.export_events_with_progress.return_value = {
            "file_path": "/api/exports/test.csv",
            "file_size": 12345,
            "event_count": 77,
        }

        await run_export_job_with_db(
            job_id=sample_export_job.id,
            export_format="csv",
            camera_id=None,
            risk_level=None,
            start_date=None,
            end_date=None,
            reviewed=None,
            columns=None,
            export_service=mock_export_service,
            job_tracker=mock_job_tracker,
            db=mock_db,
        )

        assert sample_export_job.processed_items == 77
        assert sample_export_job.total_items == 77
        assert sample_export_job.current_step == "Complete"  # paired L184 write

        # Missing event_count must default to 0, never None.
        mock_export_service.export_events_with_progress.return_value = {
            "file_path": "/api/exports/test.csv",
            "file_size": 0,
        }
        sample_export_job.processed_items = 0
        sample_export_job.total_items = None

        await run_export_job_with_db(
            job_id=sample_export_job.id,
            export_format="csv",
            camera_id=None,
            risk_level=None,
            start_date=None,
            end_date=None,
            reviewed=None,
            columns=None,
            export_service=mock_export_service,
            job_tracker=mock_job_tracker,
            db=mock_db,
        )

        assert sample_export_job.processed_items == 0
        assert sample_export_job.total_items == 0
```

### Test C — kills `R-FAILJOB` + `R-COMPLETEJOB` + `R-STARTJOB-GAP` + `R-EXPORT-IDENT` (17 survivors)

One `call_args` assertion per collaborator; `MagicMock(spec=...)` tolerates dropped positional
arguments (verified), so the `call_args` form is what does the killing.

```python
    @pytest.mark.asyncio
    async def test_run_export_job_passes_job_id_to_every_collaborator(
        self,
        mock_db: AsyncMock,
        mock_export_service: MagicMock,
        mock_job_tracker: MagicMock,
        sample_export_job: ExportJob,
    ) -> None:
        """Every hand-off must carry *this* job's id (and the live tracker/format).

        `assert_called_once()` checks arity only, so identity clobbers survived: a
        job_id of None routes the WebSocket broadcast to nobody, and export_format=None
        reaches the real service. The spec'd tracker mock silently accepts the dropped
        positional-argument forms, so assert the recorded call rather than the count.

        TDD: kills run_export_job_with_db mutmut_21/23 (start_job), 27/28/29/36/37/38
        (export service identity), 78/79/80/81 (complete_job), 117/119/120 (fail_job —
        covered by the failure-path test below); green on the original.
        """
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_export_job
        mock_db.execute.return_value = mock_result

        await run_export_job_with_db(
            job_id=sample_export_job.id,
            export_format="csv",
            camera_id=None,
            risk_level=None,
            start_date=None,
            end_date=None,
            reviewed=None,
            columns=None,
            export_service=mock_export_service,
            job_tracker=mock_job_tracker,
            db=mock_db,
        )

        start_call = mock_job_tracker.start_job.call_args
        assert start_call.args[0] == sample_export_job.id

        export_kwargs = mock_export_service.export_events_with_progress.call_args.kwargs
        assert export_kwargs["job_id"] == sample_export_job.id
        assert export_kwargs["job_tracker"] is mock_job_tracker
        assert export_kwargs["export_format"] == "csv"

        complete_call = mock_job_tracker.complete_job.call_args
        assert complete_call.args[0] == sample_export_job.id
        # The completion broadcast must still carry the download payload the UI reads.
        assert complete_call.kwargs["result"] == {
            "file_path": "/api/exports/test.csv",
            "file_size": 12345,
            "event_count": 100,
        }

    @pytest.mark.asyncio
    async def test_run_export_job_failure_reports_error_to_tracker(
        self,
        mock_db: AsyncMock,
        mock_export_service: MagicMock,
        mock_job_tracker: MagicMock,
        sample_export_job: ExportJob,
    ) -> None:
        """The failure hand-off must carry the job id and the real error text.

        TDD: kills run_export_job_with_db mutmut_117-121 (fail_job identity /
        str(None) / dropped args); green on the original.
        """
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_export_job
        mock_db.execute.return_value = mock_result
        mock_export_service.export_events_with_progress.side_effect = RuntimeError("disk full")

        await run_export_job_with_db(
            job_id=sample_export_job.id,
            export_format="csv",
            camera_id=None,
            risk_level=None,
            start_date=None,
            end_date=None,
            reviewed=None,
            columns=None,
            export_service=mock_export_service,
            job_tracker=mock_job_tracker,
            db=mock_db,
        )

        fail_call = mock_job_tracker.fail_job.call_args
        assert fail_call.args[0] == sample_export_job.id
        assert fail_call.args[1] == "disk full"
        assert fail_call.args[1] != "None"
```

### Test D — kills `M-METAFIELDS` + `M-RESULT-Guard` (9 survivors)

```python
class TestModelToResponse:
    """... existing tests ..."""

    def test_model_to_response_preserves_timing_filter_and_error_fields(self) -> None:
        """started_at / completed_at / filter_params / error_message must be forwarded.

        The sibling fields are all asserted; these four were never read, so clobbering
        any of them to None (or dropping the keyword) survived. error_message is what
        ExportPanel shows on a failed export, and started_at/completed_at drive the
        elapsed-time display in ExportProgress.

        TDD: kills _model_to_response mutmut_30/31/32/34/41/42/43/45; green on the original.
        """
        started = datetime(2025, 1, 12, 14, 0, tzinfo=UTC)
        completed = datetime(2025, 1, 12, 14, 5, tzinfo=UTC)
        filters = '{"camera_id": "front_door", "risk_level": "high"}'

        job = ExportJob(
            id=str(uuid4()),
            status=ExportJobStatus.FAILED,
            export_type="events",
            export_format="csv",
            total_items=10,
            processed_items=4,
            progress_percent=40,
            current_step="Processing events...",
            created_at=started,
            started_at=started,
            completed_at=completed,
            estimated_completion=None,
            output_path=None,
            output_size_bytes=None,
            error_message="Export error",
            filter_params=filters,
        )

        response = _model_to_response(job)

        # pydantic preserves the exact datetime object for a datetime-typed field,
        # so identity holds on the original and breaks when the value is replaced.
        assert response.started_at == started
        assert response.started_at is started
        assert response.completed_at == completed
        assert response.completed_at is completed
        assert response.filter_params == filters
        assert response.error_message == "Export error"

    def test_model_to_response_hides_result_until_completed(self) -> None:
        """`result` requires status COMPLETED *and* an output_path.

        Both existing fixtures pair the two conditions, so the `and`→`or` flip
        (mutmut_13) never diverged: a RUNNING job holding a partial `output_path`
        would expose a download link for an incomplete export.

        TDD: on the mutant the RUNNING block below gets `result is not None`
        (the `or` short-circuits on `output_path`); the original keeps it None.
        """
        for status in (ExportJobStatus.PENDING, ExportJobStatus.RUNNING):
            job = ExportJob(
                id=str(uuid4()),
                status=status,
                export_type="events",
                export_format="csv",
                total_items=10,
                processed_items=6,
                progress_percent=60,
                current_step="Processing events...",
                created_at=datetime(2025, 1, 12, 14, 0, tzinfo=UTC),
                started_at=datetime(2025, 1, 12, 14, 0, tzinfo=UTC),
                completed_at=None,
                estimated_completion=None,
                output_path="/api/exports/events_export_20250112.csv",
                output_size_bytes=12345,
                error_message=None,
                filter_params=None,
            )

            response = _model_to_response(job)

            assert response.status == ExportJobStatusEnum(status.value)
            assert response.result is None, (
                f"{status} job must not expose a download result"
            )
```

### Test E — kills `G-DETAIL` (2 survivors)

```python
class TestGetExportJob:
    """... existing tests ..."""

    @pytest.mark.asyncio
    async def test_get_export_job_not_found_detail_names_the_job(self, mock_db: AsyncMock) -> None:
        """The 404 detail must name the missing job id.

        The existing test only checks `"not found" in detail.lower()`, which still
        passes when `detail` is dropped: starlette substitutes the 404 reason phrase
        "Not Found" for a None detail. Assert the full message instead of a substring.

        TDD: kills _get_export_job mutmut_9 (detail=None) and mutmut_11 (detail= dropped);
        green on the original.
        """
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await _get_export_job("missing-job-42", mock_db)

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Export job not found: missing-job-42"
        assert exc_info.value.detail != "Not Found"
```

### Test F — kills `R-CURRENTSTEP-DONE` + `R-CURRENTSTEP-RUN` (6 survivors)

```python
    @pytest.mark.asyncio
    async def test_run_export_job_publishes_progress_steps(
        self,
        mock_db: AsyncMock,
        mock_export_service: MagicMock,
        mock_job_tracker: MagicMock,
        sample_export_job: ExportJob,
    ) -> None:
        """current_step must carry the upper-cased format, then the literal "Complete".

        `job.current_step` was never read by this class, so every string clobber
        survived; "Complete" is the literal the fixtures hand to ExportProgress.
        The pre-export write is captured by wrapping db.commit so the RUNNING-state
        value is observable despite AsyncMock.

        TDD: kills run_export_job_with_db mutmut_19/20 (`.lower()`) and 50-53
        ("Complete" clobbered); green on the original.
        """
        steps: list[str] = []

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_export_job
        mock_db.execute.return_value = mock_result
        original_commit = mock_db.commit

        async def capture_commit() -> None:
            steps.append(sample_export_job.current_step)
            await original_commit()

        mock_db.commit.side_effect = capture_commit

        await run_export_job_with_db(
            job_id=sample_export_job.id,
            export_format="csv",
            camera_id=None,
            risk_level=None,
            start_date=None,
            end_date=None,
            reviewed=None,
            columns=None,
            export_service=mock_export_service,
            job_tracker=mock_job_tracker,
            db=mock_db,
        )

        assert steps == ["Starting CSV export...", "Complete"]
```

**Note on `R-CURRENTSTEP-DONE` coverage**: Test B already asserts `current_step == "Complete"`, so
the four `R-CURRENTSTEP-DONE` survivors are killed by Test B alone; Test F adds the pre-export
half (`R-CURRENTSTEP-RUN`). Either is sufficient for that pair.

### Test G — one-line amendment to the existing not-found test (kills `R-LOG-SWALLOWED`, 1 survivor)

```python
    @pytest.mark.asyncio
    async def test_run_export_job_not_found(
        self,
        mock_db: AsyncMock,
        mock_export_service: MagicMock,
        mock_job_tracker: MagicMock,
    ) -> None:
        """... existing body unchanged, plus: ..."""
        mock_export_service.export_events_with_progress.assert_not_called()
        # A job that was never found must not be reported as a failure: the not-found
        # path is a plain return, so no tracker transition belongs to it. This also
        # kills the swallowed-TypeError mutant (mutmut_10), where the logger call at
        # L155 raises inside the try and the broad except turns the return into a
        # spurious fail_job broadcast.
        mock_job_tracker.fail_job.assert_not_called()
        mock_job_tracker.start_job.assert_not_called()
        mock_job_tracker.complete_job.assert_not_called()
```

## Coverage accounting for the drafted tests

| Drafted test | Clusters killed                                                  | Survivors killed                |
| ------------ | ---------------------------------------------------------------- | ------------------------------- |
| A            | `G-SELECT`, `R-SELECT`                                           | 8                               |
| B            | `R-COUNTS`                                                       | 11                              |
| C            | `R-FAILJOB`, `R-COMPLETEJOB`, `R-STARTJOB-GAP`, `R-EXPORT-IDENT` | 17                              |
| D            | `M-METAFIELDS`, `M-RESULT-Guard`                                 | 9                               |
| E            | `G-DETAIL`                                                       | 2                               |
| F            | `R-CURRENTSTEP-DONE`, `R-CURRENTSTEP-RUN`                        | 6                               |
| G            | `R-LOG-SWALLOWED`                                                | 1                               |
| **Total**    |                                                                  | **54 of 54 TEST-GAP survivors** |

The remaining 46 survivors are 35 EQUIVALENT (log message/`extra`-key text only — killable only by
asserting log copy, which the codebase's `caplog` idiom would allow but which just freezes wording)
and 11 LOW-VALUE (`columns` is the service's contract; the transient `start_job` message; the two
`db.refresh` no-ops under `AsyncMock`; the never-observable early `RUNNING`/`started_at` writes;
and `completed_at`, which needs a `None`-primed fixture to assert freshness rather than mere
non-nullness).

**Note on the arg-drop mutants**: unlike some earlier dossiers' assumptions, every dropped-argument
variant in this module **compiles** (they resolve to valid trailing-comma calls, e.g.
`logger.error("…", )`, `fail_job(job_id, )`) — verified with `ast.parse` on each variant body. A
structural-validity gate would therefore retire none of them; they are ordinary survivors, and the
`call_args` assertions in Tests C/E/G are what reach them.

**Recommendation for WP4.4**: adopt A–G. Test G is a two-line addition to an existing test and buys
a real wrong-behaviour guard (a never-existing job must not be broadcast as failed), so it is the
cheapest item in the set. Tests A/C are the highest-value pair: they close the `assert_called_once()`-
with-no-arg-check blind spot that accounts for 25 survivors between them.

---

_Drafted tests are UNVERIFIED — not yet run red/green. Constraint honoured: no pytest, no `mutmut run`, no repo writes; the only mutation-tool call used was read-only `uv run mutmut show`._
