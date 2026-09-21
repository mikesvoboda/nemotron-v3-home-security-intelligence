# WP4.4 Triage Dossier — `backend/services/alert_dedup.py`

- **Module:** `backend/services/alert_dedup.py`
- **Survivors:** 52 (of 173 total mutants; 121 killed, 0 unchecked)
- **Covering tier (from `mutmut-stats.json` → `tests_by_mangled_function_name`):** *unit only.* `pyproject.toml [tool.mutmut] pytest_add_cli_args_test_selection = ["backend/tests/unit"]`. `backend/tests/integration/test_alert_dedup.py` never runs under mutmut — this is the root cause of the dominant pattern below.
- **Covering test files (unit):** `backend/tests/unit/services/test_alert_dedup.py` (every service method; `_validate_dedup_key` 84 tests, `check_duplicate` 27, `get_recent_alerts_for_key` 10, `get_duplicate_stats` 9, `create_alert_if_not_duplicate` 13, `get_cooldown_for_rule` 6). `backend/tests/unit/services/test_dedup_key.py` also touches `build_dedup_key` (0 survivors there).

## Why so many survive (one sentence)

Every service method runs against `mock_session = AsyncMock()` (`backend/tests/unit/services/test_alert_dedup.py:31-38`). The methods **build a SQLAlchemy `stmt` and pass it to `session.execute(stmt)`**, but the mock returns a canned result and **the `stmt` argument is never inspected**. So any mutation to the query's *construction* (predicate dropped, `==`→`!=`, `>=`→`>`, `limit`, `order_by`, `select(None)`, `stmt = None`, cutoff sign) produces identical observable behavior in the unit tier. 40 of the 52 survivors are this single blindness.

## Cluster table (counts sum to 52)

| ID | Pattern | Count | Class | Example keys (≤3) |
|----|---------|:----:|-------|-------------------|
| CL-2 | Whole-statement clobber: `stmt = None` / `total_stmt = None` / `unique_stmt = None` replaces the built query | 5 | TEST-GAP | `check_duplicate__mutmut_6`, `get_cooldown_for_rule__mutmut_3`, `get_duplicate_stats__mutmut_5` |
| CL-6 | Single WHERE predicate dropped: `.where(<clause>)` → `.where(None)` (removes `dedup_key =` or `created_at >=` or `alert_rules.id =`) | 7 | TEST-GAP | `check_duplicate__mutmut_11`, `check_duplicate__mutmut_10`, `get_duplicate_stats__mutmut_6` |
| CL-8 | Comparison operator flipped: `==`→`!=` or `>=`→`>` on the key / timestamp / rule-id filter | 7 | TEST-GAP | `check_duplicate__mutmut_13`, `check_duplicate__mutmut_14`, `get_cooldown_for_rule__mutmut_6` |
| CL-9 | `session.execute(stmt)` → `session.execute(None)` (query discarded at call site) | 5 | TEST-GAP | `check_duplicate__mutmut_18`, `get_duplicate_stats__mutmut_10`, `get_recent_alerts_for_key__mutmut_15` |
| CL-7 | Selected entity clobbered: `select(Alert)`/`select(AlertRule)` → `select(None)` (loses `FROM …`) | 5 | TEST-GAP | `check_duplicate__mutmut_12`, `get_cooldown_for_rule__mutmut_5`, `get_duplicate_stats__mutmut_7` |
| CL-1 | Cooldown/window sign flip: `datetime.now(UTC) - timedelta(…)` → `+ timedelta(…)` (cutoff lands in the future → window always empty) | 3 | TEST-GAP | `check_duplicate__mutmut_3`, `get_recent_alerts_for_key__mutmut_3`, `get_duplicate_stats__mutmut_2` |
| CL-4 | `LIMIT` weakened: `.limit(1)`→`.limit(2)` / `.limit(None)`; `.limit(limit)`→`.limit(None)` | 3 | TEST-GAP | `check_duplicate__mutmut_15`, `check_duplicate__mutmut_8`, `get_recent_alerts_for_key__mutmut_7` |
| CL-10 | Naive cutoff: `datetime.now(UTC)` → `datetime.now(None)` (breaks the tz-aware contract the docstrings call out) | 2 | TEST-GAP | `get_recent_alerts_for_key__mutmut_4`, `get_duplicate_stats__mutmut_3` |
| CL-5 | Sort dropped: `.order_by(Alert.created_at.desc())` → `.order_by(None)` (loses most-recent-first) | 2 | TEST-GAP | `check_duplicate__mutmut_9`, `get_recent_alerts_for_key__mutmut_8` |
| CL-14 | Persisted alert loses rule attribution: `rule_id=rule_id` → `rule_id=None` / clause removed in `Alert(...)` | 2 | TEST-GAP | `create_alert_if_not_duplicate__mutmut_13`, `create_alert_if_not_duplicate__mutmut_20` |
| CL-11 | `dedup_ratio` zero-guard widened: `if total_alerts > 0` → `if total_alerts > 1` (single-alert window reports ratio 0.0 instead of 1.0) | 1 | TEST-GAP | `get_duplicate_stats__mutmut_34` |
| CL-12 | Cooldown not forwarded: `check_duplicate(dedup_key, cooldown_seconds)` → `check_duplicate(dedup_key, )` (silently reverts to default 300) | 1 | TEST-GAP | `create_alert_if_not_duplicate__mutmut_8` |
| CL-15 | Persisted object discarded: `session.add(alert)` → `session.add(None)` | 1 | TEST-GAP | `create_alert_if_not_duplicate__mutmut_28` |
| CL-3 | Lock clause: `.with_for_update(skip_locked=True)` → `skip_locked=None` / `skip_locked=False` | 2 | EQUIVALENT | `check_duplicate__mutmut_7`, `check_duplicate__mutmut_16` |
| CL-16 | Exception **message text** only (`"XX…XX"` wrap, `None`→`none`) | 5 | EQUIVALENT | `_validate_dedup_key__mutmut_3`, `_validate_dedup_key__mutmut_4`, `_validate_dedup_key__mutmut_17` |
| CL-13 | Guard boolean flip: `if dedup_result.is_duplicate and dedup_result.existing_alert` → `or` | 1 | EQUIVALENT | `create_alert_if_not_duplicate__mutmut_9` |

**TEST-GAP total: 44 · EQUIVALENT total: 8 · LOW-VALUE total: 0.** Sum = 52.

## EQUIVALENT rationale

- **CL-3 (skip_locked, 2):** rendered with `postgresql.dialect()` under SQLAlchemy 2.0.53, `with_for_update(skip_locked=True|False|None)` all emit `… FOR UPDATE` (`skip_locked` only alters the emitted `SKIP LOCKED` keyword, which the test-observable unit tier never renders and the mock never executes). `skip_locked=True→False/None` is semantically equivalent at the statement level *within this mock tier*. The **integration** file `TestConcurrencyProtection.test_for_update_skip_locked_does_not_block_different_keys` (integration:583) exercises the real DB and would catch a true lock-behavior regression — but that file is not in the mutmut selection. Not worth asserting at the unit level.
- **CL-16 (message text, 5):** every `pytest.raises(match=…)` in `TestValidateDedupKey` uses a substring (`"cannot be empty"`, `"whitespace-only"`, `"leading or trailing whitespace"`, `"invalid characters"`) that is unchanged by the `"XX…XX"` wrap or the `None`→`none` case change. Raise type and message *stem* are identical → truly equivalent.
- **CL-13 (`and`→`or`, 1):** the sole producer of `dedup_result` is `check_duplicate`, which always sets `existing_alert` when `is_duplicate` is True and leaves it `None` when False. The states where `and` and `or` diverge (`True,None` or `False,truthy`) are never produced → equivalent for all real inputs; only killable via an injected stub, which would be testing the branch, not the behavior.

## Notes on the TEST-GAP clusters

- **CL-2/CL-6/CL-7/CL-8/CL-9/CL-4/CL-5 all collapse to one fix.** A single assertion that captures `session.execute`'s first positional argument, checks it is a `Select`, compiles it, and inspects the SQL text + bound params kills **40 mutants across all four query methods at once**. This is the highest-leverage change in the module.
- **CL-1 (cutoff sign) and CL-10 (naive cutoff)** are killed by the same params check inside those tests: assert the bound `created_at` param is timezone-aware and `< datetime.now(UTC)` before the call.
- **`check_duplicate` is a real correctness path.** CL-4 `limit(2)` + `scalar_one_or_none()` (source `alert_dedup.py:192`) would raise `MultipleResultsFound` on a genuine duplicate with 2 in-window rows; CL-1 makes dedup never fire (alert fatigue). The integration tier does assert some of this (`test_check_duplicate_existing_alert_outside_cooldown` integration:123 asserts the window on a real DB) — the *gap is that mutmut only charges the unit tier*, so these count as unit TEST-GAP.
- **CL-14/CL-12/CL-15** are unit-tier gaps in `create_alert_if_not_duplicate`: `test_creates_new_alert_when_no_duplicate` (`test_alert_dedup.py:546-572`) asserts `event_id/dedup_key/severity/status/channels/metadata` but **never `rule_id`**, and asserts `add.assert_called_once()` **without the argument**, and `test_uses_rule_cooldown_when_not_specified` (`:596-620`) asserts only `is_new is True`, never the cooldown forwarded to `check_duplicate`.

## Drafted tests (UNVERIFIED — not yet run red/green)

Target file: `backend/tests/unit/services/test_alert_dedup.py`. Follows existing style (`mock_session` AsyncMock fixture, `@pytest.mark.asyncio`, class methods). **TDD procedure:** each `assert` is written against the ORIGINAL's observable SQL/params/args — it fails red on the cluster's mutant diff and passes green on the original. Add these imports at top of the file (module already imports `datetime.UTC`, `MagicMock`, `patch`):

```python
import re

from sqlalchemy import Select
from sqlalchemy.dialects import postgresql
```

Shared helper (module-level, near the fixtures):

```python
def _compiled_first_execute(mock_session, call_index: int = 0):
    """Compile the stmt that was handed to session.execute[call_index].

    Asserting the argument is a real SQLAlchemy Select (before compiling) is
    itself the kill for the `stmt = None` and `execute(None)` clobber mutants.
    Returns (sql_text_lower, bound_params).
    """
    stmt = mock_session.execute.call_args_list[call_index].args[0]
    assert isinstance(stmt, Select), f"session.execute got non-Select arg: {stmt!r}"
    compiled = stmt.compile(dialect=postgresql.dialect())
    return re.sub(r"\s+", " ", str(compiled)).strip().lower(), compiled.params
```

### T1 — `check_duplicate` query shape (kills CL-2, CL-4, CL-5, CL-6, CL-7, CL-8, CL-9, CL-1 for this method: 11 mutants)

```python
class TestCheckDuplicateQueryShape:
    """check_duplicate must build a key+window-filtered, DESC-ordered, LIMIT 1,
    FOR UPDATE query (unit tier never inspects the stmt the mock swallows).

    UNVERIFIED - not yet run red/green.
    """

    @pytest.mark.asyncio
    async def test_check_duplicate_query_constrains_key_and_window(
        self, mock_session: AsyncMock
    ) -> None:
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        service = AlertDeduplicationService(mock_session)
        before = datetime.now(UTC)
        await service.check_duplicate("front_door:person", cooldown_seconds=300)

        sql, params = _compiled_first_execute(mock_session)

        # real query over alerts (kills select(None) / stmt=None / execute(None))
        assert "from alerts" in sql
        # dedup_key equality — present, and not flipped to !=
        assert "alerts.dedup_key = " in sql
        assert "!=" not in sql
        # cooldown window filter as >= (not dropped, not flipped to >)
        assert "alerts.created_at >= " in sql
        cutoff = params["created_at_1"]
        assert cutoff.tzinfo is not None, "cutoff must be timezone-aware"
        assert cutoff < before, "cutoff must be now - cooldown, not now + cooldown"
        # most-recent-first ordering (kills order_by(None))
        assert "order by alerts.created_at desc" in sql
        # exactly one row (kills limit(None) and limit(2))
        assert "limit " in sql
        assert 1 in params.values(), "LIMIT must be 1"
        assert 2 not in params.values()
        # row lock for the check-then-insert (kills whole-statement clobber)
        assert "for update" in sql
```

### T2 — `get_recent_alerts_for_key` query shape (kills 11 mutants: CL-2,4,5,6,7,8,9 + CL-1, CL-10)

```python
class TestGetRecentAlertsQueryShape:
    """UNVERIFIED - not yet run red/green."""

    @pytest.mark.asyncio
    async def test_get_recent_alerts_query_window_order_and_limit(
        self, mock_session: AsyncMock
    ) -> None:
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        service = AlertDeduplicationService(mock_session)
        before = datetime.now(UTC)
        await service.get_recent_alerts_for_key("front_door:person")  # hours=24, limit=10

        sql, params = _compiled_first_execute(mock_session)

        assert "from alerts" in sql
        assert "alerts.dedup_key = " in sql
        assert "!=" not in sql
        assert "alerts.created_at >= " in sql
        cutoff = params["created_at_1"]
        assert cutoff.tzinfo is not None, "cutoff must be tz-aware (kills datetime.now(None))"
        assert cutoff < before, "cutoff must be now - hours, not now + hours"
        assert "order by alerts.created_at desc" in sql
        assert "limit " in sql
        assert 10 in params.values(), "default LIMIT must be 10"
```

### T3 — `get_duplicate_stats` window on both queries + single-alert ratio (kills 13 mutants: CL-2,6,7,8,9 + CL-1, CL-10 + CL-11)

```python
class TestGetDuplicateStatsQueryShape:
    """UNVERIFIED - not yet run red/green."""

    @pytest.mark.asyncio
    async def test_stats_both_queries_filter_by_window(
        self, mock_session: AsyncMock
    ) -> None:
        mock_total = MagicMock()
        mock_total.scalars.return_value.all.return_value = []
        mock_unique = MagicMock()
        mock_unique.scalars.return_value.all.return_value = []
        mock_session.execute.side_effect = [mock_total, mock_unique]

        service = AlertDeduplicationService(mock_session)
        before = datetime.now(UTC)
        await service.get_duplicate_stats()

        for idx, expect_distinct in ((0, False), (1, True)):
            sql, params = _compiled_first_execute(mock_session, idx)
            assert "from alerts" in sql
            assert "alerts.created_at >= " in sql
            cutoff = params["created_at_1"]
            assert cutoff.tzinfo is not None, "cutoff must be tz-aware (kills now(None))"
            assert cutoff < before, "window must look backward, not forward"
            if expect_distinct:
                assert "distinct alerts.dedup_key" in sql
            else:
                assert "distinct" not in sql

    @pytest.mark.asyncio
    async def test_single_alert_window_ratio_is_one(
        self, mock_session: AsyncMock
    ) -> None:
        """total_alerts == 1 must yield ratio 1.0, not 0.0 (kills `> 0` -> `> 1`)."""
        mock_total = MagicMock()
        mock_total.scalars.return_value.all.return_value = [MagicMock()]  # exactly 1
        mock_unique = MagicMock()
        mock_unique.scalars.return_value.all.return_value = ["only_key"]
        mock_session.execute.side_effect = [mock_total, mock_unique]

        service = AlertDeduplicationService(mock_session)
        stats = await service.get_duplicate_stats()

        assert stats["total_alerts"] == 1
        assert stats["unique_dedup_keys"] == 1
        assert stats["dedup_ratio"] == 1.0
```

### T4a — `get_cooldown_for_rule` query shape (kills all 5 mutants: CL-2,6,7,8,9)

```python
class TestGetCooldownQueryShape:
    """UNVERIFIED - not yet run red/green."""

    @pytest.mark.asyncio
    async def test_get_cooldown_query_targets_rule_id(
        self, mock_session: AsyncMock, sample_rule: AlertRule
    ) -> None:
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_rule
        mock_session.execute.return_value = mock_result

        service = AlertDeduplicationService(mock_session)
        await service.get_cooldown_for_rule(sample_rule.id)

        sql, params = _compiled_first_execute(mock_session)
        assert "from alert_rules" in sql
        assert "alert_rules.id = " in sql
        assert "!=" not in sql
        assert sample_rule.id in params.values()
```

### T4b — `create_alert_if_not_duplicate` persists rule_id / alert / cooldown (kills CL-14, CL-12, CL-15: 4 mutants)

```python
class TestCreateAlertPersistsArgs:
    """UNVERIFIED - not yet run red/green."""

    @pytest.mark.asyncio
    async def test_created_alert_keeps_rule_id_and_is_the_added_object(
        self, mock_session: AsyncMock
    ) -> None:
        rule_id = str(uuid.uuid4())
        mock_dedup = MagicMock()
        mock_dedup.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_dedup

        service = AlertDeduplicationService(mock_session)
        alert, is_new = await service.create_alert_if_not_duplicate(
            event_id=1,
            dedup_key="front_door:person",
            rule_id=rule_id,
            cooldown_seconds=300,
        )

        assert is_new is True
        # kills rule_id=rule_id -> None / removed (CL-14)
        assert alert.rule_id == rule_id
        # kills session.add(alert) -> add(None) (CL-15)
        assert mock_session.add.call_args.args[0] is alert

    @pytest.mark.asyncio
    async def test_explicit_cooldown_is_forwarded_to_check_duplicate(
        self, mock_session: AsyncMock
    ) -> None:
        """check_duplicate must receive the cooldown_seconds, not drop it (CL-12)."""
        fake_check = AsyncMock(return_value=DedupResult(is_duplicate=False))
        service = AlertDeduplicationService(mock_session)
        with patch.object(AlertDeduplicationService, "check_duplicate", new=fake_check):
            await service.create_alert_if_not_duplicate(
                event_id=1,
                dedup_key="front_door:person",
                cooldown_seconds=123,
            )
        fake_check.assert_awaited_once_with("front_door:person", 123)
```

**Coverage of drafted tests:** T1+T2+T3+T4a+T4b together address all 44 TEST-GAP survivors across every TEST-GAP cluster. The 8 EQUIVALENT survivors (CL-3, CL-13, CL-16) need no new test.

## File:line index of covering tests

- `backend/tests/unit/services/test_alert_dedup.py:31` — `mock_session` AsyncMock fixture (root cause).
- `.../test_alert_dedup.py:168` `TestValidateDedupKey` — asserts via `pytest.raises(match=substring)`, so CL-16 message-text mutants survive.
- `.../test_alert_dedup.py:353` `TestCheckDuplicate`; `:425` `test_uses_utc_for_comparison` asserts `datetime.now(UTC)` but only for `check_duplicate` (not CL-10's methods).
- `.../test_alert_dedup.py:482` `TestGetCooldownForRule`; `:543` `TestCreateAlertIfNotDuplicate` (`:564-572` omits `rule_id`, `:571` `add.assert_called_once()` w/o arg); `:676` `TestGetRecentAlertsForKey`; `:778` `TestGetDuplicateStats` (never runs `total_alerts == 1`).
- `.../test_alert_dedup.py:977` `TestConcurrencyScenarios.test_check_duplicate_uses_for_update` — asserts only `execute.assert_called_once()`, not the lock clause.
- `backend/tests/integration/test_alert_dedup.py` — real-DB coverage (`TestDedupCooldownBehavior:416`, `TestConcurrencyProtection:520`) that would kill much of this cluster, **but excluded from mutmut's unit-only selection** (pyproject `[tool.mutmut]`).
