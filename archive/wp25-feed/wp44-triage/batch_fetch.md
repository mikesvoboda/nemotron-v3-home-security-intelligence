# WP4.4 mutation triage dossier — `backend/services/batch_fetch.py`

Wave: WP4.3 survivor triage → WP4.4 kill batches. Read-only analysis; **no tests were run** and no
repo file was touched. Generated 2026-09-19.

## 0. Verdict data + provenance (READ THIS FIRST)

- Verdict source: `mutants/backend/services/batch_fetch.py.meta` → `exit_code_by_key`.
  101 keys total: **36 survived (exit_code 0)**, 65 killed, 0 unchecked.
- **`uv run mutmut show <key>` is UNRELIABLE for this module right now.** Two independent failures:
  1. Batching all 36 keys through one `while read` loop returned diffs for
     `backend/services/session_service.py` — i.e. the results cache being concurrently written
     served another module's payloads.
  2. Individual calls were also *inconsistent*: key `x_batch_fetch_detections__mutmut_1` returned the
     correct `order_by_time` diff on two runs, but the loop run mixed in foreign modules. Do not trust
     any single `show` output for this module without cross-checking.
- **`mutants/backend/services/batch_fetch.py.spans` is ALSO unusable** in this checkout: the char
  offsets index a different file layout, so slicing `src[s:e]` returns docstring/registry text from
  the wrong function for every key. Do not use `.spans` for diffs here.
- Diffs below were produced by the deterministic fallback: parse
  `mutants/backend/services/batch_fetch.py` (6707 lines), take each `def`/`async def` block between
  column-0 def and the next module-level statement, and diff variant `x_<fn>__mutmut_N` against
  `x_<fn>__mutmut_orig` with the name normalized away. All 36 keys extracted cleanly, zero
  extraction failures. Working files: `/tmp/wp25/wp44-triage/bf-priv/keys.txt`,
  `/tmp/wp25/wp44-triage/bf-priv/diffs.txt`, `/tmp/wp25/wp44-triage/bf-priv/extract.py`.
- **Shared-path collision warning for the harness**: the conventional scratch path
  `/tmp/surv_keys.txt` was overwritten mid-run by a sibling triage agent triaging
  `session_service.py`. Use a module-private scratch dir.
- Coverage source: `mutants/mutmut-stats.json` → `tests_by_mangled_function_name`. Note the keys are
  **fully qualified** (`backend.services.batch_fetch.x_batch_fetch_detections`); a bare
  `x_batch_fetch_detections` lookup returns None and looks like "no coverage" when there is plenty.

### Covering tests (from stats)

| Function | Tests | Files |
| --- | --- | --- |
| `x_batch_fetch_detections` | 34 | `backend/tests/unit/services/test_batch_fetch.py` (13), `test_nemotron_analyzer.py` (18), `test_context_enricher.py` (3) |
| `x__clamp_batch_size` | 34 | same 3 files (note: zero survivors in this function) |
| `x_batch_fetch_detections_by_ids` | 3 | `backend/tests/unit/services/test_batch_fetch.py:277-330` |
| `x_batch_fetch_file_paths` | 3 | `backend/tests/unit/services/test_batch_fetch.py:333-382` |

The `test_nemotron_analyzer.py` / `test_context_enricher.py` hits are transitive: the only real
consumer is `backend/services/context_enricher.py:248`
(`await batch_fetch_detections(sess, detection_ids)`), which mocks the session and asserts on its own
output, not on the statement. Every survivor here is therefore only killable from
**`backend/tests/unit/services/test_batch_fetch.py`**.

### Why so many query mutations survive (root cause, verified)

Every test mocks the session with bare `AsyncMock()` and asserts only on `execute.call_count` and on
whatever the mock hands back. `session.execute(None)` is therefore *not* an error under a mock —
the canned result comes back and the length assertions pass. The same mock blindness hides
`.where(None)` and `select(None)`, which do **not** raise at construction time. Verified in a
read-only interpreter probe (no tests run):

```
select(None)                            -> OK, Select       -> "SELECT NULL AS anon_1 FROM detections WHERE ..."
select(Detection).where(None)           -> OK, Select       -> "... FROM detections WHERE NULL"
select(Detection.file_path).where(None) -> OK, Select       -> "SELECT detections.file_path FROM detections WHERE NULL"
select(Detection).order_by(None)        -> OK, Select       -> SQL identical to no-order_by at all
query = None; session.execute(None)     -> OK under AsyncMock (canned result returned)
logger.debug(None)                      -> OK, no raise     (backend.core.logging logger)
```

This is the same payload-contract gap the wave-65 "system payload-contract kill batch" closed for
other modules, and it has an established in-repo kill idiom —
`backend/tests/unit/services/test_event_service.py:597-600`:

```python
stmt = mock_db_session.execute.call_args_list[0].args[0]
sql = " ".join(str(stmt.compile(compile_kwargs={"literal_binds": True})).split())
assert "WHERE events.id = 123" in sql
assert "WHERE NULL" not in sql.upper()
```

Verified with `literal_binds` that the idiom renders what the drafted tests assert on:
`WHERE detections.id IN (3, 1, 2)` (lists render expanded), `WHERE NULL`, `SELECT NULL AS anon_1`,
`ORDER BY detections.detected_at ASC`. Note the *empty* IN list does **not** expand
(`IN (__[POSTCOMPILE_id_1])`), so the drafted tests use non-empty ID sets.

## 1. Cluster table — 36 survivors, sums to 36

| # | Cluster | Fn | Keys (<=3 shown) | N | Class | Kill via |
| --- | --- | --- | --- | --- | --- | --- |
| C1 | `logger.debug` arg mutated (message → `None`, `"XX…XX"`, lower-, UPPER-case) | `batch_fetch_detections`, `batch_fetch_file_paths` | `det_3`, `det_4`, `det_5` (+ `det_6`, `det_13`, `det_27`, `det_54`, `paths_27`) | 8 | **EQUIVALENT** | — |
| C2 | `batch_count` counter mutated (`=1`, `-=1`, `+=2`, init `1`) — variable feeds only the debug f-string at `batch_fetch.py:127-130` | `batch_fetch_detections` | `det_30`, `det_40`, `det_41` (+ `det_42`) | 4 | **EQUIVALENT** | — |
| C3 | dedup-log guard comparison flipped `!=` → `==` (`:91`) — guards a `logger.debug` only | `batch_fetch_detections` | `det_12` | 1 | **LOW-VALUE** | — |
| C4 | single-batch path: statement/arg clobbered to `None` (`where(None)`, `select(None)`, `query=None`, `execute(None)`) | `batch_fetch_detections` | `det_16`, `det_18`, `det_21` (+ `det_24`) | 4 | **TEST-GAP** | T1 |
| C5 | `query.order_by(Detection.detected_at.asc())` → `order_by(None)` (`:102`) — silently drops ORDER BY; probe proves the SQL equals the un-ordered query | `batch_fetch_detections` | `det_22` | 1 | **TEST-GAP** | T2 |
| C6 | keyword default `order_by_time: bool = True` → `False` (`:61`) — every default caller loses ordering | `batch_fetch_detections` | `det_1` | 1 | **TEST-GAP** | T2 |
| C7 | batch-loop iteration mutated: `range(0,…)` → `range(1,…)` (`:114`, skips `unique_ids[0]`), slice `i + size` → `i - size` (`:115`, yields an empty batch every pass) | `batch_fetch_detections` | `det_37`, `det_39` | 2 | **TEST-GAP** | T3 |
| C8 | same two loop mutations on the file-path loop (`:199`, `:200`) | `batch_fetch_file_paths` | `paths_14`, `paths_16` | 2 | **TEST-GAP** | T5 |
| C9 | batch-loop statement clobbered to `None` (`query=None`, `where(None)`, `select(None)`, `execute(None)`) | `batch_fetch_detections` | `det_43`, `det_44`, `det_46` (+ `det_50`) | 4 | **TEST-GAP** | T3 |
| C10 | file-path statement clobbered to `None` (`query=None`, `where(None)`, `select(None)`, `execute(None)`) | `batch_fetch_file_paths` | `paths_17`, `paths_18`, `paths_19` (+ `paths_22`) | 4 | **TEST-GAP** | T4 |
| C11 | single-batch fast-path boundary `<=` → `<` (`:95`) | `batch_fetch_detections` | `det_14` | 1 | **LOW-VALUE** | (see note) |
| C12 | `order_by_time=` kwarg mutated in the by_ids delegate (`False`→`None`, →`True`, kwarg dropped → default `True`) — return value is a dict keyed by id, so ordering is unobservable | `batch_fetch_detections_by_ids` | `byids_5`, `byids_9`, `byids_10` | 3 | **EQUIVALENT** | — |
| C13 | `batch_size=batch_size` kwarg dropped from the delegate call (`:162-164`) — caller's batch size silently falls back to `DEFAULT_BATCH_SIZE` | `batch_fetch_detections_by_ids` | `byids_8` | 1 | **TEST-GAP** | T6 |

**Totals: TEST-GAP 19 · EQUIVALENT 15 · LOW-VALUE 2 = 36.** (`det_` =
`backend.services.batch_fetch.x_batch_fetch_detections__mutmut_`, `byids_` = `…_by_ids__mutmut_`,
`paths_` = `…x_batch_fetch_file_paths__mutmut_`.)

### Cluster notes

- **C1 (EQUIVALENT).** `logger.debug(None)` does not raise (probed), and message-text variants are
  pure log text. Nothing observable changes; asserting on debug-log text is not worth a test.
- **C2 (EQUIVALENT).** `batch_count` never escapes the function except into the debug f-string. The
  mutants change the logged batch count (`0`→`1`, decremented, doubled) and nothing else. Killing
  these would require a caplog assertion on a debug line — LOW-VALUE at best, EQUIVALENT is the
  honest call given no caller can see it.
- **C3 (LOW-VALUE).** Real operator flip on a real condition, but the guarded body is a `logger.debug`
  dedup notice (`:91-92`). Behaviour visible to callers is unchanged. Dedup itself *is* asserted
  (`test_batch_fetch.py:223` `test_deduplicates_input_ids`) — that test asserts the query count,
  which is the right assertion; this log guard is not.
- **C4 / C9 / C10 (TEST-GAP, highest value).** These are production-fatal in the real DB
  (`WHERE NULL` returns zero rows; `SELECT NULL AS anon_1` returns no `Detection`;
  `session.execute(None)` raises in SQLAlchemy) and invisible under the current mocks. 12 of the 36
  survivors. One statement-contract test per function kills all three clusters. The repo already has
  the idiom (`test_event_service.py:597-600`), so this is a mechanical port, not new design.
- **C5 / C6 (TEST-GAP).** Ordering is the documented contract
  (`batch_fetch.py:73-76` "ordered by detected_at if order_by_time=True"), and
  `test_batch_fetch.py:137` `test_preserves_order_by_detection_time` exists *specifically* to assert
  it — but it is vacuous: all three mock detections share one `detected_at` (`now`, lines 143-147)
  and the assertions are only `len(result) == 3` and `call_count == 1` (lines 158-159). Its own
  docstring says "should execute with ORDER BY clause" and then never looks at the clause. This is
  the textbook "test exists but asserts too weakly" case: the line is executed by 13 tests in
  `test_batch_fetch.py` and asserted by none.
- **C7 / C8 (TEST-GAP).** Real data loss: `range(1, …)` silently omits the first deduplicated ID, and
  `i - size` produces an empty slice every iteration (production → zero rows, no exception). The two
  multi-batch tests (`test_batch_fetch.py:96`, `:162`) drive `execute` with a `side_effect` that
  **ignores the statement argument entirely** and just replays canned batches by call index, so they
  count 2 and 3 calls and pass for any partition whatsoever. `call_count` cannot see a mis-sliced
  partition — only the statements can.
- **C11 (LOW-VALUE, not a gap in practice).** `<=` → `<` is a genuine boundary change, but when
  `len(unique_ids) == effective_batch_size` both paths issue exactly one `execute` and return the
  same ordered rows (fast path orders in SQL, loop path sorts in Python at `:134`), so the only
  differences are debug-log text and which code path ran. No test reaches the boundary at all
  (`:77` is 10 ids/size 100, `:258` is 100 ids/size 100000, `:241` is 1 id). If the team insists on a
  total kill, `assert "ORDER BY detections.detected_at ASC" in sql` at the exact-equality boundary
  (20 ids, `batch_size=20`) distinguishes the paths — but that pins an implementation detail (SQL
  order-by vs Python sort) and is the only thing that can see it, so LOW-VALUE is the correct label.
- **C12 (EQUIVALENT).** `batch_fetch_detections_by_ids` returns `{d.id: d for d in detections}`
  (`:165`), so the three `order_by_time` mutations change only dict *insertion* order; key set,
  values and `==` comparison are identical. `False`→`None` is additionally falsy-equivalent. Nobody
  should assert on dict insertion order of this API.

## 2. Drafted tests — 6 tests, killing all 19 TEST-GAP survivors

Target file for all six: **`backend/tests/unit/services/test_batch_fetch.py`**
(append helpers after the imports at line 23; T1/T2/T3 into `TestBatchFetchDetections`, T6 into
`TestBatchFetchDetectionsByIds`, T4/T5 into `TestBatchFetchFilePaths`).

`// UNVERIFIED - not yet run red/green` on every test below, per the read-only constraint.

```python
import re  # add to the module imports at line 10-13

_IN_CLAUSE = re.compile(r"WHERE detections\.id IN \(([^)]*)\)")


def _executed_sql(mock_session: AsyncMock) -> list[str]:
    """Normalize every statement handed to session.execute() into compact SQL.

    Statement-contract helper: mocks make session.execute(None) silently succeed,
    so the only way to see a clobbered query is to inspect what was passed.
    Mirrors backend/tests/unit/services/test_event_service.py:597-600.
    """
    statements: list[str] = []
    for call in mock_session.execute.call_args_list:
        stmt = call.args[0]
        assert stmt is not None, "session.execute() was called with no statement"
        sql = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        statements.append(" ".join(sql.split()))
    assert statements, "session.execute() was never called"
    return statements


def _in_clause_ids(sql: str) -> list[int]:
    """Extract the expanded detections.id IN list (needs literal_binds rendering)."""
    match = _IN_CLAUSE.search(sql)
    assert match, f"no expanded 'WHERE detections.id IN (...)' clause in: {sql}"
    return [int(part) for part in match.group(1).split(",")]


def _empty_scalars_session() -> AsyncMock:
    """AsyncMock session whose result yields no rows but records every statement."""
    mock_session = AsyncMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    mock_session.execute.return_value = mock_result
    return mock_session
```

### T1 — single-query statement contract (kills **C4**: `det_16`, `det_18`, `det_21`, `det_24`)

`// UNVERIFIED - not yet run red/green`

```python
    @pytest.mark.asyncio
    async def test_single_query_statement_selects_detections_and_filters_ids(self) -> None:
        """The one query must select Detection rows and filter on the requested IDs.

        Kills batch_fetch_detections mutmut_16 (where(None) -> "WHERE NULL"),
        mutmut_18 (select(None) -> "SELECT NULL AS anon_1"), mutmut_21
        (query = None) and mutmut_50-style execute(None) on the fast path
        (mutmut_24). The mock session accepts any argument, so call_count
        asserts (test_batch_fetch.py:74, :93) cannot see any of these.
        """
        mock_session = _empty_scalars_session()

        await batch_fetch_detections(mock_session, [3, 1, 2], batch_size=100)

        (sql,) = _executed_sql(mock_session)
        assert "NULL" not in sql.upper(), f"query was clobbered to a NULL select/predicate: {sql}"
        assert sorted(_in_clause_ids(sql)) == [1, 2, 3]
```

TDD: on `mutmut_16`/`mutmut_18` the SQL contains `WHERE NULL` / `SELECT NULL AS anon_1` (both
rendered and confirmed in the probe) so the `"NULL" not in` assert fails red; on `mutmut_21`/`mutmut_24`
`stmt is not None` fails red; on the original the statement is
`SELECT detections.id, … FROM detections WHERE detections.id IN (3, 1, 2) ORDER BY detections.detected_at ASC`
— no token containing "NULL" in the column list (verified) and the IN list extracts to `[3, 1, 2]` — green.

### T2 — default ordering is emitted as SQL (kills **C5**: `det_22`; kills **C6**: `det_1`)

`// UNVERIFIED - not yet run red/green`

```python
    @pytest.mark.asyncio
    async def test_default_order_by_time_emits_order_by_clause_in_statement(self) -> None:
        """order_by_time defaults to True, so the statement must carry ORDER BY detected_at.

        Kills mutmut_22 (order_by(None) - the rendered SQL is byte-identical to no
        ORDER BY at all) and mutmut_1 (default order_by_time True -> False).
        Replaces the vacuous assertion in test_preserves_order_by_detection_time
        (test_batch_fetch.py:137-159), which gives every mock the SAME detected_at
        and then never inspects the ORDER BY its own docstring promises.
        """
        mock_session = _empty_scalars_session()

        await batch_fetch_detections(mock_session, [1, 2, 3])

        (sql,) = _executed_sql(mock_session)
        assert "ORDER BY detections.detected_at ASC" in sql
```

TDD: `mutmut_22` and `mutmut_1` both render no `ORDER BY` (probed: `order_by(None)` equals the
un-ordered query) → red; original renders `ORDER BY detections.detected_at ASC` → green.

### T3 — multi-batch partition coverage + statement contract (kills **C7**: `det_37`, `det_39`; **C9**: `det_43`, `det_44`, `det_46`, `det_50`)

`// UNVERIFIED - not yet run red/green`

```python
    @pytest.mark.asyncio
    async def test_multi_batch_partition_covers_every_id_exactly_once(self) -> None:
        """Batches must partition the deduplicated IDs - none skipped, none repeated.

        Kills mutmut_37 (range(0, ...) -> range(1, ...) drops unique_ids[0]) and
        mutmut_39 (slice i + size -> i - size yields an empty batch every pass),
        plus the batch-loop statement clobbers mutmut_43/44/46/50. The existing
        multi-batch tests (:96, :162) replay canned rows by CALL INDEX and ignore
        the statement argument, so any partition passes their call_count asserts.
        """
        mock_session = _empty_scalars_session()

        await batch_fetch_detections(mock_session, list(range(10)), batch_size=5)

        statements = _executed_sql(mock_session)
        assert len(statements) == 2
        collected: list[int] = []
        for sql in statements:
            assert "NULL" not in sql.upper()
            collected.extend(_in_clause_ids(sql))
        assert sorted(collected) == list(range(10))
```

TDD: `mutmut_37` yields `unique_ids[1:6]`, `unique_ids[6:11]` → ID `0` never queried → `sorted(collected) != list(range(10))` red;
`mutmut_39` yields an empty IN list every pass → `collected == []` red (the `_in_clause_ids` guard also
catches the un-expanded `IN (__[POSTCOMPILE_id_1])` form); `mutmut_43`/`mutmut_50` trip `stmt is not None`,
`mutmut_44`/`mutmut_46` trip the `NULL` assert — all red. Original partitions `[0:5]`+`[5:10]` → green.

### T4 — file-path statement contract (kills **C10**: `paths_17`, `paths_18`, `paths_19`, `paths_22`)

`// UNVERIFIED - not yet run red/green`

```python
    @pytest.mark.asyncio
    async def test_file_paths_statement_selects_only_file_path_filtered_by_ids(self) -> None:
        """The optimized query must project detections.file_path for the requested IDs.

        Kills batch_fetch_file_paths mutmut_17 (query = None), mutmut_18
        (where(None) -> "WHERE NULL"), mutmut_19 (select(None) -> "SELECT NULL AS
        anon_1") and mutmut_22 (execute(None)). Existing tests for this function
        (test_batch_fetch.py:333-382) stub result.all() and assert only the
        returned list, never the statement.
        """
        from backend.services.batch_fetch import batch_fetch_file_paths

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_session.execute.return_value = mock_result

        await batch_fetch_file_paths(mock_session, [3, 1, 2])

        (sql,) = _executed_sql(mock_session)
        assert sql.startswith("SELECT detections.file_path FROM detections")
        assert "NULL" not in sql.upper()
        assert sorted(_in_clause_ids(sql)) == [1, 2, 3]
```

TDD: `mutmut_19` renders `SELECT NULL AS anon_1 …` (both asserts fail), `mutmut_18` renders
`… WHERE NULL`, `mutmut_17`/`mutmut_22` pass `None` → red. Original renders exactly
`SELECT detections.file_path FROM detections WHERE detections.id IN (3, 1, 2)` (verified verbatim in
the probe) → green.

### T5 — file-path batching coverage (kills **C8**: `paths_14`, `paths_16`)

`// UNVERIFIED - not yet run red/green`

```python
    @pytest.mark.asyncio
    async def test_file_path_batches_cover_every_id_exactly_once(self) -> None:
        """File-path batches must partition the deduplicated IDs too.

        Kills batch_fetch_file_paths mutmut_14 (range(0, ...) -> range(1, ...)
        skips unique_ids[0]) and mutmut_16 (slice i + size -> i - size -> empty
        batch each pass). Both leave the returned-list assertions at :337-370
        untouched because result.all() is stubbed.
        """
        from backend.services.batch_fetch import batch_fetch_file_paths

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_session.execute.return_value = mock_result

        await batch_fetch_file_paths(mock_session, list(range(10)), batch_size=5)

        statements = _executed_sql(mock_session)
        assert len(statements) == 2
        collected: list[int] = []
        for sql in statements:
            collected.extend(_in_clause_ids(sql))
        assert sorted(collected) == list(range(10))
```

TDD: `mutmut_14` omits ID `0`, `mutmut_16` collects nothing → red; original covers `0..9` across two
statements → green.

### T6 — `batch_size` is forwarded by the by_ids delegate (kills **C13**: `byids_8`)

`// UNVERIFIED - not yet run red/green`

```python
    @pytest.mark.asyncio
    async def test_by_ids_forwards_batch_size_to_underlying_fetch(self) -> None:
        """A caller's batch_size must reach batch_fetch_detections, not DEFAULT_BATCH_SIZE.

        Kills batch_fetch_detections_by_ids mutmut_8, which drops the
        batch_size=batch_size kwarg so 10 IDs at batch_size=5 collapse into a
        single DEFAULT_BATCH_SIZE=250 query. All three existing by_ids tests
        (test_batch_fetch.py:281, :305, :315) call with the default batch size,
        so the pass-through is never exercised.
        """
        mock_session = AsyncMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        result = await batch_fetch_detections_by_ids(mock_session, list(range(10)), batch_size=5)

        assert result == {}
        assert mock_session.execute.call_count == 2
```

TDD: `mutmut_8` produces `call_count == 1` → red; original splits 10 IDs at size 5 into 2 queries →
green.

## 3. Expected close-out

19 of 36 survivors killable with one helper block + 6 tests (all in `test_batch_fetch.py`, no new
fixtures, no conftest changes). 15 survivors are EQUIVALENT (log text, log-only counters, unobservable
dict ordering) and 2 are LOW-VALUE (log-guard comparison flip, fast-path boundary) — recommend the
`no-mutation`/equivalence ruling for those 17 rather than caplog or implementation-detail asserts.

If the team wants a zero-survivor module, the two remaining levers are: a `caplog` assertion for
C1/C2/C3 (needs `caplog.set_level(logging.DEBUG, logger="backend.services.batch_fetch")`) and the
exact-boundary ORDER BY pin for C11 — both explicitly argued against above.
