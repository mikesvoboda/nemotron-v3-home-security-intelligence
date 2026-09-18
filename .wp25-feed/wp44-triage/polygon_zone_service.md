# WP4.4 Triage Dossier — backend/services/polygon_zone_service.py

- Survivors: **100** of 181 keys (80 killed, 1 unchecked). Extracted from
  `mutants/backend/services/polygon_zone_service.py.meta` (`exit_code_by_key`, 0 == survived).
- Diffs extracted by parsing `mutants/backend/services/polygon_zone_service.py` (variant bodies
  diffed against their `__mutmut_orig` sibling). Helper: `/tmp/wp25/wp44-triage/extract2.py`, raw
  diffs in `/tmp/wp25/wp44-triage/diffs.json`.
- Sole covering test file (per `mutants/mutmut-stats.json` → `tests_by_mangled_function_name`):
  `backend/tests/unit/services/test_polygon_zone_service.py` (classes at lines: TestCreateZone :92,
  TestGetZone :193, TestGetZonesByCamera :234, TestGetZonesByType :302, TestUpdateZone :343,
  TestDeleteZone :454, TestUpdateCount :513, TestSetActive :603, TestResetAllCounts :682).
  **Root cause of the survivor mass:** every test fully mocks `db.execute` and most patch
  `get_zone`/`get_zones_by_camera` — the built SQL statement is *never inspected* and session
  methods are only checked with `.called`, never call-args. Log tests assert only
  `call_args[0][0]` (the message), never `extra`.
- Key schema fact for the EQUIVALENT calls: `PolygonZoneType` is a `StrEnum`
  (`backend/api/schemas/analytics_zone.py:14`) and pydantic coerces/validates `zone_type` to it
  (Create :269, Update :381), so `str(enum) == enum.value` and the `hasattr(...,"value")` defensive
  branch returns the same string on both paths.

## Cluster table

| # | Cluster | Count | Class | Example keys | Note |
|---|---------|-------|-------|--------------|------|
| C1 | `extra={...}` log-dict **keys renamed** (`XXkXX`/`K_UPPER`) in create/update/delete/update_count/set_active/reset | 28 | EQUIVALENT | create_zone_37, update_zone_41, reset_all_counts_15 | log payload text only; tests patch logger and assert message only. |
| C2 | `extra={...}` dict **removed or set to `None`** in `logger.*` calls | 12 | EQUIVALENT | create_zone_34, set_active_9, update_count_12 | message + call-count unchanged; no structured-log consumer asserted. |
| C3 | `zone_type` **hasattr guard mangled** (`and False`, `or True`, `hasattr(None,…)`, `"XXvalueXX"`, `"VALUE"`, `str(None)`) | 12 | EQUIVALENT | create_zone_2, update_zone_22 | StrEnum: both branches yield the same string; `str(None)` else-branch unreachable under pydantic. |
| C4 | delete_zone log-only locals `camera_id`/`zone_name` → `None` | 2 | EQUIVALENT | delete_zone_5, delete_zone_6 | vars feed only the log f-string/extra. |
| C5 | `logger.warning(None)` in update_count not-found path | 1 | EQUIVALENT | update_count_7 | test asserts `warning.assert_called_once()`, never content. |
| C6 | `active_only=None` passed to get_zones_by_camera (falsy == False) | 1 | EQUIVALENT | reset_all_counts_3 | `None` is falsy → same unfiltered query as `False`. |
| C7 | update_zone **zone_type dict-key mangled** (`"XXzone_typeXX"`/`"ZONE_TYPE"` lookup/assign, `is not None`→`is None`) | 5 | LOW-VALUE | update_zone_8, update_zone_13 | real change (enum object stored unconverted), but StrEnum equality + String-column serialization make it unobservable except via `type(x) is str`; nobody should assert that. |
| C8 | **session methods called with `None` entity**: `db.add(None)`, `db.refresh(None)`, `db.delete(None)` | 5 | TEST-GAP | create_zone_31, delete_zone_7, set_active_5 | tests assert `.called` only; a real session raises on `None`. |
| C9 | **`get_zone(None)` / `get_zones_by_camera(None,…)` lookup arg nuked** | 5 | TEST-GAP | delete_zone_2, reset_all_counts_2 | patched lookups return the fixture regardless of arg; real DB would miss the row. |
| C10 | create_zone **polygon kwarg dropped/`None`** | 2 | TEST-GAP | create_zone_14, create_zone_23 | no test asserts `result.polygon == data.polygon` — the zone's core data is unasserted at create. |
| C11 | update_zone `model_dump(exclude_unset=False)` (wipes every unset field to None) | 1 | TEST-GAP | update_zone_6 | partial-update contract: tests only assert *provided* fields, never that untouched ones survive. |
| C12 | **WHERE equality flipped `==` → `!=`** (id / camera / type) | 4 | TEST-GAP | get_zone_4, get_zones_by_camera_4, get_zones_by_type_9 | execute is mocked → stmt never inspected; inverted predicate returns the wrong row set. |
| C13 | **`active_only` filter flipped/gutted** (`!= True`, `== False`, `where(None)`) in get_zones_by_camera | 3 | TEST-GAP | get_zones_by_camera_7, get_zones_by_camera_8 | pipeline calls this with `active_only=True`; mutant would process *disabled* zones. |
| C14 | **`order_by(created_at)` dropped / `order_by(None)`** | 2 | TEST-GAP | get_zones_by_camera_10, get_zones_by_type_2 | docstring promises creation-time order; mock hides loss. |
| C15 | **query built/executed from `None`** (`stmt=None`, `select(None)`, `where(None)`, `execute(None)`, predicate args `None`/deleted) | 15 | TEST-GAP | get_zone_6, get_zones_by_type_11, get_zones_by_camera_9 | on a real session all raise; unit mocks return the canned MagicMock for `execute(None)`. |
| C16 | reset_all_counts **`active_only=False` → `True`/omitted** (disabled zones never reset) | 2 | TEST-GAP | reset_all_counts_5, reset_all_counts_6 | `get_zones_by_camera` is autospec-patched; nobody checks the call args. |

Counts: 28+12+12+2+1+1+5+5+5+2+1+4+3+2+15+2 = **100** ✔

## Drafted tests (top TEST-GAP clusters) — // UNVERIFIED - not yet run red/green

TDD procedure (same for all six): run the new test against the mutant copy of the module —
the assertion must **fail (red)** on the mutant diff; run against the original — it must
**pass (green)**. If it's green on the mutant, the assertion doesn't pin the changed behavior.

All tests follow the file's existing style: `@pytest.mark.asyncio`, fixtures
`polygon_zone_service` / `mock_session` / `sample_zone` / `sample_zone_create` (lines 36–84),
`patch.object(service, "get_zone", …, autospec=True)`.

### T1 — TestGetZone::test_get_zone_builds_id_equality_query
Kills: C12 (get_zone), C15 (get_zone 1,2,3,6). Target: TestGetZone.

```python
    @pytest.mark.asyncio
    async def test_get_zone_builds_id_equality_query(
        self,
        polygon_zone_service: PolygonZoneService,
        mock_session: AsyncMock,
        sample_zone: PolygonZone,
    ) -> None:
        """The executed statement must be a SELECT ... WHERE polygon_zones.id = <zone_id>."""
        from sqlalchemy import Select
        from sqlalchemy.dialects import sqlite

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_zone
        mock_session.execute.return_value = mock_result

        await polygon_zone_service.get_zone(42)

        stmt = mock_session.execute.call_args.args[0]
        assert isinstance(stmt, Select)
        sql = str(stmt.compile(dialect=sqlite.dialect(), compile_kwargs={"literal_binds": True}))
        assert "SELECT" in sql
        assert "polygon_zones.id = 42" in sql
        assert "!=" not in sql
```

### T2 — TestGetZonesByCamera::test_active_filter_and_order_present_in_query
Kills: C13 (3), C12 (gzbc_4), C14 (gzbc_10), C15 (gzbc 2,3,9,12). Target: TestGetZonesByCamera.

```python
    @pytest.mark.asyncio
    async def test_active_filter_and_order_present_in_query(
        self,
        polygon_zone_service: PolygonZoneService,
        mock_session: AsyncMock,
    ) -> None:
        """active_only=True must AND on is_active=true and keep the camera filter + ordering."""
        from sqlalchemy import Select
        from sqlalchemy.dialects import sqlite

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        await polygon_zone_service.get_zones_by_camera("cam1", active_only=True)

        stmt = mock_session.execute.call_args.args[0]
        assert isinstance(stmt, Select)
        sql = str(stmt.compile(dialect=sqlite.dialect(), compile_kwargs={"literal_binds": True}))
        assert "polygon_zones.camera_id = 'cam1'" in sql
        assert "!=" not in sql
        assert "polygon_zones.is_active = 1" in sql  # sqlite renders boolean as 1
        assert "ORDER BY polygon_zones.created_at" in sql

        # And the all-zones path must NOT filter on is_active at all.
        mock_session.execute.reset_mock()
        mock_session.execute.return_value = mock_result
        await polygon_zone_service.get_zones_by_camera("cam1", active_only=False)
        sql_all = str(
            mock_session.execute.call_args.args[0].compile(
                dialect=sqlite.dialect(), compile_kwargs={"literal_binds": True}
            )
        )
        assert "is_active" not in sql_all
```

### T3 — TestGetZonesByType::test_query_filters_both_camera_and_type_and_orders
Kills: C12 (gzbt 8,9), C14 (gzbt_2), C15 (gzbt 1,3,4,5,6,7,11). Target: TestGetZonesByType.

```python
    @pytest.mark.asyncio
    async def test_query_filters_both_camera_and_type_and_orders(
        self,
        polygon_zone_service: PolygonZoneService,
        mock_session: AsyncMock,
    ) -> None:
        """WHERE must carry camera_id AND zone_type equality; ORDER BY created_at required."""
        from sqlalchemy import Select
        from sqlalchemy.dialects import sqlite

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        await polygon_zone_service.get_zones_by_type("front_door", "restricted")

        stmt = mock_session.execute.call_args.args[0]
        assert isinstance(stmt, Select)
        sql = str(stmt.compile(dialect=sqlite.dialect(), compile_kwargs={"literal_binds": True}))
        assert "polygon_zones.camera_id = 'front_door'" in sql
        assert "polygon_zones.zone_type = 'restricted'" in sql
        assert "!=" not in sql
        assert "ORDER BY polygon_zones.created_at" in sql
```

### T4 — TestCreateZone::test_create_zone_persists_polygon_and_passes_zone_to_session
Kills: C10 (2), C8 (create_zone 31,32). Target: TestCreateZone.

```python
    @pytest.mark.asyncio
    async def test_create_zone_persists_polygon_and_passes_zone_to_session(
        self,
        polygon_zone_service: PolygonZoneService,
        mock_session: AsyncMock,
        sample_zone_create: PolygonZoneCreate,
    ) -> None:
        """The polygon coordinate list must be stored verbatim; add/refresh get the zone."""
        result = await polygon_zone_service.create_zone("backyard", sample_zone_create)

        assert result.polygon == sample_zone_create.polygon
        assert result.polygon is not None
        assert mock_session.add.call_args.args[0] is result
        assert mock_session.refresh.call_args.args[0] is result
```

### T5 — TestUpdateZone::test_update_zone_preserves_unset_fields
Kills: C11 (update_zone_6). Target: TestUpdateZone.

```python
    @pytest.mark.asyncio
    async def test_update_zone_preserves_unset_fields(
        self,
        polygon_zone_service: PolygonZoneService,
        mock_session: AsyncMock,
        sample_zone: PolygonZone,
    ) -> None:
        """Partial update must not wipe fields absent from the update payload."""
        original_polygon = sample_zone.polygon
        original_type = sample_zone.zone_type
        original_count = sample_zone.current_count

        with patch.object(
            polygon_zone_service, "get_zone", return_value=sample_zone, autospec=True
        ):
            result = await polygon_zone_service.update_zone(1, PolygonZoneUpdate(name="Renamed"))

        assert result is not None
        assert result.name == "Renamed"
        assert result.polygon == original_polygon
        assert result.zone_type == original_type
        assert result.current_count == original_count
```

### T6 — TestSessionContract::test_lookups_and_session_calls_receive_expected_arguments
Kills: C9 (5), C8 (update_zone_35, set_active_5, delete_zone_7), C16 (2). New class.

```python
class TestSessionContract:
    """Session/lookup call-argument contracts (mutant cluster C8/C9/C16)."""

    @pytest.mark.asyncio
    async def test_lookup_and_session_calls_receive_expected_arguments(
        self,
        polygon_zone_service: PolygonZoneService,
        mock_session: AsyncMock,
        sample_zone: PolygonZone,
    ) -> None:
        """get_zone/delete/refresh must receive the right ids/entities; reset must include inactive."""
        with patch.object(
            polygon_zone_service, "get_zone", return_value=sample_zone, autospec=True
        ):
            await polygon_zone_service.update_zone(7, PolygonZoneUpdate(name="X"))
            assert polygon_zone_service.get_zone.call_args.args[0] == 7
            assert mock_session.refresh.call_args.args[0] is sample_zone

            assert await polygon_zone_service.delete_zone(7) is True
            assert polygon_zone_service.get_zone.call_args.args[0] == 7
            assert mock_session.delete.call_args.args[0] is sample_zone

            await polygon_zone_service.update_count(7, count=2)
            assert polygon_zone_service.get_zone.call_args.args[0] == 7

            await polygon_zone_service.set_active(7, is_active=False)
            assert polygon_zone_service.get_zone.call_args.args[0] == 7

        mock_session.reset_mock()
        with patch.object(
            polygon_zone_service, "get_zones_by_camera", return_value=[], autospec=True
        ) as mock_gzbc:
            await polygon_zone_service.reset_all_counts("cam1")
            mock_gzbc.assert_called_once_with("cam1", active_only=False)
```

## Coverage arithmetic of the six drafts (survivor keys)

| Draft | Clusters killed | Keys |
|-------|-----------------|------|
| T1 | C12∂, C15∂ | 1 + 4 = 5 |
| T2 | C13, C12∂, C14∂, C15∂ | 3 + 1 + 1 + 4 = 9 |
| T3 | C12∂, C14∂, C15∂ | 2 + 1 + 7 = 10 |
| T4 | C10, C8∂ | 2 + 2 = 4 |
| T5 | C11 | 1 |
| T6 | C9, C8∂, C16 | 5 + 3 + 2 = 10 |
| **Total killed if all green/red as designed** | | **39 of 40 TEST-GAP keys** |

(C15 member `get_zones_by_camera_2` `where(None)` survives only if SQLAlchemy silently
skips a None criterion; the `"polygon_zones.camera_id = 'cam1'"` assertion in T2 covers that
case too. The 1 unaddressed TEST-GAP key is any residual `where(None)` no-op; 61 keys are
EQUIVALENT/LOW-VALUE by design.)

## Verdict summary

- EQUIVALENT: 56 (log text/payload + StrEnum-dead defensive branches + falsy-None kwarg)
- LOW-VALUE: 5 (zone_type dict-key mangling, unobservable under StrEnum equality)
- TEST-GAP: 39 (session call-args, lookup args, polygon persistence, partial-update preservation, SQL statement contract, active_only contracts)
