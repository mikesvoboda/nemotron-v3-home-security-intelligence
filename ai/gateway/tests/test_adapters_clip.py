"""Unit tests for the CLIP gateway adapter.

Tests the CLIP adapter endpoints (embed, classify, similarity, batch-similarity,
anomaly-score, health) with mocked Triton client, verifying embedding
normalization, cosine similarity, softmax scoring, and error handling.
"""

from __future__ import annotations

import base64
import io
from unittest.mock import AsyncMock, patch

import numpy as np
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from PIL import Image

from ai.gateway.adapters.clip import (
    EMBEDDING_DIMENSION,
    VISION_MODEL_NAME,
    _cosine_similarity,
    _get_image_embedding,
    _get_text_embeddings,
    router,
)
from ai.gateway.triton_client import TritonClientError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_b64_image(width: int = 224, height: int = 224) -> str:
    """Create a small test image encoded as base64."""
    img = Image.new("RGB", (width, height), color=(100, 150, 200))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def _make_embedding(dim: int = EMBEDDING_DIMENSION, seed: int = 42) -> np.ndarray:
    """Create a random normalized embedding array of shape (1, dim)."""
    rng = np.random.RandomState(seed)
    vec = rng.randn(1, dim).astype(np.float32)
    vec /= np.linalg.norm(vec) + 1e-8
    return vec


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_triton():
    """Create a mock Triton client."""
    client = AsyncMock()
    client.infer = AsyncMock()
    client.is_model_ready = AsyncMock(return_value=True)
    return client


@pytest.fixture
def app():
    """Create a test FastAPI app with the CLIP router."""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
async def client(app, mock_triton):
    """Create an async test client with mocked Triton."""
    with (
        patch("ai.gateway.adapters.clip.get_triton_client", return_value=mock_triton),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c


# =============================================================================
# _cosine_similarity unit tests
# =============================================================================


class TestCosineSimilarity:
    """Tests for the cosine similarity helper."""

    def test_identical_vectors(self):
        """Identical vectors have similarity 1.0."""
        vec = [1.0, 0.0, 0.0]
        assert abs(_cosine_similarity(vec, vec) - 1.0) < 1e-5

    def test_orthogonal_vectors(self):
        """Orthogonal vectors have similarity 0.0."""
        a = [1.0, 0.0, 0.0]
        b = [0.0, 1.0, 0.0]
        assert abs(_cosine_similarity(a, b)) < 1e-5

    def test_opposite_vectors(self):
        """Opposite vectors have similarity -1.0."""
        a = [1.0, 0.0, 0.0]
        b = [-1.0, 0.0, 0.0]
        assert abs(_cosine_similarity(a, b) - (-1.0)) < 1e-5

    def test_zero_vector_returns_zero(self):
        """A zero vector produces similarity 0.0."""
        a = [0.0, 0.0, 0.0]
        b = [1.0, 2.0, 3.0]
        assert _cosine_similarity(a, b) == 0.0

    def test_high_dimensional_normalized(self):
        """High-dimensional normalized vectors produce correct similarity."""
        rng = np.random.RandomState(1)
        a = rng.randn(768).astype(np.float32)
        a = (a / np.linalg.norm(a)).tolist()
        sim = _cosine_similarity(a, a)
        assert abs(sim - 1.0) < 1e-4


# =============================================================================
# /embed endpoint tests
# =============================================================================


class TestEmbedEndpoint:
    """Tests for the POST /embed endpoint."""

    async def test_embed_success(self, client, mock_triton):
        """Successful embedding returns 768-dim vector."""
        embedding = _make_embedding()
        mock_triton.infer.return_value = {"output": embedding}

        response = await client.post("/embed", json={"image": _make_b64_image()})

        assert response.status_code == 200
        data = response.json()
        assert len(data["embedding"]) == EMBEDDING_DIMENSION
        assert "inference_time_ms" in data

    async def test_embed_normalized(self, client, mock_triton):
        """Returned embedding is L2-normalized."""
        rng = np.random.RandomState(99)
        raw = rng.randn(1, EMBEDDING_DIMENSION).astype(np.float32) * 10
        mock_triton.infer.return_value = {"output": raw}

        response = await client.post("/embed", json={"image": _make_b64_image()})

        data = response.json()
        emb = np.array(data["embedding"])
        norm = np.linalg.norm(emb)
        assert abs(norm - 1.0) < 0.01

    async def test_embed_invalid_base64(self, client, mock_triton):
        """Invalid base64 image returns 400."""
        response = await client.post("/embed", json={"image": "not-valid-base64!@#"})
        assert response.status_code == 400

    async def test_embed_triton_error(self, client, mock_triton):
        """Triton failure returns 503."""
        mock_triton.infer.side_effect = TritonClientError("Model crashed")

        response = await client.post("/embed", json={"image": _make_b64_image()})
        assert response.status_code == 503

    async def test_embed_wrong_dimension(self, client, mock_triton):
        """Wrong embedding dimension returns 500."""
        mock_triton.infer.return_value = {"output": np.zeros((1, 256), dtype=np.float32)}

        response = await client.post("/embed", json={"image": _make_b64_image()})
        assert response.status_code == 500


# =============================================================================
# /classify endpoint tests
# =============================================================================


class TestClassifyEndpoint:
    """Tests for the POST /classify endpoint."""

    async def test_classify_success(self, client, mock_triton):
        """Classification returns scores for all labels."""
        embedding = _make_embedding()
        mock_triton.infer.return_value = {"output": embedding}
        # is_model_ready called for clip_text model
        mock_triton.is_model_ready.return_value = False

        response = await client.post(
            "/classify",
            json={
                "image": _make_b64_image(),
                "labels": ["cat", "dog", "person"],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "scores" in data
        assert len(data["scores"]) == 3
        assert "top_label" in data
        assert data["top_label"] in ["cat", "dog", "person"]
        assert "inference_time_ms" in data

    async def test_classify_empty_labels(self, client, mock_triton):
        """Empty labels list returns 400."""
        response = await client.post(
            "/classify",
            json={"image": _make_b64_image(), "labels": []},
        )
        assert response.status_code == 400

    async def test_classify_scores_sum_to_one(self, client, mock_triton):
        """Classification scores (softmax) sum to approximately 1."""
        embedding = _make_embedding()
        mock_triton.infer.return_value = {"output": embedding}
        mock_triton.is_model_ready.return_value = False

        response = await client.post(
            "/classify",
            json={"image": _make_b64_image(), "labels": ["a", "b", "c"]},
        )

        data = response.json()
        total = sum(data["scores"].values())
        assert abs(total - 1.0) < 0.01


# =============================================================================
# /similarity endpoint tests
# =============================================================================


class TestSimilarityEndpoint:
    """Tests for the POST /similarity endpoint."""

    async def test_similarity_success(self, client, mock_triton):
        """Similarity returns a float score."""
        embedding = _make_embedding()
        mock_triton.infer.return_value = {"output": embedding}
        mock_triton.is_model_ready.return_value = False

        response = await client.post(
            "/similarity",
            json={"image": _make_b64_image(), "text": "a cat"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "similarity" in data
        assert isinstance(data["similarity"], float)
        assert "inference_time_ms" in data


# =============================================================================
# /batch-similarity endpoint tests
# =============================================================================


class TestBatchSimilarityEndpoint:
    """Tests for the POST /batch-similarity endpoint."""

    async def test_batch_similarity_success(self, client, mock_triton):
        """Batch similarity returns per-text scores."""
        embedding = _make_embedding()
        mock_triton.infer.return_value = {"output": embedding}
        mock_triton.is_model_ready.return_value = False

        response = await client.post(
            "/batch-similarity",
            json={"image": _make_b64_image(), "texts": ["cat", "dog"]},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["similarities"]) == 2
        assert "cat" in data["similarities"]
        assert "dog" in data["similarities"]

    async def test_batch_similarity_empty_texts(self, client, mock_triton):
        """Empty texts list returns 400."""
        response = await client.post(
            "/batch-similarity",
            json={"image": _make_b64_image(), "texts": []},
        )
        assert response.status_code == 400


# =============================================================================
# /anomaly-score endpoint tests
# =============================================================================


class TestAnomalyScoreEndpoint:
    """Tests for the POST /anomaly-score endpoint."""

    async def test_anomaly_score_success(self, client, mock_triton):
        """Anomaly score returns values in [0, 1]."""
        embedding = _make_embedding()
        mock_triton.infer.return_value = {"output": embedding}

        baseline = [0.0] * EMBEDDING_DIMENSION
        baseline[0] = 1.0

        response = await client.post(
            "/anomaly-score",
            json={
                "image": _make_b64_image(),
                "baseline_embedding": baseline,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert 0.0 <= data["anomaly_score"] <= 1.0
        assert "similarity_to_baseline" in data

    async def test_anomaly_score_wrong_dimension(self, client, mock_triton):
        """Wrong baseline dimension returns 400."""
        response = await client.post(
            "/anomaly-score",
            json={
                "image": _make_b64_image(),
                "baseline_embedding": [0.1] * 256,
            },
        )
        assert response.status_code == 400

    async def test_anomaly_score_identical_to_baseline(self, client, mock_triton):
        """Identical image and baseline gives anomaly score near 0."""
        # Create a specific normalized embedding
        vec = np.zeros(EMBEDDING_DIMENSION, dtype=np.float32)
        vec[0] = 1.0
        mock_triton.infer.return_value = {"output": vec.reshape(1, -1)}

        baseline = vec.tolist()

        response = await client.post(
            "/anomaly-score",
            json={
                "image": _make_b64_image(),
                "baseline_embedding": baseline,
            },
        )

        data = response.json()
        assert data["anomaly_score"] < 0.05
        assert data["similarity_to_baseline"] > 0.95


# =============================================================================
# /health endpoint tests
# =============================================================================


class TestHealthEndpoint:
    """Tests for the GET /health endpoint."""

    async def test_health_model_ready(self, client, mock_triton):
        """Returns healthy when model is ready."""
        mock_triton.is_model_ready.return_value = True

        response = await client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["model_loaded"] is True
        assert data["embedding_dimension"] == EMBEDDING_DIMENSION

    async def test_health_model_not_ready(self, client, mock_triton):
        """Returns degraded when model is not ready."""
        mock_triton.is_model_ready.return_value = False

        response = await client.get("/health")

        data = response.json()
        assert data["status"] == "degraded"
        assert data["model_loaded"] is False


# =============================================================================
# _get_text_embeddings fallback tests
# =============================================================================


class TestGetTextEmbeddings:
    """Tests for the text embedding helper."""

    async def test_fallback_when_no_text_model(self, mock_triton):
        """Returns zero embeddings when clip_text model not available."""
        mock_triton.is_model_ready.return_value = False

        with patch("ai.gateway.adapters.clip.get_triton_client", return_value=mock_triton):
            result = await _get_text_embeddings(["hello", "world"])

        assert result.shape == (2, EMBEDDING_DIMENSION)
        assert np.allclose(result, 0.0)

    async def test_triton_text_model_used(self, mock_triton):
        """Uses clip_text model when available."""
        mock_triton.is_model_ready.return_value = True
        text_embs = np.random.randn(2, EMBEDDING_DIMENSION).astype(np.float32)
        mock_triton.infer.return_value = {"text_embedding": text_embs}

        with patch("ai.gateway.adapters.clip.get_triton_client", return_value=mock_triton):
            result = await _get_text_embeddings(["hello", "world"])

        assert result.shape == (2, EMBEDDING_DIMENSION)
        # Check L2 normalized
        norms = np.linalg.norm(result, axis=1)
        np.testing.assert_allclose(norms, 1.0, atol=0.01)
