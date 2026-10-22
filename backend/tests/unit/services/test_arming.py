"""Unit tests for backend.services.arming (B4.7 / docs/uplevel/4n-arming.md)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR, UUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker

from backend.models.alert import AlertRule, AlertSeverityEnum
from backend.models.arming import (
    EXTERNAL_ALERTS_RULE_ID,
    EXTERNAL_ALERTS_RULE_NAME,
    ArmingChange,
    ArmingModeExclusion,
    ArmingScheduleEntry,
    ArmingState,
)
from backend.models.camera import Camera
from backend.models.household_org import Household
from backend.models.property import Property
from backend.services.arming import (
    ArmingScheduler,
    _ensure_utc,
    _parse_hhmm,
    _resolve_household_tz,
    apply_schedule,
    ensure_external_alerts_rule,
    get_arming_status,
    get_mode_exclusions,
    is_armed,
    key_fingerprint,
    list_changes,
    mode_at,
    next_scheduled,
    resolve_arming_at,
    set_mode,
    set_mode_exclusions,
    set_schedule,
)

pytestmark = pytest.mark.unit


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(_type: Any, _compiler: Any, **_kw: Any) -> str:
    return "JSON"


@compiles(UUID, "sqlite")
def _compile_uuid_sqlite(_type: Any, _compiler: Any, **_kw: Any) -> str:
    return "VARCHAR(36)"


@compiles(TSVECTOR, "sqlite")
def _compile_tsvector_sqlite(_type: Any, _compiler: Any, **_kw: Any) -> str:
    return "TEXT"


@compiles(ARRAY, "sqlite")
def _compile_array_sqlite(_type: Any, _compiler: Any, **_kw: Any) -> str:
    return "JSON"


class _AsyncSQLiteSession:
    def __init__(self, sync_session: Session) -> None:
        self._s = sync_session

    def add(self, instance: Any) -> None:
        self._s.add(instance)

    def add_all(self, instances: Any) -> None:
        self._s.add_all(instances)

    def get_bind(self) -> Any:
        return self._s.get_bind()

    async def execute(self, statement: Any, params: Any = None, **kwargs: Any) -> Any:
        return self._s.execute(statement, params=params, **kwargs)

    async def scalars(self, statement: Any, params: Any = None, **kwargs: Any) -> Any:
        return self._s.scalars(statement, params=params, **kwargs)

    async def get(self, entity: Any, ident: Any, **kwargs: Any) -> Any:
        return self._s.get(entity, ident, **kwargs)

    async def flush(self) -> None:
        self._s.flush()

    async def commit(self) -> None:
        self._s.commit()

    async def refresh(self, instance: Any) -> None:
        self._s.refresh(instance)


@pytest.fixture
def db_session(tmp_path: Path):
    db_file = tmp_path / "arming_unit.db"
    engine = create_engine(f"sqlite:///{db_file}", future=True)

    @event.listens_for(engine, "connect")
    def _enable_fk(dbapi_conn, _conn_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    for tbl in (
        Household.__table__,
        Property.__table__,
        Camera.__table__,
        AlertRule.__table__,
        ArmingState.__table__,
        ArmingModeExclusion.__table__,
        ArmingScheduleEntry.__table__,
        ArmingChange.__table__,
    ):
        with engine.begin() as conn:
            tbl.create(conn, checkfirst=True)

    factory = sessionmaker(engine, expire_on_commit=False)
    with factory() as sync_sess:
        sync_sess.add_all(
            [
                Camera(
                    id="front_door",
                    name="Front Door",
                    folder_path="/export/foscam/front_door",
                    status="online",
                ),
                Camera(
                    id="living_room",
                    name="Living room",
                    folder_path="/export/foscam/living_room",
                    status="online",
                ),
            ]
        )
        sync_sess.commit()
        yield _AsyncSQLiteSession(sync_sess)

    engine.dispose()


class TestArmingModesAndExclusions:
    """Tests for mode_at, is_armed, set_mode, set_mode_exclusions, and change history (A2)."""

    @pytest.mark.asyncio
    async def test_default_armed_and_disarmed_arms_none_and_change_log_time_travel(
        self, db_session: _AsyncSQLiteSession
    ) -> None:
        t0 = datetime(2026, 10, 22, 10, 0, tzinfo=UTC)
        # Default install: Home with every camera armed (including any newly added camera)
        assert await mode_at(db_session, t0) == "home"  # type: ignore[arg-type]
        assert await is_armed(db_session, "front_door", at=t0) is True  # type: ignore[arg-type]
        assert await is_armed(db_session, "living_room", at=t0) is True  # type: ignore[arg-type]
        assert await is_armed(db_session, "brand_new_cam", at=t0) is True  # type: ignore[arg-type]

        # Switch to Away at t1
        t1 = t0 + timedelta(minutes=5)
        await set_mode(
            db_session,  # type: ignore[arg-type]
            "away",
            source_kind="user",
            source_name="alice",
            now=t1,
        )
        await db_session.commit()

        # Event 1 starts at t_event1 (while living_room is still armed in Away)
        t_event1 = t1 + timedelta(minutes=2)

        # At t2 > t_event1, living_room is left out of Away
        t2 = t1 + timedelta(minutes=5)
        await set_mode_exclusions(
            db_session,  # type: ignore[arg-type]
            "away",
            ["living_room"],
            source_kind="user",
            source_name="alice",
            now=t2,
        )
        await db_session.commit()

        # Event 2 starts at t_event2 > t2
        t_event2 = t2 + timedelta(minutes=2)

        # Time-travel check (A2): at t_event1 living_room WAS armed; at t_event2 it is NOT armed
        assert await mode_at(db_session, t_event1) == "away"  # type: ignore[arg-type]
        assert await is_armed(db_session, "living_room", at=t_event1) is True  # type: ignore[arg-type]
        assert await is_armed(db_session, "living_room", at=t_event2) is False  # type: ignore[arg-type]
        assert await is_armed(db_session, "front_door", at=t_event2) is True  # type: ignore[arg-type]

        # Switch to Disarmed at t3 -> Disarmed arms NO camera
        t3 = t2 + timedelta(minutes=5)
        await set_mode(
            db_session,  # type: ignore[arg-type]
            "disarmed",
            source_kind="webhook",
            source_name="keyfp123",
            now=t3,
        )
        await db_session.commit()
        assert await mode_at(db_session, t3) == "disarmed"  # type: ignore[arg-type]
        assert await is_armed(db_session, "front_door", at=t3) is False  # type: ignore[arg-type]
        assert await is_armed(db_session, "living_room", at=t3) is False  # type: ignore[arg-type]

        # History lists all 3 changes (most recent first)
        changes = await list_changes(db_session)  # type: ignore[arg-type]
        assert len(changes) == 3
        assert [c.kind for c in changes] == ["mode", "cameras", "mode"]
        assert changes[1].to_value == {"mode": "away", "excluded_camera_ids": ["living_room"]}
        assert changes[1].exclusions_after["away"] == ["living_room"]

    @pytest.mark.asyncio
    async def test_fail_armed_when_state_cannot_be_read(self) -> None:
        class _BrokenSession:
            async def execute(self, *_args: Any, **_kw: Any) -> Any:
                raise RuntimeError("db down")

        broken = _BrokenSession()
        mode, armed = await resolve_arming_at(
            broken,  # type: ignore[arg-type]
            "front_door",
            datetime(2026, 10, 22, 12, 0, tzinfo=UTC),
        )
        assert mode == "home"
        assert armed is True
        assert (
            await is_armed(
                broken,  # type: ignore[arg-type]
                "front_door",
                at=datetime(2026, 10, 22, 12, 0, tzinfo=UTC),
            )
            is True
        )


class TestArmingScheduleFixedClock:
    """Tests for apply_schedule, next_scheduled, and DST/manual-override invariants (A3)."""

    @pytest.mark.asyncio
    async def test_schedule_fires_and_manual_or_webhook_change_holds_until_next_entry(
        self, db_session: _AsyncSQLiteSession
    ) -> None:
        # Thursday 2026-10-22
        t_setup = datetime(2026, 10, 22, 20, 0, tzinfo=UTC)
        await set_schedule(
            db_session,  # type: ignore[arg-type]
            [
                {"days": ["thursday"], "time": "22:00", "mode": "night"},
                {"days": ["friday"], "time": "07:00", "mode": "home"},
            ],
            now=t_setup,
        )
        await db_session.commit()

        # Before 22:00 -> next_scheduled is 22:00 night, apply_schedule makes no change
        nxt = await next_scheduled(db_session, now=t_setup, household_tz="UTC")  # type: ignore[arg-type]
        assert nxt == (datetime(2026, 10, 22, 22, 0, tzinfo=UTC), "night")
        assert (
            await apply_schedule(db_session, now=t_setup, household_tz="UTC")  # type: ignore[arg-type]
            is None
        )

        # At 22:00 -> schedule fires and switches to night
        t_2200 = datetime(2026, 10, 22, 22, 0, tzinfo=UTC)
        ch = await apply_schedule(db_session, now=t_2200, household_tz="UTC")  # type: ignore[arg-type]
        await db_session.commit()
        assert ch is not None
        assert ch.to_value == "night"
        assert ch.source_kind == "schedule"

        # 1 second after 22:00: webhook switches to away -> manual/webhook change holds!
        t_2200_01 = t_2200 + timedelta(seconds=1)
        await set_mode(
            db_session,  # type: ignore[arg-type]
            "away",
            source_kind="webhook",
            source_name="fp1",
            now=t_2200_01,
        )
        await db_session.commit()

        # Boot catch-up / apply_schedule at 22:05 does NOT overwrite the 22:00:01 webhook change
        t_2205 = datetime(2026, 10, 22, 22, 5, tzinfo=UTC)
        assert (
            await apply_schedule(db_session, now=t_2205, household_tz="UTC")  # type: ignore[arg-type]
            is None
        )
        status = await get_arming_status(db_session, now=t_2205)  # type: ignore[arg-type]
        assert status["mode"] == "away"

        # Entry added at 22:10 for earlier today (21:00) waits for next week's occurrence
        t_2210 = datetime(2026, 10, 22, 22, 10, tzinfo=UTC)
        await set_schedule(
            db_session,  # type: ignore[arg-type]
            [
                {"days": ["thursday"], "time": "21:00", "mode": "disarmed"},
                {"days": ["friday"], "time": "07:00", "mode": "home"},
            ],
            now=t_2210,
        )
        await db_session.commit()
        assert (
            await apply_schedule(db_session, now=t_2210, household_tz="UTC")  # type: ignore[arg-type]
            is None
        )

        # Deleted entry never fires
        await set_schedule(db_session, [], now=t_2210 + timedelta(minutes=1))  # type: ignore[arg-type]
        await db_session.commit()
        t_fri_0700 = datetime(2026, 10, 23, 7, 0, tzinfo=UTC)
        assert (
            await apply_schedule(db_session, now=t_fri_0700, household_tz="UTC")  # type: ignore[arg-type]
            is None
        )

    @pytest.mark.asyncio
    async def test_dst_repeated_hour_fires_once_and_skipped_hour_moves_to_first_valid_instant(
        self, db_session: _AsyncSQLiteSession
    ) -> None:
        # 1. Spring-forward skipped hour in America/New_York: Sunday 2026-03-08 02:30 is skipped
        #    (clocks jump 01:59:59 EST -> 03:00:00 EDT at 07:00:00 UTC).
        t_before_spring = datetime(2026, 3, 8, 6, 0, tzinfo=UTC)
        await set_schedule(
            db_session,  # type: ignore[arg-type]
            [{"days": ["sunday"], "time": "02:30", "mode": "away"}],
            now=t_before_spring,
        )
        await db_session.commit()

        nxt_spring = await next_scheduled(
            db_session,  # type: ignore[arg-type]
            now=t_before_spring,
            household_tz="America/New_York",
        )
        # First valid instant at/after 02:30 on 2026-03-08 is 03:00 EDT == 07:00 UTC
        assert nxt_spring == (datetime(2026, 3, 8, 7, 0, tzinfo=UTC), "away")

        # At 06:59 UTC (01:59 EST), not yet due
        assert (
            await apply_schedule(
                db_session,  # type: ignore[arg-type]
                now=datetime(2026, 3, 8, 6, 59, tzinfo=UTC),
                household_tz="America/New_York",
            )
            is None
        )
        # At 07:00 UTC (03:00 EDT, first valid instant), fires!
        ch_spring = await apply_schedule(
            db_session,  # type: ignore[arg-type]
            now=datetime(2026, 3, 8, 7, 0, tzinfo=UTC),
            household_tz="America/New_York",
        )
        await db_session.commit()
        assert ch_spring is not None and ch_spring.to_value == "away"

        # 2. Fall-back repeated hour in America/New_York: Sunday 2026-11-01 01:30 occurs twice:
        #    first at 05:30 UTC (EDT, UTC-4), second at 06:30 UTC (EST, UTC-5).
        t_before_fall = datetime(2026, 11, 1, 4, 0, tzinfo=UTC)
        await set_schedule(
            db_session,  # type: ignore[arg-type]
            [{"days": ["sunday"], "time": "01:30", "mode": "night"}],
            now=t_before_fall,
        )
        await db_session.commit()

        # First 01:30 (05:30 UTC): fires once
        t_first_0130 = datetime(2026, 11, 1, 5, 30, tzinfo=UTC)
        ch1 = await apply_schedule(
            db_session,  # type: ignore[arg-type]
            now=t_first_0130,
            household_tz="America/New_York",
        )
        await db_session.commit()
        assert ch1 is not None and ch1.to_value == "night"

        # Second wake and restart during the repeated hour (06:30 UTC == second 01:30): does NOT fire again
        t_second_0130 = datetime(2026, 11, 1, 6, 30, tzinfo=UTC)
        ch2 = await apply_schedule(
            db_session,  # type: ignore[arg-type]
            now=t_second_0130,
            household_tz="America/New_York",
        )
        assert ch2 is None

    @pytest.mark.asyncio
    async def test_ensure_external_alerts_rule_is_idempotent_with_fixed_uuid(
        self, db_session: _AsyncSQLiteSession
    ) -> None:
        r1 = await ensure_external_alerts_rule(db_session)  # type: ignore[arg-type]
        await db_session.commit()
        r2 = await ensure_external_alerts_rule(db_session)  # type: ignore[arg-type]
        assert r1.id == EXTERNAL_ALERTS_RULE_ID
        assert r2.id == EXTERNAL_ALERTS_RULE_ID
        assert r1.name == EXTERNAL_ALERTS_RULE_NAME
        assert r1.description == "Seeded rule for external webhook alerts (B4.7)"
        assert r1.severity == AlertSeverityEnum.LOW
        assert r1.dedup_key_template == "{camera_id}:{object_type}:{rule_id}"
        assert r1.sources == ["external"]
        assert r1.enabled is True
        assert r1.cooldown_seconds == 300
        assert r1.channels == []
        assert r1.alert_on_rejected is False

    @pytest.mark.asyncio
    async def test_helpers_validation_pruning_and_scheduler(
        self, db_session: _AsyncSQLiteSession
    ) -> None:
        # 1. _ensure_utc and key_fingerprint
        naive_dt = datetime(2026, 10, 22, 12, 0, 0)
        assert _ensure_utc(naive_dt) == datetime(2026, 10, 22, 12, 0, 0, tzinfo=UTC)
        offset_dt = datetime(2026, 10, 22, 14, 0, 0, tzinfo=timezone(timedelta(hours=2)))
        assert _ensure_utc(offset_dt) == datetime(2026, 10, 22, 12, 0, 0, tzinfo=UTC)
        assert _ensure_utc(None, naive_dt) == datetime(2026, 10, 22, 12, 0, 0, tzinfo=UTC)
        assert _ensure_utc(None).tzinfo == UTC

        fp1 = key_fingerprint("secret-1")
        fp2 = key_fingerprint("secret-2")
        assert len(fp1) == 12
        assert fp1 != fp2

        # 2. _parse_hhmm validation
        assert _parse_hhmm("09:05") == (9, 5)
        with pytest.raises(ValueError, match="expected HH:MM"):
            _parse_hhmm("0905")
        with pytest.raises(ValueError, match="Out-of-range"):
            _parse_hhmm("24:00")
        with pytest.raises(ValueError, match="Out-of-range"):
            _parse_hhmm("12:60")

        # 3. _resolve_household_tz from Property and invalid override fallback
        tz_invalid = await _resolve_household_tz(db_session, "Not/AZone")  # type: ignore[arg-type]
        assert tz_invalid.key == "UTC"

        hh = Household(name="Test Household")
        db_session.add(hh)
        await db_session.flush()
        prop = Property(household_id=hh.id, name="Home", timezone="America/Chicago")
        db_session.add(prop)
        await db_session.commit()
        tz_prop = await _resolve_household_tz(db_session)  # type: ignore[arg-type]
        assert tz_prop.key == "America/Chicago"

        # 4. get_mode_exclusions for disarmed (all cameras) and invalid mode
        disarmed_excl = await get_mode_exclusions(db_session, "disarmed")  # type: ignore[arg-type]
        assert disarmed_excl == ["front_door", "living_room"]
        with pytest.raises(ValueError, match="Invalid arming mode"):
            await get_mode_exclusions(db_session, "invalid")  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="Invalid arming mode"):
            await set_mode(db_session, "invalid")  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="Camera exclusions can only be configured"):
            await set_mode_exclusions(db_session, "disarmed", ["front_door"])  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="Unknown camera_id"):
            await set_mode_exclusions(db_session, "home", ["no_such_cam"])  # type: ignore[arg-type]

        # 5. set_schedule validation errors
        with pytest.raises(ValueError, match="Invalid schedule days"):
            await set_schedule(db_session, [{"days": ["funday"], "time": "08:00", "mode": "home"}])  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="Invalid schedule mode"):
            await set_schedule(
                db_session,
                [{"days": ["monday"], "time": "08:00", "mode": "perimeter"}],  # type: ignore[arg-type]
            )

        # 6. resolve_arming_at when arming_changes is empty: disarmed vs home with exclusion
        state_row = await db_session.get(ArmingState, 1)
        if state_row is None:
            state_row = ArmingState(
                id=1,
                mode="disarmed",
                set_at=datetime(2026, 1, 1, tzinfo=UTC),
                source_kind="user",
                source_name="admin",
            )
            db_session.add(state_row)
        else:
            state_row.mode = "disarmed"
        await db_session.commit()
        assert await resolve_arming_at(
            db_session,  # type: ignore[arg-type]
            "front_door",
            datetime(2026, 1, 2, tzinfo=UTC),
        ) == ("disarmed", False)

        # Direct exclusion row when arming_changes is still empty
        state_row.mode = "home"
        db_session.add(ArmingModeExclusion(mode="home", camera_id="living_room"))
        db_session.add(ArmingModeExclusion(mode="away", camera_id="front_door"))
        await db_session.commit()
        assert await resolve_arming_at(
            db_session,  # type: ignore[arg-type]
            "living_room",
            datetime(2026, 1, 2, tzinfo=UTC),
        ) == ("home", False)
        assert await resolve_arming_at(
            db_session,  # type: ignore[arg-type]
            "front_door",
            datetime(2026, 1, 2, tzinfo=UTC),
        ) == ("home", True)

        # 7. resolve_arming_at when first change is a camera exclusion change
        t_cam_change = datetime(2026, 5, 1, 12, 0, tzinfo=UTC)
        ch_cam_1 = await set_mode_exclusions(
            db_session,  # type: ignore[arg-type]
            "home",
            ["front_door"],
            now=t_cam_change,
        )
        await db_session.commit()
        assert ch_cam_1.source_kind == "user"
        assert ch_cam_1.source_name == "user"
        assert ch_cam_1.from_value == {"mode": "home", "excluded_camera_ids": ["living_room"]}
        assert ch_cam_1.to_value == {"mode": "home", "excluded_camera_ids": ["front_door"]}
        # Away mode's exclusion was preserved, not deleted when updating home
        assert await get_mode_exclusions(db_session, "away") == ["front_door"]  # type: ignore[arg-type]
        assert await get_mode_exclusions(db_session, "home") == ["front_door"]  # type: ignore[arg-type]

        # Before the camera change, living_room WAS excluded (from_value) and front_door was NOT
        assert await resolve_arming_at(
            db_session,  # type: ignore[arg-type]
            "living_room",
            t_cam_change - timedelta(minutes=5),
        ) == ("home", False)
        assert await resolve_arming_at(
            db_session,  # type: ignore[arg-type]
            "front_door",
            t_cam_change - timedelta(minutes=5),
        ) == ("home", True)
        # After the camera change, front_door IS excluded and living_room is NOT
        assert await resolve_arming_at(
            db_session,  # type: ignore[arg-type]
            "living_room",
            t_cam_change + timedelta(minutes=5),
        ) == ("home", True)
        assert await resolve_arming_at(
            db_session,  # type: ignore[arg-type]
            "front_door",
            t_cam_change + timedelta(minutes=5),
        ) == ("home", False)

        # 8. resolve_arming_at fails armed ('home', True) when DB raises
        broken_session = AsyncMock()
        broken_session.execute.side_effect = RuntimeError("db down")
        assert await resolve_arming_at(
            broken_session,
            "living_room",
            t_cam_change,
        ) == ("home", True)

        # 9. Pruning arming_changes older than 365 days keeps the newest row before cutoff
        t_old_1 = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)
        t_old_2 = datetime(2024, 6, 1, 12, 0, tzinfo=UTC)
        t_recent = datetime(2026, 10, 22, 12, 0, tzinfo=UTC)
        ch_old_1 = await set_mode(db_session, "away", now=t_old_1)  # type: ignore[arg-type]
        ch_old_2 = await set_mode(db_session, "night", now=t_old_2)  # type: ignore[arg-type]
        await db_session.commit()
        assert ch_old_1.source_kind == "user"
        assert ch_old_1.source_name == "user"
        assert ch_old_2.from_value == "away"
        assert ch_old_2.to_value == "night"
        assert ch_old_2.exclusions_after["home"] == ["front_door"]
        old_id_1 = ch_old_1.id
        old_id_2 = ch_old_2.id

        await set_mode(
            db_session,  # type: ignore[arg-type]
            "home",
            source_kind="webhook",
            source_name="fp_webhook_1",
            now=t_recent,
        )
        await db_session.commit()

        changes = await list_changes(db_session, limit=50)  # type: ignore[arg-type]
        change_ids = {c.id for c in changes}
        assert old_id_1 not in change_ids
        assert old_id_2 in change_ids

        # 10. ArmingScheduler run_once, start, and stop + get_arming_status with next_scheduled
        prop.timezone = "UTC"
        await db_session.commit()

        @asynccontextmanager
        async def _factory():
            yield db_session

        await set_schedule(
            db_session,  # type: ignore[arg-type]
            [{"days": ["thursday"], "time": "12:05", "mode": "night"}],
            now=t_recent,
        )
        await db_session.commit()

        st_wh = await get_arming_status(db_session, now=t_recent, household_tz="UTC")  # type: ignore[arg-type]
        assert st_wh["by_whom"] == "webhook:fp_webhook_1"
        assert st_wh["since"] == t_recent
        assert st_wh["next_scheduled"] == {
            "at": datetime(2026, 10, 22, 12, 5, tzinfo=UTC),
            "mode": "night",
        }

        await set_mode(
            db_session,  # type: ignore[arg-type]
            "home",
            source_kind="user",
            source_name="alice",
            now=t_recent + timedelta(minutes=1),
        )
        await db_session.commit()
        st_user = await get_arming_status(
            db_session,  # type: ignore[arg-type]
            now=t_recent + timedelta(minutes=1),
            household_tz="UTC",
        )
        assert st_user["by_whom"] == "alice"

        sched = ArmingScheduler(session_factory=_factory)
        applied = await sched.run_once(now=datetime(2026, 10, 22, 12, 10, tzinfo=UTC))
        assert applied is not None and applied.to_value == "night"
        await sched.start()
        await sched.start()  # idempotent when already running
        sched.wake()
        await sched.stop()
