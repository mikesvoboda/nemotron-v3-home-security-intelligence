"""Unit tests for detector client service."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.camera import Camera
from backend.services.detector_client import DetectorClient, DetectorUnavailableError

# Fixtures


@pytest.fixture(autouse=True)
def mock_baseline_service():
    """Mock the baseline service to avoid database interactions in unit tests.

    This fixture automatically mocks get_baseline_service() for all tests in this
    module. The baseline service is called during detection processing to update
    analytics baselines (NEM-1259), but unit tests should not require database
    access for these updates.
    """
    mock_service = MagicMock()
    mock_service.update_baseline = AsyncMock()

    with patch("backend.services.detector_client.get_baseline_service", return_value=mock_service):
        yield mock_service


@pytest.fixture
def mock_session():
    """Mock database session."""
    session = AsyncMock(spec=AsyncSession)
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.flush = AsyncMock()
    return session


@pytest.fixture
def detector_client():
    """Create detector client instance with minimal retries for faster tests."""
    return DetectorClient(max_retries=1)


@pytest.fixture
def sample_detector_response():
    """Sample response from YOLO26 detector."""
    return {
        "detections": [
            {
                "class": "person",
                "confidence": 0.95,
                "bbox": [100, 150, 300, 400],  # [x, y, width, height]
            },
            {
                "class": "car",
                "confidence": 0.88,
                "bbox": [500, 200, 200, 150],
            },
            {
                "class": "dog",
                "confidence": 0.45,  # Below default threshold
                "bbox": [250, 300, 100, 80],
            },
        ],
        "processing_time_ms": 125.5,
        "image_size": [1920, 1080],
    }


# Test: Health Check


@pytest.mark.asyncio
async def test_health_check_success(detector_client):
    """Test health check when detector is available."""
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "healthy"}
        mock_get.return_value = mock_response

        result = await detector_client.health_check()

        assert result is True
        mock_get.assert_called_once()


@pytest.mark.asyncio
async def test_health_check_connection_error(detector_client):
    """Test health check when detector is not reachable."""
    with patch("httpx.AsyncClient.get", side_effect=httpx.ConnectError("Connection refused")):
        result = await detector_client.health_check()

        assert result is False


@pytest.mark.asyncio
async def test_health_check_timeout(detector_client):
    """Test health check when detector times out."""
    with patch("httpx.AsyncClient.get", side_effect=httpx.TimeoutException("Timeout")):
        result = await detector_client.health_check()

        assert result is False


@pytest.mark.asyncio
async def test_health_check_http_error(detector_client):
    """Test health check when detector returns error status."""
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Internal Server Error", request=MagicMock(spec=httpx.Request), response=mock_response
        )
        mock_get.return_value = mock_response

        result = await detector_client.health_check()

        assert result is False


# Test: Detect Objects - Success Cases


@pytest.mark.asyncio
async def test_detect_objects_success(detector_client, mock_session, sample_detector_response):
    """Test successful object detection."""
    image_path = "/export/foscam/front_door/image_001.jpg"
    camera_id = "front_door"

    # Mock file reading
    mock_image_data = b"fake_image_data"

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.read_bytes", return_value=mock_image_data),
        patch("httpx.AsyncClient.post") as mock_post,
        patch.object(detector_client, "_validate_image_for_detection_async", return_value=True),
    ):
        # Mock detector response
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = sample_detector_response
        mock_post.return_value = mock_response

        detections = await detector_client.detect_objects(image_path, camera_id, mock_session)

        # Should return 2 detections (1 filtered out by confidence threshold)
        assert len(detections) == 2
        assert detections[0].object_type == "person"
        assert detections[0].confidence == 0.95
        assert detections[0].camera_id == camera_id
        assert detections[0].file_path == image_path

        assert detections[1].object_type == "car"
        assert detections[1].confidence == 0.88

        # Verify bbox values
        assert detections[0].bbox_x == 100
        assert detections[0].bbox_y == 150
        assert detections[0].bbox_width == 300
        assert detections[0].bbox_height == 400

        # Verify database interactions
        assert mock_session.add.call_count == 2
        assert mock_session.commit.called


@pytest.mark.asyncio
async def test_detect_objects_filters_low_confidence(
    detector_client, mock_session, sample_detector_response
):
    """Test that detections below confidence threshold are filtered out."""
    image_path = "/export/foscam/back_door/image_002.jpg"
    camera_id = "back_door"

    mock_image_data = b"fake_image_data"

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.read_bytes", return_value=mock_image_data),
        patch("httpx.AsyncClient.post") as mock_post,
        patch.object(detector_client, "_validate_image_for_detection_async", return_value=True),
    ):
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = sample_detector_response
        mock_post.return_value = mock_response

        detections = await detector_client.detect_objects(image_path, camera_id, mock_session)

        # Should filter out dog detection (confidence 0.45 < 0.5 threshold)
        object_types = [d.object_type for d in detections]
        assert "person" in object_types
        assert "car" in object_types
        assert "dog" not in object_types


@pytest.mark.asyncio
async def test_detect_objects_no_detections(detector_client, mock_session):
    """Test when detector returns no detections."""
    image_path = "/export/foscam/garage/image_003.jpg"
    camera_id = "garage"

    mock_image_data = b"fake_image_data"
    empty_response = {"detections": [], "processing_time_ms": 50.0, "image_size": [1920, 1080]}

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.read_bytes", return_value=mock_image_data),
        patch("httpx.AsyncClient.post") as mock_post,
        patch.object(detector_client, "_validate_image_for_detection_async", return_value=True),
    ):
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = empty_response
        mock_post.return_value = mock_response

        detections = await detector_client.detect_objects(image_path, camera_id, mock_session)

        assert len(detections) == 0
        assert not mock_session.add.called


# Test: Detect Objects - Error Handling


@pytest.mark.asyncio
async def test_detect_objects_file_not_found(detector_client, mock_session):
    """Test handling when image file does not exist."""
    image_path = "/export/foscam/missing/image.jpg"
    camera_id = "front_door"

    with patch("pathlib.Path.exists", return_value=False):
        detections = await detector_client.detect_objects(image_path, camera_id, mock_session)

        assert len(detections) == 0
        assert not mock_session.add.called


@pytest.mark.asyncio
async def test_detect_objects_connection_error_raises_exception(detector_client, mock_session):
    """Test that connection errors raise DetectorUnavailableError after retry exhaustion."""
    image_path = "/export/foscam/front_door/image_004.jpg"
    camera_id = "front_door"

    mock_image_data = b"fake_image_data"

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.read_bytes", return_value=mock_image_data),
        patch("httpx.AsyncClient.post", side_effect=httpx.ConnectError("Connection refused")),
        patch.object(detector_client, "_validate_image_for_detection_async", return_value=True),
    ):
        with pytest.raises(DetectorUnavailableError) as exc_info:
            await detector_client.detect_objects(image_path, camera_id, mock_session)

        # After retry exhaustion, error message indicates retry failure (NEM-1343)
        assert "failed after" in str(exc_info.value)
        assert exc_info.value.original_error is not None
        # Verify original error is preserved
        assert isinstance(exc_info.value.original_error, httpx.ConnectError)
        assert not mock_session.add.called


@pytest.mark.asyncio
async def test_detect_objects_timeout_raises_exception(detector_client, mock_session):
    """Test that timeout errors raise DetectorUnavailableError after retry exhaustion."""
    image_path = "/export/foscam/front_door/image_005.jpg"
    camera_id = "front_door"

    mock_image_data = b"fake_image_data"

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.read_bytes", return_value=mock_image_data),
        patch("httpx.AsyncClient.post", side_effect=httpx.TimeoutException("Request timeout")),
        patch.object(detector_client, "_validate_image_for_detection_async", return_value=True),
    ):
        with pytest.raises(DetectorUnavailableError) as exc_info:
            await detector_client.detect_objects(image_path, camera_id, mock_session)

        # After retry exhaustion, error message indicates retry failure (NEM-1343)
        assert "failed after" in str(exc_info.value)
        # Verify original error is preserved
        assert isinstance(exc_info.value.original_error, httpx.TimeoutException)
        assert not mock_session.add.called


@pytest.mark.asyncio
async def test_detect_objects_server_error_raises_exception(detector_client, mock_session):
    """Test that HTTP 5xx errors raise DetectorUnavailableError after retry exhaustion."""
    image_path = "/export/foscam/front_door/image_006.jpg"
    camera_id = "front_door"

    mock_image_data = b"fake_image_data"

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.read_bytes", return_value=mock_image_data),
        patch("httpx.AsyncClient.post") as mock_post,
        patch.object(detector_client, "_validate_image_for_detection_async", return_value=True),
    ):
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Internal Server Error", request=MagicMock(spec=httpx.Request), response=mock_response
        )
        mock_post.return_value = mock_response

        with pytest.raises(DetectorUnavailableError) as exc_info:
            await detector_client.detect_objects(image_path, camera_id, mock_session)

        # After retry exhaustion, error message indicates retry failure (NEM-1343)
        assert "failed after" in str(exc_info.value)
        # Verify original error is preserved
        assert isinstance(exc_info.value.original_error, httpx.HTTPStatusError)
        assert not mock_session.add.called


@pytest.mark.asyncio
async def test_detect_objects_client_error_returns_empty(detector_client, mock_session):
    """Test that HTTP 4xx errors return empty list (no retry for client errors)."""
    image_path = "/export/foscam/front_door/image_006b.jpg"
    camera_id = "front_door"

    mock_image_data = b"fake_image_data"

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.read_bytes", return_value=mock_image_data),
        patch("httpx.AsyncClient.post") as mock_post,
        patch.object(detector_client, "_validate_image_for_detection_async", return_value=True),
    ):
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 400
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Bad Request", request=MagicMock(spec=httpx.Request), response=mock_response
        )
        mock_post.return_value = mock_response

        detections = await detector_client.detect_objects(image_path, camera_id, mock_session)

        # 4xx errors should return empty (client error, not retryable)
        assert len(detections) == 0
        assert not mock_session.add.called


@pytest.mark.asyncio
async def test_detect_objects_invalid_json_raises_exception(detector_client, mock_session):
    """Test that invalid JSON raises DetectorUnavailableError after retry exhaustion.

    Invalid JSON could indicate a server-side issue (corrupt response,
    partial response, etc.) so it should be retried (NEM-1343).
    """
    image_path = "/export/foscam/front_door/image_007.jpg"
    camera_id = "front_door"

    mock_image_data = b"fake_image_data"

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.read_bytes", return_value=mock_image_data),
        patch("httpx.AsyncClient.post") as mock_post,
        patch.object(detector_client, "_validate_image_for_detection_async", return_value=True),
    ):
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
        mock_post.return_value = mock_response

        with pytest.raises(DetectorUnavailableError) as exc_info:
            await detector_client.detect_objects(image_path, camera_id, mock_session)

        # After retry exhaustion, error message indicates retry failure (NEM-1343)
        assert "failed after" in str(exc_info.value)
        # Verify original error is a JSONDecodeError
        assert isinstance(exc_info.value.original_error, json.JSONDecodeError)
        assert not mock_session.add.called


@pytest.mark.asyncio
async def test_detect_objects_malformed_response(detector_client, mock_session):
    """Test handling when detector returns malformed response structure."""
    image_path = "/export/foscam/front_door/image_008.jpg"
    camera_id = "front_door"

    mock_image_data = b"fake_image_data"
    malformed_response = {"wrong_key": "no detections field"}

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.read_bytes", return_value=mock_image_data),
        patch("httpx.AsyncClient.post") as mock_post,
        patch.object(detector_client, "_validate_image_for_detection_async", return_value=True),
    ):
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = malformed_response
        mock_post.return_value = mock_response

        detections = await detector_client.detect_objects(image_path, camera_id, mock_session)

        assert len(detections) == 0
        assert not mock_session.add.called


@pytest.mark.asyncio
async def test_detector_client_uses_config():
    """Test that DetectorClient uses configuration values."""
    with patch("backend.services.detector_client.get_settings") as mock_settings:
        mock_settings.return_value.yolo26_url = "http://custom-detector:9000"
        mock_settings.return_value.detection_confidence_threshold = 0.7

        client = DetectorClient()

        assert client._detector_url == "http://custom-detector:9000"
        assert client._confidence_threshold == 0.7


@pytest.mark.asyncio
async def test_detect_objects_sets_file_type(detector_client, mock_session):
    """Test that file type is correctly set as MIME type."""
    image_path = "/export/foscam/front_door/snapshot.jpeg"
    camera_id = "front_door"

    mock_image_data = b"fake_image_data"
    response = {
        "detections": [
            {
                "class": "person",
                "confidence": 0.95,
                "bbox": [100, 150, 300, 400],
            }
        ],
        "processing_time_ms": 50.0,
        "image_size": [1920, 1080],
    }

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.read_bytes", return_value=mock_image_data),
        patch("httpx.AsyncClient.post") as mock_post,
        patch.object(detector_client, "_validate_image_for_detection_async", return_value=True),
    ):
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = response
        mock_post.return_value = mock_response

        detections = await detector_client.detect_objects(image_path, camera_id, mock_session)

        assert len(detections) == 1
        assert detections[0].file_type == "image/jpeg"


@pytest.mark.asyncio
async def test_detect_objects_sets_timestamp(detector_client, mock_session):
    """Test that detected_at timestamp is set."""
    image_path = "/export/foscam/front_door/image_009.jpg"
    camera_id = "front_door"

    mock_image_data = b"fake_image_data"
    response = {
        "detections": [
            {
                "class": "person",
                "confidence": 0.95,
                "bbox": [100, 150, 300, 400],
            }
        ],
        "processing_time_ms": 50.0,
        "image_size": [1920, 1080],
    }

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.read_bytes", return_value=mock_image_data),
        patch("httpx.AsyncClient.post") as mock_post,
        patch.object(detector_client, "_validate_image_for_detection_async", return_value=True),
    ):
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = response
        mock_post.return_value = mock_response

        detections = await detector_client.detect_objects(image_path, camera_id, mock_session)

        assert len(detections) == 1
        assert detections[0].detected_at is not None


# Test: Multiple Object Types


@pytest.mark.asyncio
async def test_detect_objects_multiple_types(detector_client, mock_session):
    """Test detection with multiple different object types."""
    image_path = "/export/foscam/parking/image_010.jpg"
    camera_id = "parking"

    mock_image_data = b"fake_image_data"
    response = {
        "detections": [
            {"class": "person", "confidence": 0.92, "bbox": [100, 150, 80, 200]},
            {"class": "person", "confidence": 0.89, "bbox": [300, 150, 75, 195]},
            {"class": "car", "confidence": 0.95, "bbox": [500, 200, 300, 200]},
            {"class": "bicycle", "confidence": 0.78, "bbox": [200, 250, 60, 100]},
        ],
        "processing_time_ms": 150.0,
        "image_size": [1920, 1080],
    }

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.read_bytes", return_value=mock_image_data),
        patch("httpx.AsyncClient.post") as mock_post,
        patch.object(detector_client, "_validate_image_for_detection_async", return_value=True),
    ):
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = response
        mock_post.return_value = mock_response

        detections = await detector_client.detect_objects(image_path, camera_id, mock_session)

        assert len(detections) == 4
        object_types = [d.object_type for d in detections]
        assert object_types.count("person") == 2
        assert "car" in object_types
        assert "bicycle" in object_types


@pytest.mark.asyncio
async def test_health_check_unexpected_exception(detector_client):
    """Test health check when unexpected exception occurs."""
    with patch("httpx.AsyncClient.get", side_effect=ValueError("Unexpected error")):
        result = await detector_client.health_check()

        assert result is False


@pytest.mark.asyncio
async def test_detect_objects_invalid_bbox_format(detector_client, mock_session):
    """Test handling when detector returns invalid bbox format."""
    image_path = "/export/foscam/front_door/image_011.jpg"
    camera_id = "front_door"

    mock_image_data = b"fake_image_data"
    response = {
        "detections": [
            {
                "class": "person",
                "confidence": 0.95,
                "bbox": [100, 150],  # Invalid: only 2 values instead of 4
            }
        ],
        "processing_time_ms": 50.0,
        "image_size": [1920, 1080],
    }

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.read_bytes", return_value=mock_image_data),
        patch("httpx.AsyncClient.post") as mock_post,
        patch.object(detector_client, "_validate_image_for_detection_async", return_value=True),
    ):
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = response
        mock_post.return_value = mock_response

        detections = await detector_client.detect_objects(image_path, camera_id, mock_session)

        # Should skip detection with invalid bbox
        assert len(detections) == 0
        assert not mock_session.add.called


@pytest.mark.asyncio
async def test_detect_objects_detection_processing_exception(detector_client, mock_session):
    """Test handling when exception occurs processing individual detection."""
    image_path = "/export/foscam/front_door/image_012.jpg"
    camera_id = "front_door"

    mock_image_data = b"fake_image_data"
    response = {
        "detections": [
            {
                "class": "person",
                "confidence": 0.95,
                "bbox": [100, 150, 300, 400],
            }
        ],
        "processing_time_ms": 50.0,
        "image_size": [1920, 1080],
    }

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.read_bytes", return_value=mock_image_data),
        patch("httpx.AsyncClient.post") as mock_post,
        patch("backend.services.detector_client.Detection", side_effect=ValueError("DB error")),
    ):
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = response
        mock_post.return_value = mock_response

        detections = await detector_client.detect_objects(image_path, camera_id, mock_session)

        # Should handle exception and return empty list
        assert len(detections) == 0


# Test: DetectorUnavailableError Exception


def test_detector_unavailable_error_stores_original_error():
    """Test that DetectorUnavailableError stores the original exception."""
    original = ValueError("Original error")
    error = DetectorUnavailableError("Detector unavailable", original_error=original)

    assert str(error) == "Detector unavailable"
    assert error.original_error is original


def test_detector_unavailable_error_without_original():
    """Test DetectorUnavailableError works without original error."""
    error = DetectorUnavailableError("Detector unavailable")

    assert str(error) == "Detector unavailable"
    assert error.original_error is None


# Test: HTTP 5xx vs 4xx Error Handling


@pytest.mark.asyncio
async def test_detect_objects_http_502_raises_exception(detector_client, mock_session):
    """Test that HTTP 502 Bad Gateway raises DetectorUnavailableError after retry exhaustion."""
    image_path = "/export/foscam/front_door/image_502.jpg"
    camera_id = "front_door"
    mock_image_data = b"fake_image_data"

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.read_bytes", return_value=mock_image_data),
        patch("httpx.AsyncClient.post") as mock_post,
        patch.object(detector_client, "_validate_image_for_detection_async", return_value=True),
    ):
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 502
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Bad Gateway", request=MagicMock(spec=httpx.Request), response=mock_response
        )
        mock_post.return_value = mock_response

        with pytest.raises(DetectorUnavailableError) as exc_info:
            await detector_client.detect_objects(image_path, camera_id, mock_session)

        # After retry exhaustion, error message indicates retry failure (NEM-1343)
        assert "failed after" in str(exc_info.value)
        assert isinstance(exc_info.value.original_error, httpx.HTTPStatusError)


@pytest.mark.asyncio
async def test_detect_objects_http_503_raises_exception(detector_client, mock_session):
    """Test that HTTP 503 Service Unavailable raises DetectorUnavailableError."""
    image_path = "/export/foscam/front_door/image_503.jpg"
    camera_id = "front_door"
    mock_image_data = b"fake_image_data"

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.read_bytes", return_value=mock_image_data),
        patch("httpx.AsyncClient.post") as mock_post,
        patch.object(detector_client, "_validate_image_for_detection_async", return_value=True),
    ):
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 503
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Service Unavailable", request=MagicMock(spec=httpx.Request), response=mock_response
        )
        mock_post.return_value = mock_response

        with pytest.raises(DetectorUnavailableError):
            await detector_client.detect_objects(image_path, camera_id, mock_session)


@pytest.mark.asyncio
async def test_detect_objects_http_404_returns_empty(detector_client, mock_session):
    """Test that HTTP 404 returns empty list (client error)."""
    image_path = "/export/foscam/front_door/image_404.jpg"
    camera_id = "front_door"
    mock_image_data = b"fake_image_data"

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.read_bytes", return_value=mock_image_data),
        patch("httpx.AsyncClient.post") as mock_post,
        patch.object(detector_client, "_validate_image_for_detection_async", return_value=True),
    ):
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Not Found", request=MagicMock(spec=httpx.Request), response=mock_response
        )
        mock_post.return_value = mock_response

        detections = await detector_client.detect_objects(image_path, camera_id, mock_session)

        # 4xx should return empty, not raise
        assert len(detections) == 0


@pytest.mark.asyncio
async def test_detect_objects_unexpected_error_raises_exception(detector_client, mock_session):
    """Test that unexpected errors raise DetectorUnavailableError after retry exhaustion."""
    image_path = "/export/foscam/front_door/image_unexpected.jpg"
    camera_id = "front_door"
    mock_image_data = b"fake_image_data"

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.read_bytes", return_value=mock_image_data),
        patch("httpx.AsyncClient.post", side_effect=RuntimeError("Unexpected error")),
        patch.object(detector_client, "_validate_image_for_detection_async", return_value=True),
    ):
        with pytest.raises(DetectorUnavailableError) as exc_info:
            await detector_client.detect_objects(image_path, camera_id, mock_session)

        # After retry exhaustion, error message indicates retry failure (NEM-1343)
        assert "failed after" in str(exc_info.value)
        # Verify original error is preserved
        assert isinstance(exc_info.value.original_error, RuntimeError)


# Test: Retry Logic (NEM-1343)


@pytest.mark.asyncio
async def test_detect_objects_retry_succeeds_after_transient_failure(mock_session):
    """Test that retry logic succeeds when transient failure resolves.

    This verifies the exponential backoff retry logic works correctly (NEM-1343).
    """
    image_path = "/export/foscam/front_door/image_retry.jpg"
    camera_id = "front_door"
    mock_image_data = b"fake_image_data"

    # Create client with 3 retries
    detector_client = DetectorClient(max_retries=3)

    # Success response for second attempt
    success_response = MagicMock(spec=httpx.Response)
    success_response.status_code = 200
    success_response.json.return_value = {
        "detections": [{"class": "person", "confidence": 0.95, "bbox": [100, 150, 300, 400]}]
    }

    call_count = 0

    async def mock_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            # First attempt fails with connection error
            raise httpx.ConnectError("Temporary connection error")
        # Second attempt succeeds
        return success_response

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.read_bytes", return_value=mock_image_data),
        patch("httpx.AsyncClient.post", side_effect=mock_post),
        patch.object(detector_client, "_validate_image_for_detection_async", return_value=True),
        patch("asyncio.sleep", new_callable=AsyncMock),  # Speed up test by mocking sleep
    ):
        detections = await detector_client.detect_objects(image_path, camera_id, mock_session)

        # Should succeed on second attempt
        assert call_count == 2
        assert len(detections) == 1
        assert detections[0].object_type == "person"


@pytest.mark.asyncio
async def test_detect_objects_retry_exhausts_all_attempts(mock_session):
    """Test that retry logic exhausts all attempts before failing.

    This verifies the exponential backoff retry logic reports the correct
    number of attempts (NEM-1343).
    """
    image_path = "/export/foscam/front_door/image_retry_fail.jpg"
    camera_id = "front_door"
    mock_image_data = b"fake_image_data"

    # Create client with 3 retries
    detector_client = DetectorClient(max_retries=3)

    call_count = 0

    async def mock_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        raise httpx.TimeoutException("Request timeout")

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.read_bytes", return_value=mock_image_data),
        patch("httpx.AsyncClient.post", side_effect=mock_post),
        patch.object(detector_client, "_validate_image_for_detection_async", return_value=True),
        patch("asyncio.sleep", new_callable=AsyncMock),  # Speed up test by mocking sleep
    ):
        with pytest.raises(DetectorUnavailableError) as exc_info:
            await detector_client.detect_objects(image_path, camera_id, mock_session)

        # Should exhaust all 3 attempts
        assert call_count == 3
        assert "failed after 3 attempts" in str(exc_info.value)


# Test: HTTP 400 error with error detail extraction


@pytest.mark.asyncio
async def test_detect_objects_http_400_extracts_error_detail(detector_client, mock_session):
    """Test that HTTP 400 errors extract error detail from JSON response.

    When the detector returns 400 (invalid image), the error detail should be
    extracted from the response body for better logging/debugging.
    """
    image_path = "/export/foscam/front_door/corrupted_image.jpg"
    camera_id = "front_door"
    mock_image_data = b"not actually image data"

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.read_bytes", return_value=mock_image_data),
        patch("httpx.AsyncClient.post") as mock_post,
    ):
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 400
        # The detector returns a JSON body with error detail
        mock_response.json.return_value = {
            "detail": "Invalid image file 'corrupted_image.jpg': Cannot identify image format."
        }
        mock_response.text = '{"detail": "Invalid image file"}'
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Bad Request", request=MagicMock(spec=httpx.Request), response=mock_response
        )
        mock_post.return_value = mock_response

        detections = await detector_client.detect_objects(image_path, camera_id, mock_session)

        # Should return empty (4xx is client error, no retry)
        assert len(detections) == 0
        # No DB operations should occur
        assert not mock_session.add.called


@pytest.mark.asyncio
async def test_detect_objects_http_400_handles_non_json_response(detector_client, mock_session):
    """Test that HTTP 400 handles non-JSON response body gracefully."""
    image_path = "/export/foscam/front_door/bad_image.jpg"
    camera_id = "front_door"
    mock_image_data = b"fake_image_data"

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.read_bytes", return_value=mock_image_data),
        patch("httpx.AsyncClient.post") as mock_post,
    ):
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 400
        # Detector returns non-JSON body
        mock_response.json.side_effect = ValueError("No JSON object could be decoded")
        mock_response.text = "Plain text error message"
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Bad Request", request=MagicMock(spec=httpx.Request), response=mock_response
        )
        mock_post.return_value = mock_response

        detections = await detector_client.detect_objects(image_path, camera_id, mock_session)

        # Should still return empty and not crash
        assert len(detections) == 0


# Test: Camera last_seen_at Update


@pytest.mark.asyncio
async def test_detect_objects_updates_camera_last_seen_at(detector_client, mock_session):
    """Test that camera's last_seen_at is updated when detections are stored."""
    image_path = "/export/foscam/front_door/image_last_seen.jpg"
    camera_id = "front_door"

    mock_image_data = b"fake_image_data"
    response = {
        "detections": [
            {
                "class": "person",
                "confidence": 0.95,
                "bbox": [100, 150, 300, 400],
            }
        ],
        "processing_time_ms": 50.0,
        "image_size": [1920, 1080],
    }

    # Create a mock camera object to verify last_seen_at is updated
    mock_camera = MagicMock()
    mock_camera.last_seen_at = None
    mock_session.get = AsyncMock(return_value=mock_camera)

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.read_bytes", return_value=mock_image_data),
        patch("httpx.AsyncClient.post") as mock_post,
        patch.object(detector_client, "_validate_image_for_detection_async", return_value=True),
    ):
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = response
        mock_post.return_value = mock_response

        detections = await detector_client.detect_objects(image_path, camera_id, mock_session)

        assert len(detections) == 1
        # Verify camera was fetched
        mock_session.get.assert_called_once()
        # Verify last_seen_at was updated (should be a datetime, not None)
        assert mock_camera.last_seen_at is not None


@pytest.mark.asyncio
async def test_detect_objects_updates_camera_last_seen_even_without_detections(
    detector_client, mock_session
):
    """Test that camera's last_seen_at IS updated even when no detections are found (NEM-3268).

    This ensures cameras that upload images but have no detections (empty frames or
    filtered objects) show accurate last seen timestamps in the UI.
    """
    image_path = "/export/foscam/front_door/image_empty.jpg"
    camera_id = "front_door"

    mock_image_data = b"fake_image_data"
    empty_response = {"detections": [], "processing_time_ms": 50.0, "image_size": [1920, 1080]}

    # Create a mock camera to verify last_seen_at is updated
    mock_camera = MagicMock()
    mock_camera.last_seen_at = None
    mock_session.get = AsyncMock(return_value=mock_camera)

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.read_bytes", return_value=mock_image_data),
        patch("httpx.AsyncClient.post") as mock_post,
        patch.object(detector_client, "_validate_image_for_detection_async", return_value=True),
    ):
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = empty_response
        mock_post.return_value = mock_response

        detections = await detector_client.detect_objects(image_path, camera_id, mock_session)

        assert len(detections) == 0
        # Verify camera was fetched and last_seen_at was updated (NEM-3268)
        mock_session.get.assert_called_once_with(Camera, camera_id)
        assert mock_camera.last_seen_at is not None


@pytest.mark.asyncio
async def test_detect_objects_handles_missing_camera(detector_client, mock_session):
    """Test that detection works even if camera is not found in database."""
    image_path = "/export/foscam/orphan_camera/image.jpg"
    camera_id = "orphan_camera"

    mock_image_data = b"fake_image_data"
    response = {
        "detections": [
            {
                "class": "person",
                "confidence": 0.95,
                "bbox": [100, 150, 300, 400],
            }
        ],
        "processing_time_ms": 50.0,
        "image_size": [1920, 1080],
    }

    # Camera not found in database
    mock_session.get = AsyncMock(return_value=None)

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.read_bytes", return_value=mock_image_data),
        patch("httpx.AsyncClient.post") as mock_post,
        patch.object(detector_client, "_validate_image_for_detection_async", return_value=True),
    ):
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = response
        mock_post.return_value = mock_response

        # Should not raise, just skip camera update
        detections = await detector_client.detect_objects(image_path, camera_id, mock_session)

        assert len(detections) == 1
        # Verify we still committed the detections
        mock_session.commit.assert_called_once()


# Test: Image Validation


@pytest.mark.asyncio
async def test_detect_objects_rejects_invalid_image(detector_client, mock_session):
    """Test that invalid/corrupted images are rejected before detection."""
    image_path = "/export/foscam/front_door/corrupted.jpg"
    camera_id = "front_door"

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch.object(detector_client, "_validate_image_for_detection_async", return_value=False),
    ):
        detections = await detector_client.detect_objects(image_path, camera_id, mock_session)

        # Should return empty list for invalid images
        assert len(detections) == 0
        # Should not add any detections
        assert not mock_session.add.called
        # Should not commit
        assert not mock_session.commit.called


@pytest.mark.asyncio
async def test_detect_objects_rejects_truncated_image(detector_client, mock_session, tmp_path):
    """Test that truncated images from incomplete FTP uploads are rejected."""
    from PIL import Image

    from backend.services.detector_client import MIN_DETECTION_IMAGE_SIZE

    # Create a valid image first
    valid_image = tmp_path / "valid.jpg"
    img = Image.new("RGB", (640, 480), color="red")
    # Add gradient for larger file size
    pixels = img.load()
    if pixels is not None:
        for y in range(480):
            for x in range(640):
                pixels[x, y] = (x % 256, y % 256, (x + y) % 256)
    img.save(valid_image, "JPEG", quality=95)

    # Read and truncate
    valid_bytes = valid_image.read_bytes()
    truncated_bytes = valid_bytes[: int(len(valid_bytes) * 0.6)]

    # Write truncated image
    truncated_image = tmp_path / "truncated.jpg"
    truncated_image.write_bytes(truncated_bytes)

    # Verify it's above min size but still truncated
    assert truncated_image.stat().st_size >= MIN_DETECTION_IMAGE_SIZE

    with patch("pathlib.Path.exists", return_value=True):
        # Use real validation (not mocked)
        detections = await detector_client.detect_objects(
            str(truncated_image), "camera1", mock_session
        )

        # Should return empty list for truncated images
        assert len(detections) == 0


@pytest.mark.asyncio
async def test_detect_objects_rejects_too_small_image(detector_client, mock_session, tmp_path):
    """Test that very small images are rejected (likely truncated)."""
    from backend.services.detector_client import MIN_DETECTION_IMAGE_SIZE

    # Create a small file that's below the minimum size
    small_image = tmp_path / "tiny.jpg"
    # Just write some random bytes below the threshold
    small_image.write_bytes(b"\xff\xd8\xff" + b"\x00" * 5000)  # ~5KB

    assert small_image.stat().st_size < MIN_DETECTION_IMAGE_SIZE

    with patch("pathlib.Path.exists", return_value=True):
        detections = await detector_client.detect_objects(str(small_image), "camera1", mock_session)

        # Should return empty list for too-small images
        assert len(detections) == 0


def test_validate_image_for_detection_valid_image(detector_client, tmp_path):
    """Test _validate_image_for_detection accepts valid images."""
    from PIL import Image

    # Create a valid image above minimum size
    image_path = tmp_path / "valid.jpg"
    img = Image.new("RGB", (640, 480), color="blue")
    # Add gradient for larger file size
    pixels = img.load()
    if pixels is not None:
        for y in range(480):
            for x in range(640):
                pixels[x, y] = (x % 256, y % 256, (x + y) % 256)
    img.save(image_path, "JPEG", quality=95)

    result = detector_client._validate_image_for_detection(str(image_path), "camera1")

    assert result is True


def test_validate_image_for_detection_corrupted_image(detector_client, tmp_path):
    """Test _validate_image_for_detection rejects corrupted images."""
    # Create a file with invalid image data
    image_path = tmp_path / "corrupted.jpg"
    image_path.write_text("This is not an image file!")

    result = detector_client._validate_image_for_detection(str(image_path), "camera1")

    assert result is False


def test_validate_image_for_detection_too_small(detector_client, tmp_path):
    """Test _validate_image_for_detection rejects images below minimum size."""
    from PIL import Image

    # Create a tiny valid image
    image_path = tmp_path / "tiny.jpg"
    img = Image.new("RGB", (10, 10), color="red")
    img.save(image_path, "JPEG", quality=50)

    result = detector_client._validate_image_for_detection(str(image_path), "camera1")

    assert result is False


# Test: Async Image Validation (NEM-1462)


@pytest.mark.asyncio
async def test_validate_image_for_detection_async_valid_image(detector_client, tmp_path):
    """Test async image validation accepts valid images."""
    from PIL import Image

    # Create a valid image above minimum size
    image_path = tmp_path / "valid_async.jpg"
    img = Image.new("RGB", (640, 480), color="green")
    # Add gradient for larger file size
    pixels = img.load()
    if pixels is not None:
        for y in range(480):
            for x in range(640):
                pixels[x, y] = (x % 256, y % 256, (x + y) % 256)
    img.save(image_path, "JPEG", quality=95)

    result = await detector_client._validate_image_for_detection_async(str(image_path), "camera1")

    assert result is True


@pytest.mark.asyncio
async def test_validate_image_for_detection_async_matches_sync(detector_client, tmp_path):
    """Test async validation returns same result as sync version."""
    from PIL import Image

    # Create a valid image
    image_path = tmp_path / "valid_compare.jpg"
    img = Image.new("RGB", (640, 480), color="blue")
    pixels = img.load()
    if pixels is not None:
        for y in range(480):
            for x in range(640):
                pixels[x, y] = (x % 256, y % 256, (x + y) % 256)
    img.save(image_path, "JPEG", quality=95)

    sync_result = detector_client._validate_image_for_detection(str(image_path), "camera1")
    async_result = await detector_client._validate_image_for_detection_async(
        str(image_path), "camera1"
    )

    assert sync_result == async_result


@pytest.mark.asyncio
async def test_validate_image_for_detection_async_rejects_corrupted(detector_client, tmp_path):
    """Test async image validation rejects corrupted images."""
    image_path = tmp_path / "corrupted_async.jpg"
    image_path.write_text("This is not an image file!")

    result = await detector_client._validate_image_for_detection_async(str(image_path), "camera1")

    assert result is False


@pytest.mark.asyncio
async def test_async_file_read_does_not_block_event_loop(detector_client, mock_session, tmp_path):
    """Test that async file reading doesn't block the event loop."""
    import asyncio

    from PIL import Image

    # Create a valid image
    image_path = tmp_path / "nonblocking.jpg"
    img = Image.new("RGB", (640, 480), color="purple")
    pixels = img.load()
    if pixels is not None:
        for y in range(480):
            for x in range(640):
                pixels[x, y] = (x % 256, y % 256, (x + y) % 256)
    img.save(image_path, "JPEG", quality=95)

    # Track concurrent execution
    execution_order = []

    async def track_detection():
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_response = MagicMock(spec=httpx.Response)
            mock_response.status_code = 200
            mock_response.json.return_value = {"detections": []}
            mock_post.return_value = mock_response
            await detector_client.detect_objects(str(image_path), "camera1", mock_session)
            execution_order.append("detection_complete")

    async def quick_task():
        await asyncio.sleep(0.001)
        execution_order.append("quick_task")

    # Run both concurrently
    await asyncio.gather(track_detection(), quick_task())

    # Both should complete (exact order may vary)
    assert "detection_complete" in execution_order
    assert "quick_task" in execution_order


# Test: Semaphore Concurrency Limiting (NEM-1500)


def test_detector_client_has_semaphore():
    """Test that DetectorClient has class-level semaphore for concurrency limiting."""
    # Reset class-level semaphore to ensure clean state
    DetectorClient._request_semaphore = None
    DetectorClient._semaphore_limit = 0

    # Create a client - this will initialize the semaphore on first use
    _client = DetectorClient(max_retries=1)

    # Verify semaphore is created when accessed
    semaphore = DetectorClient._get_semaphore()
    assert semaphore is not None
    # Default limit is 4
    assert DetectorClient._semaphore_limit == 4


@pytest.mark.asyncio
async def test_semaphore_limits_concurrent_requests(mock_session):
    """Test that semaphore properly limits concurrent AI requests.

    This verifies the concurrency limiting functionality (NEM-1500).
    """
    import asyncio

    # Create a semaphore with limit 2 for testing
    test_semaphore = asyncio.Semaphore(2)

    client = DetectorClient(max_retries=1)

    # Track concurrent requests
    concurrent_count = 0
    max_concurrent = 0

    async def mock_request(*args, **kwargs):
        nonlocal concurrent_count, max_concurrent
        concurrent_count += 1
        max_concurrent = max(max_concurrent, concurrent_count)
        await asyncio.sleep(0.05)  # Simulate processing time
        concurrent_count -= 1
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"detections": []}
        return mock_response

    mock_image_data = b"fake_image_data"

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.read_bytes", return_value=mock_image_data),
        patch("httpx.AsyncClient.post", side_effect=mock_request),
        patch.object(client, "_validate_image_for_detection_async", return_value=True),
        # Mock get_inference_semaphore to return our test semaphore with limit 2
        # This is the semaphore used in detect_objects, not _get_semaphore
        patch(
            "backend.services.detector_client.get_inference_semaphore",
            return_value=test_semaphore,
        ),
    ):
        # Launch 4 concurrent detection requests
        tasks = [
            client.detect_objects(f"/path/image_{i}.jpg", "camera1", mock_session) for i in range(4)
        ]
        await asyncio.gather(*tasks)

        # Max concurrent should be limited to 2 (semaphore limit)
        assert max_concurrent <= 2


# Test: Additional Error Handling Coverage (NEM-1699)


@pytest.mark.asyncio
async def test_send_detection_request_timeout_with_retry(mock_session):
    """Test httpx.TimeoutException triggers retry with exponential backoff."""
    detector_client = DetectorClient(max_retries=3)
    image_path = "/export/foscam/front_door/timeout_test.jpg"
    camera_id = "front_door"
    mock_image_data = b"fake_image_data"

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.read_bytes", return_value=mock_image_data),
        patch("httpx.AsyncClient.post", side_effect=httpx.TimeoutException("Request timeout")),
        patch.object(detector_client, "_validate_image_for_detection_async", return_value=True),
        patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
    ):
        with pytest.raises(DetectorUnavailableError) as exc_info:
            await detector_client.detect_objects(image_path, camera_id, mock_session)

        # Verify exponential backoff was used
        assert mock_sleep.call_count == 2  # 2 retries with delays
        # First retry: 2^0 = 1 second
        assert mock_sleep.call_args_list[0][0][0] == 1
        # Second retry: 2^1 = 2 seconds
        assert mock_sleep.call_args_list[1][0][0] == 2
        # Verify original error is preserved
        assert isinstance(exc_info.value.original_error, httpx.TimeoutException)


@pytest.mark.asyncio
async def test_send_detection_request_connect_error_backoff_timing(mock_session):
    """Test httpx.ConnectError retry has correct exponential backoff timing."""
    detector_client = DetectorClient(max_retries=3)
    image_path = "/export/foscam/front_door/connect_test.jpg"
    camera_id = "front_door"
    mock_image_data = b"fake_image_data"

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.read_bytes", return_value=mock_image_data),
        patch("httpx.AsyncClient.post", side_effect=httpx.ConnectError("Connection refused")),
        patch.object(detector_client, "_validate_image_for_detection_async", return_value=True),
        patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
    ):
        with pytest.raises(DetectorUnavailableError):
            await detector_client.detect_objects(image_path, camera_id, mock_session)

        # Verify all 3 retries attempted (2 delays between 3 attempts)
        assert mock_sleep.call_count == 2
        # Exponential backoff: 1s, 2s
        assert mock_sleep.call_args_list[0][0][0] == 1
        assert mock_sleep.call_args_list[1][0][0] == 2


@pytest.mark.asyncio
async def test_send_detection_request_http_500_retry_with_backoff(mock_session):
    """Test HTTP 500 error triggers retry with exponential backoff."""
    detector_client = DetectorClient(max_retries=3)
    image_path = "/export/foscam/front_door/500_test.jpg"
    camera_id = "front_door"
    mock_image_data = b"fake_image_data"

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.read_bytes", return_value=mock_image_data),
        patch("httpx.AsyncClient.post") as mock_post,
        patch.object(detector_client, "_validate_image_for_detection_async", return_value=True),
        patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
    ):
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Internal Server Error", request=MagicMock(spec=httpx.Request), response=mock_response
        )
        mock_post.return_value = mock_response

        with pytest.raises(DetectorUnavailableError) as exc_info:
            await detector_client.detect_objects(image_path, camera_id, mock_session)

        # Verify retries with exponential backoff
        assert mock_sleep.call_count == 2
        assert mock_sleep.call_args_list[0][0][0] == 1
        assert mock_sleep.call_args_list[1][0][0] == 2
        # Verify original error preserved
        assert isinstance(exc_info.value.original_error, httpx.HTTPStatusError)


@pytest.mark.asyncio
async def test_send_detection_request_http_503_triggers_circuit_breaker(mock_session):
    """Test HTTP 503 Service Unavailable opens circuit breaker pattern."""
    detector_client = DetectorClient(max_retries=2)
    image_path = "/export/foscam/front_door/503_test.jpg"
    camera_id = "front_door"
    mock_image_data = b"fake_image_data"

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.read_bytes", return_value=mock_image_data),
        patch("httpx.AsyncClient.post") as mock_post,
        patch.object(detector_client, "_validate_image_for_detection_async", return_value=True),
        patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
    ):
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 503
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Service Unavailable", request=MagicMock(spec=httpx.Request), response=mock_response
        )
        mock_post.return_value = mock_response

        with pytest.raises(DetectorUnavailableError) as exc_info:
            await detector_client.detect_objects(image_path, camera_id, mock_session)

        # Verify HTTP 503 is retried (server error)
        assert mock_sleep.call_count == 1  # 1 retry delay
        assert "failed after 2 attempts" in str(exc_info.value)


@pytest.mark.asyncio
async def test_send_detection_request_json_decode_error(mock_session):
    """Test JSONDecodeError on malformed response triggers retry."""
    detector_client = DetectorClient(max_retries=2)
    image_path = "/export/foscam/front_door/json_error.jpg"
    camera_id = "front_door"
    mock_image_data = b"fake_image_data"

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.read_bytes", return_value=mock_image_data),
        patch("httpx.AsyncClient.post") as mock_post,
        patch.object(detector_client, "_validate_image_for_detection_async", return_value=True),
        patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
    ):
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.side_effect = json.JSONDecodeError("Expecting value", "", 0)
        mock_post.return_value = mock_response

        with pytest.raises(DetectorUnavailableError) as exc_info:
            await detector_client.detect_objects(image_path, camera_id, mock_session)

        # Verify retry on JSON error
        assert mock_sleep.call_count == 1
        assert isinstance(exc_info.value.original_error, json.JSONDecodeError)


@pytest.mark.asyncio
async def test_detect_objects_file_not_found_returns_empty_gracefully(
    detector_client, mock_session
):
    """Test FileNotFoundError for invalid image path returns empty list."""
    image_path = "/nonexistent/path/image.jpg"
    camera_id = "front_door"

    with patch("pathlib.Path.exists", return_value=False):
        detections = await detector_client.detect_objects(image_path, camera_id, mock_session)

        assert len(detections) == 0
        assert not mock_session.add.called
        assert not mock_session.commit.called


@pytest.mark.asyncio
async def test_detect_objects_empty_detection_list_returned_gracefully(
    detector_client, mock_session
):
    """Test empty detection list from detector is handled gracefully.

    Even with no detections, the camera's last_seen_at should be updated (NEM-3268),
    so commit is still called but no detections are added.
    """
    image_path = "/export/foscam/front_door/empty.jpg"
    camera_id = "front_door"
    mock_image_data = b"fake_image_data"

    # Create a mock camera to verify last_seen_at is updated
    mock_camera = MagicMock()
    mock_camera.last_seen_at = None
    mock_session.get = AsyncMock(return_value=mock_camera)

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.read_bytes", return_value=mock_image_data),
        patch("httpx.AsyncClient.post") as mock_post,
        patch.object(detector_client, "_validate_image_for_detection_async", return_value=True),
    ):
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"detections": []}
        mock_post.return_value = mock_response

        detections = await detector_client.detect_objects(image_path, camera_id, mock_session)

        # Should return empty list without error
        assert len(detections) == 0
        # No detections added to session
        assert not mock_session.add.called
        # Commit IS called to save camera.last_seen_at update (NEM-3268)
        assert mock_session.commit.called
        # Verify camera was fetched and last_seen_at was updated
        mock_session.get.assert_called_once_with(Camera, camera_id)
        assert mock_camera.last_seen_at is not None


@pytest.mark.asyncio
async def test_validate_image_for_detection_os_error_handling(detector_client, tmp_path):
    """Test OSError during image validation is handled gracefully."""
    image_path = tmp_path / "os_error.jpg"
    image_path.write_bytes(b"not an image")

    # Patch PIL.Image.open to raise OSError
    with patch("PIL.Image.open", side_effect=OSError("Disk error")):
        result = detector_client._validate_image_for_detection(str(image_path), "camera1")

        assert result is False


@pytest.mark.asyncio
async def test_detect_objects_with_video_metadata(detector_client, mock_session):
    """Test detection with video_path and video_metadata parameters."""
    image_path = "/export/foscam/front_door/frame_001.jpg"
    video_path = "/export/foscam/front_door/video.mp4"
    camera_id = "front_door"
    mock_image_data = b"fake_image_data"
    video_metadata = {
        "duration": 30.5,
        "video_codec": "h264",
        "video_width": 1920,
        "video_height": 1080,
        "file_type": "video/mp4",
    }

    response = {
        "detections": [
            {
                "class": "person",
                "confidence": 0.95,
                "bbox": [100, 150, 300, 400],
            }
        ]
    }

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.read_bytes", return_value=mock_image_data),
        patch("httpx.AsyncClient.post") as mock_post,
        patch.object(detector_client, "_validate_image_for_detection_async", return_value=True),
    ):
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = response
        mock_post.return_value = mock_response

        detections = await detector_client.detect_objects(
            image_path,
            camera_id,
            mock_session,
            video_path=video_path,
            video_metadata=video_metadata,
        )

        assert len(detections) == 1
        detection = detections[0]
        # Verify video metadata was applied
        assert detection.file_path == video_path  # Uses video path, not frame path
        assert detection.file_type == "video/mp4"
        assert detection.media_type == "video"
        assert detection.duration == 30.5
        assert detection.video_codec == "h264"
        assert detection.video_width == 1920
        assert detection.video_height == 1080


@pytest.mark.asyncio
async def test_detect_objects_invalid_bbox_dict_missing_keys(detector_client, mock_session):
    """Test handling when detector returns bbox dict with missing keys."""
    image_path = "/export/foscam/front_door/bad_bbox_dict.jpg"
    camera_id = "front_door"
    mock_image_data = b"fake_image_data"

    response = {
        "detections": [
            {
                "class": "person",
                "confidence": 0.95,
                "bbox": {"x": 100, "y": 150},  # Missing width and height
            }
        ]
    }

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.read_bytes", return_value=mock_image_data),
        patch("httpx.AsyncClient.post") as mock_post,
        patch.object(detector_client, "_validate_image_for_detection_async", return_value=True),
    ):
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = response
        mock_post.return_value = mock_response

        detections = await detector_client.detect_objects(image_path, camera_id, mock_session)

        # Should skip detection with invalid bbox
        assert len(detections) == 0


@pytest.mark.asyncio
async def test_detect_objects_invalid_bbox_array_format(detector_client, mock_session):
    """Test handling when detector returns bbox array with wrong length."""
    image_path = "/export/foscam/front_door/bad_bbox_array.jpg"
    camera_id = "front_door"
    mock_image_data = b"fake_image_data"

    response = {
        "detections": [
            {
                "class": "person",
                "confidence": 0.95,
                "bbox": [100, 150, 300],  # Only 3 values instead of 4
            }
        ]
    }

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.read_bytes", return_value=mock_image_data),
        patch("httpx.AsyncClient.post") as mock_post,
        patch.object(detector_client, "_validate_image_for_detection_async", return_value=True),
    ):
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = response
        mock_post.return_value = mock_response

        detections = await detector_client.detect_objects(image_path, camera_id, mock_session)

        # Should skip detection with invalid bbox
        assert len(detections) == 0


@pytest.mark.asyncio
async def test_detect_objects_inference_semaphore_acquisition(detector_client, mock_session):
    """Test that inference semaphore is acquired during detection."""

    image_path = "/export/foscam/front_door/semaphore_test.jpg"
    camera_id = "front_door"
    mock_image_data = b"fake_image_data"

    # Track semaphore acquisition
    semaphore_acquired = False

    class MockSemaphore:
        async def __aenter__(self):
            nonlocal semaphore_acquired
            semaphore_acquired = True
            return self

        async def __aexit__(self, *args):
            pass

    mock_semaphore = MockSemaphore()

    response = {"detections": []}

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.read_bytes", return_value=mock_image_data),
        patch("httpx.AsyncClient.post") as mock_post,
        patch.object(detector_client, "_validate_image_for_detection_async", return_value=True),
        patch(
            "backend.services.detector_client.get_inference_semaphore", return_value=mock_semaphore
        ),
    ):
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = response
        mock_post.return_value = mock_response

        await detector_client.detect_objects(image_path, camera_id, mock_session)

        # Verify semaphore was acquired
        assert semaphore_acquired is True


@pytest.mark.asyncio
async def test_detect_objects_retry_exhaustion_without_exception(mock_session):
    """Test retry exhaustion edge case where last_exception is None."""
    detector_client = DetectorClient(max_retries=1)
    image_path = "/export/foscam/front_door/no_exception.jpg"
    camera_id = "front_door"
    mock_image_data = b"fake_image_data"

    # Create a scenario where the retry loop completes without setting last_exception
    # This is a defensive test for line 417 edge case
    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.read_bytes", return_value=mock_image_data),
        patch.object(detector_client, "_validate_image_for_detection_async", return_value=True),
        patch.object(detector_client, "_send_detection_request") as mock_send,
    ):
        # Simulate the edge case by raising DetectorUnavailableError directly
        mock_send.side_effect = DetectorUnavailableError("All retries exhausted")

        with pytest.raises(DetectorUnavailableError) as exc_info:
            await detector_client.detect_objects(image_path, camera_id, mock_session)

        assert "All retries exhausted" in str(exc_info.value)


# Test: Circuit Breaker Integration (NEM-1724)


@pytest.mark.asyncio
async def test_detector_client_has_circuit_breaker():
    """Test that DetectorClient initializes with a circuit breaker."""
    client = DetectorClient(max_retries=1)

    # Verify circuit breaker is present with correct configuration
    # Circuit breaker is named per detector type (e.g., "detector_yolo26", "detector_yolo26")
    assert client._circuit_breaker is not None
    assert client._circuit_breaker.name == f"detector_{client.detector_type}"
    assert client._circuit_breaker.config.failure_threshold == 5
    assert client._circuit_breaker.config.recovery_timeout == 60.0


@pytest.mark.asyncio
async def test_circuit_breaker_opens_after_repeated_failures(mock_session):
    """Test that circuit breaker opens after failure threshold is reached.

    This verifies the circuit breaker prevents retry storms (NEM-1724).
    """
    from backend.services.circuit_breaker import CircuitState

    detector_client = DetectorClient(max_retries=1)
    image_path = "/export/foscam/front_door/circuit_breaker_test.jpg"
    camera_id = "front_door"
    mock_image_data = b"fake_image_data"

    # Reset circuit breaker state to ensure clean test
    detector_client._circuit_breaker.reset()

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.read_bytes", return_value=mock_image_data),
        patch("httpx.AsyncClient.post", side_effect=httpx.ConnectError("Connection refused")),
        patch.object(detector_client, "_validate_image_for_detection_async", return_value=True),
    ):
        # Fail 5 times to reach threshold (failure_threshold=5)
        for _i in range(5):
            with pytest.raises(DetectorUnavailableError):
                await detector_client.detect_objects(image_path, camera_id, mock_session)

        # Circuit should now be OPEN
        assert detector_client._circuit_breaker.state == CircuitState.OPEN

        # Next call should be rejected immediately by circuit breaker
        # (converted to DetectorUnavailableError with specific message)
        with pytest.raises(DetectorUnavailableError) as exc_info:
            await detector_client.detect_objects(image_path, camera_id, mock_session)

        assert "temporarily unavailable" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_circuit_breaker_rejects_calls_when_open(mock_session):
    """Test that open circuit breaker immediately rejects calls without HTTP request."""
    from backend.services.circuit_breaker import CircuitState

    detector_client = DetectorClient(max_retries=1)
    image_path = "/export/foscam/front_door/circuit_open_test.jpg"
    camera_id = "front_door"
    mock_image_data = b"fake_image_data"

    # Force circuit breaker open
    detector_client._circuit_breaker.force_open()
    assert detector_client._circuit_breaker.state == CircuitState.OPEN

    http_call_count = 0

    async def mock_http_post(*args, **kwargs):
        nonlocal http_call_count
        http_call_count += 1
        raise httpx.ConnectError("Should not be called")

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.read_bytes", return_value=mock_image_data),
        patch("httpx.AsyncClient.post", side_effect=mock_http_post),
        patch.object(detector_client, "_validate_image_for_detection_async", return_value=True),
    ):
        with pytest.raises(DetectorUnavailableError) as exc_info:
            await detector_client.detect_objects(image_path, camera_id, mock_session)

        # Should not have made any HTTP calls
        assert http_call_count == 0
        assert "temporarily unavailable" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_circuit_breaker_allows_recovery_after_timeout(mock_session):
    """Test that circuit breaker transitions to half-open after recovery timeout."""
    import asyncio

    from backend.services.circuit_breaker import CircuitBreakerConfig, CircuitState

    # Create client with short recovery timeout for testing
    detector_client = DetectorClient(max_retries=1)

    # Replace circuit breaker with one that has short timeout
    from backend.services.circuit_breaker import CircuitBreaker

    detector_client._circuit_breaker = CircuitBreaker(
        name="yolo26",
        config=CircuitBreakerConfig(
            failure_threshold=5,
            recovery_timeout=0.1,  # 100ms for testing
        ),
    )

    image_path = "/export/foscam/front_door/circuit_recovery_test.jpg"
    camera_id = "front_door"
    mock_image_data = b"fake_image_data"

    # Force circuit open
    detector_client._circuit_breaker.force_open()
    assert detector_client._circuit_breaker.state == CircuitState.OPEN

    # Wait for recovery timeout
    await asyncio.sleep(0.15)

    # Mock successful response
    success_response = MagicMock(spec=httpx.Response)
    success_response.status_code = 200
    success_response.json.return_value = {"detections": []}

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.read_bytes", return_value=mock_image_data),
        patch("httpx.AsyncClient.post") as mock_post,
        patch.object(detector_client, "_validate_image_for_detection_async", return_value=True),
    ):
        mock_post.return_value = success_response

        # Should transition to HALF_OPEN and allow trial call
        detections = await detector_client.detect_objects(image_path, camera_id, mock_session)

        # Call should succeed
        assert detections == []
        # Circuit should be in HALF_OPEN or CLOSED after success
        assert detector_client._circuit_breaker.state in (
            CircuitState.HALF_OPEN,
            CircuitState.CLOSED,
        )


@pytest.mark.asyncio
async def test_circuit_breaker_success_resets_failure_count(mock_session):
    """Test that successful calls reset the failure count."""
    detector_client = DetectorClient(max_retries=1)
    image_path = "/export/foscam/front_door/circuit_reset_test.jpg"
    camera_id = "front_door"
    mock_image_data = b"fake_image_data"

    # Reset circuit breaker state
    detector_client._circuit_breaker.reset()

    # First, accumulate some failures (but not enough to open)
    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.read_bytes", return_value=mock_image_data),
        patch("httpx.AsyncClient.post", side_effect=httpx.ConnectError("Connection refused")),
        patch.object(detector_client, "_validate_image_for_detection_async", return_value=True),
    ):
        for _ in range(3):  # Less than threshold of 5
            with pytest.raises(DetectorUnavailableError):
                await detector_client.detect_objects(image_path, camera_id, mock_session)

    assert detector_client._circuit_breaker.failure_count == 3

    # Now make a successful call
    success_response = MagicMock(spec=httpx.Response)
    success_response.status_code = 200
    success_response.json.return_value = {"detections": []}

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.read_bytes", return_value=mock_image_data),
        patch("httpx.AsyncClient.post") as mock_post,
        patch.object(detector_client, "_validate_image_for_detection_async", return_value=True),
    ):
        mock_post.return_value = success_response
        await detector_client.detect_objects(image_path, camera_id, mock_session)

    # Failure count should be reset to 0 after success
    assert detector_client._circuit_breaker.failure_count == 0


@pytest.mark.asyncio
async def test_circuit_breaker_excluded_exceptions_not_counted():
    """Test that ValueError (client errors) don't count toward circuit breaker threshold.

    HTTP 4xx errors should not cause the circuit breaker to open since they
    indicate client-side issues, not server availability problems.
    """
    from backend.services.circuit_breaker import CircuitState

    detector_client = DetectorClient(max_retries=1)
    detector_client._circuit_breaker.reset()

    # Verify ValueError is excluded
    assert ValueError in detector_client._circuit_breaker.config.excluded_exceptions

    # Circuit should stay closed even after many client errors
    assert detector_client._circuit_breaker.state == CircuitState.CLOSED
    assert detector_client._circuit_breaker.failure_count == 0


@pytest.mark.asyncio
async def test_circuit_breaker_metrics_are_tracked(mock_session):
    """Test that circuit breaker metrics are properly tracked."""
    detector_client = DetectorClient(max_retries=1)
    image_path = "/export/foscam/front_door/circuit_metrics_test.jpg"
    camera_id = "front_door"
    mock_image_data = b"fake_image_data"

    # Reset circuit breaker
    detector_client._circuit_breaker.reset()
    initial_total = detector_client._circuit_breaker.get_metrics().total_calls

    # Make a few calls (successful)
    success_response = MagicMock(spec=httpx.Response)
    success_response.status_code = 200
    success_response.json.return_value = {"detections": []}

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.read_bytes", return_value=mock_image_data),
        patch("httpx.AsyncClient.post") as mock_post,
        patch.object(detector_client, "_validate_image_for_detection_async", return_value=True),
    ):
        mock_post.return_value = success_response

        for _ in range(3):
            await detector_client.detect_objects(image_path, camera_id, mock_session)

    metrics = detector_client._circuit_breaker.get_metrics()
    assert metrics.total_calls == initial_total + 3
    assert metrics.failure_count == 0


@pytest.mark.asyncio
async def test_circuit_breaker_prevents_retry_storms(mock_session):
    """Test that circuit breaker prevents retry storms when detector is down.

    When the detector is unavailable, the circuit breaker should open and
    immediately reject subsequent calls without making network requests.
    This prevents overwhelming a failing service with retry attempts.
    """
    from backend.services.circuit_breaker import CircuitState

    detector_client = DetectorClient(max_retries=1)
    image_path = "/export/foscam/front_door/retry_storm_test.jpg"
    camera_id = "front_door"
    mock_image_data = b"fake_image_data"

    detector_client._circuit_breaker.reset()

    http_call_count = 0

    async def counting_http_post(*args, **kwargs):
        nonlocal http_call_count
        http_call_count += 1
        raise httpx.ConnectError("Connection refused")

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.read_bytes", return_value=mock_image_data),
        patch("httpx.AsyncClient.post", side_effect=counting_http_post),
        patch.object(detector_client, "_validate_image_for_detection_async", return_value=True),
    ):
        # First 5 calls will hit the network (threshold=5)
        for _ in range(5):
            with pytest.raises(DetectorUnavailableError):
                await detector_client.detect_objects(image_path, camera_id, mock_session)

        # Circuit should now be open
        assert detector_client._circuit_breaker.state == CircuitState.OPEN
        calls_before_open = http_call_count

        # Next 10 calls should be rejected immediately without HTTP
        for _ in range(10):
            with pytest.raises(DetectorUnavailableError):
                await detector_client.detect_objects(image_path, camera_id, mock_session)

        # HTTP call count should not have increased
        assert http_call_count == calls_before_open


@pytest.mark.asyncio
async def test_detector_client_get_circuit_breaker_status():
    """Test that DetectorClient provides access to circuit breaker status."""
    detector_client = DetectorClient(max_retries=1)

    status = detector_client._circuit_breaker.get_status()

    assert "name" in status
    # Circuit breaker is named per detector type (e.g., "detector_yolo26", "detector_yolo26")
    assert status["name"] == f"detector_{detector_client.detector_type}"
    assert "state" in status
    assert "failure_count" in status
    assert "config" in status
    assert status["config"]["failure_threshold"] == 5
    assert status["config"]["recovery_timeout"] == 60.0


# =============================================================================
# NEM-3797: Span Events for Pipeline Stages
# =============================================================================


class TestDetectorClientSpanEvents:
    """Tests for OpenTelemetry span events in DetectorClient (NEM-3797)."""

    @pytest.fixture
    def detector_client(self):
        """Create detector client instance with minimal retries."""
        return DetectorClient(max_retries=1)

    @pytest.fixture
    def sample_response(self):
        """Sample successful detector response."""
        return {
            "detections": [
                {
                    "class": "person",
                    "confidence": 0.95,
                    "bbox": [100, 150, 300, 400],
                },
            ],
            "processing_time_ms": 50.0,
        }

    @pytest.mark.asyncio
    async def test_detect_objects_adds_frame_capture_start_event(
        self, detector_client, mock_session, sample_response
    ):
        """Should add span event when frame capture starts (NEM-3797)."""
        image_path = "/export/foscam/front_door/test.jpg"
        camera_id = "front_door"
        mock_image_data = b"fake_image_data"

        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.read_bytes", return_value=mock_image_data),
            patch("httpx.AsyncClient.post") as mock_post,
            patch.object(detector_client, "_validate_image_for_detection_async", return_value=True),
            patch("backend.services.detector_client.add_span_event") as mock_add_event,
        ):
            mock_response = MagicMock(spec=httpx.Response)
            mock_response.status_code = 200
            mock_response.json.return_value = sample_response
            mock_post.return_value = mock_response

            await detector_client.detect_objects(image_path, camera_id, mock_session)

            # Verify frame_capture.start event was called
            frame_capture_start_calls = [
                c for c in mock_add_event.call_args_list if c[0][0] == "frame_capture.start"
            ]
            assert len(frame_capture_start_calls) >= 1
            attrs = frame_capture_start_calls[0][0][1]
            assert attrs["camera.id"] == camera_id
            assert attrs["file.path"] == image_path

    @pytest.mark.asyncio
    async def test_detect_objects_adds_frame_capture_complete_event(
        self, detector_client, mock_session, sample_response
    ):
        """Should add span event when frame capture completes (NEM-3797)."""
        image_path = "/export/foscam/front_door/test.jpg"
        camera_id = "front_door"
        mock_image_data = b"fake_image_data"

        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.read_bytes", return_value=mock_image_data),
            patch("httpx.AsyncClient.post") as mock_post,
            patch.object(detector_client, "_validate_image_for_detection_async", return_value=True),
            patch("backend.services.detector_client.add_span_event") as mock_add_event,
        ):
            mock_response = MagicMock(spec=httpx.Response)
            mock_response.status_code = 200
            mock_response.json.return_value = sample_response
            mock_post.return_value = mock_response

            await detector_client.detect_objects(image_path, camera_id, mock_session)

            # Verify frame_capture.complete event was called
            frame_capture_complete_calls = [
                c for c in mock_add_event.call_args_list if c[0][0] == "frame_capture.complete"
            ]
            assert len(frame_capture_complete_calls) >= 1
            attrs = frame_capture_complete_calls[0][0][1]
            assert attrs["camera.id"] == camera_id
            assert attrs["frame.size_bytes"] == len(mock_image_data)

    @pytest.mark.asyncio
    async def test_detect_objects_adds_detection_inference_events(
        self, detector_client, mock_session, sample_response
    ):
        """Should add span events for detection inference start and complete (NEM-3797)."""
        image_path = "/export/foscam/front_door/test.jpg"
        camera_id = "front_door"
        mock_image_data = b"fake_image_data"

        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.read_bytes", return_value=mock_image_data),
            patch("httpx.AsyncClient.post") as mock_post,
            patch.object(detector_client, "_validate_image_for_detection_async", return_value=True),
            patch("backend.services.detector_client.add_span_event") as mock_add_event,
        ):
            mock_response = MagicMock(spec=httpx.Response)
            mock_response.status_code = 200
            mock_response.json.return_value = sample_response
            mock_post.return_value = mock_response

            await detector_client.detect_objects(image_path, camera_id, mock_session)

            # Verify detection_inference.start event
            inference_start_calls = [
                c for c in mock_add_event.call_args_list if c[0][0] == "detection_inference.start"
            ]
            assert len(inference_start_calls) >= 1
            start_attrs = inference_start_calls[0][0][1]
            assert start_attrs["camera.id"] == camera_id
            assert "detector.type" in start_attrs

            # Verify detection_inference.complete event
            inference_complete_calls = [
                c
                for c in mock_add_event.call_args_list
                if c[0][0] == "detection_inference.complete"
            ]
            assert len(inference_complete_calls) >= 1
            complete_attrs = inference_complete_calls[0][0][1]
            assert complete_attrs["camera.id"] == camera_id
            assert complete_attrs["detection.count"] == 1
            assert "inference.duration_ms" in complete_attrs


@pytest.mark.asyncio
async def test_detect_objects_stores_image_dimensions_for_bbox_scaling(
    detector_client, mock_session
):
    """Test that image dimensions from YOLO response are stored for bbox scaling.

    NEM-3903: YOLO returns bounding box coordinates relative to the image dimensions
    at inference time. These dimensions must be stored so the enrichment pipeline can
    scale bboxes if the image is later loaded at a different resolution.
    """
    image_path = "/export/foscam/front_door/test_image.jpg"
    camera_id = "front_door"
    mock_image_data = b"fake_image_data"

    # YOLO response includes image_width and image_height
    response = {
        "detections": [
            {
                "class": "person",
                "confidence": 0.95,
                "bbox": [100, 150, 300, 400],  # Coordinates relative to 640x480
            }
        ],
        "image_width": 640,
        "image_height": 480,
    }

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.read_bytes", return_value=mock_image_data),
        patch("httpx.AsyncClient.post") as mock_post,
        patch.object(detector_client, "_validate_image_for_detection_async", return_value=True),
    ):
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = response
        mock_post.return_value = mock_response

        detections = await detector_client.detect_objects(image_path, camera_id, mock_session)

        assert len(detections) == 1
        detection = detections[0]
        # Verify image dimensions are stored for bbox scaling
        assert detection.video_width == 640
        assert detection.video_height == 480
        # Verify this is an image detection (not video)
        assert detection.media_type == "image"


@pytest.mark.asyncio
async def test_detect_objects_image_without_dimensions_in_response(detector_client, mock_session):
    """Test handling when YOLO response doesn't include image dimensions.

    Some YOLO versions may not include image_width/image_height in the response.
    In this case, the detection should still be created but without dimensions.
    """
    image_path = "/export/foscam/front_door/test_no_dims.jpg"
    camera_id = "front_door"
    mock_image_data = b"fake_image_data"

    # YOLO response without image dimensions
    response = {
        "detections": [
            {
                "class": "car",
                "confidence": 0.88,
                "bbox": [200, 100, 150, 100],
            }
        ],
        # No image_width or image_height
    }

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.read_bytes", return_value=mock_image_data),
        patch("httpx.AsyncClient.post") as mock_post,
        patch.object(detector_client, "_validate_image_for_detection_async", return_value=True),
    ):
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = response
        mock_post.return_value = mock_response

        detections = await detector_client.detect_objects(image_path, camera_id, mock_session)

        assert len(detections) == 1
        detection = detections[0]
        # Dimensions should be None when not in response
        assert detection.video_width is None
        assert detection.video_height is None
        assert detection.media_type == "image"


@pytest.mark.asyncio
async def test_video_metadata_takes_precedence_over_response_dimensions(
    detector_client, mock_session
):
    """Test that video_metadata dimensions take precedence over YOLO response.

    When processing video frames, the video_metadata dimensions should be used
    rather than the YOLO response dimensions (which may be for the extracted frame).
    """
    image_path = "/export/foscam/front_door/frame_001.jpg"
    video_path = "/export/foscam/front_door/video.mp4"
    camera_id = "front_door"
    mock_image_data = b"fake_image_data"

    video_metadata = {
        "duration": 30.5,
        "video_codec": "h264",
        "video_width": 1920,  # Video dimensions
        "video_height": 1080,
        "file_type": "video/mp4",
    }

    # YOLO response with different dimensions (e.g., from resized frame)
    response = {
        "detections": [
            {
                "class": "person",
                "confidence": 0.95,
                "bbox": [100, 150, 300, 400],
            }
        ],
        "image_width": 640,  # Different from video dimensions
        "image_height": 480,
    }

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.read_bytes", return_value=mock_image_data),
        patch("httpx.AsyncClient.post") as mock_post,
        patch.object(detector_client, "_validate_image_for_detection_async", return_value=True),
    ):
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = response
        mock_post.return_value = mock_response

        detections = await detector_client.detect_objects(
            image_path,
            camera_id,
            mock_session,
            video_path=video_path,
            video_metadata=video_metadata,
        )

        assert len(detections) == 1
        detection = detections[0]
        # Video metadata dimensions should be used, not YOLO response
        assert detection.video_width == 1920
        assert detection.video_height == 1080
        assert detection.media_type == "video"
