# WP4.4 Triage Dossier — backend/services/zone_household_service.py

- **Survivors:** 122 (of 344 keys; 120 killed, 102 untested/null)
- **Covering test file (single):** `backend/tests/unit/services/test_zone_household_service.py`
  - `TestCheckSchedule` @ line 82, `TestMatchCronField` @ line 32, `TestZoneHouseholdServiceCRUD` @ line 376, `TestZoneHouseholdServiceZoneLookup` @ line 529
- **Method:** per-mutant bodies diffed against `__mutmut_orig` in `mutants/backend/services/zone_household_service.py` (manual region diff; `mutmut show` cross-checked on one key).

## Root-cause summary

Three failure shapes cover every TEST-GAP:

1. **Tests mock away the query.** CRUD/lookup tests mock `session.execute` and assert only the canned return (`test_get_config_returns_config_when_found` line 395) — never the compiled query passed to `execute`, so `query=None`, `select(None)`, `where(None)`, `==`→`!=` all pass.
2. **Tests never inspect constructor kwargs or result-dict payload.** `test_create_config` (line 430) patches the model class but never asserts `MockConfig.assert_called_once_with(...)`; zone-lookup tests assert only `zone_id` + `trust_level`, never `reason`.
3. **Boundary inputs absent.** No test uses a non-wildcard **day-of-month or month** cron field (so `current_day=None`/`current_month=None` survive — `*` masks them), no multi-config list (so `continue`→`break` is invisible with one config), no schedule dict missing `member_ids` (mutant default `None` raises `TypeError` — uncaught by `check_schedule`'s `except (ValueError, IndexError)`… actually raised from `get_zones_for_member`, which has no handler).

The 32 log-payload mutants and 20 unused-parameter mutants are noise, not gaps.

## Cluster table

| #   | Function              | Pattern                                                                                                                                              | Count | Class        | Example keys                                | Kill test                                                                 |
| --- | --------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- | ----- | ------------ | ------------------------------------------- | ------------------------------------------------------------------------- |
| 1   | check_schedule        | warning message/`extra` payload text (case, XX-wrap, key rename, `extra=None`, msg dropped)                                                          | 10    | EQUIVALENT   | …x_check_schedule\_\_mutmut_4, \_5, \_10    | none — log text nobody asserts                                            |
| 2   | check_schedule        | `min_val`/`max_val` args to `_match_cron_field` mutated (0→None, 0→1, 59→60, 23→24, 31→32, 12→13, 6→7)                                               | 20    | EQUIVALENT   | \_33, \_49, \_80                            | none — params are unused ("reserved for future validation" per docstring) |
| 3   | check_schedule        | day-of-month value → `None` at extraction (\_19) and at call site (\_52)                                                                             | 2     | **TEST-GAP** | \_19, \_52                                  | test A                                                                    |
| 4   | check_schedule        | month value → `None` at extraction (\_20) and at call site (\_62)                                                                                    | 2     | **TEST-GAP** | \_20, \_62                                  | test A                                                                    |
| 5   | create_config         | model constructor kwargs clobbered to `None` (zone_id, owner_id, all three lists)                                                                    | 5     | **TEST-GAP** | create_config\_\_mutmut_2, \_3, \_4         | test B1                                                                   |
| 6   | create_config         | model constructor kwargs removed entirely                                                                                                            | 5     | **TEST-GAP** | \_7, \_8, \_9                               | test B1                                                                   |
| 7   | create_config         | `X or []` → `X and []` default-coalescing flipped                                                                                                    | 3     | **TEST-GAP** | \_12, \_13, \_14                            | test B1 + B2                                                              |
| 8   | create_config         | info-log message/`extra` payload text                                                                                                                | 10    | EQUIVALENT   | \_17, \_21, \_24                            | none                                                                      |
| 9   | update_config         | skip-update guard `is not None` → `is None` for `allowed_vehicle_ids` (\_5) and `access_schedules` (\_6) — omitting the arg now **nulls the column** | 2     | **TEST-GAP** | update_config\_\_mutmut_5, \_6              | test C                                                                    |
| 10  | update_config         | info-log message/`extra` payload text                                                                                                                | 10    | EQUIVALENT   | \_8, \_12, \_15                             | none                                                                      |
| 11  | delete_config         | `zone_id`/`config_id` locals (log-only) → `None`                                                                                                     | 2     | EQUIVALENT   | delete_config\_\_mutmut_1, \_2              | none — locals feed only `logger.info`                                     |
| 12  | delete_config         | info-log message/`extra` payload text                                                                                                                | 10    | EQUIVALENT   | \_4, \_9, \_11                              | none                                                                      |
| 13  | get_config            | query construction: `query=None`, `where(None)`, `select(None)`, `==`→`!=`, `execute(None)`                                                          | 5     | **TEST-GAP** | get_config\_\_mutmut_1, \_4                 | test D                                                                    |
| 14  | get_zones_for_member  | query construction: `query=None`, `select(None)`, `execute(None)`                                                                                    | 3     | **TEST-GAP** | get_zones_for_member\_\_mutmut_1, \_3, \_6  | test E1                                                                   |
| 15  | get_zones_for_member  | result-dict `"reason"` key renamed / value cased (owner branch \_15–\_19, allowed branch \_27–\_31, schedule branch key \_54, \_55)                  | 12    | **TEST-GAP** | \_15, \_27, \_54                            | test E2                                                                   |
| 16  | get_zones_for_member  | owner-branch `continue`→`break` (\_20) and allowed-branch `continue`→`break` (\_32) — later configs dropped                                          | 2     | **TEST-GAP** | \_20, \_32                                  | test E3                                                                   |
| 17  | get_zones_for_member  | `schedule.get("member_ids", [])` default → `None`/missing (\_35, \_37) — `x in None` raises TypeError on schema-inconsistent schedule                | 2     | **TEST-GAP** | \_35, \_37                                  | test E3                                                                   |
| 18  | get_zones_for_member  | `description` extraction/default mutated: →`None`, key renamed, default→`None`/missing/`"XX…"`/`"SCHEDULED ACCESS"` (\_40–\_48)                      | 9     | **TEST-GAP** | \_40, \_42, \_47                            | test E2                                                                   |
| 19  | get_zones_for_vehicle | query construction (`query=None`, `select(None)`, `execute(None)`)                                                                                   | 3     | **TEST-GAP** | get_zones_for_vehicle\_\_mutmut_1, \_3, \_6 | test F                                                                    |
| 20  | get_zones_for_vehicle | result-dict `"reason"` key/value mutated (\_15–\_19)                                                                                                 | 5     | **TEST-GAP** | \_15, \_19                                  | test F                                                                    |

**Sum: 122 = survivors_total.** TEST-GAP total 70; EQUIVALENT 52; LOW-VALUE 0 (the log clusters could be read as LOW-VALUE but the mutation is text-only with no behavior change → EQUIVALENT per WP4.4 rubric; asserting log strings would be the wrong remedy anyway).

## Drafted tests (highest-value clusters)

All UNVERIFIED — not yet run red/green. Style follows the existing file (async fixtures on `AsyncMock` session). TDD procedure for each: apply the cluster's mutant diff → new assert **fails**; original source → **passes**.

```python
# UNVERIFIED - not yet run red/green
# Append to: backend/tests/unit/services/test_zone_household_service.py
# Kills clusters #3, #4 (day/month field values clobbered to None).
import re  # add to module imports


class TestCheckSchedule:  # ADD THESE METHODS TO THE EXISTING CLASS (line 82)
    def test_day_of_month_field(self) -> None:
        """Day-of-month field must be honoured (kills current_day=None mutants)."""
        # 00:00 on the 15th, any month/weekday
        cron = "0 0 15 * *"
        assert check_schedule(cron, datetime(2026, 1, 15, 0, 0, tzinfo=UTC)) is True
        assert check_schedule(cron, datetime(2026, 1, 16, 0, 0, tzinfo=UTC)) is False
        # Range form: on the None-clobber mutants `10 <= None` raises TypeError, which
        # check_schedule's except (ValueError, IndexError) does not catch -> test errors.
        # On the original this is True.
        assert check_schedule("0 0 10-20 * *", datetime(2026, 1, 15, 0, 0, tzinfo=UTC)) is True

    def test_month_field(self) -> None:
        """Month field must be honoured (kills current_month=None mutants)."""
        cron = "0 0 * 7 *"  # July only
        assert check_schedule(cron, datetime(2026, 7, 15, 0, 0, tzinfo=UTC)) is True
        assert check_schedule(cron, datetime(2026, 8, 15, 0, 0, tzinfo=UTC)) is False
```

```python
# UNVERIFIED - not yet run red/green
# Kills clusters #5, #6, #7 (constructor kwargs clobbered/removed, `or []` -> `and []`).
class TestZoneHouseholdServiceCRUD:  # ADD TO EXISTING CLASS (line 376)
    @pytest.mark.asyncio
    async def test_create_config_passes_all_fields_to_model(
        self,
        service: ZoneHouseholdService,
        mock_session: AsyncMock,
    ) -> None:
        """Every constructor kwarg must reach ZoneHouseholdConfig verbatim."""
        with patch(
            "backend.models.zone_household_config.ZoneHouseholdConfig", autospec=True
        ) as MockConfig:
            mock_config = MagicMock()
            mock_config.id = 1
            mock_config.zone_id = "zone-1"
            MockConfig.return_value = mock_config

            await service.create_config(
                zone_id="zone-1",
                owner_id=1,
                allowed_member_ids=[2, 3],
                allowed_vehicle_ids=[10],
                access_schedules=[{"member_ids": [4], "cron_expression": "* * * * *"}],
            )

            MockConfig.assert_called_once_with(
                zone_id="zone-1",
                owner_id=1,
                allowed_member_ids=[2, 3],
                allowed_vehicle_ids=[10],
                access_schedules=[{"member_ids": [4], "cron_expression": "* * * * *"}],
            )

    @pytest.mark.asyncio
    async def test_create_config_coerces_none_lists_to_empty_lists(
        self,
        service: ZoneHouseholdService,
        mock_session: AsyncMock,
    ) -> None:
        """Omitted lists must persist as [] (not None) — kills `or []` -> `and []`."""
        with patch(
            "backend.models.zone_household_config.ZoneHouseholdConfig", autospec=True
        ) as MockConfig:
            MockConfig.return_value = MagicMock(id=1, zone_id="zone-x")

            await service.create_config(zone_id="zone-x")

            MockConfig.assert_called_once_with(
                zone_id="zone-x",
                owner_id=None,
                allowed_member_ids=[],
                allowed_vehicle_ids=[],
                access_schedules=[],
            )
```

```python
# UNVERIFIED - not yet run red/green
# Kills cluster #9 (update_config guard `is not None` -> `is None` for vehicles/schedules).
class TestZoneHouseholdServiceCRUD:  # ADD TO EXISTING CLASS (line 376)
    @pytest.mark.asyncio
    async def test_update_config_unset_list_fields_are_preserved(
        self,
        service: ZoneHouseholdService,
        mock_session: AsyncMock,
    ) -> None:
        """Omitting allowed_vehicle_ids/access_schedules must NOT null them."""
        mock_config = MagicMock()
        mock_config.owner_id = 7
        mock_config.allowed_member_ids = [1]
        mock_config.allowed_vehicle_ids = [10]
        mock_config.access_schedules = [{"member_ids": [4]}]

        await service.update_config(mock_config, allowed_member_ids=[2])

        assert mock_config.allowed_member_ids == [2]        # provided -> updated
        assert mock_config.allowed_vehicle_ids == [10]      # omitted -> preserved
        assert mock_config.access_schedules == [{"member_ids": [4]}]  # omitted -> preserved
        assert mock_config.owner_id == 7                    # sentinel -> preserved

    @pytest.mark.asyncio
    async def test_update_config_provided_list_fields_are_written(
        self,
        service: ZoneHouseholdService,
        mock_session: AsyncMock,
    ) -> None:
        """Provided list fields must reach the config (kills guard in both directions)."""
        mock_config = MagicMock()
        mock_config.allowed_member_ids = [1]
        mock_config.allowed_vehicle_ids = [10]
        mock_config.access_schedules = []

        await service.update_config(
            mock_config, allowed_vehicle_ids=[20], access_schedules=[{"member_ids": [9]}]
        )

        assert mock_config.allowed_vehicle_ids == [20]
        assert mock_config.access_schedules == [{"member_ids": [9]}]
```

```python
# UNVERIFIED - not yet run red/green
# Kills cluster #13 (get_config query construction) and #14/#19 (query construction in
# get_zones_for_member / get_zones_for_vehicle is covered by tests E1/F; the execute-arg
# assertion here pins the same habit for get_config).
class TestZoneHouseholdServiceCRUD:  # ADD TO EXISTING CLASS (line 376)
    @pytest.mark.asyncio
    async def test_get_config_builds_zone_id_equality_query(
        self,
        service: ZoneHouseholdService,
        mock_session: AsyncMock,
    ) -> None:
        """The query sent to execute() must select configs WHERE zone_id == requested."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        await service.get_config("zone-42")

        query = mock_session.execute.call_args[0][0]
        sql = str(query.compile(compile_kwargs={"literal_binds": True}))
        assert "FROM zone_household_configs" in sql          # kills query=None / select(None) / execute(None)
        assert re.search(r"zone_household_configs\.zone_id = 'zone-42'", sql)  # kills where(None) and !=
```

```python
# UNVERIFIED - not yet run red/green
# Kills clusters #15 + #18 (reason key/value + description default handling).
class TestZoneHouseholdServiceZoneLookup:  # ADD TO EXISTING CLASS (line 529)
    @pytest.mark.asyncio
    async def test_get_zones_for_member_reason_strings_are_exact(
        self,
        service: ZoneHouseholdService,
        mock_session: AsyncMock,
    ) -> None:
        """Each trust branch must emit its exact reason payload."""
        owner = MagicMock(zone_id="z-own", owner_id=1, allowed_member_ids=[], access_schedules=[])
        allowed = MagicMock(zone_id="z-allow", owner_id=99, allowed_member_ids=[1], access_schedules=[])
        scheduled = MagicMock(
            zone_id="z-sched",
            owner_id=None,
            allowed_member_ids=[],
            access_schedules=[{"member_ids": [1], "description": "daily access"}],
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [owner, allowed, scheduled]
        mock_session.execute.return_value = mock_result

        zones = await service.get_zones_for_member(1)

        assert [z["reason"] for z in zones] == [
            "Zone owner",
            "In allowed members list",
            "Has daily access",
        ]

    @pytest.mark.asyncio
    async def test_get_zones_for_member_schedule_default_description(
        self,
        service: ZoneHouseholdService,
        mock_session: AsyncMock,
    ) -> None:
        """Schedule without description must fall back to exactly 'scheduled access'."""
        mock_config = MagicMock(
            zone_id="z-def",
            owner_id=None,
            allowed_member_ids=[],
            access_schedules=[{"member_ids": [3]}],
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_config]
        mock_session.execute.return_value = mock_result

        zones = await service.get_zones_for_member(3)

        assert zones == [{"zone_id": "z-def", "trust_level": "monitor", "reason": "Has scheduled access"}]
```

```python
# UNVERIFIED - not yet run red/green
# Kills clusters #14 + #16 + #17 (query construction, continue->break, member_ids default).
class TestZoneHouseholdServiceZoneLookup:  # ADD TO EXISTING CLASS (line 529)
    @pytest.mark.asyncio
    async def test_get_zones_for_member_query_selects_all_configs_with_zone(
        self,
        service: ZoneHouseholdService,
        mock_session: AsyncMock,
    ) -> None:
        """Full-scan query must hit zone_household_configs with the zone eager-loaded."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        await service.get_zones_for_member(1)

        query = mock_session.execute.call_args[0][0]
        sql = str(query.compile())
        assert "FROM zone_household_configs" in sql
        assert "camera_zones" in sql  # selectinload(zone) LEFT OUTER JOIN

    @pytest.mark.asyncio
    async def test_get_zones_for_member_scans_all_configs_and_tolerates_missing_keys(
        self,
        service: ZoneHouseholdService,
        mock_session: AsyncMock,
    ) -> None:
        """continue-vs-break + member_ids default: member matches in EVERY config, and a
        schedule dict missing member_ids must not raise (default []) nor skip silently."""
        first = MagicMock(zone_id="z-1", owner_id=1, allowed_member_ids=[], access_schedules=[])
        second = MagicMock(zone_id="z-2", owner_id=1, allowed_member_ids=[], access_schedules=[])
        broken_sched = MagicMock(
            zone_id="z-3",
            owner_id=99,
            allowed_member_ids=[],
            access_schedules=[{"cron_expression": "* * * * *"}],  # no member_ids key
        )
        allowed_a = MagicMock(zone_id="z-4", owner_id=99, allowed_member_ids=[1], access_schedules=[])
        allowed_b = MagicMock(zone_id="z-5", owner_id=99, allowed_member_ids=[1], access_schedules=[])
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [
            first, second, broken_sched, allowed_a, allowed_b,
        ]
        mock_session.execute.return_value = mock_result

        zones = await service.get_zones_for_member(1)

        # Owner matches in z-1 AND z-2 (kills _20: continue->break stops at z-1);
        # broken schedule skipped via default [] (kills _35/_37: `x in None` TypeError);
        # allowed matches in z-4 AND z-5 (kills _32: continue->break stops at z-4).
        assert [z["zone_id"] for z in zones] == ["z-1", "z-2", "z-4", "z-5"]
```

```python
# UNVERIFIED - not yet run red/green
# Kills clusters #19 + #20 (vehicle query construction + reason payload).
class TestZoneHouseholdServiceZoneLookup:  # ADD TO EXISTING CLASS (line 529)
    @pytest.mark.asyncio
    async def test_get_zones_for_vehicle_reason_and_query(
        self,
        service: ZoneHouseholdService,
        mock_session: AsyncMock,
    ) -> None:
        """Vehicle lookup: query must scan configs; entry payload must be exact."""
        mock_config = MagicMock(zone_id="zone-v", allowed_vehicle_ids=[10, 20])
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_config]
        mock_session.execute.return_value = mock_result

        zones = await service.get_zones_for_vehicle(10)

        query = mock_session.execute.call_args[0][0]
        sql = str(query.compile())
        assert "FROM zone_household_configs" in sql          # kills query=None / select(None)
        assert "camera_zones" in sql                          # kills dropped selectinload
        assert zones == [
            {
                "zone_id": "zone-v",
                "trust_level": "partial",
                "reason": "In allowed vehicles list",
            }
        ]  # kills reason key/value mutants (exact dict equality)
```

## Notes for WP4.4

- **Verified substrate:** `str(select(ZoneHouseholdConfig).where(zone_id == 'z').compile(compile_kwargs={'literal_binds': True}))` does emit `WHERE zone_household_configs.zone_id = 'z'`, and `select(None)`/`where(None)` build without raising — so the SQL-inspection asserts are the only reliable kill vector for cluster #13/#14/#19 (a mock `execute` swallows them silently today).
- Cluster #17 mutants (`member_ids` default → None) _raise_ `TypeError` on real DB rows lacking the key; current tests never feed a key-less schedule dict. One multi-config test kills #14, #16, #17 together.
- `update_config` guards for `owner_id` (sentinel `...`) and `allowed_member_ids` were killed by `test_update_config_skips_unset_fields` (line 485); only vehicles/schedules guards are unguarded — the drafted pair is symmetric so both branches get pinned.
- Do NOT write log-payload assertions for the 52 EQUIVALENT mutants; if mutmut keeps counting them, they are baseline candidates (or consider `mutmut` skip-regex on `logger.` statements at WP4.5 scoring time).
