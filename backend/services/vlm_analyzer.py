"""The vlm-mode analysis entry point (Phase 1.3, spec §2:100, §6 ladder).

A SIBLING of `nemotron_analyzer`, deliberately not a mode inside it: the
legacy path is unsupported (spec rev 5, ledger F10) and stays byte-identical
until R8 deletes it, so the vlm path gets its own file instead of a flag
branch inside 5000 lines of legacy machinery.

What this module owns (spec §6, in the order the rules apply):

  1. ONE AssessInput builder (`build_assess_context`) shared by production
     (values read from DB rows in session 1) and replay (2.1, values loaded
     from the eval store) - the "one code path" rule; the builder never
     touches an ORM object, only plain dicts.
  2. The invariant table (`apply_verdict_invariants`): rejected clamps the
     score to <= SeverityService.low_max (spec §6 - "the verdict gates
     alerts, the score still ranks"; the clamp and its reason are visible in
     the stored reasoning), uncertain KEEPS its score (§6:145 - uncertain is
     not rejected), the level is ALWAYS derived by SeverityService (the
     model never emits one - §3 Derived row), and a verification failure
     scores NULL with the event row still written (spec §6:320-323 - the
     event exists precisely so the UI shows "needs review").
  3. The ladder's tail: vlm_client already owns the ONE transport retry at
     temperature 0 (pinned in test_vlm_client.TestFailureLadder); when it
     still raises, this module maps the failure to verification_failed +
     the EventVerification row - it never re-retries (a second retry would
     double the S4 p95 budget a single call already fits).
  4. The VLM NEVER originates an event: the detector closing a batch is
     what puts camera/detections into Redis (batch_aggregator.close_batch)
     or into the queue payload; absent both, analyze_batch refuses loudly
     with zero writes.

Session doctrine mirrors nemotron's (split sessions, :2642-2650): session 1
READ (camera/detections/zones/household), NO session across the VLM call
(it can take the whole 25 s read budget), session 2 WRITE - Event and
EventVerification in the SAME transaction, the idempotency key AFTER the
write, and the broadcast LAST, best-effort: a broadcast failure never
un-does the committed event (the WS consumer catches up from the DB).

The WS payload carries the P0.4 `verification` key (rendered by
backend/api.schemas.event_verification.verification_payload from the rows
this module just wrote - EventVerification is async-expunged once its
session closes, so the payload is built INSIDE session 2 and published
after it); replay mode never broadcasts (spec §5: the replay loop drives
the eval store, not the console).
"""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.event_verification import verification_payload
from backend.core.config import get_settings
from backend.core.database import get_session
from backend.core.logging import get_logger
from backend.core.metrics import record_pipeline_error
from backend.models.detection import Detection
from backend.models.event import Event
from backend.models.event_detection import event_detections
from backend.models.event_verification import EventVerification
from backend.services.key_frame_selector import FrameRef, select_key_frames
from backend.services.nemotron_analyzer import ConstrainedDecodingNotEnforced
from backend.services.severity import SeverityService, get_severity_service
from backend.services.vlm_client import VlmClient, VlmClientError
from backend.services.vlm_specialists import collect_specialist_outputs
from backend.services.vlm_verdict import VlmAssessContext, VlmAssessRequest, VlmVerdict
from backend.services.zone_service import get_zones_for_detection

logger = get_logger(__name__)

# The failure classes that map to §6 step 2 (verification_failed + NULL):
# every raise vlm_client documents, plus its probe error. Anything else is
# a bug and propagates LOUD - the ladder covers engine failures, not
# programming errors.
_DEGRADABLE_ERRORS: tuple[type[BaseException], ...] = (
    VlmClientError,
    ConstrainedDecodingNotEnforced,
)

# Idempotency TTL, mirroring nemotron's _set_idempotency (batch_event:<id>).
_IDEMPOTENCY_TTL_SECONDS = 3600


# ---------------------------------------------------------------------------
# Pure builders (the ONE code path: production rows and replay store rows
# both arrive here as plain dicts; the builder never touches an ORM object)
# ---------------------------------------------------------------------------


def build_assess_context(
    *,
    camera_id: str,
    detections: list[dict[str, Any]],
    zones: list[str] | None = None,
    household: dict[str, Any] | None = None,
    zone_crossing: bool = False,
    specialist_outputs: dict[str, str] | None = None,
) -> VlmAssessContext:
    """Field-for-field AssessInput (spec §5 / G0.4 - the shape pin lives in
    scripts/test_gen_ai_contract.py; this function is that pin's runtime
    half). Detection rows are normalized to the frozen store's keys
    (control_freeze._build_snapshot: id/object_type/confidence/bbox/
    detected_at) so a production-built snapshot and an eval-store snapshot
    are the SAME shape - the corpus stays comparable with what 2.1 replays.

    Timestamp: ISO of the EARLIEST detected_at (the snapshot's moment);
    already-string values (store rows) pass through untouched."""
    det_rows = []
    for row in detections:
        det = row.get("detected_at")
        bbox = row.get("bbox")
        if bbox is None:
            bbox = [
                row.get("bbox_x"),
                row.get("bbox_y"),
                row.get("bbox_width"),
                row.get("bbox_height"),
            ]
        det_rows.append(
            {
                "id": row["id"],
                "object_type": row.get("object_type"),
                "confidence": row.get("confidence"),
                "bbox": bbox,
                "detected_at": det.isoformat() if isinstance(det, datetime) else det,
            }
        )

    times = [r["detected_at"] for r in det_rows if r["detected_at"]]
    timestamp = min(times) if times else datetime.now(UTC).isoformat()

    return VlmAssessContext(
        camera_id=camera_id,
        detections=det_rows,
        zones=list(zones or []),
        zone_crossing=zone_crossing,
        household=dict(household or {}),
        timestamp=timestamp,
        # Rev 6 (F11 ruling 4): the snapshot is the ONE carrier of the
        # specialist texts — production fills them, replay loads them from
        # the store, and the request copies them out of the context below.
        specialist_outputs=dict(specialist_outputs or {}),
    )


def detect_zone_crossing(
    detections: list[dict[str, Any]],
    zone_names_by_detection_id: dict[int, list[str]],
) -> bool:
    """The crossing signal the rows actually carry: one track (track_id)
    seen in two DIFFERENT zone memberships. No track ids or no zone
    memberships -> honest False, never a guess (zone_crossing_service
    owns the stateful enter/exit events; the analyzer only reports what
    THIS batch's rows show)."""
    memberships: dict[Any, set[str]] = {}
    for row in detections:
        track = row.get("track_id")
        if track is None:
            continue
        names = zone_names_by_detection_id.get(row["id"]) or []
        if names:
            memberships.setdefault(track, set()).update(names)
    return any(len(names) > 1 for names in memberships.values())


def build_frame_refs(detections: list[dict[str, Any]], camera_id: str) -> list[FrameRef]:
    """Detection dicts -> FrameRefs (paths only, never bytes; spec §6).
    One helper so the request's key-frame pick and the specialist stage run
    the SAME selector over the SAME picks — the texts describe exactly the
    frames the VLM sees, never a different frame set."""
    frames = []
    for row in detections:
        det = row.get("detected_at")
        epoch = int(det.timestamp()) if isinstance(det, datetime) else 0
        frames.append(
            FrameRef(
                detection_id=row["id"],
                camera_id=row.get("camera_id") or camera_id,
                object_type=row.get("object_type") or "unknown",
                confidence=row.get("confidence"),
                timestamp=epoch,
                file_path=row["file_path"],
                thumbnail_path=row.get("thumbnail_path"),
            )
        )
    return frames


def build_assess_request(
    *,
    context: VlmAssessContext,
    detections: list[dict[str, Any]],
) -> VlmAssessRequest:
    """The VlmAssessRequest: context plus 1-4 key frames (the selector's
    pick over FrameRefs built from the same dicts - paths only, never
    bytes; spec §6 privacy). The specialist texts already live inside the
    context — the request adds only the image selection (rev 6)."""
    picks = select_key_frames(build_frame_refs(detections, context.camera_id))
    return VlmAssessRequest(image_paths=[f.file_path for f in picks], context=context)


def _key_frame_ids(request: VlmAssessRequest, detections: list[dict[str, Any]]) -> list[int]:
    """Map the request's chosen paths back to detection ids for the
    provenance row (spec §4: the UI resolves them to existing thumbnails)."""
    by_path = {row["file_path"]: row["id"] for row in detections}
    return [by_path[p] for p in request.image_paths if p in by_path]


def apply_verdict_invariants(
    verdict: VlmVerdict | None,
    severity: SeverityService,
) -> dict[str, Any]:
    """The §6 rule table, as data - pinned row by row by
    test_vlm_analyzer.TestVerdictInvariants.

    verdict=None means the ladder bottomed out (transport/schema/probe
    failure): score and level are NULL (D11), summary/reasoning are honest
    text - the event row still gets written so the UI shows "needs
    review" (spec §6:320-323)."""
    if verdict is None:
        return {
            "verdict": "verification_failed",
            "risk_score": None,
            "risk_level": None,
            "summary": "VLM verification failed; this event needs review.",
            "reasoning": (
                "The VLM could not produce a valid verdict within the §6 "
                "budget (transport or schema failure after one retry at "
                "temperature 0). Score and level are NULL by design - never "
                "a fabricated low score."
            ),
            "description": "",
            "criteria": None,
        }

    risk_score: int | None = verdict.risk_score
    reasoning = verdict.reasoning
    if verdict.verdict == "rejected":
        # "the verdict gates alerts, the score still ranks" (spec §6): a
        # rejected verdict may not present above the LOW band. Clamp, and
        # leave the clamp VISIBLE in the stored reasoning ("log the clamp").
        if risk_score is not None and risk_score > severity.low_max:
            reasoning = (
                f"{reasoning} [§6: verdict 'rejected' clamped to <= "
                f"{severity.low_max} (was {risk_score})]"
            )
            risk_score = severity.low_max

    risk_level = (
        severity.risk_score_to_severity(risk_score).value if risk_score is not None else None
    )
    return {
        "verdict": verdict.verdict,
        "risk_score": risk_score,
        "risk_level": risk_level,
        "summary": verdict.summary,
        "reasoning": reasoning,
        "description": verdict.description,
        "criteria": [c.model_dump() for c in verdict.criteria],
    }


async def load_household_context(session: AsyncSession, camera_id: str) -> dict[str, Any]:
    """Zone household configs for the camera's zones, keyed by zone id.
    Honest-absent on any failure (spec §5: the snapshot claims nothing it
    could not read) - the assessment must not die over a context add-on."""
    try:
        from backend.models.zone import Zone
        from backend.models.zone_household_config import ZoneHouseholdConfig

        result = await session.execute(
            select(ZoneHouseholdConfig, Zone)
            .join(Zone, Zone.id == ZoneHouseholdConfig.zone_id)
            .where(Zone.camera_id == camera_id)
        )
        context: dict[str, Any] = {}
        for config, zone in result.all():
            context[zone.id] = {
                "zone": zone.name,
                "owner_id": config.owner_id,
                "allowed_member_ids": list(config.allowed_member_ids or []),
                "allowed_vehicle_ids": list(config.allowed_vehicle_ids or []),
            }
        return context
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning(
            "household context unavailable (assessing without it)",
            extra={"camera_id": camera_id, "error": str(exc)},
        )
        return {}


# ---------------------------------------------------------------------------
# The analyzer
# ---------------------------------------------------------------------------


class VlmAnalyzer:
    """One analyze_batch call == one batch -> (at most) one assess ->
    one Event (+ EventVerification) -> one broadcast (prod mode).

    `replay=True` (2.1 wires it) runs the identical pipeline but never
    broadcasts: the replay loop feeds the eval store, not the console."""

    def __init__(
        self,
        vlm_client: VlmClient | None = None,
        redis_client: Any | None = None,
        *,
        severity: SeverityService | None = None,
        replay: bool = False,
    ) -> None:
        self._client = vlm_client
        self._redis = redis_client
        self._severity = severity or get_severity_service()
        self._replay = replay
        settings = get_settings()
        self._settings = settings
        # Degraded-path provenance: a failed call has no verdict to read
        # the engine's own label from, so the settings labels stand in (the
        # event_verifications columns are NOT NULL). Same source nemotron
        # uses (:501-502); engine stays the shipped "llama.cpp" label, the
        # model id joins it env-first next to the VLM_URL settings (1.3).
        self._fallback_engine = settings.nemotron_verification_engine
        self._fallback_model_id = settings.vlm_model_id

    def _get_client(self) -> VlmClient:
        # Lazy: construction never opens an httpx client (the batch worker
        # builds one per worker; close() after each call releases it).
        if self._client is None:
            self._client = VlmClient()
        return self._client

    async def analyze_batch(
        self,
        batch_id: str,
        camera_id: str | None = None,
        detection_ids: list[int | str] | None = None,
        *,
        specialist_inputs: dict[str, str] | None = None,
    ) -> Event:
        """Analyze one closed batch. Raises ValueError when the batch has
        no detections, or when NO detector closed it (no camera metadata in
        Redis and no queue-payload camera - the §6 "VLM never originates an
        event" rule). Raises nothing for ENGINE failures: those land as a
        verification_failed event (§6 step 2).

        ``specialist_inputs`` is replay's carrier (2.1): the stored texts
        from the eval store's snapshot, passed through to AssessInput
        verbatim. Production never passes it - it computes the texts
        itself. Replay never re-runs the specialists either way (F11
        ruling 4): the texts a verdict was judged on are the texts that
        rode the snapshot, or the comparison is a different scene."""
        # Idempotency first (nemotron's batch_event:<id> key, same TTL).
        existing_id = await self._check_idempotency(batch_id)
        if existing_id is not None:
            async with get_session() as session:
                existing = await session.execute(select(Event).where(Event.id == existing_id))
                event = existing.scalars().first()
            if event is not None:
                logger.info(
                    "vlm idempotency hit: batch already analyzed",
                    extra={"batch_id": batch_id, "event_id": existing_id},
                )
                return event

        # Resolve batch identity. The queue payload carries camera+detection
        # ids; the Redis fallback mirrors nemotron (:2683-2693) - close_batch
        # wrote both. No camera from EITHER source means no detector ever
        # closed this batch: refuse loud, zero writes.
        if camera_id is None and self._redis is not None:
            camera_id = await self._redis.get(f"batch:{batch_id}:camera_id")
        if not camera_id:
            raise ValueError(
                f"Batch {batch_id} has no camera metadata - the detector never "
                "closed it; the VLM never originates events (spec §6)"
            )
        if detection_ids is None and self._redis is not None:
            raw = await self._redis.get(f"batch:{batch_id}:detections")
            detection_ids = json.loads(raw) if raw else []
        if not detection_ids:
            raise ValueError(f"Batch {batch_id} has no detections")
        try:
            int_ids = [int(d) for d in detection_ids]
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid detection_id in batch {batch_id}: {exc}") from None

        # ---------------- SESSION 1 (READ) --------------------------------
        # NOTE: the Camera row is deliberately NOT loaded - the frozen
        # AssessInput shape (§5, field-set pinned in 1.1) carries camera_id,
        # not camera name, so a name read here would be a dead query
        # (nemotron's prompt dict carries camera.name; this path's prompt is
        # rendered from AssessInput fields only).
        zones: list[str] = []
        zone_names_by_det: dict[int, list[str]] = {}
        household: dict[str, Any] = {}
        async with get_session() as session:
            det_result = await session.execute(select(Detection).where(Detection.id.in_(int_ids)))
            rows = det_result.scalars().all()
            if not rows:
                raise ValueError(f"No detections found for batch {batch_id}")

            detections: list[dict[str, Any]] = [
                {
                    "id": d.id,
                    "camera_id": d.camera_id,
                    "object_type": d.object_type,
                    "confidence": d.confidence,
                    "detected_at": d.detected_at,
                    "file_path": d.file_path,
                    "thumbnail_path": d.thumbnail_path,
                    "track_id": d.track_id,
                    "bbox_x": d.bbox_x,
                    "bbox_y": d.bbox_y,
                    "bbox_width": d.bbox_width,
                    "bbox_height": d.bbox_height,
                    "video_width": d.video_width,
                    "video_height": d.video_height,
                }
                for d in rows
            ]

            # Zones: which enabled zones the batch's detections sit in
            # (zone_service.get_zones_for_detection is the shipped geometry
            # - center-point membership, same rule the zone features use;
            # module-level import so the test seam patches it here).
            zone_ids: set[str] = set()
            for det in detections:
                if det.get("bbox_x") is None or det.get("video_width") is None:
                    continue
                matched = await get_zones_for_detection(
                    camera_id,
                    det["bbox_x"],
                    det["bbox_y"],
                    det["bbox_width"],
                    det["bbox_height"],
                    det["video_width"],
                    det["video_height"],
                    session,
                )
                if matched:
                    zone_names_by_det[det["id"]] = [z.name for z in matched]
                    zone_ids.update(z.id for z in matched)
            zones = sorted({n for names in zone_names_by_det.values() for n in names})
            household = await load_household_context(session, camera_id)

            # ---- Specialist stage (rev 6, F11/F12): ONE short text per
            # specialist over the selector's key-frame picks, BEFORE the
            # assess call. Runs inside session 1 because the face leg needs
            # it for the gallery read; the leg itself never raises (every
            # failure is the text "unavailable"), so this cannot extend the
            # read budget or fail the batch. Replay NEVER re-runs the
            # specialists (F11 ruling 4): replay feeds the texts loaded from
            # the eval store, so this whole block is prod-only.
            if self._replay:
                specialist_outputs: dict[str, str] = dict(specialist_inputs or {})
            else:
                try:
                    specialist_outputs = await collect_specialist_outputs(
                        key_frame_paths=select_key_frames(build_frame_refs(detections, camera_id)),
                        settings=self._settings,
                        detections=detections,
                        session=session,
                    )
                except Exception as exc:
                    # The stage's own contract is "never raise"; this catch is
                    # the analyzer's own guarantee (plan 3b: a failing or
                    # absent specialist never blocks or fails the verdict),
                    # so even a stage BUG lands as all-unavailable texts on
                    # the same keys, not a lost event.
                    logger.warning(
                        "specialist stage raised (belt catch) - all specialists unavailable",
                        extra={"batch_id": batch_id, "error": str(exc)},
                    )
                    specialist_outputs = dict.fromkeys(
                        ("faces", "plates", "person_reid"), "unavailable: specialist stage error"
                    )

        start_time = min(
            (d["detected_at"] for d in detections if d.get("detected_at") is not None),
            default=datetime.now(UTC),
        )
        end_time = max(
            (d["detected_at"] for d in detections if d.get("detected_at") is not None),
            default=start_time,
        )

        context = build_assess_context(
            camera_id=camera_id,
            detections=detections,
            zones=zones,
            household=household,
            zone_crossing=detect_zone_crossing(detections, zone_names_by_det),
            specialist_outputs=specialist_outputs,
        )
        request = build_assess_request(context=context, detections=detections)
        key_frame_ids = _key_frame_ids(request, detections)

        # ---------------- NO SESSION (external call) ---------------------
        client = self._get_client()
        prompt_text = client.prompt_text(request)
        started = time.monotonic()
        verdict: VlmVerdict | None = None
        try:
            verdict = await client.assess(request)
        except _DEGRADABLE_ERRORS as exc:
            # §6 step 2: the client's retry already burned; map to the
            # degraded row, never propagate the ladder here.
            record_pipeline_error("vlm_verification_failed")
            logger.warning(
                "vlm assess failed - event records verification_failed",
                extra={"batch_id": batch_id, "camera_id": camera_id, "error": str(exc)},
            )
        finally:
            await client.close()  # per-call httpx lifecycle (nemotron's shape)
        latency_ms = int((time.monotonic() - started) * 1000)

        outcome = apply_verdict_invariants(verdict, self._severity)
        degraded = verdict is None

        # ---------------- SESSION 2 (WRITE) ------------------------------
        async with get_session() as session:
            event = Event(
                batch_id=batch_id,
                camera_id=camera_id,
                started_at=start_time,
                ended_at=end_time,
                risk_score=outcome["risk_score"],
                risk_level=outcome["risk_level"],
                summary=outcome["summary"],
                reasoning=outcome["reasoning"],
                # Paths, never bytes (D10): the prompt text plus the key
                # frames the model was actually shown.
                llm_prompt=f"{prompt_text}\nKEY FRAMES: {request.image_paths}",
                reviewed=False,
            )
            session.add(event)
            await session.flush()

            if verdict is not None:
                engine, model_id = verdict.provenance.engine, verdict.provenance.model_id
            else:
                engine, model_id = self._fallback_engine, self._fallback_model_id
            row = EventVerification(
                event_id=event.id,
                verdict=outcome["verdict"],
                scene_description=outcome["description"] or None,
                criteria=outcome["criteria"],
                key_frame_detection_ids=key_frame_ids,
                engine=engine,
                model_id=model_id,
                # honest latency: the attempt happened; None only if it
                # never reached the transport (degraded pre-call errors).
                latency_ms=latency_ms,
            )
            session.add(row)
            await session.flush()

            # Event<->detection junction (same ON CONFLICT shape as
            # nemotron :3268, so a coalesced/re-run batch cannot double).
            from sqlalchemy.dialects.postgresql import insert as pg_insert

            values = [{"event_id": event.id, "detection_id": det_id} for det_id in int_ids]
            stmt = (
                pg_insert(event_detections)
                .values(values)
                .on_conflict_do_nothing(index_elements=["event_id", "detection_id"])
            )
            await session.execute(stmt)

            # The WS `verification` key must render BEFORE the session
            # closes: EventVerification is async-expunged at session exit,
            # so the newest-row read verification_payload performs needs
            # THIS session. (A DB-level load, no relationship lazy.)
            vrow_result = await session.execute(
                select(EventVerification).where(EventVerification.event_id == event.id)
            )
            payload = verification_payload(
                _EventView(event_id=event.id, rows=list(vrow_result.scalars().all()))
            )
            verification_json = payload.model_dump(mode="json") if payload is not None else None

        # Idempotency AFTER the write (a crash before this line just means
        # a retry re-runs - the unique events.batch_id constraint is the
        # backstop, nemotron's doctrine).
        await self._set_idempotency(batch_id, event.id)

        # Broadcast LAST, best-effort (prod only): a failure logs and the
        # committed event stands.
        if not self._replay:
            await self._broadcast(event, verification_json)

        logger.info(
            "vlm batch analyzed",
            extra={
                "batch_id": batch_id,
                "camera_id": camera_id,
                "event_id": event.id,
                "verdict": outcome["verdict"],
                "degraded": degraded,
            },
        )
        return event

    # ------------------------------------------------------------------

    async def _check_idempotency(self, batch_id: str) -> int | None:
        if not self._redis:
            return None
        try:
            raw = await self._redis.get(f"batch_event:{batch_id}")
            return int(raw) if raw is not None else None
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("vlm idempotency check failed", extra={"error": str(exc)})
            return None

    async def _set_idempotency(self, batch_id: str, event_id: int) -> None:
        if not self._redis:
            return
        try:
            await self._redis.set(
                f"batch_event:{batch_id}", str(event_id), expire=_IDEMPOTENCY_TTL_SECONDS
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning(
                "failed to set vlm idempotency key",
                extra={"batch_id": batch_id, "event_id": event_id, "error": str(exc)},
            )

    async def _broadcast(self, event: Event, verification: Any) -> None:
        if self._redis is None:
            # The broadcaster IS Redis pub/sub - with no client there is
            # nothing to publish through. The committed event stands (same
            # best-effort contract as any broadcast failure below).
            logger.debug("vlm broadcast skipped: no redis client")
            return
        try:
            from backend.services.event_broadcaster import get_broadcaster

            broadcaster = await get_broadcaster(self._redis)
            message = {
                "type": "event",
                "data": {
                    "id": event.id,
                    "event_id": event.id,
                    "batch_id": event.batch_id,
                    "camera_id": event.camera_id,
                    "risk_score": event.risk_score,
                    "risk_level": event.risk_level,
                    "summary": event.summary,
                    "reasoning": event.reasoning,
                    "started_at": event.started_at.isoformat() if event.started_at else None,
                    # P0.4's exclude_if key: present on vlm events (built
                    # from this tx's rows), and broadcast_event validates
                    # the whole payload against WebSocketEventData.
                    "verification": verification,
                },
            }
            await broadcaster.broadcast_event(message)
        except Exception as exc:
            logger.warning(
                "vlm event broadcast failed (event stands committed)",
                extra={"event_id": event.id, "error": str(exc)},
            )


class _EventView:
    """verification_payload() reads `event.verifications` defensively
    (isinstance list + newest-wins). This is that shape, fed from the
    explicit SELECT the write session already ran - no lazy load anywhere."""

    __slots__ = ("event_id", "verifications")

    def __init__(self, *, event_id: int, rows: list[EventVerification]) -> None:
        self.event_id = event_id
        self.verifications = rows


async def analyze_vlm_batch(
    batch_id: str,
    camera_id: str | None = None,
    detection_ids: list[int | str] | None = None,
    *,
    redis_client: Any | None = None,
) -> Event:
    """Module-level entry the analysis-queue consumer calls in vlm mode
    (PIPELINE_MODE flip is 1.5's; this is the callable it will point at)."""
    analyzer = VlmAnalyzer(redis_client=redis_client)
    return await analyzer.analyze_batch(batch_id, camera_id=camera_id, detection_ids=detection_ids)
