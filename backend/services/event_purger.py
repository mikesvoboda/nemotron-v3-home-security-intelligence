"""EventPurger: permanent deletion (purge) of soft-deleted events (B4.4).

Implements the Trash purger design in `docs/uplevel/4n-trash.md`:

1. Refuses any event not in Trash (`event.deleted_at is None`).
2. Collects detections linked to the purged events and to no surviving event.
3. Collects files: each event's `clip_path`, those detections' `thumbnail_path`s,
   and their `file_path`s that no surviving detection references.
4. Deletes the files, counting a missing file as deleted; if any deletion fails,
   leaves that event in Trash (`kept`), reports it, and lets the daily job retry.
5. In one transaction: deletes derived rows (`Entity` whose `primary_detection_id`
   is purged, `FaceDetectionEvent` on the event's camera within its start/end window),
   clears enrolled reference links (`PersonEmbedding.source_event_id`,
   `FaceEmbedding.source_image_path`), maintains alerts and `alert_events`
   (repointing to the earliest surviving event or removing the alert when no event
   is left), deletes detections and events, and writes a content-free audit entry.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal

from sqlalchemy import delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.core.database import get_session
from backend.core.logging import get_logger
from backend.models.alert import Alert, AlertEvent, AlertStatusEnum
from backend.models.audit import AuditAction
from backend.models.detection import Detection
from backend.models.entity import Entity
from backend.models.event import Event
from backend.models.event_detection import EventDetection
from backend.models.face_identity import FaceDetectionEvent, FaceEmbedding
from backend.models.household import PersonEmbedding
from backend.services.audit import AuditService

logger = get_logger(__name__)

PurgeReason = Literal["user", "trash_retention"]

_EMPTY_ROWS: dict[str, int] = {
    "events": 0,
    "detections": 0,
    "entities": 0,
    "face_detection_events": 0,
    "alerts": 0,
    "alert_events": 0,
    "deliveries": 0,
    "enrolled_references_unlinked": 0,
}


def purge_deadline_for_event(
    deleted_at: datetime,
    started_at: datetime,
    *,
    retention_days: int,
    trash_retention_days: int,
) -> datetime:
    """Return the timestamp at which a trashed event is due for purge.

    Purges at the earlier of `deleted_at + trash_retention_days` and
    `started_at + retention_days`. When `trash_retention_days <= 0`, the Trash
    clock is disabled and only `started_at + retention_days` applies.
    """
    retention_deadline = started_at + timedelta(days=retention_days)
    if trash_retention_days <= 0:
        return retention_deadline
    trash_deadline = deleted_at + timedelta(days=trash_retention_days)
    return min(trash_deadline, retention_deadline)


@dataclass(frozen=True)
class PurgeReport:
    """Report returned by EventPurger.purge."""

    purged: tuple[int, ...] = ()
    refused: tuple[int, ...] = ()
    kept: tuple[int, ...] = ()
    not_found: tuple[int, ...] = ()
    files_deleted: tuple[str, ...] = ()
    files_failed: tuple[str, ...] = ()
    rows_removed: dict[str, int] = field(default_factory=lambda: dict(_EMPTY_ROWS))


class EventPurger:
    """Service that permanently purges soft-deleted events and their derived data."""

    @staticmethod
    def _unlink_path(path_str: str) -> None:
        """Delete a file path, treating a missing file as already deleted."""
        path = Path(path_str)
        try:
            path.unlink()
        except FileNotFoundError:
            return

    async def purge(
        self,
        event_ids: Sequence[int],
        *,
        reason: PurgeReason = "user",
        session: AsyncSession | None = None,
        actor: str | None = None,
        request: Any = None,
    ) -> PurgeReport:
        """Purge trashed events and their exclusive detections, files, and derived rows."""
        ordered_ids = list(dict.fromkeys(int(eid) for eid in event_ids))
        if not ordered_ids:
            return PurgeReport()

        if session is None:
            async with get_session() as own_session:
                report = await self._purge_in_session(
                    own_session,
                    ordered_ids,
                    reason=reason,
                    actor=actor,
                    request=request,
                )
                await own_session.commit()
                return report

        return await self._purge_in_session(
            session,
            ordered_ids,
            reason=reason,
            actor=actor,
            request=request,
        )

    async def _purge_in_session(
        self,
        session: AsyncSession,
        ordered_ids: list[int],
        *,
        reason: PurgeReason,
        actor: str | None,
        request: Any,
    ) -> PurgeReport:
        stmt = (
            select(Event).options(selectinload(Event.detections)).where(Event.id.in_(ordered_ids))
        )
        events = list((await session.execute(stmt)).scalars().all())
        events_by_id = {ev.id: ev for ev in events}

        not_found: list[int] = []
        refused: list[int] = []
        candidates: list[Event] = []

        for eid in ordered_ids:
            ev = events_by_id.get(eid)
            if ev is None:
                not_found.append(eid)
            elif ev.deleted_at is None:
                refused.append(eid)
            else:
                candidates.append(ev)

        if not candidates:
            return PurgeReport(
                purged=(),
                refused=tuple(refused),
                kept=(),
                not_found=tuple(not_found),
                files_deleted=(),
                files_failed=(),
                rows_removed=dict(_EMPTY_ROWS),
            )

        candidate_ids = {ev.id for ev in candidates}

        # Step 2: Collect detections linked to candidate events and check surviving links
        link_rows = (
            await session.execute(
                select(EventDetection.event_id, EventDetection.detection_id).where(
                    EventDetection.event_id.in_(candidate_ids)
                )
            )
        ).all()

        event_to_det_ids: dict[int, set[int]] = {ev.id: set() for ev in candidates}
        for ev in candidates:
            for det in ev.detections:
                event_to_det_ids[ev.id].add(det.id)
        for ev_id, det_id in link_rows:
            event_to_det_ids.setdefault(ev_id, set()).add(det_id)

        all_candidate_det_ids = {
            det_id for det_ids in event_to_det_ids.values() for det_id in det_ids
        }

        shared_with_outside_det_ids: set[int] = set()
        if all_candidate_det_ids:
            outside_rows = list(
                (
                    await session.execute(
                        select(EventDetection.detection_id).where(
                            EventDetection.detection_id.in_(all_candidate_det_ids),
                            EventDetection.event_id.notin_(candidate_ids),
                        )
                    )
                )
                .scalars()
                .all()
            )
            shared_with_outside_det_ids = set(outside_rows)

        candidate_purge_det_ids = all_candidate_det_ids - shared_with_outside_det_ids

        dets_by_id: dict[int, Detection] = {}
        if candidate_purge_det_ids:
            det_objs = list(
                (
                    await session.execute(
                        select(Detection).where(Detection.id.in_(candidate_purge_det_ids))
                    )
                )
                .scalars()
                .all()
            )
            dets_by_id = {d.id: d for d in det_objs}

        # Step 3: Find which clip_paths, thumbnail_paths, and file_paths are used by surviving rows
        candidate_clips = {ev.clip_path for ev in candidates if ev.clip_path}
        surviving_clips: set[str] = set()
        if candidate_clips:
            surviving_clips = set(
                (
                    await session.execute(
                        select(Event.clip_path).where(
                            Event.id.notin_(candidate_ids),
                            Event.clip_path.in_(candidate_clips),
                        )
                    )
                )
                .scalars()
                .all()  # type: ignore[arg-type]
            )

        candidate_thumbs = {d.thumbnail_path for d in dets_by_id.values() if d.thumbnail_path}
        surviving_thumbs: set[str] = set()
        if candidate_thumbs:
            surviving_thumbs = set(
                (
                    await session.execute(
                        select(Detection.thumbnail_path).where(
                            Detection.id.notin_(candidate_purge_det_ids),
                            Detection.thumbnail_path.in_(candidate_thumbs),
                        )
                    )
                )
                .scalars()
                .all()  # type: ignore[arg-type]
            )

        candidate_files = {d.file_path for d in dets_by_id.values() if d.file_path}
        surviving_files: set[str] = set()
        if candidate_files:
            surviving_files = set(
                (
                    await session.execute(
                        select(Detection.file_path).where(
                            Detection.id.notin_(candidate_purge_det_ids),
                            Detection.file_path.in_(candidate_files),
                        )
                    )
                )
                .scalars()
                .all()  # type: ignore[arg-type]
            )

        # Step 4: Delete files per event; if any deletion fails for an event, leave that event in Trash
        files_deleted: list[str] = []
        files_failed: list[str] = []
        deleted_set: set[str] = set()
        failed_set: set[str] = set()
        purged_events: list[Event] = []
        kept_ids: list[int] = []

        for ev in candidates:
            ev_paths: list[str] = []
            if ev.clip_path and ev.clip_path not in surviving_clips:
                ev_paths.append(ev.clip_path)
            for det_id in sorted(event_to_det_ids.get(ev.id, ())):
                det_obj = dets_by_id.get(det_id)
                if det_obj is None:
                    continue
                if det_obj.thumbnail_path and det_obj.thumbnail_path not in surviving_thumbs:
                    ev_paths.append(det_obj.thumbnail_path)
                if det_obj.file_path and det_obj.file_path not in surviving_files:
                    ev_paths.append(det_obj.file_path)

            ev_failed = False
            for path_str in dict.fromkeys(ev_paths):
                if path_str in deleted_set:
                    continue
                if path_str in failed_set:
                    ev_failed = True
                    continue
                try:
                    self._unlink_path(path_str)
                    deleted_set.add(path_str)
                    files_deleted.append(path_str)
                except OSError as exc:
                    logger.warning(
                        f"Failed to delete file {path_str} while purging event {ev.id}: {exc}"
                    )
                    failed_set.add(path_str)
                    files_failed.append(path_str)
                    ev_failed = True

            if ev_failed:
                kept_ids.append(ev.id)
            else:
                purged_events.append(ev)

        rows_removed = dict(_EMPTY_ROWS)
        if not purged_events:
            return PurgeReport(
                purged=(),
                refused=tuple(refused),
                kept=tuple(kept_ids),
                not_found=tuple(not_found),
                files_deleted=tuple(files_deleted),
                files_failed=tuple(files_failed),
                rows_removed=rows_removed,
            )

        purged_ids = [ev.id for ev in purged_events]
        purged_id_set = set(purged_ids)
        kept_det_ids = {det_id for eid in kept_ids for det_id in event_to_det_ids.get(eid, ())}
        final_purge_det_ids = sorted(
            {det_id for eid in purged_ids for det_id in event_to_det_ids.get(eid, ())}
            - shared_with_outside_det_ids
            - kept_det_ids
        )

        # Step 5a: Delete derived rows (Entity and legacy FaceDetectionEvent)
        if final_purge_det_ids:
            ent_res = await session.execute(
                delete(Entity).where(Entity.primary_detection_id.in_(final_purge_det_ids))
            )
            rows_removed["entities"] = int(ent_res.rowcount or 0)  # type: ignore[attr-defined]

        face_events_removed = 0
        for ev in purged_events:
            win_start = ev.started_at
            win_end = ev.ended_at if ev.ended_at is not None else ev.started_at
            face_res = await session.execute(
                delete(FaceDetectionEvent).where(
                    FaceDetectionEvent.camera_id == ev.camera_id,
                    FaceDetectionEvent.timestamp >= win_start,
                    FaceDetectionEvent.timestamp <= win_end,
                )
            )
            face_events_removed += int(face_res.rowcount or 0)  # type: ignore[attr-defined]
        rows_removed["face_detection_events"] = face_events_removed

        # Step 5b: Clear enrolled reference links without deleting enrolled embeddings
        unlinked_count = 0
        pe_res = await session.execute(
            update(PersonEmbedding)
            .where(PersonEmbedding.source_event_id.in_(purged_id_set))
            .values(source_event_id=None)
        )
        unlinked_count += int(pe_res.rowcount or 0)  # type: ignore[attr-defined]

        if files_deleted:
            fe_res = await session.execute(
                update(FaceEmbedding)
                .where(FaceEmbedding.source_image_path.in_(files_deleted))
                .values(source_image_path=None)
            )
            unlinked_count += int(fe_res.rowcount or 0)  # type: ignore[attr-defined]
        rows_removed["enrolled_references_unlinked"] = unlinked_count

        # Step 5c: Maintain alerts and alert_events before deleting Event rows
        (
            alerts_removed,
            alert_events_removed,
            deliveries_removed,
        ) = await self._maintain_alerts_on_purge(session, purged_id_set)
        rows_removed["alerts"] = alerts_removed
        rows_removed["alert_events"] = alert_events_removed
        rows_removed["deliveries"] = deliveries_removed

        # Step 5d: Delete event_detections, detections, and events
        await session.execute(
            delete(EventDetection).where(EventDetection.event_id.in_(purged_id_set))
        )
        if final_purge_det_ids:
            det_res = await session.execute(
                delete(Detection).where(Detection.id.in_(final_purge_det_ids))
            )
            rows_removed["detections"] = int(det_res.rowcount or 0)  # type: ignore[attr-defined]

        ev_res = await session.execute(delete(Event).where(Event.id.in_(purged_id_set)))
        rows_removed["events"] = int(ev_res.rowcount or 0)  # type: ignore[attr-defined]

        # Step 5e: Write content-free audit log entries
        resolved_actor = (
            actor if actor is not None else ("system" if reason == "trash_retention" else None)
        )
        for eid in purged_ids:
            await AuditService.log_action(
                db=session,
                action=AuditAction.EVENT_PURGED,
                resource_type="event",
                resource_id=str(eid),
                actor=resolved_actor,
                details={"event_id": eid, "reason": reason},
                request=request,
            )

        await session.flush()

        return PurgeReport(
            purged=tuple(purged_ids),
            refused=tuple(refused),
            kept=tuple(kept_ids),
            not_found=tuple(not_found),
            files_deleted=tuple(files_deleted),
            files_failed=tuple(files_failed),
            rows_removed=rows_removed,
        )

    async def _maintain_alerts_on_purge(
        self,
        session: AsyncSession,
        purged_id_set: set[int],
    ) -> tuple[int, int, int]:
        """Repoint folded alerts to surviving events or remove alerts with no events left."""
        affected_alerts = list(
            (
                await session.execute(
                    select(Alert)
                    .options(selectinload(Alert.alert_events))
                    .where(
                        or_(
                            Alert.event_id.in_(purged_id_set),
                            Alert.last_event_id.in_(purged_id_set),
                            Alert.id.in_(
                                select(AlertEvent.alert_id).where(
                                    AlertEvent.event_id.in_(purged_id_set)
                                )
                            ),
                        )
                    )
                )
            )
            .scalars()
            .all()
        )

        if not affected_alerts:
            return 0, 0, 0

        ae_del = await session.execute(
            delete(AlertEvent).where(AlertEvent.event_id.in_(purged_id_set))
        )
        alert_events_removed = int(ae_del.rowcount or 0)  # type: ignore[attr-defined]

        alerts_to_delete: list[str] = []
        for alert in affected_alerts:
            covered_ids = {ae.event_id for ae in alert.alert_events} | {alert.event_id}
            if alert.last_event_id is not None:
                covered_ids.add(alert.last_event_id)
            surviving_ids = covered_ids - purged_id_set

            if not surviving_ids:
                alerts_to_delete.append(alert.id)
                continue

            surviving_events = list(
                (
                    await session.execute(
                        select(Event)
                        .where(Event.id.in_(surviving_ids))
                        .order_by(Event.started_at.asc(), Event.id.asc())
                    )
                )
                .scalars()
                .all()
            )

            if not surviving_events:
                alerts_to_delete.append(alert.id)
                continue

            earliest = surviving_events[0]
            latest = surviving_events[-1]
            alert.event_id = earliest.id
            alert.last_event_id = latest.id
            alert.last_seen_at = latest.started_at
            alert.match_count = len(surviving_events)

            if all(ev.deleted_at is not None for ev in surviving_events):
                alert.status = AlertStatusEnum.DISMISSED
                meta = dict(alert.alert_metadata) if isinstance(alert.alert_metadata, dict) else {}
                meta["dismissed_reason"] = "events moved to Trash"
                alert.alert_metadata = meta

        # Flush repointed alerts before deleting Event rows so ON DELETE CASCADE on alerts.event_id
        # does not delete a repointed alert.
        await session.flush()

        alerts_removed = 0
        deliveries_removed = 0
        if alerts_to_delete:
            deliveries_removed = await self._delete_deliveries_if_present(session, alerts_to_delete)
            al_del = await session.execute(delete(Alert).where(Alert.id.in_(alerts_to_delete)))
            alerts_removed = int(al_del.rowcount or 0)  # type: ignore[attr-defined]

        return alerts_removed, alert_events_removed, deliveries_removed

    @staticmethod
    async def _delete_deliveries_if_present(
        session: AsyncSession,
        alert_ids: list[str],
    ) -> int:
        """Delete notification_deliveries rows if the table exists (B4.2 compatibility)."""
        from backend.models.alert_delivery import NotificationDelivery

        try:
            async with session.begin_nested():
                # `delete()` + `in_()`, NOT `text("... IN :param")` with a tuple: text()
                # binds one scalar per name, so Postgres received `IN $1` (a bare parameter
                # in a list position) and answered `syntax error at or near "$1"` on every
                # purge -- feature-check run 39901062658, compose.log 04:42:02, three times.
                # The try/except below then swallowed it and purge "succeeded" while every
                # delivery row survived. `in_()` is the expanding binding the query needs;
                # the exception path keeps guarding only the table-may-not-exist case.
                res = await session.execute(
                    delete(NotificationDelivery).where(NotificationDelivery.alert_id.in_(alert_ids))
                )
                return int(res.rowcount or 0)  # type: ignore[attr-defined]
        except Exception:
            return 0
