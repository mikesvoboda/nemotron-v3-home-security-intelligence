"""Unit tests for the enrichment-light gateway adapter.

Tests the enrichment-light adapter endpoints (pose-analyze, threat-detect,
person-reid, pet-classify, depth-estimate, health) with mocked Triton client.
"""

from __future__ import annotations

import base64
import io
import json
import math
from unittest.mock import AsyncMock, patch

import numpy as np
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from PIL import Image

from ai.gateway.adapters.enrichment_light import (
    _softmax,
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


def _make_pet_logits(cat_score: float = 3.0, dog_score: float = 1.0) -> np.ndarray:
    """Create pet classification logits."""
    return np.array([cat_score, dog_score], dtype=np.float32)


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
    """Create a test FastAPI app with the enrichment-light router."""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
async def client(app, mock_triton):
    """Create an async test client with mocked Triton."""
    with patch(
        "ai.gateway.adapters.enrichment_light.get_triton_client",
        return_value=mock_triton,
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c


# =============================================================================
# _softmax unit tests
# =============================================================================


class TestSoftmax:
    """Tests for the softmax helper."""

    def test_softmax_sums_to_one(self):
        """Softmax output sums to approximately 1."""
        logits = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        probs = _softmax(logits)
        assert abs(probs.sum() - 1.0) < 0.001

    def test_softmax_large_values_no_overflow(self):
        """Handles large values without overflow."""
        logits = np.array([1000.0, 1001.0, 999.0], dtype=np.float32)
        probs = _softmax(logits)
        assert not np.any(np.isnan(probs))
        assert abs(probs.sum() - 1.0) < 0.01


# =============================================================================
# /pose-analyze endpoint tests
# =============================================================================


class TestPoseAnalyzeEndpoint:
    """Tests for the POST /pose-analyze endpoint."""

    async def test_pose_analyze_success(self, client, mock_triton):
        """Pose analysis returns keypoints and person count."""
        keypoints = [
            {"nose": [100, 50], "left_eye": [95, 45], "right_eye": [105, 45]},
            {"nose": [200, 100], "left_eye": [195, 95], "right_eye": [205, 95]},
        ]
        output = np.array([json.dumps(keypoints).encode("utf-8")], dtype=object)
        mock_triton.infer.return_value = {"OUTPUT_KEYPOINTS": output}

        response = await client.post(
            "/pose-analyze",
            json={"image": _make_b64_image()},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["num_people"] == 2
        assert len(data["keypoints"]) == 2
        assert "inference_time_ms" in data

    async def test_pose_analyze_no_people(self, client, mock_triton):
        """No people detected returns empty keypoints."""
        output = np.array([json.dumps([]).encode("utf-8")], dtype=object)
        mock_triton.infer.return_value = {"OUTPUT_KEYPOINTS": output}

        response = await client.post(
            "/pose-analyze",
            json={"image": _make_b64_image()},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["num_people"] == 0
        assert data["keypoints"] == []

    async def test_pose_analyze_non_object_dtype(self, client, mock_triton):
        """Non-object dtype returns empty keypoints."""
        output = np.array([0], dtype=np.int32)
        mock_triton.infer.return_value = {"OUTPUT_KEYPOINTS": output}

        response = await client.post(
            "/pose-analyze",
            json={"image": _make_b64_image()},
        )

        assert response.status_code == 200
        assert response.json()["keypoints"] == []

    async def test_pose_analyze_triton_error(self, client, mock_triton):
        """Triton failure returns 503."""
        mock_triton.infer.side_effect = TritonClientError("Backend error")

        response = await client.post(
            "/pose-analyze",
            json={"image": _make_b64_image()},
        )
        assert response.status_code == 503

    async def test_pose_analyze_invalid_image(self, client, mock_triton):
        """Invalid base64 returns 400."""
        response = await client.post(
            "/pose-analyze",
            json={"image": "not-valid-base64!@#$"},
        )
        assert response.status_code == 400


# =============================================================================
# /threat-detect endpoint tests
# =============================================================================


class TestThreatDetectEndpoint:
    """Tests for the POST /threat-detect endpoint."""

    async def test_threat_detected(self, client, mock_triton):
        """Threat detected returns correct fields."""
        detections = [{"class": "knife", "confidence": 0.92, "bbox": [10, 20, 100, 200]}]
        output = np.array([json.dumps(detections).encode("utf-8")], dtype=object)
        mock_triton.infer.return_value = {"OUTPUT_DETECTIONS": output}

        response = await client.post(
            "/threat-detect",
            json={"image": _make_b64_image()},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["threat_detected"] is True
        assert data["threat_type"] == "knife"
        assert data["confidence"] == 0.92
        assert len(data["detections"]) == 1

    async def test_no_threat(self, client, mock_triton):
        """No threat returns threat_detected=False."""
        output = np.array([json.dumps([]).encode("utf-8")], dtype=object)
        mock_triton.infer.return_value = {"OUTPUT_DETECTIONS": output}

        response = await client.post(
            "/threat-detect",
            json={"image": _make_b64_image()},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["threat_detected"] is False
        assert data["threat_type"] is None
        assert data["confidence"] == 0.0
        assert data["detections"] == []

    async def test_threat_detect_non_object_dtype(self, client, mock_triton):
        """Non-object dtype returns no threats."""
        output = np.array([0], dtype=np.int32)
        mock_triton.infer.return_value = {"OUTPUT_DETECTIONS": output}

        response = await client.post(
            "/threat-detect",
            json={"image": _make_b64_image()},
        )

        assert response.status_code == 200
        assert response.json()["threat_detected"] is False

    async def test_threat_detect_triton_error(self, client, mock_triton):
        """Triton failure returns 503."""
        mock_triton.infer.side_effect = TritonClientError("Model not loaded")

        response = await client.post(
            "/threat-detect",
            json={"image": _make_b64_image()},
        )
        assert response.status_code == 503


# =============================================================================
# /person-reid endpoint tests
# =============================================================================


class TestPersonReIDEndpoint:
    """Tests for the POST /person-reid endpoint."""

    async def test_person_reid_success(self, client, mock_triton):
        """Person ReID returns a normalized embedding."""
        raw_emb = np.random.randn(1, 512).astype(np.float32)
        mock_triton.infer.return_value = {"output": raw_emb}

        response = await client.post(
            "/person-reid",
            json={"image": _make_b64_image()},
        )

        assert response.status_code == 200
        data = response.json()
        assert "embedding" in data
        assert data["embedding_dimension"] == len(data["embedding"])
        # Check L2 normalization
        norm = math.sqrt(sum(x * x for x in data["embedding"]))
        assert abs(norm - 1.0) < 0.01

    async def test_person_reid_embedding_dimension(self, client, mock_triton):
        """Embedding dimension field matches actual embedding length."""
        raw_emb = np.random.randn(1, 256).astype(np.float32)
        mock_triton.infer.return_value = {"output": raw_emb}

        response = await client.post(
            "/person-reid",
            json={"image": _make_b64_image()},
        )

        data = response.json()
        assert data["embedding_dimension"] == 256

    async def test_person_reid_triton_error(self, client, mock_triton):
        """Triton failure returns 503."""
        mock_triton.infer.side_effect = TritonClientError("Error")

        response = await client.post(
            "/person-reid",
            json={"image": _make_b64_image()},
        )
        assert response.status_code == 503

    async def test_person_reid_invalid_image(self, client, mock_triton):
        """Invalid base64 returns 400."""
        response = await client.post(
            "/person-reid",
            json={"image": "bad!@#$"},
        )
        assert response.status_code == 400


# =============================================================================
# /pet-classify endpoint tests
# =============================================================================


class TestPetClassifyEndpoint:
    """Tests for the POST /pet-classify endpoint."""

    async def test_pet_classify_cat(self, client, mock_triton):
        """Cat classification returns correct pet_type."""
        mock_triton.infer.return_value = {
            "output": np.array([_make_pet_logits(cat_score=5.0, dog_score=1.0)])
        }

        response = await client.post(
            "/pet-classify",
            json={"image": _make_b64_image()},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["pet_type"] == "cat"
        assert data["cat_score"] > data["dog_score"]
        assert data["is_household_pet"] is True
        assert data["breed"] == "unknown"

    async def test_pet_classify_dog(self, client, mock_triton):
        """Dog classification returns correct pet_type."""
        mock_triton.infer.return_value = {
            "output": np.array([_make_pet_logits(cat_score=0.5, dog_score=5.0)])
        }

        response = await client.post(
            "/pet-classify",
            json={"image": _make_b64_image()},
        )

        assert response.status_code == 200
        assert response.json()["pet_type"] == "dog"

    async def test_pet_classify_triton_error(self, client, mock_triton):
        """Triton failure returns 503."""
        mock_triton.infer.side_effect = TritonClientError("Model error")

        response = await client.post(
            "/pet-classify",
            json={"image": _make_b64_image()},
        )
        assert response.status_code == 503


# =============================================================================
# /depth-estimate endpoint tests
# =============================================================================


class TestDepthEstimateEndpoint:
    """Tests for the POST /depth-estimate endpoint."""

    async def test_depth_estimate_success(self, client, mock_triton):
        """Depth estimation returns depth statistics and base64 map."""
        depth_map = np.random.rand(1, 518, 518).astype(np.float32) * 10.0
        mock_triton.infer.return_value = {"output": depth_map}

        response = await client.post(
            "/depth-estimate",
            json={"image": _make_b64_image()},
        )

        assert response.status_code == 200
        data = response.json()
        assert "depth_map_base64" in data
        assert data["min_depth"] < data["max_depth"]
        assert data["min_depth"] <= data["mean_depth"] <= data["max_depth"]
        # Verify depth_map_base64 is valid base64
        decoded = base64.b64decode(data["depth_map_base64"])
        assert len(decoded) > 0

    async def test_depth_estimate_flat_map(self, client, mock_triton):
        """Constant depth produces equal min/max/mean."""
        depth_map = np.full((1, 518, 518), 3.5, dtype=np.float32)
        mock_triton.infer.return_value = {"output": depth_map}

        response = await client.post(
            "/depth-estimate",
            json={"image": _make_b64_image()},
        )

        data = response.json()
        assert data["min_depth"] == data["max_depth"] == data["mean_depth"]

    async def test_depth_estimate_squeezable(self, client, mock_triton):
        """Depth map with extra dims (3D+) is squeezed correctly."""
        depth_map = np.random.rand(1, 1, 518, 518).astype(np.float32) * 5.0
        mock_triton.infer.return_value = {"output": depth_map}

        response = await client.post(
            "/depth-estimate",
            json={"image": _make_b64_image()},
        )

        assert response.status_code == 200
        assert "depth_map_base64" in response.json()

    async def test_depth_estimate_triton_error(self, client, mock_triton):
        """Triton failure returns 503."""
        mock_triton.infer.side_effect = TritonClientError("OOM")

        response = await client.post(
            "/depth-estimate",
            json={"image": _make_b64_image()},
        )
        assert response.status_code == 503


# =============================================================================
# /health endpoint tests
# =============================================================================


class TestHealthEndpoint:
    """Tests for the GET /health endpoint."""

    async def test_health_all_ready(self, client, mock_triton):
        """Returns healthy when all models are ready."""
        mock_triton.is_model_ready.return_value = True

        response = await client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        expected_models = {"pose", "threat", "reid", "pet", "depth"}
        assert set(data["models"].keys()) == expected_models
        assert all(v is True for v in data["models"].values())

    async def test_health_some_degraded(self, client, mock_triton):
        """Returns degraded when some models are not ready."""

        async def model_ready(name):
            return name != "threat"

        mock_triton.is_model_ready.side_effect = model_ready

        response = await client.get("/health")

        data = response.json()
        assert data["status"] == "degraded"
        assert data["models"]["threat"] is False
        assert data["models"]["pose"] is True

    async def test_health_all_down(self, client, mock_triton):
        """Returns degraded when all models are down."""
        mock_triton.is_model_ready.return_value = False

        response = await client.get("/health")

        data = response.json()
        assert data["status"] == "degraded"
        assert all(v is False for v in data["models"].values())
