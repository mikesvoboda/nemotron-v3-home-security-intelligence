"""The specialist stage — one short text per specialist into AssessInput
(Rev 6 Task 3b, owner rulings F11 + F12).

The VLM verdict reads THREE short lines — ``faces``, ``plates``,
``person_reid`` — computed here, over the batch's SELECTED key frames, before
``vlm_assess``. They ride the snapshot as ``AssessInput.specialist_outputs``
(F11 ruling 4: the snapshot is their only carrier; the VLM never originates
them, and replay never re-runs them — replay reads what production stored).

Three rules dominate every function below:

1. **Never block the verdict (spec §6).** A missing model, a missing optional
   package, a database hiccup, a failed inference — every one degrades to the
   text "unavailable". Nothing in this module raises into the analyzer; the
   entry points catch everything and there is deliberately no way for a
   specialist failure to fail a batch. "unavailable" is also never "unknown":
   the prompt shows which specialist did not run instead of a silently
   missing line.
2. **Four face outcomes, not two (F11 ruling 3).** ``classify_face_outcome``
   is the pure decision: match (name + score), unknown (PASSED the quality
   gate, no gallery match), not_identifiable (failed the gate), unavailable.
   The hard rule is that a gate-FAILING crop is never "unknown" — the owner's
   tiny/night face reading "1 unknown face" is an S2 false-positive driver,
   because "unknown" pushes the VLM toward alarm. The gate is minimum face
   size + SCRFD score, both from config (``face_min_size_px`` /
   ``face_scrfd_threshold``) — never constants here. Thresholds are
   PROVISIONAL (F12): calibration on the owner's gallery/night footage is a
   Phase 2 item, with AdaFace (small/night challenger) and CR-FIQA (quality
   model) ledgered as later items, not built.
3. **Honesty about vector spaces (F11 ruling 4 / F12).** The re-ID leg
   refuses a cross-space score and says so (see ``collect_reid_text`` — the
   store is CLIP-768, the resident Triton model is OSNet-512; a cosine across
   them is noise, and numpy raises before it even gets that far). The face
   leg enforces the same doctrine via model ids (``_gallery_model_ids``):
   probe and gallery vectors from different weight builds never produce a
   score, they produce "unavailable (re-enroll)".

Privacy (spec §6): texts carry names, percents, counts and plate strings
only — never bytes, never paths. Face detection uses the F12 CPU leg
(SCRFD-10G-KPS + w600k_r50 via face_recognizer_loader), not yolo11-face:
boxes-only cannot be ArcFace-aligned, so its crops quietly lose embedder
accuracy. Blocking work runs off the event loop.
"""

from __future__ import annotations

import asyncio
import functools
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from backend.core.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from backend.core.config import Settings

logger = get_logger(__name__)

#: The literal every degraded specialist line starts with. The VLM prompt and
#: the tests both key on it; never widen its meaning to "unknown".
UNAVAILABLE = "unavailable"

#: What the re-ID text says when the gallery and the probe live in different
#: vector spaces. Deliberately not a number — see collect_reid_text.
CROSS_SPACE_REASON = (
    "household re-ID store is CLIP-768 space; the resident Triton reid model "
    "is OSNet-512 — no cross-space score (ledgered follow-up: re-enroll in "
    "one space or swap to PersonViT/CLIP-ReID, rev 7)"
)


# ---------------------------------------------------------------------------
# Outcomes (pure data, pure decision)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class FaceOutcome:
    """One face's verdict, in the four-outcome vocabulary (F11 ruling 3).

    ``kind`` is "match" | "unknown" | "not_identifiable"; ``person_name`` /
    ``similarity`` are set only for a match. Unavailable is NOT a kind here —
    it's a different object, so a count of outcomes can never accidentally
    include a specialist that didn't run.
    """

    kind: Literal["match", "unknown", "not_identifiable"]
    person_name: str | None = None
    similarity: float | None = None


@dataclass(frozen=True, slots=True)
class FaceUnavailable:
    """The specialist could not run (weights absent, hash pin missed, model
    not loaded, inference failed). ``reason`` goes to the LOG; the text line
    stays privacy-clean ("unavailable: <short reason>" with no paths).

    ``kind`` completes the four-outcome vocabulary (F11 ruling 3):
    unavailable is A CLASS, never a score — an outcome of this type can't
    carry a similarity at all."""

    reason: str
    kind: Literal["unavailable"] = "unavailable"


def passes_quality_gate(*, face_px: float, score: float, min_px: int, min_score: float) -> bool:
    """The F11 gate: minimum face size AND minimum SCRFD score.

    Both edges are inclusive: a 40-px face at 0.6 passes (``face_min_size_px``
    default is "borderline identifiable", the point is that config moves it).
    Both knobs come from config by the caller — this function takes values,
    never reads Settings, so it stays pure.
    """
    return face_px >= min_px and score >= min_score


def classify_face_outcome(
    *,
    face_px: float,
    scrfd_score: float,
    match: dict[str, Any] | None,
    min_px: int,
    min_score: float,
) -> FaceOutcome:
    """F11 ruling 3 as a pure function: gate first, then the gallery.

    A crop that FAILS the gate is ``not_identifiable`` even when it also has
    no match — that is the S2-driver rule; ordering the checks the other way
    ("no match first") would emit ``unknown`` for the tiny/night face. A
    gate-passing crop with a gallery match is a match; without one, unknown.
    ``match`` is ``face_recognition_service.match_face``'s dict (or None if
    the gallery is empty/unqueried — treated as no match, which is honest:
    an empty gallery genuinely means "no known person here").
    """
    if not passes_quality_gate(
        face_px=face_px, score=scrfd_score, min_px=min_px, min_score=min_score
    ):
        return FaceOutcome(kind="not_identifiable")
    if match and match.get("matched") and match.get("person_name"):
        return FaceOutcome(
            kind="match",
            person_name=str(match["person_name"]),
            similarity=match.get("similarity"),
        )
    return FaceOutcome(kind="unknown")


# ---------------------------------------------------------------------------
# Texts (spec §6 privacy: names, percents, counts — no bytes, no paths)
# ---------------------------------------------------------------------------


def face_text(outcomes: Sequence[FaceOutcome | FaceUnavailable]) -> str:
    """One census line: names + percents for matches, counts for the rest.

    Zero faces is a REAL observation ("0 faces detected"), distinct from
    unavailable. Any unavailable entry degrades the whole line — a partial
    census (3 of 5 frames) must never read like a complete one.
    """
    if any(isinstance(o, FaceUnavailable) for o in outcomes):
        reason = next(o.reason for o in outcomes if isinstance(o, FaceUnavailable))  # type: ignore[union-attr]
        return f"{UNAVAILABLE}: face specialist did not run ({reason})"
    if not outcomes:
        return "0 faces detected"

    parts: list[str] = []
    matches = [o for o in outcomes if o.kind == "match"]
    unknown = sum(1 for o in outcomes if o.kind == "unknown")
    not_ident = sum(1 for o in outcomes if o.kind == "not_identifiable")
    for m in matches:
        pct = f" ({int((m.similarity or 0.0) * 100)}% match)"
        parts.append(f"known person {m.person_name}{pct}")
    if unknown:
        parts.append(f"{unknown} unknown face(s)")  # gate-PASSED only, by construction
    if not_ident:
        parts.append(f"{not_ident} face(s) not identifiable (too small or low quality)")
    return "; ".join(parts)


def plate_text(results: Sequence[Any], matches: Sequence[Any]) -> str:
    """``ABC123 - household vehicle (Dad's car)`` / ``XYZ789 - not a household
    plate``. The plate string itself is privacy-safe (it's already on the
    vehicle) — the household NAME is what the VLM needs to flip a verdict."""
    if any(isinstance(r, str) and r == UNAVAILABLE for r in results):
        return f"{UNAVAILABLE}: plate specialist did not run"
    if not results:
        return "0 license plates detected"
    by_text = {getattr(m, "text", None): m for m in matches}
    parts = []
    for r in results:
        text = getattr(r, "text", str(r))
        match = by_text.get(text)
        if match is not None and getattr(match, "matched", False):
            who = (
                getattr(match, "member_name", None)
                or getattr(match, "vehicle_id", None)
                or "household"
            )
            parts.append(f"{text} - household vehicle ({who})")
        else:
            parts.append(f"{text} - not a household plate")
    return "; ".join(parts)


def reid_text(matches: Sequence[Any] | None, unavailable_reason: str | None) -> str:
    """Honesty line first: a cross-space score would be a LIE, not a value.

    The household store (PersonEmbedding) holds CLIP-768 vectors
    (reid_service.generate_embedding -> clip_client). The resident Triton
    `reid` model is OSNet-512. Neither cosine is meaningful; numpy would
    raise ValueError on the dot product before the result mattered. Until
    the ledgered follow-up lands (re-enroll in one space, or swap the
    incumbent for PersonViT/CLIP-ReID — rev 7 candidate), the line reports
    the gap instead of a number.
    """
    if unavailable_reason:
        return f"{UNAVAILABLE}: re-ID specialist did not run ({unavailable_reason})"
    if matches is None:
        return f"{UNAVAILABLE}: re-ID specialist did not run ({CROSS_SPACE_REASON})"
    if not matches:
        return "no known-person re-ID matches"
    parts = []
    for m in matches:
        name = getattr(m, "member_name", None) or getattr(m, "person_name", None) or "known person"
        sim = getattr(m, "similarity", None)
        pct = f" ({int(sim * 100)}% match)" if isinstance(sim, float) else ""
        parts.append(f"matches household member {name}{pct}")
    return "; ".join(parts)


# ---------------------------------------------------------------------------
# Face leg collection (SCRFD -> align -> embed -> gallery match)
# ---------------------------------------------------------------------------


def _face_frames(frame_paths: Sequence[Any]) -> list[Any]:
    """FrameRef-like items or plain paths -> a uniform list (duck-typed
    .file_path, exactly like vlm_analyzer's FrameRef handling)."""
    out = []
    for item in frame_paths:
        if isinstance(item, str):
            out.append(item)
        elif getattr(item, "file_path", None):
            out.append(item.file_path)
    return out


def _face_handles() -> tuple[dict[str, Any], dict[str, Any]] | None:
    """The two loaded face-leg handles, or None when the leg can't run.

    The private-dict read is the shipped resident-model pattern (what
    enrichment uses for `stgcn-plus-plus`); the rows are resident
    (`enabled: true`), so this is a membership read, never a load trigger.
    A deploy without the two ONNX files has no entries (their load raised
    at boot and the manager kept going) — F12's degradation path, deploy-
    side, never a batch failure."""
    from backend.services.model_zoo import get_model_manager

    loaded = get_model_manager()._loaded_models
    det = loaded.get("face-detector-scrfd")
    rec = loaded.get("face-recognizer")
    if det is None or rec is None:
        return None
    return det, rec


async def _collect_face_texts(
    frame_paths: Sequence[Any],
    *,
    settings: Settings,
    gallery: Any,
    session: AsyncSession | None,
) -> list[FaceOutcome | FaceUnavailable]:
    """The real face pipeline. Every failure path returns FaceUnavailable —
    the caller's text is then "unavailable: …", never a raise, never a
    silently missing key (spec §6, F11 ruling 1)."""
    from PIL import Image

    from backend.services import face_recognizer_loader as frl

    paths = _face_frames(frame_paths)
    handles = _face_handles() if paths else None
    if handles is None:
        return [
            FaceUnavailable(
                "no key frames available"
                if not paths
                else "face weights not loaded (absent files fail the hash "
                "pin / CPU ONNX extras not installed — deploy-side, not a "
                "verdict failure)"
            )
        ]
    det_handle, rec_handle = handles

    min_px = settings.face_min_size_px
    threshold = settings.face_scrfd_threshold
    loop = asyncio.get_running_loop()
    outcomes: list[FaceOutcome | FaceUnavailable] = []
    probe_ids: set[str] = set()
    readable = False

    for path in paths:
        try:
            image = Image.open(path)
            image.load()
        except OSError:
            continue  # a missing frame file is not "unavailable", just nothing to see
        readable = True

        try:
            faces = await loop.run_in_executor(
                None,
                functools.partial(
                    frl.detect_faces, det_handle["session"], image, threshold=threshold
                ),
            )
        except frl.FaceRecognizerError as e:
            outcomes.append(FaceUnavailable(f"face detection failed: {e}"))
            continue

        for face in faces:
            if face.landmarks is None:
                outcomes.append(FaceOutcome(kind="not_identifiable"))
                continue
            try:
                crop = await loop.run_in_executor(None, frl.align_face_crop, image, face.landmarks)
                vector = await loop.run_in_executor(
                    None, frl.extract_face_embedding, rec_handle["session"], crop
                )
            except frl.FaceRecognizerError as e:
                outcomes.append(FaceUnavailable(f"face embedding failed: {e}"))
                continue
            probe_ids.add(str(rec_handle.get("model_id", "")))

            x1, y1, x2, y2 = face.bbox
            face_px = min(x2 - x1, y2 - y1)
            match = None
            if session is not None:
                try:
                    match = await gallery(session, vector, settings.face_match_threshold)
                except Exception as e:
                    # the LEG (honest), and never a stale/garbled score
                    return [FaceUnavailable(f"gallery query failed: {e}")]
            outcomes.append(
                classify_face_outcome(
                    face_px=face_px,
                    scrfd_score=face.score,
                    match=match,
                    min_px=min_px,
                    min_score=threshold,
                )
            )

    if not outcomes and not readable:
        # Nothing could be observed at all — that is "the specialist did not
        # run", NOT "0 faces" (which is a real observation the VLM may act on).
        return [FaceUnavailable("no key frame readable")]

    if probe_ids:
        # F11 ruling 2's gallery half: probe ids vs stored ids must agree, or
        # every stored vector is a different space and NO score is honest.
        try:
            gallery_ids = await _gallery_model_ids(session)
        except Exception as e:
            return [FaceUnavailable(f"gallery unreadable: {e}")]
        if gallery_ids and gallery_ids != probe_ids:
            return [
                FaceUnavailable(
                    "unavailable (re-enroll): gallery embeddings carry a "
                    f"different face-model id {sorted(gallery_ids)} than the "
                    f"loaded weights {sorted(probe_ids)}"
                )
            ]
    return outcomes


async def _gallery_model_ids(session: AsyncSession | None) -> set[str]:
    """Distinct model ids stored on the gallery's vectors (F11 ruling 2).

    The FaceEmbedding.model_id column ships with the enrollment work (it
    needs a migration); until it exists this returns an empty set, which
    reads as "gallery carries no ids" — the conservative direction: the
    specialist keeps working, and the mismatch rule activates the day the
    column lands. (Pinned by test so the rule can't silently vanish.)
    """
    if session is None:
        return set()
    from sqlalchemy import text

    try:
        result = await session.execute(text("SELECT DISTINCT model_id FROM face_embeddings"))
    except Exception:
        # No column yet (pre-migration DB) / table missing in a minimal test
        # schema: carry no ids rather than raising into the caller.
        return set()
    return {str(row[0]) for row in result if row[0]}


async def collect_face_text(
    *,
    frame_paths: Sequence[Any],
    settings: Settings,
    gallery: Any = None,
    session: AsyncSession | None = None,
) -> str:
    """The face specialist's one line. ``gallery`` is injectable
    (async (session, vector, threshold) -> match dict); the default is the
    real matcher. ``session=None`` is legitimate in tests and degraded
    deploys — matches are then None, i.e. good crops read "unknown"."""
    try:
        if gallery is None:
            gallery = _default_gallery_match
        outcomes = await _collect_face_texts(
            frame_paths, settings=settings, gallery=gallery, session=session
        )
        return face_text(outcomes)
    except Exception as e:
        logger.warning("face specialist failed", exc_info=True)
        return f"{UNAVAILABLE}: face specialist did not run ({e})"


async def _default_gallery_match(
    session: AsyncSession, vector: list[float], threshold: float
) -> dict[str, Any] | None:
    from backend.services.face_recognition_service import get_face_recognition_service

    service = get_face_recognition_service()
    return await service.match_face(session, vector, threshold=threshold)


# ---------------------------------------------------------------------------
# Plate leg
# ---------------------------------------------------------------------------


async def collect_plate_text(*, frame_paths: Sequence[Any]) -> str:
    """`fast-alpr` over the key frames + household-vehicle lookup.

    The [alpr] extra is optional — the sandbox/CI truth is the package is
    absent (fast_alpr_loader raises FastALPRError) and this line becomes
    "unavailable: …", which is the ruling's degradation, not a failure.
    The LOAD comes before the empty-frames shortcut: with the package absent
    the specialist never ran, and "0 license plates detected" over frames
    that were never looked at would be a lie."""
    paths = _face_frames(frame_paths)
    try:
        import numpy as np
        from PIL import Image

        from backend.services.fast_alpr_loader import load_fast_alpr, run_fast_alpr

        alpr = await load_fast_alpr("")
        if not paths:
            return "0 license plates detected"
        results: list[Any] = []
        for path in paths:
            try:
                image = np.asarray(Image.open(path).convert("RGB"))
            except OSError:
                continue
            results.extend(await run_fast_alpr(alpr, image))
        if not results:
            return "0 license plates detected"
        matches = await _match_plate_vehicles([getattr(r, "text", "") for r in results])
        return plate_text(results, matches)
    except Exception as e:
        logger.info("plate specialist unavailable", exc_info=True)
        return f"{UNAVAILABLE}: plate specialist did not run ({e})"


async def _match_plate_vehicles(plate_texts: Sequence[str]) -> list[Any]:
    """Household-vehicle lookup per plate. No session here (the stage runs
    OUTSIDE the analyzer's sessions — same no-session-across-the-VLM-call
    doctrine), so this opens its own, read-only, and a DB that's down just
    means every plate reads "not a household plate"… except that would be a
    LIE, so the caller keeps the plates un-matched and plate_text says so.
    Returns [] honestly on any failure; plate_text then renders every plate
    with an explicit "not a household plate" — the safe direction is checked
    by a pin below, not assumed: unknown-vs-known flips verdicts, and an
    unknown plate at night is the suspicious case, so a false "household"
    (suppression) is the dangerous lie. Never claiming household IS safe."""
    if not plate_texts:
        return []
    from backend.services.household_matcher import get_household_matcher

    matcher = get_household_matcher()
    matches: list[Any] = []
    from backend.core.database import get_session

    async with get_session() as session:
        for plate in plate_texts:
            if not plate:
                continue
            match = await matcher.match_vehicle(
                license_plate=plate,
                vehicle_embedding=None,
                vehicle_type="car",
                color=None,
                session=session,
            )
            if match is not None:
                matches.append(
                    _PlateMatch(
                        text=plate, matched=True, member_name=getattr(match, "member_name", None)
                    )
                )
    return matches


@dataclass(frozen=True, slots=True)
class _PlateMatch:
    """The tiny shape plate_text consumes (HouseholdMatch lacks the plate
    text itself, so we pair it here)."""

    text: str
    matched: bool
    member_name: str | None = None


# ---------------------------------------------------------------------------
# Re-ID leg
# ---------------------------------------------------------------------------


async def collect_reid_text() -> str:
    """F11 ruling 4 / F12: refuse the cross-space score, ledger the gap.

    The two candidate probe sources both fail the same-space test TODAY:
    - the resident Triton `reid` model emits OSNet-512 (the residency set's
      one GPU specialist); the household PersonEmbedding store holds
      CLIP-768 vectors (generate_embedding -> clip_client) — numpy's dot
      raises before a score even exists, and even padded it would be noise;
    - reid_service.generate_embedding IS the store's space (CLIP-768), but
      it requires a person crop per key frame (the YOLO26 detections' boxes
      live in the analyzer's detections list, not passed here yet) and —
      decisive for the ledger — the clip client's `/clip` router is RETIRED
      in vlm residency, so in vlm mode it can't produce a probe at all.

    So the honest line is the space-gap sentence. The day the store is
    re-enrolled in one space (or swapped to PersonViT/CLIP-ReID, rev 7),
    this function learns to probe + match + report real similarities, and
    the sentence goes away — pinned by test to say exactly what's missing.
    """
    return reid_text(matches=None, unavailable_reason=CROSS_SPACE_REASON)


# ---------------------------------------------------------------------------
# The stage entry point (vlm_analyzer calls exactly this)
# ---------------------------------------------------------------------------

#: Specialist keys the snapshot/prompt carries. The set is stable — a
#: specialist that can't run still gets its key with an "unavailable" value
#: so the prompt shows the gap per specialist (F11: keys always exist).
#: Threat is deliberately absent: the F12 call (ledgered) is NOT to include
#: the current detector — its card reports an identical 83.0% recall for
#: every class on an unnamed dataset and ships research-only; published
#: CCTV weapon AP50 is 57.4 and collapses to 3.7 across datasets.
#: GATEWAY_ENABLE_THREAT stays false. Weapon hints return as a rev 7 YOLOE-26
#: feature gated on hand/arm overlap.
SPECIALIST_KEYS = frozenset({"faces", "plates", "person_reid"})


async def collect_specialist_outputs(
    *,
    key_frame_paths: Sequence[Any],
    settings: Settings,
    detections: Sequence[Any] | None = None,  # noqa: ARG001 - re-ID crop carrier
    session: AsyncSession | None = None,
    face_gallery: Any = None,
    run_threat: bool = False,
) -> dict[str, str]:
    """One short text per specialist, over the selector's picks.

    ``key_frame_paths`` are FrameRefs from key_frame_selector (duck-typed
    .file_path); plain paths work too. ``detections`` is accepted (and
    future-consumed by the re-ID crop path) but unused by the three legs
    today — face detects its own crops, plates OCR whole frames. Runs
    concurrently; every leg self-degrades (they each catch their own world)
    and the gather wraps one more belt so even a bug here cannot fail the
    batch — the absolute floor is all-unavailable keys.

    ``session`` is the analyzer's session-1: the face leg needs it for the
    gallery; the plate/re-ID legs do not. (The stage runs BEFORE the VLM
    call but inside the read phase, so this doesn't stretch the session
    across the 25 s read budget.)

    ``run_threat`` exists so the rev-7 weapon-hint slot has a wiring point
    without shipping the detector: when True and a backend threat consumer
    exists, a fourth key appears; default False per the F12 call.
    """
    faces_task = collect_face_text(
        frame_paths=key_frame_paths,
        settings=settings,
        gallery=face_gallery,
        session=session,
    )
    plates_task = collect_plate_text(frame_paths=key_frame_paths)
    reid_task = collect_reid_text()
    tasks = {"faces": faces_task, "plates": plates_task, "person_reid": reid_task}
    if run_threat:
        tasks["threat"] = collect_threat_text(frame_paths=key_frame_paths)
    try:
        results = await asyncio.gather(*tasks.values(), return_exceptions=False)
        return dict(zip(tasks.keys(), results, strict=True))
    except Exception:
        logger.warning("specialist stage failed as a whole", exc_info=True)
        return dict.fromkeys(tasks, f"{UNAVAILABLE}: specialist stage error")


async def collect_threat_text(*, frame_paths: Sequence[Any]) -> str:  # noqa: ARG001
    """Rev 7 slot, not shipped: no backend consumer exists today (the Triton
    threat model is only reachable from the gateway side, and the F12 call
    is to keep it off). The function exists so the slot and its absence are
    both explicit and testable — the key is simply not emitted by default."""
    return f"{UNAVAILABLE}: threat detector not included (F12 call; see ledger)"
