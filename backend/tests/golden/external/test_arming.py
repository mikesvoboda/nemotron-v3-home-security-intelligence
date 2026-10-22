"""B4.7 Arming core golden path (F-290; docs/uplevel/4n-arming.md).

Exercises the external HTTP surface of the live stack (`logged_in_api`):
1. Away by webhook (`POST /api/webhooks/inbound/mode` `{"mode": "away"}`), then a confirmed
   person on camera X gives an alert.
2. Home leaving X out (`PUT /api/arming/mode` `{"mode": "home"}` +
   `PUT /api/arming/modes/home/cameras`), then the same fixture gives no alert and the
   decision names arming (`GET /api/arming/events/{id}/decision`).
3. A critical fixture while Disarmed (`POST /api/webhooks/inbound/disarm`) gives an alert
   marked `raised_while_unarmed`.
4. `/alert` (`POST /api/webhooks/inbound/alert`) with the default severity on an armed camera
   gives an external event and an alert from "External alerts".
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from backend.models.arming import EXTERNAL_ALERTS_RULE_ID

pytestmark = [pytest.mark.network, pytest.mark.timeout(300)]


def _create_person_fixture_event(
    logged_in_api: httpx.Client,
    *,
    camera_id: str,
    started_at: datetime,
    risk_score: int,
    risk_level: str,
    tag: str,
) -> int:
    det_res = logged_in_api.post(
        "/api/detections/bulk",
        json={
            "detections": [
                {
                    "camera_id": camera_id,
                    "object_type": "person",
                    "confidence": 0.94,
                    "detected_at": started_at.isoformat(),
                    "file_path": f"/cameras/b47-golden-{tag}.jpg",
                    "bbox_x": 10,
                    "bbox_y": 10,
                    "bbox_width": 60,
                    "bbox_height": 120,
                }
            ]
        },
    )
    assert det_res.status_code == 207, det_res.text[:500]
    det_id = int(det_res.json()["results"][0]["id"])

    ev_res = logged_in_api.post(
        "/api/events/bulk",
        json={
            "events": [
                {
                    "batch_id": f"b47-golden-{tag}",
                    "camera_id": camera_id,
                    "started_at": started_at.isoformat(),
                    "ended_at": (started_at + timedelta(seconds=10)).isoformat(),
                    "risk_score": risk_score,
                    "risk_level": risk_level,
                    "summary": f"B4.7 golden fixture ({tag})",
                    "reasoning": "Golden path arming evaluation",
                    "detection_ids": [det_id],
                    "verdict": "confirmed",
                }
            ]
        },
    )
    assert ev_res.status_code == 207, ev_res.text[:500]
    return int(ev_res.json()["results"][0]["id"])


def test_f290_b47_arming_core_golden_path(logged_in_api: httpx.Client) -> None:
    """4n-arming.md B4.7 golden path:
    Away by webhook -> confirmed person on camera X alerts;
    Home leaving X out -> same fixture gives no alert and decision names arming;
    critical fixture while Disarmed -> alert marked raised_while_unarmed;
    /alert with default severity on armed camera -> external event + alert from 'External alerts'.
    """
    tag = uuid.uuid4().hex[:8]
    cam_create = logged_in_api.post(
        "/api/cameras",
        json={
            "name": f"Living room {tag}",
            "folder_path": f"/cameras/b47_living_{tag}",
            "status": "online",
        },
    )
    assert cam_create.status_code == 201, cam_create.text[:500]
    cam_id = str(cam_create.json()["id"])

    key_create = logged_in_api.post(
        "/api/auth/api-keys",
        json={"name": f"b47-golden-webhook-{tag}"},
    )
    assert key_create.status_code == 201, key_create.text[:500]
    key_id = str(key_create.json()["id"])
    webhook_key = str(key_create.json()["key"])
    wh_headers = {"X-API-Key": webhook_key}

    try:
        # 1. Away by webhook, then a confirmed person on camera X gives an alert
        r_away = logged_in_api.post(
            "/api/webhooks/inbound/mode",
            json={"mode": "away"},
            headers=wh_headers,
        )
        assert r_away.status_code == 200, r_away.text[:500]
        assert r_away.json()["mode"] == "away"

        t1 = datetime.now(UTC)
        ev1_id = _create_person_fixture_event(
            logged_in_api,
            camera_id=cam_id,
            started_at=t1,
            risk_score=75,
            risk_level="high",
            tag=f"{tag}-away",
        )
        dec1 = logged_in_api.get(f"/api/arming/events/{ev1_id}/decision")
        assert dec1.status_code == 200, dec1.text[:500]
        assert dec1.json()["notify"] is True

        alerts_1 = logged_in_api.get("/api/alert-service/alerts", params={"event_id": ev1_id})
        assert alerts_1.status_code == 200, alerts_1.text[:500]
        items_1 = alerts_1.json()["items"]
        assert len(items_1) >= 1
        assert items_1[0]["raised_while_unarmed"] is False

        # 2. Home leaving X out, then the same fixture gives no alert and the decision names arming
        r_home = logged_in_api.put("/api/arming/mode", json={"mode": "home"})
        assert r_home.status_code == 200, r_home.text[:500]
        r_excl = logged_in_api.put(
            "/api/arming/modes/home/cameras",
            json={"excluded_camera_ids": [cam_id]},
        )
        assert r_excl.status_code == 200, r_excl.text[:500]
        assert r_excl.json()["excluded_camera_ids"] == [cam_id]

        t2 = datetime.now(UTC) + timedelta(seconds=1)
        ev2_id = _create_person_fixture_event(
            logged_in_api,
            camera_id=cam_id,
            started_at=t2,
            risk_score=75,
            risk_level="high",
            tag=f"{tag}-home-excl",
        )
        dec2 = logged_in_api.get(f"/api/arming/events/{ev2_id}/decision")
        assert dec2.status_code == 200, dec2.text[:500]
        assert dec2.json()["notify"] is False
        assert "arming" in dec2.json()["decided_by"].lower()
        assert "Home leaves out" in dec2.json()["decided_by"]

        alerts_2 = logged_in_api.get("/api/alert-service/alerts", params={"event_id": ev2_id})
        assert alerts_2.status_code == 200, alerts_2.text[:500]
        assert alerts_2.json()["items"] == []

        # 3. A critical fixture while Disarmed gives an alert marked raised while unarmed
        r_disarm = logged_in_api.post(
            "/api/webhooks/inbound/disarm",
            json={"reason": "golden test disarm"},
            headers=wh_headers,
        )
        assert r_disarm.status_code == 200, r_disarm.text[:500]
        assert r_disarm.json()["mode"] == "disarmed"

        t3 = datetime.now(UTC) + timedelta(seconds=2)
        ev3_id = _create_person_fixture_event(
            logged_in_api,
            camera_id=cam_id,
            started_at=t3,
            risk_score=95,
            risk_level="critical",
            tag=f"{tag}-disarmed-crit",
        )
        alerts_3 = logged_in_api.get("/api/alert-service/alerts", params={"event_id": ev3_id})
        assert alerts_3.status_code == 200, alerts_3.text[:500]
        items_3 = alerts_3.json()["items"]
        assert len(items_3) >= 1
        assert items_3[0]["raised_while_unarmed"] is True

        # 4. /alert with the default severity on an armed camera gives an external event and
        #    an alert from "External alerts"
        r_rearm = logged_in_api.post(
            "/api/webhooks/inbound/arm",
            json={},
            headers=wh_headers,
        )
        assert r_rearm.status_code == 200, r_rearm.text[:500]
        assert r_rearm.json()["mode"] == "away"

        r_ext = logged_in_api.post(
            "/api/webhooks/inbound/alert",
            json={
                "camera_id": cam_id,
                "source": "door_sensor",
                "message": f"Door sensor opened ({tag})",
            },
            headers=wh_headers,
        )
        assert r_ext.status_code == 200, r_ext.text[:500]
        ext_body = r_ext.json()
        assert ext_body["notify"] is True
        assert ext_body["severity"] == "medium"
        assert len(ext_body["alert_ids"]) == 1

        ext_alert_res = logged_in_api.get(f"/api/alert-service/alerts/{ext_body['alert_ids'][0]}")
        assert ext_alert_res.status_code == 200, ext_alert_res.text[:500]
        ext_alert = ext_alert_res.json()
        assert ext_alert["verdict_source"] == "external"
        assert ext_alert["rule_id"] == EXTERNAL_ALERTS_RULE_ID
    finally:
        logged_in_api.put("/api/arming/modes/home/cameras", json={"excluded_camera_ids": []})
        logged_in_api.put("/api/arming/mode", json={"mode": "home"})
        logged_in_api.delete(f"/api/auth/api-keys/{key_id}")
        logged_in_api.delete(f"/api/cameras/{cam_id}")
