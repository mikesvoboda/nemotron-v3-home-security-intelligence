"""Unit tests for OCR service."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from backend.services.ocr_service import (
    PlateText,
    _crop_plate_region,
    _run_ocr_sync,
    clean_plate_text,
    read_plates,
    read_single_plate,
)
from backend.services.plate_detector import PlateDetection

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
def sample_plate_detections():
    """Sample plate detections for testing."""
    return [
        PlateDetection(
            bbox=(100.0, 200.0, 300.0, 250.0),
            confidence=0.95,
            vehicle_detection_id=1,
        ),
        PlateDetection(
            bbox=(500.0, 300.0, 700.0, 350.0),
            confidence=0.88,
            vehicle_detection_id=2,
        ),
    ]


@pytest.fixture
def mock_paddleocr():
    """Create a mock PaddleOCR model."""
    model = MagicMock()
    # Mock OCR result format: [[[box], (text, confidence)], ...]
    model.ocr.return_value = [
        [
            [[[0, 0], [100, 0], [100, 50], [0, 50]], ("ABC123", 0.95)],
        ]
    ]
    return model


def test_clean_plate_text_basic():
    """Test basic plate text cleaning."""
    assert clean_plate_text("ABC 123") == "ABC123"
    assert clean_plate_text("abc-123") == "ABC123"
    assert clean_plate_text("  ABC 123  ") == "ABC123"


def test_clean_plate_text_removes_special_chars():
    """Test removal of special characters."""
    assert clean_plate_text("ABC-123!@#") == "ABC123"
    assert clean_plate_text("A.B.C.1.2.3") == "ABC123"


def test_clean_plate_text_converts_to_uppercase():
    """Test uppercase conversion."""
    assert clean_plate_text("abc123") == "ABC123"
    assert clean_plate_text("AbC123") == "ABC123"


def test_clean_plate_text_returns_none_for_short():
    """Test returns None for text too short."""
    assert clean_plate_text("A") is None
    assert clean_plate_text("") is None
    assert clean_plate_text("   ") is None


def test_clean_plate_text_returns_none_for_empty():
    """Test returns None for empty/None input."""
    assert clean_plate_text("") is None
    assert clean_plate_text(None) is None  # type: ignore[arg-type]


def test_clean_plate_text_keeps_alphanumeric_only():
    """Test only alphanumeric characters are kept."""
    assert clean_plate_text("AB C 123") == "ABC123"
    assert clean_plate_text("7XYZ-999") == "7XYZ999"


def test_clean_plate_text_handles_unicode():
    """Test handling of unicode characters."""
    # Unicode should be stripped
    result = clean_plate_text("ABC123")
    assert result == "ABC123"


def test_crop_plate_region_basic():
    """Test basic plate region cropping."""
    image = Image.new("RGB", (1000, 800), color=(255, 0, 0))
    bbox = (100.0, 200.0, 300.0, 250.0)  # x1, y1, x2, y2

    cropped = _crop_plate_region(image, bbox, padding=0.05)

    # Should be slightly larger than the bbox due to padding
    assert cropped.size[0] > 0
    assert cropped.size[1] > 0


def test_crop_plate_region_clamps_to_bounds():
    """Test that cropping clamps to image bounds."""
    image = Image.new("RGB", (500, 400), color=(255, 0, 0))
    # Bbox near edge
    bbox = (10.0, 10.0, 100.0, 60.0)

    cropped = _crop_plate_region(image, bbox, padding=0.2)

    assert cropped.size[0] <= 500
    assert cropped.size[1] <= 400


def test_crop_plate_region_zero_padding():
    """Test cropping with zero padding."""
    image = Image.new("RGB", (1000, 800), color=(255, 0, 0))
    bbox = (100.0, 200.0, 300.0, 250.0)

    cropped = _crop_plate_region(image, bbox, padding=0.0)

    assert cropped.size == (200, 50)


def test_run_ocr_sync_success(mock_paddleocr):
    """Test successful OCR execution."""
    image = Image.new("RGB", (200, 50), color=(255, 255, 255))

    text, confidence = _run_ocr_sync(mock_paddleocr, image)

    assert text == "ABC123"
    assert confidence == 0.95


def test_run_ocr_sync_no_results():
    """Test OCR with no text found."""
    model = MagicMock()
    model.ocr.return_value = [[]]  # Empty results

    image = Image.new("RGB", (200, 50), color=(0, 0, 0))

    text, confidence = _run_ocr_sync(model, image)

    assert text is None
    assert confidence == 0.0


def test_run_ocr_sync_handles_exception():
    """Test OCR exception handling."""
    model = MagicMock()
    model.ocr.side_effect = RuntimeError("OCR failed")

    image = Image.new("RGB", (200, 50), color=(255, 255, 255))

    text, confidence = _run_ocr_sync(model, image)

    assert text is None
    assert confidence == 0.0


def test_run_ocr_sync_multiple_lines():
    """Test OCR with multiple text lines."""
    model = MagicMock()
    model.ocr.return_value = [
        [
            [[[0, 0], [100, 0], [100, 25], [0, 25]], ("ABC", 0.95)],
            [[[0, 25], [100, 25], [100, 50], [0, 50]], ("123", 0.90)],
        ]
    ]

    image = Image.new("RGB", (200, 50), color=(255, 255, 255))

    text, confidence = _run_ocr_sync(model, image)

    # Should combine text
    assert text == "ABC 123"
    # Should average confidence
    assert confidence == pytest.approx(0.925, rel=0.01)


def test_run_ocr_sync_null_result():
    """Test OCR with null result."""
    model = MagicMock()
    model.ocr.return_value = None

    image = Image.new("RGB", (200, 50), color=(255, 255, 255))

    text, confidence = _run_ocr_sync(model, image)

    assert text is None
    assert confidence == 0.0


@pytest.mark.asyncio
async def test_read_plates_success(temp_test_image, sample_plate_detections, mock_paddleocr):
    """Test successful plate text reading."""
    images = {temp_test_image: Image.open(temp_test_image).convert("RGB")}

    with patch("backend.services.ocr_service.asyncio.to_thread") as mock_to_thread:
        mock_to_thread.return_value = ("ABC 123", 0.95)

        results = await read_plates(
            ocr_model=mock_paddleocr,
            plate_detections=sample_plate_detections,
            images=images,
        )

    assert len(results) == 2
    assert all(isinstance(r, PlateText) for r in results)
    assert results[0].text == "ABC123"
    assert results[0].confidence == 0.95


@pytest.mark.asyncio
async def test_read_plates_empty_detections():
    """Test with empty plate detections."""
    mock_model = MagicMock()

    results = await read_plates(
        ocr_model=mock_model,
        plate_detections=[],
    )

    assert results == []


@pytest.mark.asyncio
async def test_read_plates_no_model():
    """Test with no OCR model."""
    detections = [
        PlateDetection(
            bbox=(100.0, 200.0, 300.0, 250.0),
            confidence=0.95,
        )
    ]

    results = await read_plates(
        ocr_model=None,
        plate_detections=detections,
    )

    assert results == []


@pytest.mark.asyncio
async def test_read_plates_low_confidence_filtered(temp_test_image, sample_plate_detections):
    """Test that low confidence results are filtered."""
    images = {temp_test_image: Image.open(temp_test_image).convert("RGB")}

    with patch("backend.services.ocr_service.asyncio.to_thread") as mock_to_thread:
        # Return low confidence
        mock_to_thread.return_value = ("ABC 123", 0.3)

        results = await read_plates(
            ocr_model=MagicMock(),
            plate_detections=sample_plate_detections,
            images=images,
            min_confidence=0.5,
        )

    # Should be filtered out due to low confidence
    assert len(results) == 0


@pytest.mark.asyncio
async def test_read_plates_short_text_filtered(temp_test_image, sample_plate_detections):
    """Test that short text results are filtered."""
    images = {temp_test_image: Image.open(temp_test_image).convert("RGB")}

    with patch("backend.services.ocr_service.asyncio.to_thread") as mock_to_thread:
        # Return very short text
        mock_to_thread.return_value = ("A", 0.95)

        results = await read_plates(
            ocr_model=MagicMock(),
            plate_detections=sample_plate_detections,
            images=images,
        )

    # Should be filtered out because cleaned text is too short
    assert len(results) == 0


@pytest.mark.asyncio
async def test_read_plates_handles_exception(temp_test_image):
    """Test exception handling during OCR."""
    detections = [
        PlateDetection(
            bbox=(100.0, 200.0, 300.0, 250.0),
            confidence=0.95,
        )
    ]
    images = {temp_test_image: Image.open(temp_test_image).convert("RGB")}

    with patch("backend.services.ocr_service.asyncio.to_thread") as mock_to_thread:
        mock_to_thread.side_effect = RuntimeError("OCR crashed")

        results = await read_plates(
            ocr_model=MagicMock(),
            plate_detections=detections,
            images=images,
        )

    assert len(results) == 0


@pytest.mark.asyncio
async def test_read_plates_with_image_paths(temp_test_image, sample_plate_detections):
    """Test plate reading with image paths instead of cache."""
    with patch("backend.services.ocr_service.asyncio.to_thread") as mock_to_thread:
        mock_to_thread.return_value = ("XYZ789", 0.92)

        results = await read_plates(
            ocr_model=MagicMock(),
            plate_detections=sample_plate_detections,
            image_paths=[temp_test_image],
        )

    assert len(results) == 2
    assert all(r.text == "XYZ789" for r in results)


@pytest.mark.asyncio
async def test_read_single_plate_success():
    """Test reading single plate image."""
    plate_image = Image.new("RGB", (200, 50), color=(255, 255, 255))

    with patch("backend.services.ocr_service.asyncio.to_thread") as mock_to_thread:
        mock_to_thread.return_value = ("ABC 123", 0.95)

        result = await read_single_plate(
            ocr_model=MagicMock(),
            plate_image=plate_image,
        )

    assert result is not None
    assert result.text == "ABC123"
    assert result.confidence == 0.95


@pytest.mark.asyncio
async def test_read_single_plate_no_model():
    """Test single plate reading with no model."""
    plate_image = Image.new("RGB", (200, 50), color=(255, 255, 255))

    result = await read_single_plate(
        ocr_model=None,
        plate_image=plate_image,
    )

    assert result is None


@pytest.mark.asyncio
async def test_read_single_plate_low_confidence():
    """Test single plate with low confidence."""
    plate_image = Image.new("RGB", (200, 50), color=(255, 255, 255))

    with patch("backend.services.ocr_service.asyncio.to_thread") as mock_to_thread:
        mock_to_thread.return_value = ("ABC123", 0.3)

        result = await read_single_plate(
            ocr_model=MagicMock(),
            plate_image=plate_image,
            min_confidence=0.5,
        )

    assert result is None


@pytest.mark.asyncio
async def test_read_single_plate_handles_exception():
    """Test single plate exception handling."""
    plate_image = Image.new("RGB", (200, 50), color=(255, 255, 255))

    with patch("backend.services.ocr_service.asyncio.to_thread") as mock_to_thread:
        mock_to_thread.side_effect = RuntimeError("OCR failed")

        result = await read_single_plate(
            ocr_model=MagicMock(),
            plate_image=plate_image,
        )

    assert result is None


def test_plate_text_creation():
    """Test PlateText dataclass creation."""
    plate_text = PlateText(
        text="ABC123",
        confidence=0.95,
        plate_detection_id=42,
        raw_text="ABC 123",
        bbox=(100.0, 200.0, 300.0, 250.0),
    )

    assert plate_text.text == "ABC123"
    assert plate_text.confidence == 0.95
    assert plate_text.plate_detection_id == 42
    assert plate_text.raw_text == "ABC 123"
    assert plate_text.bbox == (100.0, 200.0, 300.0, 250.0)


def test_plate_text_defaults():
    """Test PlateText with default values."""
    plate_text = PlateText(
        text="ABC123",
        confidence=0.95,
    )

    assert plate_text.plate_detection_id is None
    assert plate_text.raw_text is None
    assert plate_text.bbox is None


@pytest.mark.asyncio
async def test_read_plates_no_images_available():
    """Test when no images are available."""
    detections = [
        PlateDetection(
            bbox=(100.0, 200.0, 300.0, 250.0),
            confidence=0.95,
        )
    ]

    results = await read_plates(
        ocr_model=MagicMock(),
        plate_detections=detections,
        images={},  # Empty image cache
        image_paths=[],  # No paths
    )

    # Should handle gracefully
    assert len(results) == 0


def test_clean_plate_text_with_numbers_only():
    """Test plate text that is only numbers."""
    assert clean_plate_text("123456") == "123456"


def test_clean_plate_text_with_letters_only():
    """Test plate text that is only letters."""
    assert clean_plate_text("ABCDEF") == "ABCDEF"
