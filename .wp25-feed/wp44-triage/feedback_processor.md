# WP4.4 Triage Dossier — backend/services/feedback_processor.py

**Method**: verdicts read from `mutants/backend/services/feedback_processor.py.meta` (JSON, single load, no decode retries). 184 keys total: 128 killed, **56 survived**, 0 null. All 56 diffs obtained via `uv run mutmut show <key>` (all succeeded, cache never conflicted). Covering tests from `mutants/mutmut-stats.json` → `tests_by_mangled_function_name`: **every function is covered only by `backend/tests/unit/services/test_feedback_processor.py`** (1352 lines).

## Why so much survives (root cause)

Every test in `backend/tests/unit/services/test_feedback_processor.py` drives the service through an `AsyncMock()` session whose `execute` either returns a canned result (`return_value`) or pops canned results from `side_effect` lists — **the statement object passed to `execute` is never inspected**. So every mutant that clobbers a `select(...)` / `.where(...)` / `execute(...)` argument still "works" (the mock answers regardless of SQL). The suite only kills mutants that raise (AttributeError/TypeError on mocked feedback objects). Second systemic gap: new-record *construction* is verified only by `session.add.assert_called_once()` / `isinstance(..., HouseholdMember)` — no field/default assertions. Third: `_auto_adjust_offset` boundary equality (`fp_rate` exactly 0.5 / exactly 0.1) is never exercised.

## Cluster table (counts sum to 56)

| # | Pattern (function / concern) | Count | Classification | Example keys (≤3) |
|---|---|---|---|---|
| C01 | `process_feedback`: entity-id args clobbered — `_get_event_with_detections(None, session)`, `_update_camera_calibration(None, ...)` | 2 | **TEST-GAP** | `…FeedbackProcessorǁprocess_feedback__mutmut_2`, `…process_feedback__mutmut_9` |
| C02 | log-call message args replaced with `None` (warning/info/debug) across 6 functions | 9 | **EQUIVALENT** | `…process_feedback__mutmut_7`, `…process_feedback__mutmut_32`, `…_update_camera_calibration__mutmut_33` |
| C03a | `_process_household_member`: base-name extraction — `split()` sep/whole-line clobbered (`None` sep, `"XX(XX"`, `rsplit`, line→None) | 5 | **TEST-GAP** | `…_process_household_member__mutmut_1`, `__mutmut_2`, `__mutmut_7` |
| C03b | `_process_household_member`: case-insensitive lookup statement clobbered (`stmt=None`, `select(None)`, `where(None)`, `lower↔upper`, `==`→`!=`, `func.lower(None)`, `execute(None)`) | 9 | **TEST-GAP** | `…__mutmut_10`, `__mutmut_14`, `__mutmut_15` |
| C03c | `_process_household_member`: new `HouseholdMember` constructor kwargs clobbered/removed (name, role, trusted_level, notes) | 8 | **TEST-GAP** | `…__mutmut_23`, `__mutmut_24`, `…__mutmut_29` |
| C04 | `_auto_adjust_offset`: `>` → `>=` at 0.5 and `<` → `<=` at 0.1 — strict thresholds relaxed at exact boundary | 2 | **TEST-GAP** | `…_auto_adjust_offset__mutmut_1`, `…__mutmut_10` |
| C05a | `_get_or_create_calibration`: SELECT statement/execution clobbered (`stmt=None`, `where(None)`, `select(None)`, `==`→`!=`, `execute(None)`) | 5 | **TEST-GAP** | `…_get_or_create_calibration__mutmut_1`, `__mutmut_4`, `__mutmut_6` |
| C05b | `_get_or_create_calibration`: new-record collection defaults clobbered/removed (`model_weights=None`/dropped, `suppress_patterns=None`/dropped) + `session.add(None)` | 5 | **TEST-GAP** | `…__mutmut_15`, `…__mutmut_16`, `…__mutmut_28` |
| C06 | `getattr(x, "attr", None)` default dropped → `getattr(x, "attr", )` (`process_feedback` actual_identity, `_update_camera_calibration` suggested_score) | 2 | **LOW-VALUE** | `…process_feedback__mutmut_24`, `…_update_camera_calibration__mutmut_21` |
| C07 | `reset_feedback_processor`: module-global sentinel `None` → `""` (falsy but not `None`) | 1 | **TEST-GAP** | `…x_reset_feedback_processor__mutmut_1` |
| C08 | `_get_event_with_detections`: SELECT statement/execution clobbered (`stmt=None`, `where(Event.id==None)`, `select(None)`, `==`→`!=`, `execute(None)`) | 5 | **TEST-GAP** | `…_get_event_with_detections__mutmut_1`, `__mutmut_6`, `__mutmut_8` |
| C01b | `_update_camera_calibration`: camera_id arg to `_get_or_create_calibration` → `None` | 1 | **TEST-GAP** | `…_update_camera_calibration__mutmut_3` |
| C13 | `_process_household_member`: `split()` maxsplit arg dropped/widened (1→dropped / 1→2) — `parts[0]` is invariant to maxsplit | 2 | **EQUIVALENT** | `…_process_household_member__mutmut_5`, `…__mutmut_8` |

Totals: TEST-GAP 43, EQUIVALENT 11, LOW-VALUE 2 — **sum 56** (2+9+5+9+8+2+5+5+2+1+5+1+2 = 56).

Per-function survivor inventory: `process_feedback` 5 (`2`,`7`,`9`,`24`,`32`), `_get_event_with_detections` 5 (`1`,`2`,`4`,`6`,`8`), `_get_or_create_calibration` 11 (`1`,`2`,`3`,`4`,`6`,`15`,`16`,`22`,`23`,`28`,`29`), `_update_camera_calibration` 3 (`3`,`21`,`33`), `_auto_adjust_offset` 4 (`1`,`9`,`10`,`18`), `_record_model_failures` 1 (`15`), `_process_household_member` 26 (`1`,`2`,`4`,`5`,`6`,`7`,`8`,`10`,`11`,`12`,`13`,`14`,`15`,`16`,`17`,`19`,`21`,`23`,`24`,`25`,`26`,`27`,`28`,`29`,`30`,`32`), `reset_feedback_processor` 1 (`1`).

## Cluster detail

### C01 / C01b — entity-id arguments clobbered to `None` (3 mutants, TEST-GAP)
`feedback_processor.py:131` `self._get_event_with_detections(feedback.event_id, session)` → `(None, session)`; `feedback_processor.py:137` `_update_camera_calibration(event.camera_id, …)` → `(None, …)`; `feedback_processor.py:232` `_get_or_create_calibration(session, camera_id)` → `(session, None)`. Real behavior change: the DB would look up the wrong row. Tests execute these lines but the mock `execute` never sees the SQL, and the mocked event's `camera_id` flows through the mocked session unchanged. Missing assertion: the compiled SQL params of the statements passed to `session.execute`. **Killed by D1.**

### C02 — log message args replaced with `None` (9 mutants, EQUIVALENT)
`logger.warning/info/debug(f"…")` → `logger.info(None)` at `feedback_processor.py:133,150-151,205,258-264,312-315,320-323,351-354,387,400-402`. `logging` accepts a `None` msg (no format args → no raise); no test captures logs (no `caplog` usage in the file). Pure observability loss, semantics identical. Not worth asserting.

### C03a — identity base-name extraction clobbered (5 mutants, TEST-GAP)
`feedback_processor.py:377` `identity_name.split("(", maxsplit=1)[0].strip()` mutated to `None` (`_1`), whitespace split (`_2` `split(None,…)`, `_4` `split(maxsplit=1)`), `"XX(XX"` separator (`_7`), `rsplit` (`_6`). All change `base_name` for realistic identities ("Mike Smith (neighbor)" → whitespace-split yields "Mike"; "Bob (x (y))" → rsplit keeps "Bob (x"). The only household test (`test_feedback_processor.py:663`) asserts *only* `isinstance(…, HouseholdMember)` on `session.add` — never the searched name or created name. **Killed by D4** (parametrized param-value asserts).

### C03b — case-insensitive member lookup clobbered (9 mutants, TEST-GAP)
`feedback_processor.py:380-384`: `stmt=None` (`_10`), `where(None)` (`_11`), `select(None)` (`_12`), `func.lower(None) == func.lower(base)` (`_13`), `func.upper(name) == lower(base)` (`_14`), `==`→`!=` (`_15`), `lower(name) == func.lower(None)` (`_16`), `= func.upper(base)` (`_17`), `execute(None)` (`_19`). SQL rendering verified against SQLAlchemy 2.0.53: original is `WHERE lower(household_members.name) = lower(:lower_1)` with params `{'lower_1': <base>}`; each mutant renders/executes a strictly different statement (or `None`). Mock session never inspects it. **Killed by D4.**

### C03c — new `HouseholdMember` constructor kwargs clobbered/removed (8 mutants, TEST-GAP)
`feedback_processor.py:391-396`: `name=None` (`_23`), `role=None` (`_24`), `trusted_level=None` (`_25`), `notes=None` (`_26`); kwargs dropped (`_27`–`_30`) → declarative `__init__` raises `TypeError` on unknown kwarg… actually removal means the kwarg is simply *not set* while the *removed line + closing paren* reshaping in mutmut leaves a valid call missing one field — either way `role`/`trusted_level` are `nullable=False` columns with **no column default** (`backend/models/household.py:94-106`), so a real flush would fail / persist wrong values. The doc contract ("New members default to FREQUENT_VISITOR role with PARTIAL trust", `feedback_processor.py:367`) is asserted nowhere: `test_creates_household_member_when_actual_identity_provided` (`test_feedback_processor.py:663-715`) checks only the isinstance of the added object. **Killed by D5.**

### C04 — FP-rate thresholds relaxed at exact equality (2 mutants, TEST-GAP)
`feedback_processor.py:308` `fp_rate > high_fp_threshold` → `>=` (`mutmut_1`); `:316` `fp_rate < low_fp_threshold` → `<=` (`mutmut_10`). At exactly 50% FP the doc says "High FP rate (> 50%)" — no decrease should happen; at exactly 10% — no increase. Existing tests use 0.55 and 0.05 (`test_feedback_processor.py:351,380`) and a moderate 0.31 (`:495`) but never the exact 0.5/0.1 boundary. **Killed by D6** (10/20 == 0.50 and 2/20 == 0.10, both hit exactly).

### C05a — calibration SELECT clobbered (5 mutants, TEST-GAP)
`feedback_processor.py:189-191`: `stmt=None` (`_1`), `where(None)` (`_2`), `select(None)` (`_3`), `==`→`!=` (`_4`), `execute(None)` (`_6`). Original renders `WHERE camera_calibrations.camera_id = :camera_id_1`; every unit test hands the mock an ignore-the-argument session. **Killed by D2.**

### C05b — new-record defaults clobbered + `session.add(None)` (5 mutants, TEST-GAP)
`feedback_processor.py:194-205`: `model_weights=None` (`_15`), `suppress_patterns=None` (`_16`), kwargs dropped (`_22`, `_23` — constructor leaves the attrs `None`; the `default=dict/list` on `backend/models/camera_calibration.py:85,89` fires only at INSERT flush, which never happens against the mock), and `session.add(None)` (`_28` — the object the test later mutates is never tracked by the session; production would silently persist nothing since `add` target differs while the service still returns it). `test_creates_new_calibration_when_none_exists` (`test_feedback_processor.py:119-136`) asserts camera_id/counts/rate/risk_offset but **not** `model_weights == {}` / `suppress_patterns == []`, and only `add.assert_called_once()` — not *what* was added. Downstream: `model_weights=None` crashes the very next `_record_model_failures` write path only if weights aren't re-initialized. **Killed by D3.**

### C08 — event SELECT clobbered (5 mutants, TEST-GAP)
`feedback_processor.py:170-172`: `stmt=None` (`_1`), `where(None)` (`_2`), `select(None)` (`_4`), `Event.id ==` → `!=` (`_6`), `execute(None)` (`_8`). `test_process_feedback_returns_event_with_detections` (`test_feedback_processor.py:603`) proves detections are *reachable* only because the mock hands back a pre-built event — the `selectinload` eager-load and the id filter itself are unasserted. **Killed by D1/D2 pattern applied in D0.**

### C06 — `getattr` default dropped (2 mutants, LOW-VALUE)
`feedback_processor.py:144` `getattr(feedback, "actual_identity", None)` → 2-arg form (`_24`); `:250` `getattr(feedback, "suggested_score", None)` → 2-arg (`_21`). Only observable for objects *lacking* the attribute; every test mock defines both attributes (set explicitly or via `MagicMock(spec=EventFeedback)` on a model that has them), so the defensive default is dead in practice. A real change (AttributeError instead of None) that nobody should ever have to assert — a real `EventFeedback` always has the columns. Low-value; optionally coverable by a plain-object feedback test, not drafted.

### C07 — singleton reset sentinel `None` → `""` (1 mutant, TEST-GAP)
`feedback_processor.py:432` `_feedback_processor = None` → `= ""`. Survives because `get_feedback_processor()` checks `is None` and `""` is falsy-but-not-None: reset → `get` still rebuilds, so `test_reset_feedback_processor_clears_cache` (`test_feedback_processor.py:1101-1108`, identity-based) passes under the mutant. The observable gap: the module global itself is left as a wrong-typed sentinel. Assert `feedback_processor._feedback_processor is None` after reset. **Killed by D7.**

### C13 — `split` maxsplit arg dropped/widened (2 mutants, EQUIVALENT)
`_process_household_member` `_5` (drop `maxsplit=1`) and `_8` (`maxsplit=2`): `s.split("(", k)[0]` is identical for any `k ≥ 1` (only later parts change). Semantically identical for all inputs.

## Drafted tests (D0–D7)

Style mirrors `backend/tests/unit/services/test_feedback_processor.py` (AsyncMock/MagicMock, `@pytest.mark.asyncio`, file-level `pytestmark = pytest.mark.unit`). SQL-substring and bind-param asserts were validated against SQLAlchemy 2.0.53 statement rendering (`WHERE events.id = :id_1` / `params {'id_1': 7}`; `camera_id_1`; `lower(household_members.name) = lower(:lower_1)`), but the tests themselves were **not executed** (live mutation run owns the machine).

**TDD procedure (one line)**: run the new tests against the mutant copy — each must FAIL (assert or AttributeError on `None`); re-run against `backend/services/feedback_processor.py` — all must PASS; that red/green pair is the kill proof.

Target file for all: `backend/tests/unit/services/test_feedback_processor.py` (append new class + methods; only covering file per mutmut-stats).

```python
# Add to imports at top of backend/tests/unit/services/test_feedback_processor.py
from sqlalchemy import Select  # noqa: E402  (add next to existing imports)
from backend.services import feedback_processor as feedback_processor_module

# =============================================================================
# WP4.4 mutation-gap tests (D0–D7)  // UNVERIFIED - not yet run red/green
# =============================================================================


class TestQueryStatementBindings:
    """Assert the SQL actually built + ids bound — mock sessions otherwise ignore it.

    Kills WP4.4 survivors: C01/C01b (process_feedback/_update_camera_calibration
    id args -> None), C05a (calibration SELECT clobbered), C08 (event SELECT
    clobbered).
    """

    @pytest.mark.asyncio
    async def test_get_or_create_calibration_binds_camera_id(self) -> None:
        """C05a/D2: the calibration lookup must filter on the given camera_id."""
        processor = FeedbackProcessor()

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        await processor._get_or_create_calibration(mock_session, "front_door")

        stmt = mock_session.execute.call_args_list[0].args[0]
        assert isinstance(stmt, Select)
        sql = str(stmt)
        assert "FROM camera_calibrations" in sql
        assert "WHERE camera_calibrations.camera_id = :" in sql
        assert stmt.compile().params == {"camera_id_1": "front_door"}

    @pytest.mark.asyncio
    async def test_process_feedback_binds_event_id_and_camera_id(self) -> None:
        """C01/C01b/D1: event lookup binds feedback.event_id; calibration lookup
        binds event.camera_id (mutants replace both args with None)."""
        processor = FeedbackProcessor()

        mock_event = MagicMock(spec=Event)
        mock_event.id = 1
        mock_event.camera_id = "front_door"
        mock_event.detections = []

        calibration = CameraCalibration(
            id=1,
            camera_id="front_door",
            total_feedback_count=5,
            false_positive_count=2,
            false_positive_rate=0.4,
            risk_offset=0,
        )

        mock_feedback = MagicMock(spec=EventFeedback)
        mock_feedback.event_id = 1
        mock_feedback.feedback_type = FeedbackType.FALSE_POSITIVE
        mock_feedback.actual_identity = None
        mock_feedback.model_failures = None
        mock_feedback.suggested_score = None

        mock_session = AsyncMock()
        mock_event_result = MagicMock()
        mock_event_result.scalar_one_or_none.return_value = mock_event
        mock_cal_result = MagicMock()
        mock_cal_result.scalar_one_or_none.return_value = calibration
        mock_session.execute.side_effect = [mock_event_result, mock_cal_result]

        await processor.process_feedback(mock_feedback, mock_session)

        event_stmt = mock_session.execute.call_args_list[0].args[0]
        assert isinstance(event_stmt, Select)
        assert "FROM events" in str(event_stmt)
        assert "WHERE events.id = :" in str(event_stmt)
        assert event_stmt.compile().params == {"id_1": 1}

        cal_stmt = mock_session.execute.call_args_list[1].args[0]
        assert isinstance(cal_stmt, Select)
        assert "WHERE camera_calibrations.camera_id = :" in str(cal_stmt)
        assert cal_stmt.compile().params == {"camera_id_1": "front_door"}


class TestCalibrationRecordDefaults:
    """C05b/D3. Kills goc mutmut_15/16/22/23 (model_weights/suppress_patterns
    None/removed) and mutmut_28 (session.add(None))."""

    @pytest.mark.asyncio
    async def test_get_or_create_calibration_new_record_defaults(self) -> None:
        processor = FeedbackProcessor()

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        calibration = await processor._get_or_create_calibration(mock_session, "front_door")

        # Collection defaults must be the empty containers, not None — a None
        # here breaks the next _record_model_failures write and the JSONB
        # NOT NULL columns at flush time.
        assert calibration.model_weights == {}
        assert calibration.suppress_patterns == []
        # add() must have received the very object returned, not None.
        mock_session.add.assert_called_once()
        assert mock_session.add.call_args_list[0].args[0] is calibration
        mock_session.flush.assert_called_once()


class TestHouseholdMemberNameBinding:
    """C03a/C03b/D4. Kills household_mutmut_1,2,4,6,7 (base_name extraction) and
    10,11,12,13,14,15,16,17,19 (lookup statement clobber)."""

    @pytest.mark.parametrize(
        ("identity", "expected_base"),
        [
            ("Mike (neighbor)", "Mike"),                    # kills "XX(XX" sep
            ("Mike Smith (neighbor)", "Mike Smith"),        # kills whitespace-split variants
            ("Bob (the guy (see notes))", "Bob"),           # kills rsplit
        ],
    )
    @pytest.mark.asyncio
    async def test_lookup_binds_parsed_base_name(
        self, identity: str, expected_base: str
    ) -> None:
        processor = FeedbackProcessor()

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        await processor._process_household_member(identity, mock_session)

        stmt = mock_session.execute.call_args_list[0].args[0]
        assert isinstance(stmt, Select)
        sql = str(stmt)
        assert "SELECT household_members.id" in sql
        # Case-insensitive on BOTH sides, equality only:
        assert "lower(household_members.name) = lower(:lower_1)" in sql
        assert stmt.compile().params == {"lower_1": expected_base}

    @pytest.mark.asyncio
    async def test_new_member_gets_documented_defaults(self) -> None:
        """C03c/D5. Kills household_mutmut_23..30 (constructor kwargs None/removed)."""
        processor = FeedbackProcessor()

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None  # no existing member
        mock_session.execute.return_value = mock_result

        member = await processor._process_household_member("Mike (neighbor)", mock_session)

        assert isinstance(member, HouseholdMember)
        mock_session.add.assert_called_once()
        assert mock_session.add.call_args_list[0].args[0] is member
        # The NEM-3332 contract (docstring 367): base name, visitor role,
        # partial trust, provenance note. None of these is asserted today.
        assert member.name == "Mike"
        assert member.role == MemberRole.FREQUENT_VISITOR
        assert member.trusted_level == TrustLevel.PARTIAL
        assert member.notes is not None
        assert "Mike (neighbor)" in member.notes


class TestAutoAdjustmentStrictThresholds:
    """C04/D6. Kills auto_adjust_offset mutmut_1 (> -> >=) and mutmut_10 (< -> <=)."""

    @pytest.mark.asyncio
    async def test_no_decrease_when_fp_rate_exactly_at_high_threshold(self) -> None:
        """10/20 == 0.50 exactly: docs say decrease only when rate is ABOVE 50%."""
        processor = FeedbackProcessor()

        calibration = CameraCalibration(
            id=1,
            camera_id="front_door",
            total_feedback_count=19,  # becomes 20 (>= min samples)
            false_positive_count=9,   # becomes 10 -> 10/20 == 0.5 exactly
            false_positive_rate=0.474,
            risk_offset=0,
        )

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = calibration
        mock_session.execute.return_value = mock_result

        mock_feedback = MagicMock(spec=EventFeedback)
        mock_feedback.feedback_type = FeedbackType.FALSE_POSITIVE
        mock_feedback.suggested_score = None

        await processor._update_camera_calibration("front_door", mock_feedback, mock_session)

        assert calibration.total_feedback_count == 20
        assert calibration.false_positive_rate == 0.5  # exact boundary
        assert calibration.risk_offset == 0            # >= mutant would make -5

    @pytest.mark.asyncio
    async def test_no_increase_when_fp_rate_exactly_at_low_threshold(self) -> None:
        """2/20 == 0.10 exactly: docs say increase only when rate is BELOW 10%."""
        processor = FeedbackProcessor()

        calibration = CameraCalibration(
            id=1,
            camera_id="front_door",
            total_feedback_count=19,  # becomes 20
            false_positive_count=2,   # CORRECT feedback keeps it at 2 -> 0.1 exactly
            false_positive_rate=0.105,
            risk_offset=0,
        )

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = calibration
        mock_session.execute.return_value = mock_result

        mock_feedback = MagicMock(spec=EventFeedback)
        mock_feedback.feedback_type = FeedbackType.CORRECT
        mock_feedback.suggested_score = None

        await processor._update_camera_calibration("front_door", mock_feedback, mock_session)

        assert calibration.total_feedback_count == 20
        assert calibration.false_positive_rate == 0.1  # exact boundary
        assert calibration.risk_offset == 0            # <= mutant would make +2


class TestSingletonResetSentinel:
    """C07/D7. Kills x_reset_feedback_processor__mutmut_1 (None -> "")."""

    def test_reset_sets_module_global_to_none_not_falsy(self) -> None:
        get_feedback_processor()
        feedback_processor_module._feedback_processor = ""  # mutant's surviving state
        reset_feedback_processor()
        # `is None`, NOT falsiness: "" would pass a `not`-style check.
        assert feedback_processor_module._feedback_processor is None
        assert isinstance(get_feedback_processor(), FeedbackProcessor)
        reset_feedback_processor()
```

Coverage mapping of drafts to clusters: D1(+C01,C01b), D2(+C05a), D3(+C05b), D4(+C03a,C03b), D5(+C03c), D6(+C04), D7(+C07) → 40 of 43 TEST-GAP survivors. Not drafted per instruction limit (3–6 clusters were prioritized; extras above are cheap inclusions): C08 (event SELECT — same assertion shape as D1's event_stmt block already kills `_get_event_with_detections` when reached via process_feedback, which exercises the exact function at `feedback_processor.py:170`; all 5 C08 mutants die under D1's event_stmt asserts). C06 stays LOW-VALUE by judgment; C02/C13 are EQUIVALENT by proof.

## Covering test file (from mutmut-stats tests_by_mangled_function_name)

- `backend/tests/unit/services/test_feedback_processor.py` — sole covering file for every function. Key landmarks: `TestGetOrCreateCalibration` L115 (weak add-assert L135-136), `TestUpdateCameraCalibration` L168, `TestAutoAdjustment` L347 (boundary gap: rates used 0.55/0.05/0.31), `TestProcessFeedback` L529 (missing-event test L581 asserts only `execute.call_count == 1`; mock session at L562-572), `TestHouseholdMemberProcessing` L659 (isinstance-only add-assert L712-715; L773-776), `TestModelFailuresRecording` L866 (no survivors here), `TestFeedbackProcessorSingleton` L1089.
- Source landmarks: `backend/services/feedback_processor.py:131,137` (C01), `:170-172` (C08), `:189-205` (C05a/C05b), `:232` (C01b), `:308,316` (C04), `:377,380-384,391-396` (C03a/b/c), `:432` (C07), `:144,250` (C06).
