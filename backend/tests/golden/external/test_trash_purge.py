"""B4.4 Trash purger golden path (F-087, F-088; docs/uplevel/4n-trash.md).

Exercises the external HTTP surface of the live stack (`logged_in_api`):
1. A permanent delete of a live event answers 409 (`DELETE /api/events/{id}?permanent=true`).
2. Trash it (`DELETE /api/events/{id}` -> 204), verify it appears in `GET /api/events/deleted`,
   then delete it permanently (`DELETE /api/events/{id}?permanent=true` -> 204), and it answers
   404 with its detections gone (`GET /api/detections/{id}` -> 404).
3. Trash remaining disposable events and call Empty Trash (`DELETE /api/events/deleted` -> 200),
   verifying Empty Trash purges the rest.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest

pytestmark = [pytest.mark.network, pytest.mark.timeout(300)]


def _pick_camera_id(logged_in_api: httpx.Client) -> str:
    events_res = logged_in_api.get("/api/events", params={"limit": 10})
    assert events_res.status_code == 200, events_res.text[:500]
    items = events_res.json().get("items") or []
    if items:
        return str(items[0]["camera_id"])

    cams_res = logged_in_api.get("/api/cameras")
    assert cams_res.status_code == 200, cams_res.text[:500]
    cams = cams_res.json()
    cam_items = cams.get("items") if isinstance(cams, dict) else cams
    assert cam_items, "expected at least one camera on the stack"
    return str(cam_items[0]["id"])


def test_b44_trash_purge_golden_path(logged_in_api: httpx.Client) -> None:
    """4n-trash.md B4.4 golden path:
    a permanent delete of a live event answers 409; trash it, delete it permanently,
    and it answers 404 with its files and detections gone; Empty Trash purges the rest.
    """
    # Verify runtime config exposes trash_retention_days
    cfg_res = logged_in_api.get("/api/system/config")
    assert cfg_res.status_code == 200, cfg_res.text[:500]
    assert cfg_res.json().get("trash_retention_days") == 30

    cam_id = _pick_camera_id(logged_in_api)
    now = datetime.now(UTC)
    tag = uuid.uuid4().hex[:8]

    # Create two disposable detections so the shared smoke event stays untouched
    det_res = logged_in_api.post(
        "/api/detections/bulk",
        json={
            "detections": [
                {
                    "camera_id": cam_id,
                    "object_type": "person",
                    "confidence": 0.91,
                    "detected_at": (now - timedelta(minutes=10)).isoformat(),
                    "file_path": f"/cameras/b44-golden-{tag}-1.jpg",
                    "bbox_x": 10,
                    "bbox_y": 10,
                    "bbox_width": 50,
                    "bbox_height": 100,
                },
                {
                    "camera_id": cam_id,
                    "object_type": "person",
                    "confidence": 0.93,
                    "detected_at": (now - timedelta(minutes=8)).isoformat(),
                    "file_path": f"/cameras/b44-golden-{tag}-2.jpg",
                    "bbox_x": 20,
                    "bbox_y": 20,
                    "bbox_width": 60,
                    "bbox_height": 110,
                },
            ]
        },
    )
    assert det_res.status_code == 207, det_res.text[:500]
    det_results = det_res.json()["results"]
    det1_id = int(det_results[0]["id"])
    det2_id = int(det_results[1]["id"])

    # Create two disposable events linked to det1_id and det2_id
    ev_res = logged_in_api.post(
        "/api/events/bulk",
        json={
            "events": [
                {
                    "batch_id": f"b44-golden-{tag}-1",
                    "camera_id": cam_id,
                    "started_at": (now - timedelta(minutes=10)).isoformat(),
                    "ended_at": (now - timedelta(minutes=9)).isoformat(),
                    "risk_score": 55,
                    "risk_level": "medium",
                    "summary": f"B4.4 golden disposable event 1 ({tag})",
                    "reasoning": "Disposable event for single permanent purge check",
                    "detection_ids": [det1_id],
                },
                {
                    "batch_id": f"b44-golden-{tag}-2",
                    "camera_id": cam_id,
                    "started_at": (now - timedelta(minutes=8)).isoformat(),
                    "ended_at": (now - timedelta(minutes=7)).isoformat(),
                    "risk_score": 60,
                    "risk_level": "medium",
                    "summary": f"B4.4 golden disposable event 2 ({tag})",
                    "reasoning": "Disposable event for Empty Trash check",
                    "detection_ids": [det2_id],
                },
            ]
        },
    )
    assert ev_res.status_code == 207, ev_res.text[:500]
    ev_results = ev_res.json()["results"]
    ev1_id = int(ev_results[0]["id"])
    ev2_id = int(ev_results[1]["id"])

    # 1. Permanent delete of a live event answers 409
    live_purge = logged_in_api.delete(f"/api/events/{ev1_id}", params={"permanent": "true"})
    assert live_purge.status_code == 409, live_purge.text[:500]

    # 2. Trash ev1, verify it is in Trash, then permanently delete it
    soft_del_1 = logged_in_api.delete(f"/api/events/{ev1_id}")
    assert soft_del_1.status_code == 204, soft_del_1.text[:500]

    trash_list_1 = logged_in_api.get("/api/events/deleted")
    assert trash_list_1.status_code == 200, trash_list_1.text[:500]
    trash_ids_1 = [item["id"] for item in trash_list_1.json()["items"]]
    assert ev1_id in trash_ids_1

    perm_del_1 = logged_in_api.delete(f"/api/events/{ev1_id}", params={"permanent": "true"})
    assert perm_del_1.status_code == 204, perm_del_1.text[:500]

    # Event 1 answers 404, is gone from Trash, and its detection answers 404
    assert logged_in_api.get(f"/api/events/{ev1_id}").status_code == 404
    trash_after_1 = logged_in_api.get("/api/events/deleted")
    assert ev1_id not in [item["id"] for item in trash_after_1.json()["items"]]
    assert logged_in_api.get(f"/api/detections/{det1_id}").status_code == 404

    # 3. Trash ev2 and call Empty Trash -> purges the rest
    soft_del_2 = logged_in_api.delete(f"/api/events/{ev2_id}")
    assert soft_del_2.status_code == 204, soft_del_2.text[:500]

    empty_res = logged_in_api.delete("/api/events/deleted")
    assert empty_res.status_code == 200, empty_res.text[:500]
    empty_body = empty_res.json()
    assert ev2_id in empty_body["purged"]
    assert empty_body["purged_count"] >= 1

    assert logged_in_api.get(f"/api/events/{ev2_id}").status_code == 404
    assert logged_in_api.get(f"/api/detections/{det2_id}").status_code == 404
    trash_final = logged_in_api.get("/api/events/deleted")
    assert ev2_id not in [item["id"] for item in trash_final.json()["items"]]
