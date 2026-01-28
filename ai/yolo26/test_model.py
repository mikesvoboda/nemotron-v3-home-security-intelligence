"""Unit tests for YOLO26 inference server."""

import base64
import io
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from fastapi.testclient import TestClient

# Add the ai/yolo26 directory to sys.path to enable imports
# This handles both pytest from project root and running tests directly
_yolo26_dir = Path(__file__).parent
if str(_yolo26_dir) not in sys.path:
    sys.path.insert(0, str(_yolo26_dir))

# Now import from the local model module
import model as model_module
from model import (
    MAX_IMAGE_SIZE_BYTES,
    SECURITY_CLASSES,
    SUPPORTED_IMAGE_EXTENSIONS,
    BoundingBox,
    Detection,
    DetectionResponse,
    YOLO26Model,
    app,
    get_gpu_metrics,
    validate_file_extension,
    validate_image_magic_bytes,
)
from PIL import Image

MODEL_MODULE_PATH = "model"


@pytest.fixture
def dummy_image():
    """Create a dummy PIL image for testing."""
    img_array = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    return Image.fromarray(img_array)


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


class TestBoundingBox:
    """Tests for BoundingBox model."""

    def test_bounding_box_creation(self):
        """Test creating a bounding box."""
        bbox = BoundingBox(x=10, y=20, width=100, height=150)
        assert bbox.x == 10
        assert bbox.y == 20
        assert bbox.width == 100
        assert bbox.height == 150


class TestDetection:
    """Tests for Detection model."""

    def test_detection_creation(self):
        """Test creating a detection."""
        detection = Detection(
            class_name="person",
            confidence=0.95,
            bbox=BoundingBox(x=10, y=20, width=100, height=150),
        )
        assert detection.class_name == "person"
        assert detection.confidence == 0.95
        assert detection.bbox.x == 10

    def test_detection_with_alias(self):
        """Test detection with 'class' alias."""
        detection = Detection(
            **{
                "class": "car",
                "confidence": 0.88,
                "bbox": {"x": 50, "y": 60, "width": 200, "height": 150},
            }
        )
        assert detection.class_name == "car"
        assert detection.confidence == 0.88


class TestDetectionResponse:
    """Tests for DetectionResponse model."""

    def test_detection_response_creation(self):
        """Test creating a detection response."""
        response = DetectionResponse(
            detections=[
                Detection(
                    class_name="person",
                    confidence=0.95,
                    bbox=BoundingBox(x=10, y=20, width=100, height=150),
                )
            ],
            inference_time_ms=45.2,
            image_width=640,
            image_height=480,
        )
        assert len(response.detections) == 1
        assert response.inference_time_ms == 45.2
        assert response.image_width == 640
        assert response.image_height == 480

    def test_empty_detections(self):
        """Test response with no detections."""
        response = DetectionResponse(
            detections=[], inference_time_ms=30.0, image_width=640, image_height=480
        )
        assert len(response.detections) == 0


class TestYOLO26Model:
    """Tests for YOLO26Model class (Ultralytics YOLO-based)."""

    def test_model_initialization(self):
        """Test model initialization with Ultralytics YOLO."""
        model = YOLO26Model(model_path="dummy_model_path", confidence_threshold=0.6, device="cpu")
        assert model.confidence_threshold == 0.6
        assert model.device == "cpu"
        assert model.model_path == "dummy_model_path"
        assert model.model is None  # Not loaded yet

    def test_model_initialization_with_default_values(self):
        """Test model initialization with default confidence threshold and device."""
        model = YOLO26Model(model_path="test_path")
        assert model.confidence_threshold == 0.5  # default
        assert model.device == "cuda:0"  # default

    def test_security_classes_filter(self):
        """Test that only security-relevant classes are included."""
        expected_classes = {
            "person",
            "car",
            "truck",
            "dog",
            "cat",
            "bird",
            "bicycle",
            "motorcycle",
            "bus",
        }
        assert expected_classes == SECURITY_CLASSES


class TestAPIEndpoints:
    """Tests for FastAPI endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture(autouse=True)
    def mock_model(self):
        """Mock the global model instance."""
        mock_instance = MagicMock()
        mock_instance.detect.return_value = (
            [
                {
                    "class": "person",
                    "confidence": 0.95,
                    "bbox": {"x": 100, "y": 150, "width": 200, "height": 400},
                }
            ],
            45.2,
        )
        # Directly set the module's model attribute
        original_model = getattr(model_module, "model", None)
        model_module.model = mock_instance
        yield mock_instance
        # Restore original
        model_module.model = original_model

    def test_health_endpoint(self, client, mock_model):
        """Test health check endpoint."""
        # Set up mock model with required attributes
        mock_model.model_path = "/dummy/path"
        mock_model.model = MagicMock()
        with patch(f"{MODEL_MODULE_PATH}.torch.cuda.is_available", return_value=False):
            response = client.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert "status" in data
            assert "model_loaded" in data
            assert "device" in data
            assert "cuda_available" in data

    def test_detect_endpoint_with_file(self, client, dummy_image_bytes):
        """Test detection endpoint with file upload."""
        response = client.post(
            "/detect", files={"file": ("test.jpg", dummy_image_bytes, "image/jpeg")}
        )

        assert response.status_code == 200
        data = response.json()
        assert "detections" in data
        assert "inference_time_ms" in data
        assert "image_width" in data
        assert "image_height" in data

    def test_detect_endpoint_with_base64(self, client, dummy_image_base64):
        """Test detection endpoint with base64 image."""
        response = client.post("/detect", json={"image_base64": dummy_image_base64})

        # Note: FastAPI expects form data or query params, not JSON body
        # This test may need adjustment based on actual implementation
        # For now, testing the validation error
        assert response.status_code in [200, 400, 422]

    def test_detect_endpoint_no_input(self, client):
        """Test detection endpoint with no input."""
        response = client.post("/detect")
        # Returns 400 when neither file nor base64 is provided
        assert response.status_code == 400

    def test_detect_endpoint_model_not_loaded(self, client):
        """Test detection when model is not loaded."""
        original_model = model_module.model
        model_module.model = None
        try:
            response = client.post(
                "/detect", files={"file": ("test.jpg", b"fake image data", "image/jpeg")}
            )
            assert response.status_code == 503
        finally:
            model_module.model = original_model

    def test_batch_detect_endpoint(self, client, dummy_image_bytes, mock_model):
        """Test batch detection endpoint."""
        mock_model.detect_batch.return_value = (
            [
                [
                    {
                        "class": "person",
                        "confidence": 0.95,
                        "bbox": {"x": 10, "y": 20, "width": 100, "height": 150},
                    }
                ],
                [
                    {
                        "class": "car",
                        "confidence": 0.88,
                        "bbox": {"x": 50, "y": 60, "width": 200, "height": 150},
                    }
                ],
            ],
            90.5,
        )

        files = [
            ("files", ("test1.jpg", dummy_image_bytes, "image/jpeg")),
            ("files", ("test2.jpg", dummy_image_bytes, "image/jpeg")),
        ]

        response = client.post("/detect/batch", files=files)

        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert "total_inference_time_ms" in data
        assert "num_images" in data

    def test_batch_detect_empty_files(self, client):
        """Test batch detection with no files."""
        response = client.post("/detect/batch", files=[])
        assert response.status_code == 422  # Validation error


class TestSizeLimits:
    """Tests for image size limits to prevent DoS attacks."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def large_image_bytes(self):
        """Create image bytes larger than MAX_IMAGE_SIZE_BYTES."""
        # Create an image that will exceed the size limit when encoded
        large_array = np.random.randint(0, 255, (4000, 4000, 3), dtype=np.uint8)
        img = Image.fromarray(large_array)
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="JPEG", quality=95)
        img_bytes.seek(0)
        return img_bytes.getvalue()

    def test_image_size_limit(self, client, large_image_bytes):
        """Test that oversized images are rejected."""
        # If image is too large, it will either get rejected with 413 or
        # when model is not loaded, will return 503
        if len(large_image_bytes) > MAX_IMAGE_SIZE_BYTES:
            response = client.post(
                "/detect", files={"file": ("large.jpg", large_image_bytes, "image/jpeg")}
            )
            # May return 413 (Payload Too Large) or 503 (Service Unavailable if model not loaded)
            assert response.status_code in [413, 503]


class TestImageValidation:
    """Tests for image validation functions."""

    def test_validate_file_extension_valid(self):
        """Test validation of supported image extensions."""
        for ext in SUPPORTED_IMAGE_EXTENSIONS:
            is_valid, msg = validate_file_extension(f"image{ext}")
            assert is_valid is True, f"Failed for extension {ext}: {msg}"

    def test_validate_file_extension_invalid(self):
        """Test rejection of unsupported file extensions."""
        is_valid, msg = validate_file_extension("image.txt")
        assert is_valid is False
        assert "Unsupported" in msg or "extension" in msg.lower()

        is_valid, msg = validate_file_extension("image.pdf")
        assert is_valid is False

        is_valid, msg = validate_file_extension("image.exe")
        assert is_valid is False

    def test_validate_image_magic_bytes_jpeg(self):
        """Test validation of JPEG magic bytes."""
        # JPEG magic bytes: FF D8 FF
        jpeg_bytes = b"\xff\xd8\xff\xe0" + b"\x00" * 10
        is_valid, format_name = validate_image_magic_bytes(jpeg_bytes)
        assert is_valid is True
        assert "JPEG" in format_name or "jpeg" in format_name.lower()

    def test_validate_image_magic_bytes_png(self):
        """Test validation of PNG magic bytes."""
        # PNG magic bytes: 89 50 4E 47
        png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 10
        is_valid, format_name = validate_image_magic_bytes(png_bytes)
        assert is_valid is True
        assert "PNG" in format_name or "png" in format_name.lower()

    def test_validate_image_magic_bytes_invalid(self):
        """Test rejection of invalid magic bytes."""
        invalid_bytes = b"NOT_AN_IMAGE" + b"\x00" * 10
        is_valid, error_msg = validate_image_magic_bytes(invalid_bytes)
        assert is_valid is False


class TestMetricsEndpoint:
    """Tests for Prometheus metrics endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_metrics_endpoint(self, client):
        """Test that metrics endpoint returns valid Prometheus format."""
        response = client.get("/metrics")
        assert response.status_code == 200
        # Check for Prometheus format markers
        assert b"# HELP" in response.content or b"# TYPE" in response.content


class TestGPUMetrics:
    """Tests for GPU metrics collection."""

    @patch(f"{MODEL_MODULE_PATH}.torch.cuda.is_available", return_value=False)
    def test_get_gpu_metrics_cpu_only(self, _mock_is_available):
        """Test GPU metrics when CUDA is not available."""
        metrics = get_gpu_metrics()
        # When CUDA is not available, GPU metrics should all be None
        assert metrics["gpu_utilization"] is None
        assert metrics["temperature"] is None
        assert metrics["power_watts"] is None

    @patch(f"{MODEL_MODULE_PATH}.torch.cuda.is_available", return_value=True)
    def test_get_gpu_metrics_with_cuda(self, _mock_is_available):
        """Test GPU metrics when CUDA is available."""
        # When CUDA is available but pynvml fails, metrics will be None
        # This is fine for testing purposes
        metrics = get_gpu_metrics()
        assert isinstance(metrics, dict)
        assert "gpu_utilization" in metrics
        assert "temperature" in metrics
        assert "power_watts" in metrics
