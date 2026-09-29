"""F11 ruling 2 extended to PERSON vectors (ledger item 20: the full swap).

One embedding space end to end: every stored person vector says WHICH
weights computed it, a vector whose origin is unknown is untrusted by
default, and a cross-space comparison answers "unavailable (re-enroll)" —
never a score. This is the person-vector twin of
backend/tests/unit/api/routes/test_face_enrollment_provenance.py; the
mechanics (three DEFAULT spellings, the sentinel vocabulary, the DDL-quote
lesson) are the face pair's, proven again here for PersonEmbedding and
EntityEmbedding.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

import backend.core.vector_provenance as vp
from backend.models.household import PersonEmbedding
from backend.services.household_matcher import (
    PersonMatchOutcome,
    compare_person_vectors,
)
from backend.services.reid_service import EMBEDDING_DIMENSION, EntityEmbedding

pytestmark = pytest.mark.unit

OSNET_ID = "osnet-ain-x1-0@osnet_ain_x1_0_msmt17@8a07e8da3894"
OTHER_ID = "clip@ViT-L@deadbeefcafe"

REPO = (
    Path(__file__).resolve().parents[4]
)  # .../workspace (services/ is one shallower than the face twin's routes/)
MIGRATION_SQL = REPO / "docs/api/migrations/2026-09-26-person-vector-provenance-model-id.sql"


def _same_direction(base: np.ndarray) -> np.ndarray:
    return base * 3.0  # cosine is scale-blind: same direction = similarity 1.0


def _orthogonal(dim: int) -> np.ndarray:
    v = np.ones(dim)
    v[0] = -(float(dim - 1) ** 0.5)  # unit vector orthogonal to ones
    return v / np.linalg.norm(v)


class TestPersonEmbeddingSchemaContract:
    def test_model_id_column_exists_not_null_with_sentinel_default(self) -> None:
        col = PersonEmbedding.__table__.columns["model_id"]
        assert col.nullable is False
        assert col.default is not None
        # The default is the SENTINEL, not a model id: a row that never says
        # who computed it is untrusted by default (drop-and-re-enroll, F11).
        assert col.default.arg == vp.LEGACY_MODEL_ID
        assert col.server_default is not None
        assert col.server_default.arg == vp.LEGACY_MODEL_ID

    def test_sentinel_is_never_shaped_like_a_model_id(self) -> None:
        assert "@" not in vp.LEGACY_MODEL_ID

    def test_vector_provenance_is_the_single_constant(self) -> None:
        # face_provenance re-exports this leaf; a second literal would split
        # the sentinel vocabulary between face and person galleries.
        from backend.core import face_provenance

        assert face_provenance.LEGACY_MODEL_ID is vp.LEGACY_MODEL_ID

    def test_emitted_ddl_default_matches_the_migration_sql(self) -> None:
        """Three spellings of the DEFAULT — model, migration SQL, conftest
        drift repair — must agree exactly (the face pair's lesson: a plain
        string server_default renders QUOTED; an f-string that pre-quotes it
        yields '''sentinel''' and splits the vocabulary)."""
        expected = f"DEFAULT '{vp.LEGACY_MODEL_ID}'"
        ddl = str(CreateTable(PersonEmbedding.__table__).compile(dialect=postgresql.dialect()))
        line = next(ln for ln in ddl.splitlines() if "model_id" in ln)
        assert expected in line, f"DDL default drifted: {line.strip()}"
        assert f"''{vp.LEGACY_MODEL_ID}''" not in line

        sql = MIGRATION_SQL.read_text()
        assert "ADD COLUMN IF NOT EXISTS model_id VARCHAR(128) NOT NULL" in sql
        assert f"DEFAULT '{vp.LEGACY_MODEL_ID}'" in sql

    def test_conftest_drift_repairs_carry_the_identical_default(self) -> None:
        """create_all never adds a column to an EXISTING table, so each test
        DB that predates the column gets an ALTER — and its DEFAULT must be
        the model's sentinel spelled byte-identically (three conftest
        sites, mirroring the face pair's)."""
        expected = (
            "ALTER TABLE person_embeddings ADD COLUMN IF NOT EXISTS "
            "model_id VARCHAR(128) NOT NULL "
            f"DEFAULT '{vp.LEGACY_MODEL_ID}'"
        )
        for rel in (
            "backend/tests/conftest.py",
            "backend/tests/integration/conftest.py",
        ):
            source = (REPO / rel).read_text()
            # The ALTERs are written across a string-concat line break;
            # join continuation lines before searching.
            joined = source.replace('"\n                    "', "").replace(
                '"\n                        "', ""
            )
            assert expected in joined, f"drift ALTER missing/divergent in {rel}"


class TestComparePersonVectors:
    """The pure decision both comparison readers share: cross-space never
    scores; a gallery with nothing comparable is "re-enroll", not "no match"."""

    def test_same_space_match_above_threshold(self) -> None:
        probe = np.ones(EMBEDDING_DIMENSION, dtype=np.float32)
        result = compare_person_vectors(
            probe,
            OSNET_ID,
            [(1, "Dad", _same_direction(probe), OSNET_ID)],
            threshold=0.7,
        )
        assert result.outcome is PersonMatchOutcome.MATCH
        assert result.match is not None
        assert result.match.member_name == "Dad"
        assert result.match.similarity > 0.7

    def test_same_space_below_threshold_is_no_match(self) -> None:
        probe = np.ones(EMBEDDING_DIMENSION, dtype=np.float32)
        result = compare_person_vectors(
            probe,
            OSNET_ID,
            [(1, "Stranger", _orthogonal(EMBEDDING_DIMENSION), OSNET_ID)],
            threshold=0.7,
        )
        assert result.outcome is PersonMatchOutcome.NO_MATCH
        assert result.match is None

    def test_cross_space_row_is_never_scored(self) -> None:
        probe = np.ones(EMBEDDING_DIMENSION, dtype=np.float32)
        # The SAME bytes under a different model_id must not produce a score.
        result = compare_person_vectors(
            probe,
            OSNET_ID,
            [(1, "Dad", probe.copy(), OTHER_ID)],
            threshold=0.7,
        )
        assert result.outcome is PersonMatchOutcome.UNAVAILABLE_REENROLL
        assert result.match is None

    def test_mixed_gallery_scores_only_same_space_rows(self) -> None:
        probe = np.ones(EMBEDDING_DIMENSION, dtype=np.float32)
        result = compare_person_vectors(
            probe,
            OSNET_ID,
            [
                (1, "Mom", _same_direction(probe), OSNET_ID),
                (2, "Ghost", probe.copy(), OTHER_ID),  # would beat Mom if scored
            ],
            threshold=0.7,
        )
        assert result.outcome is PersonMatchOutcome.MATCH
        assert result.match is not None
        assert result.match.member_name == "Mom"

    def test_gallery_of_untrusted_rows_is_reenroll_not_no_match(self) -> None:
        probe = np.ones(EMBEDDING_DIMENSION, dtype=np.float32)
        result = compare_person_vectors(
            probe,
            OSNET_ID,
            [(1, "Old", _same_direction(probe), vp.LEGACY_MODEL_ID)],
            threshold=0.7,
        )
        assert result.outcome is PersonMatchOutcome.UNAVAILABLE_REENROLL
        assert result.match is None

    def test_empty_gallery_is_no_gallery(self) -> None:
        probe = np.ones(EMBEDDING_DIMENSION, dtype=np.float32)
        result = compare_person_vectors(probe, OSNET_ID, [], threshold=0.7)
        assert result.outcome is PersonMatchOutcome.NO_GALLERY
        assert result.match is None

    @pytest.mark.parametrize("probe_id", [None, vp.LEGACY_MODEL_ID])
    def test_probe_of_unknown_provenance_is_refused(self, probe_id: str | None) -> None:
        probe = np.ones(EMBEDDING_DIMENSION, dtype=np.float32)
        result = compare_person_vectors(
            probe,
            probe_id,
            [(1, "Dad", _same_direction(probe), OSNET_ID)],
            threshold=0.7,
        )
        assert result.outcome is PersonMatchOutcome.UNAVAILABLE_REENROLL
        assert result.match is None

    def test_dimension_mismatch_row_is_skipped_never_raises(self) -> None:
        """reid_service.cosine_similarity raises on a length mismatch —
        mid-search that kills the whole pass. The pure decision skips the
        uncomparable row instead (still re-enroll when nothing is left)."""
        probe = np.ones(EMBEDDING_DIMENSION, dtype=np.float32)
        stale_768 = np.ones(768, dtype=np.float32)
        result = compare_person_vectors(
            probe, OSNET_ID, [(1, "Old", stale_768, OSNET_ID)], threshold=0.7
        )
        assert result.outcome is PersonMatchOutcome.UNAVAILABLE_REENROLL
        assert result.match is None


class TestEntityEmbeddingProvenance:
    """The Redis-side store partition key is model_id, but the belt travels
    INSIDE each entry — old payloads must decode untrusted, never trusted."""

    def _entity(self, **overrides: object) -> EntityEmbedding:
        import datetime as dt

        base: dict = {
            "entity_type": "person",
            "embedding": [0.1] * EMBEDDING_DIMENSION,
            "camera_id": "cam-1",
            "timestamp": dt.datetime(2026, 9, 26, tzinfo=dt.UTC),
            "detection_id": "det-1",
        }
        base.update(overrides)
        return EntityEmbedding(**base)  # type: ignore[arg-type]

    def test_model_id_defaults_to_the_sentinel(self) -> None:
        assert self._entity().model_id == vp.LEGACY_MODEL_ID

    def test_to_dict_carries_model_id(self) -> None:
        entity = self._entity(model_id=OSNET_ID)
        assert entity.to_dict()["model_id"] == OSNET_ID

    def test_from_dict_roundtrip_preserves_model_id(self) -> None:
        entity = self._entity(model_id=OSNET_ID)
        assert EntityEmbedding.from_dict(entity.to_dict()).model_id == OSNET_ID

    def test_old_payload_without_model_id_decodes_untrusted(self) -> None:
        stored = self._entity().to_dict()
        del stored["model_id"]
        assert EntityEmbedding.from_dict(stored).model_id == vp.LEGACY_MODEL_ID

    def test_embedding_dimension_is_osnet_512(self) -> None:
        assert EMBEDDING_DIMENSION == 512


class TestEntitiesJsonbProvenance:
    """The Postgres entity store's JSONB belt: {"vector","model","dimension"}.

    The default that lived here was the LITERAL "clip" — after the swap a
    write that never names its producer would mislabel OSNet bytes as
    CLIP's (or vice versa), which is provenance backwards. The parameter
    becomes required and the "clip" default constant is deleted: the id
    flows from the PRODUCER (B5b's one helper), never from a module."""

    def test_set_embedding_refuses_an_unnamed_producer(self) -> None:
        from backend.models.entity import Entity

        entity = Entity(entity_type="person", trust_status="unknown")
        # Omitted and explicitly-None both refuse: the post-swap danger is
        # a SILENT default mislabeling OSNet bytes as CLIP's (or the
        # reverse), and an omitted keyword is exactly how that arrives.
        with pytest.raises(ValueError, match="model"):
            entity.set_embedding([0.1] * 4)
        with pytest.raises(ValueError, match="model"):
            entity.set_embedding([0.1] * 4, model=None)

    def test_set_embedding_stores_the_named_producer(self) -> None:
        from backend.models.entity import Entity

        entity = Entity(entity_type="person", trust_status="unknown")
        entity.set_embedding([0.1] * 4, model=OSNET_ID)
        assert entity.embedding_vector["model"] == OSNET_ID
        assert entity.get_embedding_model() == OSNET_ID

    def test_from_detection_requires_the_producer_with_an_embedding(self) -> None:
        from backend.models.entity import Entity

        with pytest.raises(ValueError, match="model"):
            Entity.from_detection("person", embedding=[0.1] * 4)
        # No embedding, no producer needed: the row simply carries none.
        bare = Entity.from_detection("person")
        assert bare.embedding_vector is None
        entity = Entity.from_detection("person", embedding=[0.1] * 4, model=OSNET_ID)
        assert entity.embedding_vector["model"] == OSNET_ID

    def test_clipping_default_constant_is_gone(self) -> None:
        """A module-level DEFAULT_EMBEDDING_MODEL = "clip" is exactly the
        silent-drift class: every write inherits a CLAIM. It must not come
        back (the flow is producer -> payload, per plan A4)."""
        import backend.services.entity_clustering_service as clustering

        assert not hasattr(clustering, "DEFAULT_EMBEDDING_MODEL")

    def test_find_by_embedding_never_compares_across_spaces(self) -> None:
        """The repo's _cosine_similarity returns 0.0 for a foreign row —
        F11 wants it SKIPPED (counted), never scored, and a probe with no
        named model compares against nothing."""
        from backend.models.entity import Entity
        from backend.repositories.entity_repository import EntityRepository

        probe = [1.0] + [0.0] * 511

        def _row(model: str | None, vec: list[float]) -> Entity:
            e = Entity(entity_type="person", trust_status="unknown")
            e.embedding_vector = {"vector": vec, "model": model, "dimension": len(vec)}
            return e

        same = _row(OSNET_ID, probe)
        foreign = _row("clip", probe)  # byte-identical, WRONG space
        unprovenanced = _row(None, probe)

        # The filter is a pure predicate here (the DB query is the caller's):
        keep = EntityRepository._provenance_matches
        assert keep(same, OSNET_ID) is True
        assert keep(foreign, OSNET_ID) is False
        assert keep(unprovenanced, OSNET_ID) is False
        # A probe with no named model compares against NOTHING.
        assert keep(same, None) is False
        assert keep(same, vp.LEGACY_MODEL_ID) is False

    def test_hybrid_belt_rides_both_sides(self) -> None:
        """HybridEntityMatch carries the belt so a PostgreSQL match doesn't
        decode as untrusted downstream, and store_detection_embedding
        threads it to BOTH legs (clustering row + Redis partition)."""
        import inspect

        from backend.models.entity import Entity
        from backend.services.hybrid_entity_storage import HybridEntityMatch

        entity = Entity(entity_type="person", trust_status="unknown")
        entity.set_embedding([0.1] * 4, model=OSNET_ID)
        match = HybridEntityMatch.from_postgresql_match(entity, similarity=0.9)
        assert match.model_id == OSNET_ID

        from backend.services.hybrid_entity_storage import HybridEntityStorage

        params = inspect.signature(HybridEntityStorage.store_detection_embedding).parameters
        assert "model_id" in params


class TestCachedPayloadBelt:
    """A6: the cached person_reid payloads carry model_id (F11: every
    stored/relayed vector names its producer, so downstream readers never
    have to guess which space the bytes live in)."""

    def test_extract_person_embedding_pairing(self) -> None:
        from backend.services.household_matcher import (
            extract_person_embedding_with_provenance,
        )

        emb, model_id = extract_person_embedding_with_provenance(
            {"embeddings": {"person_reid": [0.1] * 512, "model_id": OSNET_ID}}
        )
        assert emb is not None and len(emb) == 512
        assert model_id == OSNET_ID

    def test_extract_person_embedding_pairing_legacy_is_untrusted(self) -> None:
        """A cached payload from BEFORE the swap has no belt — and the
        reader reports that honestly (None) instead of inventing one."""
        from backend.core.vector_provenance import LEGACY_MODEL_ID
        from backend.services.household_matcher import (
            extract_person_embedding_with_provenance,
        )

        emb, model_id = extract_person_embedding_with_provenance(
            {"embeddings": {"person_reid": [0.1] * 512}}
        )
        assert emb is not None
        assert model_id is None
        assert model_id != LEGACY_MODEL_ID  # reader does not launder; the
        # pure compare_person_vectors treats the None probe as re-enroll.

    # R8 S2 deleted EnrichmentResult.to_storage_dict along with
    # enrichment_pipeline, so the WRITER half of this pin (the belt riding
    # from person_embeddings into the stored embeddings payload) went with
    # it. What is left here is the reader half — the payload contract the
    # live matcher still honours — plus the batch matcher's own belt
    # threading below.

    def test_match_detections_threads_the_belt(self) -> None:
        """match_person must be called WITH the payload's belt, not bare."""
        import asyncio
        from unittest.mock import AsyncMock

        from backend.services.household_matcher import HouseholdMatcher

        matcher = HouseholdMatcher()
        matcher.match_person = AsyncMock(return_value=None)

        detection = MagicMock()
        detection.id = 7
        detection.object_type = "person"
        enrichment = {"embeddings": {"person_reid": [0.1] * 512, "model_id": OSNET_ID}}
        asyncio.run(matcher.match_detections([detection], {7: enrichment}, AsyncMock()))
        assert matcher.match_person.await_args.kwargs.get("model_id") == OSNET_ID


# B5b ("every person-vector producer labels with osnet_model_id(), never its
# own literal") had two source-scan tests here aimed at
# enrichment_pipeline's producer payload sites. R8 S2 deleted that module, so
# both scans lost their subject and went with it — a scan of a dead module
# proves nothing about the live producers. The surviving producers
# (entity_repository, entity_clustering_service, the osnet handle below) are
# pinned by their own suites, and TestGenerateEmbeddingProducer keeps the
# "handle's belt, not the catalog's claim" rule alive here.


class TestGenerateEmbeddingProducer:
    """B5: the store's own producer computes person vectors with the resident
    OSNet handle, returns the belt beside the bytes, and refuses loudly when
    the weights are not resident (no CLIP client, no silent stub)."""

    def _image(self) -> object:
        from PIL import Image

        return Image.new("RGB", (64, 128), color="red")

    async def test_absent_handle_refuses_loudly(self, monkeypatch) -> None:
        import backend.services.osnet_loader as ol
        from backend.services.reid_service import ReIdentificationService, ReIDUnavailableError

        monkeypatch.setattr(ol, "get_reid_handle", lambda: None)
        service = ReIdentificationService()
        with pytest.raises(ReIDUnavailableError, match="osnet-ain-x1-0"):
            await service.generate_embedding(self._image())

    async def test_resident_handle_returns_vector_and_belt(self, monkeypatch) -> None:
        """The belt is the HANDLE's string — the file actually loaded — not
        osnet_model_id(): a hand-deployed different weights file labels with
        its own id (honest different space), never the catalog's claim."""
        import numpy as np

        import backend.services.osnet_loader as ol
        from backend.services.reid_service import ReIdentificationService

        handle = {"model": MagicMock(), "transform": MagicMock(), "model_id": OTHER_ID}
        monkeypatch.setattr(ol, "get_reid_handle", lambda: handle)

        async def _fake_extract(model_dict, image, detection_id=None):
            from backend.services.osnet_loader import PersonEmbeddingResult

            assert model_dict is handle
            return PersonEmbeddingResult(
                embedding=np.ones(512, dtype=np.float32),
                detection_id=detection_id,
                model_id=model_dict["model_id"],
            )

        monkeypatch.setattr(ol, "extract_person_embedding", _fake_extract)

        service = ReIdentificationService()
        vector, belt = await service.generate_embedding(self._image(), bbox=(1, 1, 40, 100))
        assert len(vector) == 512
        assert belt == OTHER_ID

    def test_service_no_longer_holds_a_clip_client(self) -> None:
        """The CLIP seam is gone: constructing the service takes no client and
        the module never imports the CLIP client (the producer is the zoo
        handle; CLIP stays only where it is really CLIP's job)."""
        import inspect

        import backend.services.reid_service as rs

        params = inspect.signature(rs.ReIdentificationService.__init__).parameters
        assert "clip_client" not in params
        src = inspect.getsource(rs)
        assert "clip_client" not in src
        assert "get_clip_client" not in src


class TestEnrollmentCarriesTheBelt:
    """The enrollment path stores WHAT IT COMPUTED: the PersonEmbedding row
    gets the producer's model_id, and an unavailable producer answers a 5xx
    naming the cause (the face enrollment precedent) — never a row whose
    provenance is a guess."""

    @pytest.mark.asyncio
    async def test_person_embedding_row_gets_the_belt(self, monkeypatch, tmp_path) -> None:
        import numpy as np
        from fastapi import HTTPException

        import backend.api.routes.household as hh
        from backend.models.household import HouseholdMember

        member = HouseholdMember(id=1, name="Dad")
        detection = MagicMock()
        detection.id = 50
        detection.object_type = "person"
        detection.file_path = str(tmp_path / "t.jpg")
        detection.bbox_x = 10
        detection.bbox_y = 10
        detection.bbox_width = 20
        detection.bbox_height = 40
        event = MagicMock()
        event.id = 100
        event.detections = [detection]

        session = AsyncMock()
        counts = {"n": 0}

        def _execute(query):
            result = MagicMock()
            counts["n"] += 1
            result.scalar_one_or_none.return_value = member if counts["n"] == 1 else event
            return result

        session.execute.side_effect = _execute

        service = MagicMock()
        service.generate_embedding = AsyncMock(return_value=([0.1] * 512, OSNET_ID))
        monkeypatch.setattr(hh, "get_reid_service", lambda: service)

        import contextlib

        from PIL import Image

        real_open = Image.open

        @contextlib.contextmanager
        def _fake_open(path):
            yield Image.new("RGB", (64, 128))

        monkeypatch.setattr(hh.Image, "open", _fake_open)
        assert real_open is not None  # PIL stays importable under the patch

        request = MagicMock()
        request.event_id = 100
        request.confidence = 0.95

        try:
            await hh.add_embedding_from_event(member_id=1, request=request, session=session)
        except HTTPException as exc:  # pragma: no cover - fail loud below
            raise AssertionError(f"enrollment raised {exc.status_code}: {exc.detail}") from exc

        row = session.add.call_args[0][0]
        assert row.model_id == OSNET_ID
        assert np.frombuffer(row.embedding, dtype=np.float32).shape == (512,)

    @pytest.mark.asyncio
    async def test_unavailable_producer_answers_5xx_naming_the_cause(
        self, monkeypatch, tmp_path
    ) -> None:
        from fastapi import HTTPException

        import backend.api.routes.household as hh
        from backend.models.household import HouseholdMember
        from backend.services.reid_service import ReIDUnavailableError

        member = HouseholdMember(id=1, name="Dad")
        detection = MagicMock()
        detection.id = 50
        detection.object_type = "person"
        detection.file_path = str(tmp_path / "t.jpg")
        detection.bbox_x = None
        detection.bbox_y = None
        detection.bbox_width = None
        detection.bbox_height = None
        event = MagicMock()
        event.id = 100
        event.detections = [detection]

        session = AsyncMock()
        counts = {"n": 0}

        def _execute(query):
            result = MagicMock()
            counts["n"] += 1
            result.scalar_one_or_none.return_value = member if counts["n"] == 1 else event
            return result

        session.execute.side_effect = _execute

        service = MagicMock()
        service.generate_embedding = AsyncMock(
            side_effect=ReIDUnavailableError("osnet-ain-x1-0 is not resident")
        )
        monkeypatch.setattr(hh, "get_reid_service", lambda: service)

        import contextlib

        from PIL import Image

        @contextlib.contextmanager
        def _fake_open(path):
            yield Image.new("RGB", (64, 128))

        monkeypatch.setattr(hh.Image, "open", _fake_open)

        request = MagicMock()
        request.event_id = 100
        request.confidence = 0.95

        with pytest.raises(HTTPException) as exc:
            await hh.add_embedding_from_event(member_id=1, request=request, session=session)
        assert exc.value.status_code in (503, 500)
        assert "osnet" in str(exc.value.detail).lower()
        session.add.assert_not_called()


class TestClientVectorEndpointRetired:
    """D-1: a client-claimed model_id is no trust anchor — the endpoint
    answers 410 Gone (the face client-vector enrollment precedent)."""

    def test_match_person_endpoint_is_gone(self) -> None:
        import inspect

        import backend.api.routes.household_matcher as hm

        src = inspect.getsource(hm.match_person)
        assert "410" in src or "GONE" in src
