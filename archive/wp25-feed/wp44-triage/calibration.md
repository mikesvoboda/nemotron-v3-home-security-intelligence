# WP4.4 Triage Dossier — backend/api/routes/calibration.py

- **Survivors: 38** (of 83 generated; 45 killed, 0 unchecked) — verdicts from
  `mutants/backend/api/routes/calibration.py.meta`, diffs via `uv run mutmut show <key>` (all 38 succeeded).
- **Covering test file (mutmut-stats `tests_by_mangled_function_name`):**
  `backend/tests/unit/api/routes/test_calibration.py` (unit file: 903 L; fixtures `mock_db_session` L42-50,
  `client` L53-67, `mock_calibration` L70-84).
  No other unit file touches these functions. Integration file
  `backend/tests/integration/api/test_calibration_routes.py` (real DB, asserts `user_id`/thresholds) exists
  but is **out of the mutation tier** — `[tool.mutmut] pytest_add_cli_args_test_selection = ["backend/tests/unit"]`
  (pyproject L627+), so integration assertions cannot kill these mutants. All kills must be unit-tier.
- **Structural fact that drives every TEST-GAP here:** the unit tests mock `AsyncSession` wholesale.
  `db.execute` is a canned `MagicMock` (never inspects its argument), `db.add`/`commit`/`refresh` are asserted
  only by call-count, and — the big one — the auto-create/update tests install a
  `refresh.side_effect = mock_refresh` that **blindly re-writes id/user_id/thresholds onto the object**,
  erasing whatever the code under test constructed or assigned. Anything the route puts *into* the DB layer
  (query, constructed fields, assigned attributes) is invisible to every existing assertion.
- **Model note** (`backend/models/user_calibration.py` L44-56): all four calibration columns are
  `nullable=False` with column defaults `default=30 / 60 / 85 / 0.1` that **exactly match** the route's
  `DEFAULT_*` constants (calibration.py L37-40). `user_id` is `nullable=False`, `unique=True`, no default.
  Response schema `UserCalibrationResponse` (`backend/api/schemas/calibration.py` L136-172, aliased
  `CalibrationResponse` at L257) requires all of id/user_id/low/medium/high/decay/counts/timestamps —
  a `None` on any of them fails `model_validate` (→ 500), which the drafted tests exploit.
- Verified non-test probes (no pytest run): SQLAlchemy 2.0 compile of the mutant statements —
  `where(None)` → `... WHERE NULL` (always zero rows → repeated auto-create → UNIQUE violation on 2nd call);
  `select(None)` → `SELECT NULL AS anon_1 ...` (scalar is always NULL → same always-create failure);
  `!=` → `WHERE user_calibration.user_id != :user_id_1` (never finds the row).

## Cluster table

| # | Cluster | Keys (<=3 ex.) | n | Class | Why |
|---|---------|----------------|---|-------|-----|
| C1 | Auto-create constructor: default kwarg values clobbered to `None` (user_id/low/medium/high/decay) | `...calibration.x__get_or_create_calibration__mutmut_9`, `_10`, `_13` (also 11, 12) | 5 | **TEST-GAP** | On a real DB every one is a NOT-NULL IntegrityError at flush; in tests the constructor result is only ever read back through the `mock_refresh` overwrite (test_calibration.py L128-140, L384-396), and `add` is asserted by count only (`add.assert_called_once()` L152). Line executed, payload never asserted. |
| C2 | Auto-create constructor: `user_id=` kwarg removed entirely | `...x__get_or_create_calibration__mutmut_14` | 1 | **TEST-GAP** | No column default for `user_id` (`nullable=False, unique=True`) → NULL insert on real DB. Same mock blindness as C1. (Killed by the same test.) |
| C3 | Auto-create constructor: threshold/decay kwargs removed (model defaults fill in) | `...x__get_or_create_calibration__mutmut_15`, `_17`, `_18` (also 16) | 4 | **EQUIVALENT** | Column defaults 30/60/85/0.1 (model L46-53) are value-identical to the route constants, so omitting the kwarg produces the same row; under mocks `refresh` overwrites anyway. Note (not a test gap): constants and model defaults are two sources of truth — drift would silently change behavior of the *original* code, a maintainability comment at most. |
| C4 | `db.add(None)` — session.add payload clobbered | `...x__get_or_create_calibration__mutmut_19` | 1 | **TEST-GAP** | Real DB: TypeError at flush. Tests: `add` is `MagicMock` and only `assert_called_once()` (L152) — argument never asserted. |
| C5 | Lookup query argument destroyed (`execute(None)` / `where(None)` / `select(None)`) | `...x__get_or_create_calibration__mutmut_2`, `_3`, `_4` | 3 | **TEST-GAP** | Mocked `execute` returns its canned result regardless of argument; on a real DB #3/#4 make the lookup never find the row (repeated auto-create → UNIQUE violation), #2 raises outright. No unit assertion ever inspects the statement passed to `execute`. |
| C6 | Comparison operator flipped `==` → `!=` on the `user_id` lookup predicate | `...x__get_or_create_calibration__mutmut_5` | 1 | **TEST-GAP** | Classic freshness/lookup operator flip: real DB returns the wrong row / no row. Invisible under the canned-result mock. |
| C7 | Update assignment target clobbered: `calibration.<field> = None` for low/medium/high/decay in `_apply_calibration_update` | `...x__apply_calibration_update__mutmut_22`, `_24`, `_28` (also 26) | 4 | **TEST-GAP** | The assignments at calibration.py L232-239 execute, but every covering test's `refresh.side_effect` (L174-180, L210-213, ...) re-writes the values after the assign, and the response assertions read the refresh-injected values — the assigned attribute value itself is never asserted. On a real DB: NOT NULL violation. |
| C8 | Log message text mutants (`logger.info` msg → None / XX-wrapped / lower / UPPER) | `...x__apply_calibration_update__mutmut_30`, `_34`, `...x__get_or_create_calibration__mutmut_21` (also apply 35, 36) | 5 | **EQUIVALENT** | Pure message text; `logging.info(None)` doesn't raise. No behavioral difference. |
| C9 | Log `extra=` payload dropped (`extra=None` / `extra` kwarg removed) | `...x__apply_calibration_update__mutmut_31`, `_33`, `...x__get_or_create_calibration__mutmut_22` (also goc 24) | 4 | **LOW-VALUE** | Real change to the structured log record, still no crash; nobody should be asserting on log-record structure. |
| C10 | Log `extra=` key renames (`user_id/low/medium/high` → `XX..XX`/UPPER) | `...x__apply_calibration_update__mutmut_37`, `_39`, `...x__get_or_create_calibration__mutmut_25` (also apply 38, 40-44, goc 26) | 10 | **LOW-VALUE** | Same as C9 — structured-field naming; real but not worth a test. |

Totals: TEST-GAP 15 (C1 5, C2 1, C4 1, C5 3, C6 1, C7 4) · EQUIVALENT 9 (C3 4, C8 5) · LOW-VALUE 14 (C9 4, C10 10). **Sum = 38 = survivors_total.**

Drafted tests below (3 tests) cover all four highest-value TEST-GAP clusters:
T1 kills C1+C2+C4 (7 mutants), T2 kills C5+C6 (4), T3 kills C7 (4) — 15/15 TEST-GAP survivors.

## Drafted tests — `backend/tests/unit/api/routes/test_calibration.py`

// UNVERIFIED - not yet run red/green (sandbox mutation run in progress; no test execution performed).

### T1 — kills C1 + C2 + C4 (auto-create row payload)

Blind-spot being closed: existing auto-create tests let `mock_refresh` *supply* the field values
(L128-140, L384-396) and never look at the object handed to `db.add`. T1 refreshes only DB-generated
columns and asserts what the route actually constructed and passed to `add`.

```python
    def test_get_calibration_auto_create_constructs_default_row(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Auto-creation builds the row with user_id and default thresholds and adds THAT object.

        Kills mutmut C1/C2/C4: constructor kwarg -> None, user_id kwarg removed, db.add(None).
        Refresh only supplies DB-generated columns; the threshold attributes must come from
        what the route assigned (a real refresh would read back exactly those).
        """
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        def mock_refresh(obj):
            obj.id = 1
            obj.correct_count = 0
            obj.false_positive_count = 0
            obj.missed_threat_count = 0
            obj.severity_wrong_count = 0
            obj.created_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
            obj.updated_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)

        mock_db_session.refresh.side_effect = mock_refresh

        response = client.get("/api/calibration")

        assert response.status_code == 200

        # Payload handed to the session (kills db.add(None): attribute access on None raises)
        added = mock_db_session.add.call_args.args[0]
        assert added.user_id == "default"
        assert added.low_threshold == 30
        assert added.medium_threshold == 60
        assert added.high_threshold == 85
        assert added.decay_factor == 0.1

        # Response is built from those constructed values, not from refresh injection
        data = response.json()
        assert data["user_id"] == "default"
        assert data["low_threshold"] == 30
        assert data["medium_threshold"] == 60
        assert data["high_threshold"] == 85
        assert data["decay_factor"] == 0.1
```

TDD: with each C1/C2 mutant applied the constructed attribute is `None`/unset → `CalibrationResponse`
(required fields) raises before 200 and the `added.*` asserts fail — test red; on original — green.
C4 (`db.add(None)`) → `added.user_id` raises `AttributeError` on `None` — red; green on original.

### T2 — kills C5 + C6 (lookup statement payload)

```python
    def test_get_calibration_query_filters_by_user_id_equality(
        self, client: TestClient, mock_db_session: AsyncMock, mock_calibration: MagicMock
    ) -> None:
        """The lookup must execute a UserCalibration SELECT filtered by user_id equality.

        Kills mutmut C5/C6: db.execute(None), where(None), select(None), == -> != flip.
        """
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_calibration
        mock_db_session.execute.return_value = mock_result

        response = client.get("/api/calibration")

        assert response.status_code == 200

        mock_db_session.execute.assert_called_once()
        stmt = mock_db_session.execute.call_args.args[0]
        sql = str(stmt)
        # Full-entity SELECT (kills select(None), and execute(None): str(None) matches none of these)
        assert "user_calibration.id" in sql
        # A real WHERE clause (kills where(None) -> "WHERE NULL")
        assert "NULL" not in sql.upper()
        # Equality, not inequality (kills == -> != flip)
        assert "!=" not in sql
        assert "user_calibration.user_id = :" in sql
```

TDD: red per-mutant — `execute(None)` → `str(None)` fails the first assert; `where(None)` → `WHERE NULL`;
`select(None)` → no `user_calibration.id` in the SELECT list; `!=` → last two asserts fail. Green on original
(str(stmt) renders `... WHERE user_calibration.user_id = :user_id_1`).

### T3 — kills C7 (update assignment payload)

Blind-spot being closed: existing partial-update tests (L202-279) let `refresh.side_effect` re-write the
attributes after the endpoint assigns them, so nothing ever reads what was assigned.

```python
    def test_put_update_writes_values_onto_calibration_object(
        self, client: TestClient, mock_db_session: AsyncMock, mock_calibration: MagicMock
    ) -> None:
        """PUT must assign each provided value onto the ORM object before commit/refresh.

        Kills mutmut C7: calibration.low/medium/high/decay = None assignment clobbers.
        refresh stays a plain no-op AsyncMock: the attributes already carry the assigned
        values, which is exactly what a real refresh would read back.
        """
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_calibration
        mock_db_session.execute.return_value = mock_result

        response = client.put(
            "/api/calibration",
            json={
                "low_threshold": 25,
                "medium_threshold": 55,
                "high_threshold": 80,
                "decay_factor": 0.15,
            },
        )

        assert response.status_code == 200

        # Assigned on the ORM object (not supplied by refresh)
        assert mock_calibration.low_threshold == 25
        assert mock_calibration.medium_threshold == 55
        assert mock_calibration.high_threshold == 80
        assert mock_calibration.decay_factor == 0.15

        data = response.json()
        assert data["low_threshold"] == 25
        assert data["medium_threshold"] == 55
        assert data["high_threshold"] == 80
        assert data["decay_factor"] == 0.15
```

TDD: on e.g. mutmut_22 the assignment writes `None`, refresh no-op leaves it, response model (required
`int`) fails → non-200/exception and `mock_calibration.low_threshold == 25` fails — red; on original — green.

## Notes for the fix lane

- All three tests belong to existing classes in
  `backend/tests/unit/api/routes/test_calibration.py`: T1 → `TestGetCalibration`, T2 → `TestGetCalibration`,
  T3 → `TestUpdateCalibration`. No new fixtures needed; imports already sufficient (`datetime/UTC`,
  `AsyncMock/MagicMock`, `TestClient`) — file L23-28.
- C9/C10 (LOW-VALUE, 14 mutants): a `caplog`-based assertion on `extra` keys would kill them, but the repo
  has zero caplog usage in this file — recommend accepting as not-worth-killing unless the log-record schema
  ever becomes an operational contract.
- C3 (EQUIVALENT): no test; optionally a one-line comment noting route constants duplicate model column defaults.
- Kill-count projection if all three drafted tests land green: TEST-GAP survivors 15 → 0; module survivors
  38 → 23 (all EQUIVALENT/LOW-VALUE log-text + kwarg-removal classes).
