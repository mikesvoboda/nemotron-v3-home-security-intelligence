"""Alert pipeline entry point and one-minute recovery sweep (B4.1 / 4n-alerting.md).

`AlertPipeline.process(event_id)` runs in one transaction after a verdict commits:
1. Checks `event_notify_decisions` for idempotency per event.
2. Resolves the verdict chain (`verdict.resolve`) and runs pure policy (`policy.evaluate`).
3. Acquires `pg_advisory_xact_lock` on `(rule_id, activity_key)` in sorted order (F10).
4. Folds into an open alert within cooldown or creates a new `open` alert, recording
   `alert_events` and escalating severity when a repeat is more severe (OD-22(d), F5).
5. Writes `event_notify_decisions` (`notify` = created or escalated, `decided_by` = rule name).
6. Invokes the delivery planner hook (empty in B4.1; B4.2 plugs in `planner.plan`).
7. After commit, publishes `alert_created` or `alert_updated` over WebSocket.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.websocket import WebSocketAlertEventType
from backend.core.config import get_settings
from backend.core.database import get_session
from backend.core.time_utils import utc_now
from backend.models.alert import (
    ActivitySnooze,
    Alert,
    AlertEvent,
    AlertRule,
    AlertStatusEnum,
)
from backend.models.detection import Detection
from backend.models.enrichment import ThreatDetection
from backend.models.event import Event
from backend.models.event_detection import event_detections
from backend.models.event_notify import EventNotifyDecision
from backend.models.event_verification import EventVerification
from backend.models.face_identity import (
    EnrollmentCandidate,
    EnrollmentStatus,
    FaceDetectionEvent,
    KnownPerson,
)
from backend.models.notification_preferences import (
    DEFAULT_CAMERA_RISK_THRESHOLD,
    CameraNotificationSetting,
    NotificationPreferences,
)
from backend.models.property import Property
from backend.services.alerting.policy import (
    DEFAULT_RULE_ID,
    SEVERITY_PRIORITY,
    PolicyContext,
    RuleMatch,
    SnoozeEntry,
    default_rule_from_settings,
    evaluate,
)
from backend.services.alerting.verdict import (
    FaceCandidate,
    ResolvedVerdict,
    SpecialistEvidence,
    resolve,
)

logger = logging.getLogger(__name__)

STALE_EVENT_CUTOFF = timedelta(hours=1)
UPGRADE_SLUG_0012 = "0012-alert-pipeline-core"


def _empty_planner(*args: Any, **kwargs: Any) -> Sequence[Any]:  # noqa: ARG001
    """Default B4.1 planner hook that plans no external deliveries yet."""
    return ()


def _normalise_planned(record: Any, now: datetime) -> dict[str, Any]:
    """Normalise one planner record (dict or PlannedDelivery) to a dict."""
    if isinstance(record, dict):
        return {**record, "planned_at": now}
    return {
        "alert_id": getattr(record, "alert_id", None),
        "recipient_id": record.recipient_id,
        "channel_id": record.channel_id,
        "channel_kind": (
            record.channel_kind.value
            if getattr(record.channel_kind, "value", None)
            else record.channel_kind
        ),
        "status": (record.status.value if getattr(record.status, "value", None) else record.status),
        "include_names": getattr(record, "include_names", False),
        "planned_at": now,
    }


@dataclass(frozen=True, slots=True)
class PipelineResult:
    """Result of running AlertPipeline.process for one event."""

    event_id: int
    notify: bool
    decided_by: str
    resolved: ResolvedVerdict | None = None
    created_alerts: tuple[Alert, ...] = ()
    updated_alerts: tuple[Alert, ...] = ()
    planned_deliveries: tuple[Any, ...] = ()
    already_processed: bool = False


def _ensure_utc(dt: datetime | None, fallback: datetime) -> datetime:
    if dt is None:
        return fallback.replace(tzinfo=UTC) if fallback.tzinfo is None else fallback
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt


class AlertPipeline:
    """Single entry point after a verdict commits."""

    def __init__(
        self,
        *,
        session_factory: Callable[[], Any] = get_session,
        redis_client: Any | None = None,
        broadcaster: Any | None = None,
        planner: Callable[..., Sequence[Any]] | None = None,
        memory_store: Any | None = None,
        delivery_writer: Callable[..., Any] | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._redis = redis_client
        self._broadcaster = broadcaster
        self._planner = planner or _empty_planner
        self._memory_store = memory_store
        # B4.2: writes the planner's records as delivery rows in the SAME
        # transaction as the alert ("the alert and its pending deliveries are
        # written in one transaction"). None keeps the B4.1 shape (no rows).
        self._delivery_writer = delivery_writer

    @classmethod
    def from_memory_store(
        cls,
        store: Any,
        *,
        broadcaster: Any | None = None,
        planner: Callable[..., Sequence[Any]] | None = None,
    ) -> AlertPipeline:
        """Create an AlertPipeline backed by an in-memory store for fast unit tests."""
        return cls(memory_store=store, broadcaster=broadcaster, planner=planner)

    async def process(
        self,
        event_id: int,
        *,
        session: AsyncSession | None = None,
        now: datetime | None = None,
        specialists: SpecialistEvidence | None = None,
    ) -> PipelineResult:
        """Process one committed event idempotently."""
        current_now = _ensure_utc(now, utc_now())
        if self._memory_store is not None:
            result = self._process_in_memory(
                event_id,
                now=current_now,
                specialists=specialists,
            )
            await self._publish_alerts(result.created_alerts, result.updated_alerts)
            return result

        if session is not None:
            result = await self._process_in_session(
                session,
                event_id,
                now=current_now,
                specialists=specialists,
            )
        else:
            async with self._session_factory() as owned_session:
                result = await self._process_in_session(
                    owned_session,
                    event_id,
                    now=current_now,
                    specialists=specialists,
                )
                await owned_session.commit()

        reached_ids = await self._publish_alerts(result.created_alerts, result.updated_alerts)
        # B4.2 (4n-alerting.md:115): the browser rows are marked ``broadcast``
        # once the publish returns — the worker's republish ladder takes only
        # the rows the publish missed (reached nobody or raised).
        await self._mark_browser_rows_broadcast(reached_ids)
        # B4.2: the deliveries are committed — wake the worker so sends start
        # immediately (the poll interval is only the fallback).
        if result.planned_deliveries:
            from backend.services.delivery_worker_registry import wake_delivery_worker

            wake_delivery_worker()
        return result

    async def publish_and_mark(self, result: PipelineResult) -> None:
        """Publish the result's alerts and mark its browser rows ``broadcast``.

        The post-commit tail the production callers (``vlm_analyzer``) run
        after their own commit; ``process()`` runs the same sequence inline.
        """
        reached_ids = await self._publish_alerts(result.created_alerts, result.updated_alerts)
        await self._mark_browser_rows_broadcast(reached_ids)

    def _process_in_memory(
        self,
        event_id: int,
        *,
        now: datetime,
        specialists: SpecialistEvidence | None,
    ) -> PipelineResult:
        store = self._memory_store
        assert store is not None

        existing_dec = store.decisions.get(event_id)
        if existing_dec is not None:
            return PipelineResult(
                event_id=event_id,
                notify=bool(existing_dec.notify),
                decided_by=str(existing_dec.decided_by),
                already_processed=True,
            )

        event = store.events.get(event_id)
        if event is None:
            return PipelineResult(event_id=event_id, notify=False, decided_by=DEFAULT_RULE_ID)

        verifs = [v for v in store.verifications if v.event_id == event_id]
        latest_verif = verifs[-1].verdict if verifs else None
        det_ids = [did for eid, did in store.event_detection_links if eid == event_id]
        detections = [store.detections[did] for did in det_ids if did in store.detections]

        resolved = resolve(
            event,
            detections,
            specialists,
            verdict=latest_verif,
            risk_score=event.risk_score,
        )

        cam_enabled = store.camera_enabled.get(event.camera_id, True)
        cam_threshold = store.camera_thresholds.get(event.camera_id, DEFAULT_CAMERA_RISK_THRESHOLD)
        default_rule = default_rule_from_settings(
            camera_id=event.camera_id,
            camera_enabled=cam_enabled,
            camera_risk_threshold=cam_threshold,
            risk_filters=store.risk_filters,
        )
        all_rules = [default_rule, *[r for r in store.rules if r.enabled]]
        snooze_entries = [
            SnoozeEntry(camera_id=s.camera_id, object_type=s.object_type, until=s.until)
            for s in store.snoozes
            if s.camera_id == event.camera_id
        ]

        event_time = _ensure_utc(event.started_at, now)
        ctx = PolicyContext(
            event_id=event.id,
            camera_id=event.camera_id,
            timestamp=event_time,
            resolved=resolved,
            household_tz=store.household_tz,
            master_enabled=store.master_enabled,
            risk_filters=store.risk_filters,
            camera_enabled=cam_enabled,
            camera_risk_threshold=cam_threshold,
            detection_confidence_threshold=get_settings().detection_confidence_threshold,
            detections=detections,
            threats=(),
            rules=all_rules,
            snoozes=snooze_entries,
        )

        matches = evaluate(ctx)
        sorted_lock_matches = sorted(
            matches,
            key=lambda m: (m.rule_id or DEFAULT_RULE_ID, m.activity_key[0], m.activity_key[1]),
        )
        for m in sorted_lock_matches:
            store.advisory_locks.append(
                (m.rule_id or DEFAULT_RULE_ID, m.activity_key[0], m.activity_key[1])
            )

        is_stale = (now - event_time) > STALE_EVENT_CUTOFF
        created_alerts: list[Alert] = []
        updated_alerts: list[Alert] = []
        planned_deliveries: list[Any] = []
        notified = False

        for match in matches:
            open_alert = self._find_open_alert_in_memory(store, match, event_time)
            if open_alert is not None:
                open_alert.match_count = (open_alert.match_count or 1) + 1
                open_alert.last_seen_at = event_time
                open_alert.last_event_id = event.id
                open_alert.updated_at = now
                store.alert_events.append(AlertEvent(alert_id=open_alert.id, event_id=event.id))

                if SEVERITY_PRIORITY.get(match.effective_severity.value, 0) > SEVERITY_PRIORITY.get(
                    open_alert.severity.value, 0
                ):
                    open_alert.severity = match.effective_severity
                    notified = True
                    planned_deliveries.extend(self._planner(open_alert, now=now, stale=is_stale))
                updated_alerts.append(open_alert)
            else:
                alert = Alert(
                    id=str(uuid.uuid4()),
                    event_id=event.id,
                    rule_id=match.rule_id,
                    severity=match.effective_severity,
                    status=AlertStatusEnum.OPEN,
                    dedup_key=match.dedup_key,
                    verdict_source=resolved.source,
                    match_count=1,
                    last_seen_at=event_time,
                    last_event_id=event.id,
                    channels=[],
                    alert_metadata={
                        "rule_name": match.rule_name,
                        "matched_conditions": list(match.matched_conditions),
                        "recognised": list(resolved.recognised),
                    },
                    created_at=now,
                    updated_at=now,
                )
                store.alerts.append(alert)
                store.alert_events.append(AlertEvent(alert_id=alert.id, event_id=event.id))
                created_alerts.append(alert)
                notified = True
                planned_deliveries.extend(self._planner(alert, now=now, stale=is_stale))

        decided_by = matches[0].rule_name if matches else DEFAULT_RULE_ID
        decision = EventNotifyDecision(
            id=len(store.decisions) + 1,
            event_id=event.id,
            notify=notified,
            decided_by=decided_by,
            created_at=now,
        )
        store.decisions[event.id] = decision
        store.committed += 1
        self._record_planned_deliveries_in_store(store, planned_deliveries, now)

        return PipelineResult(
            event_id=event.id,
            notify=notified,
            decided_by=decided_by,
            resolved=resolved,
            created_alerts=tuple(created_alerts),
            updated_alerts=tuple(updated_alerts),
            planned_deliveries=tuple(planned_deliveries),
            already_processed=False,
        )

    @staticmethod
    def _find_open_alert_in_memory(
        store: Any,
        match: RuleMatch,
        event_time: datetime,
    ) -> Alert | None:
        cutoff = event_time - timedelta(seconds=match.cooldown_seconds)
        candidates: list[Alert] = [
            a
            for a in store.alerts
            if a.status == AlertStatusEnum.OPEN
            and a.dedup_key == match.dedup_key
            and a.rule_id == match.rule_id
            and _ensure_utc(a.last_seen_at or a.created_at, event_time) >= cutoff
        ]
        if not candidates:
            return None
        return candidates[-1]

    async def _process_in_session(
        self,
        session: AsyncSession,
        event_id: int,
        *,
        now: datetime,
        specialists: SpecialistEvidence | None,
    ) -> PipelineResult:
        # Serialize concurrent process() calls for the same event_id on Postgres
        bind = session.get_bind()
        is_postgres = getattr(getattr(bind, "dialect", None), "name", "postgresql") == "postgresql"
        if is_postgres:
            await session.execute(
                text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
                {"key": f"alert_pipeline_event:{event_id}"},
            )

        existing_dec = (
            (
                await session.execute(
                    select(EventNotifyDecision).where(EventNotifyDecision.event_id == event_id)
                )
            )
            .scalars()
            .first()
        )
        if existing_dec is not None:
            return PipelineResult(
                event_id=event_id,
                notify=bool(existing_dec.notify),
                decided_by=str(existing_dec.decided_by),
                already_processed=True,
            )

        event = (await session.execute(select(Event).where(Event.id == event_id))).scalars().first()
        if event is None:
            return PipelineResult(event_id=event_id, notify=False, decided_by=DEFAULT_RULE_ID)

        vrow = (
            (
                await session.execute(
                    select(EventVerification)
                    .where(EventVerification.event_id == event.id)
                    .order_by(EventVerification.id.desc())
                )
            )
            .scalars()
            .first()
        )
        verdict_str = vrow.verdict if vrow is not None else None

        detections = list(
            (
                await session.execute(
                    select(Detection)
                    .join(event_detections, Detection.id == event_detections.c.detection_id)
                    .where(event_detections.c.event_id == event.id)
                    .order_by(Detection.id.asc())
                )
            )
            .scalars()
            .all()
        )

        det_ids = [d.id for d in detections if d.id is not None]
        threats: list[ThreatDetection] = []
        if det_ids:
            threats = list(
                (
                    await session.execute(
                        select(ThreatDetection).where(ThreatDetection.detection_id.in_(det_ids))
                    )
                )
                .scalars()
                .all()
            )

        event_time = _ensure_utc(event.started_at, now)
        spec_evidence = specialists
        if spec_evidence is None:
            spec_evidence = await self._load_specialist_evidence(
                session,
                camera_id=event.camera_id,
                started_at=event_time,
                ended_at=_ensure_utc(event.ended_at, event_time),
            )

        resolved = resolve(
            event,
            detections,
            spec_evidence,
            verdict=verdict_str,
            risk_score=event.risk_score,
        )

        # Load preferences, camera settings, household timezone, rules, and active snoozes
        prefs = (
            (
                await session.execute(
                    select(NotificationPreferences).where(NotificationPreferences.id == 1)
                )
            )
            .scalars()
            .first()
        )
        master_enabled = True if prefs is None else bool(prefs.enabled)
        risk_filters: Sequence[str] = (
            ("critical", "high", "medium")
            if prefs is None or prefs.risk_filters is None
            else tuple(prefs.risk_filters)
        )

        cam_setting = (
            (
                await session.execute(
                    select(CameraNotificationSetting).where(
                        CameraNotificationSetting.camera_id == event.camera_id
                    )
                )
            )
            .scalars()
            .first()
        )
        camera_enabled = True if cam_setting is None else bool(cam_setting.enabled)
        camera_threshold = (
            DEFAULT_CAMERA_RISK_THRESHOLD
            if cam_setting is None
            else int(cam_setting.risk_threshold)
        )

        prop = (
            (await session.execute(select(Property).order_by(Property.id.asc()).limit(1)))
            .scalars()
            .first()
        )
        household_tz = prop.timezone if prop and prop.timezone else "UTC"

        db_rules = list(
            (
                await session.execute(
                    select(AlertRule)
                    .where(AlertRule.enabled.is_(True))
                    .order_by(AlertRule.id.asc())
                )
            )
            .scalars()
            .all()
        )
        default_rule = default_rule_from_settings(
            camera_id=event.camera_id,
            camera_enabled=camera_enabled,
            camera_risk_threshold=camera_threshold,
            risk_filters=risk_filters,
        )
        all_rules = [default_rule, *db_rules]

        db_snoozes = list(
            (
                await session.execute(
                    select(ActivitySnooze).where(
                        ActivitySnooze.camera_id == event.camera_id,
                        ActivitySnooze.until > event_time,
                    )
                )
            )
            .scalars()
            .all()
        )
        snooze_entries = [
            SnoozeEntry(camera_id=s.camera_id, object_type=s.object_type, until=s.until)
            for s in db_snoozes
        ]

        ctx = PolicyContext(
            event_id=event.id,
            camera_id=event.camera_id,
            timestamp=event_time,
            resolved=resolved,
            household_tz=household_tz,
            master_enabled=master_enabled,
            risk_filters=risk_filters,
            camera_enabled=camera_enabled,
            camera_risk_threshold=camera_threshold,
            detection_confidence_threshold=get_settings().detection_confidence_threshold,
            detections=detections,
            threats=threats,
            rules=all_rules,
            snoozes=snooze_entries,
        )

        matches = evaluate(ctx)

        # F10: take pg_advisory_xact_lock on (rule_id, activity_key) in sorted order
        if is_postgres and matches:
            sorted_locks = sorted(
                {
                    (
                        m.rule_id or DEFAULT_RULE_ID,
                        f"{m.activity_key[0]}:{m.activity_key[1]}",
                    )
                    for m in matches
                }
            )
            for rule_key, act_key in sorted_locks:
                await session.execute(
                    text("SELECT pg_advisory_xact_lock(hashtext(:rkey), hashtext(:akey))"),
                    {"rkey": rule_key, "akey": act_key},
                )

        is_stale = (now - event_time) > STALE_EVENT_CUTOFF
        created_alerts: list[Alert] = []
        updated_alerts: list[Alert] = []
        planned_deliveries: list[Any] = []
        notified = False

        for match in matches:
            open_alert = await self._find_open_alert(session, match, event_time)
            if open_alert is not None:
                open_alert.match_count = (open_alert.match_count or 1) + 1
                open_alert.last_seen_at = event_time
                open_alert.last_event_id = event.id
                open_alert.updated_at = now
                await self._link_alert_event(
                    session, open_alert.id, event.id, is_postgres=is_postgres
                )

                if SEVERITY_PRIORITY.get(match.effective_severity.value, 0) > SEVERITY_PRIORITY.get(
                    open_alert.severity.value, 0
                ):
                    open_alert.severity = match.effective_severity
                    notified = True
                    planned_deliveries.extend(self._planner(open_alert, now=now, stale=is_stale))
                await session.flush()
                updated_alerts.append(open_alert)
            else:
                alert = Alert(
                    event_id=event.id,
                    rule_id=match.rule_id,
                    severity=match.effective_severity,
                    status=AlertStatusEnum.OPEN,
                    dedup_key=match.dedup_key,
                    verdict_source=resolved.source,
                    match_count=1,
                    last_seen_at=event_time,
                    last_event_id=event.id,
                    channels=[],
                    alert_metadata={
                        "rule_name": match.rule_name,
                        "matched_conditions": list(match.matched_conditions),
                        "recognised": list(resolved.recognised),
                    },
                )
                session.add(alert)
                await session.flush()
                await self._link_alert_event(session, alert.id, event.id, is_postgres=is_postgres)
                created_alerts.append(alert)
                notified = True
                planned_deliveries.extend(self._planner(alert, now=now, stale=is_stale))

        decided_by = matches[0].rule_name if matches else DEFAULT_RULE_ID
        await self._upsert_decision(
            session,
            event_id=event.id,
            notify=notified,
            decided_by=decided_by,
            now=now,
            is_postgres=is_postgres,
        )
        await self._write_deliveries_in_session(session, planned_deliveries)

        return PipelineResult(
            event_id=event.id,
            notify=notified,
            decided_by=decided_by,
            resolved=resolved,
            created_alerts=tuple(created_alerts),
            updated_alerts=tuple(updated_alerts),
            planned_deliveries=tuple(planned_deliveries),
            already_processed=False,
        )

    @staticmethod
    def _record_planned_deliveries_in_store(
        store: Any, planned_deliveries: list[Any], now: datetime
    ) -> None:
        """Memory path: append the planner's records to the store's history.

        The fake planners in tests return dicts; the real planner returns
        ``PlannedDelivery`` dataclasses — both are normalised to a dict with the
        fields the history read needs.
        """
        if not planned_deliveries:
            return
        for record in planned_deliveries:
            store.deliveries.append(_normalise_planned(record, now))

    async def _write_deliveries_in_session(
        self, session: AsyncSession, planned_deliveries: list[Any]
    ) -> None:
        """DB path: persist the planner's records inside the caller's transaction.

        The planner records may be dicts (tests) or ``PlannedDelivery``
        dataclasses (production). With no writer configured this is a no-op
        (B4.1 shape preserved).
        """
        if not planned_deliveries or self._delivery_writer is None:
            return
        await self._delivery_writer(session, planned_deliveries)

    @staticmethod
    async def _find_open_alert(
        session: AsyncSession,
        match: RuleMatch,
        event_time: datetime,
    ) -> Alert | None:
        cutoff = event_time - timedelta(seconds=match.cooldown_seconds)
        rule_cond = (
            Alert.rule_id == match.rule_id if match.rule_id is not None else Alert.rule_id.is_(None)
        )
        stmt = (
            select(Alert)
            .where(
                Alert.status == AlertStatusEnum.OPEN,
                Alert.dedup_key == match.dedup_key,
                rule_cond,
            )
            .order_by(Alert.last_seen_at.desc().nulls_last(), Alert.created_at.desc())
            .limit(1)
        )
        candidate = (await session.execute(stmt)).scalars().first()
        if candidate is None:
            return None
        ref_time = _ensure_utc(candidate.last_seen_at or candidate.created_at, event_time)
        if ref_time < cutoff:
            return None
        return candidate

    @staticmethod
    async def _link_alert_event(
        session: AsyncSession,
        alert_id: str,
        event_id: int,
        *,
        is_postgres: bool,
    ) -> None:
        if is_postgres:
            stmt = (
                pg_insert(AlertEvent)
                .values(alert_id=alert_id, event_id=event_id)
                .on_conflict_do_nothing(index_elements=["alert_id", "event_id"])
            )
            await session.execute(stmt)
        else:
            session.add(AlertEvent(alert_id=alert_id, event_id=event_id))
            await session.flush()

    @staticmethod
    async def _upsert_decision(
        session: AsyncSession,
        *,
        event_id: int,
        notify: bool,
        decided_by: str,
        now: datetime,
        is_postgres: bool,
    ) -> None:
        if is_postgres:
            stmt = (
                pg_insert(EventNotifyDecision)
                .values(
                    event_id=event_id,
                    notify=notify,
                    decided_by=decided_by,
                    created_at=now,
                )
                .on_conflict_do_update(
                    index_elements=["event_id"],
                    set_={
                        "notify": notify,
                        "decided_by": decided_by,
                        "created_at": now,
                    },
                )
            )
            await session.execute(stmt)
        else:
            session.add(
                EventNotifyDecision(
                    event_id=event_id,
                    notify=notify,
                    decided_by=decided_by,
                    created_at=now,
                )
            )
            await session.flush()

    @staticmethod
    async def _load_specialist_evidence(
        session: AsyncSession,
        *,
        camera_id: str,
        started_at: datetime,
        ended_at: datetime,
    ) -> SpecialistEvidence:
        window_start = started_at - timedelta(seconds=5)
        window_end = ended_at + timedelta(seconds=5)
        face_rows = list(
            (
                await session.execute(
                    select(FaceDetectionEvent)
                    .where(
                        FaceDetectionEvent.camera_id == camera_id,
                        FaceDetectionEvent.timestamp >= window_start,
                        FaceDetectionEvent.timestamp <= window_end,
                    )
                    .order_by(FaceDetectionEvent.id.asc())
                )
            )
            .scalars()
            .all()
        )
        if not face_rows:
            return SpecialistEvidence()

        person_ids = {r.matched_person_id for r in face_rows if r.matched_person_id is not None}
        persons_by_id: dict[int, KnownPerson] = {}
        auto_enrolled_person_ids: set[int] = set()
        if person_ids:
            persons = (
                (await session.execute(select(KnownPerson).where(KnownPerson.id.in_(person_ids))))
                .scalars()
                .all()
            )
            persons_by_id = {p.id: p for p in persons}

            auto_rows = (
                (
                    await session.execute(
                        select(EnrollmentCandidate.enrolled_person_id).where(
                            EnrollmentCandidate.enrolled_person_id.in_(person_ids),
                            EnrollmentCandidate.status == EnrollmentStatus.AUTO_ENROLLED.value,
                        )
                    )
                )
                .scalars()
                .all()
            )
            auto_enrolled_person_ids = {pid for pid in auto_rows if pid is not None}

        candidates: list[FaceCandidate] = []
        for fr in face_rows:
            if fr.is_unknown or fr.matched_person_id is None:
                candidates.append(FaceCandidate(is_unknown=True))
                continue
            person = persons_by_id.get(fr.matched_person_id)
            if person is None:
                candidates.append(FaceCandidate(is_unknown=True))
                continue
            is_auto = person.id in auto_enrolled_person_ids or bool(
                person.notes and "auto-enrolled" in person.notes.lower()
            )
            candidates.append(
                FaceCandidate(
                    person_name=person.name,
                    is_household_member=bool(person.is_household_member),
                    is_auto_enrolled=is_auto,
                    is_unknown=False,
                )
            )
        return SpecialistEvidence(faces=tuple(candidates))

    async def _publish_alerts(
        self,
        created_alerts: Sequence[Alert],
        updated_alerts: Sequence[Alert],
    ) -> set[str]:
        """Publish the alert frames; return the alert ids whose publish reached
        at least one client (or completed without a count — the frame went out).

        The pipeline marks the browser delivery rows ``broadcast`` for those
        ids once the publish returns (4n-alerting.md:115); a publish that
        reached nobody or raised leaves the rows ``pending`` for the worker's
        15 s republish ladder (F3).
        """
        if not created_alerts and not updated_alerts:
            return set()
        broadcaster = self._broadcaster
        if broadcaster is None:
            if self._redis is None:
                return set()
            try:
                from backend.services.event_broadcaster import get_broadcaster

                broadcaster = await get_broadcaster(self._redis)
            except Exception as exc:
                logger.warning(f"Failed to acquire broadcaster for alert publish: {exc}")
                return set()

        reached_ids: set[str] = set()
        for alert in created_alerts:
            try:
                reached = await broadcaster.broadcast_alert(
                    alert.to_dict(for_websocket=True),
                    WebSocketAlertEventType.ALERT_CREATED,
                )
                if reached is None or reached > 0:
                    reached_ids.add(str(alert.id))
            except Exception as exc:
                logger.warning(
                    "Failed to publish alert_created frame",
                    extra={"alert_id": alert.id, "error": str(exc)},
                )

        for alert in updated_alerts:
            try:
                reached = await broadcaster.broadcast_alert(
                    alert.to_dict(for_websocket=True),
                    WebSocketAlertEventType.ALERT_UPDATED,
                )
                if reached is None or reached > 0:
                    reached_ids.add(str(alert.id))
            except Exception as exc:
                logger.warning(
                    "Failed to publish alert_updated frame",
                    extra={"alert_id": alert.id, "error": str(exc)},
                )
        return reached_ids

    async def _mark_browser_rows_broadcast(self, alert_ids: set[str]) -> None:
        """Mark the alerts' pending browser delivery rows ``broadcast`` (B4.2).

        The pipeline publishes the browser channel's frame itself; once the
        publish reaches a client, its rows are done — the worker's republish
        ladder only exists for rows the publish missed. No-op without a
        session factory (the in-memory test path keeps no DB rows).
        """
        if not alert_ids or self._memory_store is not None:
            return
        async with self._session_factory() as session:
            await session.execute(
                # Internal SET-list, values bound; the ids are a bound array.
                text(  # nosemgrep: python.sqlalchemy.security.audit.avoid-sqlalchemy-text.avoid-sqlalchemy-text
                    "UPDATE notification_deliveries SET "
                    "status = 'broadcast', sent_at = timezone('utc', now()), "
                    "updated_at = timezone('utc', now()) "
                    "WHERE alert_id = ANY(:ids) AND kind = 'browser' AND status = 'pending'"
                ),
                {"ids": sorted(alert_ids)},
            )
            await session.commit()

    async def sweep_unprocessed(
        self,
        *,
        session: AsyncSession | None = None,
        now: datetime | None = None,
        upgrade_applied_at: datetime | None = None,
        limit: int = 100,
    ) -> list[PipelineResult]:
        """Re-run `process()` for every event without a notify decision whose
        verification was written after the alerting upgrade ran (oldest first, paged).
        """
        current_now = _ensure_utc(now, utc_now())
        if self._memory_store is not None:
            cutoff = _ensure_utc(upgrade_applied_at, datetime(2026, 1, 1, tzinfo=UTC))
            store = self._memory_store
            pending_verifs = sorted(
                (
                    v
                    for v in store.verifications
                    if v.event_id not in store.decisions
                    and _ensure_utc(v.created_at, current_now) >= cutoff
                ),
                key=lambda v: (_ensure_utc(v.created_at, current_now), v.event_id),
            )
            seen: set[int] = set()
            event_ids: list[int] = []
            for v in pending_verifs:
                if v.event_id not in seen:
                    seen.add(v.event_id)
                    event_ids.append(v.event_id)
                if len(event_ids) >= limit:
                    break
            return [await self.process(eid, now=current_now) for eid in event_ids]

        async def _query_ids(sess: AsyncSession) -> list[int]:
            cutoff = upgrade_applied_at
            if cutoff is None:
                try:
                    row = (
                        await sess.execute(
                            text("SELECT applied_at FROM schema_upgrades WHERE slug = :slug"),
                            {"slug": UPGRADE_SLUG_0012},
                        )
                    ).first()
                    if row and row[0] is not None:
                        cutoff = _ensure_utc(row[0], current_now)
                except Exception:
                    cutoff = None

            stmt = (
                select(EventVerification.event_id)
                .outerjoin(
                    EventNotifyDecision,
                    EventNotifyDecision.event_id == EventVerification.event_id,
                )
                .where(EventNotifyDecision.id.is_(None))
            )
            if cutoff is not None:
                stmt = stmt.where(EventVerification.created_at >= cutoff)
            stmt = stmt.order_by(
                EventVerification.created_at.asc(),
                EventVerification.id.asc(),
            ).limit(limit)
            rows = (await sess.execute(stmt)).scalars().all()
            return list(dict.fromkeys(rows))

        if session is not None:
            event_ids = await _query_ids(session)
            return [await self.process(eid, session=session, now=current_now) for eid in event_ids]

        async with self._session_factory() as owned_session:
            event_ids = await _query_ids(owned_session)
        return [await self.process(eid, now=current_now) for eid in event_ids]
