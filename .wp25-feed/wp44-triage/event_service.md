# WP4.4 Triage Dossier — backend/services/event_service.py

**Census**: 102 mutants, 59 killed, **42 survivors**, 0 unchecked.
**Diffs**: all 42 pulled cleanly via `uv run mutmut show <key>` (rc=0), saved at `/tmp/wp25/wp44-triage/evs_diffs.txt`.
**Survivors live in 3 methods only**: `soft_delete_event` (19), `restore_event` (16), `hard_delete_event` (7).
Source: `backend/services/event_service.py` (L92–173 soft, L175–247 restore, L249–299 hard).

## Covering tests (mutmut-stats tests_by_mangled_function_name)

- `soft_delete_event` / `hard_delete_event` / `restore_event` (service level):
  `backend/tests/unit/services/test_event_service.py`
  - `TestEventServiceSoftDeleteFileDeletion` L25–158 (3 tests: schedules / no-cascade / no-files)
  - `TestEventServiceHardDeleteFileDeletion` L161–321 (4 tests)
  - `TestEventServiceRestoreFileDeletion` L324–365 (1 test)
- `restore_event` (route level): `backend/tests/unit/routes/test_restore_endpoints.py` L170–220
  (success/409/404) — these exercise `EventService.restore_event` through the route with
  `mock_db_session.execute = AsyncMock(return_value=mock_result)`, i.e. **statement-blind mocks**.

**Root cause of the survivor set**: every covering test replaces `AsyncSession` with a `MagicMock` whose
`execute` returns a canned row regardless of the `stmt` argument, and replaces `FileService` with mocks.
Only Python-level control flow (cascade flag, file-list non-emptiness) is observable. The SQL text
construction, loader options, tz-awareness, and log payloads are executed but never asserted.

## Library behavior used for classification (verified via SQLAlchemy-introspection one-liners, no tests run)

- `select(Event).where(None)` **builds and compiles** → `... FROM events WHERE NULL` (silent, no raise).
- `select(None).options(selectinload(Event.detections))` **raises `ArgumentError` at build time**
  ("Query has only expression-based entities; attribute loader options … can't be applied here").
- Removing `undefer(Event.reasoning)` / `undefer(Event.llm_prompt)` **changes the compiled SELECT list**
  (column disappears); removing `selectinload(Event.detections)` does **not** change SQL text but changes
  `stmt._with_options` length (3 → 2).
- `datetime.now(None)` → **naive** datetime (no raise); `datetime.now(UTC)` → `tzinfo is UTC`.

## Verdict anomaly (flag for census owner)

4 survivor keys have variants that raise `ArgumentError` at build time (soft_5, soft_9, restore_10,
hard_4 — the `select(None).options(...)` mutations). Under the mutmut trampoline
(`mutmut/mutation/trampoline.py` dispatches straight into the variant when `MUTANT_UNDER_TEST` matches),
the covering test would error → expected kill, yet meta records exit 0. Do NOT reclassify as EQUIVALENT;
treat as unverified verdicts. The drafted statement-capture tests below (which actually invoke the
service and therefore hit the build error) will re-kill them when run.
Whole-statement → `stmt = None` variants (soft_2, restore_2, hard_1) also look anomalous
(mock `execute(None)` returns the canned row, so they are plausibly true survivors), as are the
`where(None)` variants (compile to `WHERE NULL`, mock-blind).

## Cluster table (counts sum to 42)

| # | Pattern | Keys (fn:mutmut) | N | Classification | Why |
|---|---------|------------------|---|----------------|-----|
| C1 | Fetch-statement mutations in `soft/restore/hard` event lookup: whole stmt→`None` (soft_2, restore_2, hard_1), `where(None)`→`WHERE NULL` (soft_3, restore_3, hard_2), `select(None)` (soft_5, hard_4, restore_10 — build-error), `==`→`!=` (soft_7, restore_14, hard_6), `execute(stmt)`→`execute(None)` (soft_9, restore_16, hard_8) | soft:2,3,5,7,9; restore:2,3,10,14,16; hard:1,2,4,6,8 | 15 | **EQUIVALENT** (as measured) + anomaly flag on soft_5, soft_9, restore_10, hard_4 | `db.execute` is a canned-return `AsyncMock` in every covering test — it never inspects `stmt`; `execute(None)` returns the same row. Python-level behavior identical under the mock. `==`→`!=` is a **real bug shielded by mock-blindness** → TEST-GAP for the id-predicate portion; see drafted test A. |
| C2 | Alert-count statement mutations (cascade branch): stmt→`None` (soft_19), `where(None)` (soft_20), `select(None)` (soft_21 — build-error), `==`→`!=` (soft_22), `execute` arg→`None` (soft_24) | soft:19,20,21,22,24 | 5 | **EQUIVALENT** (as measured) + anomaly flag on soft_21 | `alert_count` feeds only a log line (L148–152) — no return/state effect. Under the mock, count is 0 either way. The `!=` flip is shielded by mock-blindness; a stmt-capture assertion kills it (drafted test B). |
| C3 | Log/message payload → `None`: `logger.info(None)` / `logger.debug(None)` | soft:18,36,37; restore:34,35; hard:15,21 | 7 | **EQUIVALENT** | Message text only; `logger` accepts `None` payload, no behavior or return change. No caller should assert on message strings. |
| C4 | `if detection_count > 0` / `if alert_count > 0` / `if cancelled_count > 0` boundary flips (`>= 0`, `> 1`) guarding `logger.info` calls | soft:16,17,26,27; restore:27,28,32,33 | 8 | **LOW-VALUE** | The guarded branch is exclusively a log line (L136–152, L230–242). Off-by-one changes whether/when info logs fire; nobody should assert log-volume boundaries. |
| C5 | `cascade: bool = True` keyword-default flip → `False` | soft:1; restore:1 | 2 | **TEST-GAP** | Real behavior change: default-cascade callers (route `DELETE /events/{id}` passes `cascade=cascade` with API default `Query(True)`; batch route passes `cascade=True` explicitly — but any library caller relying on the signature default silently skips file scheduling / deletion-cancel). Tests always pass `cascade` explicitly (test_event_service.py L100/L133/L155/L359) → default never pinned. Drafted tests D + F2. |
| C6 | `undefer` removals from restore fetch options | restore:8 (reasoning), restore:9 (llm_prompt) — grouped with restore:7 (`selectinload` removal) below | 2 | **TEST-GAP** | Removing an `undefer` drops the deferred column from the SELECT list (SQL verified). Restored event then lazy-loads on attribute access outside greenlet context → the "prevent lazy loading errors" guard (L200–201 comment) is unasserted. Drafted test C. |
| C7 | `selectinload(Event.detections)` removal from restore fetch options | restore:7 | 1 | **TEST-GAP** | Same guard; kills via `stmt._with_options` count (3→2, SQL text unchanged — verified). Covered by drafted test C. |
| C8 | `if cascade and event_deleted_at is not None` → `cascade or event_deleted_at is not None` | restore:24 | 1 | **TEST-GAP** | `or` flip makes **cascade=False restores still cancel pending file deletions** — a real contract change (cancel is only meant to ride the cascade leg; it is also where `undefer`'d state is used). Existing tests never call `restore_event(cascade=False)` (only soft-delete has the no-cascade test, L118). Drafted test E. |
| C9 | `datetime.now(UTC)` → `datetime.now(None)` (naive timestamp written to `event.deleted_at`) | soft:13 | 1 | **TEST-GAP** | Naive `deleted_at` breaks the retention/comparison contracts elsewhere (`Event.deleted_at` compared against aware datetimes → TypeError in Postgres client/psycopg comparisons). Test L114 asserts only `is not None`. Drafted test G. |

Totals: EQUIVALENT 27 (C1 15 + C2 5 + C3 7) · LOW-VALUE 8 (C4) · TEST-GAP 7 (C5 2 + C6 2 + C7 1 + C8 1 + C9 1).
Sum = 27+8+7 = 42. C1/C2 equivalence is *mock-induced* (the underlying `==`→`!=` and `where(None)` flips
are real bugs); the drafted statement-capture tests convert them to kills.

## Drafted tests — `backend/tests/unit/services/test_event_service.py`

// UNVERIFIED - not yet run red/green. Follows existing fixtures
(`mock_file_service`, `mock_db_session`, `_create_mock_event`, `_create_mock_detection`)
in test_event_service.py L28–72. Add import: `from datetime import timezone` (test file already
imports `UTC, datetime` at L15 and `AsyncMock, MagicMock` at L17).

### A — soft-delete fetch targets exactly the requested id (kills soft_7; build-errors kill soft_5, soft_9, soft_2/3/… re-verified)

```python
    @pytest.mark.asyncio
    async def test_soft_delete_fetch_statement_targets_the_requested_event(
        self, mock_file_service: MagicMock, mock_db_session: MagicMock
    ) -> None:
        """Pinned SQL contract: the event lookup filters Event.id == event_id exactly.

        WP4.4 kill-test: == was mutated to != (mutmut_7) and the where clause to None
        (WHERE NULL, mutmut_3) — both invisible to the statement-blind execute mock.
        """
        event = self._create_mock_event(event_id=123, clip_path=None)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = event
        mock_db_session.execute.return_value = mock_result

        service = EventService(file_service=mock_file_service)
        await service.soft_delete_event(event_id=123, db=mock_db_session, cascade=True)

        stmt = mock_db_session.execute.call_args_list[0].args[0]
        sql = " ".join(str(stmt.compile(compile_kwargs={"literal_binds": True})).split())
        assert "WHERE events.id = 123" in sql
        assert "!=" not in sql
        assert "WHERE NULL" not in sql.upper()
```

TDD: on mutmut_7 the compiled WHERE reads `events.id != 123` → assertion fails; on the original it passes.

### B — alert-count lookup filters by this event (kills soft_22; also 19/20/24 via capture, 21 via build error)

```python
    @pytest.mark.asyncio
    async def test_soft_delete_alert_count_statement_filters_by_event_id(
        self, mock_file_service: MagicMock, mock_db_session: MagicMock
    ) -> None:
        """Cascade branch must count alerts for THIS event (Alert.event_id == event_id).

        WP4.4 kill-test: == was mutated to != (mutmut_22); alert_count is otherwise
        log-only so no existing test inspects the statement.
        """
        event = self._create_mock_event(event_id=123, clip_path=None)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = event
        mock_db_session.execute.return_value = mock_result

        service = EventService(file_service=mock_file_service)
        await service.soft_delete_event(event_id=123, db=mock_db_session, cascade=True)

        assert mock_db_session.execute.call_count == 2  # event fetch, then alert count
        alert_stmt = mock_db_session.execute.call_args_list[1].args[0]
        sql = " ".join(str(alert_stmt.compile(compile_kwargs={"literal_binds": True})).split())
        assert sql.startswith("SELECT")
        assert "WHERE alerts.event_id = 123" in sql
        assert "!=" not in sql
```

TDD: on mutmut_22 the WHERE reads `alerts.event_id != 123` → fails; original passes.

### C — restore fetch keeps eager-load + undefer options (kills restore_7, restore_8, restore_9; build error kills restore_10/2/3 family re-verified)

```python
    @pytest.mark.asyncio
    async def test_restore_event_fetch_eagerly_loads_detections_and_deferred_columns(
        self, mock_file_service: MagicMock, mock_db_session: MagicMock
    ) -> None:
        """Restore bypasses soft-delete filtering and must eagerly load detections,
        reasoning and llm_prompt to prevent greenlet lazy-load errors.

        WP4.4 kill-tests: selectinload removal (mutmut_7) drops one loader option;
        undefer removals (mutmut_8/_9) drop the column from the SELECT list.
        """
        event = MagicMock()
        event.id = 123
        event.is_deleted = True
        event.deleted_at = datetime.now(UTC)
        event.detections = []

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = event
        mock_db_session.execute.return_value = mock_result

        service = EventService(file_service=mock_file_service)
        await service.restore_event(event_id=123, db=mock_db_session, cascade=True)

        stmt = mock_db_session.execute.call_args_list[0].args[0]
        # selectinload(Event.detections): loader options are opaque Load objects that do
        # not affect SQL text — pin the count (original: selectinload + 2 undefer = 3).
        assert len(stmt._with_options) == 3
        sql = " ".join(str(stmt.compile(compile_kwargs={"literal_binds": True})).split())
        # undefer(Event.reasoning) / undefer(Event.llm_prompt): must appear in the SELECT list.
        assert "events.reasoning" in sql
        assert "events.llm_prompt" in sql
```

TDD: mutmut_7 → `len(...) == 2`; mutmut_8 → `events.reasoning` missing; mutmut_9 → `events.llm_prompt` missing; original passes all three.

### D — soft-delete default cascade (kills soft_1)

```python
    @pytest.mark.asyncio
    async def test_soft_delete_default_cascade_schedules_file_deletion(
        self, mock_file_service: MagicMock, mock_db_session: MagicMock
    ) -> None:
        """cascade defaults to True: a caller that omits it must still get file scheduling.

        WP4.4 kill-test: the keyword default was flipped to False (mutmut_1).
        """
        event = self._create_mock_event(event_id=123, clip_path="/path/to/clip.mp4")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = event
        mock_db_session.execute.return_value = mock_result

        service = EventService(file_service=mock_file_service)
        await service.soft_delete_event(event_id=123, db=mock_db_session)  # cascade omitted

        mock_file_service.schedule_deletion.assert_called_once()
```

TDD: with default flipped to False the cascade branch is skipped → `assert_called_once` fails; original passes.

### E — cascade=False restore must NOT cancel file deletions (kills restore_24)

```python
    @pytest.mark.asyncio
    async def test_restore_without_cascade_skips_file_deletion_cancel(
        self, mock_file_service: MagicMock, mock_db_session: MagicMock
    ) -> None:
        """restore_event(cascade=False) restores the row but leaves the scheduled
        deletion job untouched (cancel rides the cascade leg only).

        WP4.4 kill-test: `cascade and event_deleted_at is not None` was flipped to
        `or` (mutmut_24), making non-cascade restores cancel deletions.
        """
        event = MagicMock()
        event.id = 123
        event.is_deleted = True
        event.deleted_at = datetime.now(UTC)
        event.detections = []

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = event
        mock_db_session.execute.return_value = mock_result

        service = EventService(file_service=mock_file_service)
        await service.restore_event(event_id=123, db=mock_db_session, cascade=False)

        assert event.deleted_at is None
        mock_file_service.cancel_deletion_by_event_id.assert_not_called()
```

TDD: on the `or` flip the cancel mock gets called → `assert_not_called` fails; original passes.

### F — restore default cascade (kills restore_1)

```python
    @pytest.mark.asyncio
    async def test_restore_default_cascade_cancels_pending_file_deletions(
        self, mock_file_service: MagicMock, mock_db_session: MagicMock
    ) -> None:
        """cascade defaults to True: a caller that omits it must still get deletion-cancel.

        WP4.4 kill-test: the keyword default was flipped to False (mutmut_1).
        """
        event = MagicMock()
        event.id = 123
        event.is_deleted = True
        event.deleted_at = datetime.now(UTC)
        event.detections = []

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = event
        mock_db_session.execute.return_value = mock_result

        service = EventService(file_service=mock_file_service)
        await service.restore_event(event_id=123, db=mock_db_session)  # cascade omitted

        mock_file_service.cancel_deletion_by_event_id.assert_called_once_with(123)
```

TDD: flipped default skips the cascade leg → call assertion fails; original passes.

### G — soft-delete timestamp is UTC-aware (kills soft_13)

```python
    @pytest.mark.asyncio
    async def test_soft_delete_stamps_utc_aware_deleted_at(
        self, mock_file_service: MagicMock, mock_db_session: MagicMock
    ) -> None:
        """deleted_at must be timezone-aware (UTC): naive timestamps break retention
        comparisons against aware datetimes downstream.

        WP4.4 kill-test: datetime.now(UTC) was mutated to datetime.now(None) → naive
        (mutmut_13); existing tests only assert `is not None`.
        """
        event = self._create_mock_event(event_id=123, clip_path=None)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = event
        mock_db_session.execute.return_value = mock_result

        service = EventService(file_service=mock_file_service)
        result = await service.soft_delete_event(event_id=123, db=mock_db_session, cascade=True)

        assert result.deleted_at is not None
        assert result.deleted_at.tzinfo is not None, "deleted_at must be timezone-aware"
        assert result.deleted_at.utcoffset() == timezone.utc.utcoffset(None)
```

TDD: `datetime.now(None)` gives naive → `tzinfo is not None` fails; `datetime.now(UTC)` passes.

## Kill coverage of drafted batch

| Drafted test | Kills (of 42) |
|---|---|
| A | soft_7 (+ re-kills soft_5/9 build errors; pins soft_2/3 too) |
| B | soft_22 (+ soft_21 build error; pins 19/20/24) |
| C | restore_7, restore_8, restore_9 (+ re-kills restore_10 build error) |
| D | soft_1 |
| E | restore_24 |
| F | restore_1 |
| G | soft_13 |

Projected strict kill: ~11–13 of 42 (the deterministic TEST-GAP + anomaly-rekill set); remaining
29–31 are the log-text (7), log-boundary (8) and mock-blind statement-shape families (C1/C2
non-flip members) — killable only with a real-DB (sqlite integration) harness, which this module's
test file deliberately does not use.
