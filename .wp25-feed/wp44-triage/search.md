# WP4.4 Triage Dossier — `backend/services/search.py`

Source under test: `backend/services/search.py` (496 lines)
Mutant copy: `mutants/backend/services/search.py`
Verdicts: `mutants/backend/services/search.py.meta`
**Sole covering test file for every function in this module: `backend/tests/unit/services/test_search.py` (1471 lines).**

## Run state (important caveat)

| metric                     | value         |
| -------------------------- | ------------- |
| total keys                 | 477           |
| checked                    | 242           |
| killed                     | 133           |
| **survived (this triage)** | **109**       |
| **not yet checked**        | **235 (49%)** |

Half the module is still unchecked. Expect the survivor set to grow; expect the new keys to land in
the same clusters (`_build_search_query` holds 84/109 and most of its remaining unchecked keys).

## Structural finding 1: these survivors are bind-param mutations, not text mutations

The reason `_build_search_query` alone holds 84 survivors is mechanical: almost every literal in
it is rendered by SQLAlchemy as a **bind parameter**, not as SQL text.

```
events.search_vector @@ websearch_to_tsquery(CAST(%(param_2)s AS REGCONFIG), %(websearch_to_tsquery_1)s)
params: {'param_2': 'english', 'websearch_to_tsquery_1': 'person', 'ts_rank_1': 10, 'param_1': 0.0}
```

`str(compiled)` never contains `english`, `10`, `1.0`, `0.0`, `tsquery_str`, or `query`. Every
existing assertion in `TestBuildSearchQuery` / `TestILikeFallbackBehavior` /
`TestBuildSearchQueryOrderBehavior` is a `str(compiled).lower()` substring check, so all of them are
blind to every value in that tuple. Killing these requires `compiled.params` or expression-tree
walking.

## Structural finding 2: five existing tests are **vacuously green**

Verified in a scratch reproduction (`/tmp/wp25/probe/`, throwaway model, repo venv SQLAlchemy,
never importing the repo): `select(Event)` emits every non-deferred column, so `summary` and
`object_types` appear in the compiled string whether or not the ILIKE fallback mentions them; and
`Event.reasoning` (`backend/models/event.py:70`) is `deferred(...)` yet also appears in the
projection, contributed by the _separate_ `.options(undefer(Event.reasoning))`. **Deleting all three
ILIKE clauses still yields a statement string containing `summary`, `reasoning`, `object_types`
and `is null`.** That is exactly why
`test_ilike_fallback_searches_summary/_reasoning/_object_types` and
`test_ilike_fallback_only_when_search_vector_is_null` (test_search.py:541-595) all survive the
deletion mutants (cluster 6/7). This is a live bug-detection hole, not just a mutant nuisance.

## Structural finding 3: the "ordering" test never tests ordering

`TestBuildSearchQueryOrderBehavior.test_search_query_has_relevance_ordering` (test*search.py:1048)
calls `_build_search_query(...)` — **a function that never calls `order_by`**. The ordering lives in
`search_events` (line 425). So all 8 ordering mutants survive a test written specifically to kill
one of them, and its docstring even cites "mutant_25". Its assertion is
`assert "relevance_score" in query_text.lower()`, which is satisfied by the \_projection alias*.

---

## Cluster table (exhaustive — counts sum to 109, partition verified by script)

Key prefixes: `bsq` = `backend.services.search.x__build_search_query__mutmut_`,
`se` = `x_search_events__mutmut_`, `r2sr` = `x__row_to_search_result__mutmut_`,
`rfr` = `x_refresh_event_search_vector__mutmut_`, `upt` = `x_update_event_object_types__mutmut_`.

| #   | cluster                                                                         | n   | class      | example keys      | why it survives                                                                                                                              |
| --- | ------------------------------------------------------------------------------- | --- | ---------- | ----------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | ts_rank normalisation constants (`*10`, cap `1.0`)                              | 8   | TEST-GAP   | bsq:36,40,41      | `*10` and `1.0` are bind params (finding 1)                                                                                                  |
| 2   | result ordering: relevance term + `started_at DESC` tiebreaker                  | 8   | TEST-GAP   | se:25,29          | ordering built in `search_events`, never compiled or inspected (finding 3)                                                                   |
| 3   | filter wiring at the `search_events` call-site                                  | 2   | TEST-GAP   | se:10,13          | helper well covered; applying its output is not asserted                                                                                     |
| 4   | pagination `limit` / `offset`                                                   | 3   | TEST-GAP   | se:34,35          | response echoes `limit`; `offset=0` compiles to **no** OFFSET clause                                                                         |
| 5   | `ts_rank(search_vector, tsquery)` args                                          | 4   | TEST-GAP   | bsq:31,32         | bind-param blindness                                                                                                                         |
| 6   | ILIKE fallback clauses (summary/reasoning/object_types)                         | 6   | TEST-GAP   | bsq:61,64,65      | **vacuous substring assertions** (finding 2)                                                                                                 |
| 7   | `search_vector @@ tsquery` predicate                                            | 4   | TEST-GAP   | bsq:50,56         | same vacuity; `is null` satisfied by the fallback arm's guard                                                                                |
| 8   | ILIKE escaping (`safe_query`)                                                   | 2   | TEST-GAP   | bsq:47,48         | escaped value lands in a bind param; `escape_ilike_pattern(None)` → `""`, no error                                                           |
| 9   | `to_tsquery`/`websearch_to_tsquery` args (regconfig `english`, query strings)   | 16  | TEST-GAP   | bsq:17,21,29      | regconfig is a bind param; branch choice is only checked via `has_search is True`, which is always True                                      |
| 10  | `has_operators` operator list `["&","\|","!","<->"]`                            | 6   | TEST-GAP   | bsq:3,7           | corrupting `"<->"` silently re-routes phrases to websearch; nothing distinguishes the branches                                               |
| 11  | `outerjoin` ON `==`→`!=` (FTS branch)                                           | 1   | TEST-GAP   | bsq:91            | no test asserts join semantics                                                                                                               |
| 12  | `outerjoin` ON `==`→`!=` (no-query branch)                                      | 1   | TEST-GAP   | bsq:120           | same                                                                                                                                         |
| 13  | raw SQL statement → `None` (refresh/update)                                     | 2   | LOW-VALUE  | rfr:1, upt:8      | `db.execute` is an `AsyncMock`; tests read `call_args[0][1]` (params) only                                                                   |
| 14  | raw SQL keyword-case / XX-wrap mutants                                          | 3   | EQUIVALENT | upt:13,14,15      | SQL keywords are case-insensitive; `:event_id`/`:object_types` preserved — semantically identical SQL                                        |
| 15  | no-query placeholder columns dropped / → `None` (Event, relevance, camera_name) | 6   | LOW-VALUE  | bsq:103,106       | malformed projection; `compile()`-only tests never execute it                                                                                |
| 16  | no-query `relevance_score` label renamed / →`None` / type→`None`                | 4   | LOW-VALUE  | bsq:109,111,115   | projection alias; the no-query path never orders on it                                                                                       |
| 17  | no-query `camera_name` label renamed / →`None`                                  | 3   | LOW-VALUE  | bsq:117,119       | same                                                                                                                                         |
| 18  | no-query `cast(0.0, None)` (Float→None)                                         | 1   | EQUIVALENT | bsq:110           | renders `CAST(NULL AS FLOAT)`; indistinguishable from the constant for every consumer                                                        |
| 19  | no-query `cast(0.0 → 1.0, Float)`                                               | 1   | TEST-GAP   | bsq:114           | bind param; no test asserts the empty-query path yields relevance 0.0                                                                        |
| 20  | FTS-branch projection/label mutants                                             | 7   | LOW-VALUE  | bsq:81,86,88      | malformed projection / invisible alias                                                                                                       |
| 21  | `undefer(Event.reasoning)` dropped                                              | 2   | LOW-VALUE  | bsq:72,97         | deferred-load behaviour is not exercised (and the projection still shows `reasoning` — finding 2 cuts both ways)                             |
| 22  | `selectinload(Event.detections)` dropped                                        | 2   | LOW-VALUE  | bsq:73,98         | N+1/perf only; no behaviour assertion                                                                                                        |
| 23  | `outerjoin(Camera, None)` / ON dropped                                          | 4   | EQUIVALENT | bsq:76,78,100,102 | `Event.camera_id` carries `ForeignKey("cameras.id")` (event.py:53-55); **verified** both forms compile to `ON cameras.id = events.camera_id` |
| 24  | thumbnail `detection_ids[0]` → `[1]`                                            | 1   | TEST-GAP   | r2sr:12           | fixture has 3 detections but never asserts `thumbnail_url`                                                                                   |
| 25  | thumbnail forced to `None` (conditional/branch)                                 | 2   | TEST-GAP   | r2sr:9,10         | same                                                                                                                                         |
| 26  | `thumbnail_url` kwarg → `None` / dropped                                        | 2   | TEST-GAP   | r2sr:27,42        | dataclass default is `None`, so dropping the kwarg is invisible                                                                              |
| 27  | `search_events` orchestration args dropped                                      | 4   | LOW-VALUE  | se:3,6            | `db` is `AsyncMock`; only response shape asserted                                                                                            |
| 28  | count-query construction mutants                                                | 3   | LOW-VALUE  | se:14,18          | `scalar()` mocked to a constant and echoed                                                                                                   |
| 29  | `db.execute(None)`                                                              | 1   | LOW-VALUE  | se:37             | `AsyncMock` accepts anything                                                                                                                 |

**Rollup: TEST-GAP 67 · LOW-VALUE 34 · EQUIVALENT 8 = 109.**

---

## Covering-test map (file:line)

All in `backend/tests/unit/services/test_search.py`:

| source construct                            | test class @ line                                                                                                                | what it actually asserts                                                                         |
| ------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| `_convert_query_to_tsquery` + token helpers | `TestQueryParsing` @40, `TestQueryOperatorEdgeCases` @673, `TestQueryEmptyTokens` @757, `TestSearchQueryParsingProperties` @1126 | returned tsquery **string** — strong (0 survivors)                                               |
| `_build_filter_conditions`                  | `TestBuildFilterConditions` @363                                                                                                 | `len(conditions) == N` per filter — strong (0 survivors)                                         |
| `_build_search_query`                       | `TestBuildSearchQuery` @428, `TestILikeFallbackBehavior` @516, `TestBuildSearchQueryOrderBehavior` @1039                         | `has_search is True`, `result is not None`, `str(compiled)` substrings — **weak on every value** |
| `_row_to_search_result`                     | `TestRowToSearchResult` @598                                                                                                     | every field **except** `thumbnail_url`; fixture has 3 detections                                 |
| `search_events`                             | `TestSearchEventsAsync` @781, `TestPaginationAndLimits` @729                                                                     | `AsyncMock` db; response fields echoed                                                           |
| `refresh_event_search_vector`               | `TestRefreshEventSearchVector` @912                                                                                              | `call_args[0][1] == {"event_id": 42}`, `commit.assert_called_once()`                             |
| `update_event_object_types`                 | `TestUpdateEventObjectTypes` @948                                                                                                | `call_args[0][1]["object_types"] == "person, vehicle"` — strong on params, silent on SQL         |

Style to copy: params via `mock_db.execute.call_args[0][1]` (test*search.py:929, 965); SQL shape via
`result.compile(dialect=postgresql.dialect())` + `str(compiled)` (test_search.py:532-533). The
missing half of the idiom is `compiled.params`, `literal_binds=True`, and `call_args_list[1]` to
reach the \_page* query (execute is called twice: count then page).

---

## Drafted tests

All target `backend/tests/unit/services/test_search.py`. **UNVERIFIED — not yet run red/green.**
TDD procedure, per test: run it against the mutant copy → the new assertion must fail; run it
against `backend/services/search.py` → must pass. Reject any test green against both (asserts
nothing) or red against both (asserts something false).

Needed imports (add to the module header; `AsyncMock, MagicMock` and `pytest` already present at
test_search.py:19-21):

```python
from sqlalchemy.dialects import postgresql
```

### T-A → kills clusters 1, 5, 19 (+ value half of 9)

```python
class TestRelevanceRankingValues:
    """ts_rank normalisation constants. These were bind params, invisible to the existing
    str()-substring tests, so *10, the 1.0 cap and the no-query 0.0 all survived."""

    @staticmethod
    def _rank_expr(result):
        for col in result.inner_columns:
            if getattr(col, "name", None) == "relevance_score":
                return getattr(col, "element", col)
        raise AssertionError("no relevance_score column in projection")

    def test_rank_multiplies_ts_rank_by_ten_and_caps_at_one(self):
        from sqlalchemy.sql.functions import Function

        result, _has_search = _build_search_query("person & vehicle", "person AND vehicle")
        rank = self._rank_expr(result)

        assert isinstance(rank, Function) and rank.name == "least"
        scaled, cap = rank.clauses.clauses
        # ts_rank(...) * 10 -- the multiplier is a bind param, read .value, not str()
        assert scaled.left.name == "ts_rank"
        assert scaled.right.value == 10
        # scored against the event's own search vector
        assert str(scaled.left.columns[0]).endswith("events.search_vector")
        # ... and capped at 1.0 so the frontend percentage never exceeds 100
        assert cap.type.__class__.__name__ == "Float"
        assert list(cap.compile().params.values())[0] == 1.0

    def test_no_query_branch_reports_zero_relevance(self):
        """An empty query has nothing to rank: relevance is exactly 0.0, not 1.0 or NULL."""
        result, has_search = _build_search_query("", "")
        assert has_search is False
        label = next(
            c for c in result.inner_columns if getattr(c, "name", None) == "relevance_score"
        )
        assert list(label.element.compile().params.values())[0] == 0.0
```

Red-on-mutant: `bsq:41` (`*11`) / `bsq:40` (`/10`) break `right.value == 10`; `bsq:46` (cap 2.0)
breaks the cap assertion; `bsq:37,38,39,42` break shape/arity; `bsq:36` breaks `scaled.left.name`;
`bsq:31,33` break the search-vector assertion; `bsq:32,34` break the ts_rank arg set; `bsq:114`
breaks the 0.0 assertion.

### T-B → kills cluster 2

```python
class TestSearchEventsOrdering:
    """search_events built the ORDER BY nobody asserted: the only 'ordering' test calls
    _build_search_query, which never calls order_by at all."""

    @staticmethod
    def _mock_executes():
        count = MagicMock()
        count.scalar.return_value = 0
        rows = MagicMock()
        rows.all.return_value = []
        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[count, rows])
        return db

    @pytest.mark.asyncio
    async def test_search_results_ordered_by_relevance_then_started_at(self):
        db = self._mock_executes()
        await search_events(db, "person AND vehicle")

        statement = db.execute.call_args_list[1].args[0]
        sql = str(statement.compile(dialect=postgresql.dialect()))
        order_by = sql[sql.index("ORDER BY") :]
        assert "relevance_score DESC" in order_by
        # tiebreaker matters: equal relevance ranks must still come out newest-first
        assert "events.started_at DESC" in order_by
        assert order_by.index("relevance_score") < order_by.index("events.started_at")

    @pytest.mark.asyncio
    async def test_no_query_results_ordered_by_started_at_only(self):
        db = self._mock_executes()
        await search_events(db, "")

        statement = db.execute.call_args_list[1].args[0]
        sql = str(statement.compile(dialect=postgresql.dialect()))
        order_by = sql[sql.index("ORDER BY") :]
        assert "ORDER BY events.started_at DESC" in sql
        assert "relevance_score" not in order_by
```

Red-on-mutant: `se:23,25,28,30` remove/replace the relevance term; `se:24,26,29` remove the
started_at term (`se:29` lowercases `desc`, hence the exact-case assertion); `se:32` breaks the
no-query test.

### T-C → kills cluster 4

```python
    @pytest.mark.asyncio
    async def test_pagination_applies_limit_and_offset_to_sql(self):
        """limit/offset were echoed into SearchResponse but never applied. offset=0 compiles to
        no OFFSET clause at all, so a dropped .offset() is invisible without this test."""
        db = TestSearchEventsOrdering._mock_executes()
        db.execute.side_effect[0].scalar.return_value = 100

        await search_events(db, "person", limit=10, offset=20)

        statement = db.execute.call_args_list[1].args[0]
        assert statement._limit._value == 10
        assert statement._offset._value == 20
        sql = str(statement.compile(dialect=postgresql.dialect()))
        assert "LIMIT" in sql and "OFFSET" in sql

    @pytest.mark.asyncio
    async def test_default_limit_reaches_sql(self):
        db = TestSearchEventsOrdering._mock_executes()
        await search_events(db, "person")
        assert db.execute.call_args_list[1].args[0]._limit._value == 50
```

(append to `TestSearchEventsOrdering`). Red-on-mutant: `se:35` → `_limit._value` is None; `se:34` →
no OFFSET clause; `se:33` (`base_query = None`) raises before the assertion.

### T-D → kills cluster 3

```python
    @pytest.mark.asyncio
    async def test_filters_are_applied_to_the_executed_query(self):
        """_build_filter_conditions is well covered; nothing checked that search_events applies
        what it returns -- conditions = None and where(None) both survived."""
        db = TestSearchEventsOrdering._mock_executes()
        db.execute.side_effect[0].scalar.return_value = 1
        filters = SearchFilters(
            camera_ids=["front_door"],
            severity=["high"],
            start_date=datetime(2025, 1, 1),
            reviewed=False,
        )

        await search_events(db, "person", filters=filters)

        # the count query (first) must already carry the filters, and so must the page query
        for call in db.execute.call_args_list:
            sql = str(call.args[0].compile(dialect=postgresql.dialect())).lower()
            assert "events.camera_id in" in sql
            assert "events.risk_level in" in sql
            assert "events.started_at >=" in sql
            assert "events.reviewed" in sql
        page_params = db.execute.call_args_list[1].args[0].compile(
            dialect=postgresql.dialect()
        ).params
        assert "front_door" in page_params.values()
        assert "high" in page_params.values()
```

Red-on-mutant: `se:10` (`conditions = None`) and `se:13` (`where(None)`) drop every clause.

### T-E → kills clusters 6, 7, 8 and the reachable part of 10 — **highest value in this dossier**

Repairs the five vacuously-passing assertions from finding 2.

```python
class TestIlikeFallbackIsReal:
    """The fallback for events with a NULL search_vector. The existing tests assert
    `"summary" in str(compiled).lower()`, but select(Event) already projects events.summary and
    undefer(reasoning) already projects events.reasoning -- those assertions stay green even with
    the whole fallback deleted. Assert against the WHERE clause only."""

    @staticmethod
    def _where(result) -> str:
        compiled = str(
            result.compile(
                dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
            )
        )
        return compiled[compiled.index("WHERE") :].lower()

    def test_fallback_matches_all_three_text_columns(self):
        result, _ = _build_search_query("person", "person")
        where = self._where(result)
        assert "ilike" in where
        for column in (
            "events.summary ilike",
            "events.reasoning ilike",
            "events.object_types ilike",
        ):
            assert column in where, f"{column} missing from the fallback WHERE clause"
        # and it must stay gated on the vector being NULL
        assert "search_vector is null" in where

    def test_fts_match_operator_is_present(self):
        result, _ = _build_search_query("person", "person")
        where = self._where(result)
        assert "@@" in where
        assert "websearch_to_tsquery" in where  # no operators -> websearch branch

    def test_operator_queries_use_to_tsquery_not_websearch(self):
        """has_operators routes to to_tsquery; a corrupted operator list silently re-routes."""
        result, _ = _build_search_query("(suspicious <-> person)", '"suspicious person"')
        where = self._where(result)
        assert "@@" in where
        assert "to_tsquery" in where and "websearch_to_tsquery" not in where

    def test_ilike_pattern_escapes_wildcards_from_the_query(self):
        """escape_ilike_pattern must actually flow into the bound ILIKE pattern."""
        result, _ = _build_search_query("test", "test%with_wild")
        where = self._where(result)
        assert r"test\%with\_wild" in where, f"ILIKE pattern not escaped: {where}"
```

`literal_binds=True` renders the bound ILIKE string inline — without it both the escaping and the
column-in-WHERE checks are impossible. Red-on-mutant: `bsq:61-66` remove columns from WHERE;
`bsq:50,52` remove the `@@` predicate; `bsq:56` renders `XX@@XX`; `bsq:47,48` yield `%` / `%<empty>%`
patterns; `bsq:7` (corrupted `"<->"`) re-routes the proximity query to `websearch_to_tsquery`.

### T-F → kills clusters 24, 25, 26

```python
class TestThumbnailUrl:
    """thumbnail_url was never asserted anywhere, despite the row fixture carrying 3 detections."""

    @staticmethod
    def _row(detection_ids, relevance=0.5):
        event = MagicMock()
        event.id = 1
        event.camera_id = "front_door"
        event.started_at = datetime(2025, 12, 28, 12, 0, 0)
        event.ended_at = None
        event.risk_score = 40
        event.risk_level = "medium"
        event.summary = "Person"
        event.reasoning = "Night"
        event.reviewed = False
        event.object_types = "person"
        detections = []
        for det_id in detection_ids:
            det = MagicMock()
            det.id = det_id
            detections.append(det)
        event.detections = detections
        return (event, relevance, "Front Door Camera")

    def test_thumbnail_url_uses_first_detection_id(self):
        result = _row_to_search_result(self._row([7, 8, 9]))
        assert result.thumbnail_url == "/api/detections/7/image"
        assert result.detection_ids == [7, 8, 9]
        assert result.detection_count == 3

    def test_thumbnail_url_is_none_without_detections(self):
        result = _row_to_search_result(self._row([]))
        assert result.thumbnail_url is None
```

Red-on-mutant: `r2sr:12` → `/api/detections/8/image`; `r2sr:9,10` → None on the populated row;
`r2sr:27` → None always; `r2sr:42` → dataclass default None.

---

## Not drafted, but WP4.4 should know

- **Cluster 9 (16 keys, the largest gap)** is the least reachable: `'english'` is a bind param on
  both branches. One parameterised test asserting `compiled.params` carries `"english"` **and**
  which function name (`to_tsquery` vs `websearch_to_tsquery`) appears takes all 16 out. Same
  pattern as T-E's branch test — worth extending rather than drafting blind.
- **Clusters 20-22** sweep cheaply: assert the projection has exactly 3 columns and
  `len(result._with_options) == 2` (verified: dropping either loader drops the count to 1). ~15
  keys for ~10 lines.
- **Cluster 23 (4 keys) should be suppressed, not tested**: with the real FK, `outerjoin(Camera,
None)` and `outerjoin(Camera)` compile to the identical ON clause. Consider a mutmut ignore for
  ON-clause-argument removal on FK-bearing joins.
- **Clusters 27-29** are only killable against a real DB. `backend/tests/integration/` exists with
  `integration_db` / `db_session` fixtures (`backend/tests/conftest.py:41-43`). One integration
  test seeding 3 events and calling `search_events` kills most of them and validates the SQL the
  unit tests can only string-match. Recommend as a WP4.4 item.

## Verification performed (read-only; no repo test was executed)

Checked in a throwaway model under `/tmp/wp25/probe/` using the repo's own venv SQLAlchemy, never
by importing the repo:

- `str(compiled)` omits `english` / `10` / `1.0` / `0.0` — all bind params. Confirmed.
- deleting all three ILIKE clauses leaves `summary`, `reasoning`, `object_types`, `is null` present
  in the full statement string. Confirmed → 5 existing tests are vacuous.
- `Event.reasoning` is `deferred`, absent from a plain `select(Event)`, added by `undefer`.
  Confirmed against `backend/models/event.py:70`.
- `outerjoin(Camera, None)` and `outerjoin(Camera)` both render `ON cameras.id = events.camera_id`
  given the FK at `event.py:53-55`. Confirmed → cluster 23 is EQUIVALENT.
- `order_by(text("relevance_score DESC"))` renders `ORDER BY relevance_score DESC` regardless of the
  projection alias's case. Confirmed → why `se:30` survives and why T-B asserts exact casing.
- `offset=0` compiles to **no** OFFSET clause; `limit=None` compiles to `LIMIT ALL`. Confirmed.
- `where(None)` compiles without error (renders `NULL`). Confirmed → why `se:13` survives.
