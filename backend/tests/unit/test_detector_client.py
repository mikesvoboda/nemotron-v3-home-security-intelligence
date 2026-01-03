"""Unit tests for detector client service."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.detector_client import DetectorClient, DetectorUnavailableError

# Fixtures


@pytest.fixture
def mock_session():
    """Mock database session."""
    session = AsyncMock(spec=AsyncSession)
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.fixture
def detector_client():
    """Create detector client instance."""
    return DetectorClient()


@pytest.fixture
def sample_detector_response():
    """Sample response from RT-DETRv2 detector."""
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
        patch.object(detector_client, "_validate_image_for_detection", return_value=True),
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
        patch.object(detector_client, "_validate_image_for_detection", return_value=True),
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
        patch.object(detector_client, "_validate_image_for_detection", return_value=True),
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
    """Test that connection errors raise DetectorUnavailableError for retry."""
    image_path = "/export/foscam/front_door/image_004.jpg"
    camera_id = "front_door"

    mock_image_data = b"fake_image_data"

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.read_bytes", return_value=mock_image_data),
        patch("httpx.AsyncClient.post", side_effect=httpx.ConnectError("Connection refused")),
        patch.object(detector_client, "_validate_image_for_detection", return_value=True),
    ):
        with pytest.raises(DetectorUnavailableError) as exc_info:
            await detector_client.detect_objects(image_path, camera_id, mock_session)

        assert "Connection refused" in str(exc_info.value)
        assert exc_info.value.original_error is not None
        assert not mock_session.add.called


@pytest.mark.asyncio
async def test_detect_objects_timeout_raises_exception(detector_client, mock_session):
    """Test that timeout errors raise DetectorUnavailableError for retry."""
    image_path = "/export/foscam/front_door/image_005.jpg"
    camera_id = "front_door"

    mock_image_data = b"fake_image_data"

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.read_bytes", return_value=mock_image_data),
        patch("httpx.AsyncClient.post", side_effect=httpx.TimeoutException("Request timeout")),
        patch.object(detector_client, "_validate_image_for_detection", return_value=True),
    ):
        with pytest.raises(DetectorUnavailableError) as exc_info:
            await detector_client.detect_objects(image_path, camera_id, mock_session)

        assert "timed out" in str(exc_info.value)
        assert not mock_session.add.called


@pytest.mark.asyncio
async def test_detect_objects_server_error_raises_exception(detector_client, mock_session):
    """Test that HTTP 5xx errors raise DetectorUnavailableError for retry."""
    image_path = "/export/foscam/front_door/image_006.jpg"
    camera_id = "front_door"

    mock_image_data = b"fake_image_data"

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.read_bytes", return_value=mock_image_data),
        patch("httpx.AsyncClient.post") as mock_post,
        patch.object(detector_client, "_validate_image_for_detection", return_value=True),
    ):
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Internal Server Error", request=MagicMock(spec=httpx.Request), response=mock_response
        )
        mock_post.return_value = mock_response

        with pytest.raises(DetectorUnavailableError) as exc_info:
            await detector_client.detect_objects(image_path, camera_id, mock_session)

        assert "server error: 500" in str(exc_info.value)
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
        patch.object(detector_client, "_validate_image_for_detection", return_value=True),
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
    """Test that invalid JSON raises DetectorUnavailableError for retry.

    Invalid JSON could indicate a server-side issue (corrupt response,
    partial response, etc.) so it should be retried.
    """
    image_path = "/export/foscam/front_door/image_007.jpg"
    camera_id = "front_door"

    mock_image_data = b"fake_image_data"

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.read_bytes", return_value=mock_image_data),
        patch("httpx.AsyncClient.post") as mock_post,
        patch.object(detector_client, "_validate_image_for_detection", return_value=True),
    ):
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
        mock_post.return_value = mock_response

        with pytest.raises(DetectorUnavailableError) as exc_info:
            await detector_client.detect_objects(image_path, camera_id, mock_session)

        assert "Invalid JSON" in str(exc_info.value)
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
        patch.object(detector_client, "_validate_image_for_detection", return_value=True),
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
        mock_settings.return_value.rtdetr_url = "http://custom-detector:9000"
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
        patch.object(detector_client, "_validate_image_for_detection", return_value=True),
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
        patch.object(detector_client, "_validate_image_for_detection", return_value=True),
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
        patch.object(detector_client, "_validate_image_for_detection", return_value=True),
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
        patch.object(detector_client, "_validate_image_for_detection", return_value=True),
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
        patch("backend.services.detector_client.Detection", side_effect=Exception("DB error")),
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
    """Test that HTTP 502 Bad Gateway raises DetectorUnavailableError."""
    image_path = "/export/foscam/front_door/image_502.jpg"
    camera_id = "front_door"
    mock_image_data = b"fake_image_data"

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.read_bytes", return_value=mock_image_data),
        patch("httpx.AsyncClient.post") as mock_post,
        patch.object(detector_client, "_validate_image_for_detection", return_value=True),
    ):
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 502
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Bad Gateway", request=MagicMock(spec=httpx.Request), response=mock_response
        )
        mock_post.return_value = mock_response

        with pytest.raises(DetectorUnavailableError) as exc_info:
            await detector_client.detect_objects(image_path, camera_id, mock_session)

        assert "502" in str(exc_info.value)


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
        patch.object(detector_client, "_validate_image_for_detection", return_value=True),
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
        patch.object(detector_client, "_validate_image_for_detection", return_value=True),
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
    """Test that unexpected errors raise DetectorUnavailableError."""
    image_path = "/export/foscam/front_door/image_unexpected.jpg"
    camera_id = "front_door"
    mock_image_data = b"fake_image_data"

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.read_bytes", return_value=mock_image_data),
        patch("httpx.AsyncClient.post", side_effect=RuntimeError("Unexpected error")),
        patch.object(detector_client, "_validate_image_for_detection", return_value=True),
    ):
        with pytest.raises(DetectorUnavailableError) as exc_info:
            await detector_client.detect_objects(image_path, camera_id, mock_session)

        assert "Unexpected" in str(exc_info.value)


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
        patch.object(detector_client, "_validate_image_for_detection", return_value=True),
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
async def test_detect_objects_no_camera_update_when_no_detections(detector_client, mock_session):
    """Test that camera's last_seen_at is NOT updated when no detections are found."""
    image_path = "/export/foscam/front_door/image_empty.jpg"
    camera_id = "front_door"

    mock_image_data = b"fake_image_data"
    empty_response = {"detections": [], "processing_time_ms": 50.0, "image_size": [1920, 1080]}

    mock_session.get = AsyncMock()

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.read_bytes", return_value=mock_image_data),
        patch("httpx.AsyncClient.post") as mock_post,
        patch.object(detector_client, "_validate_image_for_detection", return_value=True),
    ):
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = empty_response
        mock_post.return_value = mock_response

        detections = await detector_client.detect_objects(image_path, camera_id, mock_session)

        assert len(detections) == 0
        # Verify camera was NOT fetched (no detections = no update)
        mock_session.get.assert_not_called()


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
        patch.object(detector_client, "_validate_image_for_detection", return_value=True),
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
        patch.object(detector_client, "_validate_image_for_detection", return_value=False),
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
