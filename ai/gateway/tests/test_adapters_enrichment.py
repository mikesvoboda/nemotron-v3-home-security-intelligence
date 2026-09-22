"""Unit tests for the enrichment (heavy) gateway adapter.

Tests the enrichment adapter endpoints (vehicle-classify, clothing-classify,
demographics, action-classify, pet-classify, depth-estimate, pose-analyze,
enrich, health) with mocked Triton client.
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

from ai.gateway.adapters.enrichment import (
    NTU60_LABELS,
    _classify_with_text_embeddings,
    _infer_vehicle,
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


def _make_vehicle_logits() -> np.ndarray:
    """Create vehicle classification logits (11 classes)."""
    logits = np.zeros(11, dtype=np.float32)
    logits[4] = 5.0  # car class index
    return logits


def _make_pet_logits(cat_score: float = 3.0, dog_score: float = 1.0) -> np.ndarray:
    """Create pet classification logits (2 classes: cat, dog)."""
    return np.array([cat_score, dog_score], dtype=np.float32)


def _make_demographics_logits(
    age_idx: int = 2, gender_idx: int = 0
) -> tuple[np.ndarray, np.ndarray]:
    """Create age and gender classification logits."""
    age_logits = np.zeros(8, dtype=np.float32)
    age_logits[age_idx] = 5.0

    gender_logits = np.zeros(2, dtype=np.float32)
    gender_logits[gender_idx] = 5.0

    return age_logits, gender_logits


def _make_pose_output(confidence: float = 0.0) -> np.ndarray:
    """Create a YOLOv8-pose output (1, 56, 8400) with one person in slot 0.

    ``confidence`` <= 0 means "no detections" (all values zero).
    """
    output = np.zeros((1, 56, 8400), dtype=np.float32)
    if confidence <= 0:
        return output
    output[0, 0, 0] = 320.0  # cx
    output[0, 1, 0] = 320.0  # cy
    output[0, 2, 0] = 100.0  # w
    output[0, 3, 0] = 200.0  # h
    output[0, 4, 0] = confidence
    for i in range(17):
        output[0, 5 + i * 3, 0] = 300.0 + i  # x
        output[0, 6 + i * 3, 0] = 200.0 + i  # y
        output[0, 7 + i * 3, 0] = 0.8  # visibility
    return output


def _make_stgcn_logits(action_idx: int = 42) -> np.ndarray:
    """Create ST-GCN++ classification logits (60 NTU-60 classes)."""
    logits = np.zeros((1, 60), dtype=np.float32)
    logits[0, action_idx] = 5.0
    return logits


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
    """Create a test FastAPI app with the enrichment router."""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
async def client(app, mock_triton):
    """Create an async test client with mocked Triton."""
    with patch("ai.gateway.adapters.enrichment.get_triton_client", return_value=mock_triton):
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

    def test_softmax_preserves_order(self):
        """Larger input produces larger output."""
        logits = np.array([1.0, 3.0, 2.0], dtype=np.float32)
        probs = _softmax(logits)
        assert probs[1] > probs[2] > probs[0]

    def test_softmax_uniform_input(self):
        """Equal inputs produce equal outputs."""
        logits = np.array([2.0, 2.0, 2.0], dtype=np.float32)
        probs = _softmax(logits)
        np.testing.assert_allclose(probs, 1.0 / 3, atol=0.01)

    def test_softmax_large_values(self):
        """Handles large values without overflow (max-subtraction trick)."""
        logits = np.array([1000.0, 1001.0, 999.0], dtype=np.float32)
        probs = _softmax(logits)
        assert not np.any(np.isnan(probs))
        assert not np.any(np.isinf(probs))
        assert abs(probs.sum() - 1.0) < 0.01


# =============================================================================
# _classify_with_text_embeddings unit tests
# =============================================================================


class TestClassifyWithTextEmbeddings:
    """Tests for zero-shot clothing classification logic."""

    def _make_text_cache(self) -> dict:
        """Build a deterministic text embedding cache for testing."""
        np.random.seed(42)
        cache = {}
        defs = {
            "clothing_type": ["hoodie", "jacket", "t-shirt"],
            "color": ["black", "red", "white"],
            "style": ["casual", "formal", "athletic"],
            "suspicious": ["ski_mask", "all_black_outfit"],
            "service_uniform": ["delivery", "police"],
        }
        for cat, labels in defs.items():
            embs = np.random.randn(len(labels), 768).astype(np.float32)
            norms = np.linalg.norm(embs, axis=1, keepdims=True)
            cache[cat] = (labels, embs / norms)
        return cache

    def test_returns_all_fields(self):
        """Classification result contains all required fields."""
        cache = self._make_text_cache()
        img_emb = np.random.randn(768).astype(np.float32)
        result = _classify_with_text_embeddings(img_emb, cache)
        assert "clothing_type" in result
        assert "color" in result
        assert "style" in result
        assert "confidence" in result
        assert "description" in result
        assert "is_suspicious" in result
        assert "is_service_uniform" in result
        assert "top_category" in result

    def test_picks_best_match(self):
        """Classification picks the label whose embedding is closest."""
        cache = self._make_text_cache()
        # Use the first clothing_type embedding as the image embedding
        # so it should match that label
        labels, embs = cache["clothing_type"]
        img_emb = embs[0].copy()
        result = _classify_with_text_embeddings(img_emb, cache)
        assert result["clothing_type"] == labels[0]

    def test_handles_2d_embedding(self):
        """Works with shape (1, 768) input."""
        cache = self._make_text_cache()
        img_emb = np.random.randn(1, 768).astype(np.float32)
        result = _classify_with_text_embeddings(img_emb, cache)
        assert isinstance(result["clothing_type"], str)

    def test_suspicious_flag(self):
        """High similarity to suspicious prompt sets is_suspicious=True."""
        cache = self._make_text_cache()
        # Use the suspicious embedding directly
        _labels, suspicious_embs = cache["suspicious"]
        img_emb = suspicious_embs[0].copy() * 10  # amplify to ensure high sim
        result = _classify_with_text_embeddings(img_emb, cache)
        assert result["is_suspicious"] is True


# =============================================================================
# /vehicle-classify endpoint tests
# =============================================================================


class TestVehicleClassifyEndpoint:
    """Tests for the POST /vehicle-classify endpoint."""

    async def test_vehicle_classify_success(self, client, mock_triton):
        """Successful vehicle classification returns expected fields."""
        mock_triton.infer.return_value = {"output": np.array([_make_vehicle_logits()])}

        response = await client.post(
            "/vehicle-classify",
            json={"image": _make_b64_image()},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["vehicle_type"] == "car"
        assert "display_name" in data
        assert "confidence" in data
        assert isinstance(data["is_commercial"], bool)
        assert data["is_commercial"] is False
        assert "all_scores" in data
        assert "inference_time_ms" in data

    async def test_vehicle_classify_commercial(self, client, mock_triton):
        """Commercial vehicle types are flagged."""
        logits = np.zeros(11, dtype=np.float32)
        logits[0] = 5.0  # articulated_truck
        mock_triton.infer.return_value = {"output": np.array([logits])}

        response = await client.post(
            "/vehicle-classify",
            json={"image": _make_b64_image()},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["is_commercial"] is True

    async def test_vehicle_classify_triton_error(self, client, mock_triton):
        """Triton failure returns 503."""
        mock_triton.infer.side_effect = TritonClientError("GPU error")

        response = await client.post(
            "/vehicle-classify",
            json={"image": _make_b64_image()},
        )

        assert response.status_code == 503

    async def test_vehicle_classify_invalid_image(self, client, mock_triton):
        """Invalid base64 image returns 400."""
        response = await client.post(
            "/vehicle-classify",
            json={"image": "not-valid-base64!@#"},
        )
        assert response.status_code == 400


# =============================================================================
# /clothing-classify endpoint tests
# =============================================================================


class TestClothingClassifyEndpoint:
    """Tests for the POST /clothing-classify endpoint."""

    async def test_clothing_classify_placeholder_fallback(self, client, mock_triton):
        """Returns placeholder fields when text encoder is unavailable."""
        emb = np.random.randn(1, 768).astype(np.float32)
        mock_triton.infer.return_value = {"embedding": emb}

        with patch(
            "ai.gateway.adapters.enrichment._ensure_clothing_text_embeddings",
            return_value=None,
        ):
            response = await client.post(
                "/clothing-classify",
                json={"image": _make_b64_image()},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["clothing_type"] == "casual"
        assert data["color"] == "unknown"
        assert data["style"] == "everyday"
        assert isinstance(data["is_suspicious"], bool)
        assert isinstance(data["is_service_uniform"], bool)
        assert "inference_time_ms" in data

    async def test_clothing_classify_zero_shot(self, client, mock_triton):
        """Returns real results when text embeddings are available."""
        emb = np.random.randn(1, 768).astype(np.float32)
        mock_triton.infer.return_value = {"embedding": emb}

        fake_cache = {}
        for cat, n in [
            ("clothing_type", 15),
            ("color", 14),
            ("style", 8),
            ("suspicious", 5),
            ("service_uniform", 7),
        ]:
            labels = [f"label_{i}" for i in range(n)]
            embeddings = np.random.randn(n, 768).astype(np.float32)
            norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
            fake_cache[cat] = (labels, embeddings / norms)

        with patch(
            "ai.gateway.adapters.enrichment._ensure_clothing_text_embeddings",
            return_value=fake_cache,
        ):
            response = await client.post(
                "/clothing-classify",
                json={"image": _make_b64_image()},
            )

        assert response.status_code == 200
        data = response.json()
        assert "clothing_type" in data
        assert "color" in data
        assert "style" in data
        assert "confidence" in data
        assert "description" in data
        assert isinstance(data["is_suspicious"], bool)
        assert isinstance(data["is_service_uniform"], bool)
        assert "inference_time_ms" in data

    async def test_clothing_classify_triton_error(self, client, mock_triton):
        """Triton failure returns 503."""
        mock_triton.infer.side_effect = TritonClientError("OOM")

        response = await client.post(
            "/clothing-classify",
            json={"image": _make_b64_image()},
        )
        assert response.status_code == 503


# =============================================================================
# /demographics endpoint tests
# =============================================================================


class TestDemographicsEndpoint:
    """Tests for the POST /demographics endpoint."""

    async def test_demographics_success(self, client, mock_triton):
        """Successful demographics returns age and gender."""
        age_logits, gender_logits = _make_demographics_logits(age_idx=2, gender_idx=0)

        mock_triton.infer.side_effect = [
            {"output": np.array([age_logits])},
            {"output": np.array([gender_logits])},
        ]

        response = await client.post(
            "/demographics",
            json={"image": _make_b64_image()},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["age_range"] == "21-30"
        assert data["gender"] == "male"
        assert 0 <= data["age_confidence"] <= 1
        assert 0 <= data["gender_confidence"] <= 1

    async def test_demographics_triton_error(self, client, mock_triton):
        """Triton failure returns 503."""
        mock_triton.infer.side_effect = TritonClientError("Model unavailable")

        response = await client.post(
            "/demographics",
            json={"image": _make_b64_image()},
        )
        assert response.status_code == 503


# =============================================================================
# /action-classify endpoint tests
# =============================================================================


class TestActionClassifyEndpoint:
    """Tests for the POST /action-classify endpoint (ST-GCN++ pipeline).

    NEM-5563: xclip_action retired; /action-classify now runs each frame
    through Triton ``pose`` (keypoint extraction), resamples the track to
    (1, 2, 100, 17, 3) and classifies it with Triton ``stgcn_action``.
    """

    async def test_action_classify_success(self, client, mock_triton):
        """Frames with a person classify to an NTU-60 label."""
        calls: list[str] = []

        async def _infer(*, model_name, inputs, outputs, timeout=None):
            calls.append(model_name)
            if model_name == "pose":
                return {"output0": _make_pose_output(confidence=0.9)}
            return {"output": _make_stgcn_logits(action_idx=42)}  # falling

        mock_triton.infer.side_effect = _infer

        response = await client.post(
            "/action-classify",
            json={"frames": [_make_b64_image(), _make_b64_image()], "top_k": 5},
        )

        assert response.status_code == 200
        data = response.json()
        # Shipped contract (WP6.4 triage): /action-classify returns a SINGLE
        # top-level action object (ActionClassifyResponse: action/confidence/
        # is_suspicious/risk_weight/all_scores) — same shape as the legacy
        # service (ai/enrichment/model.py) and the backend consumer
        # (enrichment_client.py ActionClassificationResult). The plural
        # "actions" list per-frame never existed anywhere.
        assert calls == ["pose", "pose", "stgcn_action"]
        assert data["action"] == NTU60_LABELS[42]  # "falling"
        # softmax of a single logit-5.0 class over 60 classes
        assert data["confidence"] == pytest.approx(0.7155, abs=0.01)
        # NTU index 42 is in STGCN_HIGH_RISK_INDICES (stgcn_loader parity).
        assert data["is_suspicious"] is True
        assert data["risk_weight"] == 0.8
        assert set(data["all_scores"]) <= set(NTU60_LABELS)
        assert len(data["all_scores"]) == 5

    async def test_action_classify_skeleton_tensor_shape(self, client, mock_triton):
        """stgcn_action receives (1, 2, 100, 17, 3) FP32 named 'input'."""
        seen: dict[str, np.ndarray] = {}

        async def _infer(*, model_name, inputs, outputs, timeout=None):
            if model_name == "pose":
                return {"output0": _make_pose_output(confidence=0.9)}
            seen["input"] = inputs["input"]
            return {"output": _make_stgcn_logits(action_idx=7)}  # sitting down

        mock_triton.infer.side_effect = _infer

        response = await client.post(
            "/action-classify",
            json={"frames": [_make_b64_image()] * 4, "top_k": 3},
        )

        assert response.status_code == 200
        tensor = seen["input"]
        assert tensor.shape == (1, 2, 100, 17, 3)
        assert tensor.dtype == np.float32
        # Person slot 2 is the zero pad; slot 1 carries the resampled track.
        assert np.allclose(tensor[0, 1], 0.0)
        assert np.any(tensor[0, 0] != 0.0)
        assert response.json()["is_suspicious"] is False
        assert response.json()["risk_weight"] == 0.2

    async def test_action_classify_picks_highest_confidence_person(self, client, mock_triton):
        """Multi-person frames must feed ST-GCN++ the *best* detection.

        Anchor order is not confidence order: a low-confidence person at an
        early anchor must lose to a high-confidence person at a later anchor
        (mirror of enrichment_light's argmax convention).
        """
        seen: dict[str, np.ndarray] = {}

        def _two_person_output() -> np.ndarray:
            out = np.zeros((1, 56, 8400), dtype=np.float32)
            # Person A: early anchor, low conf, keypoints near (10, 20).
            out[0, 4, 100] = 0.30
            # Person B: later anchor, high conf, keypoints near (500, 600).
            out[0, 4, 5000] = 0.95
            for i in range(17):
                out[0, 5 + i * 3, 100] = 10.0 + i  # A x
                out[0, 6 + i * 3, 100] = 20.0 + i  # A y
                out[0, 7 + i * 3, 100] = 0.5  # A visibility
                out[0, 5 + i * 3, 5000] = 500.0 + i  # B x
                out[0, 6 + i * 3, 5000] = 600.0 + i  # B y
                out[0, 7 + i * 3, 5000] = 0.9  # B visibility
            return out

        async def _infer(*, model_name, inputs, outputs, timeout=None):
            if model_name == "pose":
                return {"output0": _two_person_output()}
            seen["input"] = inputs["input"]
            return {"output": _make_stgcn_logits(action_idx=7)}

        mock_triton.infer.side_effect = _infer

        response = await client.post("/action-classify", json={"frames": [_make_b64_image()] * 2})
        assert response.status_code == 200

        tensor = seen["input"]
        xs = tensor[0, 0, :, :, 0]  # resampled track x-coords
        ys = tensor[0, 0, :, :, 1]
        # Person B coords (~500/600), not person A (~10/20): resampling only
        # interpolates between frames, so every sample stays in B's range.
        nonzero = xs > 0
        assert nonzero.any()
        assert xs[nonzero].min() > 400.0
        assert ys[nonzero].min() > 500.0

    async def test_action_classify_no_people_returns_unknown(self, client, mock_triton):
        """Frames with no detections skip stgcn_action and report 'unknown'."""

        async def _infer(*, model_name, inputs, outputs, timeout=None):
            assert model_name == "pose"  # skeleton never sent: zero tracks
            return {"output0": _make_pose_output(confidence=0.0)}

        mock_triton.infer.side_effect = _infer

        response = await client.post(
            "/action-classify",
            json={"frames": [_make_b64_image(), _make_b64_image()], "top_k": 5},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["action"] == "unknown"
        assert data["confidence"] == 0.0
        assert data["is_suspicious"] is False

    async def test_action_classify_empty_frames(self, client, mock_triton):
        """Empty frames list returns 400."""
        response = await client.post(
            "/action-classify",
            json={"frames": [], "top_k": 5},
        )
        assert response.status_code == 400

    async def test_action_classify_pose_down_returns_503(self, client, mock_triton):
        """Pose failure on every frame is a serving outage, not 'no person'."""
        mock_triton.infer.side_effect = TritonClientError("Pose model unavailable")

        response = await client.post(
            "/action-classify",
            json={"frames": [_make_b64_image()], "top_k": 5},
        )

        assert response.status_code == 503

    async def test_action_classify_undecodable_frames_return_400(self, client, mock_triton):
        """Frames that are not images at all are a client error (400)."""
        response = await client.post(
            "/action-classify",
            json={"frames": ["bm90LWFuLWltYWdl", "bm90LWFuLWltYWdl"], "top_k": 5},
        )

        assert response.status_code == 400

    async def test_action_classify_stgcn_error_returns_503(self, client, mock_triton):
        """ST-GCN++ failure after a good track returns 503."""

        async def _infer(*, model_name, inputs, outputs, timeout=None):
            if model_name == "pose":
                return {"output0": _make_pose_output(confidence=0.9)}
            raise TritonClientError("stgcn_action unavailable")

        mock_triton.infer.side_effect = _infer

        response = await client.post(
            "/action-classify",
            json={"frames": [_make_b64_image()], "top_k": 5},
        )
        assert response.status_code == 503


# =============================================================================
# /pet-classify endpoint tests
# =============================================================================


class TestPetClassifyEndpoint:
    """Tests for the POST /pet-classify endpoint."""

    async def test_pet_classify_cat(self, client, mock_triton):
        """Cat detection returns correct pet_type."""
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

    async def test_pet_classify_dog(self, client, mock_triton):
        """Dog detection returns correct pet_type."""
        mock_triton.infer.return_value = {
            "output": np.array([_make_pet_logits(cat_score=1.0, dog_score=5.0)])
        }

        response = await client.post(
            "/pet-classify",
            json={"image": _make_b64_image()},
        )

        assert response.status_code == 200
        assert response.json()["pet_type"] == "dog"

    async def test_pet_classify_triton_error(self, client, mock_triton):
        """Triton failure returns 503."""
        mock_triton.infer.side_effect = TritonClientError("Error")

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
        """Depth estimation returns depth stats and base64 map."""
        depth_map = np.random.rand(1, 518, 518).astype(np.float32) * 10.0
        mock_triton.infer.return_value = {"depth_map": depth_map}

        response = await client.post(
            "/depth-estimate",
            json={"image": _make_b64_image()},
        )

        assert response.status_code == 200
        data = response.json()
        assert "depth_map_base64" in data
        assert data["min_depth"] < data["max_depth"]
        assert data["min_depth"] <= data["mean_depth"] <= data["max_depth"]
        # Verify base64 is valid
        decoded = base64.b64decode(data["depth_map_base64"])
        assert len(decoded) > 0

    async def test_depth_estimate_flat_depth(self, client, mock_triton):
        """Constant depth map produces equal min/max/mean."""
        depth_map = np.full((1, 518, 518), 5.0, dtype=np.float32)
        mock_triton.infer.return_value = {"depth_map": depth_map}

        response = await client.post(
            "/depth-estimate",
            json={"image": _make_b64_image()},
        )

        data = response.json()
        assert data["min_depth"] == data["max_depth"] == data["mean_depth"]

    async def test_depth_estimate_triton_error(self, client, mock_triton):
        """Triton failure returns 503."""
        mock_triton.infer.side_effect = TritonClientError("GPU OOM")

        response = await client.post(
            "/depth-estimate",
            json={"image": _make_b64_image()},
        )
        assert response.status_code == 503


# =============================================================================
# /pose-analyze endpoint tests
# =============================================================================


class TestPoseAnalyzeEndpoint:
    """Tests for the POST /pose-analyze endpoint."""

    async def test_pose_analyze_success(self, client, mock_triton):
        """Pose analysis returns keypoints."""
        # Create a mock YOLOv8-pose output: (1, 56, 8400) with one detection
        output = np.zeros((1, 56, 8400), dtype=np.float32)
        # Set one detection with confidence > 0.25
        output[0, 0, 0] = 320.0  # cx
        output[0, 1, 0] = 320.0  # cy
        output[0, 2, 0] = 100.0  # w
        output[0, 3, 0] = 200.0  # h
        output[0, 4, 0] = 0.9  # confidence
        # Set some keypoint data (17 keypoints x 3 values)
        for i in range(17):
            output[0, 5 + i * 3, 0] = 300.0 + i  # x
            output[0, 6 + i * 3, 0] = 200.0 + i  # y
            output[0, 7 + i * 3, 0] = 0.8  # visibility
        mock_triton.infer.return_value = {"output0": output}

        response = await client.post(
            "/pose-analyze",
            json={"image": _make_b64_image()},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["num_people"] == 1
        assert len(data["keypoints"]) == 1

    async def test_pose_analyze_no_people(self, client, mock_triton):
        """No people returns empty keypoints."""
        # All-zeros output means no detections above threshold
        output = np.zeros((1, 56, 8400), dtype=np.float32)
        mock_triton.infer.return_value = {"output0": output}

        response = await client.post(
            "/pose-analyze",
            json={"image": _make_b64_image()},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["num_people"] == 0
        assert data["keypoints"] == []

    async def test_pose_analyze_triton_error(self, client, mock_triton):
        """Triton failure returns 503."""
        mock_triton.infer.side_effect = TritonClientError("Backend crash")

        response = await client.post(
            "/pose-analyze",
            json={"image": _make_b64_image()},
        )
        assert response.status_code == 503


# =============================================================================
# /enrich endpoint tests
# =============================================================================


class TestEnrichEndpoint:
    """Tests for the POST /enrich unified endpoint."""

    async def test_enrich_person(self, client, mock_triton):
        """Person enrichment fans out to clothing + demographics."""
        # clothing model returns 768-dim embedding (fashion_clip uses pixel_values/embedding)
        clothing_emb = np.random.randn(1, 768).astype(np.float32)
        # demographics returns age and gender logits
        age_logits, gender_logits = _make_demographics_logits()

        mock_triton.infer.side_effect = [
            {"embedding": clothing_emb},  # fashion_clip
            {"output": np.array([age_logits])},  # demographics_age
            {"output": np.array([gender_logits])},  # demographics_gender
        ]

        # Patch the clothing zero-shot text-encoder seam like the sibling
        # tests in this file (275/311) do (WP6.4): unpatched, _infer_clothing
        # loads FashionSigLIP weights from huggingface.co mid-test, blows the
        # 5s marker timeout, and pytest-timeout's Failed — an
        # OutcomeException, i.e. a BaseException, NOT an Exception — slips
        # past enrich()'s isinstance(results[i], Exception) guards into the
        # response body, surfacing as
        # PydanticSerializationError: Unable to serialize unknown type:
        # <class 'Failed'>. The real bug the red was hiding is the missing
        # mock (network + slow in a unit test), not the endpoint.
        with patch(
            "ai.gateway.adapters.enrichment._ensure_clothing_text_embeddings",
            return_value=None,
        ):
            response = await client.post(
                "/enrich",
                json={"image": _make_b64_image(), "detection_type": "person"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["detection_type"] == "person"
        assert "enrichments" in data
        # Should have clothing and demographics sub-results
        enrichments = data["enrichments"]
        assert "clothing" in enrichments or "demographics" in enrichments

    async def test_enrich_vehicle(self, client, mock_triton):
        """Vehicle enrichment runs vehicle classification."""
        mock_triton.infer.return_value = {"output": np.array([_make_vehicle_logits()])}

        response = await client.post(
            "/enrich",
            json={"image": _make_b64_image(), "detection_type": "vehicle"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["detection_type"] == "vehicle"
        assert "vehicle" in data["enrichments"]
        assert data["enrichments"]["vehicle"]["vehicle_type"] == "car"

    async def test_enrich_cat(self, client, mock_triton):
        """Cat enrichment runs pet classification."""
        mock_triton.infer.return_value = {
            "output": np.array([_make_pet_logits(cat_score=5.0, dog_score=1.0)])
        }

        response = await client.post(
            "/enrich",
            json={"image": _make_b64_image(), "detection_type": "cat"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "pet" in data["enrichments"]
        assert data["enrichments"]["pet"]["pet_type"] == "cat"

    async def test_enrich_unknown_type(self, client, mock_triton):
        """Unknown detection type returns empty enrichments."""
        response = await client.post(
            "/enrich",
            json={"image": _make_b64_image(), "detection_type": "unknown_object"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["detection_type"] == "unknown_object"
        assert data["enrichments"] == {}

    async def test_enrich_triton_error(self, client, mock_triton):
        """Triton error returns 503."""
        mock_triton.infer.side_effect = TritonClientError("GPU unavailable")

        response = await client.post(
            "/enrich",
            json={"image": _make_b64_image(), "detection_type": "vehicle"},
        )
        assert response.status_code == 503

    async def test_enrich_invalid_image(self, client, mock_triton):
        """Invalid image returns 400."""
        response = await client.post(
            "/enrich",
            json={"image": "bad-data!@#", "detection_type": "vehicle"},
        )
        assert response.status_code == 400


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
        assert all(v is True for v in data["models"].values())

    async def test_health_some_degraded(self, client, mock_triton):
        """Returns degraded when some models are not ready."""

        # Make is_model_ready return True for some, False for others
        async def model_ready(name):
            return name != "depth"

        mock_triton.is_model_ready.side_effect = model_ready

        response = await client.get("/health")

        data = response.json()
        assert data["status"] == "degraded"
        assert data["models"]["depth"] is False

    async def test_health_all_down(self, client, mock_triton):
        """Returns degraded when all models are down."""
        mock_triton.is_model_ready.return_value = False

        response = await client.get("/health")

        data = response.json()
        assert data["status"] == "degraded"
        assert all(v is False for v in data["models"].values())
