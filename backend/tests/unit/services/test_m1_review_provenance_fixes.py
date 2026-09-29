"""M1 code-review fixes: every stored vector scores only against its own space.

ABOUTME: The M1 milestone review (2026-09-27) found six places where the F11
provenance rule the re-ID swap installed was enforced at ONE reader and
skipped at another - the same defect class the swap exists to kill. Each test
here exercises the SHIPPED path, not a unit of the guard: a real caller whose
belt never reached the comparison. All twelve went red first against the
reviewed head (8da6f2c8); four of those reds were my own wrong fixtures,
caught by reading each failure reason before writing any code, and the shapes
below are the real ones. Each test names the file:line the review reported.

Fixes covered:
- F-A entities.py:708           /entities/matches/{id} dropped the query's belt
- F-E face_recognition_service  match_face scored rows without reading model_id
- F-F face_recognition.py:1257  client-vector match trusted an unnamed space
- F-D household_matcher:290     SIMILARITY_THRESHOLD stuck at the CLIP-era 0.85
- F-B face_recognition.py:534   enrollment ignored detection.bbox_*

F-C (the enrichment tier's _run_household_matching reader, which passed no
model_id) is not covered here any more: R8 S2 deleted enrichment_pipeline
outright, so that reader has no code to guard. The F11 rule it enforced is
still pinned on the live readers — the household matcher suite and
test_person_vector_provenance.py.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest

BELT = "osnet-ain-x1-0@osnet_ain_x1_0_msmt17@8a07e8da3894"
SENTINEL = "legacy-unknown-provenance"
OTHER_BELT = "some-other-weights@v1@deadbeefcafe"


def _unit(values: list[float]) -> np.ndarray:
    arr = np.array(values, dtype=np.float32)
    return arr / np.linalg.norm(arr)


# ---------------------------------------------------------------------------
# F-E - match_face must read the gallery's provenance, not just its bytes
# ---------------------------------------------------------------------------


class _FakeFaceRow:
    def __init__(self, person_id: int, name: str, vector: list[float], model_id: str) -> None:
        self.id = person_id
        self.embedding = np.array(vector, dtype=np.float32).tobytes()
        self.model_id = model_id
        self.person = SimpleNamespace(id=person_id, name=name, is_household_member=True)


class _FakeFaceSession:
    """Answers the gallery SELECT with rows carrying model_id."""

    def __init__(self, rows: list[_FakeFaceRow]) -> None:
        self._rows = rows
        self.execute_calls = 0

    async def execute(self, _stmt: Any) -> Any:
        self.execute_calls += 1
        rows = self._rows

        class _Scalars:
            def all(self) -> list[_FakeFaceRow]:
                return rows

        class _Result:
            def scalars(self) -> _Scalars:
                return _Scalars()

        return _Result()


@pytest.mark.asyncio
async def test_match_face_never_scores_a_sentinel_row() -> None:
    """A pre-swap gallery row is NEVER scored, even when its bytes align.

    F11: an unprovenanced vector gets "unavailable", not a score. Before the
    fix this returned matched=True with a perfect similarity computed from
    bytes the provenance rule was never consulted about.
    """
    from backend.services.face_recognition_service import FaceRecognitionService

    vector = [1.0, 0.0, 0.0, 0.0]
    service = FaceRecognitionService()
    session = _FakeFaceSession([_FakeFaceRow(1, "Alice", vector, SENTINEL)])

    result = await service.match_face(session, _unit(vector), threshold=0.5, model_id=BELT)

    assert result["matched"] is False
    assert result.get("unavailable") is True
    assert result["similarity"] == 0.0


@pytest.mark.asyncio
async def test_match_face_never_scores_a_foreign_space_row() -> None:
    from backend.services.face_recognition_service import FaceRecognitionService

    vector = [1.0, 0.0, 0.0, 0.0]
    service = FaceRecognitionService()
    session = _FakeFaceSession([_FakeFaceRow(1, "Alice", vector, OTHER_BELT)])

    result = await service.match_face(session, _unit(vector), threshold=0.5, model_id=BELT)

    assert result["matched"] is False
    assert result.get("unavailable") is True


@pytest.mark.asyncio
async def test_match_face_still_matches_same_space_and_honors_threshold() -> None:
    """The guard must not cost the honest path its answer."""
    from backend.services.face_recognition_service import FaceRecognitionService

    vector = [1.0, 0.0, 0.0, 0.0]
    service = FaceRecognitionService()
    session = _FakeFaceSession([_FakeFaceRow(1, "Alice", vector, BELT)])

    result = await service.match_face(session, _unit(vector), threshold=0.5, model_id=BELT)

    assert result["matched"] is True
    assert result["person_name"] == "Alice"
    assert result["similarity"] > 0.99


@pytest.mark.asyncio
async def test_match_face_mixed_gallery_scores_only_the_own_space_row() -> None:
    """A sentinel row that is a BETTER byte-match must not win, and must not
    be counted as "no match found at X" - the space is not comparable."""
    from backend.services.face_recognition_service import FaceRecognitionService

    own = [0.0, 1.0, 0.0, 0.0]  # same-space row, similarity 1.0 with probe
    other = [1.0, 0.0, 0.0, 0.0]  # foreign row, byte-identical to the probe
    service = FaceRecognitionService()
    session = _FakeFaceSession(
        [
            _FakeFaceRow(1, "Foreign", other, SENTINEL),
            _FakeFaceRow(2, "Alice", own, BELT),
        ]
    )

    result = await service.match_face(session, _unit(own), threshold=0.5, model_id=BELT)

    assert result["matched"] is True
    assert result["person_name"] == "Alice"


@pytest.mark.asyncio
async def test_match_face_probe_without_a_belt_is_unavailable_not_a_score() -> None:
    """A caller that cannot say what computed its vector gets no score."""
    from backend.services.face_recognition_service import FaceRecognitionService

    vector = [1.0, 0.0, 0.0, 0.0]
    service = FaceRecognitionService()
    session = _FakeFaceSession([_FakeFaceRow(1, "Alice", vector, BELT)])

    result = await service.match_face(session, _unit(vector), threshold=0.5)

    assert result["matched"] is False
    assert result.get("unavailable") is True
    assert result["similarity"] == 0.0


# ---------------------------------------------------------------------------
# F-F - the client-vector face match cannot trust an unnamed space (D-1 twin)
# ---------------------------------------------------------------------------


def test_face_match_endpoint_is_retired_410() -> None:
    """POST /face-events/match answers 410 Gone, always.

    A vector the server did not compute carries no trustworthy provenance:
    scoring it either crosses spaces or trusts a client-claimed model_id,
    which is no trust anchor. This is D-1's posture on the household twin
    (routes/household_matcher.py:72) mirrored onto the face side, and it is
    why the endpoint is retired rather than patched to "refuse to score".
    """
    from fastapi import HTTPException

    from backend.api.routes import face_recognition as fr
    from backend.api.schemas.face_recognition import FaceMatchRequest

    req = FaceMatchRequest(embedding=[0.0] * 512)
    with pytest.raises(HTTPException) as exc_info:
        import asyncio

        asyncio.run(fr.match_face(req, session=None))  # type: ignore[arg-type]

    assert exc_info.value.status_code == 410


def test_face_match_route_is_deprecated_with_a_410_response() -> None:
    """OpenAPI shows the retirement, so a client sees it before calling."""
    from backend.api.routes import face_recognition as fr

    routes = [r for r in fr.router.routes if getattr(r, "path", "").endswith("/face-events/match")]
    assert routes, "the match route disappeared instead of being retired"
    route = routes[0]
    assert route.deprecated is True
    assert 410 in route.responses or "410" in route.responses


# ---------------------------------------------------------------------------
# F-E follow-through - the face LEG must report an uncomparable gallery as
# unavailable, not fold it into "1 unknown face" (an availability gap and a
# real observation are different answers; face_text already keeps them apart
# for every OTHER gap - weights, hash, space_mismatch - the gallery's own
# state was the one hole left by match_face never saying "unavailable").
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_face_leg_reports_unavailable_gallery_not_unknown(tmp_path: Any) -> None:
    import backend.services.vlm_specialists as vs
    from backend.core.config import Settings

    frame = tmp_path / "frame.jpg"
    _write_test_jpeg(frame)

    class _Face:
        bbox = (100, 100, 180, 180)
        landmarks = object()
        score = 0.99

    async def _gallery(session: Any, vector: Any, threshold: Any) -> dict[str, Any]:
        # exactly what match_face now answers when nothing is comparable
        return {
            "matched": False,
            "person_id": None,
            "person_name": None,
            "similarity": 0.0,
            "is_unknown": True,
            "is_household_member": None,
            "unavailable": True,
        }

    import backend.services.face_recognizer_loader as frl

    original_detect = frl.detect_faces
    original_align = frl.align_face_crop
    original_embed = frl.extract_face_embedding
    frl.detect_faces = lambda *_a, **_k: [_Face()]  # type: ignore[assignment]
    frl.align_face_crop = lambda *_a, **_k: object()  # type: ignore[assignment]
    frl.extract_face_embedding = lambda *_a, **_k: [0.0] * 512  # type: ignore[assignment]
    original_handles = frl.get_face_leg_handles
    frl.get_face_leg_handles = lambda: (  # type: ignore[assignment]
        {"session": object()},
        {"session": object(), "model_id": BELT},
    )
    try:
        text = await vs.collect_face_text(
            frame_paths=[frame],
            settings=Settings(),
            gallery=_gallery,
            session=object(),
        )
    finally:
        frl.detect_faces = original_detect  # type: ignore[assignment]
        frl.align_face_crop = original_align  # type: ignore[assignment]
        frl.extract_face_embedding = original_embed  # type: ignore[assignment]
        frl.get_face_leg_handles = original_handles  # type: ignore[assignment]

    assert "unknown" not in text.lower(), text
    assert "unavailable" in text.lower(), text


# ---------------------------------------------------------------------------
# F-A - /entities/matches/{id} must search the query embedding's own partition
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_entities_match_endpoint_threads_the_query_belt() -> None:
    """The endpoint reads the stored query vector, so it KNOWS its space.

    find_matching_entities answers "zero candidates" for a belt-less probe
    (the honest F11 answer), so omitting the belt here is not a graceful
    degrade - it is a permanently empty match list on an endpoint that
    reports 200.
    """
    from datetime import UTC, datetime

    from backend.api.routes import entities as entities_routes
    from backend.api.schemas.entities import EntityTypeFilter
    from backend.services.reid_service import EntityEmbedding

    captured: dict[str, Any] = {}

    query = EntityEmbedding(
        entity_type="person",
        embedding=[0.1] * 512,
        camera_id="cam",
        timestamp=datetime(2026, 9, 27, tzinfo=UTC),
        detection_id="det-1",
        model_id=BELT,
    )

    class _Svc:
        async def get_entity_history(self, **_kw: Any) -> list[EntityEmbedding]:
            return [query]

        async def find_matching_entities(self, **kw: Any) -> list[Any]:
            captured.update(kw)
            return []

    class _Redis:  # the route only needs a truthy client
        pass

    original = entities_routes._get_redis_client
    entities_routes._get_redis_client = _async_value(_Redis())  # type: ignore[assignment]
    try:
        await entities_routes.get_entity_matches(
            detection_id="det-1",
            entity_type=EntityTypeFilter.person,
            threshold=0.7,
            reid_service=_Svc(),  # type: ignore[arg-type]
        )
    finally:
        entities_routes._get_redis_client = original  # type: ignore[assignment]

    assert captured.get("model_id") == BELT


def _async_value(value: Any) -> Any:
    async def _get() -> Any:
        return value

    return _get


# ---------------------------------------------------------------------------
# F-D - the household threshold is the OSNet-space value, from config
# ---------------------------------------------------------------------------


def test_household_matcher_default_threshold_comes_from_config() -> None:
    """D-2 moved the re-ID space to 0.7; this reader must follow it.

    0.85 in the OSNet space is the near-certain-miss setting - it is what
    D-2's own config description names as "would drop every legitimate OSNet
    match". The number must come from settings so one config change moves
    every reader at once.
    """
    from backend.core.config import get_settings
    from backend.services.household_matcher import HouseholdMatcher

    settings = get_settings()
    matcher = HouseholdMatcher()

    assert matcher._similarity_threshold == settings.reid_similarity_threshold


def test_household_matcher_class_default_matches_the_osnet_space() -> None:
    from backend.services.household_matcher import HouseholdMatcher

    assert pytest.approx(0.7) == HouseholdMatcher.SIMILARITY_THRESHOLD


def test_household_matcher_explicit_threshold_still_wins() -> None:
    """Config is the default, not an override of a caller who names a number."""
    from backend.services.household_matcher import HouseholdMatcher

    matcher = HouseholdMatcher(similarity_threshold=0.42)

    assert matcher.similarity_threshold == pytest.approx(0.42)


# ---------------------------------------------------------------------------
# F-B - enrollment honors the detection's bbox
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_enrollment_crops_to_the_detection_bbox(tmp_path: Any) -> None:
    """Two people in one frame: enrolling detection A cannot enroll person B.

    The route's own docstring names bbox_* as the input; the leg was handed
    the whole image and took the highest-confidence face anywhere in it, so
    a bystander's face became the enrolled identity. The crop is the whole
    difference: a leg that only ever sees the person's own box cannot pick
    someone else, and the quality gate then measures THAT person's face.
    """
    import backend.api.routes.face_recognition as fr
    import backend.core.config as config_module
    import backend.services.face_recognizer_loader as frl
    from backend.core.config import Settings

    frame = tmp_path / "frame.jpg"
    _write_test_jpeg(frame, size=(640, 480))

    calls: list[dict[str, Any]] = []

    def _fake_extract(image: Any, **kw: Any) -> tuple[list[float], float, str]:
        calls.append({"size": getattr(image, "size", None)})
        return ([0.0] * 512, 0.9, str(kw["model_id"]))

    original_extract = frl.extract_enrollment_vector
    original_handles = frl.get_face_leg_handles
    original_settings = config_module.get_settings
    frl.extract_enrollment_vector = _fake_extract  # type: ignore[assignment]
    frl.get_face_leg_handles = lambda: (  # type: ignore[assignment]
        {"session": object()},
        {"session": object(), "model_id": BELT},
    )
    config_module.get_settings = lambda: Settings(  # type: ignore[assignment]
        face_scrfd_threshold=0.5, face_min_size_px=20
    )
    try:
        detection = SimpleNamespace(
            id=11,
            file_path=str(frame),
            object_type="person",
            bbox_x=100,
            bbox_y=50,
            bbox_width=200,
            bbox_height=400,
        )
        result = await fr.extract_face_embedding_from_detection(detection)
    finally:
        frl.extract_enrollment_vector = original_extract  # type: ignore[assignment]
        frl.get_face_leg_handles = original_handles  # type: ignore[assignment]
        config_module.get_settings = original_settings  # type: ignore[assignment]

    assert result is not None
    assert calls, "the leg was never called"
    # The crop IS the detection box (100,50)-(300,450) -> 200x400, not the
    # 640x480 frame. That is the whole fix.
    assert calls[-1]["size"] == (200, 400)
    assert result[2] == BELT


@pytest.mark.asyncio
async def test_enrollment_clamps_an_overrunning_bbox(tmp_path: Any) -> None:
    """A detection box that hangs off the frame edge must not crash or skew.

    Tracker boxes routinely exceed the frame; cropping straight past the
    edge would hand the leg a silently different geometry than the box
    names, so the box is clamped to the image instead.
    """
    import backend.api.routes.face_recognition as fr
    import backend.core.config as config_module
    import backend.services.face_recognizer_loader as frl
    from backend.core.config import Settings

    frame = tmp_path / "frame.jpg"
    _write_test_jpeg(frame, size=(640, 480))

    calls: list[dict[str, Any]] = []

    def _fake_extract(image: Any, **kw: Any) -> tuple[list[float], float, str]:
        calls.append({"size": getattr(image, "size", None)})
        return ([0.0] * 512, 0.9, str(kw["model_id"]))

    original_extract = frl.extract_enrollment_vector
    original_handles = frl.get_face_leg_handles
    original_settings = config_module.get_settings
    frl.extract_enrollment_vector = _fake_extract  # type: ignore[assignment]
    frl.get_face_leg_handles = lambda: (  # type: ignore[assignment]
        {"session": object()},
        {"session": object(), "model_id": BELT},
    )
    config_module.get_settings = lambda: Settings(  # type: ignore[assignment]
        face_scrfd_threshold=0.5, face_min_size_px=20
    )
    try:
        detection = SimpleNamespace(
            id=12,
            file_path=str(frame),
            object_type="person",
            bbox_x=100,
            bbox_y=50,
            bbox_width=900,  # runs past 640
            bbox_height=900,  # runs past 480
        )
        await fr.extract_face_embedding_from_detection(detection)
    finally:
        frl.extract_enrollment_vector = original_extract  # type: ignore[assignment]
        frl.get_face_leg_handles = original_handles  # type: ignore[assignment]
        config_module.get_settings = original_settings  # type: ignore[assignment]

    assert calls[-1]["size"] == (640 - 100, 480 - 50)


@pytest.mark.asyncio
async def test_enrollment_without_any_bbox_is_the_logged_weak_path(
    tmp_path: Any, caplog: Any
) -> None:
    """bbox_* is nullable, so "no box" is a real state - distinct from a
    corrupt one. The frame is all there was: enroll from it, but say so
    rather than let it read as the box-scoped path.
    """
    import backend.api.routes.face_recognition as fr
    import backend.core.config as config_module
    import backend.services.face_recognizer_loader as frl
    from backend.core.config import Settings

    frame = tmp_path / "frame.jpg"
    _write_test_jpeg(frame, size=(640, 480))

    calls: list[dict[str, Any]] = []

    def _fake_extract(image: Any, **kw: Any) -> tuple[list[float], float, str]:
        calls.append({"size": getattr(image, "size", None)})
        return ([0.0] * 512, 0.9, str(kw["model_id"]))

    original_extract = frl.extract_enrollment_vector
    original_handles = frl.get_face_leg_handles
    original_settings = config_module.get_settings
    frl.extract_enrollment_vector = _fake_extract  # type: ignore[assignment]
    frl.get_face_leg_handles = lambda: (  # type: ignore[assignment]
        {"session": object()},
        {"session": object(), "model_id": BELT},
    )
    config_module.get_settings = lambda: Settings(  # type: ignore[assignment]
        face_scrfd_threshold=0.5, face_min_size_px=20
    )
    try:
        detection = SimpleNamespace(
            id=13,
            file_path=str(frame),
            object_type="person",
            bbox_x=None,
            bbox_y=None,
            bbox_width=None,
            bbox_height=None,
        )
        result = await fr.extract_face_embedding_from_detection(detection)
    finally:
        frl.extract_enrollment_vector = original_extract  # type: ignore[assignment]
        frl.get_face_leg_handles = original_handles  # type: ignore[assignment]
        config_module.get_settings = original_settings  # type: ignore[assignment]

    assert result is not None, "a box-less detection is still enrollable"
    assert calls[-1]["size"] == (640, 480)


def test_a_useless_bbox_is_refused_not_falled_back(tmp_path: Any) -> None:
    """A box that names no area is corrupt input, not "no box".

    Falling back to the whole frame here would resurrect the exact bug this
    crop removes, behind data that claims to carry a position.
    """
    from PIL import Image

    import backend.api.routes.face_recognition as fr

    image = Image.new("RGB", (640, 480))
    detection = SimpleNamespace(id=14, bbox_x=100, bbox_y=50, bbox_width=0, bbox_height=0)
    with pytest.raises(RuntimeError, match="no usable bbox"):
        fr._crop_to_detection_bbox(image, detection)


def _write_test_jpeg(path: Any, size: tuple[int, int] = (640, 480)) -> None:
    from PIL import Image

    Image.new("RGB", size, color=(120, 130, 140)).save(path, format="JPEG")
