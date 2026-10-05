# TARGET-MODULE: backend.services.face_recognition_service
"""Battery AT — campaign #44 kill battery for backend/services/face_recognition_service.py.

Style (proven on AR/AS): every observable the entered branch WRITES is
asserted, not merely "reached" (see [[entered-branch-must-assert-every-
observable-it-writes]]).

- DB helpers: a recording Session whose pins are the FULL normalized
  statement STRING + compiled PARAMS dict per execute; a None statement
  RAISES TypeError mirroring SQLAlchemy; results POSITIONAL.  Exact-shape
  pins measured THIS session: '.where(None)' COMPILES to 'WHERE NULL',
  'id == None' to 'IS NULL', 'limit(None)' renders 'LIMIT -1',
  'offset(None)' DROPS the clause, 'order_by(None)' drops ORDER BY,
  'select(None).select_from(sub)' -> 'SELECT NULL AS anon_1 FROM (...
  anon_2)' (the inner subquery RENUMBERS to anon_2 — measured), and
  'select(None)' WITH selectinload RAISES ArgumentError at compile.
- ORM write paths: the added FaceEmbedding is pinned FIELD-BY-FIELD
  against non-default values (person_id=7 / 4, embedding bytes,
  quality_score=0.55 / 0.75, source_image_path="/src.jpg"); an unflushed
  SQLAlchemy model reads an unset / =None kwarg back as None (measured),
  so the drop and =None ctor families die on value equality.
  session.refresh is REAL SQLAlchemy inspection (sqlalchemy.inspect), so
  refresh(None) raises NoInspectionAvailable exactly as the real session
  does (measured).
- Logging: module logs via %-style (method, ARGS, kwargs) FULL tuple
  equality — rename/XX/UPPER/lower/None/arg-drop/arg-None twins die
  ([[fragment-count-asserts-pass-xx-mutants]]).  Multi-literal messages
  were re-extracted from the AST so the pins are the JOINED constants
  byte-exact.
- float32 numerics measured THIS session (probe [0.6,0.8] normalizes to
  bytes 9a99193fcdcc4c3f == np.float32 literal, and cos(raw[3,4]) == 1.0
  exactly, so a tie keeps the FIRST row — kills the '>=' best-match twin
  by NAME): cos([3,4],[4,3]) == 0.9599999785423279; cos([1,0], [0.6,0.8])
  == 0.6000000238418579 (strictly BELOW the 0.68 default — kills the
  'and'->'or' gate twin); a float64 probe scores 1.000000023841858 where
  the f32 cast scores 1.0 (kills the astype(None) twin at threshold 1.0);
  antipodal cos is exactly -1.0 which is NOT > the -1.0 init (kills the
  '>=' compare twin, the -2.0 init twin via a matched-dict flip at
  threshold -1.0, and the best_match='' twin via TypeError on ''
  subscript); a zero probe stays 0.0 through the cosine guard while the
  'norm >= 0' twin divides 0/0 -> nan -> best_match never set -> dict
  similarity -1.0.  The match_face query-normalize twins ('norm > 1',
  '/ -> *') were brute-forced over 200k random f32 pairs: they diverge
  ONLY at the last-bit (ULP) level, so NO environment-independent pin
  exists -> adjudicated EQUIV, not pinned.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any
from unittest import mock
from unittest.mock import AsyncMock

import numpy as np
import pytest
from sqlalchemy import inspect as sqlinspect

import backend.services.face_recognition_service as frs
from backend.core.face_provenance import LEGACY_MODEL_ID

# ============================================================================
# Measured constants
# ============================================================================

INIT_MSG = "FaceRecognitionService initialized with threshold=%.2f"
GKP_WARN_MSG = "Cannot add embedding: person %d not found"
ADDED_MSG = "Added face embedding for person %s (id=%d, quality=%.2f)"
NO_GALLERY_MSG = "No known embeddings in database"
REFUSE_MSG = (
    "Face match refused: the probe carries no provenance, so no "
    "comparison against the gallery is honest (F11)"
)
UNAVAIL_MSG = (
    "Face match unavailable: %d gallery row(s) carry no vector in space %s (re-enroll needed)"
)
SCORED_MSG = (
    "Face match scored %d comparable row(s), skipped %d uncomparable row(s) (different model_id)"
)
MATCHED_MSG = "Face matched to %s (id=%d) with similarity %.3f"
NOMATCH_MSG = "No match found (best similarity: %.3f, threshold: %.2f)"
RETRIEVED_MSG = "Retrieved %d appearances for person %d (total: %d)"
CREATED_MSG = "Created embedding for person %s from face event %d (quality=%.2f)"
IDENTIFIED_MSG = "Identified face event %d as person %s (id=%d)"

GKP_SELECT = (
    "SELECT known_persons.id, known_persons.name, "
    "known_persons.is_household_member, known_persons.notes, "
    "known_persons.created_at, known_persons.updated_at FROM known_persons "
    "WHERE known_persons.id = :id_1"
)
ALL_EMB_SELECT = (
    "SELECT face_embeddings.id, face_embeddings.person_id, "
    "face_embeddings.embedding, face_embeddings.model_id, "
    "face_embeddings.quality_score, face_embeddings.source_image_path, "
    "face_embeddings.created_at FROM face_embeddings"
)
EV_SELECT = (
    "SELECT face_detection_events.id, face_detection_events.camera_id, "
    "face_detection_events.timestamp, face_detection_events.bbox, "
    "face_detection_events.embedding, face_detection_events.model_id, "
    "face_detection_events.matched_person_id, "
    "face_detection_events.match_confidence, "
    "face_detection_events.is_unknown, face_detection_events.quality_score, "
    "face_detection_events.age_estimate, "
    "face_detection_events.gender_estimate, "
    "face_detection_events.created_at FROM face_detection_events "
    "WHERE face_detection_events.id = :id_1"
)
PR_SELECT = GKP_SELECT
APPEAR_BASE = (
    "SELECT face_detection_events.id, face_detection_events.camera_id, "
    "face_detection_events.timestamp, face_detection_events.bbox, "
    "face_detection_events.embedding, face_detection_events.model_id, "
    "face_detection_events.matched_person_id, "
    "face_detection_events.match_confidence, "
    "face_detection_events.is_unknown, face_detection_events.quality_score, "
    "face_detection_events.age_estimate, "
    "face_detection_events.gender_estimate, "
    "face_detection_events.created_at FROM face_detection_events "
    "WHERE face_detection_events.matched_person_id = :matched_person_id_1 "
)
APPEAR_CAM = "AND face_detection_events.camera_id = :camera_id_1 "
APPEAR_COUNT = (
    "SELECT count(*) AS count_1 FROM (SELECT face_detection_events.id AS id, "
    "face_detection_events.camera_id AS camera_id, "
    "face_detection_events.timestamp AS timestamp, "
    "face_detection_events.bbox AS bbox, "
    "face_detection_events.embedding AS embedding, "
    "face_detection_events.model_id AS model_id, "
    "face_detection_events.matched_person_id AS matched_person_id, "
    "face_detection_events.match_confidence AS match_confidence, "
    "face_detection_events.is_unknown AS is_unknown, "
    "face_detection_events.quality_score AS quality_score, "
    "face_detection_events.age_estimate AS age_estimate, "
    "face_detection_events.gender_estimate AS gender_estimate, "
    "face_detection_events.created_at AS created_at FROM "
    "face_detection_events WHERE face_detection_events.matched_person_id = "
    ":matched_person_id_1 AND face_detection_events.camera_id = :camera_id_1"
    ") AS anon_1"
)
APPEAR_ORDERED = (
    APPEAR_BASE + APPEAR_CAM + "ORDER BY face_detection_events.timestamp "
    "DESC LIMIT :param_1 OFFSET :param_2"
)

F32 = np.float32
N068 = np.array([0.6, 0.8], dtype=F32)
N068_BYTES = N068.tobytes()  # 9a99193fcdcc4c3f, measured == [0.6,0.8]/norm
RAW34_BYTES = np.array([3, 4], dtype=F32).tobytes()
ZERO_BYTES = np.array([0, 0], dtype=F32).tobytes()
HALF_RAW = np.array([0.3, 0.4], dtype=F32)
NEG_BYTES = np.array([-0.6, -0.8], dtype=F32).tobytes()
DIM3_BYTES = np.array([0.6, 0.8, 0.1], dtype=F32).tobytes()
SIM_06 = 0.6000000238418579  # measured cos([1,0], N068) — BELOW 0.68
SIM_96 = 0.9599999785423279  # measured cos(f32[3,4], f32[4,3])
SIM_F64 = 1.000000023841858  # measured unnormalized float64 probe vs N068


def _unknown_dict(similarity: float, unavailable: bool) -> dict[str, Any]:
    return {
        "matched": False,
        "person_id": None,
        "person_name": None,
        "similarity": similarity,
        "is_unknown": True,
        "is_household_member": None,
        "unavailable": unavailable,
    }


# ============================================================================
# Fakes
# ============================================================================


class Result:
    def __init__(self, payload: Any) -> None:
        self._payload = payload

    def scalar_one_or_none(self) -> Any:
        return self._payload

    def scalar(self) -> Any:
        return self._payload

    def scalars(self) -> Result:
        return self

    def all(self) -> list[Any]:
        return list(self._payload)


class Session:
    """Mirrors AsyncSession: a None statement RAISES (SQLAlchemy 'query
    expected'); every accepted statement pins as (normalized-string,
    compiled-params); results POSITIONAL; refresh() runs REAL SQLAlchemy
    inspection so refresh(None) raises NoInspectionAvailable (measured)."""

    def __init__(self, results: list[Any] | None = None) -> None:
        self.results = list(results or [])
        self.queries: list[tuple[str, dict[str, Any]]] = []
        self.added: list[Any] = []
        self.commits = 0

    async def execute(self, query: Any) -> Result:
        if query is None:
            raise TypeError("query expected")
        stmt = query
        norm = " ".join(str(stmt).split())
        self.queries.append((norm, dict(stmt.compile().params)))
        if not self.results:
            raise IndexError("unexpected execute — shipped issues no further queries")
        return Result(self.results.pop(0))

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        self.commits += 1

    async def refresh(self, obj: Any) -> None:
        state = sqlinspect(obj)  # None -> NoInspectionAvailable (measured)
        assert state is not None


class Rec:
    """%-style logger: pins (method, args, kwargs) with FULL tuple equality."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

    def debug(self, *args: Any, **kw: Any) -> None:
        self.calls.append(("debug", args, kw))

    def info(self, *args: Any, **kw: Any) -> None:
        self.calls.append(("info", args, kw))

    def warning(self, *args: Any, **kw: Any) -> None:
        self.calls.append(("warning", args, kw))

    def error(self, *args: Any, **kw: Any) -> None:
        self.calls.append(("error", args, kw))


@contextmanager
def log_rec():
    rec = Rec()
    with mock.patch.object(frs, "logger", rec):
        yield rec


def person(pid: int = 7, name: str = "Ann", household: bool = True) -> Any:
    p = mock.MagicMock()
    p.id = pid
    p.name = name
    p.is_household_member = household
    return p


def emb_row(
    pid: int,
    name: str,
    household: bool,
    blob: bytes,
    model_id: Any,
    row_id: int = 1,
) -> Any:
    """A gallery row shaped like the FaceEmbedding ORM objects
    _get_all_embeddings consumes (person relationship + bytes + provenance)."""
    e = mock.MagicMock()
    e.id = row_id
    e.person = person(pid, name, household)
    e.embedding = blob
    e.model_id = model_id
    return e


def gallery_row(*a: Any, **k: Any) -> Any:
    return emb_row(*a, **k)


class PlainEvent:
    """An event WITHOUT a model_id attribute — exactly what the shipped
    getattr(event, 'model_id', LEGACY) sentinel path reads (measured: the
    2-arg trailing-comma getattr twin RAISES AttributeError here)."""

    def __init__(self, **kw: Any) -> None:
        self.id = 11
        self.embedding = b"EVB"
        self.quality_score = 0.75
        self.is_unknown = True
        self.__dict__.update(kw)


# ============================================================================
# __init__ + cosine_similarity
# ============================================================================


async def test_init_logs_threshold_and_stores_it() -> None:
    svc = frs.FaceRecognitionService.__new__(frs.FaceRecognitionService)
    with log_rec() as rec:
        frs.FaceRecognitionService.__init__(svc, 0.42)
    assert rec.calls == [("info", (INIT_MSG, 0.42), {})]
    assert svc.similarity_threshold == 0.42
    default = frs.FaceRecognitionService.__new__(frs.FaceRecognitionService)
    with log_rec() as rec2:
        frs.FaceRecognitionService.__init__(default)
    assert rec2.calls == [("info", (INIT_MSG, frs.DEFAULT_MATCH_THRESHOLD), {})]
    assert default.similarity_threshold == 0.68


def test_cosine_similarity_exact_values() -> None:
    assert frs.cosine_similarity(np.array([3, 4], dtype=F32), np.array([3, 4], dtype=F32)) == 1.0
    assert frs.cosine_similarity(np.array([3, 4], dtype=F32), np.array([4, 3], dtype=F32)) == SIM_96


def test_cosine_similarity_zero_guard_is_or_not_and() -> None:
    # and-twin lets (zero, nonzero) fall through to 0/0 -> nan.
    zero = np.frombuffer(ZERO_BYTES, dtype=F32)
    assert frs.cosine_similarity(zero, N068) == 0.0
    assert frs.cosine_similarity(N068, zero) == 0.0


# ============================================================================
# get_known_person / _get_all_embeddings (statement pins)
# ============================================================================


async def test_get_known_person_statement_pinned_and_payload_returned() -> None:
    s = Session(results=[person(7, "Ann")])
    svc = frs.FaceRecognitionService.__new__(frs.FaceRecognitionService)
    out = await svc.get_known_person(s, 7)
    assert out.name == "Ann"
    assert s.queries == [(GKP_SELECT, {"id_1": 7})]


async def test_get_all_embeddings_statement_pinned_tuples_exact() -> None:
    s = Session(
        results=[
            [
                gallery_row(7, "Ann", True, N068_BYTES, "m1", row_id=1),
                gallery_row(9, "Zed", False, RAW34_BYTES, None, row_id=2),
            ]
        ]
    )
    svc = frs.FaceRecognitionService.__new__(frs.FaceRecognitionService)
    out = await svc._get_all_embeddings(s)
    assert s.queries == [(ALL_EMB_SELECT, {})]
    assert len(out) == 2
    assert out[0][0] == 7 and out[0][1] == "Ann" and out[0][2] is True
    assert np.array_equal(out[0][3], N068) and out[0][4] == "m1"
    # measured: str(emb.model_id or LEGACY_MODEL_ID) — a None id reads the sentinel
    assert out[1][0] == 9 and out[1][4] == LEGACY_MODEL_ID


# ============================================================================
# add_face_embedding
# ============================================================================


async def test_add_face_embedding_missing_person_warns_pinned() -> None:
    s = Session(results=[None])
    svc = frs.FaceRecognitionService.__new__(frs.FaceRecognitionService)
    with log_rec() as rec:
        out = await svc.add_face_embedding(s, 999, [3, 4])
    assert out is None
    assert s.queries == [(GKP_SELECT, {"id_1": 999})]
    assert rec.calls == [("warning", (GKP_WARN_MSG, 999), {})]
    assert s.added == []


async def test_add_face_embedding_normalizes_stores_and_logs_exact() -> None:
    s = Session(results=[person(7, "Ann")])
    svc = frs.FaceRecognitionService.__new__(frs.FaceRecognitionService)
    with log_rec() as rec:
        out = await svc.add_face_embedding(
            s, 7, [3, 4], quality_score=0.55, source_image_path="/src.jpg", model_id="m1"
        )
    assert out is s.added[0]
    # person lookup used the ACTUAL person_id (None-twin reads id == None ->
    # 'WHERE known_persons.id IS NULL' — measured compile, differs on BOTH
    # the string and the params).
    assert s.queries == [(GKP_SELECT, {"id_1": 7})]
    stored = s.added[0]
    assert stored.person_id == 7
    assert stored.embedding == N068_BYTES  # kills dtype=None / trailing-comma
    # (float64, 16 bytes), np.array(None) (nan scalar, 4 bytes), the
    # '/ -> *' twin (000070410000a041) and embedding=None/byte-drops.
    assert stored.quality_score == 0.55
    assert stored.source_image_path == "/src.jpg"
    assert stored.model_id == "m1"
    assert s.commits == 1
    assert rec.calls == [("info", (ADDED_MSG, "Ann", 7, 0.55), {})]


async def test_add_face_embedding_zero_norm_not_divided() -> None:
    # norm > 1 twin leaves a 0-norm vector UNsplit (0/0 -> nan bytes);
    # norm >= 0 twin divides by zero -> nan bytes 0000c07f0000c07f.
    s = Session(results=[person(7, "Ann")])
    svc = frs.FaceRecognitionService.__new__(frs.FaceRecognitionService)
    with log_rec() as rec:
        await svc.add_face_embedding(s, 7, [0.0, 0.0], quality_score=1.0)
    assert s.added[0].embedding == ZERO_BYTES
    assert rec.calls == [("info", (ADDED_MSG, "Ann", 7, 1.0), {})]


async def test_add_face_embedding_half_norm_vector_normalized() -> None:
    # '> 1' twin stores the RAW half-length bytes 9a99993ecdcccc3e;
    # shipped normalizes to exactly N068 bytes (measured).
    s = Session(results=[person(7, "Ann")])
    svc = frs.FaceRecognitionService.__new__(frs.FaceRecognitionService)
    with log_rec() as rec:
        await svc.add_face_embedding(s, 7, HALF_RAW.tolist(), quality_score=0.9)
    assert s.added[0].embedding == N068_BYTES
    assert s.added[0].embedding != HALF_RAW.tobytes()
    assert rec.calls == [("info", (ADDED_MSG, "Ann", 7, 0.9), {})]


# ============================================================================
# get_person_appearances
# ============================================================================


async def test_get_person_appearances_missing_person_returns_none() -> None:
    svc = frs.FaceRecognitionService.__new__(frs.FaceRecognitionService)
    s = Session()
    with mock.patch.object(svc, "get_known_person", new_callable=AsyncMock) as gk:
        gk.return_value = None
        assert await svc.get_person_appearances(s, 7) is None
    gk.assert_awaited_once_with(s, 7)
    assert s.queries == []


async def test_get_person_appearances_full_filter_count_order_and_log() -> None:
    ev = mock.MagicMock()
    ev.id = 100
    ev.camera_id = "cam"
    ev.camera = None
    ev.timestamp = "TS"
    ev.match_confidence = 0.9
    s = Session(results=[3, [ev]])
    svc = frs.FaceRecognitionService.__new__(frs.FaceRecognitionService)
    with mock.patch.object(svc, "get_known_person", new_callable=AsyncMock) as gk:
        gk.return_value = person(7, "Ann")
        with log_rec() as rec:
            out = await svc.get_person_appearances(s, 7, camera_id="cam")
    assert out is not None
    appearances, total = out
    assert total == 3
    assert appearances == [
        {
            "timestamp": "TS",
            "camera_id": "cam",
            "camera_name": "cam",  # camera relationship None -> id fallback
            "detection_id": 100,
            "confidence": 0.9,
            "thumbnail_url": None,
        }
    ]
    assert s.queries == [
        (APPEAR_COUNT, {"matched_person_id_1": 7, "camera_id_1": "cam"}),
        (
            APPEAR_ORDERED,
            {"matched_person_id_1": 7, "camera_id_1": "cam", "param_1": 50, "param_2": 0},
        ),
    ]
    assert rec.calls == [("debug", (RETRIEVED_MSG, 1, 7, 3), {})]


# ============================================================================
# identify_face_event
# ============================================================================


async def test_identify_face_event_missing_event_raises_after_pinned_query() -> None:
    s = Session(results=[None])
    svc = frs.FaceRecognitionService.__new__(frs.FaceRecognitionService)
    with pytest.raises(ValueError, match="Face event with id 11 not found"):
        await svc.identify_face_event(s, 11, 4)
    assert s.queries == [(EV_SELECT, {"id_1": 11})]


async def test_identify_face_event_creates_embedding_with_pinned_provenance() -> None:
    ev = PlainEvent()
    s = Session(results=[ev, person(4, "Bob", household=False)])
    svc = frs.FaceRecognitionService.__new__(frs.FaceRecognitionService)
    with log_rec() as rec:
        out = await svc.identify_face_event(s, 11, 4)
    assert out == {"success": True, "created_embedding": True}
    assert s.queries == [(EV_SELECT, {"id_1": 11}), (PR_SELECT, {"id_1": 4})]
    new_emb = s.added[0]
    assert new_emb.person_id == 4
    assert new_emb.embedding == b"EVB"
    assert new_emb.quality_score == 0.75
    assert new_emb.source_image_path is None
    # the explicit-None kwarg is SET (kills the source_image_path= drop via
    # the unloaded-attribute set, measured below); an event with NO model_id
    # attribute reads the sentinel — the None twin stores None and the
    # trailing-comma getattr RAISES AttributeError (both measured).
    assert new_emb.model_id == LEGACY_MODEL_ID
    assert "source_image_path" not in sqlinspect(new_emb).unloaded
    assert s.commits == 1
    assert rec.calls == [
        ("info", (CREATED_MSG, "Bob", 11, 0.75), {}),
        ("info", (IDENTIFIED_MSG, 11, "Bob", 4), {}),
    ]


async def test_identify_face_event_low_quality_skips_embedding() -> None:
    ev = PlainEvent(quality_score=0.65)
    s = Session(results=[ev, person(4, "Bob")])
    svc = frs.FaceRecognitionService.__new__(frs.FaceRecognitionService)
    with log_rec() as rec:
        out = await svc.identify_face_event(s, 11, 4)
    assert out == {"success": True, "created_embedding": False}
    assert s.added == []
    assert rec.calls == [("info", (IDENTIFIED_MSG, 11, "Bob", 4), {})]
    assert ev.matched_person_id == 4
    assert ev.is_unknown is False


# ============================================================================
# match_face
# ============================================================================


async def _match(
    svc: Any,
    embedding: Any,
    gallery: list[Any],
    **kw: Any,
) -> tuple[dict, list, Rec]:
    s = Session(results=[gallery])
    with log_rec() as rec:
        out = await svc.match_face(s, embedding, **kw)
    return out, s.queries, rec


def _svc() -> Any:
    return frs.FaceRecognitionService.__new__(frs.FaceRecognitionService)


async def test_match_empty_gallery_is_unknown_not_unavailable() -> None:
    svc = _svc()
    svc._similarity_threshold = 0.68
    out, _, rec = await _match(svc, [0.6, 0.8], [])
    assert out == _unknown_dict(0.0, False)
    assert rec.calls == [("debug", (NO_GALLERY_MSG,), {})]


async def test_match_none_provenance_probe_refused() -> None:
    # 'untrusted_probe = None' (whole-RHS drop) and the 'or'->'and' twin both
    # proceed instead of refusing — the refusal INFO call is the discriminator
    # (the unavailable-fallback DICT is byte-identical on this input).
    svc = _svc()
    svc._similarity_threshold = 0.68
    gallery = [gallery_row(7, "Ann", True, N068_BYTES, "m1")]
    out, _, rec = await _match(svc, [0.6, 0.8], gallery, model_id=None)
    assert out == _unknown_dict(0.0, True)
    assert rec.calls == [("info", (REFUSE_MSG,), {})]


async def test_match_legacy_provenance_probe_refused() -> None:
    svc = _svc()
    svc._similarity_threshold = 0.68
    gallery = [gallery_row(7, "Ann", True, N068_BYTES, LEGACY_MODEL_ID)]
    out, _, rec = await _match(svc, [0.6, 0.8], gallery, model_id=LEGACY_MODEL_ID)
    assert out == _unknown_dict(0.0, True)
    assert rec.calls == [("info", (REFUSE_MSG,), {})]


async def test_match_all_rows_uncomparable_counts_skipped() -> None:
    # one wrong-model row + one wrong-LENGTH row: skipped must be 2 exactly
    # (kills skipped = 1 / += 2 / -= 1 and the comparable twins never even
    # run here — comparable stays 0).
    svc = _svc()
    svc._similarity_threshold = 0.68
    gallery = [
        gallery_row(7, "Ann", True, N068_BYTES, "m2"),
        gallery_row(8, "B", False, DIM3_BYTES, "m1"),
    ]
    out, _, rec = await _match(svc, [0.6, 0.8], gallery, model_id="m1")
    assert out == _unknown_dict(0.0, True)
    assert rec.calls == [("info", (UNAVAIL_MSG, 2, "m1"), {})]


async def test_match_mixed_gallery_first_tie_and_exact_counts() -> None:
    # 2 comparable + 2 skipped; both comparables score EXACTLY 1.0 so '>='
    # would steal the tie to Bob; threshold 1.0 (== shipped sim) so the
    # '> threshold' twin loses the match.
    svc = _svc()
    svc._similarity_threshold = 0.68
    gallery = [
        gallery_row(7, "Ann", True, N068_BYTES, "m1"),
        gallery_row(8, "Bob", False, RAW34_BYTES, "m1"),
        gallery_row(9, "Skip", True, N068_BYTES, "m2"),
        gallery_row(10, "Dim", False, DIM3_BYTES, "m1"),
    ]
    out, _, rec = await _match(svc, [0.6, 0.8], gallery, model_id="m1", threshold=1.0)
    assert out == {
        "matched": True,
        "person_id": 7,
        "person_name": "Ann",
        "similarity": 1.0,
        "is_unknown": False,
        "is_household_member": True,
        "unavailable": False,
    }
    assert rec.calls == [
        ("debug", (SCORED_MSG, 2, 2), {}),
        ("debug", (MATCHED_MSG, "Ann", 7, 1.0), {}),
    ]


async def test_match_below_threshold_reports_similarities() -> None:
    # measured: cos([1,0], N068) == 0.6000000238418579 < 0.68 — the 'and'->
    # 'or' gate twin flips to MATCHED here because best_match IS set.
    svc = _svc()
    svc._similarity_threshold = 0.68
    gallery = [gallery_row(7, "Ann", True, N068_BYTES, "m1")]
    out, _, rec = await _match(svc, np.array([1.0, 0.0], dtype=F32), gallery, model_id="m1")
    assert out == _unknown_dict(SIM_06, False)
    assert rec.calls == [("debug", (NOMATCH_MSG, SIM_06, 0.68), {})]


async def test_match_antipodal_exact_minus_one_keeps_best_match_unset() -> None:
    # similarity -1.0 is NOT > the -1.0 init: shipped never sets best_match,
    # so the gate's 'is not None' guard fails even at threshold -1.0.
    # '>=' twin (sets best_match -> matched dict), '-2.0' init twin (same
    # flip) and best_match='' twin (TypeError on ''["person_id"]) all die.
    svc = _svc()
    svc._similarity_threshold = 0.68
    gallery = [gallery_row(7, "Ann", True, NEG_BYTES, "m1")]
    out, _, rec = await _match(svc, [0.6, 0.8], gallery, model_id="m1", threshold=-1.0)
    assert out == _unknown_dict(-1.0, False)
    assert rec.calls == [("debug", (NOMATCH_MSG, -1.0, -1.0), {})]


async def test_match_default_threshold_used_when_arg_none() -> None:
    # 'is None' -> 'is not None' twin leaves threshold=None -> the gate
    # compares float >= None -> TypeError (RED).  Shipped: 0.6000000238...
    # >= the service's 0.5 -> matched.
    svc = _svc()
    svc._similarity_threshold = 0.5
    gallery = [gallery_row(7, "Ann", True, N068_BYTES, "m1")]
    out, _, rec = await _match(svc, [1.0, 0.0], gallery, model_id="m1", threshold=None)
    assert out == {
        "matched": True,
        "person_id": 7,
        "person_name": "Ann",
        "similarity": SIM_06,
        "is_unknown": False,
        "is_household_member": True,
        "unavailable": False,
    }
    assert rec.calls == [("debug", (MATCHED_MSG, "Ann", 7, SIM_06), {})]


async def test_match_float64_probe_cast_to_float32_scores_exact_one() -> None:
    # astype(None) twin keeps float64 -> similarity 1.000000023841858, not
    # 1.0 (measured); at threshold 1.0 BOTH match, so the dict VALUE pin
    # is what kills.
    svc = _svc()
    svc._similarity_threshold = 0.68
    gallery = [gallery_row(7, "Ann", True, N068_BYTES, "m1")]
    out, _, rec = await _match(
        svc, np.array([0.6, 0.8]), gallery, model_id="m1", threshold=1.0
    )  # float64 array ON PURPOSE (kills any added cast in the else-arm too)
    assert out["similarity"] == 1.0
    assert out["similarity"] != SIM_F64
    assert out["person_name"] == "Ann"
    assert rec.calls == [("debug", (MATCHED_MSG, "Ann", 7, 1.0), {})]


async def test_match_zero_probe_guarded_to_zero_not_nan() -> None:
    # 'norm >= 0' twin divides [0,0]/0 -> nan probe: cosine's guard misses
    # (nan == 0 is False) and returns nan; nan > -1.0 is False so best_match
    # stays unset and the dict reports -1.0, not shipped 0.0 (measured).
    svc = _svc()
    svc._similarity_threshold = 0.68
    gallery = [gallery_row(7, "Ann", True, N068_BYTES, "m1")]
    out, _, rec = await _match(svc, [0.0, 0.0], gallery, model_id="m1")
    assert out == _unknown_dict(0.0, False)
    assert rec.calls == [("debug", (NOMATCH_MSG, 0.0, 0.68), {})]
