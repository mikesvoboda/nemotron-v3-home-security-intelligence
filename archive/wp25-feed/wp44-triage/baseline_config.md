# WP4.4 Triage Dossier — backend/services/baseline_config.py

UNVERIFIED — read-only triage wave; no tests were run. Drafted tests below are marked UNVERIFIED.

## Run state

- `mutants/backend/services/baseline_config.py.meta`: 110 tracked keys, 0 unchecked, 77 killed, **33 SURVIVED** (this dossier).
- All 33 diffs extracted via `uv run mutmut show <key>` (all succeeded, no timeouts).
- Covering tests (`mutants/mutmut-stats.json` → `tests_by_mangled_function_name`):
  - `get_camera_config` / `set_camera_config` / `reset_camera_baseline` / `__init__` → **only `backend/tests/unit/services/test_baseline_config.py`** (plus one co-named unrelated `test_enrichment_transformers.py::TestSanitizeErrors::test_sanitize_errors_empty_list` collision — not real coverage of this module).
  - `__init__` and the module-level singleton are covered transitively by every test (each constructs `BaselineConfigService()`).

## Critical run-selection finding (explains several "should have been killed" survivors)

`mutants/mutmut-stats.json` → `duration_by_test` lists **27425 tests, of which ZERO are from `backend/tests/integration/`** (the 13 rows containing `/integration/` are `backend/tests/unit/integration/test_helpers_unit.py`). The integration suite `backend/tests/integration/test_baseline_config_service.py` — which *does* run the service against a real DB and *does* assert `rowcount == 3` (kills `or 1`), `WHERE NULL`-style scoping, zero-count behaviour, and the exact `"at least 0.5"` / `"at least 1"` message regexes — **was not part of the mutation run**. Several survivors below would be killed by it if it were selected.

Second finding: **no test in the repo asserts the ValueError message raised by the service**, only that it contains the field name (`backend/tests/unit/services/test_baseline_config.py:207`, `:224`), so all message-text mutants there survive.

Third: `mutmut` only mutates `backend/services/baseline_config.py`. The API route duplicates the same guard in `backend/api/routes/cameras.py:2135-2139`, so boundary mutants in this module are masked in production *only by a sibling module that is separately mutated*.

## Cluster table (verified partition: each of the 33 keys appears exactly once; sum = 33)

TEST-GAP 18, LOW-VALUE 4, EQUIVALENT 11. Cluster IDs are assigned by drafting priority, so they are not in class order.

### TEST-GAP (6 clusters, 18 mutants)

| ID | Pattern | N | Keys (all) | Classification note |
|----|---------|---|-----------|---------------------|
| C1 | `get_camera_config`: **override gate bypassed** — `if override_active` → `if (override_active) or True`, so per-camera values are used even when the override flag is off. Mutants run but produce wrong values. | 2 | gc_17, gc_30 | TEST-GAP. `test_get_camera_config_no_override` (test_baseline_config.py:19) never creates an *existing override dict with `override_global_config` absent/False* — it only tests a camera with **no entry at all**, where `.get(..., default)` happens to return the global. The two guard mutants are therefore never distinguished. |
| C2 | `get_camera_config`: **global fallback default deleted** on the override-lookup `.get(...)` — `global_conf["threshold_stdev"]` / `global_conf["min_samples"]` → `None` or argument removed. Real behaviour change (returns `None` instead of the global default); the surviving mutants are only reached on a code path no test enters. | 4 | gc_19, gc_21, gc_32, gc_34 | TEST-GAP, same root cause as C1: the missing branch is "override active but that one key unset". No test seeds a partial override, so both this and C1 hide behind the same hole. |
| C3 | `set_camera_config`: **validation boundary flipped** — `< 0.5` → `<= 0.5`, `< 1` → `<= 1`, and the constants widened to `< 1.5`, `< 2`. Legitimate inputs at the boundary (`0.5`, `1`) start raising `ValueError`. | 4 | sc_3, sc_4, sc_10, sc_11 | TEST-GAP. `test_set_camera_config_validates_threshold_min` (line 194) probes `0.3` and `test_set_camera_config_accepts_valid_range` (line 227) probes `2.5`/`10` — the boundary values `0.5` and `1` themselves are never asserted, and the widened-constant mutants pass `2.5`. Also unguarded in practice only because `backend/api/routes/cameras.py:2135-2139` re-implements the same check — a different module that mutation testing will break independently. |
| C4 | `reset_camera_baseline`: **WHERE predicate inverted** `==` → `!=` on both deletes (activity + class). The delete runs, the mock returns a rowcount, the call count is 2 — but production wipes *every other camera's* baselines. | 2 | rs_5, rs_13 | TEST-GAP. `test_reset_camera_baseline_no_side_effects` (line 162) is mis-named — it asserts only the mocked rowcounts and `execute.call_count == 2`, and **never inspects the statement passed to `session.execute`**, so it cannot see the inverted predicate. The integration test that does check this (`test_reset_baseline_only_affects_target_camera`) is not in the run (see finding above). |
| C5 | `reset_camera_baseline`: **`rowcount or 0` fallback → `rowcount or 1`** — a driver that reports `rowcount = 0` (or `None`/`-1`, which the guard also catches) makes the API report `1` baseline deleted when nothing was deleted. | 2 | rs_8, rs_16 | TEST-GAP. Every unit test mocks `rowcount` to a positive int (168/42, 50/15, 100/30), so the `or` fallback is never executed. The zero path exists only in the unslected integration test `test_reset_baseline_returns_zero_for_no_data`. |
| C9 | `set_camera_config`: **validation message text clobbered** (`XX…XX` / UPPER) on both `raise ValueError(...)` calls — 2 per message. Real string change, only observable via the message. | 4 | sc_6, sc_7, sc_13, sc_14 | TEST-GAP — "test exists but asserts too weakly". `assert "threshold_stdev" in str(...).lower()` (line 207) and `assert "0.5" in str(...)` (line 208) pass on all four copies: the field-name substring survives both clobber and uppercasing (lowered afterwards), and `"0.5"`/`"1"` survive uppercasing. The UPPER variants *would* be killed by the integration suite's case-sensitive `match=r"at least 0\.5"` — but that suite is not in the run (finding above). |

### LOW-VALUE (2 clusters, 4 mutants)

| ID | Pattern | N | Keys | Note |
|----|---------|---|------|------|
| C6 | `reset_camera_baseline`: **whole `delete(...)` expression replaced by `None`**, i.e. `session.execute(None)` (activity + class). | 2 | rs_2, rs_10 | Real change (production raises `ArgumentError: SQL expression object expected`), but killing it needs only an argument-type assertion on `session.execute` — same assertion drafted in D5 for C4, so no separate test. Classified LOW-VALUE (trivially-loud TypeError on the real path) rather than TEST-GAP to keep the drafting budget on C1–C5; it is nevertheless killed by D5. |
| C7 | `reset_camera_baseline`: **`delete(...)` → `where(None)`** → `DELETE FROM activity_baselines WHERE NULL`, which deletes nothing. | 2 | rs_3, rs_11 | Real change; same missing assertion as C4 (statement scoping) and likewise killed by D5. `WHERE NULL` rendering verified against SQLAlchemy in this repo's env. |

### EQUIVALENT (1 cluster, 11 mutants)

| ID | Pattern | N | Keys | Note |
|----|---------|---|------|------|
| C8 | `set_camera_config` / `reset_camera_baseline`: **pure log-message text mutated** — the four f-string interpolations' dict keys clobbered (`get(None)`, `get('XXkeyXX')`, `get('KEY_UPPER')`), and both whole message expressions elided to `logger.info(None)`. | 11 | sc_30, sc_31, sc_32, sc_33, sc_34, sc_35, sc_36, sc_37, sc_38, sc_39, rs_17 | All changes stay inside `logger.info(...)`'s message argument. The clobbered-key copies only render `threshold=None` inside an info line; the elided copies remain valid `info(None)` calls. `get_logger` returns a plain stdlib `logging.Logger` (backend/core/logging.py:1107-1123) and no test inspects log records for this module. Pure message text → EQUIVALENT. |

## Explicit partition (sums to 33, no key twice)

| Cluster | Class | N | Keys |
|---------|-------|---|------|
| C1 | TEST-GAP | 2 | gc_17, gc_30 |
| C2 | TEST-GAP | 4 | gc_19, gc_21, gc_32, gc_34 |
| C3 | TEST-GAP | 4 | sc_3, sc_4, sc_10, sc_11 |
| C4 | TEST-GAP | 2 | rs_5, rs_13 |
| C5 | TEST-GAP | 2 | rs_8, rs_16 |
| C9 | TEST-GAP | 4 | sc_6, sc_7, sc_13, sc_14 |
| C6 | LOW-VALUE | 2 | rs_2, rs_10 |
| C7 | LOW-VALUE | 2 | rs_3, rs_11 |
| C8 | EQUIVALENT | 11 | sc_30, sc_31, sc_32, sc_33, sc_34, sc_35, sc_36, sc_37, sc_38, sc_39, rs_17 |
| **Total** | | **33** | |

Key-prefix legend: `gc_` = `xǁBaselineConfigServiceǁget_camera_config__mutmut_`, `sc_` = `…ǁset_camera_config__mutmut_`, `rs_` = `…ǁreset_camera_baseline__mutmut_`. Full module prefix is `backend.services.baseline_config.`.

## Drafted tests

Target file for all six: `backend/tests/unit/services/test_baseline_config.py` (the only covering test file; style = class-scoped, function-local imports, `_camera_configs.clear()` reset, `AsyncMock` session).

### D1 → kills C1 + C2 (6 mutants, the override gate)

```python
class TestOverrideSemantics:
    """Tests for the override_global_config gate in get_camera_config.

    NEM-4921: the gate is the whole point of the feature — a stored override
    dict must be IGNORED unless override_global_config is explicitly True, and
    a partial override must fall back to the global default per key.
    """

    @pytest.mark.asyncio
    async def test_override_flag_false_ignores_stored_per_camera_values(self) -> None:
        """Stored per-camera values stay dormant while override_global_config is False."""
        from backend.services.baseline_config import BaselineConfigService, _camera_configs

        _camera_configs.clear()
        _camera_configs["camera-1"] = {
            "threshold_stdev": 9.0,
            "min_samples": 99,
            "override_global_config": False,
        }

        service = BaselineConfigService()
        config = await service.get_camera_config("camera-1")

        assert config["override_global_config"] is False
        assert config["threshold_stdev"] == config["global_config"]["threshold_stdev"]
        assert config["min_samples"] == config["global_config"]["min_samples"]
        # and the globals are the documented defaults, not the stored override
        assert config["threshold_stdev"] == 2.0
        assert config["min_samples"] == 10

    @pytest.mark.asyncio
    async def test_override_flag_absent_defaults_to_global(self) -> None:
        """An override dict with no override_global_config key behaves as global."""
        from backend.services.baseline_config import BaselineConfigService, _camera_configs

        _camera_configs.clear()
        _camera_configs["camera-1"] = {"threshold_stdev": 9.0, "min_samples": 99}

        service = BaselineConfigService()
        config = await service.get_camera_config("camera-1")

        assert config["override_global_config"] is False
        assert config["threshold_stdev"] == 2.0
        assert config["min_samples"] == 10

    @pytest.mark.asyncio
    async def test_partial_override_falls_back_to_global_per_key(self) -> None:
        """Active override with only threshold set keeps the global min_samples."""
        from backend.services.baseline_config import BaselineConfigService, _camera_configs

        _camera_configs.clear()
        _camera_configs["camera-1"] = {
            "threshold_stdev": 3.75,
            "override_global_config": True,
        }

        service = BaselineConfigService()
        config = await service.get_camera_config("camera-1")

        assert config["threshold_stdev"] == 3.75
        # the deleted-default mutants return None here
        assert config["min_samples"] == 10
        assert config["min_samples"] == config["global_config"]["min_samples"]

    @pytest.mark.asyncio
    async def test_partial_override_with_only_min_samples(self) -> None:
        """Active override with only min_samples set keeps the global threshold."""
        from backend.services.baseline_config import BaselineConfigService, _camera_configs

        _camera_configs.clear()
        _camera_configs["camera-1"] = {
            "min_samples": 25,
            "override_global_config": True,
        }

        service = BaselineConfigService()
        config = await service.get_camera_config("camera-1")

        # deleted-default mutants return None here
        assert config["threshold_stdev"] == 2.0
        assert config["min_samples"] == 25
```

TDD: `test_partial_override_falls_back_to_global_per_key` asserts `10` but the mutant returns `None` → red; original returns `10` → green. `test_override_flag_false_ignores_stored_per_camera_values` asserts `2.0` but the `or True` mutant returns `9.0` → red.

### D2 → kills C3 (validation boundary)

```python
class TestValidationBoundaries:
    """Boundary tests for set_camera_config validation (the `<` comparisons)."""

    @pytest.mark.asyncio
    async def test_threshold_exactly_at_minimum_is_accepted(self) -> None:
        """threshold_stdev == 0.5 is legal: the guard is `< 0.5`, not `<= 0.5`."""
        from backend.services.baseline_config import BaselineConfigService, _camera_configs

        _camera_configs.clear()
        service = BaselineConfigService()

        config = await service.set_camera_config(camera_id="camera-1", threshold_stdev=0.5)

        assert config["threshold_stdev"] == 0.5

    @pytest.mark.asyncio
    async def test_min_samples_exactly_at_minimum_is_accepted(self) -> None:
        """min_samples == 1 is legal: the guard is `< 1`, not `<= 1`."""
        from backend.services.baseline_config import BaselineConfigService, _camera_configs

        _camera_configs.clear()
        service = BaselineConfigService()

        config = await service.set_camera_config(camera_id="camera-1", min_samples=1)

        assert config["min_samples"] == 1

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "kwargs",
        [
            {"threshold_stdev": 1.0},
            {"threshold_stdev": 1.25},
            {"min_samples": 2},
        ],
    )
    async def test_values_just_above_minimum_are_accepted(self, kwargs: dict) -> None:
        """The minimum constants are 0.5 / 1 — slightly above must not raise."""
        from backend.services.baseline_config import BaselineConfigService, _camera_configs

        _camera_configs.clear()
        service = BaselineConfigService()

        config = await service.set_camera_config(camera_id="camera-1", **kwargs)

        assert config["threshold_stdev"] == kwargs.get("threshold_stdev", 2.0)
        assert config["min_samples"] == kwargs.get("min_samples", 10)
```

TDD: on `<= 0.5` the first test raises `ValueError` instead of returning → red; on `< 1.5` / `< 2` the parametrised values raise → red; original passes all → green.

### D3 → kills C9 (and the service-level half of the message contract)

```python
class TestValidationMessages:
    """The service's own ValueError copy is part of the API contract (cameras.py re-raises it)."""

    @pytest.mark.asyncio
    async def test_threshold_error_message_is_exact(self) -> None:
        from backend.services.baseline_config import BaselineConfigService, _camera_configs

        _camera_configs.clear()
        service = BaselineConfigService()

        with pytest.raises(ValueError, match=r"^threshold_stdev must be at least 0\.5$"):
            await service.set_camera_config(camera_id="camera-1", threshold_stdev=0.3)

    @pytest.mark.asyncio
    async def test_min_samples_error_message_is_exact(self) -> None:
        from backend.services.baseline_config import BaselineConfigService, _camera_configs

        _camera_configs.clear()
        service = BaselineConfigService()

        with pytest.raises(ValueError, match=r"^min_samples must be at least 1$"):
            await service.set_camera_config(camera_id="camera-1", min_samples=0)
```

TDD: `match` is case-sensitive and anchored, so the `XX…XX` and `UPPER CASE` copies fail to match → red; original matches → green.

### D4 → kills C5 (rowcount fallback)

```python
class TestResetRowCountFallback:
    """rowcount==0/None from the driver must report 0, never a fabricated count."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("rowcount", [0, None, -1])
    async def test_zero_rowcount_reports_zero_deletions(self, rowcount: int | None) -> None:
        from unittest.mock import AsyncMock

        from backend.services.baseline_config import BaselineConfigService

        mock_session = AsyncMock()
        activity_result = MagicMock()
        activity_result.rowcount = rowcount
        class_result = MagicMock()
        class_result.rowcount = rowcount
        mock_session.execute.side_effect = [activity_result, class_result]

        service = BaselineConfigService()
        result = await service.reset_camera_baseline(camera_id="camera-1", session=mock_session)

        assert result == {"activity_baselines_deleted": 0, "class_baselines_deleted": 0}
```

TDD: on `rowcount or 1` the assert gets `1` → red; original coerces to `0` → green.

### D5 → kills C4 + C6 + C7 (delete-statement contract)

```python
class TestResetDeleteStatements:
    """reset_camera_baseline must delete per-table, scoped to exactly this camera."""

    @staticmethod
    def _sql(statement: object) -> str:
        from sqlalchemy.dialects import postgresql

        return str(statement).compile(dialect=postgresql.dialect())

    @pytest.mark.asyncio
    async def test_each_delete_targets_the_expected_table_scoped_to_camera(self) -> None:
        from unittest.mock import AsyncMock

        from backend.services.baseline_config import BaselineConfigService

        mock_session = AsyncMock()
        activity_result = MagicMock()
        activity_result.rowcount = 1
        class_result = MagicMock()
        class_result.rowcount = 1
        mock_session.execute.side_effect = [activity_result, class_result]

        service = BaselineConfigService()
        await service.reset_camera_baseline(camera_id="camera-1", session=mock_session)

        assert mock_session.execute.call_count == 2
        activity_stmt, class_stmt = (c.args[0] for c in mock_session.execute.call_args_list)

        activity_sql = self._sql(activity_stmt)
        class_sql = self._sql(class_stmt)

        # right tables, real WHERE clause, positive camera scoping, bound to camera-1
        assert "DELETE FROM activity_baselines" in activity_sql
        assert "DELETE FROM class_baselines" in class_sql
        for sql in (activity_sql, class_sql):
            assert "WHERE NULL" not in sql
            assert "camera_id = " in sql
            assert "camera_id != " not in sql and "camera_id <>" not in sql
        params = activity_stmt.compile().params
        assert params["camera_id_1"] == "camera-1"
```

TDD: on `==`→`!=` the `camera_id != ` guard trips → red; on `where(None)` the `WHERE NULL` guard trips → red; on the whole expression → `None`, `str(None).compile(...)` raises / the table name is missing → red; original passes → green. (If `params["camera_id_1"]` keys differently on this SQLAlchemy version, fall back to `assert "camera-1" in activity_stmt.compile().params.values()`.)

## Where the assertions were missing (file:line)

- `backend/tests/unit/services/test_baseline_config.py:19` `test_get_camera_config_no_override` — only tests "no entry", never "entry with flag off" → hides C1/C2.
- `backend/tests/unit/services/test_baseline_config.py:194` / `:211` / `:227` — validation probed only at 0.3 / 0 / 2.5, never at the boundary → hides C3; message asserted by substring only → hides C9.
- `backend/tests/unit/services/test_baseline_config.py:112`, `:138`, `:162`, `:318` — all four reset tests mock `rowcount` positive and assert only counts + `call_count`, never the statement → hides C4/C5/C6/C7. `:162` `test_reset_camera_baseline_no_side_effects` is mis-named: it proves nothing about side effects.
- `backend/tests/integration/test_baseline_config_service.py:242` (`returns_zero_for_no_data`), `:257` (`only_affects_target_camera`), `:145`/`:156` (message regex) — the tests that *would* kill C4/C5/C9, **absent from the mutation run's test selection** (see finding above). Recommend WP4.4 also fix the run selection rather than duplicating all of this into unit tests.
