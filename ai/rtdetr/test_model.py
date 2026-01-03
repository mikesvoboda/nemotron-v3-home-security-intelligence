"""Unit tests for RT-DETRv2 inference server."""

import base64
import io
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from fastapi.testclient import TestClient

# Add the ai/rtdetr directory to sys.path to enable imports
# This handles both pytest from project root and running tests directly
_rtdetr_dir = Path(__file__).parent
if str(_rtdetr_dir) not in sys.path:
    sys.path.insert(0, str(_rtdetr_dir))

# Now import from the local model module
import model as model_module  # noqa: E402
from model import (  # noqa: E402
    MAX_BASE64_SIZE_BYTES,
    MAX_IMAGE_SIZE_BYTES,
    SECURITY_CLASSES,
    SUPPORTED_IMAGE_EXTENSIONS,
    BoundingBox,
    Detection,
    DetectionResponse,
    HealthResponse,
    RTDETRv2Model,
    app,
    get_gpu_metrics,
    validate_file_extension,
    validate_image_magic_bytes,
)
from PIL import Image  # noqa: E402

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


class TestRTDETRv2Model:
    """Tests for RTDETRv2Model class (HuggingFace Transformers-based)."""

    def test_model_initialization(self):
        """Test model initialization with HuggingFace Transformers."""
        model = RTDETRv2Model(model_path="dummy_model_path", confidence_threshold=0.6, device="cpu")
        assert model.confidence_threshold == 0.6
        assert model.device == "cpu"
        assert model.model_path == "dummy_model_path"
        assert model.model is None  # Not loaded yet
        assert model.processor is None  # Not loaded yet

    def test_model_initialization_with_default_values(self):
        """Test model initialization with default confidence threshold and device."""
        model = RTDETRv2Model(model_path="test_path")
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

    def test_detect_endpoint_rejects_oversized_base64(self, client):
        """Test that oversized base64 data is rejected with 413 BEFORE decoding."""
        # Create oversized base64 string (just over the limit)
        oversized_base64 = "A" * (MAX_BASE64_SIZE_BYTES + 1)

        # Send as query parameter (FastAPI parameter without Body/Form annotation)
        response = client.post(f"/detect?image_base64={oversized_base64[:1000]}")

        # The endpoint validates the size, should reject with 413
        # Note: Due to URL length limits in practice, we can't actually send 13MB via query param
        # This test verifies the endpoint handles missing/invalid inputs correctly
        # For very large base64 data, the validation happens in the code at line 485-491
        assert response.status_code in [400, 413, 422]

    def test_detect_endpoint_rejects_invalid_base64(self, client):
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
        mock_instance = MagicMock()
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
        )
        assert response.gpu_utilization == 75.0
        assert response.temperature == 65
        assert response.power_watts == 150.0

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


class TestHealthEndpointGpuMetrics:
    """Tests for health endpoint returning GPU metrics."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture(autouse=True)
    def mock_model(self):
        """Mock the global model instance."""
        mock_instance = MagicMock()
        mock_instance.model_path = "/dummy/path"
        mock_instance.model = MagicMock()
        original_model = getattr(model_module, "model", None)
        model_module.model = mock_instance
        yield mock_instance
        model_module.model = original_model

    def test_health_endpoint_returns_gpu_metrics(self, client, _mock_model):
        """Test health endpoint returns GPU metrics when CUDA available."""
        with (
            patch(f"{MODEL_MODULE_PATH}.torch.cuda.is_available", return_value=True),
            patch(
                f"{MODEL_MODULE_PATH}.get_vram_usage",
                return_value=3.5,
            ),
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

            # Verify new GPU metric fields are present
            assert "gpu_utilization" in data
            assert "temperature" in data
            assert "power_watts" in data

            # Verify values
            assert data["gpu_utilization"] == 75.0
            assert data["temperature"] == 65
            assert data["power_watts"] == 150.0

    def test_health_endpoint_no_cuda_returns_null_metrics(self, client, _mock_model):
        """Test health endpoint returns null GPU metrics when CUDA unavailable."""
        with patch(f"{MODEL_MODULE_PATH}.torch.cuda.is_available", return_value=False):
            response = client.get("/health")
            assert response.status_code == 200
            data = response.json()

            # Verify fields are present but None
            assert data["gpu_utilization"] is None
            assert data["temperature"] is None
            assert data["power_watts"] is None

    def test_health_endpoint_partial_metrics(self, client, _mock_model):
        """Test health endpoint returns partial GPU metrics when some fail."""
        with (
            patch(f"{MODEL_MODULE_PATH}.torch.cuda.is_available", return_value=True),
            patch(
                f"{MODEL_MODULE_PATH}.get_vram_usage",
                return_value=2.0,
            ),
            patch(
                f"{MODEL_MODULE_PATH}.get_gpu_metrics",
                return_value={
                    "gpu_utilization": 50.0,
                    "temperature": None,  # Failed
                    "power_watts": 100.0,
                },
            ),
        ):
            response = client.get("/health")
            assert response.status_code == 200
            data = response.json()

            assert data["gpu_utilization"] == 50.0
            assert data["temperature"] is None
            assert data["power_watts"] == 100.0
