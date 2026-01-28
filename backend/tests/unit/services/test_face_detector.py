"""Unit tests for face detector service."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from backend.services.face_detector import (
    HEAD_REGION_RATIO,
    FaceDetection,
    PersonDetection,
    _convert_crop_bbox_to_original,
    _crop_bbox_with_padding,
    _get_head_region,
    _run_face_detection_sync,
    detect_faces,
    is_person_class,
)

# Fixtures


@pytest.fixture
def temp_test_image():
    """Create a temporary test image."""
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        # Create a simple 1920x1080 RGB image
        img = Image.new("RGB", (1920, 1080), color=(100, 150, 200))
        img.save(tmp.name, "JPEG")
        yield tmp.name
        # Cleanup
        Path(tmp.name).unlink(missing_ok=True)


@pytest.fixture
def sample_person_detections(temp_test_image):
    """Sample person detections for testing."""
    return [
        PersonDetection(
            id=1,
            bbox_x=100,
            bbox_y=100,
            bbox_width=200,
            bbox_height=500,  # Tall person bbox
            file_path=temp_test_image,
        ),
        PersonDetection(
            id=2,
            bbox_x=500,
            bbox_y=200,
            bbox_width=180,
            bbox_height=450,
            file_path=temp_test_image,
        ),
    ]


@pytest.fixture
def mock_yolo_face_model():
    """Create a mock YOLO face detection model."""
    model = MagicMock()

    # Mock prediction result
    mock_box = MagicMock()
    mock_box.xyxyn = [MagicMock()]
    mock_box.xyxyn[0].tolist.return_value = [0.2, 0.2, 0.8, 0.8]  # normalized bbox
    mock_box.conf = [MagicMock()]
    mock_box.conf[0] = 0.89

    mock_result = MagicMock()
    mock_result.boxes = [mock_box]

    model.predict.return_value = [mock_result]
    return model


def test_get_head_region_basic():
    """Test basic head region extraction."""
    person_bbox = (100, 200, 200, 500)  # x, y, width, height

    head = _get_head_region(person_bbox)

    # x and width should be unchanged
    assert head[0] == 100
    assert head[2] == 200
    # y should be unchanged
    assert head[1] == 200
    # height should be 40% of original
    assert head[3] == 200  # 500 * 0.4 = 200


def test_get_head_region_custom_ratio():
    """Test head region with custom ratio."""
    person_bbox = (100, 200, 200, 500)

    head = _get_head_region(person_bbox, head_ratio=0.3)

    assert head[3] == 150  # 500 * 0.3 = 150


def test_get_head_region_full_height():
    """Test head region with full height ratio."""
    person_bbox = (100, 200, 200, 500)

    head = _get_head_region(person_bbox, head_ratio=1.0)

    assert head[3] == 500


def test_get_head_region_preserves_xy():
    """Test that head region preserves original x and y."""
    person_bbox = (50, 100, 300, 600)

    head = _get_head_region(person_bbox)

    assert head[0] == 50
    assert head[1] == 100


def test_face_crop_bbox_with_padding_basic():
    """Test basic bbox cropping with padding for face detector."""
    image = Image.new("RGB", (1000, 800), color=(255, 0, 0))
    bbox = (100, 100, 200, 200)  # x, y, width, height
    padding = 0.2

    cropped = _crop_bbox_with_padding(image, bbox, padding)

    # With 20% padding on 200x200: 40px each side
    # Expected: 280x280 (200 + 2*40)
    assert cropped.size[0] == 280
    assert cropped.size[1] == 280


def test_crop_bbox_with_padding_clamps_to_bounds():
    """Test cropping clamps to image boundaries."""
    image = Image.new("RGB", (300, 300), color=(255, 0, 0))
    bbox = (10, 10, 100, 100)  # Near top-left corner
    padding = 0.5  # 50% padding would exceed bounds

    cropped = _crop_bbox_with_padding(image, bbox, padding)

    # Should be clamped to image bounds
    assert cropped.size[0] <= 300
    assert cropped.size[1] <= 300


def test_crop_bbox_with_padding_zero():
    """Test cropping with zero padding."""
    image = Image.new("RGB", (1000, 800), color=(255, 0, 0))
    bbox = (100, 100, 200, 150)

    cropped = _crop_bbox_with_padding(image, bbox, padding=0.0)

    assert cropped.size == (200, 150)


def test_face_convert_crop_bbox_to_original():
    """Test bbox coordinate conversion for face detector."""
    crop_bbox_norm = [0.25, 0.25, 0.75, 0.75]
    original_bbox = (100, 100, 200, 200)
    crop_size = (280, 280)
    image_size = (1000, 800)
    padding = 0.2

    result = _convert_crop_bbox_to_original(
        crop_bbox_norm, original_bbox, crop_size, image_size, padding
    )

    assert len(result) == 4
    assert all(isinstance(v, float) for v in result)
    # x1 < x2 and y1 < y2
    assert result[0] < result[2]
    assert result[1] < result[3]


def test_convert_crop_bbox_clamps_to_bounds():
    """Test converted bbox is clamped to image bounds."""
    crop_bbox_norm = [0.0, 0.0, 1.0, 1.0]
    original_bbox = (900, 700, 200, 200)  # Near edge
    crop_size = (280, 280)
    image_size = (1000, 800)
    padding = 0.2

    result = _convert_crop_bbox_to_original(
        crop_bbox_norm, original_bbox, crop_size, image_size, padding
    )

    assert result[0] >= 0
    assert result[1] >= 0
    assert result[2] <= 1000
    assert result[3] <= 800


def test_run_face_detection_sync_with_detection(mock_yolo_face_model):
    """Test synchronous face detection."""
    image = Image.new("RGB", (200, 200), color=(100, 100, 100))

    results = _run_face_detection_sync(mock_yolo_face_model, image, confidence_threshold=0.3)

    assert len(results) == 1
    bbox_norm, conf = results[0]
    assert bbox_norm == [0.2, 0.2, 0.8, 0.8]
    assert conf == 0.89


def test_run_face_detection_sync_no_faces():
    """Test detection with no faces found."""
    model = MagicMock()
    mock_result = MagicMock()
    mock_result.boxes = []
    model.predict.return_value = [mock_result]

    image = Image.new("RGB", (200, 200), color=(0, 0, 0))

    results = _run_face_detection_sync(model, image, confidence_threshold=0.3)

    assert results == []


def test_run_face_detection_sync_handles_exception():
    """Test exception handling in sync detection."""
    model = MagicMock()
    model.predict.side_effect = RuntimeError("Model error")

    image = Image.new("RGB", (200, 200), color=(100, 100, 100))

    results = _run_face_detection_sync(model, image, confidence_threshold=0.3)

    assert results == []


@pytest.mark.asyncio
async def test_detect_faces_success(sample_person_detections, mock_yolo_face_model):
    """Test successful face detection."""
    faces = await detect_faces(
        model=mock_yolo_face_model,
        person_detections=sample_person_detections,
        confidence_threshold=0.3,
    )

    # Should have 2 faces (one per person)
    assert len(faces) == 2
    assert all(isinstance(f, FaceDetection) for f in faces)
    assert faces[0].person_detection_id == 1
    assert faces[1].person_detection_id == 2
    assert all(f.confidence == 0.89 for f in faces)


@pytest.mark.asyncio
async def test_detect_faces_empty_detections():
    """Test with empty person detections."""
    mock_model = MagicMock()

    faces = await detect_faces(
        model=mock_model,
        person_detections=[],
    )

    assert faces == []
    mock_model.predict.assert_not_called()


@pytest.mark.asyncio
async def test_detect_faces_no_model():
    """Test with no model provided."""
    detections = [
        PersonDetection(
            id=1,
            bbox_x=100,
            bbox_y=100,
            bbox_width=200,
            bbox_height=500,
            file_path="/fake/path.jpg",
        )
    ]

    faces = await detect_faces(
        model=None,
        person_detections=detections,
    )

    assert faces == []


@pytest.mark.asyncio
async def test_detect_faces_missing_image():
    """Test handling of missing image file."""
    detections = [
        PersonDetection(
            id=1,
            bbox_x=100,
            bbox_y=100,
            bbox_width=200,
            bbox_height=500,
            file_path="/nonexistent/image.jpg",
        )
    ]
    mock_model = MagicMock()

    faces = await detect_faces(
        model=mock_model,
        person_detections=detections,
    )

    assert faces == []


@pytest.mark.asyncio
async def test_detect_faces_with_cached_images(temp_test_image, mock_yolo_face_model):
    """Test face detection with pre-loaded image cache."""
    detections = [
        PersonDetection(
            id=1,
            bbox_x=100,
            bbox_y=100,
            bbox_width=200,
            bbox_height=500,
            file_path=temp_test_image,
        )
    ]

    # Pre-load image
    cached_image = Image.open(temp_test_image).convert("RGB")
    images = {temp_test_image: cached_image}

    faces = await detect_faces(
        model=mock_yolo_face_model,
        person_detections=detections,
        images=images,
    )

    assert len(faces) == 1


@pytest.mark.asyncio
async def test_detect_faces_handles_inference_exception(temp_test_image):
    """Test exception handling during inference."""
    detections = [
        PersonDetection(
            id=1,
            bbox_x=100,
            bbox_y=100,
            bbox_width=200,
            bbox_height=500,
            file_path=temp_test_image,
        )
    ]

    mock_model = MagicMock()
    mock_model.predict.side_effect = RuntimeError("GPU error")

    faces = await detect_faces(
        model=mock_model,
        person_detections=detections,
    )

    # Should return empty, not raise
    assert faces == []


@pytest.mark.asyncio
async def test_detect_faces_multiple_faces_per_person(temp_test_image):
    """Test detection of multiple faces in single person region."""
    detections = [
        PersonDetection(
            id=1,
            bbox_x=100,
            bbox_y=100,
            bbox_width=400,
            bbox_height=600,
            file_path=temp_test_image,
        )
    ]

    # Mock model that returns 2 faces
    mock_model = MagicMock()
    mock_box1 = MagicMock()
    mock_box1.xyxyn = [MagicMock()]
    mock_box1.xyxyn[0].tolist.return_value = [0.1, 0.2, 0.4, 0.6]
    mock_box1.conf = [0.92]

    mock_box2 = MagicMock()
    mock_box2.xyxyn = [MagicMock()]
    mock_box2.xyxyn[0].tolist.return_value = [0.6, 0.2, 0.9, 0.6]
    mock_box2.conf = [0.85]

    mock_result = MagicMock()
    mock_result.boxes = [mock_box1, mock_box2]
    mock_model.predict.return_value = [mock_result]

    faces = await detect_faces(
        model=mock_model,
        person_detections=detections,
    )

    assert len(faces) == 2
    assert faces[0].confidence == 0.92
    assert faces[1].confidence == 0.85


@pytest.mark.asyncio
async def test_detect_faces_custom_head_ratio(temp_test_image, mock_yolo_face_model):
    """Test face detection with custom head ratio."""
    detections = [
        PersonDetection(
            id=1,
            bbox_x=100,
            bbox_y=100,
            bbox_width=200,
            bbox_height=500,
            file_path=temp_test_image,
        )
    ]

    faces = await detect_faces(
        model=mock_yolo_face_model,
        person_detections=detections,
        head_ratio=0.5,  # Use 50% of person bbox for head
    )

    assert len(faces) == 1


@pytest.mark.asyncio
async def test_detect_faces_custom_padding(temp_test_image, mock_yolo_face_model):
    """Test face detection with custom padding."""
    detections = [
        PersonDetection(
            id=1,
            bbox_x=100,
            bbox_y=100,
            bbox_width=200,
            bbox_height=500,
            file_path=temp_test_image,
        )
    ]

    faces = await detect_faces(
        model=mock_yolo_face_model,
        person_detections=detections,
        padding=0.3,  # 30% padding
    )

    assert len(faces) == 1


def test_is_person_class_person():
    """Test person class is recognized."""
    assert is_person_class("person") is True
    assert is_person_class("Person") is True
    assert is_person_class("PERSON") is True


def test_is_person_class_non_person():
    """Test non-person classes are rejected."""
    assert is_person_class("car") is False
    assert is_person_class("dog") is False
    assert is_person_class("bicycle") is False
    assert is_person_class("people") is False  # Note: only "person" matches


def test_face_detection_creation():
    """Test FaceDetection dataclass creation."""
    face = FaceDetection(
        bbox=(100.0, 150.0, 200.0, 250.0),
        confidence=0.92,
        person_detection_id=42,
    )

    assert face.bbox == (100.0, 150.0, 200.0, 250.0)
    assert face.confidence == 0.92
    assert face.person_detection_id == 42


def test_face_detection_default_id():
    """Test FaceDetection with default person_detection_id."""
    face = FaceDetection(
        bbox=(100.0, 150.0, 200.0, 250.0),
        confidence=0.92,
    )

    assert face.person_detection_id is None


def test_person_detection_creation():
    """Test PersonDetection dataclass creation."""
    detection = PersonDetection(
        id=1,
        bbox_x=100,
        bbox_y=200,
        bbox_width=180,
        bbox_height=450,
        file_path="/path/to/image.jpg",
    )

    assert detection.id == 1
    assert detection.bbox_x == 100
    assert detection.bbox_y == 200
    assert detection.bbox_width == 180
    assert detection.bbox_height == 450
    assert detection.file_path == "/path/to/image.jpg"


def test_person_detection_default_id():
    """Test PersonDetection with default id."""
    detection = PersonDetection(
        bbox_x=100,
        bbox_y=200,
        bbox_width=180,
        bbox_height=450,
        file_path="/path/to/image.jpg",
    )

    assert detection.id is None


def test_head_region_ratio_constant():
    """Test HEAD_REGION_RATIO has expected value."""
    assert HEAD_REGION_RATIO == 0.4


@pytest.mark.asyncio
async def test_detect_faces_uses_thread_pool(temp_test_image, mock_yolo_face_model):
    """Test that inference runs in thread pool."""
    detections = [
        PersonDetection(
            id=1,
            bbox_x=100,
            bbox_y=100,
            bbox_width=200,
            bbox_height=500,
            file_path=temp_test_image,
        )
    ]

    with patch("asyncio.to_thread") as mock_to_thread:
        mock_to_thread.return_value = [([0.2, 0.2, 0.8, 0.8], 0.89)]

        faces = await detect_faces(
            model=mock_yolo_face_model,
            person_detections=detections,
        )

        mock_to_thread.assert_called_once()
        assert len(faces) == 1


# =============================================================================
# Metrics Tests (NEM-4143)
# =============================================================================


@pytest.mark.asyncio
async def test_detect_faces_records_metrics(temp_test_image, mock_yolo_face_model):
    """Test that face detection records Prometheus metrics."""
    detections = [
        PersonDetection(
            id=1,
            bbox_x=100,
            bbox_y=100,
            bbox_width=200,
            bbox_height=500,
            file_path=temp_test_image,
        )
    ]

    with (
        patch("backend.services.face_detector.record_face_detection") as mock_record_detection,
        patch(
            "backend.services.face_detector.observe_face_embedding_duration"
        ) as mock_observe_duration,
        patch(
            "backend.services.face_detector.observe_face_recognition_confidence"
        ) as mock_observe_confidence,
    ):
        faces = await detect_faces(
            model=mock_yolo_face_model,
            person_detections=detections,
            camera_id="front_door",
        )

        assert len(faces) == 1

        # Verify face detection metric was recorded
        mock_record_detection.assert_called_once_with("front_door", "unknown")

        # Verify embedding duration metric was recorded
        mock_observe_duration.assert_called_once()
        call_args = mock_observe_duration.call_args
        assert call_args[0][0] == "front_door"
        assert isinstance(call_args[0][1], float)
        assert call_args[0][1] >= 0  # Duration should be non-negative

        # Verify confidence metric was recorded
        mock_observe_confidence.assert_called_once_with("front_door", 0.89)


@pytest.mark.asyncio
async def test_detect_faces_metrics_with_multiple_faces(temp_test_image):
    """Test that metrics are recorded for each detected face."""
    detections = [
        PersonDetection(
            id=1,
            bbox_x=100,
            bbox_y=100,
            bbox_width=400,
            bbox_height=600,
            file_path=temp_test_image,
        )
    ]

    # Mock model that returns 2 faces
    mock_model = MagicMock()
    mock_box1 = MagicMock()
    mock_box1.xyxyn = [MagicMock()]
    mock_box1.xyxyn[0].tolist.return_value = [0.1, 0.2, 0.4, 0.6]
    mock_box1.conf = [0.92]

    mock_box2 = MagicMock()
    mock_box2.xyxyn = [MagicMock()]
    mock_box2.xyxyn[0].tolist.return_value = [0.6, 0.2, 0.9, 0.6]
    mock_box2.conf = [0.85]

    mock_result = MagicMock()
    mock_result.boxes = [mock_box1, mock_box2]
    mock_model.predict.return_value = [mock_result]

    with (
        patch("backend.services.face_detector.record_face_detection") as mock_record_detection,
        patch(
            "backend.services.face_detector.observe_face_embedding_duration"
        ) as mock_observe_duration,
        patch(
            "backend.services.face_detector.observe_face_recognition_confidence"
        ) as mock_observe_confidence,
    ):
        faces = await detect_faces(
            model=mock_model,
            person_detections=detections,
            camera_id="back_yard",
        )

        assert len(faces) == 2

        # Each face should record detection and confidence metrics
        assert mock_record_detection.call_count == 2
        assert mock_observe_confidence.call_count == 2

        # Duration is recorded once per person detection processed
        mock_observe_duration.assert_called_once()

        # Verify confidence values
        confidence_calls = mock_observe_confidence.call_args_list
        assert confidence_calls[0][0] == ("back_yard", 0.92)
        assert confidence_calls[1][0] == ("back_yard", 0.85)


@pytest.mark.asyncio
async def test_detect_faces_metrics_default_camera_id(temp_test_image, mock_yolo_face_model):
    """Test that 'unknown' camera_id is used when not provided."""
    detections = [
        PersonDetection(
            id=1,
            bbox_x=100,
            bbox_y=100,
            bbox_width=200,
            bbox_height=500,
            file_path=temp_test_image,
        )
    ]

    with (
        patch("backend.services.face_detector.record_face_detection") as mock_record_detection,
        patch("backend.services.face_detector.observe_face_embedding_duration"),
        patch("backend.services.face_detector.observe_face_recognition_confidence"),
    ):
        faces = await detect_faces(
            model=mock_yolo_face_model,
            person_detections=detections,
            # camera_id not provided
        )

        assert len(faces) == 1

        # Verify "unknown" is used as default camera_id
        mock_record_detection.assert_called_once_with("unknown", "unknown")


@pytest.mark.asyncio
async def test_detect_faces_no_metrics_on_empty_detections():
    """Test that no metrics are recorded when no person detections provided."""
    mock_model = MagicMock()

    with (
        patch("backend.services.face_detector.record_face_detection") as mock_record_detection,
        patch(
            "backend.services.face_detector.observe_face_embedding_duration"
        ) as mock_observe_duration,
        patch(
            "backend.services.face_detector.observe_face_recognition_confidence"
        ) as mock_observe_confidence,
    ):
        faces = await detect_faces(
            model=mock_model,
            person_detections=[],
            camera_id="test_camera",
        )

        assert faces == []

        # No metrics should be recorded
        mock_record_detection.assert_not_called()
        mock_observe_duration.assert_not_called()
        mock_observe_confidence.assert_not_called()


@pytest.mark.asyncio
async def test_detect_faces_no_metrics_on_no_faces_found(temp_test_image):
    """Test that duration metric is still recorded even when no faces found."""
    detections = [
        PersonDetection(
            id=1,
            bbox_x=100,
            bbox_y=100,
            bbox_width=200,
            bbox_height=500,
            file_path=temp_test_image,
        )
    ]

    # Mock model that returns no faces
    mock_model = MagicMock()
    mock_result = MagicMock()
    mock_result.boxes = []
    mock_model.predict.return_value = [mock_result]

    with (
        patch("backend.services.face_detector.record_face_detection") as mock_record_detection,
        patch(
            "backend.services.face_detector.observe_face_embedding_duration"
        ) as mock_observe_duration,
        patch(
            "backend.services.face_detector.observe_face_recognition_confidence"
        ) as mock_observe_confidence,
    ):
        faces = await detect_faces(
            model=mock_model,
            person_detections=detections,
            camera_id="garage",
        )

        assert faces == []

        # Duration metric should still be recorded (inference ran, just found no faces)
        mock_observe_duration.assert_called_once()
        assert mock_observe_duration.call_args[0][0] == "garage"

        # No face detection or confidence metrics (no faces found)
        mock_record_detection.assert_not_called()
        mock_observe_confidence.assert_not_called()
