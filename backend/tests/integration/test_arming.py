"""Integration tests for Arming core service and `/api/arming` routes (B4.7 / 4n-arming.md)."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from backend.core.database import get_session
from backend.models.alert import AlertRule
from backend.models.arming import EXTERNAL_ALERTS_RULE_ID, EXTERNAL_ALERTS_RULE_NAME
from backend.models.camera import Camera
from backend.services.arming import ensure_external_alerts_rule
from backend.services.backup_service import BackupService
from backend.services.restore_service import RestoreService

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_arming_api_routes_roundtrip(client: AsyncClient) -> None:
    cam_id = f"arming_cam_{uuid.uuid4().hex[:8]}"
    async with get_session() as db:
        db.add(
            Camera(
                id=cam_id,
                name="Living room",
                folder_path=f"/export/foscam/{cam_id}",
                status="online",
            )
        )
        await db.commit()

    # 1. GET /api/arming
    r0 = await client.get("/api/arming")
    assert r0.status_code == 200
    assert r0.json()["mode"] in ("home", "away", "night", "disarmed")

    # 2. PUT /api/arming/mode
    r_mode = await client.put("/api/arming/mode", json={"mode": "home"})
    assert r_mode.status_code == 200
    assert r_mode.json()["mode"] == "home"

    # 3. PUT / GET /api/arming/modes/home/cameras
    r_cams = await client.put(
        "/api/arming/modes/home/cameras",
        json={"excluded_camera_ids": [cam_id]},
    )
    assert r_cams.status_code == 200
    assert r_cams.json()["excluded_camera_ids"] == [cam_id]

    r_cams_get = await client.get("/api/arming/modes/home/cameras")
    assert r_cams_get.status_code == 200
    assert r_cams_get.json()["excluded_camera_ids"] == [cam_id]

    # 4. PUT / GET /api/arming/schedule
    r_sched = await client.put(
        "/api/arming/schedule",
        json={"items": [{"days": ["monday"], "time": "23:00", "mode": "night"}]},
    )
    assert r_sched.status_code == 200
    assert len(r_sched.json()["items"]) == 1

    # 5. GET /api/arming/changes
    r_changes = await client.get("/api/arming/changes")
    assert r_changes.status_code == 200
    assert len(r_changes.json()["items"]) >= 2

    # Clean up schedule and exclusions
    await client.put("/api/arming/schedule", json={"items": []})
    await client.put("/api/arming/modes/home/cameras", json={"excluded_camera_ids": []})


@pytest.mark.asyncio
async def test_restore_archive_with_seeded_external_alerts_rule_leaves_one_row(
    client: AsyncClient,
    tmp_path: Path,
) -> None:
    """Restoring an archive containing the seeded External alerts rule leaves one row, not two (4n-arming.md)."""
    async with get_session() as db:
        await ensure_external_alerts_rule(db)
        await db.commit()

        backup_svc = BackupService(backup_dir=tmp_path)
        backup_res = await backup_svc.create_backup(db, job_id="b47-restore-dedup")

        restore_svc = RestoreService()
        await restore_svc.restore_from_backup(
            backup_file=backup_res.file_path,
            db=db,
            job_id="b47-restore-apply",
        )
        await db.commit()

        count_by_id = (
            await db.execute(
                select(func.count())
                .select_from(AlertRule)
                .where(AlertRule.id == EXTERNAL_ALERTS_RULE_ID)
            )
        ).scalar()
        count_by_name = (
            await db.execute(
                select(func.count())
                .select_from(AlertRule)
                .where(AlertRule.name == EXTERNAL_ALERTS_RULE_NAME)
            )
        ).scalar()
        assert count_by_id == 1
        assert count_by_name == 1
