"""Unit tests for the OSNet person re-identification gateway seam ([r306b])."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import numpy as np
import pytest
import yaml
from PIL import Image

import backend.services.osnet_loader as ol
from backend.services.osnet_loader import (
    OSNET_EMBEDDING_DIM,
    OSNET_ZOO_NAME,
    PersonEmbeddingResult,
    _enforce_embedding_dim,
    extract_person_embedding,
    extract_person_embeddings_batch,
    format_person_reid_context,
    get_reid_handle,
    load_osnet_model,
    match_person_embeddings,
    osnet_model_id,
)

OSNET_SHA256 = (
    "8a07e8da38946f7cee37f4561617bf8b6d2fe8f3a4027852893ea092e46d919f"  # pragma: allowlist secret
)
OSNET_ID = "osnet-ain-x1-0@osnet_ain_x1_0_msmt17@8a07e8da3894"


def _yaml_catalog() -> dict[str, dict]:
    models_yml = Path(__file__).resolve().parents[4] / "models.yml"
    return {m["name"]: m for m in yaml.safe_load(models_yml.read_text())["models"]}


def _unit_vec(seed: int = 42, dim: int = 512) -> np.ndarray:
    rng = np.random.default_rng(seed)
    vec = rng.standard_normal(dim).astype(np.float32)
    return vec / np.linalg.norm(vec)


class TestOSNetConstants:
    def test_osnet_embedding_dim_constant(self) -> None:
        assert OSNET_EMBEDDING_DIM == 512
        assert OSNET_ZOO_NAME == "osnet-ain-x1-0"


class TestPersonEmbeddingResult:
    def test_create_result_with_defaults(self) -> None:
        emb = _unit_vec(1)
        res = PersonEmbeddingResult(embedding=emb)
        assert np.array_equal(res.embedding, emb)
        assert res.detection_id is None
        assert res.confidence == 1.0
        assert res.model_id is None

    def test_create_result_with_all_fields(self) -> None:
        emb = _unit_vec(2)
        res = PersonEmbeddingResult(
            embedding=emb,
            detection_id="det_1",
            confidence=0.85,
            model_id=OSNET_ID,
        )
        assert res.detection_id == "det_1"
        assert res.confidence == 0.85
        assert res.model_id == OSNET_ID

    def test_to_dict(self) -> None:
        emb = _unit_vec(3)
        res = PersonEmbeddingResult(
            embedding=emb,
            detection_id="det_3",
            confidence=0.9,
            model_id=OSNET_ID,
        )
        assert res.to_dict() == {
            "embedding": emb.tolist(),
            "detection_id": "det_3",
            "confidence": 0.9,
            "embedding_dim": 512,
            "model_id": OSNET_ID,
        }

    def test_cosine_similarity_identical(self) -> None:
        emb = _unit_vec(4)
        a = PersonEmbeddingResult(embedding=emb)
        b = PersonEmbeddingResult(embedding=emb.copy())
        assert a.cosine_similarity(b) == pytest.approx(1.0, abs=1e-5)

    def test_cosine_similarity_opposite(self) -> None:
        emb = _unit_vec(5)
        a = PersonEmbeddingResult(embedding=emb)
        b = PersonEmbeddingResult(embedding=-emb)
        assert a.cosine_similarity(b) == pytest.approx(-1.0, abs=1e-5)

    def test_cosine_similarity_orthogonal(self) -> None:
        a_vec = np.zeros(512, dtype=np.float32)
        b_vec = np.zeros(512, dtype=np.float32)
        a_vec[0] = 1.0
        b_vec[1] = 1.0
        a = PersonEmbeddingResult(embedding=a_vec)
        b = PersonEmbeddingResult(embedding=b_vec)
        assert a.cosine_similarity(b) == pytest.approx(0.0, abs=1e-6)


class TestDimensionGuardRaises:
    def test_short_features_raise_not_pad(self) -> None:
        with pytest.raises(RuntimeError, match="512"):
            _enforce_embedding_dim(np.ones(256, dtype=np.float32))

    def test_long_features_raise_not_truncate(self) -> None:
        with pytest.raises(RuntimeError, match="512"):
            _enforce_embedding_dim(np.ones(768, dtype=np.float32))

    def test_exact_512_flattens_and_returns(self) -> None:
        out = _enforce_embedding_dim(np.ones((1, 512), dtype=np.float32))
        assert out.shape == (512,)


class TestModelsYmlOsnetRow:
    def test_row_names_the_weights_file(self) -> None:
        row = _yaml_catalog()["osnet-ain-x1-0"]
        assert row["runtime_file"] == "osnet_ain_x1_0_msmt17.pth"

    def test_row_pins_weights_by_sha256(self) -> None:
        row = _yaml_catalog()["osnet-ain-x1-0"]
        assert row["sha256"] == OSNET_SHA256

    def test_description_carries_the_honest_benchmark(self) -> None:
        row = _yaml_catalog()["osnet-ain-x1-0"]
        assert "osnet" in row["description"].lower()


class TestOsnetModelId:
    def test_value_is_row_derived_never_a_literal(self) -> None:
        row = _yaml_catalog()["osnet-ain-x1-0"]
        stem = row["runtime_file"].removesuffix(".pth")
        assert osnet_model_id() == f"osnet-ain-x1-0@{stem}@{row['sha256'][:12]}"
        assert osnet_model_id() == OSNET_ID

    def test_same_value_for_every_caller(self) -> None:
        assert osnet_model_id() == osnet_model_id()


class TestGetReidHandle:
    def test_returns_gateway_handle(self, monkeypatch) -> None:
        monkeypatch.setattr(
            ol,
            "get_settings",
            lambda: SimpleNamespace(enrichment_light_url="http://ai-gateway:8090/enrich-lt"),
        )
        assert get_reid_handle() == {
            "kind": "gateway",
            "base_url": "http://ai-gateway:8090/enrich-lt",
            "model_id": None,
        }


class TestLoadOSNetModel:
    @pytest.mark.asyncio
    async def test_load_returns_gateway_handle_with_derived_belt(self, tmp_path: Path) -> None:
        weights = tmp_path / "osnet_ain_x1_0_msmt17.pth"
        result = await load_osnet_model(str(weights), expected_sha256=OSNET_SHA256)
        assert result["kind"] == "gateway"
        assert result["model_id"] == OSNET_ID
        assert result["embedding_dim"] == 512

    @pytest.mark.asyncio
    async def test_load_rejects_traversal_path(self) -> None:
        with pytest.raises(RuntimeError, match="Invalid model path"):
            await load_osnet_model("/tmp/../etc/passwd")  # noqa: S108


class TestExtractPersonEmbedding:
    @pytest.mark.asyncio
    async def test_extract_delegates_to_gateway(self) -> None:
        crop = Image.new("RGB", (64, 128))
        expected = PersonEmbeddingResult(
            embedding=_unit_vec(10), detection_id="d1", model_id=OSNET_ID
        )
        with patch(
            "backend.services.reid_gateway.embed_person_via_gateway",
            new=AsyncMock(return_value=expected),
        ) as gw:
            out = await extract_person_embedding(
                {"kind": "gateway", "base_url": "http://gw/enrich-lt", "model_id": None},
                crop,
                detection_id="d1",
            )
        assert out is expected
        gw.assert_awaited_once_with(crop, base_url="http://gw/enrich-lt", detection_id="d1")


class TestExtractPersonEmbeddingsBatch:
    @pytest.mark.asyncio
    async def test_batch_raises_gateway_per_crop_error(self) -> None:
        with pytest.raises(RuntimeError, match="gateway handle embeds per crop"):
            await extract_person_embeddings_batch(
                {"kind": "gateway", "base_url": "http://gw/enrich-lt"},
                [Image.new("RGB", (32, 64))],
            )


class TestMatchPersonEmbeddings:
    def test_match_person_embeddings_sorted_by_similarity(self) -> None:
        q = PersonEmbeddingResult(embedding=_unit_vec(100))
        g_same = PersonEmbeddingResult(embedding=q.embedding.copy(), detection_id="same")
        g_orth = PersonEmbeddingResult(embedding=-q.embedding.copy(), detection_id="opp")
        matches = match_person_embeddings(q, [g_orth, g_same], threshold=0.7)
        assert len(matches) == 1
        assert matches[0][0].detection_id == "same"
        assert matches[0][1] == pytest.approx(1.0, abs=1e-5)

    def test_match_person_embeddings_empty_gallery(self) -> None:
        q = PersonEmbeddingResult(embedding=_unit_vec(101))
        assert match_person_embeddings(q, []) == []


class TestFormatPersonReidContext:
    def test_format_person_reid_context_no_matches(self) -> None:
        text = format_person_reid_context([], "det_1")
        assert "No prior matches found" in text

    def test_format_person_reid_context_bands(self) -> None:
        m1 = PersonEmbeddingResult(embedding=_unit_vec(1), detection_id="d_high")
        m2 = PersonEmbeddingResult(embedding=_unit_vec(2), detection_id="d_med")
        m3 = PersonEmbeddingResult(embedding=_unit_vec(3), detection_id="d_low")
        text = format_person_reid_context([(m1, 0.95), (m2, 0.85), (m3, 0.75)], "probe")
        assert "HIGH CONFIDENCE match to d_high" in text
        assert "Likely same person as d_med" in text
        assert "Possible match to d_low" in text
