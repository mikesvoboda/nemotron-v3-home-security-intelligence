"""Key-frame selection for the VLM verification path (Phase 1.3, spec §2:100).

Picks 1-4 stills per batch: the best detection per camera/class plus the
most recent. A pure function over image REFERENCES - ingest-agnostic on
purpose, which is the seam R1 needs (the same selector serves DB-built
batches in production and eval-store-built batches in replay, 2.1, without
either half knowing about the other).

Contract the property tests pin (backend/tests/unit/services/
test_key_frame_selector.py):

  * 0-4 results, unique detection ids, a subset of the input;
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
    """Return 1-4 frames (0 iff the input is empty), strongest pair first.

    Per (camera, class) pair the representative is the max by
    (confidence, timestamp, id-desc tiebreak); pairs then compete for the
    4 slots on their representative's rank. A batch whose detections all
    share one pair yields a single frame - within spec's 1-4 band, and a
    second frame of one track tells the verifier nothing the best one
    didn't."""
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
    return ranked[:MAX_KEY_FRAMES]
