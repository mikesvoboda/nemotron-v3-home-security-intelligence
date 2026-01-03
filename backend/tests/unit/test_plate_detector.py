"""Unit tests for license plate detector service."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from backend.services.plate_detector import (
    VEHICLE_CLASSES,
    PlateDetection,
    VehicleDetection,
    _convert_crop_bbox_to_original,
    _crop_bbox_with_padding,
    _run_plate_detection_sync,
    detect_plates,
    is_vehicle_class,
)

# Fixtures


@pytest.fixture
def temp_test_image():
    """Create a temporary test image."""
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        # Create a simple 1920x1080 RGB image (typical security camera resolution)
        img = Image.new("RGB", (1920, 1080), color=(100, 150, 200))
        img.save(tmp.name, "JPEG")
        yield tmp.name
        # Cleanup
        Path(tmp.name).unlink(missing_ok=True)


@pytest.fixture
def sample_vehicle_detections(temp_test_image):
    """Sample vehicle detections for testing."""
    return [
        VehicleDetection(
            id=1,
            bbox_x=100,
            bbox_y=200,
            bbox_width=400,
            bbox_height=300,
            file_path=temp_test_image,
        ),
        VehicleDetection(
            id=2,
            bbox_x=800,
            bbox_y=300,
            bbox_width=350,
            bbox_height=250,
            file_path=temp_test_image,
        ),
    ]


@pytest.fixture
def mock_yolo_model():
    """Create a mock YOLO model."""
    model = MagicMock()

    # Mock prediction result
    mock_box = MagicMock()
    mock_box.xyxyn = [MagicMock()]
    mock_box.xyxyn[0].tolist.return_value = [0.2, 0.3, 0.8, 0.7]  # normalized bbox
    mock_box.conf = [MagicMock()]
    mock_box.conf[0] = 0.92

    mock_result = MagicMock()
    mock_result.boxes = [mock_box]

    model.predict.return_value = [mock_result]
    return model


def test_plate_crop_bbox_with_padding_basic():
    """Test basic bbox cropping with padding for plate detector."""
    image = Image.new("RGB", (1000, 800), color=(255, 0, 0))
    bbox = (100, 100, 200, 150)  # x, y, width, height
    padding = 0.1

    cropped = _crop_bbox_with_padding(image, bbox, padding)

    # With 10% padding on a 200x150 box: 20px horizontal, 15px vertical
    # Expected crop: (80, 85) to (320, 265) = 240x180
    assert cropped.size[0] == 240  # width with padding
    assert cropped.size[1] == 180  # height with padding


def test_crop_bbox_with_padding_clamps_to_image_bounds():
    """Test that cropping clamps to image boundaries."""
    image = Image.new("RGB", (500, 400), color=(255, 0, 0))
    # Bbox near edge - padding would go out of bounds
    bbox = (10, 10, 100, 80)
    padding = 0.2

    cropped = _crop_bbox_with_padding(image, bbox, padding)

    # Should not exceed image bounds
    assert cropped.size[0] <= 500
    assert cropped.size[1] <= 400


def test_crop_bbox_with_padding_zero_padding():
    """Test cropping with zero padding."""
    image = Image.new("RGB", (1000, 800), color=(255, 0, 0))
    bbox = (100, 100, 200, 150)

    cropped = _crop_bbox_with_padding(image, bbox, padding=0.0)

    assert cropped.size == (200, 150)


def test_plate_convert_crop_bbox_to_original():
    """Test bbox coordinate conversion from crop to original image for plates."""
    # Normalized bbox in crop space
    crop_bbox_norm = [0.25, 0.25, 0.75, 0.75]
    # Original vehicle bbox
    original_bbox = (100, 100, 200, 200)
    # Crop size after padding
    crop_size = (240, 240)
    # Original image size
    image_size = (1000, 800)
    padding = 0.1

    result = _convert_crop_bbox_to_original(
        crop_bbox_norm, original_bbox, crop_size, image_size, padding
    )

    # Result should be (x1, y1, x2, y2) in original coordinates
    assert len(result) == 4
    assert all(isinstance(v, float) for v in result)
    # x1 < x2 and y1 < y2
    assert result[0] < result[2]
    assert result[1] < result[3]


def test_convert_crop_bbox_clamps_to_image_bounds():
    """Test that converted bbox is clamped to image bounds."""
    crop_bbox_norm = [0.0, 0.0, 1.0, 1.0]  # Full crop region
    original_bbox = (950, 750, 100, 100)  # Near image edge
    crop_size = (120, 120)
    image_size = (1000, 800)
    padding = 0.1

    result = _convert_crop_bbox_to_original(
        crop_bbox_norm, original_bbox, crop_size, image_size, padding
    )

    # Should be clamped to image bounds
    assert result[0] >= 0
    assert result[1] >= 0
    assert result[2] <= 1000
    assert result[3] <= 800


def test_run_plate_detection_sync_with_detections(mock_yolo_model):
    """Test synchronous plate detection returns correct format."""
    image = Image.new("RGB", (400, 300), color=(100, 100, 100))

    results = _run_plate_detection_sync(mock_yolo_model, image, confidence_threshold=0.25)

    assert len(results) == 1
    bbox_norm, conf = results[0]
    assert bbox_norm == [0.2, 0.3, 0.8, 0.7]
    assert conf == 0.92


def test_run_plate_detection_sync_no_detections():
    """Test synchronous detection with no plates found."""
    model = MagicMock()
    mock_result = MagicMock()
    mock_result.boxes = []
    model.predict.return_value = [mock_result]

    image = Image.new("RGB", (400, 300), color=(100, 100, 100))

    results = _run_plate_detection_sync(model, image, confidence_threshold=0.25)

    assert results == []


def test_run_plate_detection_sync_handles_exception():
    """Test that exceptions are handled gracefully."""
    model = MagicMock()
    model.predict.side_effect = RuntimeError("Model inference failed")

    image = Image.new("RGB", (400, 300), color=(100, 100, 100))

    results = _run_plate_detection_sync(model, image, confidence_threshold=0.25)

    assert results == []


@pytest.mark.asyncio
async def test_detect_plates_success(sample_vehicle_detections, mock_yolo_model):
    """Test successful plate detection."""
    plates = await detect_plates(
        model=mock_yolo_model,
        vehicle_detections=sample_vehicle_detections,
        confidence_threshold=0.25,
    )

    # Should have 2 plates (one per vehicle)
    assert len(plates) == 2
    assert all(isinstance(p, PlateDetection) for p in plates)
    assert plates[0].vehicle_detection_id == 1
    assert plates[1].vehicle_detection_id == 2
    assert all(p.confidence == 0.92 for p in plates)


@pytest.mark.asyncio
async def test_detect_plates_empty_detections():
    """Test with empty vehicle detections list."""
    mock_model = MagicMock()

    plates = await detect_plates(
        model=mock_model,
        vehicle_detections=[],
    )

    assert plates == []
    mock_model.predict.assert_not_called()


@pytest.mark.asyncio
async def test_detect_plates_no_model():
    """Test with no model provided."""
    detections = [
        VehicleDetection(
            id=1,
            bbox_x=100,
            bbox_y=100,
            bbox_width=200,
            bbox_height=150,
            file_path="/fake/path.jpg",
        )
    ]

    plates = await detect_plates(
        model=None,
        vehicle_detections=detections,
    )

    assert plates == []


@pytest.mark.asyncio
async def test_detect_plates_missing_image():
    """Test handling of missing image file."""
    detections = [
        VehicleDetection(
            id=1,
            bbox_x=100,
            bbox_y=100,
            bbox_width=200,
            bbox_height=150,
            file_path="/nonexistent/image.jpg",
        )
    ]
    mock_model = MagicMock()

    plates = await detect_plates(
        model=mock_model,
        vehicle_detections=detections,
    )

    assert plates == []


@pytest.mark.asyncio
async def test_detect_plates_with_cached_images(temp_test_image, mock_yolo_model):
    """Test plate detection with pre-loaded image cache."""
    detections = [
        VehicleDetection(
            id=1,
            bbox_x=100,
            bbox_y=100,
            bbox_width=200,
            bbox_height=150,
            file_path=temp_test_image,
        )
    ]

    # Pre-load image
    cached_image = Image.open(temp_test_image).convert("RGB")
    images = {temp_test_image: cached_image}

    plates = await detect_plates(
        model=mock_yolo_model,
        vehicle_detections=detections,
        images=images,
    )

    assert len(plates) == 1


@pytest.mark.asyncio
async def test_detect_plates_handles_inference_exception(temp_test_image):
    """Test that inference exceptions are handled gracefully."""
    detections = [
        VehicleDetection(
            id=1,
            bbox_x=100,
            bbox_y=100,
            bbox_width=200,
            bbox_height=150,
            file_path=temp_test_image,
        )
    ]

    mock_model = MagicMock()
    mock_model.predict.side_effect = RuntimeError("GPU out of memory")

    plates = await detect_plates(
        model=mock_model,
        vehicle_detections=detections,
    )

    # Should return empty list, not raise
    assert plates == []


@pytest.mark.asyncio
async def test_detect_plates_multiple_plates_per_vehicle(temp_test_image):
    """Test detection of multiple plates in single vehicle region."""
    detections = [
        VehicleDetection(
            id=1,
            bbox_x=100,
            bbox_y=100,
            bbox_width=400,
            bbox_height=300,
            file_path=temp_test_image,
        )
    ]

    # Mock model that returns 2 plates
    mock_model = MagicMock()
    mock_box1 = MagicMock()
    mock_box1.xyxyn = [MagicMock()]
    mock_box1.xyxyn[0].tolist.return_value = [0.1, 0.4, 0.4, 0.6]
    mock_box1.conf = [0.95]

    mock_box2 = MagicMock()
    mock_box2.xyxyn = [MagicMock()]
    mock_box2.xyxyn[0].tolist.return_value = [0.6, 0.4, 0.9, 0.6]
    mock_box2.conf = [0.88]

    mock_result = MagicMock()
    mock_result.boxes = [mock_box1, mock_box2]
    mock_model.predict.return_value = [mock_result]

    plates = await detect_plates(
        model=mock_model,
        vehicle_detections=detections,
    )

    assert len(plates) == 2
    assert plates[0].confidence == 0.95
    assert plates[1].confidence == 0.88


def test_is_vehicle_class_car():
    """Test car is recognized as vehicle."""
    assert is_vehicle_class("car") is True
    assert is_vehicle_class("Car") is True
    assert is_vehicle_class("CAR") is True


def test_is_vehicle_class_truck():
    """Test truck is recognized as vehicle."""
    assert is_vehicle_class("truck") is True


def test_is_vehicle_class_bus():
    """Test bus is recognized as vehicle."""
    assert is_vehicle_class("bus") is True


def test_is_vehicle_class_motorcycle():
    """Test motorcycle is recognized as vehicle."""
    assert is_vehicle_class("motorcycle") is True


def test_is_vehicle_class_non_vehicle():
    """Test non-vehicle classes are rejected."""
    assert is_vehicle_class("person") is False
    assert is_vehicle_class("dog") is False
    assert is_vehicle_class("bicycle") is False


def test_vehicle_classes_constant():
    """Test VEHICLE_CLASSES contains expected classes."""
    assert "car" in VEHICLE_CLASSES
    assert "truck" in VEHICLE_CLASSES
    assert "bus" in VEHICLE_CLASSES
    assert "motorcycle" in VEHICLE_CLASSES


def test_plate_detection_creation():
    """Test PlateDetection dataclass creation."""
    plate = PlateDetection(
        bbox=(100.0, 200.0, 300.0, 250.0),
        confidence=0.95,
        vehicle_detection_id=42,
    )

    assert plate.bbox == (100.0, 200.0, 300.0, 250.0)
    assert plate.confidence == 0.95
    assert plate.vehicle_detection_id == 42


def test_plate_detection_default_id():
    """Test PlateDetection with default vehicle_detection_id."""
    plate = PlateDetection(
        bbox=(100.0, 200.0, 300.0, 250.0),
        confidence=0.95,
    )

    assert plate.vehicle_detection_id is None


def test_vehicle_detection_creation():
    """Test VehicleDetection dataclass creation."""
    detection = VehicleDetection(
        id=1,
        bbox_x=100,
        bbox_y=200,
        bbox_width=300,
        bbox_height=200,
        file_path="/path/to/image.jpg",
    )

    assert detection.id == 1
    assert detection.bbox_x == 100
    assert detection.bbox_y == 200
    assert detection.bbox_width == 300
    assert detection.bbox_height == 200
    assert detection.file_path == "/path/to/image.jpg"


def test_vehicle_detection_default_id():
    """Test VehicleDetection with default id."""
    detection = VehicleDetection(
        bbox_x=100,
        bbox_y=200,
        bbox_width=300,
        bbox_height=200,
        file_path="/path/to/image.jpg",
    )

    assert detection.id is None


@pytest.mark.asyncio
async def test_detect_plates_uses_thread_pool(temp_test_image, mock_yolo_model):
    """Test that inference runs in thread pool."""
    detections = [
        VehicleDetection(
            id=1,
            bbox_x=100,
            bbox_y=100,
            bbox_width=200,
            bbox_height=150,
            file_path=temp_test_image,
        )
    ]

    with patch("asyncio.to_thread") as mock_to_thread:
        # Make to_thread return expected result
        mock_to_thread.return_value = [([0.2, 0.3, 0.8, 0.7], 0.92)]

        plates = await detect_plates(
            model=mock_yolo_model,
            vehicle_detections=detections,
        )

        # Verify to_thread was called
        mock_to_thread.assert_called_once()
        assert len(plates) == 1
