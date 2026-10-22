"""Unit tests for AlertPipeline and sweep (B4.1 / docs/uplevel/4n-alerting.md)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock

import pytest

from backend.api.schemas.websocket import WebSocketAlertEventType
from backend.models.alert import (
    ActivitySnooze,
    Alert,
    AlertEvent,
    AlertRule,
    AlertSeverityEnum,
    AlertStatusEnum,
)
from backend.models.detection import Detection
from backend.models.event import Event
from backend.models.event_notify import EventNotifyDecision
from backend.models.event_verification import EventVerification
from backend.services.alerting.pipeline import AlertPipeline, _normalise_planned
from backend.services.alerting.verdict import FaceCandidate, SpecialistEvidence


class _InMemoryPipelineDB:
    """Lightweight relational store for unit-testing AlertPipeline transaction semantics."""

    def __init__(self) -> None:
        self.events: dict[int, Event] = {}
        self.verifications: list[EventVerification] = []
        self.detections: dict[int, Detection] = {}
        self.event_detection_links: list[tuple[int, int]] = []
        self.rules: list[AlertRule] = []
        self.snoozes: list[ActivitySnooze] = []
        self.alerts: list[Alert] = []
        self.alert_events: list[AlertEvent] = []
        self.decisions: dict[int, EventNotifyDecision] = {}
        self.advisory_locks: list[tuple[str, str, str]] = []
        self.committed: int = 0
        self.camera_enabled: dict[str, bool] = {}
        self.camera_thresholds: dict[str, int] = {}
        self.master_enabled: bool = True
        self.risk_filters: tuple[str, ...] = ("critical", "high", "medium")
        self.household_tz: str = "UTC"
        # B4.2: recorded planned deliveries (planner output, normalised dicts).
        self.deliveries: list[dict[str, Any]] = []

    def add_event(
        self,
        event_id: int,
        camera_id: str = "front_door",
        *,
        risk_score: int | None = 75,
        verdict: str = "confirmed",
        started_at: datetime | None = None,
        detections: list[tuple[str, float]] | None = None,
        verification_created_at: datetime | None = None,
    ) -> Event:
        ts = started_at or datetime(2026, 10, 22, 2, 0, tzinfo=UTC)
        ev = Event(
            id=event_id,
            batch_id=f"batch-{event_id}",
            camera_id=camera_id,
            started_at=ts,
            ended_at=ts,
            risk_score=risk_score,
            risk_level="high" if (risk_score or 0) >= 60 else "medium",
            summary="Test summary",
            reasoning="Test reasoning",
        )
        self.events[event_id] = ev
        vrow = EventVerification(
            id=len(self.verifications) + 1,
            event_id=event_id,
            verdict=verdict,
            engine="llama.cpp",
            model_id="qwen3-vl",
            created_at=verification_created_at or ts,
        )
        self.verifications.append(vrow)

        det_specs = detections if detections is not None else [("person", 0.92)]
        for obj_type, conf in det_specs:
            det_id = len(self.detections) + 1
            det = Detection(
                id=det_id,
                camera_id=camera_id,
                file_path=f"/export/foscam/det_{det_id}.jpg",
                object_type=obj_type,
                confidence=conf,
                detected_at=ts,
            )
            self.detections[det_id] = det
            self.event_detection_links.append((event_id, det_id))
        return ev


@pytest.mark.asyncio
async def test_pipeline_creates_open_alert_and_publishes_alert_created() -> None:
    store = _InMemoryPipelineDB()
    t0 = datetime(2026, 10, 22, 2, 0, tzinfo=UTC)
    store.add_event(1, "front_door", risk_score=75, verdict="confirmed", started_at=t0)

    broadcaster = AsyncMock()
    pipeline = AlertPipeline.from_memory_store(store, broadcaster=broadcaster)

    res = await pipeline.process(1, now=t0)

    assert res.notify is True
    assert res.decided_by == "default"
    assert res.already_processed is False
    assert len(store.alerts) == 1
    alert = store.alerts[0]
    assert alert.status == AlertStatusEnum.OPEN
    assert alert.verdict_source == "local"
    assert alert.match_count == 1
    assert alert.last_seen_at == t0
    assert alert.last_event_id == 1
    assert alert.severity == AlertSeverityEnum.HIGH

    assert len(store.alert_events) == 1
    assert store.alert_events[0].alert_id == alert.id
    assert store.alert_events[0].event_id == 1

    assert 1 in store.decisions
    assert store.decisions[1].notify is True
    assert store.decisions[1].decided_by == "default"

    broadcaster.broadcast_alert.assert_awaited_once()
    call_args = broadcaster.broadcast_alert.await_args
    assert call_args.args[1] == WebSocketAlertEventType.ALERT_CREATED
    assert call_args.args[0]["id"] == alert.id
    assert call_args.args[0]["status"] == "open"


@pytest.mark.asyncio
async def test_pipeline_idempotent_per_event() -> None:
    store = _InMemoryPipelineDB()
    t0 = datetime(2026, 10, 22, 2, 0, tzinfo=UTC)
    store.add_event(1, "front_door", risk_score=75, verdict="confirmed", started_at=t0)

    broadcaster = AsyncMock()
    pipeline = AlertPipeline.from_memory_store(store, broadcaster=broadcaster)

    res1 = await pipeline.process(1, now=t0)
    res2 = await pipeline.process(1, now=t0 + timedelta(seconds=5))

    assert res1.notify is True
    assert res2.already_processed is True
    assert res2.notify is True
    assert len(store.alerts) == 1
    assert store.alerts[0].match_count == 1
    assert broadcaster.broadcast_alert.await_count == 1


@pytest.mark.asyncio
async def test_pipeline_folds_repeats_within_cooldown_without_notifying_again() -> None:
    store = _InMemoryPipelineDB()
    t0 = datetime(2026, 10, 22, 2, 0, tzinfo=UTC)
    t1 = t0 + timedelta(seconds=120)
    store.add_event(1, "front_door", risk_score=75, verdict="confirmed", started_at=t0)
    store.add_event(2, "front_door", risk_score=70, verdict="confirmed", started_at=t1)

    broadcaster = AsyncMock()
    pipeline = AlertPipeline.from_memory_store(store, broadcaster=broadcaster)

    res1 = await pipeline.process(1, now=t0)
    res2 = await pipeline.process(2, now=t1)

    assert res1.notify is True
    assert res2.notify is False
    assert len(store.alerts) == 1
    alert = store.alerts[0]
    assert alert.match_count == 2
    assert alert.last_seen_at == t1
    assert alert.last_event_id == 2
    assert [ae.event_id for ae in store.alert_events] == [1, 2]
    assert store.decisions[2].notify is False

    assert broadcaster.broadcast_alert.await_count == 2
    second_call = broadcaster.broadcast_alert.await_args_list[1]
    assert second_call.args[1] == WebSocketAlertEventType.ALERT_UPDATED


@pytest.mark.asyncio
async def test_pipeline_fold_escalates_and_notifies_when_severity_rises() -> None:
    store = _InMemoryPipelineDB()
    t0 = datetime(2026, 10, 22, 2, 0, tzinfo=UTC)
    t1 = t0 + timedelta(seconds=60)
    store.add_event(1, "front_door", risk_score=65, verdict="confirmed", started_at=t0)
    store.add_event(2, "front_door", risk_score=92, verdict="confirmed", started_at=t1)

    broadcaster = AsyncMock()
    pipeline = AlertPipeline.from_memory_store(store, broadcaster=broadcaster)

    await pipeline.process(1, now=t0)
    res2 = await pipeline.process(2, now=t1)

    assert res2.notify is True
    assert len(store.alerts) == 1
    alert = store.alerts[0]
    assert alert.match_count == 2
    assert alert.severity == AlertSeverityEnum.CRITICAL
    assert store.decisions[2].notify is True


@pytest.mark.asyncio
async def test_pipeline_opens_new_alert_after_cooldown_expires() -> None:
    store = _InMemoryPipelineDB()
    t0 = datetime(2026, 10, 22, 2, 0, tzinfo=UTC)
    t1 = t0 + timedelta(seconds=301)
    store.add_event(1, "front_door", risk_score=75, verdict="confirmed", started_at=t0)
    store.add_event(2, "front_door", risk_score=75, verdict="confirmed", started_at=t1)

    broadcaster = AsyncMock()
    pipeline = AlertPipeline.from_memory_store(store, broadcaster=broadcaster)

    await pipeline.process(1, now=t0)
    res2 = await pipeline.process(2, now=t1)

    assert res2.notify is True
    assert len(store.alerts) == 2
    assert store.alerts[0].match_count == 1
    assert store.alerts[1].match_count == 1
    assert store.alerts[1].last_event_id == 2


@pytest.mark.asyncio
async def test_pipeline_takes_advisory_locks_in_sorted_order() -> None:
    store = _InMemoryPipelineDB()
    t0 = datetime(2026, 10, 22, 2, 0, tzinfo=UTC)
    store.add_event(1, "front_door", risk_score=80, verdict="confirmed", started_at=t0)
    store.rules = [
        AlertRule(
            id="rule-z",
            name="Rule Z",
            enabled=True,
            severity=AlertSeverityEnum.HIGH,
            risk_threshold=70,
            cooldown_seconds=300,
        ),
        AlertRule(
            id="rule-a",
            name="Rule A",
            enabled=True,
            severity=AlertSeverityEnum.CRITICAL,
            risk_threshold=70,
            cooldown_seconds=300,
        ),
    ]

    pipeline = AlertPipeline.from_memory_store(store)
    await pipeline.process(1, now=t0)

    # Sorted by (rule_id or 'default', camera_id, object_type): default, rule-a, rule-z
    assert [lock[0] for lock in store.advisory_locks] == ["default", "rule-a", "rule-z"]


@pytest.mark.asyncio
async def test_pipeline_detector_fallback_and_trusted_suppression_and_rejected() -> None:
    store = _InMemoryPipelineDB()
    t0 = datetime(2026, 10, 22, 2, 0, tzinfo=UTC)
    # 1. VLM failure -> detector fallback -> unverified alert
    store.add_event(
        1,
        "front_door",
        risk_score=None,
        verdict="verification_failed",
        started_at=t0,
        detections=[("person", 0.9)],
    )
    # 2. Trusted face covering everyone -> no alert
    store.add_event(
        2,
        "back_yard",
        risk_score=80,
        verdict="confirmed",
        started_at=t0,
        detections=[("person", 0.9)],
    )
    # 3. Rejected verdict -> no alert
    store.add_event(
        3,
        "side_gate",
        risk_score=15,
        verdict="rejected",
        started_at=t0,
        detections=[("person", 0.9)],
    )

    pipeline = AlertPipeline.from_memory_store(store)

    r1 = await pipeline.process(1, now=t0)
    assert r1.notify is True
    assert len(store.alerts) == 1
    assert store.alerts[0].verdict_source == "detector"

    r2 = await pipeline.process(
        2,
        now=t0,
        specialists=SpecialistEvidence(
            faces=(
                FaceCandidate(
                    person_name="Alice",
                    is_household_member=True,
                    is_auto_enrolled=False,
                    is_unknown=False,
                ),
            )
        ),
    )
    assert r2.notify is False
    assert len(store.alerts) == 1
    assert store.decisions[2].notify is False

    r3 = await pipeline.process(3, now=t0)
    assert r3.notify is False
    assert len(store.alerts) == 1
    assert store.decisions[3].notify is False


@pytest.mark.asyncio
async def test_pipeline_sweep_processes_missing_decisions_and_marks_stale_events() -> None:
    store = _InMemoryPipelineDB()
    now = datetime(2026, 10, 22, 4, 0, tzinfo=UTC)
    stale_time = now - timedelta(hours=2)
    fresh_time = now - timedelta(minutes=10)

    store.add_event(
        10,
        "front_door",
        risk_score=80,
        verdict="confirmed",
        started_at=stale_time,
        verification_created_at=stale_time,
    )
    store.add_event(
        11,
        "back_yard",
        risk_score=80,
        verdict="confirmed",
        started_at=fresh_time,
        verification_created_at=fresh_time,
    )

    planner_calls: list[tuple[int, bool]] = []

    def fake_planner(
        alert: Alert, *, stale: bool = False, **kwargs: object
    ) -> list[dict[str, str]]:
        planner_calls.append((alert.event_id, stale))
        return [{"status": "expired" if stale else "pending"}]

    pipeline = AlertPipeline.from_memory_store(store, planner=fake_planner)
    results = await pipeline.sweep_unprocessed(
        now=now,
        upgrade_applied_at=now - timedelta(hours=3),
    )

    assert [r.event_id for r in results] == [10, 11]
    assert len(store.alerts) == 2
    assert planner_calls == [(10, True), (11, False)]
    assert results[0].planned_deliveries == ({"status": "expired"},)
    assert results[1].planned_deliveries == ({"status": "pending"},)


# -- B4.2: delivery-row recording (planner output lands as rows) -------------


class TestPlannedDeliveryRecording:
    async def test_memory_path_records_planned_deliveries_in_store(self) -> None:
        """The store records the planner's output so history reads see it."""
        store = _InMemoryPipelineDB()
        store.add_event(1, "front_door", risk_score=75, verdict="confirmed")
        now = datetime(2026, 10, 22, 2, 0, tzinfo=UTC)  # not stale (within 1h cutoff)

        def fake_planner(
            alert: Alert, *, stale: bool = False, **kw: object
        ) -> list[dict[str, str]]:
            return [
                {
                    "status": "expired" if stale else "pending",
                    "recipient_id": "r1",
                    "channel_id": "c1",
                    "channel_kind": "email",
                    "alert_id": alert.id,
                }
            ]

        pipeline = AlertPipeline.from_memory_store(store, planner=fake_planner)
        result = await pipeline.process(1, now=now)

        assert result.notify is True
        assert len(store.deliveries) == 1
        rec = store.deliveries[0]
        assert rec["alert_id"] == store.alerts[0].id
        assert rec["status"] == "pending"
        assert rec["recipient_id"] == "r1"
        assert rec["channel_id"] == "c1"

    async def test_writer_hook_persists_records_in_one_transaction(self) -> None:
        """The writer hook receives the session and the planned records.

        DB-path shape is proven end-to-end in the DB-gated suite
        (test_delivery_pipeline_db.py): the hook runs inside the caller's
        transaction, so a rollback removes alert AND delivery rows together.
        """
        pipeline = AlertPipeline()

        async def fake_writer(session: object, records: list[dict[str, str]]) -> None:
            written.extend(records)

        pipeline._delivery_writer = fake_writer
        written: list[dict[str, str]] = []
        await pipeline._write_deliveries_in_session(
            session=None,  # type: ignore[arg-type]
            planned_deliveries=[{"status": "pending", "recipient_id": "r1", "channel_id": "c1"}],
        )
        assert written == [{"status": "pending", "recipient_id": "r1", "channel_id": "c1"}]

    async def test_no_writer_is_noop(self) -> None:
        """Without a writer (B4.1 default), planning alone changes nothing."""
        pipeline = AlertPipeline()
        # _write_deliveries_in_session with writer None and records present: no-op.
        await pipeline._write_deliveries_in_session(
            session=None,  # type: ignore[arg-type]
            planned_deliveries=[{"status": "pending"}],
        )

    async def test_normalise_planned_accepts_dataclass_and_dict(self) -> None:
        from backend.models.alert_delivery import DeliveryChannelKind, DeliveryStatus
        from backend.services.alerting.planner import PlannedDelivery

        now = datetime(2026, 10, 22, 3, 0, tzinfo=UTC)
        dc = PlannedDelivery(
            alert_id="a1",
            recipient_id="r1",
            channel_id="c1",
            channel_kind=DeliveryChannelKind.EMAIL,
            status=DeliveryStatus.SUPPRESSED,
            include_names=False,
        )
        rec = _normalise_planned(dc, now)
        assert rec == {
            "alert_id": "a1",
            "recipient_id": "r1",
            "channel_id": "c1",
            "channel_kind": "email",
            "status": "suppressed",
            "include_names": False,
            "planned_at": now,
        }
        assert _normalise_planned({"status": "pending"}, now)["planned_at"] == now


@pytest.mark.asyncio
async def test_pipeline_sqlalchemy_session_path_process_and_sweep(tmp_path) -> None:
    """Exercise AlertPipeline's SQLAlchemy session path (`_process_in_session`,
    `_find_open_alert`, `_link_alert_event`, `_upsert_decision`, and `sweep_unprocessed`).
    """
    import contextlib

    from sqlalchemy import create_engine
    from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR, UUID
    from sqlalchemy.ext.compiler import compiles
    from sqlalchemy.orm import Session, sessionmaker

    from backend.models.camera import Camera
    from backend.models.enrichment import ThreatDetection
    from backend.models.event_detection import EventDetection
    from backend.models.face_identity import (
        EnrollmentCandidate,
        FaceDetectionEvent,
        KnownPerson,
    )
    from backend.models.household_org import Household
    from backend.models.notification_preferences import (
        CameraNotificationSetting,
        NotificationPreferences,
    )
    from backend.models.property import Property

    @compiles(JSONB, "sqlite")
    def _c_jsonb(_t: Any, _c: Any, **_kw: Any) -> str:
        return "JSON"

    @compiles(UUID, "sqlite")
    def _c_uuid(_t: Any, _c: Any, **_kw: Any) -> str:
        return "VARCHAR(36)"

    @compiles(TSVECTOR, "sqlite")
    def _c_tsv(_t: Any, _c: Any, **_kw: Any) -> str:
        return "TEXT"

    @compiles(ARRAY, "sqlite")
    def _c_arr(_t: Any, _c: Any, **_kw: Any) -> str:
        return "JSON"

    class _SQLiteAsyncSession:
        def __init__(self, s: Session) -> None:
            self._s = s

        def add(self, obj: Any) -> None:
            self._s.add(obj)

        def get_bind(self) -> Any:
            return self._s.get_bind()

        async def execute(self, stmt: Any, params: Any = None, **kw: Any) -> Any:
            if hasattr(stmt, "text") and "pg_advisory_xact_lock" in str(stmt.text):
                return None
            return self._s.execute(stmt, params=params, **kw)

        async def scalars(self, stmt: Any, params: Any = None, **kw: Any) -> Any:
            return self._s.scalars(stmt, params=params, **kw)

        async def get(self, entity: Any, ident: Any, **kw: Any) -> Any:
            return self._s.get(entity, ident, **kw)

        async def flush(self) -> None:
            self._s.flush()

        async def commit(self) -> None:
            self._s.commit()

    engine = create_engine(f"sqlite:///{tmp_path / 'pipeline_sa.db'}", future=True)
    for tbl in (
        Household.__table__,
        Property.__table__,
        Camera.__table__,
        Event.__table__,
        EventVerification.__table__,
        EventNotifyDecision.__table__,
        Detection.__table__,
        ThreatDetection.__table__,
        EventDetection.__table__,
        KnownPerson.__table__,
        FaceDetectionEvent.__table__,
        EnrollmentCandidate.__table__,
        NotificationPreferences.__table__,
        CameraNotificationSetting.__table__,
        AlertRule.__table__,
        Alert.__table__,
        AlertEvent.__table__,
        ActivitySnooze.__table__,
    ):
        with engine.begin() as conn:
            tbl.create(conn, checkfirst=True)

    maker = sessionmaker(engine, expire_on_commit=False)

    @contextlib.asynccontextmanager
    async def session_factory():
        with maker() as sync_s:
            yield _SQLiteAsyncSession(sync_s)

    t0 = datetime(2026, 10, 22, 2, 0, tzinfo=UTC)
    t1 = t0 + timedelta(seconds=60)
    with maker() as s:
        s.add(
            Camera(
                id="front_door",
                name="Front Door",
                folder_path="/export/foscam/front_door",
                status="online",
            )
        )
        ev1 = Event(
            id=1,
            batch_id="b-sa-1",
            camera_id="front_door",
            started_at=t0,
            risk_score=75,
            risk_level="high",
            summary="SA event 1",
        )
        ev2 = Event(
            id=2,
            batch_id="b-sa-2",
            camera_id="front_door",
            started_at=t1,
            risk_score=80,
            risk_level="high",
            summary="SA event 2",
        )
        s.add_all([ev1, ev2])
        s.flush()
        det1 = Detection(
            id=10,
            camera_id="front_door",
            file_path="/cameras/sa1.jpg",
            detected_at=t0,
            object_type="person",
            confidence=0.92,
            enrichment_data={
                "threats": [{"type": "weapon", "severity": "high", "confidence": 0.9}]
            },
        )
        det2 = Detection(
            id=11,
            camera_id="front_door",
            file_path="/cameras/sa2.jpg",
            detected_at=t1,
            object_type="person",
            confidence=0.93,
        )
        s.add_all([det1, det2])
        s.flush()
        s.add_all(
            [
                EventDetection(event_id=1, detection_id=10),
                EventDetection(event_id=2, detection_id=11),
                EventVerification(
                    event_id=1,
                    verdict="confirmed",
                    engine="ai-vlm",
                    model_id="qwen",
                    created_at=t0,
                ),
                EventVerification(
                    event_id=2,
                    verdict="confirmed",
                    engine="ai-vlm",
                    model_id="qwen",
                    created_at=t1,
                ),
            ]
        )
        s.commit()

    broadcaster = AsyncMock()
    pipeline = AlertPipeline(session_factory=session_factory, broadcaster=broadcaster)
    r1 = await pipeline.process(1, now=t0)
    assert r1.notify is True
    assert len(r1.created_alerts) == 1

    # Sweep processes undecided event 2 and folds it into the open alert from event 1
    swept = await pipeline.sweep_unprocessed(now=t1, upgrade_applied_at=t0 - timedelta(hours=1))
    assert [r.event_id for r in swept] == [2]
    assert len(swept[0].updated_alerts) == 1
    engine.dispose()
