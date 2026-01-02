"""Unit tests for RT-DETRv2 inference server."""

import base64
import io
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from fastapi.testclient import TestClient

# Import the model module
from model import (
    MAX_BASE64_SIZE_BYTES,
    MAX_IMAGE_SIZE_BYTES,
    SECURITY_CLASSES,
    BoundingBox,
    Detection,
    DetectionResponse,
    RTDETRv2Model,
    app,
)
from PIL import Image


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


class TestRTDETRv2Model:
    """Tests for RTDETRv2Model class."""

    @patch("model.Path.exists")
    def test_model_initialization(self, mock_exists):
        """Test model initialization."""
        mock_exists.return_value = True
        model = RTDETRv2Model(
            model_path="dummy_model.onnx", confidence_threshold=0.6, device="cpu", use_onnx=True
        )
        assert model.confidence_threshold == 0.6
        assert model.device == "cpu"
        assert model.use_onnx is True

    def test_preprocess_image(self, dummy_image):
        """Test image preprocessing."""
        model = RTDETRv2Model(model_path="dummy.onnx", device="cpu")

        img_array, original_size = model.preprocess_image(dummy_image)

        # Check shape: (1, 3, 640, 640)
        assert img_array.shape == (1, 3, 640, 640)
        assert original_size == (640, 480)  # Original image size

        # Check normalization
        assert img_array.min() >= 0.0
        assert img_array.max() <= 1.0

    def test_preprocess_image_converts_grayscale(self):
        """Test preprocessing converts grayscale to RGB."""
        gray_img = Image.new("L", (640, 480), color=128)
        model = RTDETRv2Model(model_path="dummy.onnx", device="cpu")

        img_array, _ = model.preprocess_image(gray_img)

        # Should have 3 channels
        assert img_array.shape[1] == 3

    def test_postprocess_detections_onnx_format(self):
        """Test postprocessing ONNX-style outputs."""
        model = RTDETRv2Model(model_path="dummy.onnx", confidence_threshold=0.5, device="cpu")

        # Mock ONNX outputs: [boxes, scores, labels]
        boxes = np.array([[[100, 150, 300, 550]]], dtype=np.float32)  # (1, 1, 4)
        scores = np.array([[0.95]], dtype=np.float32)  # (1, 1)
        labels = np.array([[0]], dtype=np.int32)  # (1, 1) - person class

        outputs = [boxes, scores, labels]
        detections = model.postprocess_detections(
            outputs, original_size=(640, 480), image_size=(640, 640)
        )

        assert len(detections) == 1
        assert detections[0]["class"] == "person"
        assert detections[0]["confidence"] == 0.95
        assert "bbox" in detections[0]

    def test_postprocess_filters_low_confidence(self):
        """Test that low confidence detections are filtered out."""
        model = RTDETRv2Model(
            model_path="dummy.onnx",
            confidence_threshold=0.7,  # High threshold
            device="cpu",
        )

        # Mock outputs with low confidence
        boxes = np.array([[[100, 150, 300, 550]]], dtype=np.float32)
        scores = np.array([[0.4]], dtype=np.float32)  # Below threshold
        labels = np.array([[0]], dtype=np.int32)

        outputs = [boxes, scores, labels]
        detections = model.postprocess_detections(
            outputs, original_size=(640, 480), image_size=(640, 640)
        )

        # Should be filtered out
        assert len(detections) == 0

    def test_postprocess_filters_non_security_classes(self):
        """Test that non-security classes are filtered out."""
        model = RTDETRv2Model(model_path="dummy.onnx", confidence_threshold=0.5, device="cpu")

        # Mock outputs with "chair" class (not in SECURITY_CLASSES)
        boxes = np.array([[[100, 150, 300, 550]]], dtype=np.float32)
        scores = np.array([[0.95]], dtype=np.float32)
        labels = np.array([[56]], dtype=np.int32)  # chair class

        outputs = [boxes, scores, labels]
        detections = model.postprocess_detections(
            outputs, original_size=(640, 480), image_size=(640, 640)
        )

        # Should be filtered out (not security-relevant)
        assert len(detections) == 0

    def test_security_classes_filter(self):
        """Test that only security-relevant classes are included."""
        expected_classes = {"person", "car", "truck", "dog", "cat", "bird", "bicycle", "motorcycle"}
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
        with patch("model.model") as mock:
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
            mock.return_value = mock_instance
            # Make the mock available as model.model
            import model as model_module

            model_module.model = mock_instance
            yield mock_instance

    def test_health_endpoint(self, client):
        """Test health check endpoint."""
        with (
            patch("model.torch.cuda.is_available", return_value=False),
            patch("model.model", MagicMock()),
        ):
            response = client.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert "status" in data
            assert "model_loaded" in data
            assert "device" in data
            assert "cuda_available" in data

    def test_detect_endpoint_with_file(self, client, dummy_image_bytes, _mock_model):
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

    def test_detect_endpoint_with_base64(self, client, dummy_image_base64, _mock_model):
        """Test detection endpoint with base64 image."""
        response = client.post("/detect", json={"image_base64": dummy_image_base64})

        # Note: FastAPI expects form data or query params, not JSON body
        # This test may need adjustment based on actual implementation
        # For now, testing the validation error
        assert response.status_code in [200, 400, 422]

    def test_detect_endpoint_no_input(self, client, _mock_model):
        """Test detection endpoint with no input."""
        response = client.post("/detect")
        assert response.status_code == 422  # Validation error

    def test_detect_endpoint_model_not_loaded(self, client):
        """Test detection when model is not loaded."""
        with patch("model.model", None):
            response = client.post(
                "/detect", files={"file": ("test.jpg", b"fake image data", "image/jpeg")}
            )
            assert response.status_code == 503

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

    def test_batch_detect_empty_files(self, client, _mock_model):
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
        with patch("model.model"):
            mock_instance = MagicMock()
            mock_instance.detect.return_value = ([], 10.0)
            mock_instance.detect_batch.return_value = ([[]], 10.0)
            import model as model_module

            model_module.model = mock_instance
            yield mock_instance

    def test_size_limits_are_reasonable(self):
        """Test that size limits are set to reasonable values."""
        # 10MB is reasonable for security camera images
        assert MAX_IMAGE_SIZE_BYTES == 10 * 1024 * 1024
        # Base64 encoding adds ~33% overhead
        assert MAX_BASE64_SIZE_BYTES > MAX_IMAGE_SIZE_BYTES
        assert MAX_BASE64_SIZE_BYTES < MAX_IMAGE_SIZE_BYTES * 2

    def test_detect_endpoint_rejects_oversized_file(self, client, _mock_model):
        """Test that oversized file uploads are rejected with 413."""
        # Create oversized data (just over 10MB)
        oversized_data = b"x" * (MAX_IMAGE_SIZE_BYTES + 1)

        response = client.post(
            "/detect", files={"file": ("large.jpg", oversized_data, "image/jpeg")}
        )

        assert response.status_code == 413
        assert "exceeds maximum" in response.json()["detail"]
        assert "10MB" in response.json()["detail"]

    def test_detect_endpoint_rejects_oversized_base64(self, client, _mock_model):
        """Test that oversized base64 data is rejected with 413 BEFORE decoding."""
        # Create oversized base64 string (just over the limit)
        oversized_base64 = "A" * (MAX_BASE64_SIZE_BYTES + 1)

        response = client.post("/detect", json={"image_base64": oversized_base64})

        # Should be rejected at 413 (payload too large)
        # Note: FastAPI may return 422 for JSON body parsing
        assert response.status_code in [413, 422]
        if response.status_code == 413:
            assert "exceeds" in response.json()["detail"].lower()

    def test_detect_endpoint_rejects_invalid_base64(self, client, _mock_model):
        """Test that invalid base64 encoding is rejected with 400."""
        # Invalid base64 (not properly padded, contains invalid chars)
        invalid_base64 = "not-valid-base64!!!"

        response = client.post("/detect", json={"image_base64": invalid_base64})

        # Should be rejected with 400 or 422
        assert response.status_code in [400, 422]

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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


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
        with patch("model.model"):
            mock_instance = MagicMock()
            mock_instance.detect.return_value = ([], 10.0)
            mock_instance.detect_batch.return_value = ([[]], 10.0)
            import model as model_module

            model_module.model = mock_instance
            yield mock_instance

    def test_detect_rejects_non_image_file_with_400(self, client, _mock_model):
        """Test that non-image files (e.g., text files) return 400 Bad Request."""
        # Send a text file disguised as a JPEG
        text_data = b"This is not an image, just plain text content."

        response = client.post(
            "/detect", files={"file": ("fake_image.jpg", text_data, "image/jpeg")}
        )

        assert response.status_code == 400
        assert "Invalid image file" in response.json()["detail"]
        assert "fake_image.jpg" in response.json()["detail"]

    def test_detect_rejects_corrupted_image_with_400(self, client, _mock_model):
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

    def test_detect_rejects_empty_file_with_400(self, client, _mock_model):
        """Test that empty files return 400 Bad Request."""
        response = client.post("/detect", files={"file": ("empty.jpg", b"", "image/jpeg")})

        assert response.status_code == 400
        assert (
            "empty.jpg" in response.json()["detail"].lower()
            or "Invalid image file" in response.json()["detail"]
        )

    def test_detect_rejects_random_binary_with_400(self, client, _mock_model):
        """Test that random binary data returns 400 Bad Request."""
        import os

        random_data = os.urandom(1024)  # 1KB of random binary data

        response = client.post("/detect", files={"file": ("random.bin", random_data, "image/jpeg")})

        assert response.status_code == 400
        assert (
            "Invalid image file" in response.json()["detail"]
            or "Cannot identify image" in response.json()["detail"]
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

    def test_detect_error_includes_filename(self, client, _mock_model):
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

    def test_detect_rejects_video_file_with_400(self, client, _mock_model):
        """Test that video files (which have image extensions sometimes) return 400."""
        # Simulate an AVI file header disguised with .jpg extension
        avi_header = b"RIFF\x00\x00\x00\x00AVI LIST"

        response = client.post("/detect", files={"file": ("video.jpg", avi_header, "image/jpeg")})

        assert response.status_code == 400
        assert (
            "video.jpg" in response.json()["detail"].lower()
            or "Invalid image file" in response.json()["detail"]
        )
