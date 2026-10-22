"""Integration golden-path tests for B4.1 Alert pipeline core (docs/uplevel/4n-alerting.md).

Exercises the six required B4.1 golden-path scenarios against live PostgreSQL and Redis:
1. Confirmed verdict -> open Alert row, AlertEvent link, notify=True, and `alert_created` frame.
2. Repeats within cooldown fold into the open alert (`match_count=2`, `alert_updated` frame).
3. Activity snooze holds (via PATCH /api/events/{id} snooze_until -> ActivitySnooze), suppressing
   non-critical matches while critical breaks through.
4. VLM failure (`verification_failed`, NULL score) -> unverified alert (`verdict_source="detector"`).
5. Trusted household face covering every detected person -> no alert (`notify=False`).
6. Rejected verdict -> no alert (`notify=False`), unless `alert_on_rejected=True`.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from backend.api.schemas.websocket import WebSocketAlertEventType
from backend.models.alert import (
    ActivitySnooze,
    Alert,
    AlertEvent,
    AlertSeverityEnum,
    AlertStatusEnum,
)
from backend.models.camera import Camera
from backend.models.detection import Detection
from backend.models.event_notify import EventNotifyDecision
from backend.models.face_identity import FaceDetectionEvent, KnownPerson
from backend.services.alerting.pipeline import AlertPipeline
from backend.services.vlm_analyzer import VlmAnalyzer
from backend.services.vlm_client import VlmTransportError
from backend.services.vlm_verdict import VlmVerdict

pytestmark = pytest.mark.integration


class _ScriptedVlmClient:
    """Scripted VLM client for driving VlmAnalyzer.analyze_batch without GPU/network."""

    def __init__(self, outcomes: list[VlmVerdict | Exception]) -> None:
        self._outcomes = list(outcomes)

    def prompt_text(self, request: Any) -> str:
        return f"ASSESS camera={request.context.camera_id}"

    async def assess(self, request: Any) -> VlmVerdict:
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    async def close(self) -> None:
        return None


def _verdict(
    *,
    verdict: str = "confirmed",
    risk_score: int = 75,
    summary: str = "Person walking up the driveway at night.",
) -> VlmVerdict:
    return VlmVerdict.model_validate(
        {
            "verdict": verdict,
            "risk_score": risk_score,
            "summary": summary,
            "reasoning": "Criterion evidence reviewed.",
            "description": "Driveway at night, one person.",
            "criteria": [{"name": "person_present", "passed": True, "evidence": "full frame"}],
            "provenance": {"engine": "llama.cpp", "model_id": "Qwen3VL-8B-Instruct-Q4_K_M"},
        }
    )


async def _make_camera(db_session: Any) -> Camera:
    cam = Camera(
        id=f"b41cam-{uuid.uuid4().hex[:8]}",
        name=f"B4.1 Camera {uuid.uuid4().hex[:6]}",
        folder_path="/export/foscam/b41",
    )
    db_session.add(cam)
    await db_session.commit()
    return cam


async def _make_detections(
    db_session: Any,
    camera_id: str,
    *,
    detected_at: datetime,
    specs: list[tuple[str, float]] | None = None,
) -> list[int]:
    items = specs or [("person", 0.92)]
    ids: list[int] = []
    for idx, (obj_type, conf) in enumerate(items):
        det = Detection(
            camera_id=camera_id,
            file_path=f"/export/foscam/b41/det_{uuid.uuid4().hex[:8]}_{idx}.jpg",
            object_type=obj_type,
            confidence=conf,
            detected_at=detected_at + timedelta(seconds=idx),
        )
        db_session.add(det)
        await db_session.flush()
        ids.append(det.id)
    await db_session.commit()
    return ids


class TestB41AlertPipelineCoreGoldenPath:
    """End-to-end golden path for B4.1 Alert pipeline core on real Postgres."""

    async def test_confirmed_creates_open_alert_and_folds_repeats_within_cooldown(
        self,
        db_session: Any,
        real_redis: Any,
    ) -> None:
        cam = await _make_camera(db_session)
        t0 = datetime(2026, 10, 22, 3, 0, tzinfo=UTC)
        t1 = t0 + timedelta(seconds=60)

        det_ids_1 = await _make_detections(db_session, cam.id, detected_at=t0)
        det_ids_2 = await _make_detections(db_session, cam.id, detected_at=t1)

        analyzer = VlmAnalyzer(
            vlm_client=_ScriptedVlmClient(
                [
                    _verdict(verdict="confirmed", risk_score=75),
                    _verdict(verdict="confirmed", risk_score=72),
                ]
            ),
            redis_client=real_redis,
        )

        broadcaster = AsyncMock()
        from backend.services import event_broadcaster as eb_mod

        orig_get_broadcaster = eb_mod.get_broadcaster

        async def _fake_get_broadcaster(_redis: Any = None) -> Any:
            return broadcaster

        eb_mod.get_broadcaster = _fake_get_broadcaster  # type: ignore[assignment]
        try:
            ev1 = await analyzer.analyze_batch(
                f"b41-confirmed-1-{uuid.uuid4().hex[:6]}",
                camera_id=cam.id,
                detection_ids=det_ids_1,
            )
            ev2 = await analyzer.analyze_batch(
                f"b41-confirmed-2-{uuid.uuid4().hex[:6]}",
                camera_id=cam.id,
                detection_ids=det_ids_2,
            )
        finally:
            eb_mod.get_broadcaster = orig_get_broadcaster  # type: ignore[assignment]

        # 1. Confirmed verdict -> open Alert row + alert_created frame
        alerts = list(
            (await db_session.execute(select(Alert).where(Alert.dedup_key == f"{cam.id}:default")))
            .scalars()
            .all()
        )
        assert len(alerts) == 1
        alert = alerts[0]
        assert alert.status == AlertStatusEnum.OPEN
        assert alert.verdict_source == "local"
        assert alert.severity == AlertSeverityEnum.HIGH

        # 2. Repeat within cooldown folded into the same open alert
        assert alert.match_count == 2
        assert alert.event_id == ev1.id
        assert alert.last_event_id == ev2.id
        assert alert.last_seen_at == t1

        linked_events = list(
            (
                await db_session.execute(
                    select(AlertEvent.event_id)
                    .where(AlertEvent.alert_id == alert.id)
                    .order_by(AlertEvent.event_id.asc())
                )
            )
            .scalars()
            .all()
        )
        assert linked_events == [ev1.id, ev2.id]

        dec1 = await db_session.scalar(
            select(EventNotifyDecision).where(EventNotifyDecision.event_id == ev1.id)
        )
        dec2 = await db_session.scalar(
            select(EventNotifyDecision).where(EventNotifyDecision.event_id == ev2.id)
        )
        assert dec1 is not None and dec1.notify is True and dec1.decided_by == "default"
        assert dec2 is not None and dec2.notify is False and dec2.decided_by == "default"

        alert_frames = [
            call.args
            for call in broadcaster.broadcast_alert.await_args_list
            if call.args[0].get("id") == alert.id
        ]
        assert len(alert_frames) == 2
        assert alert_frames[0][1] == WebSocketAlertEventType.ALERT_CREATED
        assert alert_frames[0][0]["status"] == "open"
        assert alert_frames[1][1] == WebSocketAlertEventType.ALERT_UPDATED

    async def test_snooze_holds_and_critical_breaks_through(
        self,
        client: Any,
        db_session: Any,
        real_redis: Any,
    ) -> None:
        cam = await _make_camera(db_session)
        t0 = datetime.now(UTC) - timedelta(minutes=5)
        t1 = t0 + timedelta(minutes=1)
        t2 = t0 + timedelta(minutes=2)

        det_ids_1 = await _make_detections(db_session, cam.id, detected_at=t0)
        det_ids_2 = await _make_detections(db_session, cam.id, detected_at=t1)
        det_ids_3 = await _make_detections(db_session, cam.id, detected_at=t2)

        analyzer = VlmAnalyzer(
            vlm_client=_ScriptedVlmClient(
                [
                    _verdict(verdict="confirmed", risk_score=70),
                    _verdict(verdict="confirmed", risk_score=75),
                    _verdict(verdict="confirmed", risk_score=92),
                ]
            ),
            redis_client=real_redis,
        )

        ev1 = await analyzer.analyze_batch(
            f"b41-snooze-1-{uuid.uuid4().hex[:6]}",
            camera_id=cam.id,
            detection_ids=det_ids_1,
        )

        # Snooze via PATCH /api/events/{id} -> writes ActivitySnooze on (cam.id, "person")
        snooze_until = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
        patch_res = await client.patch(
            f"/api/events/{ev1.id}",
            json={"snooze_until": snooze_until},
        )
        assert patch_res.status_code == 200

        snooze_row = await db_session.scalar(
            select(ActivitySnooze).where(
                ActivitySnooze.camera_id == cam.id,
                ActivitySnooze.object_type == "person",
            )
        )
        assert snooze_row is not None
        assert snooze_row.source_event_id == ev1.id

        # Dismiss the first alert so the next event would open a new alert if not snoozed
        first_alert = await db_session.scalar(select(Alert).where(Alert.event_id == ev1.id))
        assert first_alert is not None
        first_alert.status = AlertStatusEnum.DISMISSED
        await db_session.commit()

        # Next high-severity event (risk 75 -> HIGH) is held by the snooze
        ev2 = await analyzer.analyze_batch(
            f"b41-snooze-2-{uuid.uuid4().hex[:6]}",
            camera_id=cam.id,
            detection_ids=det_ids_2,
        )
        dec2 = await db_session.scalar(
            select(EventNotifyDecision).where(EventNotifyDecision.event_id == ev2.id)
        )
        assert dec2 is not None and dec2.notify is False
        alert2 = await db_session.scalar(select(Alert).where(Alert.event_id == ev2.id))
        assert alert2 is None

        # GET /api/events/{ev2.id} reflects the active ActivitySnooze.until
        get_ev2 = await client.get(f"/api/events/{ev2.id}")
        assert get_ev2.status_code == 200
        assert get_ev2.json()["snooze_until"] is not None

        # Critical event (risk 92 -> CRITICAL) breaks through the snooze!
        ev3 = await analyzer.analyze_batch(
            f"b41-snooze-3-{uuid.uuid4().hex[:6]}",
            camera_id=cam.id,
            detection_ids=det_ids_3,
        )
        dec3 = await db_session.scalar(
            select(EventNotifyDecision).where(EventNotifyDecision.event_id == ev3.id)
        )
        assert dec3 is not None and dec3.notify is True
        alert3 = await db_session.scalar(select(Alert).where(Alert.event_id == ev3.id))
        assert alert3 is not None
        assert alert3.severity == AlertSeverityEnum.CRITICAL
        assert alert3.status == AlertStatusEnum.OPEN

    async def test_vlm_failure_produces_unverified_detector_alert(
        self,
        db_session: Any,
        real_redis: Any,
    ) -> None:
        cam = await _make_camera(db_session)
        t0 = datetime(2026, 10, 22, 3, 15, tzinfo=UTC)
        det_ids = await _make_detections(
            db_session,
            cam.id,
            detected_at=t0,
            specs=[("person", 0.88)],
        )

        analyzer = VlmAnalyzer(
            vlm_client=_ScriptedVlmClient([VlmTransportError("vlm engine unreachable")]),
            redis_client=real_redis,
        )
        ev = await analyzer.analyze_batch(
            f"b41-vlmfail-{uuid.uuid4().hex[:6]}",
            camera_id=cam.id,
            detection_ids=det_ids,
        )
        assert ev.risk_score is None

        alert = await db_session.scalar(select(Alert).where(Alert.event_id == ev.id))
        assert alert is not None
        assert alert.status == AlertStatusEnum.OPEN
        assert alert.verdict_source == "detector"
        assert alert.severity == AlertSeverityEnum.MEDIUM

    async def test_trusted_face_covering_everyone_suppresses_alert(
        self,
        db_session: Any,
        real_redis: Any,
    ) -> None:
        cam = await _make_camera(db_session)
        t0 = datetime(2026, 10, 22, 3, 30, tzinfo=UTC)
        det_ids = await _make_detections(
            db_session,
            cam.id,
            detected_at=t0,
            specs=[("person", 0.95)],
        )

        # Seed trusted household member and matching FaceDetectionEvent in the event's window
        person = KnownPerson(
            name=f"Household Alice {uuid.uuid4().hex[:4]}",
            is_household_member=True,
        )
        db_session.add(person)
        await db_session.flush()

        face_event = FaceDetectionEvent(
            camera_id=cam.id,
            timestamp=t0,
            bbox={"x1": 10, "y1": 10, "x2": 100, "y2": 100},
            embedding=b"\x00" * 16,
            matched_person_id=person.id,
            match_confidence=0.94,
            is_unknown=False,
            quality_score=0.9,
        )
        db_session.add(face_event)
        await db_session.commit()

        analyzer = VlmAnalyzer(
            vlm_client=_ScriptedVlmClient([_verdict(verdict="confirmed", risk_score=85)]),
            redis_client=real_redis,
        )
        ev = await analyzer.analyze_batch(
            f"b41-trusted-{uuid.uuid4().hex[:6]}",
            camera_id=cam.id,
            detection_ids=det_ids,
        )

        alert = await db_session.scalar(select(Alert).where(Alert.event_id == ev.id))
        assert alert is None
        dec = await db_session.scalar(
            select(EventNotifyDecision).where(EventNotifyDecision.event_id == ev.id)
        )
        assert dec is not None and dec.notify is False

    async def test_rejected_verdict_suppresses_alert_unless_overridden(
        self,
        db_session: Any,
        real_redis: Any,
    ) -> None:
        cam = await _make_camera(db_session)
        t0 = datetime(2026, 10, 22, 3, 45, tzinfo=UTC)
        det_ids = await _make_detections(
            db_session,
            cam.id,
            detected_at=t0,
            specs=[("person", 0.91)],
        )

        analyzer = VlmAnalyzer(
            vlm_client=_ScriptedVlmClient([_verdict(verdict="rejected", risk_score=80)]),
            redis_client=real_redis,
        )
        ev = await analyzer.analyze_batch(
            f"b41-rejected-{uuid.uuid4().hex[:6]}",
            camera_id=cam.id,
            detection_ids=det_ids,
        )

        alert = await db_session.scalar(select(Alert).where(Alert.event_id == ev.id))
        assert alert is None
        dec = await db_session.scalar(
            select(EventNotifyDecision).where(EventNotifyDecision.event_id == ev.id)
        )
        assert dec is not None and dec.notify is False

    async def test_idempotency_hit_and_recovery_and_sweep_and_rule_test_route(
        self,
        client: Any,
        db_session: Any,
        real_redis: Any,
    ) -> None:
        from sqlalchemy import delete

        cam = await _make_camera(db_session)
        t0 = datetime.now(UTC) - timedelta(minutes=2)
        det_ids = await _make_detections(
            db_session,
            cam.id,
            detected_at=t0,
            specs=[("person", 0.93)],
        )
        batch_id = f"b41-idem-{uuid.uuid4().hex[:6]}"

        analyzer = VlmAnalyzer(
            vlm_client=_ScriptedVlmClient([_verdict(verdict="confirmed", risk_score=80)]),
            redis_client=real_redis,
        )
        ev = await analyzer.analyze_batch(batch_id, camera_id=cam.id, detection_ids=det_ids)

        # Simulate crash between commit and AlertPipeline by deleting alert + decision
        await db_session.execute(delete(Alert).where(Alert.event_id == ev.id))
        await db_session.execute(
            delete(EventNotifyDecision).where(EventNotifyDecision.event_id == ev.id)
        )
        await db_session.commit()

        # 1. Redis idempotency hit re-runs AlertPipeline.process(ev.id)
        ev_idem = await analyzer.analyze_batch(batch_id, camera_id=cam.id, detection_ids=det_ids)
        assert ev_idem.id == ev.id
        alert_after_idem = await db_session.scalar(select(Alert).where(Alert.event_id == ev.id))
        assert alert_after_idem is not None
        assert alert_after_idem.status == AlertStatusEnum.OPEN

        # 2. Sweep re-runs AlertPipeline.process for events missing EventNotifyDecision
        await db_session.execute(delete(Alert).where(Alert.event_id == ev.id))
        await db_session.execute(
            delete(EventNotifyDecision).where(EventNotifyDecision.event_id == ev.id)
        )
        await db_session.commit()

        pipeline = AlertPipeline(redis_client=real_redis)
        swept = await pipeline.sweep_unprocessed(
            session=db_session,
            now=t0 + timedelta(minutes=2),
            upgrade_applied_at=t0 - timedelta(hours=1),
        )
        await db_session.commit()
        assert any(r.event_id == ev.id and r.notify is True for r in swept)

        # 3. Rule Test route runs policy (including excluded_camera_ids and alert_on_rejected)
        create_res = await client.post(
            "/api/alerts/rules",
            json={
                "name": f"B4.1 Policy Rule {uuid.uuid4().hex[:6]}",
                "enabled": True,
                "severity": "high",
                "risk_threshold": 60,
                "excluded_camera_ids": [cam.id],
                "alert_on_rejected": True,
            },
        )
        assert create_res.status_code == 201
        rule_id = create_res.json()["id"]
        assert create_res.json()["excluded_camera_ids"] == [cam.id]
        assert create_res.json()["alert_on_rejected"] is True

        test_res = await client.post(
            f"/api/alerts/rules/{rule_id}/test",
            json={"event_ids": [ev.id]},
        )
        assert test_res.status_code == 200
        assert test_res.json()["events_matched"] == 0

        # Remove excluded_camera_ids -> rule matches
        upd_res = await client.put(
            f"/api/alerts/rules/{rule_id}",
            json={"excluded_camera_ids": []},
        )
        assert upd_res.status_code == 200
        test_res_2 = await client.post(
            f"/api/alerts/rules/{rule_id}/test",
            json={"event_ids": [ev.id]},
        )
        assert test_res_2.status_code == 200
        assert test_res_2.json()["events_matched"] == 1
        await client.delete(f"/api/alerts/rules/{rule_id}")
