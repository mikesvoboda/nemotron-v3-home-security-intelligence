"""Unit tests for detector client service."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.detector_client import DetectorClient, DetectorServiceError

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
        mock_response = MagicMock()
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
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Internal Server Error", request=MagicMock(), response=mock_response
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
    ):
        # Mock detector response
        mock_response = MagicMock()
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
    ):
        mock_response = MagicMock()
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
    ):
        mock_response = MagicMock()
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
async def test_detect_objects_connection_error(detector_client, mock_session):
    """Test that connection errors raise DetectorServiceError for retry handling."""
    image_path = "/export/foscam/front_door/image_004.jpg"
    camera_id = "front_door"

    mock_image_data = b"fake_image_data"

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.read_bytes", return_value=mock_image_data),
        patch("httpx.AsyncClient.post", side_effect=httpx.ConnectError("Connection refused")),
    ):
        # Connection errors should raise DetectorServiceError to allow retry
        with pytest.raises(DetectorServiceError) as exc_info:
            await detector_client.detect_objects(image_path, camera_id, mock_session)

        assert "Cannot connect to RT-DETR service" in str(exc_info.value)
        assert exc_info.value.cause is not None
        assert not mock_session.add.called


@pytest.mark.asyncio
async def test_detect_objects_timeout(detector_client, mock_session):
    """Test that timeouts raise DetectorServiceError for retry handling."""
    image_path = "/export/foscam/front_door/image_005.jpg"
    camera_id = "front_door"

    mock_image_data = b"fake_image_data"

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.read_bytes", return_value=mock_image_data),
        patch("httpx.AsyncClient.post", side_effect=httpx.TimeoutException("Request timeout")),
    ):
        # Timeouts should raise DetectorServiceError to allow retry
        with pytest.raises(DetectorServiceError) as exc_info:
            await detector_client.detect_objects(image_path, camera_id, mock_session)

        assert "timed out" in str(exc_info.value)
        assert exc_info.value.cause is not None
        assert not mock_session.add.called


@pytest.mark.asyncio
async def test_detect_objects_http_error_5xx(detector_client, mock_session):
    """Test that HTTP 5xx errors raise DetectorServiceError for retry handling."""
    image_path = "/export/foscam/front_door/image_006.jpg"
    camera_id = "front_door"

    mock_image_data = b"fake_image_data"

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.read_bytes", return_value=mock_image_data),
        patch("httpx.AsyncClient.post") as mock_post,
    ):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Internal Server Error", request=MagicMock(), response=mock_response
        )
        mock_post.return_value = mock_response

        # 5xx errors should raise DetectorServiceError to allow retry
        with pytest.raises(DetectorServiceError) as exc_info:
            await detector_client.detect_objects(image_path, camera_id, mock_session)

        assert "HTTP 500" in str(exc_info.value)
        assert not mock_session.add.called


@pytest.mark.asyncio
async def test_detect_objects_http_error_4xx(detector_client, mock_session):
    """Test that HTTP 4xx errors return empty list (no retry - client error)."""
    image_path = "/export/foscam/front_door/image_006b.jpg"
    camera_id = "front_door"

    mock_image_data = b"fake_image_data"

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.read_bytes", return_value=mock_image_data),
        patch("httpx.AsyncClient.post") as mock_post,
    ):
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Bad Request", request=MagicMock(), response=mock_response
        )
        mock_post.return_value = mock_response

        # 4xx errors return empty list - no retry (client error)
        detections = await detector_client.detect_objects(image_path, camera_id, mock_session)

        assert len(detections) == 0
        assert not mock_session.add.called


@pytest.mark.asyncio
async def test_detect_objects_invalid_json(detector_client, mock_session):
    """Test that invalid JSON raises DetectorServiceError for retry handling."""
    image_path = "/export/foscam/front_door/image_007.jpg"
    camera_id = "front_door"

    mock_image_data = b"fake_image_data"

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.read_bytes", return_value=mock_image_data),
        patch("httpx.AsyncClient.post") as mock_post,
    ):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
        mock_post.return_value = mock_response

        # JSON decode errors are treated as transient and should be retried
        with pytest.raises(DetectorServiceError) as exc_info:
            await detector_client.detect_objects(image_path, camera_id, mock_session)

        assert "Unexpected error" in str(exc_info.value)
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
    ):
        mock_response = MagicMock()
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
    """Test that file type is correctly extracted from path."""
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
    ):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = response
        mock_post.return_value = mock_response

        detections = await detector_client.detect_objects(image_path, camera_id, mock_session)

        assert len(detections) == 1
        assert detections[0].file_type == ".jpeg"


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
    ):
        mock_response = MagicMock()
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
    ):
        mock_response = MagicMock()
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
    ):
        mock_response = MagicMock()
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
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = response
        mock_post.return_value = mock_response

        detections = await detector_client.detect_objects(image_path, camera_id, mock_session)

        # Should handle exception and return empty list
        assert len(detections) == 0
