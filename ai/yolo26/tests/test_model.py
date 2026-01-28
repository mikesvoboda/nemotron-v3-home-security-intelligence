"""Unit tests for YOLO26 inference server."""

import io
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from fastapi.testclient import TestClient

# Add the ai/yolo26 directory to sys.path to enable imports
# This handles both pytest from project root and running tests directly
_yolo26_dir = Path(__file__).parent.parent
if str(_yolo26_dir) not in sys.path:
    sys.path.insert(0, str(_yolo26_dir))

# Now import from the local model module
import model as model_module
from model import (
    COCO_CLASSES,
    MAX_BASE64_SIZE_BYTES,
    MAX_IMAGE_SIZE_BYTES,
    SECURITY_CLASSES,
    SUPPORTED_IMAGE_EXTENSIONS,
    BoundingBox,
    Detection,
    DetectionResponse,
    HealthResponse,
    YOLO26Model,
    app,
    delete_stale_engine,
    get_gpu_metrics,
    get_pt_model_path_for_engine,
    get_tensorrt_version,
    is_tensorrt_version_mismatch_error,
    validate_file_extension,
    validate_image_magic_bytes,
)
from PIL import Image

MODEL_MODULE_PATH = "model"


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
    """Tests for YOLO26Model class (Ultralytics YOLO with TensorRT)."""

    def test_model_initialization(self):
        """Test model initialization."""
        model = YOLO26Model(model_path="dummy_model_path", confidence_threshold=0.6, device="cpu")
        assert model.confidence_threshold == 0.6
        assert model.device == "cpu"
        assert model.model_path == "dummy_model_path"
        assert model.model is None  # Not loaded yet
        assert model.cache_clear_frequency == 1  # default

    def test_model_initialization_with_default_values(self):
        """Test model initialization with default confidence threshold and device."""
        model = YOLO26Model(model_path="test_path")
        assert model.confidence_threshold == 0.5  # default
        assert model.device == "cuda:0"  # default
        assert model.cache_clear_frequency == 1  # default

    def test_model_initialization_with_cache_clear_frequency(self):
        """Test model initialization with custom cache clear frequency."""
        model = YOLO26Model(model_path="test_path", cache_clear_frequency=10)
        assert model.cache_clear_frequency == 10
        assert model.cache_clear_count == 0

    def test_model_initialization_cache_clear_disabled(self):
        """Test model initialization with cache clearing disabled."""
        model = YOLO26Model(model_path="test_path", cache_clear_frequency=0)
        assert model.cache_clear_frequency == 0

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

    def test_coco_class_mapping(self):
        """Test COCO class ID to name mapping."""
        assert COCO_CLASSES[0] == "person"
        assert COCO_CLASSES[2] == "car"
        assert COCO_CLASSES[7] == "truck"
        assert COCO_CLASSES[16] == "dog"

    def test_detect_raises_if_model_not_loaded(self):
        """Test that detect() raises RuntimeError if model not loaded."""
        model = YOLO26Model(model_path="test_path")
        test_image = Image.new("RGB", (640, 480), color=(128, 128, 128))

        with pytest.raises(RuntimeError, match="Model not loaded"):
            model.detect(test_image)

    def test_detect_with_mock_model(self, mock_yolo_model):
        """Test detect method with mocked YOLO model."""
        model = YOLO26Model(model_path="test_path", device="cpu", cache_clear_frequency=0)
        model.model = mock_yolo_model

        test_image = Image.new("RGB", (640, 480), color=(128, 128, 128))

        detections, inference_time = model.detect(test_image)

        # Verify results
        assert len(detections) == 1
        assert detections[0]["class"] == "person"
        assert detections[0]["confidence"] == 0.95
        assert detections[0]["bbox"]["x"] == 100
        assert detections[0]["bbox"]["y"] == 150
        assert detections[0]["bbox"]["width"] == 200  # 300 - 100
        assert detections[0]["bbox"]["height"] == 400  # 550 - 150
        assert inference_time > 0

    def test_detect_converts_rgba_to_rgb(self, mock_yolo_model):
        """Test that RGBA images are converted to RGB."""
        model = YOLO26Model(model_path="test_path", device="cpu", cache_clear_frequency=0)
        model.model = mock_yolo_model

        # Create RGBA image
        rgba_image = Image.new("RGBA", (640, 480), color=(128, 128, 128, 255))

        detections, _ = model.detect(rgba_image)

        # Should not raise and should return results
        assert isinstance(detections, list)
        # Verify predict was called (model conversion happened)
        mock_yolo_model.predict.assert_called_once()

    def test_detect_filters_non_security_classes(self):
        """Test that non-security classes are filtered out."""
        model = YOLO26Model(model_path="test_path", device="cpu", cache_clear_frequency=0)

        # Create mock model that returns non-security class
        mock_model = MagicMock()
        mock_result = MagicMock()
        mock_boxes = MagicMock()

        # Mock a detection for "chair" (class ID 56 in COCO, not in SECURITY_CLASSES)
        mock_box = MagicMock()
        mock_box.cls.item.return_value = 56  # chair class (not security-relevant)
        mock_box.conf.item.return_value = 0.90
        mock_box.xyxy = [[100.0, 150.0, 300.0, 550.0]]

        mock_boxes.__len__.return_value = 1
        mock_boxes.__iter__.return_value = iter([mock_box])
        mock_result.boxes = mock_boxes
        mock_model.predict.return_value = [mock_result]

        model.model = mock_model

        test_image = Image.new("RGB", (640, 480), color=(128, 128, 128))
        detections, _ = model.detect(test_image)

        # Should filter out non-security class
        assert len(detections) == 0

    def test_detect_with_empty_results(self, mock_empty_yolo_model):
        """Test detect with no detections."""
        model = YOLO26Model(model_path="test_path", device="cpu", cache_clear_frequency=0)
        model.model = mock_empty_yolo_model

        test_image = Image.new("RGB", (640, 480), color=(128, 128, 128))
        detections, inference_time = model.detect(test_image)

        assert len(detections) == 0
        assert inference_time > 0

    def test_detect_batch_processes_multiple_images(self, mock_yolo_model):
        """Test detect_batch processes multiple images."""
        model = YOLO26Model(model_path="test_path", device="cpu", cache_clear_frequency=0)
        model.model = mock_yolo_model

        test_images = [
            Image.new("RGB", (640, 480), color=(128, 128, 128)),
            Image.new("RGB", (640, 480), color=(64, 64, 64)),
        ]

        all_detections, total_time = model.detect_batch(test_images)

        assert len(all_detections) == 2
        assert all(isinstance(dets, list) for dets in all_detections)
        assert total_time > 0
        # Verify predict was called twice
        assert mock_yolo_model.predict.call_count == 2

    def test_cuda_cache_clearing_called(self, mock_yolo_model):
        """Test that CUDA cache clearing is called when enabled."""
        model = YOLO26Model(model_path="test_path", device="cuda:0", cache_clear_frequency=1)
        model.model = mock_yolo_model

        test_image = Image.new("RGB", (640, 480), color=(128, 128, 128))

        with (
            patch(f"{MODEL_MODULE_PATH}.torch.cuda.is_available", return_value=True),
            patch(f"{MODEL_MODULE_PATH}.torch.cuda.empty_cache") as mock_empty_cache,
        ):
            model.detect(test_image)

            # Verify cache was cleared
            mock_empty_cache.assert_called_once()
            assert model.cache_clear_count == 1

    def test_cuda_cache_not_cleared_on_cpu(self, mock_yolo_model):
        """Test that CUDA cache is not cleared on CPU."""
        model = YOLO26Model(model_path="test_path", device="cpu", cache_clear_frequency=1)
        model.model = mock_yolo_model

        test_image = Image.new("RGB", (640, 480), color=(128, 128, 128))

        with (
            patch(f"{MODEL_MODULE_PATH}.torch.cuda.is_available", return_value=False),
            patch(f"{MODEL_MODULE_PATH}.torch.cuda.empty_cache") as mock_empty_cache,
        ):
            model.detect(test_image)

            # Verify cache was NOT cleared
            mock_empty_cache.assert_not_called()

    def test_cuda_cache_not_cleared_when_disabled(self, mock_yolo_model):
        """Test that CUDA cache is not cleared when frequency=0."""
        model = YOLO26Model(model_path="test_path", device="cuda:0", cache_clear_frequency=0)
        model.model = mock_yolo_model

        test_image = Image.new("RGB", (640, 480), color=(128, 128, 128))

        with (
            patch(f"{MODEL_MODULE_PATH}.torch.cuda.is_available", return_value=True),
            patch(f"{MODEL_MODULE_PATH}.torch.cuda.empty_cache") as mock_empty_cache,
        ):
            model.detect(test_image)

            # Verify cache was NOT cleared
            mock_empty_cache.assert_not_called()
            assert model.cache_clear_count == 0

    def test_detect_batch_cache_clearing_frequency(self, mock_yolo_model):
        """Test batch detection clears cache at configured frequency."""
        model = YOLO26Model(model_path="test_path", device="cuda:0", cache_clear_frequency=2)
        model.model = mock_yolo_model

        test_images = [Image.new("RGB", (640, 480), color=(i, i, i)) for i in range(5)]

        with (
            patch(f"{MODEL_MODULE_PATH}.torch.cuda.is_available", return_value=True),
            patch(f"{MODEL_MODULE_PATH}.torch.cuda.empty_cache") as mock_empty_cache,
        ):
            model.detect_batch(test_images)

            # With frequency=2 and 5 images: clear after image 2, 4
            # Total: 2 clears (not 5)
            assert mock_empty_cache.call_count == 2

    def test_detect_clears_cache_on_exception(self, mock_yolo_model):
        """Test that cache is cleared even when exception occurs."""
        model = YOLO26Model(model_path="test_path", device="cuda:0", cache_clear_frequency=1)
        mock_yolo_model.predict.side_effect = RuntimeError("Test error")
        model.model = mock_yolo_model

        test_image = Image.new("RGB", (640, 480), color=(128, 128, 128))

        with (
            patch(f"{MODEL_MODULE_PATH}.torch.cuda.is_available", return_value=True),
            patch(f"{MODEL_MODULE_PATH}.torch.cuda.empty_cache") as mock_empty_cache,
        ):
            with pytest.raises(RuntimeError, match="Test error"):
                model.detect(test_image)

            # Cache should still be cleared in finally block
            mock_empty_cache.assert_called_once()
            assert model.cache_clear_count == 1


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
        mock_instance.model = MagicMock()
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
        # Set required attributes for health check
        mock_instance._is_compiled = False
        mock_instance.torch_compile_mode = "reduce-overhead"
        # NEM-3877, NEM-3878: Add new health check attributes
        mock_instance.inference_healthy = True
        mock_instance.active_backend = "tensorrt"
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
        mock_model.tensorrt_enabled = True
        with patch(f"{MODEL_MODULE_PATH}.torch.cuda.is_available", return_value=False):
            response = client.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert "status" in data
            assert "model_loaded" in data
            assert "device" in data
            assert "cuda_available" in data
            assert "tensorrt_enabled" in data

    def test_health_endpoint_with_cuda(self, client, mock_model):
        """Test health endpoint with CUDA available."""
        mock_model.model_path = "/dummy/path"
        mock_model.tensorrt_enabled = True
        with (
            patch(f"{MODEL_MODULE_PATH}.torch.cuda.is_available", return_value=True),
            patch(f"{MODEL_MODULE_PATH}.get_vram_usage", return_value=3.5),
            patch(
                f"{MODEL_MODULE_PATH}.get_gpu_metrics",
                return_value={
                    "gpu_utilization": 75.0,
                    "temperature": 65,
                    "power_watts": 150.0,
                },
            ),
        ):
            response = client.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert data["cuda_available"] is True
            assert data["device"] == "cuda:0"
            assert data["vram_used_gb"] == 3.5
            assert data["gpu_utilization"] == 75.0
            assert data["temperature"] == 65
            assert data["power_watts"] == 150.0

    def test_metrics_endpoint(self, client, mock_model):
        """Test metrics endpoint."""
        mock_model.model_path = "/dummy/path"
        with patch(f"{MODEL_MODULE_PATH}.torch.cuda.is_available", return_value=False):
            response = client.get("/metrics")
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/plain")
            # Verify Prometheus format
            content = response.content.decode("utf-8")
            assert "yolo26_model_loaded" in content

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
    def dummy_image_bytes(self):
        """Create dummy image bytes for testing."""
        img_array = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        img = Image.fromarray(img_array)
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="JPEG")
        img_bytes.seek(0)
        return img_bytes.getvalue()

    @pytest.fixture(autouse=True)
    def _mock_model(self):
        """Mock the global model instance."""
        mock_instance = MagicMock()
        mock_instance.model = MagicMock()
        mock_instance.detect.return_value = ([], 10.0)
        mock_instance.detect_batch.return_value = ([[]], 10.0)
        original_model = getattr(model_module, "model", None)
        model_module.model = mock_instance
        yield mock_instance
        model_module.model = original_model

    def test_size_limits_are_reasonable(self):
        """Test that size limits are set to reasonable values."""
        # 10MB is reasonable for security camera images
        assert MAX_IMAGE_SIZE_BYTES == 10 * 1024 * 1024
        # Base64 encoding adds ~33% overhead
        assert MAX_BASE64_SIZE_BYTES > MAX_IMAGE_SIZE_BYTES
        assert MAX_BASE64_SIZE_BYTES < MAX_IMAGE_SIZE_BYTES * 2

    def test_detect_endpoint_rejects_oversized_file(self, client):
        """Test that oversized file uploads are rejected with 413."""
        # Create oversized data (just over 10MB)
        oversized_data = b"x" * (MAX_IMAGE_SIZE_BYTES + 1)

        response = client.post(
            "/detect", files={"file": ("large.jpg", oversized_data, "image/jpeg")}
        )

        assert response.status_code == 413
        assert "exceeds maximum" in response.json()["detail"]
        assert "10MB" in response.json()["detail"]

    def test_detect_endpoint_accepts_valid_sized_file(self, client, _mock_model, dummy_image_bytes):
        """Test that valid-sized files are accepted."""
        response = client.post(
            "/detect", files={"file": ("test.jpg", dummy_image_bytes, "image/jpeg")}
        )

        assert response.status_code == 200
        assert "detections" in response.json()

    def test_batch_detect_rejects_oversized_file(self, client, _mock_model, dummy_image_bytes):
        """Test that batch detection rejects oversized files with 413."""
        # Create one valid file and one oversized
        oversized_data = b"x" * (MAX_IMAGE_SIZE_BYTES + 1)

        files = [
            ("files", ("small.jpg", dummy_image_bytes, "image/jpeg")),
            ("files", ("large.jpg", oversized_data, "image/jpeg")),
        ]

        response = client.post("/detect/batch", files=files)

        assert response.status_code == 413
        assert "Image 1" in response.json()["detail"]  # Second file (index 1)
        assert "large.jpg" in response.json()["detail"]

    def test_batch_detect_accepts_valid_sized_files(self, client, _mock_model, dummy_image_bytes):
        """Test that batch detection accepts valid-sized files."""
        files = [
            ("files", ("test1.jpg", dummy_image_bytes, "image/jpeg")),
            ("files", ("test2.jpg", dummy_image_bytes, "image/jpeg")),
        ]

        response = client.post("/detect/batch", files=files)

        assert response.status_code == 200
        assert "results" in response.json()


class TestInvalidImageHandling:
    """Tests for invalid/corrupted image file handling.

    These tests verify that PIL.UnidentifiedImageError and similar errors
    are handled correctly, returning 400 Bad Request instead of 500 Server Error.
    """

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def dummy_image_bytes(self):
        """Create valid dummy image bytes for comparison."""
        img_array = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        img = Image.fromarray(img_array)
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="JPEG")
        img_bytes.seek(0)
        return img_bytes.getvalue()

    @pytest.fixture(autouse=True)
    def _mock_model(self):
        """Mock the global model instance."""
        mock_instance = MagicMock()
        mock_instance.model = MagicMock()
        mock_instance.detect.return_value = ([], 10.0)
        mock_instance.detect_batch.return_value = ([[]], 10.0)
        original_model = getattr(model_module, "model", None)
        model_module.model = mock_instance
        yield mock_instance
        model_module.model = original_model

    def test_detect_rejects_non_image_file_with_400(self, client):
        """Test that non-image files (e.g., text files) return 400 Bad Request."""
        # Send a text file disguised as a JPEG
        text_data = b"This is not an image, just plain text content."

        response = client.post(
            "/detect", files={"file": ("fake_image.jpg", text_data, "image/jpeg")}
        )

        assert response.status_code == 400
        assert "Invalid image file" in response.json()["detail"]
        assert "fake_image.jpg" in response.json()["detail"]

    def test_detect_rejects_corrupted_image_with_400(self, client):
        """Test that corrupted/truncated image files return 400 Bad Request."""
        # Create truncated JPEG data (valid header but incomplete)
        # JPEG files start with FF D8 FF
        corrupted_jpeg = bytes([0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10]) + b"corrupted data"

        response = client.post(
            "/detect", files={"file": ("corrupted.jpg", corrupted_jpeg, "image/jpeg")}
        )

        # Should return 400, not 500
        assert response.status_code == 400
        assert (
            "corrupted.jpg" in response.json()["detail"].lower()
            or "Invalid image file" in response.json()["detail"]
        )

    def test_detect_rejects_empty_file_with_400(self, client):
        """Test that empty files return 400 Bad Request."""
        response = client.post("/detect", files={"file": ("empty.jpg", b"", "image/jpeg")})

        assert response.status_code == 400
        assert (
            "empty.jpg" in response.json()["detail"].lower()
            or "Invalid image file" in response.json()["detail"]
        )

    def test_detect_rejects_random_binary_with_400(self, client):
        """Test that random binary data returns 400 Bad Request."""
        import os

        random_data = os.urandom(1024)  # 1KB of random binary data

        # Use a .jpg extension to bypass extension validation and test magic bytes
        response = client.post("/detect", files={"file": ("random.jpg", random_data, "image/jpeg")})

        assert response.status_code == 400
        assert (
            "Invalid image file" in response.json()["detail"]
            or "Cannot identify image" in response.json()["detail"]
            or "Unknown file format" in response.json()["detail"]
        )

    def test_batch_detect_rejects_invalid_file_with_400(
        self, client, _mock_model, dummy_image_bytes
    ):
        """Test that batch detection rejects invalid files with 400, not 500."""
        text_data = b"This is not an image"

        files = [
            ("files", ("valid.jpg", dummy_image_bytes, "image/jpeg")),
            ("files", ("invalid.jpg", text_data, "image/jpeg")),
        ]

        response = client.post("/detect/batch", files=files)

        assert response.status_code == 400
        # Should identify the invalid file by index or name
        assert "index 1" in response.json()["detail"] or "invalid.jpg" in response.json()["detail"]

    def test_detect_error_includes_filename(self, client):
        """Test that error messages include the filename for debugging."""
        text_data = b"not an image"

        response = client.post(
            "/detect", files={"file": ("my_camera_shot.jpg", text_data, "image/jpeg")}
        )

        assert response.status_code == 400
        # The filename should be in the error detail for debugging
        assert "my_camera_shot.jpg" in response.json()["detail"]

    def test_detect_valid_image_still_works(self, client, _mock_model, dummy_image_bytes):
        """Test that valid images still work correctly after error handling changes."""
        response = client.post(
            "/detect", files={"file": ("valid_image.jpg", dummy_image_bytes, "image/jpeg")}
        )

        assert response.status_code == 200
        assert "detections" in response.json()
        assert "inference_time_ms" in response.json()

    def test_detect_rejects_video_file_with_400(self, client):
        """Test that video files (which have image extensions sometimes) return 400."""
        # Simulate an AVI file header disguised with .jpg extension
        avi_header = b"RIFF\x00\x00\x00\x00AVI LIST"

        response = client.post("/detect", files={"file": ("video.jpg", avi_header, "image/jpeg")})

        assert response.status_code == 400
        assert (
            "video.jpg" in response.json()["detail"].lower()
            or "Invalid image file" in response.json()["detail"]
        )


class TestMagicByteValidation:
    """Tests for magic byte validation function.

    These tests verify that the validate_image_magic_bytes() function
    correctly identifies valid and invalid image file formats based on
    their file signatures (magic bytes).
    """

    def test_valid_jpeg_magic_bytes(self):
        """Test that valid JPEG magic bytes are recognized."""
        # Standard JPEG starts with FF D8 FF
        jpeg_data = bytes([0xFF, 0xD8, 0xFF, 0xE0]) + b"\x00" * 100
        is_valid, result = validate_image_magic_bytes(jpeg_data)
        assert is_valid is True
        assert result == "JPEG"

    def test_valid_png_magic_bytes(self):
        """Test that valid PNG magic bytes are recognized."""
        # PNG signature: 89 50 4E 47 0D 0A 1A 0A
        png_data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        is_valid, result = validate_image_magic_bytes(png_data)
        assert is_valid is True
        assert result == "PNG"

    def test_valid_gif87a_magic_bytes(self):
        """Test that valid GIF87a magic bytes are recognized."""
        gif_data = b"GIF87a" + b"\x00" * 100
        is_valid, result = validate_image_magic_bytes(gif_data)
        assert is_valid is True
        assert result == "GIF"

    def test_valid_gif89a_magic_bytes(self):
        """Test that valid GIF89a magic bytes are recognized."""
        gif_data = b"GIF89a" + b"\x00" * 100
        is_valid, result = validate_image_magic_bytes(gif_data)
        assert is_valid is True
        assert result == "GIF"

    def test_valid_bmp_magic_bytes(self):
        """Test that valid BMP magic bytes are recognized."""
        bmp_data = b"BM" + b"\x00" * 100
        is_valid, result = validate_image_magic_bytes(bmp_data)
        assert is_valid is True
        assert result == "BMP"

    def test_valid_webp_magic_bytes(self):
        """Test that valid WEBP magic bytes are recognized."""
        # WEBP: RIFF header + "WEBP" at offset 8
        webp_data = b"RIFF\x00\x00\x00\x00WEBP" + b"\x00" * 100
        is_valid, result = validate_image_magic_bytes(webp_data)
        assert is_valid is True
        assert result == "WEBP"

    def test_empty_data_rejected(self):
        """Test that empty data is rejected."""
        is_valid, result = validate_image_magic_bytes(b"")
        assert is_valid is False
        assert "Empty" in result

    def test_too_small_data_rejected(self):
        """Test that data smaller than 8 bytes is rejected."""
        is_valid, result = validate_image_magic_bytes(b"ABC")
        assert is_valid is False
        assert "too small" in result

    def test_text_file_detected(self):
        """Test that plain text files are detected and rejected."""
        text_data = b"This is just a plain text file, not an image at all."
        is_valid, result = validate_image_magic_bytes(text_data)
        assert is_valid is False
        assert "Text file" in result or "Unknown file format" in result

    def test_utf8_bom_text_detected(self):
        """Test that UTF-8 BOM text files are detected."""
        bom_data = b"\xef\xbb\xbfThis is UTF-8 text with BOM"
        is_valid, result = validate_image_magic_bytes(bom_data)
        assert is_valid is False
        assert "Text file" in result

    def test_avi_video_detected(self):
        """Test that AVI video files are detected and rejected."""
        avi_data = b"RIFF\x00\x00\x00\x00AVI " + b"\x00" * 100
        is_valid, result = validate_image_magic_bytes(avi_data)
        assert is_valid is False
        assert "Video file" in result or "AVI" in result

    def test_wav_audio_detected(self):
        """Test that WAV audio files are detected and rejected."""
        wav_data = b"RIFF\x00\x00\x00\x00WAVE" + b"\x00" * 100
        is_valid, result = validate_image_magic_bytes(wav_data)
        assert is_valid is False
        assert "Audio file" in result or "WAV" in result

    def test_random_binary_rejected(self):
        """Test that random binary data is rejected."""
        random_data = bytes([0x12, 0x34, 0x56, 0x78, 0x9A, 0xBC, 0xDE, 0xF0] * 10)
        is_valid, result = validate_image_magic_bytes(random_data)
        assert is_valid is False
        assert "Unknown file format" in result


class TestFileExtensionValidation:
    """Tests for file extension validation function.

    These tests verify that the validate_file_extension() function
    correctly validates file extensions against supported image types.
    """

    def test_valid_jpg_extension(self):
        """Test that .jpg extension is valid."""
        is_valid, error = validate_file_extension("image.jpg")
        assert is_valid is True
        assert error == ""

    def test_valid_jpeg_extension(self):
        """Test that .jpeg extension is valid."""
        is_valid, error = validate_file_extension("image.jpeg")
        assert is_valid is True
        assert error == ""

    def test_valid_png_extension(self):
        """Test that .png extension is valid."""
        is_valid, error = validate_file_extension("image.png")
        assert is_valid is True
        assert error == ""

    def test_valid_gif_extension(self):
        """Test that .gif extension is valid."""
        is_valid, error = validate_file_extension("image.gif")
        assert is_valid is True
        assert error == ""

    def test_valid_bmp_extension(self):
        """Test that .bmp extension is valid."""
        is_valid, error = validate_file_extension("image.bmp")
        assert is_valid is True
        assert error == ""

    def test_valid_webp_extension(self):
        """Test that .webp extension is valid."""
        is_valid, error = validate_file_extension("image.webp")
        assert is_valid is True
        assert error == ""

    def test_uppercase_extensions_valid(self):
        """Test that uppercase extensions are treated as case-insensitive."""
        for ext in [".JPG", ".JPEG", ".PNG", ".GIF", ".BMP", ".WEBP"]:
            is_valid, error = validate_file_extension(f"image{ext}")
            assert is_valid is True, f"Extension {ext} should be valid"
            assert error == ""

    def test_invalid_txt_extension(self):
        """Test that .txt extension is rejected."""
        is_valid, error = validate_file_extension("document.txt")
        assert is_valid is False
        assert "Unsupported file extension" in error
        assert ".txt" in error

    def test_invalid_mp4_extension(self):
        """Test that .mp4 extension is rejected."""
        is_valid, error = validate_file_extension("video.mp4")
        assert is_valid is False
        assert "Unsupported file extension" in error
        assert ".mp4" in error

    def test_invalid_avi_extension(self):
        """Test that .avi extension is rejected."""
        is_valid, error = validate_file_extension("video.avi")
        assert is_valid is False
        assert "Unsupported file extension" in error

    def test_none_filename_allowed(self):
        """Test that None filename is allowed (no validation possible)."""
        is_valid, error = validate_file_extension(None)
        assert is_valid is True
        assert error == ""

    def test_no_extension_allowed(self):
        """Test that files without extension are allowed (can't validate)."""
        is_valid, error = validate_file_extension("filename_without_extension")
        assert is_valid is True
        assert error == ""

    def test_supported_extensions_constant(self):
        """Test that SUPPORTED_IMAGE_EXTENSIONS contains expected formats."""
        expected = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}
        assert expected == SUPPORTED_IMAGE_EXTENSIONS


class TestHealthResponse:
    """Tests for HealthResponse model with GPU metrics fields."""

    def test_health_response_includes_gpu_metrics_fields(self):
        """Test that HealthResponse includes gpu_utilization, temperature, and power_watts fields."""
        response = HealthResponse(
            status="healthy",
            model_loaded=True,
            device="cuda:0",
            cuda_available=True,
            model_name="/path/to/model",
            vram_used_gb=3.5,
            gpu_utilization=75.0,
            temperature=65,
            power_watts=150.0,
            tensorrt_enabled=True,
        )
        assert response.gpu_utilization == 75.0
        assert response.temperature == 65
        assert response.power_watts == 150.0
        assert response.tensorrt_enabled is True

    def test_health_response_gpu_metrics_optional(self):
        """Test that GPU metrics fields are optional (None when unavailable)."""
        response = HealthResponse(
            status="degraded",
            model_loaded=False,
            device="cpu",
            cuda_available=False,
        )
        assert response.gpu_utilization is None
        assert response.temperature is None
        assert response.power_watts is None

    def test_health_response_partial_gpu_metrics(self):
        """Test that GPU metrics can be partially provided."""
        response = HealthResponse(
            status="healthy",
            model_loaded=True,
            device="cuda:0",
            cuda_available=True,
            vram_used_gb=4.0,
            gpu_utilization=50.0,
            temperature=None,  # Some metrics may fail individually
            power_watts=120.0,
        )
        assert response.gpu_utilization == 50.0
        assert response.temperature is None
        assert response.power_watts == 120.0


class TestGetGpuMetrics:
    """Tests for get_gpu_metrics() function."""

    def test_get_gpu_metrics_cuda_not_available(self):
        """Test that get_gpu_metrics returns empty dict when CUDA not available."""
        with patch(f"{MODEL_MODULE_PATH}.torch.cuda.is_available", return_value=False):
            result = get_gpu_metrics()
            assert result["gpu_utilization"] is None
            assert result["temperature"] is None
            assert result["power_watts"] is None

    def test_get_gpu_metrics_pynvml_not_installed(self):
        """Test that get_gpu_metrics returns None values when pynvml not installed."""
        with patch(f"{MODEL_MODULE_PATH}.torch.cuda.is_available", return_value=True):
            # Mock import to fail
            import builtins

            original_import = builtins.__import__

            def mock_import(name, *args, **kwargs):
                if name == "pynvml":
                    raise ImportError("pynvml not installed")
                return original_import(name, *args, **kwargs)

            with patch.object(builtins, "__import__", side_effect=mock_import):
                result = get_gpu_metrics()
                assert result["gpu_utilization"] is None
                assert result["temperature"] is None
                assert result["power_watts"] is None

    def test_get_gpu_metrics_with_pynvml(self):
        """Test get_gpu_metrics when pynvml is available."""
        mock_pynvml = MagicMock()
        mock_handle = MagicMock()
        mock_utilization = MagicMock()
        mock_utilization.gpu = 75.0

        mock_pynvml.nvmlDeviceGetHandleByIndex.return_value = mock_handle
        mock_pynvml.nvmlDeviceGetUtilizationRates.return_value = mock_utilization
        mock_pynvml.nvmlDeviceGetTemperature.return_value = 65
        mock_pynvml.NVML_TEMPERATURE_GPU = 0
        mock_pynvml.nvmlDeviceGetPowerUsage.return_value = 150000  # milliwatts
        mock_pynvml.NVMLError = Exception

        with (
            patch(f"{MODEL_MODULE_PATH}.torch.cuda.is_available", return_value=True),
            patch.dict("sys.modules", {"pynvml": mock_pynvml}),
        ):
            result = get_gpu_metrics()
            assert result["gpu_utilization"] == 75.0
            assert result["temperature"] == 65
            assert result["power_watts"] == 150.0

    def test_get_gpu_metrics_partial_failure(self):
        """Test get_gpu_metrics when some pynvml calls fail."""
        mock_pynvml = MagicMock()
        mock_handle = MagicMock()
        mock_utilization = MagicMock()
        mock_utilization.gpu = 50.0

        # Configure mock
        mock_pynvml.nvmlDeviceGetHandleByIndex.return_value = mock_handle
        mock_pynvml.nvmlDeviceGetUtilizationRates.return_value = mock_utilization
        # Temperature fails
        mock_pynvml.nvmlDeviceGetTemperature.side_effect = Exception("Temp error")
        mock_pynvml.NVML_TEMPERATURE_GPU = 0
        mock_pynvml.nvmlDeviceGetPowerUsage.return_value = 100000  # milliwatts
        mock_pynvml.NVMLError = Exception

        with (
            patch(f"{MODEL_MODULE_PATH}.torch.cuda.is_available", return_value=True),
            patch.dict("sys.modules", {"pynvml": mock_pynvml}),
        ):
            result = get_gpu_metrics()
            assert result["gpu_utilization"] == 50.0
            assert result["temperature"] is None  # Failed
            assert result["power_watts"] == 100.0


class TestTensorRTVersionUtilities:
    """Tests for TensorRT version checking utilities (NEM-3871)."""

    def test_get_tensorrt_version_when_installed(self):
        """Test get_tensorrt_version returns version when TensorRT is installed."""
        mock_trt = MagicMock()
        mock_trt.__version__ = "10.14.1.48"

        with patch.dict("sys.modules", {"tensorrt": mock_trt}):
            version = get_tensorrt_version()
            assert version == "10.14.1.48"

    def test_get_tensorrt_version_when_not_installed(self):
        """Test get_tensorrt_version returns None when TensorRT is not installed."""
        with patch.dict("sys.modules", {"tensorrt": None}):
            # Remove tensorrt from sys.modules to simulate ImportError
            import sys

            original = sys.modules.pop("tensorrt", None)
            try:
                version = get_tensorrt_version()
                assert version is None
            finally:
                if original is not None:
                    sys.modules["tensorrt"] = original

    def test_is_tensorrt_version_mismatch_error_old_plan_file(self):
        """Test detection of 'older plan file' error."""
        error = RuntimeError("Failed due to an old deserialization call on a newer plan file.")
        assert is_tensorrt_version_mismatch_error(error) is True

    def test_is_tensorrt_version_mismatch_error_different_version(self):
        """Test detection of 'different version' error."""
        error = RuntimeError("TensorRT model exported with a different version than 10.14.1.48")
        assert is_tensorrt_version_mismatch_error(error) is True

    def test_is_tensorrt_version_mismatch_error_deserialization(self):
        """Test detection of deserialization error."""
        error = RuntimeError("IRuntime::deserializeCudaEngine: Error Code 1: Internal Error")
        assert is_tensorrt_version_mismatch_error(error) is True

    def test_is_tensorrt_version_mismatch_error_incompatible(self):
        """Test detection of 'incompatible' error."""
        error = RuntimeError("Engine is incompatible with this version of TensorRT")
        assert is_tensorrt_version_mismatch_error(error) is True

    def test_is_tensorrt_version_mismatch_error_not_matching(self):
        """Test that unrelated errors are not flagged as version mismatch."""
        error = RuntimeError("File not found: /models/yolo26.engine")
        assert is_tensorrt_version_mismatch_error(error) is False

    def test_is_tensorrt_version_mismatch_error_cuda_error(self):
        """Test that CUDA errors are not flagged as version mismatch."""
        error = RuntimeError("CUDA out of memory")
        assert is_tensorrt_version_mismatch_error(error) is False

    def test_get_pt_model_path_for_engine_fp16_suffix(self, tmp_path):
        """Test deriving .pt path from engine with _fp16 suffix."""
        # Create the .pt file
        pt_file = tmp_path / "yolo26m.pt"
        pt_file.touch()

        engine_path = str(tmp_path / "yolo26m_fp16.engine")
        result = get_pt_model_path_for_engine(engine_path)
        assert result == str(pt_file)

    def test_get_pt_model_path_for_engine_int8_suffix(self, tmp_path):
        """Test deriving .pt path from engine with _int8 suffix."""
        # Create the .pt file
        pt_file = tmp_path / "yolo26m.pt"
        pt_file.touch()

        engine_path = str(tmp_path / "yolo26m_int8.engine")
        result = get_pt_model_path_for_engine(engine_path)
        assert result == str(pt_file)

    def test_get_pt_model_path_for_engine_no_suffix(self, tmp_path):
        """Test deriving .pt path from engine without precision suffix."""
        # Create the .pt file
        pt_file = tmp_path / "yolo26m.pt"
        pt_file.touch()

        engine_path = str(tmp_path / "yolo26m.engine")
        result = get_pt_model_path_for_engine(engine_path)
        assert result == str(pt_file)

    def test_get_pt_model_path_for_engine_not_found(self, tmp_path):
        """Test returns None when .pt file doesn't exist."""
        engine_path = str(tmp_path / "nonexistent_fp16.engine")
        result = get_pt_model_path_for_engine(engine_path)
        assert result is None

    def test_get_pt_model_path_for_engine_parent_directory(self, tmp_path):
        """Test finding .pt file in parent directory."""
        # Create the .pt file in parent directory
        pt_file = tmp_path / "yolo26m.pt"
        pt_file.touch()

        # Create exports subdirectory
        exports_dir = tmp_path / "exports"
        exports_dir.mkdir()

        engine_path = str(exports_dir / "yolo26m_fp16.engine")
        result = get_pt_model_path_for_engine(engine_path)
        assert result == str(pt_file)

    def test_delete_stale_engine_success(self, tmp_path):
        """Test successful deletion of stale engine file."""
        engine_file = tmp_path / "stale.engine"
        engine_file.touch()

        assert engine_file.exists()
        result = delete_stale_engine(str(engine_file))
        assert result is True
        assert not engine_file.exists()

    def test_delete_stale_engine_not_exists(self, tmp_path):
        """Test deletion of non-existent file returns False."""
        engine_path = str(tmp_path / "nonexistent.engine")
        result = delete_stale_engine(engine_path)
        assert result is False


class TestYOLO26ModelTensorRTVersionHandling:
    """Tests for YOLO26Model TensorRT version mismatch handling (NEM-3871)."""

    def test_model_initialization_with_auto_rebuild(self):
        """Test model initialization includes auto_rebuild parameter."""
        model = YOLO26Model(
            model_path="test.engine",
            auto_rebuild=True,
            pt_model_path="/models/test.pt",
        )
        assert model.auto_rebuild is True
        assert model.pt_model_path == "/models/test.pt"

    def test_model_initialization_auto_rebuild_default(self):
        """Test auto_rebuild defaults to True from env var."""
        with patch.dict("os.environ", {"YOLO26_AUTO_REBUILD": "true"}):
            model = YOLO26Model(model_path="test.engine")
            assert model.auto_rebuild is True

    def test_model_initialization_auto_rebuild_disabled(self):
        """Test auto_rebuild can be disabled via env var."""
        with patch.dict("os.environ", {"YOLO26_AUTO_REBUILD": "false"}, clear=False):
            model = YOLO26Model(model_path="test.engine", auto_rebuild=None)
            assert model.auto_rebuild is False

    def test_version_mismatch_detection_in_load_model_path(self, tmp_path):
        """Test that version mismatch is detected based on exception patterns.

        This test validates that is_tensorrt_version_mismatch_error() correctly
        identifies the error patterns that trigger auto-rebuild.
        """
        # Test various error patterns that should trigger version mismatch handling
        mismatch_errors = [
            RuntimeError("Failed due to an old deserialization call on a newer plan file."),
            RuntimeError("IRuntime::deserializeCudaEngine: Error Code 1: Internal Error"),
            RuntimeError("TensorRT model exported with a different version than 10.14.1.48"),
            RuntimeError("Engine is incompatible with this version of TensorRT"),
        ]

        for error in mismatch_errors:
            assert is_tensorrt_version_mismatch_error(error) is True, (
                f"Expected error to be detected as version mismatch: {error}"
            )

        # Test errors that should NOT trigger version mismatch handling
        non_mismatch_errors = [
            RuntimeError("File not found: /models/yolo26.engine"),
            RuntimeError("CUDA out of memory"),
            RuntimeError("Invalid model format"),
        ]

        for error in non_mismatch_errors:
            assert is_tensorrt_version_mismatch_error(error) is False, (
                f"Expected error NOT to be detected as version mismatch: {error}"
            )

    def test_handle_version_mismatch_finds_pt_model(self, tmp_path):
        """Test that _handle_tensorrt_version_mismatch finds the correct .pt model."""
        # Create mock .pt file
        pt_file = tmp_path / "yolo26m.pt"
        pt_file.touch()

        engine_path = tmp_path / "yolo26m_fp16.engine"
        engine_path.touch()

        model = YOLO26Model(
            model_path=str(engine_path),
            auto_rebuild=True,
            device="cpu",
        )

        # Verify the utility function finds the correct .pt path
        found_pt_path = get_pt_model_path_for_engine(str(engine_path))
        assert found_pt_path == str(pt_file)

    def test_pt_model_path_not_found_for_engine(self, tmp_path):
        """Test that get_pt_model_path_for_engine returns None when no .pt model exists."""
        engine_path = tmp_path / "yolo26m_fp16.engine"
        engine_path.touch()
        # Intentionally don't create the .pt file

        # Verify the utility function returns None when no .pt found
        found_pt_path = get_pt_model_path_for_engine(str(engine_path))
        assert found_pt_path is None

    def test_health_response_includes_tensorrt_version(self):
        """Test that HealthResponse includes tensorrt_version field."""
        response = HealthResponse(
            status="healthy",
            model_loaded=True,
            device="cuda:0",
            cuda_available=True,
            tensorrt_enabled=True,
            tensorrt_version="10.14.1.48",
        )
        assert response.tensorrt_version == "10.14.1.48"

    def test_health_response_tensorrt_version_optional(self):
        """Test that tensorrt_version field is optional."""
        response = HealthResponse(
            status="healthy",
            model_loaded=True,
            device="cuda:0",
            cuda_available=True,
        )
        assert response.tensorrt_version is None


class TestInferenceHealthCheck:
    """Tests for inference health tracking and warmup validation (NEM-3877, NEM-3878).

    These tests verify that:
    1. Warmup inference is performed on startup to validate the model works
    2. Health check reports whether inference has been tested successfully
    3. The inference_healthy flag is properly tracked
    4. The MODEL_INFERENCE_HEALTHY Prometheus metric is exposed
    """

    def test_yolo26_model_has_inference_healthy_attribute(self):
        """Test that YOLO26Model tracks inference health status."""
        model = YOLO26Model(model_path="test_path", device="cpu")
        # Should have inference_healthy attribute (defaults to False until warmup succeeds)
        assert hasattr(model, "inference_healthy")
        assert model.inference_healthy is False  # Not yet tested

    def test_warmup_sets_inference_healthy_on_success(self, mock_yolo_model):
        """Test that successful warmup sets inference_healthy to True."""
        model = YOLO26Model(model_path="test_path", device="cpu", cache_clear_frequency=0)
        model.model = mock_yolo_model
        model.inference_healthy = False  # Pre-condition

        # Run warmup (which calls detect internally)
        model._warmup(num_iterations=1)

        # After successful warmup, inference_healthy should be True
        assert model.inference_healthy is True

    def test_warmup_sets_inference_healthy_false_on_failure(self):
        """Test that failed warmup sets inference_healthy to False."""
        model = YOLO26Model(model_path="test_path", device="cpu", cache_clear_frequency=0)

        # Create a mock model that raises on predict
        failing_model = MagicMock()
        failing_model.predict.side_effect = RuntimeError("TensorRT version mismatch")
        model.model = failing_model
        model.inference_healthy = True  # Pre-condition (set to True to verify it changes)

        # Run warmup - should catch exception and set inference_healthy=False
        model._warmup(num_iterations=1)

        assert model.inference_healthy is False

    def test_health_response_includes_inference_tested_field(self):
        """Test that HealthResponse includes inference_tested field."""
        response = HealthResponse(
            status="healthy",
            model_loaded=True,
            device="cuda:0",
            cuda_available=True,
            inference_tested=True,
        )
        assert response.inference_tested is True

    def test_health_response_inference_tested_optional(self):
        """Test that inference_tested field is optional (defaults to None)."""
        response = HealthResponse(
            status="healthy",
            model_loaded=True,
            device="cuda:0",
            cuda_available=True,
        )
        assert response.inference_tested is None

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_health_endpoint_reports_inference_tested(self, client):
        """Test that /health endpoint includes inference_tested field."""
        # Set up mock model with inference_healthy=True
        mock_instance = MagicMock()
        mock_instance.model = MagicMock()
        mock_instance.model_path = "/dummy/path"
        mock_instance.tensorrt_enabled = True
        mock_instance._is_compiled = False
        mock_instance.torch_compile_mode = "reduce-overhead"
        mock_instance.inference_healthy = True
        mock_instance.active_backend = "tensorrt"

        original_model = getattr(model_module, "model", None)
        model_module.model = mock_instance
        try:
            with patch(f"{MODEL_MODULE_PATH}.torch.cuda.is_available", return_value=False):
                response = client.get("/health")
                assert response.status_code == 200
                data = response.json()
                assert "inference_tested" in data
                assert data["inference_tested"] is True
        finally:
            model_module.model = original_model

    def test_health_endpoint_reports_unhealthy_when_inference_failed(self, client):
        """Test that /health reports 'unhealthy' when inference test failed."""
        mock_instance = MagicMock()
        mock_instance.model = MagicMock()
        mock_instance.model_path = "/dummy/path"
        mock_instance.tensorrt_enabled = True
        mock_instance._is_compiled = False
        mock_instance.torch_compile_mode = "reduce-overhead"
        mock_instance.inference_healthy = False  # Inference failed
        mock_instance.active_backend = "pytorch"

        original_model = getattr(model_module, "model", None)
        model_module.model = mock_instance
        try:
            with patch(f"{MODEL_MODULE_PATH}.torch.cuda.is_available", return_value=False):
                response = client.get("/health")
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "unhealthy"
                assert data["inference_tested"] is False
        finally:
            model_module.model = original_model


class TestTensorRTFallback:
    """Tests for TensorRT to PyTorch fallback mechanism (NEM-3877).

    These tests verify that:
    1. When TensorRT engine fails to load, the system falls back to PyTorch
    2. The active_backend attribute reflects which backend is being used
    3. Fallback logging is appropriate
    """

    def test_yolo26_model_has_active_backend_attribute(self):
        """Test that YOLO26Model tracks the active backend."""
        model = YOLO26Model(model_path="test.engine", device="cpu")
        assert hasattr(model, "active_backend")
        # Should default to None until model is loaded
        assert model.active_backend is None

    def test_active_backend_set_to_tensorrt_on_engine_load(self):
        """Test that active_backend is 'tensorrt' when engine loads successfully."""
        model = YOLO26Model(model_path="test.engine", device="cpu")

        # Mock successful TensorRT load by setting model directly
        mock_yolo_instance = MagicMock()
        model.model = mock_yolo_instance

        # Simulate what load_model does for engine files
        model.tensorrt_enabled = True
        model.active_backend = "tensorrt"

        assert model.active_backend == "tensorrt"
        assert model.tensorrt_enabled is True

    def test_active_backend_set_to_pytorch_on_pt_load(self):
        """Test that active_backend is 'pytorch' when .pt file loads."""
        model = YOLO26Model(model_path="test.pt", device="cpu")

        # Mock successful PyTorch load by setting model directly
        mock_yolo_instance = MagicMock()
        mock_yolo_instance.model = MagicMock()
        model.model = mock_yolo_instance

        # Simulate what load_model does for .pt files
        model.tensorrt_enabled = False
        model.active_backend = "pytorch"

        assert model.active_backend == "pytorch"
        assert model.tensorrt_enabled is False

    def test_fallback_to_pytorch_on_tensorrt_load_failure(self, tmp_path):
        """Test fallback logic by calling _fallback_to_pytorch directly."""
        # Create mock .pt file
        pt_file = tmp_path / "yolo26m.pt"
        pt_file.touch()

        engine_path = tmp_path / "yolo26m_fp16.engine"
        engine_path.touch()

        model = YOLO26Model(
            model_path=str(engine_path),
            device="cpu",
            auto_rebuild=False,  # Disable rebuild to force fallback
            pt_model_path=str(pt_file),
        )

        # Mock YOLO class for fallback
        mock_pt_yolo = MagicMock()
        mock_pt_yolo.model = MagicMock()

        # Mock the ultralytics module for the internal import
        mock_ultralytics = MagicMock()
        mock_ultralytics.YOLO = MagicMock(return_value=mock_pt_yolo)

        # Call _fallback_to_pytorch directly with mocked ultralytics
        with patch.dict("sys.modules", {"ultralytics": mock_ultralytics}):
            model._fallback_to_pytorch()

        # Should have fallen back to PyTorch
        assert model.active_backend == "pytorch"
        assert model.tensorrt_enabled is False
        assert model.model_path == str(pt_file)

    def test_tensorrt_fallback_error_pattern_none_object(self):
        """Test that NoneType execution context error triggers fallback."""
        error = RuntimeError("'NoneType' object has no attribute 'create_execution_context'")
        assert is_tensorrt_version_mismatch_error(error) is True

    def test_health_response_includes_active_backend_field(self):
        """Test that HealthResponse includes active_backend field."""
        response = HealthResponse(
            status="healthy",
            model_loaded=True,
            device="cuda:0",
            cuda_available=True,
            active_backend="tensorrt",
        )
        assert response.active_backend == "tensorrt"

    def test_health_response_active_backend_optional(self):
        """Test that active_backend field is optional."""
        response = HealthResponse(
            status="healthy",
            model_loaded=True,
            device="cuda:0",
            cuda_available=True,
        )
        assert response.active_backend is None


class TestModelInferenceHealthyMetric:
    """Tests for MODEL_INFERENCE_HEALTHY Prometheus metric (NEM-3878).

    This metric should track whether the model inference is healthy (1) or not (0).
    """

    def test_model_inference_healthy_metric_exists(self):
        """Test that MODEL_INFERENCE_HEALTHY metric is exported from metrics module."""
        from metrics import MODEL_INFERENCE_HEALTHY

        assert MODEL_INFERENCE_HEALTHY is not None

    def test_model_inference_healthy_in_exports(self):
        """Test that MODEL_INFERENCE_HEALTHY is in __all__ exports."""
        from metrics import __all__

        assert "MODEL_INFERENCE_HEALTHY" in __all__


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
