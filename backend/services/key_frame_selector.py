"""Key-frame selection for the VLM verification path (Phase 1.3, spec §2:100).

Picks 1-4 stills per batch: the best detection per camera/class plus the
most recent. A pure function over image REFERENCES - ingest-agnostic on
purpose, which is the seam R1 needs (the same selector serves DB-built
batches in production and eval-store-built batches in replay, 2.1, without
either half knowing about the other).

Contract the property tests pin (backend/tests/unit/services/
test_key_frame_selector.py):

  * 0-4 results, unique detection ids, a subset of the input;
  * ONE result per FILE (`file_path` is a still's identity): the budget
    counts physical stills, so two detections sharing an image - the
    detector's ordinary output shape, one row per object over one frame -
    can never claim two slots;
  * deterministic: arrival order cannot change the result (replay equality);
  * ONE frame per (camera, class) pair - the pair's best, so a weaker
    member never shares the frame budget with the representative that
    already tells its story; "plus the most recent" (spec §2) is honored
    per pair (the rep IS the newest of its pair whenever confidence ties)
    and across pairs (newer pairs win strength ties, and the recency order
    of the picks is the pair-strength order);
  * None confidence sorts as honest-absent (never laundered to 0.0 - the
    `detections.confidence` column is nullable and a fabricated 0 would
    out-rank nothing but hide behind everything);
  * ties break toward the MOST RECENT frame, then the lowest detection id,
    so runs are stable;
  * results carry file paths only - image bytes never pass through here
    (spec §6 privacy: stored rows reference images by path).
"""

from __future__ import annotations

from dataclasses import dataclass

MAX_KEY_FRAMES = 4

# A confidence the column may legally hold when the detector did not emit
# one. -1.0 sorts below every real [0.0, 1.0] value without pretending the
# absence IS a low score (ck_detections_confidence_range already forbids
# negative stored values - this constant never touches the DB).
_ABSENT_CONFIDENCE = -1.0


@dataclass(frozen=True, slots=True)
class FrameRef:
    """One candidate still. Field names mirror the `Detection` columns they
    come from (`file_path` NOT NULL, `thumbnail_path`/`confidence` nullable)
    so production builds one per row with a straight field copy; replay
    builds the same object from an eval-store item."""

    detection_id: int
    camera_id: str
    object_type: str
    confidence: float | None
    timestamp: int  # epoch seconds; recency is all the selector needs
    file_path: str
    thumbnail_path: str | None = None


def _conf(frame: FrameRef) -> float:
    return frame.confidence if frame.confidence is not None else _ABSENT_CONFIDENCE


def _rank_key(frame: FrameRef) -> tuple[float, int, int]:
    """Strength, then recency, then id (ascending, hence negated under a
    descending sort) - a TOTAL order, so the strongest-first sort is
    arrival-order-independent, which is what the determinism property pins."""
    return (_conf(frame), frame.timestamp, -frame.detection_id)


def select_key_frames(frames: list[FrameRef]) -> list[FrameRef]:
    """Return 1-4 DISTINCT STILLS (0 iff the input is empty), strongest first.

    Per (camera, class) pair the representative is the max by
    (confidence, timestamp, id-desc tiebreak); pairs then compete for the
    slots on their representative's rank - but a pair wins at most ONE slot
    per FILE, because the budget counts physical stills, not pairs. A batch
    whose detections all share one pair yields a single frame - within spec's
    1-4 band, and a second frame of one track tells the verifier nothing the
    best one didn't.

    The per-FILE rule (added 2026-09-27) is the same insight one level up:
    the detector emits one row per OBJECT over a shared `file_path`, so a
    single JPEG carrying a person, a car and a dog is three PAIRS on one
    STILL, and a pair-only budget would hand that one image up to four slots
    - the verifier shown one picture by a request that claimed four, with
    three genuinely different frames starved out. `file_path` is the still's
    identity; when a file loses its slot to a stronger pair, the still is
    still represented, so nothing the model could learn from that FILE is
    lost - only the duplicate pixels are."""
    # Unique by detection id (first occurrence wins) so a duplicated row
    # cannot double-count against the frame budget.
    unique: dict[int, FrameRef] = {}
    for frame in frames:
        unique.setdefault(frame.detection_id, frame)

    pairs: dict[tuple[str, str], list[FrameRef]] = {}
    for frame in unique.values():
        pairs.setdefault((frame.camera_id, frame.object_type), []).append(frame)

    representatives = [max(members, key=_rank_key) for members in pairs.values()]
    ranked = sorted(representatives, key=_rank_key, reverse=True)

    picks: list[FrameRef] = []
    shown: set[str] = set()
    for frame in ranked:
        if frame.file_path in shown:
            continue
        picks.append(frame)
        shown.add(frame.file_path)
        if len(picks) == MAX_KEY_FRAMES:
            break
    return picks
