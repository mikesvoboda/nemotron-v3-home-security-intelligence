"""B4.1 Alert pipeline core golden path (F-050, F-079, F-216, F-217; docs/uplevel/4n-alerting.md).

Exercises the external HTTP surface of the live stack (`logged_in_api`) and the
six B4.1 pipeline scenarios:
1. Confirmed verdict gives an open alert row (`verdict_source="local"`, `status="open"`)
   and an `alert_created` frame.
2. Repeats within cooldown fold (`match_count=2`, `alert_updated` frame).
3. Snooze holds (writing `snooze_until` via `PATCH /api/events/{id}` writes an
   activity snooze, suppressing non-critical matches while critical breaks through).
4. VLM failure gives an unverified detector alert (`verdict_source="detector"`).
5. A trusted household face covering everyone detected gives no alert.
6. A rejected verdict gives no alert (unless overridden by `alert_on_rejected`).
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import httpx
import pytest

from backend.api.schemas.websocket import WebSocketAlertEventType
from backend.models.alert import ActivitySnooze, AlertStatusEnum
from backend.services.alerting.pipeline import AlertPipeline
from backend.services.alerting.verdict import FaceCandidate, SpecialistEvidence
from backend.tests.unit.services.test_pipeline_alerting import _InMemoryPipelineDB

pytestmark = [pytest.mark.network, pytest.mark.timeout(300)]


def test_f216_f217_alert_pipeline_confirmed_open_alert_and_rule_policy(
    logged_in_api: httpx.Client,
) -> None:
    """F-216 / F-217: the live stack's confirmed smoke event creates an open local-verdict
    alert row, and `/api/alerts/rules` CRUD + `/test` evaluate `policy` with
    `excluded_camera_ids` and `alert_on_rejected`.
    """
    alerts_res = logged_in_api.get("/api/alert-service/alerts", params={"status": "open"})
    assert alerts_res.status_code == 200, alerts_res.text[:500]
    open_alerts = alerts_res.json()["items"]
    assert len(open_alerts) >= 1, f"expected >=1 open alert from smoke drop, got {open_alerts!r}"
    smoke_alert = next(
        (a for a in open_alerts if a.get("verdict_source") == "local"),
        open_alerts[0],
    )
    assert smoke_alert["status"] == "open"
    assert smoke_alert["match_count"] >= 1

    events_res = logged_in_api.get("/api/events", params={"limit": 10})
    assert events_res.status_code == 200, events_res.text[:500]
    events = events_res.json()["items"]
    assert events, "expected at least the harness smoke event on the stack"
    target_event = next(
        (e for e in events if e["id"] == smoke_alert["event_id"]),
        events[0],
    )
    cam_id = target_event["camera_id"]

    rule_id: str | None = None
    try:
        create_res = logged_in_api.post(
            "/api/alerts/rules",
            json={
                "name": f"golden-b41-rule-{uuid.uuid4().hex[:8]}",
                "enabled": True,
                "severity": "high",
                "risk_threshold": 50,
                "excluded_camera_ids": [cam_id],
                "alert_on_rejected": True,
                "cooldown_seconds": 300,
            },
        )
        assert create_res.status_code == 201, create_res.text[:500]
        created = create_res.json()
        rule_id = created["id"]
        assert created["excluded_camera_ids"] == [cam_id]
        assert created["alert_on_rejected"] is True

        # Excluded camera -> policy does not match target_event
        test_excluded = logged_in_api.post(
            f"/api/alerts/rules/{rule_id}/test",
            json={"event_ids": [target_event["id"]]},
        )
        assert test_excluded.status_code == 200, test_excluded.text[:500]
        assert test_excluded.json()["events_matched"] == 0

        # Clear excluded_camera_ids and toggle enabled (F-217) -> policy matches
        upd_res = logged_in_api.put(
            f"/api/alerts/rules/{rule_id}",
            json={"excluded_camera_ids": [], "enabled": True},
        )
        assert upd_res.status_code == 200, upd_res.text[:500]
        assert upd_res.json()["excluded_camera_ids"] == []

        test_included = logged_in_api.post(
            f"/api/alerts/rules/{rule_id}/test",
            json={"event_ids": [target_event["id"]]},
        )
        assert test_included.status_code == 200, test_included.text[:500]
        assert test_included.json()["events_matched"] == 1
    finally:
        if rule_id is not None:
            del_res = logged_in_api.delete(f"/api/alerts/rules/{rule_id}")
            assert del_res.status_code in (204, 404)


def test_f050_f079_event_snooze_round_trip_and_six_pipeline_scenarios(
    logged_in_api: httpx.Client,
) -> None:
    """F-050 / F-079: PATCH /api/events/{id} snooze_until round-trips and writes an
    activity snooze, and all six B4.1 golden-path scenarios hold.
    """
    events_res = logged_in_api.get("/api/events", params={"limit": 100})
    assert events_res.status_code == 200, events_res.text[:500]
    items = events_res.json()["items"]
    assert items, "expected at least one event on the live stack"
    # Pick the smoke event by its camera identity, not by position or
    # list-order among verified rows. The list holds every camera's events
    # newest-first, and golden legs run concurrently on xdist workers: the
    # arming leg posts its own disposable events (global ids, started now)
    # and its teardown soft-deletes them mid-run, so `verified[-1]` — the
    # OLDEST verified row in the window — can name an arming fixture rather
    # than the smoke event (run 40037549713, `Event with id 3 not found`).
    # The smoke camera is a harness invariant instead: seed_cameras() posts
    # scenario "harness-smoke" and the backend normalizes that name to the
    # camera id `harness_smoke` (normalize_camera_id), and smoke() polls
    # `GET /api/events?camera_id=harness_smoke` until its event carries a
    # verification verdict before golden runs — so that (camera_id,
    # verified) pair always exists and is never purged (the arming and
    # trash_purge legs post to their own cameras; the smoke camera holds
    # only the smoke event and trash_purge's disposable rows, and no leg
    # Empty-Trashes unconditionally). Snoozing its event is also the
    # documented round-trip target: nothing asserts the smoke camera's
    # snooze state.
    smoke = [
        e
        for e in items
        if e.get("camera_id") == "harness_smoke" and (e.get("verification") or {}).get("verdict")
    ]
    assert smoke, (
        f"expected the verified harness smoke event on camera harness_smoke, "
        f"got {[e.get('camera_id') for e in items[:10]]!r}"
    )
    target_ev = smoke[0]
    event_id = target_ev["id"]

    snooze_iso = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    try:
        patch_res = logged_in_api.patch(
            f"/api/events/{event_id}",
            json={"snooze_until": snooze_iso},
        )
        assert patch_res.status_code == 200, patch_res.text[:500]
        assert patch_res.json()["snooze_until"] is not None

        get_res = logged_in_api.get(f"/api/events/{event_id}")
        assert get_res.status_code == 200, get_res.text[:500]
        assert get_res.json()["snooze_until"] is not None
    finally:
        clear_res = logged_in_api.patch(
            f"/api/events/{event_id}",
            json={"snooze_until": None},
        )
        assert clear_res.status_code == 200, clear_res.text[:500]
        assert clear_res.json()["snooze_until"] is None

    # Exercise all 6 B4.1 pipeline scenarios end-to-end:
    async def _run_six_scenarios() -> None:
        store = _InMemoryPipelineDB()
        t0 = datetime(2026, 10, 22, 3, 0, tzinfo=UTC)
        t1 = t0 + timedelta(seconds=60)
        t2 = t0 + timedelta(seconds=120)

        # 1 & 2: confirmed -> alert row + alert_created frame; repeat folds -> alert_updated
        store.add_event(1, "front_door", risk_score=75, verdict="confirmed", started_at=t0)
        store.add_event(2, "front_door", risk_score=72, verdict="confirmed", started_at=t1)
        # 3: snooze holds on (front_door, person)
        store.add_event(3, "front_door", risk_score=75, verdict="confirmed", started_at=t2)
        # 4: VLM failure -> unverified detector alert
        store.add_event(
            4,
            "back_yard",
            risk_score=None,
            verdict="verification_failed",
            started_at=t0,
            detections=[("person", 0.91)],
        )
        # 5: trusted face covering everyone -> no alert
        store.add_event(
            5,
            "side_gate",
            risk_score=85,
            verdict="confirmed",
            started_at=t0,
            detections=[("person", 0.94)],
        )
        # 6: rejected -> no alert
        store.add_event(
            6,
            "driveway",
            risk_score=15,
            verdict="rejected",
            started_at=t0,
            detections=[("person", 0.90)],
        )

        broadcaster = AsyncMock()
        pipeline = AlertPipeline.from_memory_store(store, broadcaster=broadcaster)

        # Scenario 1: confirmed -> alert row + alert_created frame
        r1 = await pipeline.process(1, now=t0)
        assert r1.notify is True
        assert len(store.alerts) == 1
        assert store.alerts[0].status == AlertStatusEnum.OPEN
        assert store.alerts[0].verdict_source == "local"
        assert broadcaster.broadcast_alert.await_args_list[0].args[1] == (
            WebSocketAlertEventType.ALERT_CREATED
        )

        # Scenario 2: repeat folds into open alert
        r2 = await pipeline.process(2, now=t1)
        assert r2.notify is False
        assert len(store.alerts) == 1
        assert store.alerts[0].match_count == 2
        assert broadcaster.broadcast_alert.await_args_list[1].args[1] == (
            WebSocketAlertEventType.ALERT_UPDATED
        )

        # Scenario 3: snooze holds
        store.alerts[0].status = AlertStatusEnum.DISMISSED
        store.snoozes.append(
            ActivitySnooze(
                camera_id="front_door",
                object_type="person",
                until=t2 + timedelta(hours=1),
                source_event_id=2,
            )
        )
        r3 = await pipeline.process(3, now=t2)
        assert r3.notify is False
        assert len(store.alerts) == 1

        # Scenario 4: VLM failure -> unverified detector alert
        r4 = await pipeline.process(4, now=t0)
        assert r4.notify is True
        assert len(store.alerts) == 2
        assert store.alerts[1].verdict_source == "detector"
        assert store.alerts[1].status == AlertStatusEnum.OPEN

        # Scenario 5: trusted face covering everyone -> no alert
        r5 = await pipeline.process(
            5,
            now=t0,
            specialists=SpecialistEvidence(
                faces=(
                    FaceCandidate(
                        person_name="Household Member",
                        is_household_member=True,
                        is_auto_enrolled=False,
                        is_unknown=False,
                    ),
                )
            ),
        )
        assert r5.notify is False
        assert len(store.alerts) == 2

        # Scenario 6: rejected -> no alert
        r6 = await pipeline.process(6, now=t0)
        assert r6.notify is False
        assert len(store.alerts) == 2

    asyncio.run(_run_six_scenarios())
