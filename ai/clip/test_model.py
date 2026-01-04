"""Unit tests for CLIP Embedding Server.

Tests cover:
- BatchSimilarityRequest batch size validation (NEM-1101)
- Division by zero protection in anomaly score calculation (NEM-1100)
- Request model validation
- API endpoint behavior
"""

import base64
import io
import math
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import torch
from fastapi.testclient import TestClient
from PIL import Image

# Add the ai/clip directory to sys.path to enable imports
_clip_dir = Path(__file__).parent
if str(_clip_dir) not in sys.path:
    sys.path.insert(0, str(_clip_dir))

# Now import from the local model module
import model as model_module  # noqa: E402
from model import (  # noqa: E402
    EMBEDDING_DIMENSION,
    MAX_BATCH_TEXTS_SIZE,
    BatchSimilarityRequest,
    CLIPEmbeddingModel,
    app,
)

MODEL_MODULE_PATH = "model"


@pytest.fixture
def dummy_image():
    """Create a dummy PIL image for testing."""
    return Image.new("RGB", (100, 100), color="red")


@pytest.fixture
def dummy_image_bytes(dummy_image):
    """Create dummy image bytes for testing."""
    img_bytes = io.BytesIO()
    dummy_image.save(img_bytes, format="JPEG")
    img_bytes.seek(0)
    return img_bytes.getvalue()


@pytest.fixture
def dummy_image_base64(dummy_image_bytes):
    """Create base64-encoded dummy image for testing."""
    return base64.b64encode(dummy_image_bytes).decode("utf-8")


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


class TestBatchSimilarityRequestValidation:
    """Tests for BatchSimilarityRequest batch size validation (NEM-1101).

    Security requirement: Prevent resource exhaustion through oversized batch requests.
    """

    def test_max_batch_texts_size_constant_is_reasonable(self):
        """Test that MAX_BATCH_TEXTS_SIZE is set to a reasonable limit."""
        # Should be a positive integer with sensible default (100 or 1000)
        assert MAX_BATCH_TEXTS_SIZE > 0
        assert MAX_BATCH_TEXTS_SIZE <= 1000
        assert isinstance(MAX_BATCH_TEXTS_SIZE, int)

    def test_batch_similarity_request_accepts_valid_batch_size(self, dummy_image_base64):
        """Test that BatchSimilarityRequest accepts requests within the limit."""
        # Create a request with a reasonable number of texts
        texts = ["text " + str(i) for i in range(10)]
        request = BatchSimilarityRequest(image=dummy_image_base64, texts=texts)

        assert len(request.texts) == 10

    def test_batch_similarity_request_accepts_at_limit(self, dummy_image_base64):
        """Test that BatchSimilarityRequest accepts exactly MAX_BATCH_TEXTS_SIZE texts."""
        texts = ["text " + str(i) for i in range(MAX_BATCH_TEXTS_SIZE)]
        request = BatchSimilarityRequest(image=dummy_image_base64, texts=texts)

        assert len(request.texts) == MAX_BATCH_TEXTS_SIZE

    def test_batch_similarity_request_rejects_over_limit(self, dummy_image_base64):
        """Test that BatchSimilarityRequest rejects requests exceeding the limit."""
        # Create a request with too many texts
        texts = ["text " + str(i) for i in range(MAX_BATCH_TEXTS_SIZE + 1)]

        with pytest.raises(ValueError) as exc_info:
            BatchSimilarityRequest(image=dummy_image_base64, texts=texts)

        # Error message should mention the limit
        error_message = str(exc_info.value).lower()
        assert (
            "batch size" in error_message or "texts" in error_message or "maximum" in error_message
        )

    def test_batch_similarity_request_rejects_extremely_large_batch(self, dummy_image_base64):
        """Test that extremely large batches are rejected to prevent DoS."""
        # Attempt to create a request with 10,000 texts (way over any reasonable limit)
        texts = ["text " + str(i) for i in range(10000)]

        with pytest.raises(ValueError):
            BatchSimilarityRequest(image=dummy_image_base64, texts=texts)


class TestBatchSimilarityEndpointValidation:
    """Tests for /batch-similarity endpoint batch size validation."""

    @pytest.fixture(autouse=True)
    def mock_model(self):
        """Mock the global model instance."""
        mock_instance = MagicMock()
        mock_instance.model = MagicMock()
        mock_instance.compute_batch_similarity.return_value = ({"text": 0.5}, 10.0)
        original_model = getattr(model_module, "model", None)
        model_module.model = mock_instance
        yield mock_instance
        model_module.model = original_model

    def test_endpoint_rejects_oversized_batch_with_422(self, client, dummy_image_base64):
        """Test that /batch-similarity rejects oversized batches with 422 status."""
        texts = ["text " + str(i) for i in range(MAX_BATCH_TEXTS_SIZE + 1)]

        response = client.post(
            "/batch-similarity",
            json={"image": dummy_image_base64, "texts": texts},
        )

        # Should be rejected by Pydantic validation with 422
        assert response.status_code == 422
        error_detail = response.json()
        assert "detail" in error_detail

    def test_endpoint_accepts_valid_batch(self, client, dummy_image_base64):
        """Test that /batch-similarity accepts valid batch sizes."""
        texts = ["cat", "dog", "bird"]

        response = client.post(
            "/batch-similarity",
            json={"image": dummy_image_base64, "texts": texts},
        )

        assert response.status_code == 200
        data = response.json()
        assert "similarities" in data
        assert "inference_time_ms" in data

    def test_endpoint_accepts_at_limit(self, client, dummy_image_base64, mock_model):
        """Test that /batch-similarity accepts exactly MAX_BATCH_TEXTS_SIZE texts."""
        texts = ["text " + str(i) for i in range(MAX_BATCH_TEXTS_SIZE)]

        # Mock should return similarities for all texts
        mock_model.compute_batch_similarity.return_value = (
            dict.fromkeys(texts, 0.5),
            100.0,
        )

        response = client.post(
            "/batch-similarity",
            json={"image": dummy_image_base64, "texts": texts},
        )

        assert response.status_code == 200


class TestBatchSizeErrorMessages:
    """Tests for helpful error messages when batch size is exceeded."""

    def test_error_message_includes_limit(self, dummy_image_base64):
        """Test that error message includes the maximum allowed batch size."""
        texts = ["text " + str(i) for i in range(MAX_BATCH_TEXTS_SIZE + 1)]

        with pytest.raises(ValueError) as exc_info:
            BatchSimilarityRequest(image=dummy_image_base64, texts=texts)

        error_message = str(exc_info.value)
        # Error should mention the limit value
        assert str(MAX_BATCH_TEXTS_SIZE) in error_message

    def test_error_message_includes_actual_size(self, dummy_image_base64):
        """Test that error message includes the actual batch size provided."""
        actual_size = MAX_BATCH_TEXTS_SIZE + 50
        texts = ["text " + str(i) for i in range(actual_size)]

        with pytest.raises(ValueError) as exc_info:
            BatchSimilarityRequest(image=dummy_image_base64, texts=texts)

        error_message = str(exc_info.value)
        # Error should mention the actual size provided
        assert str(actual_size) in error_message


class TestAnomalyScoreDivisionByZero:
    """Tests for division by zero protection in anomaly score calculation (NEM-1100).

    The compute_anomaly_score method normalizes embeddings by dividing by their L2 norm.
    If the norm is zero (zero vector), this causes division by zero, resulting in NaN values.

    These tests verify that epsilon protection prevents this issue.
    """

    @pytest.fixture
    def zero_embedding(self) -> list[float]:
        """Create a zero embedding that would cause division by zero."""
        return [0.0] * EMBEDDING_DIMENSION

    @pytest.fixture
    def near_zero_embedding(self) -> list[float]:
        """Create a near-zero embedding with very small values."""
        return [1e-40] * EMBEDDING_DIMENSION

    @pytest.fixture
    def valid_embedding(self) -> list[float]:
        """Create a valid normalized embedding."""
        values = [1.0 / (EMBEDDING_DIMENSION**0.5)] * EMBEDDING_DIMENSION
        return values

    def test_zero_baseline_embedding_without_epsilon_produces_nan(
        self, zero_embedding: list[float]
    ) -> None:
        """Demonstrate that zero baseline embedding causes NaN without epsilon.

        This test proves the bug exists by showing that dividing a zero vector
        by its norm (which is zero) produces NaN values.

        RED phase: This test documents the bug behavior.
        """
        baseline_tensor = torch.tensor(zero_embedding, dtype=torch.float32)

        # The norm of a zero vector is 0
        norm = baseline_tensor.norm(p=2)
        assert norm.item() == 0.0, "Zero embedding should have zero norm"

        # Division by zero produces NaN
        result_without_epsilon = baseline_tensor / norm

        # Verify NaN is produced (this is the bug we're fixing)
        assert torch.isnan(result_without_epsilon).all(), "Division by zero norm should produce NaN"

    def test_zero_baseline_embedding_with_epsilon_is_finite(
        self, zero_embedding: list[float]
    ) -> None:
        """Test that epsilon protection prevents NaN for zero baseline.

        GREEN phase: This test verifies the fix works.
        """
        baseline_tensor = torch.tensor(zero_embedding, dtype=torch.float32)
        epsilon = 1e-8

        # With epsilon protection, division should not produce NaN
        result_with_epsilon = baseline_tensor / (baseline_tensor.norm(p=2) + epsilon)

        # Result should be finite (not NaN or Inf)
        assert torch.isfinite(result_with_epsilon).all(), (
            "Normalized baseline with epsilon should be finite"
        )

    def test_zero_current_embedding_with_epsilon_is_finite(self) -> None:
        """Test that epsilon protection prevents NaN for zero current embedding."""
        current_tensor = torch.tensor([0.0] * EMBEDDING_DIMENSION, dtype=torch.float32)
        epsilon = 1e-8

        result_with_epsilon = current_tensor / (current_tensor.norm(p=2) + epsilon)

        assert torch.isfinite(result_with_epsilon).all(), (
            "Normalized current with epsilon should be finite"
        )

    def test_both_zero_embeddings_with_epsilon_produces_finite_similarity(self) -> None:
        """Test that both zero embeddings with epsilon produce finite similarity."""
        current_tensor = torch.tensor([0.0] * EMBEDDING_DIMENSION, dtype=torch.float32)
        baseline_tensor = torch.tensor([0.0] * EMBEDDING_DIMENSION, dtype=torch.float32)
        epsilon = 1e-8

        current_norm = current_tensor / (current_tensor.norm(p=2) + epsilon)
        baseline_norm = baseline_tensor / (baseline_tensor.norm(p=2) + epsilon)

        # Both should be finite
        assert torch.isfinite(current_norm).all(), "Current should be finite"
        assert torch.isfinite(baseline_norm).all(), "Baseline should be finite"

        # Cosine similarity should also be finite
        similarity = torch.dot(current_norm, baseline_norm)
        assert torch.isfinite(similarity), "Similarity should be finite"

    def test_near_zero_embedding_with_epsilon_is_finite(
        self, near_zero_embedding: list[float]
    ) -> None:
        """Test that near-zero embeddings with epsilon produce finite results."""
        tensor = torch.tensor(near_zero_embedding, dtype=torch.float32)
        epsilon = 1e-8

        result_with_epsilon = tensor / (tensor.norm(p=2) + epsilon)

        assert torch.isfinite(result_with_epsilon).all(), (
            "Near-zero embedding with epsilon should be finite"
        )


class TestComputeAnomalyScoreIntegration:
    """Integration tests for compute_anomaly_score method (NEM-1100).

    These tests verify the compute_anomaly_score method handles edge cases correctly.
    """

    @pytest.fixture
    def mock_clip_model(self):
        """Create a mock CLIP model for testing without loading weights."""
        with patch.object(CLIPEmbeddingModel, "extract_embedding") as mock_extract:
            # Return a valid embedding by default
            mock_extract.return_value = (
                [0.1] * EMBEDDING_DIMENSION,
                10.0,  # inference_time_ms
            )
            model = CLIPEmbeddingModel(model_path="/fake/path", device="cpu")
            yield model, mock_extract

    def test_compute_anomaly_score_with_zero_baseline_returns_finite(self, mock_clip_model) -> None:
        """Test that compute_anomaly_score handles zero baseline embedding.

        This is the main regression test for NEM-1100.
        """
        model, _mock_extract = mock_clip_model

        # Create a test image
        test_image = Image.new("RGB", (224, 224), color="red")

        # Zero baseline embedding
        zero_baseline = [0.0] * EMBEDDING_DIMENSION

        # Call compute_anomaly_score
        anomaly_score, similarity, _inference_time = model.compute_anomaly_score(
            test_image, zero_baseline
        )

        # Results should be finite numbers
        assert isinstance(anomaly_score, float), "Anomaly score should be float"
        assert isinstance(similarity, float), "Similarity should be float"
        assert not math.isnan(anomaly_score), "Anomaly score should not be NaN"
        assert not math.isnan(similarity), "Similarity should not be NaN"

    def test_compute_anomaly_score_with_zero_current_returns_finite(self, mock_clip_model) -> None:
        """Test that compute_anomaly_score handles zero current embedding."""
        model, mock_extract = mock_clip_model

        # Make extract_embedding return zero embedding
        mock_extract.return_value = ([0.0] * EMBEDDING_DIMENSION, 10.0)

        test_image = Image.new("RGB", (224, 224), color="red")
        valid_baseline = [0.1] * EMBEDDING_DIMENSION

        anomaly_score, similarity, _inference_time = model.compute_anomaly_score(
            test_image, valid_baseline
        )

        # Results should be finite
        assert not math.isnan(anomaly_score), "Anomaly score should not be NaN"
        assert not math.isnan(similarity), "Similarity should not be NaN"

    def test_compute_anomaly_score_with_both_zero_returns_finite(self, mock_clip_model) -> None:
        """Test that compute_anomaly_score handles both zero embeddings."""
        model, mock_extract = mock_clip_model

        # Make extract_embedding return zero embedding
        mock_extract.return_value = ([0.0] * EMBEDDING_DIMENSION, 10.0)

        test_image = Image.new("RGB", (224, 224), color="red")
        zero_baseline = [0.0] * EMBEDDING_DIMENSION

        anomaly_score, similarity, _inference_time = model.compute_anomaly_score(
            test_image, zero_baseline
        )

        # Results should be finite
        assert not math.isnan(anomaly_score), "Anomaly score should not be NaN"
        assert not math.isnan(similarity), "Similarity should not be NaN"

    def test_compute_anomaly_score_bounds(self, mock_clip_model) -> None:
        """Test that anomaly score is always in [0, 1] range."""
        model, _mock_extract = mock_clip_model

        test_image = Image.new("RGB", (224, 224), color="red")

        # Test with various baseline embeddings
        test_cases = [
            [0.0] * EMBEDDING_DIMENSION,  # Zero vector
            [0.1] * EMBEDDING_DIMENSION,  # Uniform positive
            [-0.1] * EMBEDDING_DIMENSION,  # Uniform negative
            [1e-40] * EMBEDDING_DIMENSION,  # Near-zero
        ]

        for baseline in test_cases:
            anomaly_score, _similarity, _ = model.compute_anomaly_score(test_image, baseline)

            assert 0.0 <= anomaly_score <= 1.0, f"Anomaly score {anomaly_score} should be in [0, 1]"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
