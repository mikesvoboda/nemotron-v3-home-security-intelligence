"""P0.1 (spec §5/§8 step 0.1): the control-freeze tool.

PREMISE (ledger F9, owner ruling 2026-09-25): the freeze EXECUTION is ruled
N/A - the previous home system is offline and no pre-switch traffic exists
to timestamp, so the control-timestamp-FIRST step has no subject. This tool
is nonetheless CODE-DONE and tested so a returning production system can run
it (R8: an empty state, not a deletion). The sequencing rule stays intact
wherever pre-switch events DO exist: 0.1's control timestamp is recorded
BEFORE 0.2 serves any new event (dormancy rule; ledger [O] row).

What one freeze does (spec §5, "Historical, pre-switch" row):

  Event (pre-switch) -> EvalItem in the eval store:
    * the event's detection images COPIED INTO the store dir. Cleanup keeps
      images by default (files outlive event rows), but the freeze copies
      anyway: retention DOES hard-delete Events, and a frozen item must
      survive every later purge of production history;
    * the AssessInput snapshot (camera, detection context, timestamp) -
      honest fields only; zone/household state is not recorded on event
      rows, so the snapshot claims none;
    * the control: the verdict RECORDED by the dual-GPU 30B pipeline
      (Event.risk_score; spec §5 "Recorded ... copied at freeze time") plus
      the owner's label from EventFeedback: false_positive -> benign;
      missed_threat, or accurate on high -> incident with expected_severity
      (falls back to the event's own score band). Unlabeled events freeze
      with label "" (empty = unlabeled): they carry NO control claim and
      metrics skip them in S2/S3, but the item still gets its run (spec §5
      requires an offline-30B control on EVERY item). An event with no
      recorded score at all is skipped loudly - without a control there is
      nothing to replay against;
    * source_event_id provenance ONLY: it rides the item_id as text
      ("pre-switch::{event_id}") - no foreign key, no production linkage
      (the eval store is a separate SQLite world by design).

  Plus one manifest row per frozen item - kind ("historical-pre-switch"),
  label source, control source. This is what "frozen" means for M0.

Privacy (D10): the store path is a REQUIRED argument and EvalStore.put_item
refuses repo/capture-root media at write time; the freeze additionally
refuses to copy a SOURCE from inside the store root (a recursive copy bomb)
or from any repo/capture-residence path. The tool never reads capture roots
itself - it only ever touches files the production DB names.
"""

from __future__ import annotations

import json
import logging
import shutil
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.evaluation.assess_input import AssessInput, EvalItem
from backend.evaluation.eval_store import _REAL_MEDIA_PREFIXES, EvalStore
from backend.models.event import Event

_LOG = logging.getLogger(__name__)

# spec §5 manifest kind for this row of the item table
CONTROL_KIND = "historical-pre-switch"
_ITEM_NS = "pre-switch"

# severity band edges from backend.services.severity (configurable at runtime
# there; these are the taxonomy defaults the recorded scores were banded with)
_LOW_MAX = 29
_MEDIUM_MAX = 59
_HIGH_MAX = 84

# owner feedback types that assert the alert was correct
_ACCURATE_TYPES = frozenset({"accurate", "correct"})


def score_band(score: int) -> str:
    """Severity band of a 0-100 score (taxonomy defaults, same edges as
    backend.services.severity / EventResponse.risk_level)."""
    if score <= _LOW_MAX:
        return "low"
    if score <= _MEDIUM_MAX:
        return "medium"
    if score <= _HIGH_MAX:
        return "high"
    return "critical"


class ControlFreezeError(Exception):
    """A whole-run precondition failed (never a per-event skip)."""


def map_feedback(
    feedback: Any,
    event_risk_score: int | None = None,
) -> tuple[str | None, str | None]:
    """Owner label from EventFeedback, per the spec §5 table VERBATIM:
    false_positive -> benign; missed_threat, or accurate on high -> incident
    with expected_severity. Anything else (no feedback, accurate-on-low,
    severity_wrong) yields (None, None): the event is UNLABELED, which the
    freeze honors as an empty label rather than guessing.

    expected_severity fallback for a bare `accurate` on a high/critical event
    is the event's own score band: `accurate` endorses the recorded verdict,
    so the recorded band IS the owner-asserted minimum (never invent a
    higher one)."""
    if feedback is None:
        return None, None
    ftype = str(getattr(feedback, "feedback_type", "") or "")
    if ftype == "false_positive":
        return "benign", None
    if ftype == "missed_threat":
        return "incident", getattr(feedback, "expected_severity", None) or "high"
    if ftype in _ACCURATE_TYPES:
        if event_risk_score is not None and event_risk_score > _MEDIUM_MAX:
            declared = getattr(feedback, "expected_severity", None)
            return "incident", declared or score_band(event_risk_score)
        return None, None
    return None, None


def resolve_control(event: Any) -> int | None:
    """The control score = the verdict RECORDED on the event (spec §5:
    "Recorded by the dual-GPU 30B pipeline, copied at freeze time"). The
    30B-era pipeline persisted its score to Event.risk_score and the raw
    response to LLMInteraction.raw_response; prefer the column, fall back to
    parsing the recorded response, else None (= no control -> skip loudly)."""
    score = getattr(event, "risk_score", None)
    if isinstance(score, int):
        return score
    li = getattr(event, "llm_interaction", None)
    raw = getattr(li, "raw_response", None) if li is not None else None
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return None
        if isinstance(parsed, dict):
            value = parsed.get("risk_score")
            if isinstance(value, int):
                return value
    return None


@dataclass
class FreezeResult:
    """One freeze attempt's outcome - the manifest's raw material."""

    item_id: str
    source_event_id: int
    kind: str = CONTROL_KIND
    label: str = ""  # "" = unlabeled (carries no control claim for S2/S3)
    expected_severity: str | None = None
    control_score: int | None = None
    label_source: str = "none"  # "owner-feedback" | "none"
    control_source: str = "recorded-30b"  # the ONLY legal source pre-switch
    copied_media: tuple[str, ...] = ()
    skipped: bool = False
    reason: str | None = None


def item_id_for(event_id: int) -> str:
    """Deterministic id - provenance rides it, and re-running the freeze is
    therefore idempotent by construction."""
    return f"{_ITEM_NS}::{event_id}"


def _looks_like_real_media(path: str) -> bool:
    low = str(path).lower()
    return any(m in low for m in _REAL_MEDIA_PREFIXES)


def _resides_in_repo(path: Path) -> bool:
    repo_root = Path(__file__).resolve().parents[2]
    r_low, root_low = str(path).casefold(), str(repo_root).casefold()
    return r_low == root_low or root_low in [str(x) for x in Path(r_low).parents]


def _copy_into_store(src: Path, dest_root: Path, event_id: int) -> Path:
    """Copy one source file into <dest_root>/event-<id>/, refusing sources
    that are not plain readable files, that live inside the store root (a
    recursive copy bomb), or that reside in the repo / a capture root (D10).
    EvalStore.put_item guards the item's media paths at write time; THIS
    guard is about the copy operation itself."""
    if not src.is_file():
        raise OSError(f"not a regular file: {src}")
    resolved = src.resolve()
    store_resolved = dest_root.resolve()
    if store_resolved == resolved or store_resolved in resolved.parents:
        raise ControlFreezeError(f"refusing to copy a source from inside the store root: {src}")
    if _looks_like_real_media(str(resolved)) or _resides_in_repo(resolved):
        raise ControlFreezeError(
            f"privacy (D10): refusing to copy media that resides in the repo or a "
            f"capture root: {src}"
        )
    dest_dir = dest_root / f"event-{event_id}"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / resolved.name
    if dest.exists():  # a re-run over the same store must not clobber a frozen copy
        stem, suffix = resolved.stem, resolved.suffix
        dest = dest_dir / f"{stem}-{resolved.stat().st_ino}{suffix}"
    shutil.copy2(resolved, dest)
    return dest


def _build_snapshot(event: Any, detections: list[Any]) -> AssessInput:
    """Honest snapshot only (the eval_store stock-loader discipline): zone
    and household state is NOT recorded on event rows, so nothing is claimed
    for it - empty, never invented."""
    det_rows = [
        {
            "id": d.id,
            "object_type": d.object_type,
            "confidence": d.confidence,
            "bbox": [d.bbox_x, d.bbox_y, d.bbox_width, d.bbox_height],
            "detected_at": d.detected_at.isoformat() if d.detected_at else None,
        }
        for d in detections
    ]
    ts = event.started_at
    return AssessInput(
        camera_id=event.camera_id,
        detections=det_rows,
        zones=[],
        zone_crossing=False,
        household={},
        timestamp=ts.isoformat() if isinstance(ts, datetime) else str(ts),
    )


async def freeze_event(
    *,
    session: AsyncSession,
    event_id: int,
    store: EvalStore,
    store_media_dir: str | Path,
) -> FreezeResult:
    """Load one production event (eager: detections, feedback, the recorded
    LLMInteraction) and freeze it. The ORM read seam; the freeze itself is
    `freeze_loaded_event`. The real read path is pinned by
    backend/tests/integration/test_p01_control_freeze.py (live test PG -
    the plan's "test PG with rows staged by fixture" branch; aiosqlite is
    not in this repo's dependency set, so no sqlite unit fixture)."""
    stmt = (
        select(Event)
        .where(Event.id == event_id)
        .options(
            selectinload(Event.detections),
            selectinload(Event.feedback),
            selectinload(Event.llm_interaction),
        )
    )
    event = (await session.execute(stmt)).scalar_one_or_none()
    item_id = item_id_for(event_id)
    if event is None:
        return _skip(item_id, event_id, reason=f"event {event_id} not found")
    return freeze_loaded_event(event, store=store, store_media_dir=store_media_dir)


def freeze_loaded_event(
    event: Any,
    *,
    store: EvalStore,
    store_media_dir: str | Path,
) -> FreezeResult:
    """Freeze ONE already-loaded event into `store` (the synchronous core -
    any Event-shaped row with .detections/.feedback/.llm_interaction loaded;
    this is also the unit-test seam, fed fabricated rows). Skips are LOUD:
    returned on FreezeResult (with reason) and logged - never silent, never
    an exception for a per-event condition (one bad event must not abort a
    batch)."""
    event_id = int(event.id)
    item_id = item_id_for(event_id)

    if store.get_item(item_id) is not None:
        # frozen items are immutable (store doctrine) - a re-run is a no-op
        return _skip(item_id, event_id, reason="already frozen (immutable item)")

    control = resolve_control(event)
    if control is None:
        return _skip(
            item_id,
            event_id,
            reason="no recorded control score (risk_score NULL and no parseable "
            "LLMInteraction) - nothing to replay against",
        )

    label, severity = map_feedback(event.feedback, event_risk_score=control)
    label_source = "owner-feedback" if label is not None else "none"

    copied, detections, media_error = _copy_event_media(event, store_media_dir)
    if media_error is not None:
        return _skip(item_id, event_id, reason=media_error)

    item = EvalItem(
        item_id=item_id,
        media_paths=[str(p) for p in copied],
        expected_label=label or "",  # "" = unlabeled; store contract holds
        expected_risk_score=control,
        snapshot=_build_snapshot(event, detections),
        source=CONTROL_KIND,
    )
    try:
        store.put_item(item)
    except ValidationError as e:  # item contract rejection (should not happen)
        _LOG.error("freeze rejected event=%s by the item contract: %s", event_id, e)
        return _skip(item_id, event_id, reason=f"item contract: {e}")
    except ValueError as e:
        msg = str(e)
        if "frozen" in msg:
            # put_item doctrine: same id, different content. The deterministic
            # id makes this a changed-source event (a detection changed under
            # us, or a concurrent shard raced) - loud skip, never a silent
            # overwrite of a frozen item.
            return _skip(item_id, event_id, reason=f"item frozen with different content: {e}")
        # the D10 residence guard firing means the STORE DIRECTORY itself is
        # misconfigured (inside the repo / a capture root). That is not a
        # per-event condition - it fails the whole run loudly.
        raise ControlFreezeError(f"store location rejected by the D10 guard: {e}") from e

    return FreezeResult(
        item_id=item_id,
        source_event_id=event_id,
        label=label or "",
        expected_severity=severity,
        control_score=control,
        label_source=label_source,
        control_source="recorded-30b",
        copied_media=tuple(str(p) for p in copied),
    )


def _copy_event_media(
    event: Any, store_media_dir: str | Path
) -> tuple[list[Path], list[Any], str | None]:
    """Copy every detection's image + thumbnail into the store. Returns
    (copied paths, detections, error) - error set = LOUD skip reason (media
    must be self-contained in the store or the item is not frozen at all).
    An empty detection set is also an error: no media, nothing to replay."""
    detections = list(event.detections or [])
    if not detections:
        return [], [], "event carries no detections (no media)"
    media_root = Path(store_media_dir)
    # Preflight (D10): copies land wherever media_root points, so a media root
    # inside the repo or a capture root misconfigures the WHOLE run - refuse
    # before anything is written, as an error rather than a per-event skip.
    root_resolved = media_root.expanduser().resolve()
    if _resides_in_repo(root_resolved) or _looks_like_real_media(str(root_resolved)):
        raise ControlFreezeError(
            f"store media root {store_media_dir!r} resolves to {root_resolved}, "
            "inside the repo or a capture root (D10) - point the freeze at an "
            "off-repo eval root"
        )
    copied: list[Path] = []
    try:
        for det in detections:
            for attr in ("file_path", "thumbnail_path"):
                raw = getattr(det, attr, None)
                if not raw:
                    continue
                src = Path(str(raw)).expanduser()
                if not src.is_file():
                    raise OSError(f"detection {det.id} {attr} missing on disk: {raw}")
                copied.append(_copy_into_store(src, media_root, int(event.id)))
    except (OSError, ControlFreezeError) as e:
        _LOG.warning("freeze skip event=%s: %s", event.id, e)
        return [], detections, f"media: {e}"
    return copied, detections, None


def _skip(item_id: str, event_id: int, *, reason: str) -> FreezeResult:
    _LOG.warning("freeze skip %s (event %s): %s", item_id, event_id, reason)
    return FreezeResult(
        item_id=item_id,
        source_event_id=event_id,
        skipped=True,
        reason=reason,
        control_source="none",
    )


async def freeze_events(
    *,
    session: AsyncSession,
    event_ids: list[int],
    store: EvalStore,
    store_media_dir: str | Path,
) -> list[FreezeResult]:
    """Batch freeze: every event gets a row, good or loud-skip. The manifest
    is only honest if skips appear in it too."""
    return [
        await freeze_event(
            session=session,
            event_id=eid,
            store=store,
            store_media_dir=store_media_dir,
        )
        for eid in event_ids
    ]


def write_manifest(results: list[FreezeResult], path: str | Path) -> Path:
    """Freeze manifest: one JSON row per item - kind, label source, control
    source (plan Task 1: "this is what 'frozen' means for M0"). Skips are
    written too, with their reason - a manifest that hides losses is not
    evidence."""
    p = Path(path)
    with p.open("w", encoding="utf-8") as fh:
        for r in results:
            row = asdict(r)
            row["copied_media"] = list(r.copied_media)
            row["frozen_at"] = datetime.now(UTC).isoformat()
            fh.write(json.dumps(row) + "\n")
    return p


__all__ = [
    "CONTROL_KIND",
    "ControlFreezeError",
    "FreezeResult",
    "freeze_event",
    "freeze_events",
    "freeze_loaded_event",
    "item_id_for",
    "map_feedback",
    "resolve_control",
    "score_band",
    "write_manifest",
]
