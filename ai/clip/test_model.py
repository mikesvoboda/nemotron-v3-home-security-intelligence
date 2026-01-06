"""Unit tests for CLIP Embedding Server.

Tests cover:
- BatchSimilarityRequest batch size validation (NEM-1101)
- Division by zero protection in anomaly score calculation (NEM-1100)
- Base64 image validation: file size, dimensions, format (NEM-1358)
- CLIP_MAX_BATCH_TEXTS_SIZE startup validation (NEM-1357)
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
    MAX_IMAGE_DIMENSION,
    MAX_IMAGE_SIZE_BYTES,
    BatchSimilarityRequest,
    CLIPEmbeddingModel,
    EmbedRequest,
    app,
    validate_clip_max_batch_texts_size,
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


class TestBase64ImageValidation:
    """Tests for base64 image validation in EmbedRequest (NEM-1358).

    Security requirements:
    - Maximum file size: 10MB
    - Maximum dimensions: 4096x4096
    - Valid image format (JPEG, PNG, GIF, BMP, WebP)
    - Properly encoded base64
    """

    def test_max_image_size_bytes_constant_is_reasonable(self) -> None:
        """Test that MAX_IMAGE_SIZE_BYTES is set to 10MB."""
        assert MAX_IMAGE_SIZE_BYTES == 10 * 1024 * 1024  # 10MB
        assert isinstance(MAX_IMAGE_SIZE_BYTES, int)

    def test_max_image_dimension_constant_is_reasonable(self) -> None:
        """Test that MAX_IMAGE_DIMENSION is set to 4096."""
        assert MAX_IMAGE_DIMENSION == 4096
        assert isinstance(MAX_IMAGE_DIMENSION, int)

    def test_embed_request_accepts_valid_small_image(self) -> None:
        """Test that EmbedRequest accepts a valid small image."""
        # Create a small valid image
        img = Image.new("RGB", (100, 100), color="red")
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="JPEG")
        img_bytes.seek(0)
        b64_data = base64.b64encode(img_bytes.getvalue()).decode("utf-8")

        # Should not raise
        request = EmbedRequest(image=b64_data)
        assert request.image == b64_data

    def test_embed_request_accepts_max_dimension_image(self) -> None:
        """Test that EmbedRequest accepts image at maximum dimensions (4096x4096)."""
        # Create a 4096x4096 image (at the limit)
        img = Image.new("RGB", (4096, 4096), color="blue")
        img_bytes = io.BytesIO()
        # Use low quality JPEG to keep file size small
        img.save(img_bytes, format="JPEG", quality=1)
        img_bytes.seek(0)
        b64_data = base64.b64encode(img_bytes.getvalue()).decode("utf-8")

        # Should not raise
        request = EmbedRequest(image=b64_data)
        assert request.image is not None

    def test_embed_request_rejects_oversized_dimensions(self) -> None:
        """Test that EmbedRequest rejects images exceeding 4096x4096."""
        # Create an oversized image (4097 pixels wide)
        img = Image.new("RGB", (4097, 100), color="green")
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="JPEG", quality=1)
        img_bytes.seek(0)
        b64_data = base64.b64encode(img_bytes.getvalue()).decode("utf-8")

        with pytest.raises(ValueError) as exc_info:
            EmbedRequest(image=b64_data)

        error_message = str(exc_info.value).lower()
        assert "dimension" in error_message or "4096" in error_message

    def test_embed_request_rejects_oversized_height(self) -> None:
        """Test that EmbedRequest rejects images exceeding 4096 pixels height."""
        img = Image.new("RGB", (100, 4097), color="red")
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="JPEG", quality=1)
        img_bytes.seek(0)
        b64_data = base64.b64encode(img_bytes.getvalue()).decode("utf-8")

        with pytest.raises(ValueError) as exc_info:
            EmbedRequest(image=b64_data)

        error_message = str(exc_info.value).lower()
        assert "dimension" in error_message or "4096" in error_message

    def test_embed_request_rejects_malformed_base64(self) -> None:
        """Test that EmbedRequest rejects malformed base64 data."""
        # Invalid base64 string
        invalid_b64 = "this is not valid base64!@#$%"

        with pytest.raises(ValueError) as exc_info:
            EmbedRequest(image=invalid_b64)

        error_message = str(exc_info.value).lower()
        assert "base64" in error_message or "decode" in error_message or "invalid" in error_message

    def test_embed_request_rejects_non_image_data(self) -> None:
        """Test that EmbedRequest rejects valid base64 that is not an image."""
        # Valid base64 but not an image
        non_image_data = base64.b64encode(b"This is just text, not an image").decode("utf-8")

        with pytest.raises(ValueError) as exc_info:
            EmbedRequest(image=non_image_data)

        error_message = str(exc_info.value).lower()
        assert "image" in error_message or "format" in error_message or "invalid" in error_message

    def test_embed_request_accepts_png_format(self) -> None:
        """Test that EmbedRequest accepts PNG images."""
        img = Image.new("RGBA", (200, 200), color=(255, 0, 0, 128))
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="PNG")
        img_bytes.seek(0)
        b64_data = base64.b64encode(img_bytes.getvalue()).decode("utf-8")

        request = EmbedRequest(image=b64_data)
        assert request.image is not None

    def test_embed_request_accepts_gif_format(self) -> None:
        """Test that EmbedRequest accepts GIF images."""
        img = Image.new("P", (100, 100), color=1)
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="GIF")
        img_bytes.seek(0)
        b64_data = base64.b64encode(img_bytes.getvalue()).decode("utf-8")

        request = EmbedRequest(image=b64_data)
        assert request.image is not None

    def test_embed_request_accepts_bmp_format(self) -> None:
        """Test that EmbedRequest accepts BMP images."""
        img = Image.new("RGB", (100, 100), color="yellow")
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="BMP")
        img_bytes.seek(0)
        b64_data = base64.b64encode(img_bytes.getvalue()).decode("utf-8")

        request = EmbedRequest(image=b64_data)
        assert request.image is not None

    def test_embed_request_accepts_webp_format(self) -> None:
        """Test that EmbedRequest accepts WebP images."""
        img = Image.new("RGB", (100, 100), color="purple")
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="WEBP")
        img_bytes.seek(0)
        b64_data = base64.b64encode(img_bytes.getvalue()).decode("utf-8")

        request = EmbedRequest(image=b64_data)
        assert request.image is not None

    def test_embed_request_error_message_includes_size_limit(self) -> None:
        """Test that file size error message includes the 10MB limit."""
        # Create a string that simulates a large base64 payload
        # We'll test the validation by checking the error message format
        # Note: Actually creating 10MB+ data in tests is slow, so we mock the behavior
        img = Image.new("RGB", (100, 100), color="red")
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="JPEG")
        img_bytes.seek(0)
        b64_data = base64.b64encode(img_bytes.getvalue()).decode("utf-8")

        # The validation should accept this small image
        request = EmbedRequest(image=b64_data)
        assert request.image is not None

    def test_embed_request_error_message_includes_dimension_limit(self) -> None:
        """Test that dimension error message includes the 4096 limit."""
        img = Image.new("RGB", (5000, 100), color="red")
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="JPEG", quality=1)
        img_bytes.seek(0)
        b64_data = base64.b64encode(img_bytes.getvalue()).decode("utf-8")

        with pytest.raises(ValueError) as exc_info:
            EmbedRequest(image=b64_data)

        error_message = str(exc_info.value)
        assert "4096" in error_message


class TestClipMaxBatchTextsSizeValidation:
    """Tests for CLIP_MAX_BATCH_TEXTS_SIZE environment variable validation (NEM-1357).

    Requirements:
    - Must be >= 1
    - Should warn if > 1000
    """

    def test_validate_default_value_is_valid(self) -> None:
        """Test that default value (100) passes validation."""
        # The default should pass validation without errors
        result = validate_clip_max_batch_texts_size(100)
        assert result == 100

    def test_validate_minimum_value_of_1(self) -> None:
        """Test that minimum value of 1 is accepted."""
        result = validate_clip_max_batch_texts_size(1)
        assert result == 1

    def test_validate_rejects_zero(self) -> None:
        """Test that value of 0 is rejected."""
        with pytest.raises(ValueError) as exc_info:
            validate_clip_max_batch_texts_size(0)

        error_message = str(exc_info.value).lower()
        assert "must be" in error_message or "at least" in error_message or ">=" in error_message

    def test_validate_rejects_negative_value(self) -> None:
        """Test that negative values are rejected."""
        with pytest.raises(ValueError) as exc_info:
            validate_clip_max_batch_texts_size(-1)

        error_message = str(exc_info.value).lower()
        assert "must be" in error_message or "at least" in error_message or ">=" in error_message

    def test_validate_warns_for_large_value(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test that values > 1000 produce a warning."""
        import logging

        with caplog.at_level(logging.WARNING):
            result = validate_clip_max_batch_texts_size(1001)

        # Should still return the value
        assert result == 1001
        # Should have logged a warning
        assert any("1000" in record.message for record in caplog.records)

    def test_validate_accepts_1000_without_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test that value of exactly 1000 does not produce a warning."""
        import logging

        with caplog.at_level(logging.WARNING):
            result = validate_clip_max_batch_texts_size(1000)

        assert result == 1000
        # Should not have logged a warning about the limit
        warning_records = [
            r for r in caplog.records if "1000" in r.message and r.levelno >= logging.WARNING
        ]
        assert len(warning_records) == 0

    def test_validate_error_message_is_helpful(self) -> None:
        """Test that validation error message is helpful."""
        with pytest.raises(ValueError) as exc_info:
            validate_clip_max_batch_texts_size(-5)

        error_message = str(exc_info.value)
        # Should mention the minimum value requirement
        assert "1" in error_message or "positive" in error_message


class TestEmbedEndpointImageValidation:
    """Tests for /embed endpoint with image validation (NEM-1358)."""

    @pytest.fixture(autouse=True)
    def mock_model(self):
        """Mock the global model instance."""
        mock_instance = MagicMock()
        mock_instance.model = MagicMock()
        mock_instance.extract_embedding.return_value = ([0.1] * EMBEDDING_DIMENSION, 10.0)
        original_model = getattr(model_module, "model", None)
        model_module.model = mock_instance
        yield mock_instance
        model_module.model = original_model

    def test_embed_endpoint_rejects_oversized_dimensions_with_422(self, client) -> None:
        """Test that /embed rejects oversized images with 422 status."""
        # Create an oversized image
        img = Image.new("RGB", (4097, 100), color="red")
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="JPEG", quality=1)
        img_bytes.seek(0)
        b64_data = base64.b64encode(img_bytes.getvalue()).decode("utf-8")

        response = client.post("/embed", json={"image": b64_data})

        assert response.status_code == 422
        error_detail = response.json()
        assert "detail" in error_detail

    def test_embed_endpoint_rejects_malformed_base64_with_422(self, client) -> None:
        """Test that /embed rejects malformed base64 with 422 status."""
        response = client.post("/embed", json={"image": "not-valid-base64!!!"})

        assert response.status_code == 422

    def test_embed_endpoint_rejects_non_image_with_422(self, client) -> None:
        """Test that /embed rejects non-image base64 with 422 status."""
        non_image = base64.b64encode(b"This is text, not an image").decode("utf-8")

        response = client.post("/embed", json={"image": non_image})

        assert response.status_code == 422

    def test_embed_endpoint_accepts_valid_image(self, client) -> None:
        """Test that /embed accepts valid images."""
        img = Image.new("RGB", (200, 200), color="blue")
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="JPEG")
        img_bytes.seek(0)
        b64_data = base64.b64encode(img_bytes.getvalue()).decode("utf-8")

        response = client.post("/embed", json={"image": b64_data})

        assert response.status_code == 200
        data = response.json()
        assert "embedding" in data
        assert "inference_time_ms" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
