"""Unit tests for YOLO26 instance segmentation support (NEM-3912).

Tests for:
- Instance segmentation model loading
- Segmentation endpoint functionality
- Mask data format and validation
- Integration with detection responses
"""

import io
import sys
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest
from PIL import Image

# Add the ai/yolo26 directory to sys.path to enable imports
_yolo26_dir = Path(__file__).parent.parent
if str(_yolo26_dir) not in sys.path:
    sys.path.insert(0, str(_yolo26_dir))

# Import test dependencies
# Import module to test (after path setup)
import model as model_module  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

MODEL_MODULE_PATH = "model"


class TestSegmentationResponse:
    """Tests for SegmentationResponse model."""

    def test_segmentation_response_import(self):
        """Test that SegmentationResponse can be imported."""
        from model import SegmentationResponse

        assert SegmentationResponse is not None

    def test_segmentation_detection_import(self):
        """Test that SegmentationDetection can be imported."""
        from model import SegmentationDetection

        assert SegmentationDetection is not None

    def test_segmentation_detection_creation(self):
        """Test creating a segmentation detection."""
        from model import BoundingBox, SegmentationDetection

        detection = SegmentationDetection(
            class_name="person",
            confidence=0.95,
            bbox=BoundingBox(x=10, y=20, width=100, height=150),
            mask_rle={"counts": [10, 20, 30], "size": [480, 640]},
            mask_polygon=[[10, 20, 30, 40, 50, 60]],
        )
        assert detection.class_name == "person"
        assert detection.confidence == 0.95
        assert detection.bbox.x == 10
        assert detection.mask_rle is not None
        assert detection.mask_polygon is not None

    def test_segmentation_response_creation(self):
        """Test creating a segmentation response."""
        from model import BoundingBox, SegmentationDetection, SegmentationResponse

        response = SegmentationResponse(
            detections=[
                SegmentationDetection(
                    class_name="person",
                    confidence=0.95,
                    bbox=BoundingBox(x=10, y=20, width=100, height=150),
                    mask_rle={"counts": [10, 20, 30], "size": [480, 640]},
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

    def test_empty_segmentation_detections(self):
        """Test response with no segmentation detections."""
        from model import SegmentationResponse

        response = SegmentationResponse(
            detections=[], inference_time_ms=30.0, image_width=640, image_height=480
        )
        assert len(response.detections) == 0


class TestYOLO26ModelSegmentation:
    """Tests for YOLO26Model segmentation capabilities."""

    def test_segment_method_exists(self):
        """Test that YOLO26Model has a segment method."""
        from model import YOLO26Model

        model = YOLO26Model(model_path="test_path", device="cpu")
        assert hasattr(model, "segment")

    def test_segment_raises_if_model_not_loaded(self):
        """Test that segment() raises RuntimeError if model not loaded."""
        from model import YOLO26Model

        model = YOLO26Model(model_path="test_path")
        test_image = Image.new("RGB", (640, 480), color=(128, 128, 128))

        with pytest.raises(RuntimeError, match="Model not loaded"):
            model.segment(test_image)

    def test_segment_with_mock_model(self, mock_yolo_segmentation_model):
        """Test segment method with mocked YOLO model."""
        from model import YOLO26Model

        model = YOLO26Model(model_path="test_path", device="cpu", cache_clear_frequency=0)
        model.model = mock_yolo_segmentation_model

        test_image = Image.new("RGB", (640, 480), color=(128, 128, 128))

        detections, inference_time = model.segment(test_image)

        # Verify results
        assert len(detections) == 1
        assert detections[0]["class"] == "person"
        assert detections[0]["confidence"] == 0.95
        assert detections[0]["bbox"]["x"] == 100
        assert "mask_rle" in detections[0]
        assert "mask_polygon" in detections[0]
        assert inference_time > 0

    def test_segment_converts_rgba_to_rgb(self, mock_yolo_segmentation_model):
        """Test that RGBA images are converted to RGB for segmentation."""
        from model import YOLO26Model

        model = YOLO26Model(model_path="test_path", device="cpu", cache_clear_frequency=0)
        model.model = mock_yolo_segmentation_model

        # Create RGBA image
        rgba_image = Image.new("RGBA", (640, 480), color=(128, 128, 128, 255))

        detections, _ = model.segment(rgba_image)

        # Should not raise and should return results
        assert isinstance(detections, list)
        # Verify predict was called
        mock_yolo_segmentation_model.predict.assert_called_once()

    def test_segment_filters_non_security_classes(self):
        """Test that non-security classes are filtered out in segmentation."""
        from model import YOLO26Model

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

        # Mock masks (even though filtered out)
        mock_masks = MagicMock()
        mock_masks.__len__.return_value = 1
        mock_mask_data = MagicMock()
        mock_mask_data.cpu.return_value.numpy.return_value = np.zeros((480, 640), dtype=np.uint8)
        mock_masks.data = [mock_mask_data]
        mock_masks.xy = [np.array([[10, 20], [30, 40], [50, 60]])]
        mock_result.masks = mock_masks

        mock_model.predict.return_value = [mock_result]
        model.model = mock_model

        test_image = Image.new("RGB", (640, 480), color=(128, 128, 128))
        detections, _ = model.segment(test_image)

        # Should filter out non-security class
        assert len(detections) == 0

    def test_segment_with_empty_results(self, mock_empty_yolo_segmentation_model):
        """Test segment with no detections."""
        from model import YOLO26Model

        model = YOLO26Model(model_path="test_path", device="cpu", cache_clear_frequency=0)
        model.model = mock_empty_yolo_segmentation_model

        test_image = Image.new("RGB", (640, 480), color=(128, 128, 128))
        detections, inference_time = model.segment(test_image)

        assert len(detections) == 0
        assert inference_time > 0


class TestSegmentationEndpoint:
    """Tests for the /segment FastAPI endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from model import app

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
    def mock_model(self):
        """Mock the global model instance for segmentation."""
        mock_instance = MagicMock()
        mock_instance.model = MagicMock()
        mock_instance.segment.return_value = (
            [
                {
                    "class": "person",
                    "confidence": 0.95,
                    "bbox": {"x": 100, "y": 150, "width": 200, "height": 400},
                    "mask_rle": {"counts": [10, 20, 30], "size": [480, 640]},
                    "mask_polygon": [[10, 20, 30, 40, 50, 60]],
                }
            ],
            45.2,
        )
        # Set required attributes for health check
        mock_instance._is_compiled = False
        mock_instance.torch_compile_mode = "reduce-overhead"
        mock_instance.inference_healthy = True
        mock_instance.active_backend = "tensorrt"

        original_model = getattr(model_module, "model", None)
        model_module.model = mock_instance
        yield mock_instance
        model_module.model = original_model

    def test_segment_endpoint_exists(self, client, mock_model, dummy_image_bytes):
        """Test that /segment endpoint exists and accepts POST requests."""
        response = client.post(
            "/segment", files={"file": ("test.jpg", dummy_image_bytes, "image/jpeg")}
        )

        assert response.status_code == 200

    def test_segment_endpoint_returns_masks(self, client, mock_model, dummy_image_bytes):
        """Test that /segment endpoint returns mask data."""
        response = client.post(
            "/segment", files={"file": ("test.jpg", dummy_image_bytes, "image/jpeg")}
        )

        assert response.status_code == 200
        data = response.json()
        assert "detections" in data
        assert len(data["detections"]) == 1
        assert "mask_rle" in data["detections"][0]
        assert "mask_polygon" in data["detections"][0]

    def test_segment_endpoint_model_not_loaded(self, client, dummy_image_bytes):
        """Test segmentation when model is not loaded."""
        original_model = model_module.model
        model_module.model = None
        try:
            response = client.post(
                "/segment", files={"file": ("test.jpg", dummy_image_bytes, "image/jpeg")}
            )
            assert response.status_code == 503
        finally:
            model_module.model = original_model

    def test_segment_endpoint_with_base64(self, client, mock_model, dummy_image_bytes):
        """Test segmentation endpoint with base64 image."""
        import base64

        image_base64 = base64.b64encode(dummy_image_bytes).decode("utf-8")
        response = client.post("/segment", json={"image_base64": image_base64})

        assert response.status_code in [200, 400, 422]

    def test_segment_endpoint_no_input(self, client, mock_model):
        """Test segmentation endpoint with no input."""
        response = client.post("/segment")
        assert response.status_code == 400


class TestMaskEncoding:
    """Tests for mask encoding utilities."""

    def test_encode_mask_to_rle(self):
        """Test run-length encoding of segmentation mask."""
        from model import encode_mask_to_rle

        # Create a simple binary mask
        mask = np.zeros((100, 100), dtype=np.uint8)
        mask[20:40, 30:60] = 1  # Rectangle of 1s

        rle = encode_mask_to_rle(mask)

        assert "counts" in rle
        assert "size" in rle
        assert rle["size"] == [100, 100]
        assert len(rle["counts"]) > 0

    def test_decode_rle_to_mask(self):
        """Test decoding RLE back to mask.

        Note: RLE encoding uses column-major (Fortran) order for COCO compatibility.
        The round-trip encode->decode should perfectly reconstruct the original mask.
        """
        from model import decode_rle_to_mask, encode_mask_to_rle

        # Create original mask with a simple rectangular region
        original_mask = np.zeros((100, 100), dtype=np.uint8)
        original_mask[20:40, 30:60] = 1

        # Encode and decode
        rle = encode_mask_to_rle(original_mask)
        decoded_mask = decode_rle_to_mask(rle)

        # Should match original shape
        assert decoded_mask.shape == original_mask.shape

        # RLE encoding/decoding should preserve the non-zero count
        assert decoded_mask.sum() == original_mask.sum()

        # Verify the dimensions are recorded correctly
        assert rle["size"] == [100, 100]

        # For COCO-style RLE, the mask should round-trip correctly
        # Note: The mask is flattened in column-major order, so the
        # exact pixel positions should be preserved through the round-trip
        # Compare the flattened versions to verify consistency
        original_flat = original_mask.flatten(order="F")
        decoded_flat = decoded_mask.flatten(order="F")
        assert np.array_equal(original_flat, decoded_flat)

    def test_mask_to_polygon(self):
        """Test converting binary mask to polygon contours."""
        from model import mask_to_polygon

        # Create a simple binary mask with a rectangle
        mask = np.zeros((100, 100), dtype=np.uint8)
        mask[20:40, 30:60] = 1

        polygons = mask_to_polygon(mask)

        assert len(polygons) >= 1
        # Each polygon should have at least 4 points (for a rectangle)
        assert len(polygons[0]) >= 8  # 4 points * 2 coordinates

    def test_empty_mask_encoding(self):
        """Test encoding an empty mask."""
        from model import encode_mask_to_rle

        empty_mask = np.zeros((100, 100), dtype=np.uint8)
        rle = encode_mask_to_rle(empty_mask)

        assert "counts" in rle
        assert "size" in rle
        # Empty mask should have specific encoding
        assert rle["size"] == [100, 100]


# Fixtures for segmentation tests


@pytest.fixture
def mock_yolo_segmentation_model():
    """Create a mock YOLO model with segmentation support for testing."""
    mock_model = MagicMock()

    # Mock predict method to return results with masks
    mock_result = MagicMock()
    mock_boxes = MagicMock()

    # Mock a single detection (person) with segmentation
    mock_box = MagicMock()
    mock_box.cls.item.return_value = 0  # person class
    mock_box.conf.item.return_value = 0.95
    mock_xyxy_tensor = MagicMock()
    mock_xyxy_tensor.tolist.return_value = [100.0, 150.0, 300.0, 550.0]
    mock_box.xyxy = [mock_xyxy_tensor]

    mock_boxes.__len__.return_value = 1
    mock_boxes.__iter__.return_value = iter([mock_box])

    mock_result.boxes = mock_boxes

    # Mock masks
    mock_masks = MagicMock()
    mock_masks.__len__.return_value = 1

    # Create a mock mask array
    mock_mask_data = np.zeros((480, 640), dtype=np.uint8)
    mock_mask_data[150:550, 100:300] = 1  # Person-sized mask

    mock_masks_data = MagicMock()
    mock_masks_data.__getitem__.return_value.cpu.return_value.numpy.return_value = mock_mask_data
    mock_masks.data = mock_masks_data

    # Mock polygon coordinates
    mock_masks.xy = [np.array([[100, 150], [300, 150], [300, 550], [100, 550]])]

    mock_result.masks = mock_masks

    mock_model.predict.return_value = [mock_result]

    return mock_model


@pytest.fixture
def mock_empty_yolo_segmentation_model():
    """Create a mock YOLO segmentation model that returns no detections."""
    mock_model = MagicMock()

    mock_result = MagicMock()
    mock_boxes = MagicMock()
    mock_boxes.__len__.return_value = 0
    mock_boxes.__iter__.return_value = iter([])

    mock_result.boxes = mock_boxes
    mock_result.masks = None

    mock_model.predict.return_value = [mock_result]

    return mock_model


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
