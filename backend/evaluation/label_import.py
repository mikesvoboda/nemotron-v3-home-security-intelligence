"""P0.5 (spec §5/§8 step 0.5): labels + eval-item imports.

Owner feedback and born-labeled generated scenarios become EVAL ITEMS in the
frozen store, and the M0 size bar (100 benign / 20 incidents, spec §5) is
enforced in code. Three duties, three surfaces:

  1. `import_loaded_event` / `import_event` — spec §5's "Historical,
     post-switch" row: an owner-LABELED event (via the SAME §5 mapping
     control_freeze pins: false_positive -> benign; missed_threat, or
     accurate on high -> incident with expected_severity) becomes an item
     keyed by `source_event_id` (it rides the item_id "post-switch::{id}" —
     provenance only, no FK). Unlabeled events are NOT imported here: §5
     excludes them from S2/S3, and a store of labeled items is what the bar
     counts. Their control is NOT the recorded verdict — post-switch events
     were produced by the Nano-4B placeholder, so every imported item
     carries the OFFLINE-30B-REPLAY PLACEHOLDER (control_score None,
     control_source "offline-30b-replay-pending"). The replay itself is
     Phase 2.1's harness — deliberately NOT built here (plan Task 5).

  2. `import_generated_items` — the synthetic-incidents import path for the
     (post-Task-0) media-bearing scenarios. Born-labeled (ledger F9/F5):
     the label comes from where the generator PLACED the set — the same
     committed-corpus category discipline `load_synthetic_items` uses, never
     invented here. Expected score = the set's declared risk band midpoint
     (same discipline); expected severity = that band's level. A set with
     no media skips loudly — `load_synthetic_items` already carries
     label-only sets as DRAFT items; this import is the MEDIA-BEARING one
     and never freezes a fabricated path (D10).

  3. `m0_size_report` — the size check is a computation over the store, not
     a vibe: fewer than 100 benign or 20 LABELED incidents is never
     "M0-complete". Unlabeled items ("" = the unlabeled sentinel) are
     excluded from both sides (spec §5: "Unlabeled items are excluded from
     S2 and S3").

Premise (ledger F9, owner ruling 2026-09-25): the feedback-UI labeling pass
has no running system; label provenance shifts to born-labeled synthetic
generation. The import path and the size-check test are unchanged by that —
they read labels, whoever minted them. The owner labeling execution box
stays open for a returning home stack (R8: an empty state, not a deletion).

Privacy (D10): images COPY INTO the store dir (an item must survive any
retention purge); the store/media paths are required arguments and both the
copy-operation guard (control_freeze's, shared here) and EvalStore.put_item's
write-time residence guard decide every path. This tool never reads capture
roots itself — it only touches files the production DB names.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.evaluation.assess_input import AssessInput, EvalItem
from backend.evaluation.control_freeze import (
    ControlFreezeError,
    _copy_event_media,
    map_feedback,
    score_band,
)
from backend.evaluation.eval_store import EvalStore
from backend.models.event import Event

_LOG = logging.getLogger(__name__)

# spec §5 "Historical, post-switch" row + §5 synthetic row, as item kinds
FEEDBACK_KIND = "historical-post-switch"
GENERATED_KIND = "synthetic-generated"

# control placeholder (Phase 2.1's offline 30B replay fills it; NOTHING here
# may mint a real control score - the placeholder verdict is not a control)
CONTROL_PLACEHOLDER = "offline-30b-replay-pending"
BORN_LABEL_SOURCE = "born-labeled-scenario-spec"

# spec §5 size bar: "at least 100 benign and 20 incidents"
M0_MIN_BENIGN = 100
M0_MIN_INCIDENTS = 20

_ITEM_NS_EVENT = "post-switch"
_ITEM_NS_GENERATED = "generated"

# severity band floors - the minimum score of each level (backend.services
# .severity taxonomy defaults; mirrors control_freeze's band edges: LOW 0-29,
# MEDIUM 30-59, HIGH 60-84, CRITICAL 85-100). S3 asks "at or ABOVE the
# expected minimum", so an incident's expected score is the FLOOR of the
# owner's (or the band's) severity claim - never a higher invention.
_SEVERITY_FLOORS = {"low": 0, "medium": 30, "high": 60, "critical": 85}

# media-bearing extensions for the born-labeled corpus scan (images S-3/
# replay feed the VLM; video arrives with the owner's generated clips)
_MEDIA_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".mp4", ".mov", ".avi", ".mkv"}


class LabelImportError(Exception):
    """A whole-run precondition failed (never a per-item skip)."""


def severity_floor(severity: str | None) -> int:
    """Minimum score asserting `severity` (taxonomy defaults). An unknown or
    missing severity floors at 0 = the honest 'any score claims at least
    low' - never a crash, never an invented demand."""
    return _SEVERITY_FLOORS.get(str(severity or "").lower(), 0)


def item_id_for_event(event_id: int) -> str:
    """Deterministic id: source_event_id rides it (provenance only, no FK)
    and re-running the import is idempotent by construction."""
    return f"{_ITEM_NS_EVENT}::{event_id}"


def item_id_for_generated(category: str, set_name: str, video_id: str | None = None) -> str:
    """Born-labeled id. Distinct namespace from load_synthetic_items'
    'synthetic:...' DRAFT ids so the label-only draft and the media-bearing
    import of the same set are separate, comparable store rows."""
    base = f"{_ITEM_NS_GENERATED}:{category}:{set_name}"
    return base + (f"::{video_id}" if video_id else "")


@dataclass
class ImportResult:
    """One import attempt's outcome - the manifest's raw material."""

    item_id: str
    kind: str  # FEEDBACK_KIND | GENERATED_KIND
    source_event_id: int | None = None  # provenance only, post-switch rows
    label: str = ""  # "" = unlabeled (never imported by box 1; bar-excluded)
    expected_severity: str | None = None
    control_score: int | None = None  # always None until 2.1's replay runs
    label_source: str = "none"  # owner-feedback | born-labeled-scenario-spec | none
    control_source: str = CONTROL_PLACEHOLDER
    media_paths: tuple[str, ...] = ()
    skipped: bool = False
    reason: str | None = None


# ---------------------------------------------------------------------
# 1. EventFeedback -> eval item (spec §5 "Historical, post-switch")
# ---------------------------------------------------------------------


def _build_snapshot(event: Any, detections: list[Any]) -> AssessInput:
    """Honest snapshot only (the freeze/stock-loader discipline): zone and
    household state is NOT recorded on event rows, so nothing is claimed."""
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


def _skip(
    item_id: str,
    kind: str,
    *,
    reason: str,
    source_event_id: int | None = None,
) -> ImportResult:
    _LOG.warning("label import skip %s: %s", item_id, reason)
    return ImportResult(
        item_id=item_id,
        kind=kind,
        source_event_id=source_event_id,
        skipped=True,
        reason=reason,
        label_source="none",
        control_source="none",
    )


def import_loaded_event(
    event: Any,
    *,
    store: EvalStore,
    store_media_dir: str | Path,
) -> ImportResult:
    """Import ONE already-loaded labeled event (the synchronous core - any
    Event-shaped row with .detections/.feedback loaded; also the unit seam,
    fed fabricated rows, mirroring control_freeze.freeze_loaded_event).

    Only LABELED events import: map_feedback says (None, None) for no
    feedback, accurate-on-low and severity_wrong - those events are
    unlabeled for §5's purposes and stay excluded from the S2/S3 bar rather
    than freezing a wrong claim (unlike a pre-switch freeze, where EVERY
    event still earns a control run, an import exists to build the labeled
    corpus). Skips are LOUD: returned with a reason and logged - never an
    exception for a per-event condition."""
    event_id = int(event.id)
    item_id = item_id_for_event(event_id)

    if store.get_item(item_id) is not None:
        return _skip(
            item_id,
            FEEDBACK_KIND,
            reason="already imported (immutable item)",
            source_event_id=event_id,
        )

    # §5 mapping, ONE source with the freeze. The event's own score decides
    # only whether an `accurate` is a high-band endorsement (map_feedback's
    # documented fallback) - it is NEVER the control or the expected score.
    recorded = getattr(event, "risk_score", None)
    label, severity = map_feedback(event.feedback, event_risk_score=recorded)
    if label is None:
        return _skip(
            item_id,
            FEEDBACK_KIND,
            reason="no label (no feedback, accurate-on-low, or severity_wrong) - "
            "stays excluded from the S2/S3 bar (§5)",
            source_event_id=event_id,
        )

    # Copy + D10 guards (incl. the media-root residence PREFLIGHT: a
    # repo/capture-resident root misconfigures the WHOLE run and raises) are
    # the freeze's, shared verbatim - same doctrine, same tests behind it.
    try:
        copied, detections, media_error = _copy_event_media(event, store_media_dir)
    except ControlFreezeError as e:
        raise LabelImportError(f"store media root rejected by the D10 guard: {e}") from e
    if media_error is not None:
        return _skip(item_id, FEEDBACK_KIND, reason=media_error, source_event_id=event_id)
    if not copied:
        return _skip(
            item_id,
            FEEDBACK_KIND,
            reason="event detections name no files on disk (no media)",
            source_event_id=event_id,
        )

    # S3 semantics: expected score = the owner's severity MINIMUM, never the
    # placeholder pipeline's recorded verdict.
    expected_score = severity_floor(severity)
    item = EvalItem(
        item_id=item_id,
        media_paths=[str(p) for p in copied],
        expected_label=label,
        expected_risk_score=expected_score,
        snapshot=_build_snapshot(event, detections),
        source=FEEDBACK_KIND,
    )
    try:
        store.put_item(item)
    except ControlFreezeError as e:  # defensive: guard type from the shared copy helper
        raise LabelImportError(f"store location rejected by the D10 guard: {e}") from e
    except ValueError as e:
        msg = str(e)
        if "frozen" in msg:
            return _skip(
                item_id,
                FEEDBACK_KIND,
                reason=f"item frozen with different content: {e}",
                source_event_id=event_id,
            )
        raise LabelImportError(f"store location rejected by the D10 guard: {e}") from e

    return ImportResult(
        item_id=item_id,
        kind=FEEDBACK_KIND,
        source_event_id=event_id,
        label=label,
        expected_severity=severity,
        control_score=None,  # 2.1's replay is the only thing that fills this
        label_source="owner-feedback",
        control_source=CONTROL_PLACEHOLDER,
        media_paths=tuple(str(p) for p in copied),
    )


async def import_event(
    *,
    session: AsyncSession,
    event_id: int,
    store: EvalStore,
    store_media_dir: str | Path,
) -> ImportResult:
    """The ORM read seam (pinned live by
    backend/tests/integration/test_p05_label_import.py): load detections +
    feedback eagerly and hand the row to the sync core."""
    stmt = (
        select(Event)
        .where(Event.id == event_id)
        .options(selectinload(Event.detections), selectinload(Event.feedback))
    )
    event = (await session.execute(stmt)).scalar_one_or_none()
    item_id = item_id_for_event(event_id)
    if event is None:
        return _skip(
            item_id, FEEDBACK_KIND, reason=f"event {event_id} not found", source_event_id=event_id
        )
    return import_loaded_event(event, store=store, store_media_dir=store_media_dir)


async def import_labeled_events(
    *,
    session: AsyncSession,
    store: EvalStore,
    store_media_dir: str | Path,
    event_ids: list[int] | None = None,
) -> list[ImportResult]:
    """Batch import. Without explicit ids, sweep EVERY event that carries
    feedback (one feedback row per event by UNIQUE(event_id)); unlabeled
    events are never candidates. Every candidate gets a manifest row,
    good or loud-skip."""
    if event_ids is None:
        stmt = select(Event.id).join(Event.feedback).order_by(Event.id)
        event_ids = [r[0] for r in (await session.execute(stmt)).all()]
    return [
        await import_event(
            session=session, event_id=eid, store=store, store_media_dir=store_media_dir
        )
        for eid in event_ids
    ]


# ---------------------------------------------------------------------
# 2. Born-labeled generated scenarios -> media-bearing eval items
# ---------------------------------------------------------------------


def _dir_media_files(dirpath: Path) -> list[Path]:
    """Media files sitting directly in a generated set dir (frames or
    clips), sorted for a stable fingerprint. Sidecar JSONs never count."""
    return sorted(p for p in dirpath.iterdir() if p.suffix.lower() in _MEDIA_SUFFIXES)


def _set_media(dirpath: Path) -> tuple[list[Path], str | None]:
    """A generated set's media: its manifest.json when present (the stock
    convention, held to CONTAINMENT - the G0 audit #1 discipline: a manifest
    naming /etc/shadow is refused, not trusted), else a scan of media files
    sitting in the dir. Returns (paths, loud-skip reason). A manifest that
    exists is AUTHORITATIVE: if every frame it names escapes the dir, that
    is a refused set, not an excuse to scan around it."""
    manifest = dirpath / "manifest.json"
    if not manifest.is_file():
        return _dir_media_files(dirpath), None
    try:
        frames = json.loads(manifest.read_text())
    except (OSError, json.JSONDecodeError) as e:
        return [], f"manifest unreadable: {e}"
    if not isinstance(frames, list):
        return [], f"manifest is {type(frames).__name__}, not a list"
    paths: list[Path] = []
    named = 0
    for entry in frames:
        raw = entry.get("file") if isinstance(entry, dict) else None
        if not raw:
            continue
        named += 1
        resolved = Path(str(raw)).expanduser()
        resolved = resolved if resolved.is_absolute() else (dirpath / resolved)
        resolved = resolved.resolve()
        if dirpath.resolve() not in resolved.parents:
            _LOG.warning("generated set %s: manifest path %r escapes the set dir", dirpath, raw)
            continue
        paths.append(resolved)
    if named and not paths:
        return [], "every manifest frame escapes the set dir (refused, not scanned around)"
    if not paths:
        # manifest present but names nothing: fall back to the dir scan
        return _dir_media_files(dirpath), None
    return paths, None


def _midpoint(risk: Any) -> int:
    """Declared band midpoint (load_synthetic_items' rule: unbounded or
    malformed -> 0, honest unknown)."""
    if not isinstance(risk, dict):
        return 0
    lo, hi = risk.get("min_score"), risk.get("max_score")
    if isinstance(lo, (int, float)) and isinstance(hi, (int, float)):
        return int((lo + hi) // 2)
    return 0


def import_generated_items(
    *,
    corpus_dir: str | Path,
    store: EvalStore,
) -> list[ImportResult]:
    """Every media-bearing generated set under corpus_dir
    (<category>/<set>/expected_labels.json + frames/clips) becomes a frozen
    item. Labels are BORN: category comes from the set's placement (the
    committed corpus places each of the 13 scenarios in exactly one
    category), expected score from the set's declared risk band, severity
    from that band's level. Nothing is invented:

      * no media -> LOUD skip (load_synthetic_items carries those DRAFTs;
        inventing a path would be a D10 fabrication);
      * an unknown category -> loud skip (no guessed label);
      * a manifest escaping its set dir -> that frame is refused (audit #1);
      * store media paths ARE the source paths (the owner's generated corpus
        is off-repo, unlike production event media - EvalStore.put_item's
        write-time residence guard still decides every path, and a
        repo-resident corpus fails the run loudly rather than importing).

    A missing corpus_dir is a hard error. Idempotent by deterministic id."""
    from backend.evaluation.eval_store import _CATEGORY_LABELS  # the ONE label vocabulary

    root = Path(corpus_dir)
    if not root.is_dir():
        raise FileNotFoundError(f"generated corpus not found: {root}")
    out: list[ImportResult] = []
    for path in sorted(root.glob("*/*/expected_labels.json")):
        dirpath = path.parent
        category, set_name = dirpath.parent.name, dirpath.name
        try:
            labels = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError) as e:
            out.append(
                _skip(
                    item_id_for_generated(category, set_name),
                    GENERATED_KIND,
                    reason=f"unreadable label set: {e}",
                )
            )
            continue
        if not isinstance(labels, dict):
            out.append(
                _skip(
                    item_id_for_generated(category, set_name),
                    GENERATED_KIND,
                    reason=f"label set JSON is {type(labels).__name__}, not an object",
                )
            )
            continue
        vid = labels.get("video_id") if isinstance(labels.get("video_id"), str) else None
        item_id = item_id_for_generated(category, set_name, vid)
        # placement first; the labels file's own "category" may CONFIRM it
        # (load_synthetic_items honors the same override) but never rescues
        # an unknown directory into a guessed label.
        declared = labels.get("category")
        eff = declared if declared in _CATEGORY_LABELS else category
        label = _CATEGORY_LABELS.get(eff)
        if label is None:
            out.append(
                _skip(
                    item_id,
                    GENERATED_KIND,
                    reason=f"unknown category {category!r} - no committed label",
                )
            )
            continue
        if store.get_item(item_id) is not None:
            out.append(_skip(item_id, GENERATED_KIND, reason="already imported (immutable item)"))
            continue
        media, media_reason = _set_media(dirpath)
        if media_reason:
            out.append(_skip(item_id, GENERATED_KIND, reason=media_reason))
            continue
        if not media:
            out.append(
                _skip(
                    item_id,
                    GENERATED_KIND,
                    reason="no media files (label-only set stays a load_synthetic_items "
                    "DRAFT; this import is the media-bearing one)",
                )
            )
            continue
        score = _midpoint(labels.get("risk"))
        # expected_severity is the S3 demand - it exists for INCIDENTS only;
        # a benign item's bar is S2 (a level ceiling), not a floor, so it
        # carries no severity claim.
        severity = score_band(score) if label == "incident" and score > 0 else None
        item = EvalItem(
            item_id=item_id,
            media_paths=[str(p) for p in media],
            expected_label=label,
            expected_risk_score=score,
            snapshot=AssessInput(
                camera_id="synthetic-source",
                detections=list(labels.get("detections") or []),
                zones=[],
                zone_crossing=False,
                household={},
                timestamp="1970-01-01T00:00:00+00:00",  # honest epoch sentinel
            ),
            source=GENERATED_KIND,
        )
        try:
            store.put_item(item)
        except ValueError as e:
            msg = str(e)
            if "frozen" in msg:
                out.append(
                    _skip(
                        item_id, GENERATED_KIND, reason=f"item frozen with different content: {e}"
                    )
                )
                continue
            # the D10 guard rejecting media means the corpus itself is
            # repo-resident - a misconfigured run, not a per-item skip.
            raise LabelImportError(f"corpus rejected by the D10 guard: {e}") from e
        out.append(
            ImportResult(
                item_id=item_id,
                kind=GENERATED_KIND,
                label=label,
                expected_severity=severity,
                control_score=None,
                label_source=BORN_LABEL_SOURCE,
                control_source=CONTROL_PLACEHOLDER,
                media_paths=tuple(str(p) for p in media),
            )
        )
    return out


# ---------------------------------------------------------------------
# 3. The M0 size bar (spec §5) — code, not vibes
# ---------------------------------------------------------------------


def m0_size_report(store: EvalStore) -> dict[str, Any]:
    """Count the store's LABELED items against the §5 bar. Unlabeled items
    ("" sentinel) are excluded from both sides; an unknown non-empty label
    counts on neither side but surfaces in `unknown` so a vocabulary drift
    can't hide as 'unlabeled'. Purely a read."""
    rows = store._db.execute("SELECT payload FROM items").fetchall()
    benign = incidents = unlabeled = unknown = 0
    for (payload,) in rows:
        try:
            label = json.loads(payload).get("expected_label", "")
        except json.JSONDecodeError:  # a corrupt row must not crash a gate
            unknown += 1
            continue
        if not label:
            unlabeled += 1
        elif label == "benign":
            benign += 1
        elif label == "incident":
            incidents += 1
        else:
            unknown += 1
    reasons: list[str] = []
    if benign < M0_MIN_BENIGN:
        reasons.append(f"benign {benign} < {M0_MIN_BENIGN} required (spec §5)")
    if incidents < M0_MIN_INCIDENTS:
        reasons.append(f"incidents {incidents} < {M0_MIN_INCIDENTS} required (spec §5)")
    return {
        "benign": benign,
        "incidents": incidents,
        "unlabeled": unlabeled,
        "unknown": unknown,
        "min_benign": M0_MIN_BENIGN,
        "min_incidents": M0_MIN_INCIDENTS,
        "m0_complete": not reasons,
        "reasons": reasons,
    }


def write_import_manifest(results: list[ImportResult], path: str | Path) -> Path:
    """Import manifest: one JSON row per attempt - kind, label source,
    control source, skips WITH reasons (a manifest that hides losses is not
    evidence; same doctrine as control_freeze.write_manifest)."""
    p = Path(path)
    with p.open("w", encoding="utf-8") as fh:
        for r in results:
            row = asdict(r)
            row["media_paths"] = list(r.media_paths)
            row["imported_at"] = datetime.now(UTC).isoformat()
            fh.write(json.dumps(row) + "\n")
    return p


__all__ = [
    "BORN_LABEL_SOURCE",
    "CONTROL_PLACEHOLDER",
    "FEEDBACK_KIND",
    "GENERATED_KIND",
    "M0_MIN_BENIGN",
    "M0_MIN_INCIDENTS",
    "ImportResult",
    "LabelImportError",
    "import_event",
    "import_generated_items",
    "import_labeled_events",
    "import_loaded_event",
    "item_id_for_event",
    "item_id_for_generated",
    "m0_size_report",
    "severity_floor",
    "write_import_manifest",
]
