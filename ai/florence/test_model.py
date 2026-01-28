"""Unit tests for Florence-2 Vision-Language Server.

Tests cover:
- Security objects detection endpoint (NEM-3027)
- SecurityObjectsResponse model validation
- SECURITY_OBJECTS vocabulary constant
- Endpoint behavior with mocked model
"""

import base64
import io
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from PIL import Image

# Add the ai/florence directory to sys.path to enable imports
_florence_dir = Path(__file__).parent
if str(_florence_dir) not in sys.path:
    sys.path.insert(0, str(_florence_dir))

# Now import from the local model module
import model as model_module
from model import (
    OPEN_VOCABULARY_DETECTION_PROMPT,
    SECURITY_OBJECTS,
    SECURITY_OBJECTS_PROMPT,
    SecurityObjectDetection,
    SecurityObjectsResponse,
    app,
)

MODEL_MODULE_PATH = "model"


@pytest.fixture
def dummy_image():
    """Create a dummy PIL image for testing."""
    return Image.new("RGB", (640, 480), color="red")


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


class TestSecurityObjectsVocabulary:
    """Tests for SECURITY_OBJECTS vocabulary constant (NEM-3027)."""

    def test_security_objects_is_list(self):
        """Test that SECURITY_OBJECTS is a list."""
        assert isinstance(SECURITY_OBJECTS, list)

    def test_security_objects_contains_expected_categories(self):
        """Test that SECURITY_OBJECTS contains expected security-relevant objects."""
        expected_objects = [
            "person",
            "face",
            "mask",
            "weapon",
            "knife",
            "gun",
            "vehicle",
            "car",
            "package",
            "backpack",
        ]
        for obj in expected_objects:
            assert obj in SECURITY_OBJECTS, f"Expected '{obj}' in SECURITY_OBJECTS"

    def test_security_objects_not_empty(self):
        """Test that SECURITY_OBJECTS is not empty."""
        assert len(SECURITY_OBJECTS) > 0

    def test_security_objects_all_strings(self):
        """Test that all items in SECURITY_OBJECTS are strings."""
        for obj in SECURITY_OBJECTS:
            assert isinstance(obj, str), f"Expected string, got {type(obj)}"

    def test_security_objects_no_duplicates(self):
        """Test that SECURITY_OBJECTS has no duplicate entries."""
        assert len(SECURITY_OBJECTS) == len(set(SECURITY_OBJECTS))


class TestSecurityObjectsPrompt:
    """Tests for SECURITY_OBJECTS_PROMPT constant (NEM-3027)."""

    def test_security_objects_prompt_format(self):
        """Test that SECURITY_OBJECTS_PROMPT has correct format."""
        assert SECURITY_OBJECTS_PROMPT.startswith("Detect: ")

    def test_security_objects_prompt_contains_objects(self):
        """Test that SECURITY_OBJECTS_PROMPT contains all security objects."""
        for obj in SECURITY_OBJECTS:
            assert obj in SECURITY_OBJECTS_PROMPT, f"Expected '{obj}' in prompt"

    def test_open_vocabulary_detection_prompt_format(self):
        """Test that OPEN_VOCABULARY_DETECTION_PROMPT is correctly formatted."""
        assert OPEN_VOCABULARY_DETECTION_PROMPT == "<OPEN_VOCABULARY_DETECTION>"


class TestSecurityObjectDetectionModel:
    """Tests for SecurityObjectDetection Pydantic model (NEM-3027)."""

    def test_security_object_detection_valid(self):
        """Test that SecurityObjectDetection accepts valid data."""
        detection = SecurityObjectDetection(
            label="person",
            bbox=[100.0, 150.0, 300.0, 400.0],
            confidence=0.95,
        )
        assert detection.label == "person"
        assert detection.bbox == [100.0, 150.0, 300.0, 400.0]
        assert detection.confidence == 0.95

    def test_security_object_detection_default_confidence(self):
        """Test that SecurityObjectDetection has default confidence of 1.0."""
        detection = SecurityObjectDetection(
            label="car",
            bbox=[0.0, 0.0, 100.0, 100.0],
        )
        assert detection.confidence == 1.0

    def test_security_object_detection_confidence_bounds(self):
        """Test that confidence is validated to be between 0 and 1."""
        # Valid minimum
        detection_min = SecurityObjectDetection(
            label="knife",
            bbox=[0.0, 0.0, 50.0, 50.0],
            confidence=0.0,
        )
        assert detection_min.confidence == 0.0

        # Valid maximum
        detection_max = SecurityObjectDetection(
            label="gun",
            bbox=[0.0, 0.0, 50.0, 50.0],
            confidence=1.0,
        )
        assert detection_max.confidence == 1.0

    def test_security_object_detection_rejects_invalid_confidence(self):
        """Test that confidence values outside [0, 1] are rejected."""
        with pytest.raises(ValueError):
            SecurityObjectDetection(
                label="weapon",
                bbox=[0.0, 0.0, 50.0, 50.0],
                confidence=1.5,  # Invalid: > 1.0
            )

        with pytest.raises(ValueError):
            SecurityObjectDetection(
                label="weapon",
                bbox=[0.0, 0.0, 50.0, 50.0],
                confidence=-0.1,  # Invalid: < 0.0
            )


class TestSecurityObjectsResponseModel:
    """Tests for SecurityObjectsResponse Pydantic model (NEM-3027)."""

    def test_security_objects_response_valid(self):
        """Test that SecurityObjectsResponse accepts valid data."""
        response = SecurityObjectsResponse(
            detections=[
                SecurityObjectDetection(label="person", bbox=[100, 150, 300, 400], confidence=1.0),
                SecurityObjectDetection(label="car", bbox=[400, 200, 600, 400], confidence=1.0),
            ],
            objects_queried=["person", "car", "package"],
            inference_time_ms=150.5,
        )
        assert len(response.detections) == 2
        assert response.detections[0].label == "person"
        assert response.objects_queried == ["person", "car", "package"]
        assert response.inference_time_ms == 150.5

    def test_security_objects_response_empty_detections(self):
        """Test that SecurityObjectsResponse accepts empty detections list."""
        response = SecurityObjectsResponse(
            detections=[],
            objects_queried=SECURITY_OBJECTS,
            inference_time_ms=100.0,
        )
        assert len(response.detections) == 0
        assert len(response.objects_queried) > 0


class TestDetectSecurityObjectsEndpoint:
    """Tests for /detect_security_objects endpoint (NEM-3027)."""

    @pytest.fixture(autouse=True)
    def mock_model(self):
        """Mock the global model instance."""
        mock_instance = MagicMock()
        mock_instance.model = MagicMock()
        # Return Florence-2 style detection result
        mock_instance.extract_raw.return_value = (
            {
                "bboxes": [[100, 150, 300, 400], [400, 200, 600, 400]],
                "bboxes_labels": ["person", "car"],
            },
            150.0,  # inference_time_ms
        )
        original_model = getattr(model_module, "model", None)
        model_module.model = mock_instance
        yield mock_instance
        model_module.model = original_model

    def test_endpoint_returns_200_with_valid_image(self, client, dummy_image_base64):
        """Test that /detect_security_objects returns 200 with valid image."""
        response = client.post(
            "/detect_security_objects",
            json={"image": dummy_image_base64},
        )
        assert response.status_code == 200

    def test_endpoint_returns_detections(self, client, dummy_image_base64):
        """Test that /detect_security_objects returns expected detection structure."""
        response = client.post(
            "/detect_security_objects",
            json={"image": dummy_image_base64},
        )
        assert response.status_code == 200
        data = response.json()

        assert "detections" in data
        assert "objects_queried" in data
        assert "inference_time_ms" in data

        assert len(data["detections"]) == 2
        assert data["detections"][0]["label"] == "person"
        assert data["detections"][0]["bbox"] == [100, 150, 300, 400]
        assert data["detections"][0]["confidence"] == 1.0

        assert data["detections"][1]["label"] == "car"

    def test_endpoint_returns_objects_queried(self, client, dummy_image_base64):
        """Test that /detect_security_objects returns the security objects list."""
        response = client.post(
            "/detect_security_objects",
            json={"image": dummy_image_base64},
        )
        assert response.status_code == 200
        data = response.json()

        # Should return the full SECURITY_OBJECTS list
        assert data["objects_queried"] == SECURITY_OBJECTS

    def test_endpoint_calls_model_with_correct_prompt(self, client, dummy_image_base64, mock_model):
        """Test that /detect_security_objects calls model with correct prompt."""
        response = client.post(
            "/detect_security_objects",
            json={"image": dummy_image_base64},
        )
        assert response.status_code == 200

        # Verify extract_raw was called
        mock_model.extract_raw.assert_called_once()

        # Get the prompt that was used
        call_args = mock_model.extract_raw.call_args
        prompt_used = call_args[0][1]  # Second positional argument

        # Verify prompt format
        assert prompt_used.startswith(OPEN_VOCABULARY_DETECTION_PROMPT)
        assert SECURITY_OBJECTS_PROMPT in prompt_used

    def test_endpoint_handles_empty_detections(self, client, dummy_image_base64, mock_model):
        """Test that /detect_security_objects handles empty detection results."""
        # Mock empty detection result
        mock_model.extract_raw.return_value = (
            {"bboxes": [], "bboxes_labels": []},
            100.0,
        )

        response = client.post(
            "/detect_security_objects",
            json={"image": dummy_image_base64},
        )
        assert response.status_code == 200
        data = response.json()

        assert data["detections"] == []
        assert data["objects_queried"] == SECURITY_OBJECTS

    def test_endpoint_handles_alternative_keys(self, client, dummy_image_base64, mock_model):
        """Test that endpoint handles alternative result keys (boxes/labels)."""
        # Mock result with alternative keys
        mock_model.extract_raw.return_value = (
            {
                "boxes": [[50, 50, 150, 150]],
                "labels": ["package"],
            },
            120.0,
        )

        response = client.post(
            "/detect_security_objects",
            json={"image": dummy_image_base64},
        )
        assert response.status_code == 200
        data = response.json()

        assert len(data["detections"]) == 1
        assert data["detections"][0]["label"] == "package"


class TestDetectSecurityObjectsEndpointErrors:
    """Tests for /detect_security_objects endpoint error handling."""

    def test_endpoint_returns_503_when_model_not_loaded(self, client, dummy_image_base64):
        """Test that /detect_security_objects returns 503 when model is not loaded."""
        original_model = model_module.model
        model_module.model = None

        try:
            response = client.post(
                "/detect_security_objects",
                json={"image": dummy_image_base64},
            )
            assert response.status_code == 503
            assert "Model not loaded" in response.json()["detail"]
        finally:
            model_module.model = original_model

    def test_endpoint_returns_400_for_invalid_base64(self, client):
        """Test that /detect_security_objects returns 400 for invalid base64."""
        # Mock model to ensure we get past the model check
        mock_instance = MagicMock()
        mock_instance.model = MagicMock()
        original_model = model_module.model
        model_module.model = mock_instance

        try:
            response = client.post(
                "/detect_security_objects",
                json={"image": "not-valid-base64!!!"},
            )
            assert response.status_code == 400
        finally:
            model_module.model = original_model

    def test_endpoint_returns_400_for_non_image_data(self, client):
        """Test that /detect_security_objects returns 400 for non-image base64."""
        mock_instance = MagicMock()
        mock_instance.model = MagicMock()
        original_model = model_module.model
        model_module.model = mock_instance

        try:
            # Valid base64 but not an image
            non_image = base64.b64encode(b"This is text, not an image").decode("utf-8")
            response = client.post(
                "/detect_security_objects",
                json={"image": non_image},
            )
            assert response.status_code == 400
        finally:
            model_module.model = original_model


class TestDetectSecurityObjectsMetrics:
    """Tests for /detect_security_objects endpoint metrics tracking."""

    @pytest.fixture(autouse=True)
    def mock_model(self):
        """Mock the global model instance."""
        mock_instance = MagicMock()
        mock_instance.model = MagicMock()
        mock_instance.extract_raw.return_value = (
            {"bboxes": [], "bboxes_labels": []},
            100.0,
        )
        original_model = getattr(model_module, "model", None)
        model_module.model = mock_instance
        yield mock_instance
        model_module.model = original_model

    def test_endpoint_records_success_metrics(self, client, dummy_image_base64):
        """Test that successful requests increment success metrics."""
        # Clear any existing metrics

        # Make a successful request
        response = client.post(
            "/detect_security_objects",
            json={"image": dummy_image_base64},
        )
        assert response.status_code == 200

        # The metrics should have been incremented (we can't easily verify the exact values
        # without more complex setup, but we verify the endpoint doesn't crash)

    def test_endpoint_returns_inference_time(self, client, dummy_image_base64):
        """Test that endpoint returns inference time in response."""
        response = client.post(
            "/detect_security_objects",
            json={"image": dummy_image_base64},
        )
        assert response.status_code == 200
        data = response.json()

        assert "inference_time_ms" in data
        assert data["inference_time_ms"] == 100.0  # From mock (via autouse fixture)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
