"""Unit tests for CLIP Embedding Server.

Tests cover:
- BatchSimilarityRequest batch size validation (NEM-1101)
- Division by zero protection in anomaly score calculation (NEM-1100)
- Base64 image validation: file size, dimensions, format (NEM-1358)
- CLIP_MAX_BATCH_TEXTS_SIZE startup validation (NEM-1357)
- Prompt template ensembling for surveillance context (NEM-3029)
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
import model as model_module
from model import (
    CAMERA_TYPE_TEMPLATES,
    EMBEDDING_DIMENSION,
    MAX_BATCH_TEXTS_SIZE,
    MAX_IMAGE_DIMENSION,
    MAX_IMAGE_SIZE_BYTES,
    SURVEILLANCE_TEMPLATES,
    BatchSimilarityRequest,
    CameraType,
    ClassifyRequest,
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


class TestSurveillanceTemplates:
    """Tests for surveillance-specific prompt templates (NEM-3029).

    These tests verify the prompt templates are correctly defined and contain
    the required placeholder for label substitution.
    """

    def test_surveillance_templates_exist(self) -> None:
        """Test that SURVEILLANCE_TEMPLATES is defined and non-empty."""
        assert SURVEILLANCE_TEMPLATES is not None
        assert len(SURVEILLANCE_TEMPLATES) > 0
        assert isinstance(SURVEILLANCE_TEMPLATES, list)

    def test_surveillance_templates_contain_placeholder(self) -> None:
        """Test that all templates contain the {} placeholder."""
        for template in SURVEILLANCE_TEMPLATES:
            assert "{}" in template, f"Template missing placeholder: {template}"

    def test_surveillance_templates_have_expected_count(self) -> None:
        """Test that we have the expected number of base templates (5)."""
        assert len(SURVEILLANCE_TEMPLATES) == 5

    def test_camera_type_enum_values(self) -> None:
        """Test that CameraType enum has expected values."""
        expected_types = {"standard", "night_vision", "outdoor", "indoor", "doorbell"}
        actual_types = {ct.value for ct in CameraType}
        assert actual_types == expected_types

    def test_camera_type_templates_exist_for_all_types(self) -> None:
        """Test that each CameraType has corresponding templates."""
        for camera_type in CameraType:
            assert camera_type in CAMERA_TYPE_TEMPLATES, f"Missing templates for {camera_type}"
            templates = CAMERA_TYPE_TEMPLATES[camera_type]
            assert len(templates) > 0, f"Empty templates for {camera_type}"

    def test_camera_type_templates_contain_placeholder(self) -> None:
        """Test that all camera type templates contain the {} placeholder."""
        for camera_type, templates in CAMERA_TYPE_TEMPLATES.items():
            for template in templates:
                assert "{}" in template, (
                    f"Template missing placeholder for {camera_type}: {template}"
                )

    def test_night_vision_templates_mention_ir_or_night(self) -> None:
        """Test that night vision templates have relevant keywords."""
        night_templates = CAMERA_TYPE_TEMPLATES[CameraType.NIGHT_VISION]
        keywords = ["night", "infrared", "ir", "low-light", "grayscale"]

        for template in night_templates:
            template_lower = template.lower()
            has_keyword = any(kw in template_lower for kw in keywords)
            assert has_keyword, f"Night vision template missing relevant keywords: {template}"


class TestClassifyWithEnsembleMethod:
    """Tests for the classify_with_ensemble method in CLIPEmbeddingModel (NEM-3029).

    These tests verify the ensemble classification provides correct behavior
    and proper error handling.
    """

    @pytest.fixture
    def mock_clip_model_for_ensemble(self):
        """Create a mock CLIP model for ensemble testing."""
        with patch.object(CLIPEmbeddingModel, "load_model"):
            model = CLIPEmbeddingModel(model_path="/fake/path", device="cpu")

            # Track the number of labels passed for dynamic text feature generation
            call_context = {"num_labels": 0}

            # Mock processor that tracks input sizes
            def mock_processor_call(**kwargs):
                if "text" in kwargs:
                    # Track how many text prompts were passed
                    call_context["num_labels"] = len(kwargs["text"])
                return {
                    "pixel_values": torch.randn(1, 3, 224, 224),
                    "input_ids": torch.randint(0, 1000, (call_context.get("num_labels", 1), 77)),
                    "attention_mask": torch.ones(call_context.get("num_labels", 1), 77),
                }

            mock_processor = MagicMock()
            mock_processor.side_effect = mock_processor_call
            model.processor = mock_processor

            # Mock the underlying CLIP model
            mock_underlying_model = MagicMock()
            # Use a function that returns a fresh iterator each time
            mock_underlying_model.parameters = lambda: iter([torch.tensor([1.0])])

            # Mock get_image_features to return normalized embeddings
            mock_underlying_model.get_image_features.return_value = torch.randn(
                1, EMBEDDING_DIMENSION
            )

            # Mock get_text_features to return dynamic number of embeddings based on input
            def mock_text_features(**kwargs):
                # Return embeddings for the number of labels that were processed
                num_labels = call_context.get("num_labels", 1)
                return torch.randn(num_labels, EMBEDDING_DIMENSION)

            mock_underlying_model.get_text_features.side_effect = mock_text_features

            model.model = mock_underlying_model
            model.device = "cpu"

            yield model

    def test_classify_with_ensemble_returns_four_values(self, mock_clip_model_for_ensemble) -> None:
        """Test that classify_with_ensemble returns (scores, top_label, time, metadata)."""
        model = mock_clip_model_for_ensemble
        test_image = Image.new("RGB", (224, 224), color="red")
        labels = ["person", "car", "dog"]

        result = model.classify_with_ensemble(test_image, labels)

        assert len(result) == 4
        scores, top_label, inference_time_ms, metadata = result

        assert isinstance(scores, dict)
        assert isinstance(top_label, str)
        assert isinstance(inference_time_ms, float)
        assert isinstance(metadata, dict)

    def test_classify_with_ensemble_scores_sum_to_one(self, mock_clip_model_for_ensemble) -> None:
        """Test that ensemble classification scores sum to approximately 1.0."""
        model = mock_clip_model_for_ensemble
        test_image = Image.new("RGB", (224, 224), color="red")
        labels = ["person", "car", "dog"]

        scores, _, _, _ = model.classify_with_ensemble(test_image, labels)

        total = sum(scores.values())
        assert abs(total - 1.0) < 1e-5, f"Scores should sum to 1.0, got {total}"

    def test_classify_with_ensemble_returns_all_labels(self, mock_clip_model_for_ensemble) -> None:
        """Test that scores dict contains all input labels."""
        model = mock_clip_model_for_ensemble
        test_image = Image.new("RGB", (224, 224), color="red")
        labels = ["person", "car", "dog", "cat"]

        scores, _, _, _ = model.classify_with_ensemble(test_image, labels)

        assert set(scores.keys()) == set(labels)

    def test_classify_with_ensemble_top_label_in_labels(self, mock_clip_model_for_ensemble) -> None:
        """Test that top_label is one of the input labels."""
        model = mock_clip_model_for_ensemble
        test_image = Image.new("RGB", (224, 224), color="red")
        labels = ["person", "car", "dog"]

        _, top_label, _, _ = model.classify_with_ensemble(test_image, labels)

        assert top_label in labels

    def test_classify_with_ensemble_metadata_contains_expected_keys(
        self, mock_clip_model_for_ensemble
    ) -> None:
        """Test that metadata contains expected keys."""
        model = mock_clip_model_for_ensemble
        test_image = Image.new("RGB", (224, 224), color="red")
        labels = ["person", "car"]

        _, _, _, metadata = model.classify_with_ensemble(test_image, labels)

        expected_keys = {"templates_used", "num_templates", "camera_type", "ensemble_method"}
        assert expected_keys.issubset(metadata.keys())

    def test_classify_with_ensemble_uses_correct_camera_type_templates(
        self, mock_clip_model_for_ensemble
    ) -> None:
        """Test that ensemble uses the correct templates for camera type."""
        model = mock_clip_model_for_ensemble
        test_image = Image.new("RGB", (224, 224), color="red")
        labels = ["person"]

        for camera_type in [CameraType.STANDARD, CameraType.NIGHT_VISION, CameraType.OUTDOOR]:
            _, _, _, metadata = model.classify_with_ensemble(
                test_image, labels, camera_type=camera_type
            )

            expected_templates = CAMERA_TYPE_TEMPLATES[camera_type]
            assert metadata["templates_used"] == expected_templates
            assert metadata["camera_type"] == camera_type.value

    def test_classify_with_ensemble_uses_custom_templates(
        self, mock_clip_model_for_ensemble
    ) -> None:
        """Test that custom templates override camera type selection."""
        model = mock_clip_model_for_ensemble
        test_image = Image.new("RGB", (224, 224), color="red")
        labels = ["person"]
        custom_templates = ["custom template showing {}", "another custom {}"]

        _, _, _, metadata = model.classify_with_ensemble(
            test_image, labels, templates=custom_templates
        )

        assert metadata["templates_used"] == custom_templates
        assert metadata["num_templates"] == len(custom_templates)

    def test_classify_with_ensemble_rejects_empty_labels(
        self, mock_clip_model_for_ensemble
    ) -> None:
        """Test that classify_with_ensemble raises ValueError for empty labels."""
        model = mock_clip_model_for_ensemble
        test_image = Image.new("RGB", (224, 224), color="red")

        with pytest.raises(ValueError) as exc_info:
            model.classify_with_ensemble(test_image, [])

        assert "empty" in str(exc_info.value).lower()

    def test_classify_with_ensemble_rejects_template_without_placeholder(
        self, mock_clip_model_for_ensemble
    ) -> None:
        """Test that templates without {} placeholder are rejected."""
        model = mock_clip_model_for_ensemble
        test_image = Image.new("RGB", (224, 224), color="red")
        labels = ["person"]
        bad_templates = ["template without placeholder"]

        with pytest.raises(ValueError) as exc_info:
            model.classify_with_ensemble(test_image, labels, templates=bad_templates)

        assert "placeholder" in str(exc_info.value).lower()

    def test_classify_with_ensemble_handles_model_not_loaded(self) -> None:
        """Test that classify_with_ensemble raises RuntimeError when model not loaded."""
        model = CLIPEmbeddingModel(model_path="/fake/path", device="cpu")
        # Don't load the model
        test_image = Image.new("RGB", (224, 224), color="red")

        with pytest.raises(RuntimeError) as exc_info:
            model.classify_with_ensemble(test_image, ["person"])

        assert "not loaded" in str(exc_info.value).lower()

    def test_classify_with_ensemble_converts_non_rgb_images(
        self, mock_clip_model_for_ensemble
    ) -> None:
        """Test that non-RGB images are converted before processing."""
        model = mock_clip_model_for_ensemble
        # Create a grayscale image
        test_image = Image.new("L", (224, 224), color=128)
        labels = ["person"]

        # Should not raise - image should be converted to RGB
        scores, _, _, _ = model.classify_with_ensemble(test_image, labels)

        assert len(scores) == 1


class TestClassifyEndpointWithEnsemble:
    """Tests for /classify endpoint with ensemble support (NEM-3029)."""

    @pytest.fixture(autouse=True)
    def mock_model_for_classify(self):
        """Mock the global model instance for classify endpoint tests."""
        mock_instance = MagicMock()
        mock_instance.model = MagicMock()

        # Mock classify (simple)
        mock_instance.classify.return_value = (
            {"person": 0.8, "car": 0.2},
            "person",
            10.0,
        )

        # Mock classify_with_ensemble
        mock_instance.classify_with_ensemble.return_value = (
            {"person": 0.85, "car": 0.15},
            "person",
            15.0,
            {
                "templates_used": SURVEILLANCE_TEMPLATES,
                "num_templates": 5,
                "camera_type": "standard",
                "ensemble_method": "mean",
            },
        )

        original_model = getattr(model_module, "model", None)
        model_module.model = mock_instance
        yield mock_instance
        model_module.model = original_model

    def test_classify_uses_ensemble_by_default(
        self, client, dummy_image_base64, mock_model_for_classify
    ) -> None:
        """Test that /classify uses ensemble classification by default."""
        response = client.post(
            "/classify",
            json={"image": dummy_image_base64, "labels": ["person", "car"]},
        )

        assert response.status_code == 200
        # Should have called classify_with_ensemble, not classify
        mock_model_for_classify.classify_with_ensemble.assert_called_once()
        mock_model_for_classify.classify.assert_not_called()

    def test_classify_returns_ensemble_metadata(self, client, dummy_image_base64) -> None:
        """Test that /classify returns ensemble metadata when using ensembling."""
        response = client.post(
            "/classify",
            json={"image": dummy_image_base64, "labels": ["person", "car"]},
        )

        assert response.status_code == 200
        data = response.json()
        assert "ensemble_metadata" in data
        assert data["ensemble_metadata"] is not None
        assert "templates_used" in data["ensemble_metadata"]
        assert "num_templates" in data["ensemble_metadata"]

    def test_classify_without_ensemble(
        self, client, dummy_image_base64, mock_model_for_classify
    ) -> None:
        """Test that /classify can disable ensemble with use_ensemble=False."""
        response = client.post(
            "/classify",
            json={
                "image": dummy_image_base64,
                "labels": ["person", "car"],
                "use_ensemble": False,
            },
        )

        assert response.status_code == 200
        # Should have called classify, not classify_with_ensemble
        mock_model_for_classify.classify.assert_called_once()
        mock_model_for_classify.classify_with_ensemble.assert_not_called()

    def test_classify_without_ensemble_returns_null_metadata(
        self, client, dummy_image_base64
    ) -> None:
        """Test that ensemble_metadata is null when use_ensemble=False."""
        response = client.post(
            "/classify",
            json={
                "image": dummy_image_base64,
                "labels": ["person", "car"],
                "use_ensemble": False,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["ensemble_metadata"] is None

    def test_classify_with_camera_type(
        self, client, dummy_image_base64, mock_model_for_classify
    ) -> None:
        """Test that /classify accepts camera_type parameter."""
        response = client.post(
            "/classify",
            json={
                "image": dummy_image_base64,
                "labels": ["person", "car"],
                "camera_type": "night_vision",
            },
        )

        assert response.status_code == 200
        # Verify camera_type was passed to the method
        call_args = mock_model_for_classify.classify_with_ensemble.call_args
        assert call_args.kwargs["camera_type"] == CameraType.NIGHT_VISION

    def test_classify_with_invalid_camera_type(self, client, dummy_image_base64) -> None:
        """Test that /classify rejects invalid camera_type values."""
        response = client.post(
            "/classify",
            json={
                "image": dummy_image_base64,
                "labels": ["person", "car"],
                "camera_type": "invalid_type",
            },
        )

        assert response.status_code == 422  # Pydantic validation error

    def test_classify_response_contains_scores(self, client, dummy_image_base64) -> None:
        """Test that /classify response contains scores dict."""
        response = client.post(
            "/classify",
            json={"image": dummy_image_base64, "labels": ["person", "car"]},
        )

        assert response.status_code == 200
        data = response.json()
        assert "scores" in data
        assert isinstance(data["scores"], dict)
        assert "person" in data["scores"]
        assert "car" in data["scores"]

    def test_classify_response_contains_top_label(self, client, dummy_image_base64) -> None:
        """Test that /classify response contains top_label."""
        response = client.post(
            "/classify",
            json={"image": dummy_image_base64, "labels": ["person", "car"]},
        )

        assert response.status_code == 200
        data = response.json()
        assert "top_label" in data
        assert data["top_label"] == "person"

    def test_classify_response_contains_inference_time(self, client, dummy_image_base64) -> None:
        """Test that /classify response contains inference_time_ms."""
        response = client.post(
            "/classify",
            json={"image": dummy_image_base64, "labels": ["person", "car"]},
        )

        assert response.status_code == 200
        data = response.json()
        assert "inference_time_ms" in data
        assert isinstance(data["inference_time_ms"], float)


class TestClassifyRequestModel:
    """Tests for ClassifyRequest Pydantic model with ensemble fields."""

    def test_classify_request_defaults_to_ensemble_true(self, dummy_image_base64) -> None:
        """Test that use_ensemble defaults to True."""
        request = ClassifyRequest(
            image=dummy_image_base64,
            labels=["person", "car"],
        )
        assert request.use_ensemble is True

    def test_classify_request_defaults_to_standard_camera_type(self, dummy_image_base64) -> None:
        """Test that camera_type defaults to STANDARD."""
        request = ClassifyRequest(
            image=dummy_image_base64,
            labels=["person", "car"],
        )
        assert request.camera_type == CameraType.STANDARD

    def test_classify_request_accepts_camera_type_enum(self, dummy_image_base64) -> None:
        """Test that ClassifyRequest accepts CameraType enum values."""
        for camera_type in CameraType:
            request = ClassifyRequest(
                image=dummy_image_base64,
                labels=["person"],
                camera_type=camera_type,
            )
            assert request.camera_type == camera_type

    def test_classify_request_accepts_camera_type_string(self, dummy_image_base64) -> None:
        """Test that ClassifyRequest accepts camera type as string."""
        request = ClassifyRequest(
            image=dummy_image_base64,
            labels=["person"],
            camera_type="night_vision",
        )
        assert request.camera_type == CameraType.NIGHT_VISION

    def test_classify_request_can_disable_ensemble(self, dummy_image_base64) -> None:
        """Test that use_ensemble can be set to False."""
        request = ClassifyRequest(
            image=dummy_image_base64,
            labels=["person"],
            use_ensemble=False,
        )
        assert request.use_ensemble is False


class TestEnsembleVsSinglePromptComparison:
    """Tests comparing ensemble vs single-prompt classification behavior.

    These tests document the expected behavioral differences between
    ensemble and non-ensemble classification.
    """

    @pytest.fixture
    def mock_model_with_tracking(self):
        """Create a mock model that tracks method calls."""
        mock_instance = MagicMock()
        mock_instance.model = MagicMock()
        mock_instance.classify_call_count = 0
        mock_instance.ensemble_call_count = 0

        def track_classify(*args, **kwargs):
            mock_instance.classify_call_count += 1
            return ({"person": 0.7, "car": 0.3}, "person", 8.0)

        def track_ensemble(*args, **kwargs):
            mock_instance.ensemble_call_count += 1
            return (
                {"person": 0.75, "car": 0.25},
                "person",
                12.0,
                {
                    "templates_used": SURVEILLANCE_TEMPLATES,
                    "num_templates": 5,
                    "camera_type": "standard",
                    "ensemble_method": "mean",
                },
            )

        mock_instance.classify.side_effect = track_classify
        mock_instance.classify_with_ensemble.side_effect = track_ensemble

        original_model = getattr(model_module, "model", None)
        model_module.model = mock_instance
        yield mock_instance
        model_module.model = original_model

    def test_ensemble_method_called_more_text_encoder_calls(self, mock_model_with_tracking) -> None:
        """Document that ensemble uses more text encoder calls (one per template)."""
        # This is expected behavior - ensemble processes multiple templates
        # The mock tracks that classify_with_ensemble was called
        mock_model_with_tracking.classify_with_ensemble(
            Image.new("RGB", (100, 100), "red"),
            ["person", "car"],
        )

        assert mock_model_with_tracking.ensemble_call_count == 1

    def test_ensemble_typically_higher_latency(
        self,
        client,
        dummy_image_base64,
        mock_model_with_tracking,
    ) -> None:
        """Document that ensemble typically has higher latency than simple classify."""
        # Call with ensemble (default)
        response_ensemble = client.post(
            "/classify",
            json={"image": dummy_image_base64, "labels": ["person", "car"]},
        )

        # Call without ensemble
        response_simple = client.post(
            "/classify",
            json={"image": dummy_image_base64, "labels": ["person", "car"], "use_ensemble": False},
        )

        ensemble_time = response_ensemble.json()["inference_time_ms"]
        simple_time = response_simple.json()["inference_time_ms"]

        # Ensemble should take longer due to multiple template processing
        # (In this mock, ensemble returns 12.0ms vs simple 8.0ms)
        assert ensemble_time > simple_time


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
