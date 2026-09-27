"""F11 ruling 2's enrollment half: ONE embedding space, end to end.

The gallery's stored vectors must say WHICH weights produced them, and
nothing that was not computed by the pinned server-side extractor may
carry a real model id. Today that is load-bearing, not theoretical: both
placeholder extractors were literally ``np.random.rand(512)``
(ledger row 1.3b), so every vector an old enrollment stored is noise —
the honest id for one is the ``legacy`` sentinel, never a model id, and
the face specialist reads that sentinel as "re-enroll", never as a score.

What this pins:

* the ``FaceEmbedding.model_id`` column exists, NOT NULL, defaulted to
  the sentinel (a row written by old code that never mentions the column
  is flagged, not trusted);
* ``add_face_embedding`` takes an explicit ``model_id`` and defaults to
  the sentinel — the server-side enrollments pass the loaded handle's id;
* the client-supplied-vector endpoint is GONE (410): a vector computed
  off-box cannot be trusted to share the space, and there is no server
  extractor it could have come from — enrollment goes through the image
  endpoints that run the pinned loader;
* ``extract_face_embedding_from_detection`` / ``_from_image`` run the
  REAL loader leg (SCRFD -> align -> w600k_r50) and report the loaded
  recognizer's model_id; absent weights fail loud at enrollment (a 5xx
  naming the cause), never a random vector;
* ``identify_face_event`` copies an event's vectors with the event's own
  provenance (the one embedding space rule applied to the copy path).
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest
from PIL import Image

import backend.services.face_recognizer_loader as frl
import backend.services.model_zoo as mz
from backend.api.routes import face_recognition as froute
from backend.api.schemas.face_recognition import (
    EnrollFromDetectionRequest,
    FaceEmbeddingCreate,
)
from backend.models.detection import Detection
from backend.models.face_identity import FaceDetectionEvent, FaceEmbedding

pytestmark = pytest.mark.unit


class TestSchemaContract:
    def test_model_id_column_exists_not_null_with_sentinel_default(self) -> None:
        col = FaceEmbedding.__table__.columns["model_id"]
        assert col.nullable is False
        # The default is the SENTINEL, not a model id: a row that never
        # says who computed it is untrusted by default (old code path).
        assert col.default is not None
        assert col.default.arg == frl.LEGACY_MODEL_ID

    def test_face_detection_event_carries_the_same_provenance_column(self) -> None:
        # The identify/queue copy paths move an EVENT's vector into the
        # gallery; the carrier must exist on the event side too.
        from backend.models.face_identity import FaceDetectionEvent

        col = FaceDetectionEvent.__table__.columns["model_id"]
        assert col.nullable is False
        assert col.default.arg == frl.LEGACY_MODEL_ID

    def test_loader_exports_the_sentinel(self) -> None:
        assert frl.LEGACY_MODEL_ID
        assert "@" not in frl.LEGACY_MODEL_ID  # never shaped like a model id

    def test_emitted_ddl_default_matches_the_migration_sql(self) -> None:
        """The schema has THREE spellings of this default — the model, the
        migration SQL, and conftest's drift repair — and `create_all` never
        adds a column to an existing table, so they must agree exactly.

        A plain-string ``server_default`` is rendered as a SQL string literal
        (one pair of quotes). Spelling it ``f"'{...}'"`` instead produced
        ``'''legacy-unknown-provenance'''`` in the DDL, which Postgres reads
        as a literal that begins and ends with a quote — a gallery whose
        ORM-created rows and SQL-created rows carry DIFFERENT sentinels, and
        the mismatch guard compares those strings for equality. Pin the
        rendered text, not the Python attribute, because the Python attribute
        looked right in both spellings.
        """
        from sqlalchemy.dialects import postgresql
        from sqlalchemy.schema import CreateTable

        expected = f"DEFAULT '{frl.LEGACY_MODEL_ID}'"
        for model in (FaceEmbedding, FaceDetectionEvent):
            ddl = str(CreateTable(model.__table__).compile(dialect=postgresql.dialect()))
            line = next(ln for ln in ddl.splitlines() if "model_id" in ln)
            assert expected in line, f"DDL default drifted: {line.strip()}"
            assert f"''{frl.LEGACY_MODEL_ID}''" not in line


class TestServiceContract:
    async def test_add_face_embedding_defaults_to_the_sentinel(self) -> None:
        """A caller that names no extractor gets the untrusted flag."""
        from backend.services.face_recognition_service import FaceRecognitionService

        service = FaceRecognitionService()
        session = AsyncMock()
        session.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        # person lookup returns None -> early exit; inspect the call instead
        await service.add_face_embedding(session, 1, embedding=[0.0] * 512)
        # No FaceEmbedding constructed on the not-found path: assert the
        # signature carries the default instead (the found-path is next test).
        import inspect

        sig = inspect.signature(service.add_face_embedding)
        assert sig.parameters["model_id"].default == frl.LEGACY_MODEL_ID

    async def test_stored_row_carries_the_given_model_id(self) -> None:
        from backend.services.face_recognition_service import FaceRecognitionService

        service = FaceRecognitionService()
        person = SimpleNamespace(id=7, name="Dad")
        session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = person
        session.execute.return_value = result
        row: list[FaceEmbedding] = []
        # production calls session.add() synchronously (only commit/refresh
        # are awaited), so the capture must be a sync mock — an AsyncMock's
        # side_effect runs inside the un-awaited coroutine and never fires.
        session.add = MagicMock(side_effect=lambda obj: row.append(obj))

        emb = await service.add_face_embedding(
            session, 7, embedding=[0.1] * 512, model_id="face-recognizer@w600k_r50@abc"
        )
        assert emb is not None
        assert emb.model_id == "face-recognizer@w600k_r50@abc"
        assert row and row[0].model_id == emb.model_id


class TestClientVectorPathIsGone:
    async def test_posted_vector_is_rejected_as_gone(self) -> None:
        """F12/F11: "a client-computed vector can't be trusted to share our
        space" — the endpoint answers 410 with the sanctioned path, and the
        service is NEVER reached (the 512-length check must not run first:
        a right-sized vector fails the same way)."""
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            await froute.add_face_embedding(
                person_id=1,
                data=FaceEmbeddingCreate(embedding=[0.5] * 512),
                session=AsyncMock(),
            )
        assert exc.value.status_code == 410
        assert "image" in str(exc.value.detail).lower()


# ---------------------------------------------------------------------------
# The extractor legs: REAL loader over fake sessions (the shipped
# deterministic fakes from the specialists suite, inline so this file owns
# its bytes: same crop bytes -> same vector).
# ---------------------------------------------------------------------------


class _FakeDetector:
    """One face centered at (10,10) x stride 8 -> 240 px, score 0.99,
    landmarks present (the specialists-suite fake, same layout)."""

    box_dist = (10.0, 10.0, 20.0, 20.0)

    def get_inputs(self):
        return [type("I", (), {"name": "input.1"})()]

    def run(self, _out, feeds):
        blob = np.asarray(next(iter(feeds.values())), dtype=np.float32)
        h_in, w_in = blob.shape[2], blob.shape[3]
        outs = [[], [], []]
        for level, stride in enumerate((8, 16, 32)):
            h, w = h_in // stride, w_in // stride
            n = h * w * 2
            s = np.zeros((n, 1), np.float32)
            b = np.zeros((n, 4), np.float32)
            k = np.zeros((n, 10), np.float32)
            if stride == 8:
                row, col = min(10, h - 1), min(10, w - 1)
                idx = (row * w + col) * 2
                s[idx, 0] = 0.99
                b[idx] = self.box_dist
                k[idx, :] = np.tile(np.float32([0.5, 0.5]), 5)
            outs[0].append(s)
            outs[1].append(b)
            outs[2].append(k)
        return outs[0] + outs[1] + outs[2]


class _FakeEmbed:
    def get_inputs(self):
        return [type("I", (), {"name": "input.1"})()]

    def run(self, _out, feeds):
        arr = np.asarray(next(iter(feeds.values())), dtype=np.float32).reshape(-1)
        buckets = np.array([b.mean() for b in np.array_split(arr, 512)])
        mixing = np.linspace(-1.0, 1.0, 512 * 512, dtype=np.float32).reshape(512, 512)
        return [(np.tanh(buckets @ mixing.T) * 37.0).reshape(1, 512)]


REAL_ID = "face-recognizer@w600k_r50@4c06341c33c2"


class _Manager:
    def __init__(self, with_leg: bool) -> None:
        self._loaded_models: dict[str, dict] = {}
        if with_leg:
            self._loaded_models["face-detector-scrfd"] = {
                "session": _FakeDetector(),
                "input_name": "input.1",
                "model_id": "face-detector-scrfd@scrfd_10g_bnkps@5838f7fe0536",
            }
            self._loaded_models["face-recognizer"] = {
                "session": _FakeEmbed(),
                "input_name": "input.1",
                "model_id": REAL_ID,
                "embedding_dim": 512,
            }


@pytest.fixture
def face_jpg(tmp_path):
    rng = np.random.default_rng(5)
    path = tmp_path / "person.jpg"
    Image.fromarray(rng.integers(0, 255, (480, 640, 3), dtype=np.uint8), "RGB").save(path)
    return path


@pytest.fixture
def with_leg(monkeypatch):
    monkeypatch.setattr(mz, "get_model_manager", lambda: _Manager(True))


@pytest.fixture
def without_leg(monkeypatch):
    monkeypatch.setattr(mz, "get_model_manager", lambda: _Manager(False))


class TestDetectionExtractorIsReal:
    async def test_real_vector_and_loaded_model_id_and_gate_quality(self, with_leg, face_jpg):
        det = Detection(
            id=100,
            camera_id="cam",
            file_path=str(face_jpg),
            object_type="person",
            confidence=0.9,
        )
        embedding, quality, model_id = await froute.extract_face_embedding_from_detection(det)
        assert model_id == REAL_ID, "provenance is the LOADED weights, not a constant"
        assert embedding is not None and len(embedding) == 512
        assert abs(float(np.linalg.norm(np.asarray(embedding))) - 1.0) < 1e-4
        # quality is DERIVED from the gate inputs (crop size + scrfd score),
        # not the old bbox-area heuristic: a 240-px face at 0.99 is excellent.
        assert quality >= 0.7
        # deterministic: same file -> same vector
        again, _, _ = await froute.extract_face_embedding_from_detection(det)
        assert np.allclose(np.asarray(embedding), np.asarray(again))

    async def test_weights_absent_fails_loud_not_random(self, without_leg, face_jpg):
        """The pre-fix bug class: the placeholder happily "enrolled" a
        random vector. Absent weights must raise (the endpoint maps it to
        a 5xx naming the cause), never return anything."""
        det = Detection(
            id=101,
            camera_id="cam",
            file_path=str(face_jpg),
            object_type="person",
            confidence=0.9,
        )
        with pytest.raises(RuntimeError) as exc:
            await froute.extract_face_embedding_from_detection(det)
        assert "unavailable" in str(exc.value).lower() or "weight" in str(exc.value).lower()

    async def test_no_face_is_none_not_a_raise(self, monkeypatch, face_jpg):
        """Zero faces is a REAL observation: (None, None, None) -> the
        endpoint's 400 arm, kept distinct from the weights arm."""

        class _NoFaceDetector(_FakeDetector):
            def run(self, out, feeds):
                outs = super().run(out, feeds)
                for s in outs[:3]:  # zero scores at every level
                    s[:] = 0.0
                return outs

        manager = _Manager(True)
        manager._loaded_models["face-detector-scrfd"]["session"] = _NoFaceDetector()
        monkeypatch.setattr(mz, "get_model_manager", lambda: manager)
        det = Detection(
            id=102,
            camera_id="cam",
            file_path=str(face_jpg),
            object_type="person",
            confidence=0.9,
        )
        embedding, quality, model_id = await froute.extract_face_embedding_from_detection(det)
        assert embedding is None and quality is None and model_id is None


class TestImageExtractorIsReal:
    async def test_image_extractor_reports_model_id(self, with_leg, face_jpg):
        """The tuple gains the provenance slot (bulk-enroll writes it)."""
        out = await froute.extract_face_embedding_from_image(face_jpg.read_bytes(), "p.jpg")
        assert len(out) == 4, "extraction must report which weights computed the vector"
        embedding, quality, error, model_id = out
        assert error is None
        assert model_id == REAL_ID

    async def test_weights_absent_reports_error_not_random(self, without_leg, face_jpg):
        out = await froute.extract_face_embedding_from_image(face_jpg.read_bytes(), "p.jpg")
        embedding, quality, error, model_id = out
        assert embedding is None and quality is None and model_id is None
        assert error and "unavailable" in error.lower()

    async def test_undersized_upload_still_rejected_first(self, with_leg, tmp_path):
        path = tmp_path / "tiny.png"
        Image.new("RGB", (32, 32)).save(path)
        out = await froute.extract_face_embedding_from_image(path.read_bytes(), "t.png")
        embedding, quality, error, model_id = out
        assert embedding is None and "too small" in error.lower()


class TestIdentifyCopiesProvenance:
    async def test_embedding_from_event_carries_the_events_model_id(self) -> None:
        from backend.services.face_recognition_service import FaceRecognitionService

        service = FaceRecognitionService()
        event = SimpleNamespace(
            id=9,
            is_unknown=True,
            quality_score=0.9,
            embedding=np.ones(512, dtype=np.float32).tobytes(),
            model_id="face-recognizer@w600k_r50@abc",
        )
        person = SimpleNamespace(id=3, name="Mom")
        session = AsyncMock()
        result = MagicMock()
        # first execute -> event, second -> person
        result.scalar_one_or_none.side_effect = [event, person, None]
        session.execute.return_value = result
        rows: list[FaceEmbedding] = []
        session.add = MagicMock(side_effect=lambda obj: rows.append(obj))

        out = await service.identify_face_event(session, event_id=9, known_person_id=3)
        assert out["created_embedding"] is True
        copied = [r for r in rows if isinstance(r, FaceEmbedding)]
        assert copied and copied[0].model_id == "face-recognizer@w600k_r50@abc"

    async def test_legacy_event_copies_the_sentinel(self) -> None:
        """The whole point: identifying an OLD event (random vector) into
        the gallery flags the row, so the specialist answers re-enroll
        instead of scoring noise."""
        from backend.services.face_recognition_service import FaceRecognitionService

        service = FaceRecognitionService()
        event = SimpleNamespace(
            id=10,
            is_unknown=True,
            quality_score=0.9,
            embedding=np.ones(512, dtype=np.float32).tobytes(),
            model_id=frl.LEGACY_MODEL_ID,
        )
        person = SimpleNamespace(id=4, name="Old")
        session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.side_effect = [event, person, None]
        session.execute.return_value = result
        rows: list[FaceEmbedding] = []
        session.add = MagicMock(side_effect=lambda obj: rows.append(obj))
        out = await service.identify_face_event(session, event_id=10, known_person_id=4)
        assert out["created_embedding"] is True
        copied = [r for r in rows if isinstance(r, FaceEmbedding)]
        assert copied[0].model_id == frl.LEGACY_MODEL_ID


class TestGalleryGuardReadsTheColumn:
    async def test_sentinel_rows_activate_the_re_enroll_guard(self) -> None:
        """The _gallery_model_ids contract on a REAL column: sentinel rows
        are DISTINCT ids, so a gallery of old vectors trips
        'unavailable (re-enroll)' instead of scoring noise. (The live-DB
        end of this rides the integration tier; here the fake session
        proves the SELECT's semantics: NULLs skipped, sentinel kept.)"""
        import backend.services.vlm_specialists as vs

        result = MagicMock()
        result.__iter__.return_value = iter([(frl.LEGACY_MODEL_ID,), (REAL_ID,), (None,)])
        session = AsyncMock()
        session.execute.return_value = result
        ids = await vs._gallery_model_ids(session)
        assert ids == {frl.LEGACY_MODEL_ID, REAL_ID}
        assert None not in ids


class TestEnrollFromDetectionWiresProvenance:
    async def test_endpoint_passes_the_extractors_model_id_to_storage(
        self, with_leg, face_jpg
    ) -> None:
        """The compose seam: extractor -> add_face_embedding(model_id=...).
        Real extraction against the fake leg end-to-end through the
        endpoint body (person/detection rows via mocked session)."""
        person = SimpleNamespace(id=1, name="Dad", embeddings=[])
        det = Detection(
            id=100,
            camera_id="cam",
            file_path=str(face_jpg),
            object_type="person",
            confidence=0.9,
        )
        session = AsyncMock()
        res_p = MagicMock()
        res_p.scalar_one_or_none.return_value = person
        res_d = MagicMock()
        res_d.scalar_one_or_none.return_value = det
        session.execute.side_effect = [res_p, res_d]
        stored: dict = {}

        async def _add(
            _session, person_id, *, embedding, quality_score, source_image_path, model_id
        ):
            stored.update(model_id=model_id, n=len(embedding))
            return SimpleNamespace(
                id=5,
                person_id=person_id,
                quality_score=quality_score,
                source_image_path=source_image_path,
                model_id=model_id,
            )

        # The route module did `from ... import get_face_recognition_service`,
        # so the seam to patch is the ROUTE's name, not the service module's.
        orig = froute.get_face_recognition_service
        froute.get_face_recognition_service = lambda: SimpleNamespace(add_face_embedding=_add)
        try:
            resp = await froute.enroll_from_detection(
                person_id=1,
                data=EnrollFromDetectionRequest(detection_id="100"),
                session=session,
            )
        finally:
            froute.get_face_recognition_service = orig
        assert resp.success is True
        assert stored["model_id"] == REAL_ID
        assert stored["n"] == 512
