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


@pytest.mark.asyncio
async def test_f290_golden_four_step_sequence_on_real_postgres(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify the exact 4-step F-290 golden path sequence over HTTP against real Postgres."""
    from datetime import UTC, datetime, timedelta

    from pydantic import SecretStr

    from backend.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "api_keys", [SecretStr("b47-int-wh-key")])
    wh_headers = {"X-API-Key": "b47-int-wh-key"}

    tag = uuid.uuid4().hex[:8]
    cam_create = await client.post(
        "/api/cameras",
        json={
            "name": f"Living room ({tag})",
            "folder_path": f"/export/foscam/b47_living_{tag}",
            "status": "online",
        },
    )
    assert cam_create.status_code == 201, cam_create.text
    cam_id = cam_create.json()["id"]

    det_now = datetime.now(UTC)
    det_res = await client.post(
        "/api/detections/bulk",
        json={
            "detections": [
                {
                    "camera_id": cam_id,
                    "object_type": "person",
                    "confidence": 0.94,
                    "detected_at": det_now.isoformat(),
                    "file_path": f"/cameras/b47-int-{tag}-{idx}.jpg",
                    "bbox_x": 10,
                    "bbox_y": 10,
                    "bbox_width": 60,
                    "bbox_height": 120,
                }
                for idx in range(3)
            ]
        },
    )
    assert det_res.status_code == 207, det_res.text
    det_ids = [int(r["id"]) for r in det_res.json()["results"]]

    # 1. Away by webhook -> confirmed person on camera X gives an alert
    r_away = await client.post(
        "/api/webhooks/inbound/mode",
        json={"mode": "away"},
        headers=wh_headers,
    )
    assert r_away.status_code == 200, r_away.text

    t1 = datetime.now(UTC)
    ev1_res = await client.post(
        "/api/events/bulk",
        json={
            "events": [
                {
                    "batch_id": f"b47-int-{tag}-away",
                    "camera_id": cam_id,
                    "started_at": t1.isoformat(),
                    "ended_at": (t1 + timedelta(seconds=10)).isoformat(),
                    "risk_score": 75,
                    "risk_level": "high",
                    "summary": "Away fixture",
                    "reasoning": "Test",
                    "detection_ids": [det_ids[0]],
                    "verdict": "confirmed",
                }
            ]
        },
    )
    assert ev1_res.status_code == 207, ev1_res.text
    ev1_id = int(ev1_res.json()["results"][0]["id"])
    dec1 = await client.get(f"/api/arming/events/{ev1_id}/decision")
    assert dec1.status_code == 200, dec1.text
    assert dec1.json()["notify"] is True
    alerts_1 = await client.get("/api/alert-service/alerts", params={"event_id": ev1_id})
    assert alerts_1.status_code == 200, alerts_1.text
    items_1 = alerts_1.json()["items"]
    assert len(items_1) >= 1
    assert items_1[0]["raised_while_unarmed"] is False
    for a1 in items_1:
        await client.post(f"/api/alert-service/alerts/{a1['id']}/dismiss", json={})

    # 2. Home leaving X out -> same fixture gives no alert and decision names arming
    r_home = await client.put("/api/arming/mode", json={"mode": "home"})
    assert r_home.status_code == 200, r_home.text
    r_excl = await client.put(
        "/api/arming/modes/home/cameras",
        json={"excluded_camera_ids": [cam_id]},
    )
    assert r_excl.status_code == 200, r_excl.text

    t2 = datetime.now(UTC) + timedelta(seconds=1)
    ev2_res = await client.post(
        "/api/events/bulk",
        json={
            "events": [
                {
                    "batch_id": f"b47-int-{tag}-home",
                    "camera_id": cam_id,
                    "started_at": t2.isoformat(),
                    "ended_at": (t2 + timedelta(seconds=10)).isoformat(),
                    "risk_score": 75,
                    "risk_level": "high",
                    "summary": "Home excluded fixture",
                    "reasoning": "Test",
                    "detection_ids": [det_ids[1]],
                    "verdict": "confirmed",
                }
            ]
        },
    )
    assert ev2_res.status_code == 207, ev2_res.text
    ev2_id = int(ev2_res.json()["results"][0]["id"])
    dec2 = await client.get(f"/api/arming/events/{ev2_id}/decision")
    assert dec2.status_code == 200, dec2.text
    assert dec2.json()["notify"] is False
    assert "arming" in dec2.json()["decided_by"].lower(), dec2.json()
    assert "Home leaves out" in dec2.json()["decided_by"]

    # 3. Critical fixture while Disarmed gives an alert marked raised while unarmed
    r_disarm = await client.post(
        "/api/webhooks/inbound/disarm",
        json={"reason": "int test disarm"},
        headers=wh_headers,
    )
    assert r_disarm.status_code == 200, r_disarm.text

    t3 = datetime.now(UTC) + timedelta(seconds=2)
    ev3_res = await client.post(
        "/api/events/bulk",
        json={
            "events": [
                {
                    "batch_id": f"b47-int-{tag}-crit",
                    "camera_id": cam_id,
                    "started_at": t3.isoformat(),
                    "ended_at": (t3 + timedelta(seconds=10)).isoformat(),
                    "risk_score": 95,
                    "risk_level": "critical",
                    "summary": "Critical fixture while disarmed",
                    "reasoning": "Test",
                    "detection_ids": [det_ids[2]],
                    "verdict": "confirmed",
                }
            ]
        },
    )
    assert ev3_res.status_code == 207, ev3_res.text
    ev3_id = int(ev3_res.json()["results"][0]["id"])
    alerts_3 = await client.get("/api/alert-service/alerts", params={"event_id": ev3_id})
    assert alerts_3.status_code == 200, alerts_3.text
    items_3 = alerts_3.json()["items"]
    assert len(items_3) >= 1
    assert items_3[0]["raised_while_unarmed"] is True

    # 4. /alert with default severity on armed camera gives external event + alert from "External alerts"
    r_rearm = await client.post(
        "/api/webhooks/inbound/arm",
        json={},
        headers=wh_headers,
    )
    assert r_rearm.status_code == 200, r_rearm.text
    r_ext = await client.post(
        "/api/webhooks/inbound/alert",
        json={
            "camera_id": cam_id,
            "source": "door_sensor",
            "message": f"Door sensor opened ({tag})",
        },
        headers=wh_headers,
    )
    assert r_ext.status_code == 200, r_ext.text
    ext_body = r_ext.json()
    assert ext_body["notify"] is True
    assert ext_body["severity"] == "medium"
    assert len(ext_body["alert_ids"]) == 1
    ext_alert = (await client.get(f"/api/alert-service/alerts/{ext_body['alert_ids'][0]}")).json()
    assert ext_alert["verdict_source"] == "external"
    assert ext_alert["rule_id"] == EXTERNAL_ALERTS_RULE_ID
