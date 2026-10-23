"""Unit tests for backend.api.routes.arming (`/api/arming`, B4.7 / 4n-arming.md)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, event
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR, UUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker

from backend.api.routes.arming import (
    read_arming_changes,
    read_arming_schedule,
    read_arming_status,
    read_mode_cameras,
    update_arming_mode,
    update_arming_schedule,
    update_mode_cameras,
)
from backend.api.schemas.arming import (
    ArmingModeCamerasUpdateRequest,
    ArmingScheduleEntrySchema,
    ArmingScheduleUpdateRequest,
    ArmingSetModeRequest,
)
from backend.models.arming import (
    ArmingChange,
    ArmingModeExclusion,
    ArmingScheduleEntry,
    ArmingState,
)
from backend.models.camera import Camera
from backend.models.household_org import Household
from backend.models.property import Property

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

    def get_bind(self) -> Any:
        return self._s.get_bind()

    async def execute(self, statement: Any, params: Any = None, **kwargs: Any) -> Any:
        return self._s.execute(statement, params=params, **kwargs)

    async def flush(self) -> None:
        self._s.flush()

    async def commit(self) -> None:
        self._s.commit()


@pytest.fixture
def db_session(tmp_path: Path):
    db_file = tmp_path / "arming_routes_unit.db"
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
        ArmingState.__table__,
        ArmingModeExclusion.__table__,
        ArmingScheduleEntry.__table__,
        ArmingChange.__table__,
    ):
        with engine.begin() as conn:
            tbl.create(conn, checkfirst=True)

    factory = sessionmaker(engine, expire_on_commit=False)
    with factory() as sync_sess:
        sync_sess.add(
            Camera(
                id="living_room",
                name="Living room",
                folder_path="/export/foscam/living_room",
                status="online",
            )
        )
        sync_sess.commit()
        yield _AsyncSQLiteSession(sync_sess)

    engine.dispose()


class TestArmingAppRoutes:
    """Unit tests for GET/PUT /api/arming, /mode, /modes/{mode}/cameras, /schedule, /changes."""

    @pytest.mark.asyncio
    async def test_arming_routes_roundtrip_and_422_validation(
        self, db_session: _AsyncSQLiteSession
    ) -> None:
        req = SimpleNamespace(state=SimpleNamespace(user=SimpleNamespace(username="admin")))

        # 1. GET /api/arming default
        st0 = await read_arming_status(db=db_session)  # type: ignore[arg-type]
        assert st0.mode == "home"

        # 2. PUT /api/arming/mode -> away
        st1 = await update_arming_mode(
            ArmingSetModeRequest(mode="away"),
            req,  # type: ignore[arg-type]
            db=db_session,  # type: ignore[arg-type]
        )
        assert st1.mode == "away"
        assert st1.source_kind == "user"
        assert st1.source_name == "admin"

        # Invalid mode -> 422
        with pytest.raises(HTTPException) as exc_mode:
            await update_arming_mode(
                ArmingSetModeRequest(mode="invalid"),
                req,  # type: ignore[arg-type]
                db=db_session,  # type: ignore[arg-type]
            )
        assert exc_mode.value.status_code == 422

        # 3. PUT / GET /api/arming/modes/home/cameras
        cams_res = await update_mode_cameras(
            "home",
            ArmingModeCamerasUpdateRequest(excluded_camera_ids=["living_room"]),
            req,  # type: ignore[arg-type]
            db=db_session,  # type: ignore[arg-type]
        )
        assert cams_res.mode == "home"
        assert cams_res.excluded_camera_ids == ["living_room"]

        cams_read = await read_mode_cameras("home", db=db_session)  # type: ignore[arg-type]
        assert cams_read.excluded_camera_ids == ["living_room"]

        # Unknown camera -> 422
        with pytest.raises(HTTPException) as exc_cam:
            await update_mode_cameras(
                "home",
                ArmingModeCamerasUpdateRequest(excluded_camera_ids=["unknown_cam"]),
                req,  # type: ignore[arg-type]
                db=db_session,  # type: ignore[arg-type]
            )
        assert exc_cam.value.status_code == 422

        # 4. PUT / GET /api/arming/schedule
        sched_res = await update_arming_schedule(
            ArmingScheduleUpdateRequest(
                items=[
                    ArmingScheduleEntrySchema(
                        days=["monday", "tuesday"], time="22:30", mode="night"
                    )
                ]
            ),
            db=db_session,  # type: ignore[arg-type]
        )
        assert len(sched_res.items) == 1
        assert sched_res.items[0].time == "22:30"

        sched_read = await read_arming_schedule(db=db_session)  # type: ignore[arg-type]
        assert len(sched_read.items) == 1

        # Invalid schedule time -> 422
        with pytest.raises(HTTPException) as exc_sched:
            await update_arming_schedule(
                ArmingScheduleUpdateRequest(
                    items=[ArmingScheduleEntrySchema(days=["monday"], time="99:99", mode="night")]
                ),
                db=db_session,  # type: ignore[arg-type]
            )
        assert exc_sched.value.status_code == 422

        # 5. GET /api/arming/changes
        changes = await read_arming_changes(limit=50, db=db_session)  # type: ignore[arg-type]
        assert len(changes.items) == 2
        assert [c.kind for c in changes.items] == ["cameras", "mode"]
