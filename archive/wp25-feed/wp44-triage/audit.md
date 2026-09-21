# WP4.4 Triage Dossier — backend/services/audit.py

- **Module:** `backend/services/audit.py` (230 LOC: `get_actor_from_request`, `AuditService.log_action` / `get_audit_logs` / `get_audit_log_by_id`, singleton helpers)
- **Meta:** `mutants/backend/services/audit.py.meta` — 141 keys total: **42 survived**, 99 killed, 0 unchecked
- **Cluster totals:** 17 clusters, 34 TEST-GAP / 7 EQUIVALENT / 1 LOW-VALUE (sum = 42)
- **Covering unit test file:** `backend/tests/unit/services/test_audit.py` (951 lines). Per `mutmut-stats.json` `tests_by_mangled_function_name`, `log_action` / `get_actor_from_request` are additionally touched by `backend/tests/unit/api/routes/test_ai_audit.py`, `backend/tests/unit/routes/test_ai_audit_routes.py`, `backend/tests/unit/api/routes/test_events_coverage.py`, `backend/tests/unit/routes/test_{admin,cameras,events}_routes.py`, `backend/tests/unit/services/test_notification.py` — none of those assert query SQL shape either. Real-DB coverage exists in `backend/tests/integration/test_audit.py` (pagination disjointness at :90-123, filters at :59-87) but integration tests are not in the mutmut unit feed.

## Why the survivors survive — the mock-canned-row blind spot

Every `get_audit_logs` / `get_audit_log_by_id` test in `test_audit.py` stubs `db.execute` with a canned result object and **never inspects the query passed to it** (e.g. `test_get_audit_logs_with_pagination`, :615-655: mock returns a fixed `mock_logs` list regardless of `query`). The suite therefore asserts only mock return values. Empirically verified against SQLAlchemy 2.0.53 (in-memory compile, no DB):

- `select(X).where(None)` is a **silent no-op** — existing clauses stay, new clause is dropped (so filter-drop mutants don't error).
- `order_by(None)` renders identical to no `order_by`.
- `limit(None)` renders `LIMIT -1`; `offset(None)` drops the `OFFSET` clause entirely (SQLAlchemy coerces None→-1).
- `select(None)` renders `SELECT NULL AS anon_1` — executes fine on a real DB (Postgres allows FROM-less `SELECT NULL`), returns 1 row.
- `db.execute(None)` / `count_query = None` → `str` is `"None"` — invisible to canned mocks; on a real session it raises `ArgumentError` (so they'd die in integration, but the unit feed never sees SQL).

The two unit-level boundary tests (`:600` and `:656`) assert nothing about date boundaries (their window is ±1 day / ±1 hour), order, or pagination.

## Cluster table (42 survivors)

| # | Pattern (function / concern) | n | Keys (≤3 shown) | Class | Evidence / kill lever |
|---|---|---|---|---|---|
| A1 | `get_actor_from_request` API-key mask boundary `len(key) > 8` → `>= 8` / `> 9` (audit.py:37) | 2 | `x_get_actor_from_request__mutmut_20`, `__mutmut_21` | **TEST-GAP** | Tests only use 16/13/9… keys of len 11+ and `"short"` (len 5) (`test_audit.py:33-67, :110-125`); len-8 and len-9 never exercised → both branch arms for the boundary unobserved. Draft D1. |
| A2 | `get_actor_from_request` sentinel `ip_address = None` → `""` (audit.py:41) | 1 | `x_get_actor_from_request__mutmut_28` | **EQUIVALENT** | Both values are falsy at `if ip_address:` (:51) → `"unknown"`; overwritten by `host`/XFF whenever set. Unreachable diff. |
| B1 | `log_action` enum guards `isinstance(x, AuditAction/AuditStatus)` conjuncted with `and False` (audit.py:87-88) | 2 | `xǁAuditServiceǁlog_action__mutmut_2`, `__mutmut_5` | **EQUIVALENT** | `AuditAction`/`AuditStatus` are `str, Enum` (backend/models/audit.py:14, :82) → `log.action == "event_reviewed"` passes with the enum instance anyway (`x == x.value` is True); existing `test_log_action_with_enum` (:231-260) "passes" both shapes. Diff only observable through type checks nobody should assert. |
| B2 | `log_action` actor auto-derive call `get_actor_from_request(request)` → `(None)` (audit.py:92) | 1 | `log_action__mutmut_9` | **TEST-GAP** | `test_log_action_with_none_actor_auto_derives_unknown` (:845-865) covers only actor=None **without request** → `"unknown"`; the request-present branch (masked key / ip from request) never asserted. Draft D2. |
| B3 | `log_action` ip guard `request.client.host if request.client else None` → `... if (request.client) or True ...` (audit.py:99) | 1 | `log_action__mutmut_14` | **TEST-GAP** | Every log_action test with a request uses a mock **with** `client` set (`mock_request` fixture :211-229); `request` present + `client=None` (real for some ASGI transports) never passed — mutant does `None.host` → AttributeError, original logs `ip_address=None`. Draft D3. |
| B4 | `log_action` timestamp arg `timestamp=datetime.now(UTC)` → `None` / dropped / `now(None)` naive (audit.py:109) | 3 | `log_action__mutmut_28`, `__mutmut_37`, `__mutmut_46` | **TEST-GAP** | No unit test asserts `result.timestamp` at all; the row-level `default=lambda: datetime.now(UTC)` (models/audit.py:100-104) fires only at DB flush (mocked → never), so mutant leaves the attribute None/naive invisibly. `now(None)` returns naive local time — a tz bug with security meaning. Draft D4. |
| B5 | `log_action` `db.add(audit_log)` → `db.add(None)` (audit.py:120) | 1 | `log_action__mutmut_47` | **LOW-VALUE** | Mocked `session.add` accepts anything; real session raises `sqlalchemy.exc.ArgumentError`. The returned row is built before `add` so every field assertion still passes; only an integration "was it persisted" check would kill it, and `integration/test_audit.py` incidentally covers persistence. Nobody should unit-assert `add` argument shape. |
| C1 | `get_audit_logs` root `select(AuditLog)` → `select(None)` (audit.py:154) | 1 | `xǁAuditServiceǁget_audit_logs__mutmut_2` | **TEST-GAP** | Renders `SELECT NULL AS anon_1` — valid SQL; all filters/order/paging clauses still attach, so even SQL-shape checks must look at the **select list**. Draft D5 asserts `main_sql.startswith("SELECT audit_logs.id")`. |
| C2 | `get_audit_logs` filter clause dropped: `where(col == val)` → `where(None)` for action / resource_type / resource_id / actor / status / start_date / end_date (audit.py:157-170) | 7 | `__mutmut_4`, `__mutmut_7`, `__mutmut_10` (+13, 16, 19, 22) | **TEST-GAP** | `where(None)` is a silent clause no-op (verified) and mocks ignore the query → all 7 `test_get_audit_logs_with_*_filter` tests (:365-655) pass unchanged. Draft D5 asserts each `audit_logs.<col> = :<col>_1` fragment in both emitted SQLs. |
| C3 | `get_audit_logs` filter operator flip `==` → `!=` (same 5 eq-filters, audit.py:158-166) | 5 | `__mutmut_5`, `__mutmut_8`, `__mutmut_11` (+14, 17) | **TEST-GAP** | `!=` renders fine, mocks blind. Draft D5 asserts `!=` absent + `= :param` present. |
| C4 | `get_audit_logs` date bounds `timestamp >= start` → `>` and `<= end` → `<` (audit.py:168-170) | 2 | `__mutmut_20`, `__mutmut_23` | **TEST-GAP** | Boundary-exclusive bug (logs exactly at `start_date`/`end_date` vanish); `test_get_audit_logs_with_date_range_filter` (:572-615) uses a ±1-day window that never hits equality. Draft D5 asserts `>= :` / `<= :` fragments. |
| C5 | `get_audit_logs` count pipeline → `None`: `count_query = None` / `select(None).select_from(...)` / `db.execute(count_query→None)` (audit.py:173-174) | 3 | `__mutmut_24`, `__mutmut_26`, `__mutmut_28` | **TEST-GAP** | First `execute` receives `None`/NULL-select — canned mock returns the count result anyway. Draft D5 captures the first executed string and asserts `count(*)` + filter fragments inside it (subquery keeps WHEREs — verified). |
| C6 | `get_audit_logs` `order_by(AuditLog.timestamp.desc())` → `order_by(None)` (audit.py:178) | 1 | `__mutmut_33` | **TEST-GAP** | Renders byte-identical to un-ordered select (verified); mock returns canned "ordered" list. Newest-first ordering is the function's contract. Drafts D5/D5b. |
| C7 | `get_audit_logs` pagination → None: `query = None` / `offset(None)` / `limit(None)` (audit.py:181) | 3 | `__mutmut_34`, `__mutmut_35`, `__mutmut_36` | **TEST-GAP** | `limit(None)`→`LIMIT -1`, `offset(None)`→ clause gone (verified); `test_get_audit_logs_with_pagination` (:615-655) ignores the query. Drafts D5/D5b assert `LIMIT :param_1 OFFSET :param_2`. |
| C8 | `get_audit_logs` final `db.execute(query)` → `db.execute(None)` (audit.py:184) | 1 | `__mutmut_38` | **TEST-GAP** | Same mock blindness; second executed string captured by D5/D5b. |
| D1 | `get_audit_log_by_id` query shape: `execute(None)` / `where(None)` / `select(None)` / `id ==` → `!=` (audit.py:203) | 4 | `xǁAuditServiceǁget_audit_log_by_id__mutmut_2`, `__mutmut_3`, `__mutmut_4` (+5) | **TEST-GAP** | Both by-id tests (:763-803) canned-stub `execute`; `id=42` vs `id!=42` indistinguishable to a mock. Draft D6 asserts `FROM audit_logs` + `WHERE audit_logs.id = :id_1` + no `!=`/`NULL`. |
| D2 | `get_audit_log_by_id` `cast("AuditLog \| None", ...)` annotation string mutated (`None` / `"XX…XX"` / case flips) (audit.py:204) | 4 | `__mutmut_6`, `__mutmut_10`, `__mutmut_11` (+12) | **EQUIVALENT** | `typing.cast` is a pure no-op returning its second argument; even `cast(None, v)` returns `v`. Zero runtime semantics. |

**Kill-lever summary:** 34 of 42 survivors are one systemic gap — the mocked-session tests never capture the SQL passed to `db.execute`. Two capturing tests (D5, D6) kill 27 of them; D1-D4 add 6; the 7 EQUIVALENT + 1 LOW-VALUE stay by design.

## Drafted tests — UNVERIFIED (not yet run red/green)

All go in `backend/tests/unit/services/test_audit.py`, matching existing style (fixtures `mock_db_session` / `mock_request` in `TestAuditService`; plain `MagicMock` requests in `TestGetActorFromRequest`). TDD procedure for each: apply the mutant diff (or hand-patch the one line), run the new test — assertion must **fail**; restore original — must **pass**. File already imports everything used (`UTC`, `datetime`, `MagicMock`, `pytest`, `AuditLog`, `AuditService`, `get_actor_from_request`); no new imports needed.

### D1 — `TestGetActorFromRequest.test_api_key_mask_length_boundaries` → kills A1 (m20, m21)

```python
    def test_api_key_mask_length_boundaries(self):
        """Keys of exactly 8 / 9 chars sit on either side of the >8 mask boundary."""
        # len == 8 takes the else-branch (first 4 chars), len == 9 takes the [:8] branch.
        for key, expected in (
            ("abcdefgh", "api_key:abcd..."),      # len 8: NOT > 8 -> [:4]
            ("abcdefghi", "api_key:abcdefgh..."), # len 9: > 8 -> [:8]
        ):
            mock_request = MagicMock()
            mock_request.headers = MagicMock()
            mock_request.headers.get = lambda header, _default=None, _key=key: {
                "X-API-Key": _key,
            }.get(header, _default)
            mock_request.query_params = MagicMock()
            mock_request.query_params.get = MagicMock(return_value=None)

            assert get_actor_from_request(mock_request) == expected, f"key len {len(key)}"
```

Mutant m20 (`>=8`) returns `api_key:abcdefgh...` for the 8-char key; m21 (`>9`) returns `api_key:abcd...` for the 9-char key.

### D2 — `TestAuditService.test_log_action_auto_derives_actor_from_request` → kills B2 (m9)

```python
    @pytest.mark.asyncio
    async def test_log_action_auto_derives_actor_from_request(self, mock_db_session):
        """actor=None with a request must derive the masked-key actor, not 'unknown'."""

        async def async_flush():
            pass

        mock_db_session.flush = async_flush

        mock_req = MagicMock()
        mock_req.client = MagicMock()
        mock_req.client.host = "10.0.0.1"
        mock_req.headers = MagicMock()
        mock_req.headers.get = lambda key, default=None: {
            "X-API-Key": "abcdefgh12345",
        }.get(key, default)

        result = await AuditService.log_action(
            db=mock_db_session,
            action=AuditAction.EVENT_REVIEWED,
            resource_type="event",
            actor=None,
            request=mock_req,
        )

        assert result.actor == "api_key:abcdefgh..."
```

m9 (`get_actor_from_request(None)`) yields `"unknown"`.

### D3 — `TestAuditService.test_log_action_request_without_client_does_not_crash` → kills B3 (m14), also kills any `or True` client-guard mutants

```python
    @pytest.mark.asyncio
    async def test_log_action_request_without_client_does_not_crash(self, mock_db_session):
        """A request with client=None (some ASGI transports) must log ip_address=None."""

        async def async_flush():
            pass

        mock_db_session.flush = async_flush

        mock_req = MagicMock()
        mock_req.client = None
        mock_req.headers = MagicMock()
        mock_req.headers.get = lambda key, default=None: None

        result = await AuditService.log_action(
            db=mock_db_session,
            action=AuditAction.EVENT_REVIEWED,
            resource_type="event",
            actor="test_user",
            request=mock_req,
        )

        assert result.ip_address is None
```

m14 evaluates `request.client.host` unconditionally → `AttributeError: 'NoneType' object has no attribute 'host'`.

### D4 — `TestAuditService.test_log_action_sets_aware_utc_timestamp` → kills B4 (m28, m37, m46)

```python
    @pytest.mark.asyncio
    async def test_log_action_sets_aware_utc_timestamp(self, mock_db_session):
        """The AuditLog row must carry an aware UTC timestamp before flush (flush is mocked,
        so the model-level default never runs — the timestamp= argument is load-bearing)."""

        async def async_flush():
            pass

        mock_db_session.flush = async_flush

        before = datetime.now(UTC)
        result = await AuditService.log_action(
            db=mock_db_session,
            action=AuditAction.EVENT_REVIEWED,
            resource_type="event",
            actor="test_user",
        )
        after = datetime.now(UTC)

        assert result.timestamp is not None
        assert result.timestamp.tzinfo is not None  # datetime.now(None) is naive -> fails
        assert before <= result.timestamp <= after
```

m28 sets `timestamp=None` and m37 omits the kwarg (unset attribute → `AttributeError`/None); m46's naive `now(None)` fails the tzinfo assert (and could break the bounds compare).

### D5 — `TestAuditService.test_get_audit_logs_builds_real_query` (+ empty-row twin) → kills C1-C8 (23 survivors)

```python
    @pytest.mark.asyncio
    async def test_get_audit_logs_builds_real_query(self, mock_db_session):
        """Filters, date bounds, ordering, pagination and the count subquery must appear in
        the emitted SQL — mocked execute() returns canned rows, so nothing else observes it."""

        captured: list[str] = []
        now = datetime.now(UTC)

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 3
        mock_logs_result = MagicMock()
        mock_logs_scalars = MagicMock()
        mock_logs_scalars.all.return_value = [
            AuditLog(
                id=1,
                timestamp=now,
                action="event_reviewed",
                resource_type="event",
                resource_id="event-1",
                actor="admin",
                status="success",
            ),
        ]
        mock_logs_result.scalars.return_value = mock_logs_scalars

        call_count = [0]

        async def mock_execute(query):
            captured.append(str(query))
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_count_result
            return mock_logs_result

        mock_db_session.execute = mock_execute

        logs, total = await AuditService.get_audit_logs(
            db=mock_db_session,
            action="event_reviewed",
            resource_type="event",
            resource_id="event-1",
            actor="admin",
            status="success",
            start_date=now,
            end_date=now,
            limit=5,
            offset=5,
        )

        assert total == 3
        assert len(logs) == 1
        assert len(captured) == 2
        count_sql, main_sql = captured

        # Count pipeline must be a real count over the filtered subquery (kills C5)
        assert "count(*)" in count_sql
        # Root select must project the AuditLog columns, not NULL (kills C1)
        assert main_sql.startswith("SELECT audit_logs.id")
        # All five equality filters survive into both statements (kills C2 drops + C3 flips)
        for fragment in (
            "audit_logs.action = :action_1",
            "audit_logs.resource_type = :resource_type_1",
            "audit_logs.resource_id = :resource_id_1",
            "audit_logs.actor = :actor_1",
            "audit_logs.status = :status_1",
        ):
            assert fragment in count_sql, fragment
            assert fragment in main_sql, fragment
        assert "!=" not in main_sql and "!=" not in count_sql
        # Date bounds are INCLUSIVE (kills C4 exclusive-boundary flips)
        assert "audit_logs.timestamp >= :" in main_sql
        assert "audit_logs.timestamp <= :" in main_sql
        # Newest-first ordering and real LIMIT/OFFSET (kills C6, C7; None args render
        # "LIMIT -1" / drop OFFSET, verified against SQLAlchemy 2.0.53)
        assert "ORDER BY audit_logs.timestamp DESC" in main_sql
        assert "LIMIT :param_1" in main_sql
        assert "OFFSET :param_2" in main_sql
        # Second execute got the ordered/paged select, not None (kills C8 — a str(None)
        # "None" would have failed the main_sql asserts above too)

    @pytest.mark.asyncio
    async def test_get_audit_logs_pagination_survives_empty_result_rows(self, mock_db_session):
        """Even when the canned result rows are empty (every *_empty / invalid-limit test),
        the SQL must still carry order + LIMIT + OFFSET — pins C6/C7/C8 against a suite
        whose fixtures all return zero rows."""

        captured: list[str] = []

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 10
        mock_logs_result = MagicMock()
        mock_logs_scalars = MagicMock()
        mock_logs_scalars.all.return_value = []
        mock_logs_result.scalars.return_value = mock_logs_scalars

        call_count = [0]

        async def mock_execute(query):
            captured.append(str(query))
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_count_result
            return mock_logs_result

        mock_db_session.execute = mock_execute

        logs, total = await AuditService.get_audit_logs(db=mock_db_session, limit=5, offset=5)

        assert total == 10
        assert logs == []
        main_sql = captured[1]
        assert "ORDER BY audit_logs.timestamp DESC" in main_sql
        assert "LIMIT :param_1" in main_sql
        assert "OFFSET :param_2" in main_sql
```

Every C-cluster mutant changes at least one of the captured strings (`str(None)` == `"None"`, `SELECT NULL ...`, dropped fragment, `!=`, `> :`/`< :`, `LIMIT -1`, missing `OFFSET`/`ORDER BY`); each replacement was verified against SQLAlchemy 2.0.53 renders.

### D6 — `TestAuditService.test_get_audit_log_by_id_queries_by_primary_key` → kills D1 (m2, m3, m4, m5)

```python
    @pytest.mark.asyncio
    async def test_get_audit_log_by_id_queries_by_primary_key(self, mock_db_session):
        """The lookup must SELECT audit_logs WHERE id = :id (mocked execute ignores the query)."""

        captured: list[str] = []

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        async def mock_execute(query):
            captured.append(str(query))
            return mock_result

        mock_db_session.execute = mock_execute

        result = await AuditService.get_audit_log_by_id(db=mock_db_session, audit_id=42)

        assert result is None
        assert len(captured) == 1
        sql = captured[0]
        assert "SELECT audit_logs.id" in sql   # kills select(None) -> "SELECT NULL AS anon_1"
        assert "FROM audit_logs" in sql
        assert "WHERE audit_logs.id = :id_1" in sql  # kills where(None) ("WHERE NULL")
        assert "!=" not in sql                        # kills id != audit_id
        assert captured[0] != "None"                  # kills db.execute(None)
```

## Covering-test file:line map

| Function | Unit tests (file:lines) | What they miss |
|---|---|---|
| `get_actor_from_request` | `backend/tests/unit/services/test_audit.py:25-125` | len-8 / len-9 key boundary (:33-67 uses len 16/13/5) |
| `AuditService.log_action` | `test_audit.py:231-325`, `:805-890`; route-level: `backend/tests/unit/api/routes/test_ai_audit.py`, `backend/tests/unit/routes/test_ai_audit_routes.py` | actor=None+request branch; client=None; any `timestamp` assertion |
| `AuditService.get_audit_logs` | `test_audit.py:326-761` | query SQL entirely (13 filter/paging/date tests all use canned `mock_execute`) |
| `AuditService.get_audit_log_by_id` | `test_audit.py:762-803` | query SQL entirely |
| (integration, real DB) | `backend/tests/integration/test_audit.py:35-151` | boundary-inclusive date equality (window ±1d); still would not kill tz-naive `now(None)` |
