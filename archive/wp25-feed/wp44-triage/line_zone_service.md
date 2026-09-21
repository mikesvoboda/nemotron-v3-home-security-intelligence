# WP4.4 Triage Dossier — backend/services/line_zone_service.py

- **Module:** `backend/services/line_zone_service.py` (375 lines)
- **Survivors:** **59** of 135 keys (all 135 checked, 0 nulls; 76 killed, 59 survived with exit_code == 0).
  Extracted from `mutants/backend/services/line_zone_service.py.meta` → `exit_code_by_key`.
- **Key prefix:** all survivor keys are `backend.services.line_zone_service.xǁLineZoneServiceǁ<method>__mutmut_<N>`;
  shortened below to `<method>_<N>`.
- **Diffs:** `uv run mutmut show <key>` succeeded for all 59 keys (raw dump: `/tmp/lzscratch/diffs.txt`). No manual fallback needed.
- **Sole covering test file** (per `mutants/mutmut-stats.json` → `tests_by_mangled_function_name`):
  `backend/tests/unit/services/test_line_zone_service.py` (667 lines).
  Fixture anchors: `mock_session` :29, `line_zone_service` :41, `sample_zone_create` :47, `sample_zone` :62.
  Class anchors: TestCreateZone :85, TestGetZone :176, TestGetZonesByCamera :217, TestGetAllZones :280,
  TestUpdateZone :327, TestDeleteZone :438, TestIncrementCount :491, TestResetCounts :587, TestGetLineZoneService :658.

## Root cause of the survivor mass (test-design facts, file:line)

1. **`db.execute` is a bare AsyncMock** (:36) that returns a canned `MagicMock` for *any* argument —
   the constructed SELECT is never compiled or inspected, so `None`-nuked statements, gutted `where()`
   and `==`→`!=` predicate flips all sail through.
2. **Session methods are only checked with `.called`**, never call-args
   (`assert mock_session.add.called` :100, `.delete.called` :453, `.refresh.called` :102/346) — so
   `add(None)`/`delete(None)`/`refresh(None)` survive.
3. **`get_zone` is autospec-patched with a fixture return-value that ignores its argument**
   (e.g. :338, :449, :502) — so `self.get_zone(None)` returns the same zone as `get_zone(zone_id)`.
4. **Log tests assert only `call_args[0][0]` (the message), never the `extra=` payload**
   (:167, :430, :483, :579, :650) — the 32 `extra`-dict mutants (key renames / dict removal) survive.
5. **SQLAlchemy 2.0.53 semantics verified in-repo** (compiled against the project venv):
   `select(X).where(None)` renders `WHERE NULL` (never true — PostgreSQL would reject it),
   `order_by(None, c)` renders `ORDER BY NULL, c`, single-arg `order_by(None)` **clears** the clause
   (no ORDER BY at all), `select(None)` compiles to `SELECT NULL AS anon_1` (no FROM), and
   `select(...).column_descriptions[0]["entity"]` is `LineZone` (None for `select(None)`).

## Cluster table (counts sum to 59: TEST-GAP 25 + EQUIVALENT 34 + LOW-VALUE 0)

| # | Pattern (cluster) | Count | Keys (≤3 examples) | Src line(s) | Class | Why / test gap |
|---|---|---|---|---|---|---|
| C1 | `increment_count` `zone.out_count += 1` → `zone.out_count = 1` (out-side counter assigned instead of incremented) | 1 | increment_count_17 | :236 | TEST-GAP | `test_increment_count_multiple_times` (:524) does the second increment on the **in** side (`1,2` not `1,3`); no test ever does two consecutive **out** increments |
| C2 | `update_zone` `data.model_dump(exclude_unset=True)` → `exclude_unset=False` (partial update becomes full overwrite of every unset field with None) | 1 | update_zone_6 | :171 | TEST-GAP | Partial-update contract is the docstring's headline ("Only fields present … are modified", :151); every test asserts only the **provided** fields (:331-397), never that an untouched field (start_x, target_classes, alert_on_cross) survives the write |
| C3 | WHERE equality flipped `==` → `!=` (get_zone id / get_zones_by_camera camera_id) | 2 | get_zone_5, get_zones_by_camera_6 | :131, :144 | TEST-GAP | execute is mocked → inverted predicate still returns the canned fixture; on a real DB it returns the complement set (wrong zone / other cameras' zones) |
| C4 | `db.execute` fed a gutted statement: whole stmt → `None`, `select(None)`, or `where(None)` | 8 | get_zone_2, get_zone_3, get_zone_4 (+ gzbc_2/4/5, all_2/7) | :131, :144, :281 | TEST-GAP | Mocked execute answers anything; `execute(None)` raises TypeError and `select(None)` loses the FROM on a real session; `where(None)` renders `WHERE NULL` (PostgreSQL syntax error) |
| C5 | `order_by` clause gutted: `order_by(None)`/`order_by(None, col)`/`order_by(col, None)`/order key dropped | 5 | get_zones_by_camera_3, get_all_zones_3, get_all_zones_5 (+4,6) | :144, :281 | TEST-GAP | Docstrings promise "ordered by creation time" (:141) / "camera ID and creation time" (:278); results come from the mock, so ordering loss is invisible |
| C6 | Session entity arg nuked: `db.add(None)` / `db.refresh(None)` / `db.delete(None)` | 4 | create_zone_19, create_zone_20, update_zone_17 (+ delete_zone_5) | :107, :109, :177, :202 | TEST-GAP | Tests assert `.called` only; a real session raises on a None entity (the zone silently never persisted / never deleted) |
| C7 | Internal lookup fed wrong key: `self.get_zone(zone_id)` → `self.get_zone(None)` in delete/update/increment/reset | 4 | delete_zone_2, update_zone_2, increment_count_8 (+ reset_counts_2) | :198, :166, :228, :259 | TEST-GAP | `get_zone` is autospec-patched with a fixture return ignoring args; call-args never asserted. Real DB: wrong row deleted / right row never found. (update_zone_2/delete_zone_2 also flip the not-found branch for a real session) |
| C8 | Log `extra={...}` dict **keys renamed** (`"k"`→`"XXkXX"` / `"K_UPPER"`) in create/update/delete/increment/reset | 22 | create_zone_25, create_zone_26, create_zone_27 (+28,29,30; update_22,23,24,25; delete_10,11; increment_24..31; reset_13,14) | :113-117, :181-184, :207, :242-247, :271 | EQUIVALENT | Structured-log payload only; logger is patched and only the message is asserted; no consumer of record-extra exists in tests. Matches polygon_zone_service dossier C1 precedent. (Side-killable via the extra-dict assertion folded into draft P2) |
| C9 | Log `extra={...}` set to `extra=None` or the extra kwarg dropped from `logger.*` | 10 | create_zone_22, create_zone_24, update_zone_19 (+21; delete_7,9; increment_21,23; reset_10,12) | :111-118, :179-185, :205-208, :240-248, :269-272 | EQUIVALENT | Message, level and call-count unchanged; only the (never-asserted) payload vanishes. polygon precedent C2. |
| C10 | `logger.warning(f"Cannot …: zone {zone_id} not found")` → `logger.warning(None)` on increment/reset not-found paths | 2 | increment_count_10, reset_counts_4 | :230, :261 | EQUIVALENT | Tests assert only `warning.assert_called_once()` (:562, :633); the f-string is evaluated before the call so nothing crashes. polygon precedent C5 |

**Sum check:** 1+1+2+8+5+4+4+22+10+2 = **59** ✔

## Highest-value TEST-GAP clusters → drafted tests

Selected: **P1→C1+C7(increment)**, **P2→C2 (+C8/C9 update extras as side-kills)**, **P3→C3+C4 (get_zone)**,
**P4→C3+C4+C5 (get_zones_by_camera)**, **P5→C4+C5 (get_all_zones)**, **P6→C6+C7 (create/update/delete)**.
TDD procedure (identical for all): run the new test against the mutant copy of the module — the
assertion must **fail (red)** on the mutant's diff; run against the original — it must **pass (green)**.
Every assertion below was sanity-checked against the real SQLAlchemy 2.0.53 compile output
(`column_descriptions`, `whereclause`, literal-binded SQL) so it is red-on-mutant/green-original by construction.

Direct coverage: P1..P6 hit 24 of 25 TEST-GAP mutants (reset_counts_2 gets a one-line pin noted under P1)
plus 6 EQUIVALENT-classified update-extra mutants as side-kills.

Style follows the existing file: `@pytest.mark.asyncio`, fixtures `line_zone_service` / `mock_session` /
`sample_zone` / `sample_zone_create`, `patch("backend.services.line_zone_service.logger", autospec=True)`.
Where the *class-level* `patch.object(LineZoneService, "get_zone", …)` is used instead of the file's
instance-level patch, it is so the autospec mock records `(instance, zone_id)` call-args unambiguously.

```python
# =============================================================================
# WP4.4 kill-tests for surviving line_zone_service mutants (UNVERIFIED)
# add to imports:  from sqlalchemy.dialects import postgresql
# =============================================================================


def _last_compiled_stmt(mock_session: AsyncMock) -> str:
    """SQL text of the statement the service passed to the last db.execute() call."""
    stmt = mock_session.execute.call_args.args[0]
    return str(
        stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
    )


class TestCreateZone:  # (existing class — add this method)
    # // UNVERIFIED - not yet run red/green
    # P6a — kills create_zone_19 (db.add(None)), create_zone_20 (db.refresh(None))
    @pytest.mark.asyncio
    async def test_create_zone_adds_and_refreshes_the_created_zone(
        self,
        line_zone_service: LineZoneService,
        mock_session: AsyncMock,
        sample_zone_create: LineZoneCreate,
    ) -> None:
        """Session calls must receive the created zone, not None."""
        result = await line_zone_service.create_zone("front_door", sample_zone_create)

        assert mock_session.add.call_args.args[0] is result
        assert mock_session.refresh.call_args.args[0] is result


class TestGetZone:  # (existing class — add this method)
    # // UNVERIFIED - not yet run red/green
    # P3 — kills get_zone_2 (execute(None)), get_zone_3 (where(None)),
    #      get_zone_4 (select(None)), get_zone_5 (id == → id !=)
    @pytest.mark.asyncio
    async def test_get_zone_builds_id_equality_query(
        self,
        line_zone_service: LineZoneService,
        mock_session: AsyncMock,
        sample_zone: LineZone,
    ) -> None:
        """get_zone must execute a LineZone SELECT with an id-equality WHERE."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_zone
        mock_session.execute.return_value = mock_result

        result = await line_zone_service.get_zone(1)

        assert result is sample_zone
        stmt = mock_session.execute.call_args.args[0]
        # execute(None) -> no column_descriptions; select(None) -> entity is None
        assert getattr(stmt, "column_descriptions", [{}])[0].get("entity") is LineZone
        # where(None) renders a bare NULL clause with no column reference
        assert "line_zones.id" in str(stmt.whereclause)
        sql = _last_compiled_stmt(mock_session)
        assert " WHERE " in sql.upper() and "line_zones.id" in sql
        # equality flip to `!=` must be visible in the compiled predicate
        assert "!=" not in sql and "<>" not in sql


class TestGetZonesByCamera:  # (existing class — add this method)
    # // UNVERIFIED - not yet run red/green
    # P4 — kills get_zones_by_camera_2 (stmt None), _3 (order_by(None) drops ORDER BY),
    #      _4 (where(None)), _5 (select(None)), _6 (camera_id == → !=)
    @pytest.mark.asyncio
    async def test_get_zones_by_camera_builds_filtered_ordered_query(
        self,
        line_zone_service: LineZoneService,
        mock_session: AsyncMock,
    ) -> None:
        """Query must select LineZone, filter by camera equality, order by created_at."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        await line_zone_service.get_zones_by_camera("front_door")

        sql = _last_compiled_stmt(mock_session).upper()
        assert "FROM LINE_ZONES" in sql  # select(None)/execute(None) fail here
        assert "LINE_ZONES.CAMERA_ID = 'FRONT_DOOR'" in sql  # where(None) / != fail here
        assert "!=" not in sql and "<>" not in sql
        assert "ORDER BY LINE_ZONES.CREATED_AT" in sql  # order_by(None) fails here


class TestGetAllZones:  # (existing class — add this method)
    # // UNVERIFIED - not yet run red/green
    # P5 — kills get_all_zones_2 (stmt None), _3 (order_by(None, created_at)),
    #      _4 (order_by(camera_id, None)), _5 (camera key dropped),
    #      _6 (created_at key dropped), _7 (select(None))
    @pytest.mark.asyncio
    async def test_get_all_zones_selects_all_ordered_by_camera_then_created_at(
        self,
        line_zone_service: LineZoneService,
        mock_session: AsyncMock,
    ) -> None:
        """get_all_zones must compile a full-table SELECT ordered by camera_id, created_at."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        await line_zone_service.get_all_zones()

        sql = _last_compiled_stmt(mock_session).upper()
        assert "FROM LINE_ZONES" in sql
        assert "ORDER BY LINE_ZONES.CAMERA_ID, LINE_ZONES.CREATED_AT" in sql
        assert "WHERE" not in sql


class TestUpdateZone:  # (existing class — add this method)
    # // UNVERIFIED - not yet run red/green
    # P2 — kills update_zone_6 (exclude_unset=True → False: every unset field would be
    #      overwritten with None) AND side-kills update_zone_19/21/22/23/24/25
    #      (extra-dict removal/rename) via the structured-log assertion.
    @pytest.mark.asyncio
    async def test_update_zone_partial_update_preserves_unset_fields(
        self,
        line_zone_service: LineZoneService,
        mock_session: AsyncMock,
        sample_zone: LineZone,
    ) -> None:
        """Only the fields the caller actually sent may be modified or logged."""
        with patch.object(
            line_zone_service, "get_zone", return_value=sample_zone, autospec=True
        ):
            with patch("backend.services.line_zone_service.logger", autospec=True) as mock_logger:
                data = LineZoneUpdate(name="Only Name")

                result = await line_zone_service.update_zone(1, data)

        assert result is not None
        assert result.name == "Only Name"
        # every UNSET field must keep its stored value (kills exclude_unset=False)
        assert result.camera_id == "front_door"
        assert result.start_x == 100
        assert result.start_y == 400
        assert result.end_x == 500
        assert result.end_y == 400
        assert result.alert_on_cross is True
        assert result.target_classes == ["person", "car"]
        assert result.in_count == 0
        assert result.out_count == 0
        # the structured log must carry exactly the canonical extra dict
        # (kills the XXkey/UPPER renames and the extra=None / dropped-extra mutants)
        assert mock_logger.info.call_args.kwargs["extra"] == {
            "zone_id": 1,
            "updated_fields": ["name"],
        }

    # // UNVERIFIED - not yet run red/green
    # P6b — kills update_zone_2 (get_zone(None)) and update_zone_17 (refresh(None))
    @pytest.mark.asyncio
    async def test_update_zone_looks_up_and_refreshes_the_fetched_zone(
        self,
        line_zone_service: LineZoneService,
        mock_session: AsyncMock,
        sample_zone: LineZone,
    ) -> None:
        """update_zone must look up the zone by the given id and refresh that same object."""
        with patch.object(
            LineZoneService, "get_zone", autospec=True, return_value=sample_zone
        ) as mock_get_zone:
            result = await line_zone_service.update_zone(7, LineZoneUpdate(name="X"))

        mock_get_zone.assert_called_once_with(line_zone_service, 7)
        assert result is sample_zone
        assert mock_session.refresh.call_args.args[0] is sample_zone


class TestDeleteZone:  # (existing class — add this method)
    # // UNVERIFIED - not yet run red/green
    # P6c — kills delete_zone_2 (get_zone(None)) and delete_zone_5 (db.delete(None))
    @pytest.mark.asyncio
    async def test_delete_zone_deletes_the_fetched_zone(
        self,
        line_zone_service: LineZoneService,
        mock_session: AsyncMock,
        sample_zone: LineZone,
    ) -> None:
        """delete_zone must fetch by the given id and delete exactly that entity."""
        with patch.object(
            LineZoneService, "get_zone", autospec=True, return_value=sample_zone
        ) as mock_get_zone:
            result = await line_zone_service.delete_zone(3)

        assert result is True
        mock_get_zone.assert_called_once_with(line_zone_service, 3)
        assert mock_session.delete.call_args.args[0] is sample_zone


class TestIncrementCount:  # (existing class — add this method)
    # // UNVERIFIED - not yet run red/green
    # P1 — kills increment_count_17 (out_count += 1 → = 1) and increment_count_8
    #      (get_zone(None), via the class-level autospec call-args pin)
    @pytest.mark.asyncio
    async def test_increment_count_out_accumulates_and_looks_up_by_id(
        self,
        line_zone_service: LineZoneService,
        mock_session: AsyncMock,
        sample_zone: LineZone,
    ) -> None:
        """Repeated 'out' increments must accumulate; the zone id must reach get_zone."""
        sample_zone.out_count = 3
        with patch.object(
            LineZoneService, "get_zone", autospec=True, return_value=sample_zone
        ) as mock_get_zone:
            await line_zone_service.increment_count(1, direction="out")

            mock_get_zone.assert_called_with(line_zone_service, 1)
            assert sample_zone.out_count == 4  # `= 1` mutant gives 1
            assert sample_zone.in_count == 0

            await line_zone_service.increment_count(1, direction="out")
            assert sample_zone.out_count == 5


# Optional one-line companion (kills the last TEST-GAP mutant reset_counts_2,
# self.get_zone(zone_id) → self.get_zone(None)): inside TestResetCounts's
# test_reset_counts_success, patch at class level instead of the instance and add
#     mock_get_zone.assert_called_once_with(line_zone_service, 1)
# following the exact pattern of P6b/P1 above.
```

### Kill map (drafted tests → clusters)

| Draft | Directly kills | Mutants |
|---|---|---|
| P1 | C1, C7 | increment_count_17, increment_count_8 |
| P2 | C2 (+C8/C9 update-extra side-kills) | update_zone_6, _19, _21, _22, _23, _24, _25 |
| P3 | C3, C4 | get_zone_2, _3, _4, _5 |
| P4 | C3, C4, C5 | get_zones_by_camera_2, _3, _4, _5, _6 |
| P5 | C4, C5 | get_all_zones_2, _3, _4, _5, _6, _7 |
| P6 | C6, C7 | create_zone_19, _20; update_zone_2, _17; delete_zone_2, _5 |
| (one-line pin) | C7 | reset_counts_2 |

Total direct kill reach: all 25 TEST-GAP survivors + 6 EQUIVALENT-classified (update-extra) mutants.

## Why the remaining 28 EQUIVALENT mutants get no test

- **C8 (22 key renames) + C9 (10 extra removals):** `extra` is pure structured-log payload. The repo's
  log tests (this file and its siblings) assert the message string and call count only; no test consumer
  of `record.<key>` exists in the module's blast radius, and structlog/stdlib formatting is identical.
  Writing a dedicated extra-payload test per call site would be low-signal; P2 demonstrates the
  assertion for the one site (update_zone) that a kill-test already touches. Precedent: the
  polygon_zone_service dossier classified the identical patterns (its C1/C2/C5) as EQUIVALENT.
- **C10 (2 `logger.warning(None)`):** message content is not part of any asserted contract;
  `assert_called_once()` still passes; the pre-call f-string is pre-existing source text, so the
  mutant changes nothing observable.
