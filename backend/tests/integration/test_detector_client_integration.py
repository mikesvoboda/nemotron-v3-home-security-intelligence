"""Integration tests for DetectorClient service.

These tests use a real SQLite database to verify that the DetectorClient
correctly persists detections and handles various scenarios including
confidence filtering, error handling, and multiple detection scenarios.

HTTP calls to the YOLO26 service are mocked to isolate the tests.
"""

import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest
from sqlalchemy import select

from backend.models.camera import Camera
from backend.models.detection import Detection
from backend.services.detector_client import DetectorClient, DetectorUnavailableError


@pytest.fixture
async def sample_camera(integration_db):
    """Create a sample camera in the database for foreign key requirements.

    Uses unique names and folder paths to prevent conflicts with unique constraints.
    """
    from backend.core.database import get_session

    camera_id = f"test_camera_{uuid.uuid4().hex[:8]}"
    async with get_session() as db:
        camera = Camera(
            id=camera_id,
            name=f"Test Camera {camera_id[-8:]}",
            folder_path=f"/export/foscam/{camera_id}",
            status="online",
        )
        db.add(camera)
        await db.commit()
        await db.refresh(camera)
        return camera


@pytest.fixture
def temp_image_file():
    """Create a temporary image file for testing.

    Creates a valid JPEG image that passes all validation checks,
    including minimum file size requirements (>10KB).
    """
    from PIL import Image

    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        # Create a valid image that's large enough to pass validation
        # Using 640x480 with gradient ensures file size > 10KB
        img = Image.new("RGB", (640, 480), color="red")
        pixels = img.load()
        if pixels is not None:
            for y in range(480):
                for x in range(640):
                    pixels[x, y] = (x % 256, y % 256, (x + y) % 256)
        img.save(f.name, "JPEG", quality=95)
        yield f.name
    # Cleanup happens after test
    Path(f.name).unlink(missing_ok=True)


@pytest.fixture
def detector_client():
    """Create a DetectorClient instance."""
    return DetectorClient()


@pytest.fixture
def detector_client_no_retry():
    """Create a DetectorClient instance with no retries for error handling tests.

    Using max_retries=1 speeds up error handling tests by skipping retry delays.
    """
    return DetectorClient(max_retries=1)


@pytest.fixture
def mock_detector_response():
    """Standard detector response with multiple detections."""
    return {
        "detections": [
            {
                "class": "person",
                "confidence": 0.95,
                "bbox": {"x": 100, "y": 150, "width": 300, "height": 400},
            },
            {
                "class": "car",
                "confidence": 0.88,
                "bbox": {"x": 500, "y": 200, "width": 200, "height": 150},
            },
        ],
        "processing_time_ms": 125.5,
        "image_size": [1920, 1080],
    }


class TestDetectObjectsStoresInDatabase:
    """Tests verifying that detections are persisted to the database."""

    async def test_detect_objects_stores_in_database(
        self,
        integration_db,
        sample_camera,
        temp_image_file,
        detector_client,
        mock_detector_response,
    ):
        """Test that detections are correctly persisted to the database."""
        from backend.core.database import get_session

        # Mock HTTP call to detector
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_detector_response
        mock_response.raise_for_status = MagicMock()

        with patch.object(httpx.AsyncClient, "post", return_value=mock_response):
            async with get_session() as session:
                detections = await detector_client.detect_objects(
                    image_path=temp_image_file,
                    camera_id=sample_camera.id,
                    session=session,
                )

                assert len(detections) == 2

        # Verify detections were persisted by querying the database
        async with get_session() as session:
            result = await session.execute(
                select(Detection).where(Detection.camera_id == sample_camera.id)
            )
            persisted_detections = result.scalars().all()

            assert len(persisted_detections) == 2

            # Verify first detection data
            person_detection = next(d for d in persisted_detections if d.object_type == "person")
            assert person_detection.confidence == 0.95
            assert person_detection.bbox_x == 100
            assert person_detection.bbox_y == 150
            assert person_detection.bbox_width == 300
            assert person_detection.bbox_height == 400
            assert person_detection.file_path == temp_image_file
            assert person_detection.camera_id == sample_camera.id

            # Verify second detection data
            car_detection = next(d for d in persisted_detections if d.object_type == "car")
            assert car_detection.confidence == 0.88
            assert car_detection.bbox_x == 500
            assert car_detection.bbox_y == 200
            assert car_detection.bbox_width == 200
            assert car_detection.bbox_height == 150

    async def test_detect_objects_stores_correct_file_type(
        self, integration_db, sample_camera, detector_client
    ):
        """Test that file type is correctly stored as MIME type."""
        from PIL import Image

        from backend.core.database import get_session

        # Map of extensions to expected MIME types
        extension_to_mime = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
        }

        # Create temp files with different extensions using valid images
        for ext, expected_mime in extension_to_mime.items():
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as f:
                # Create a valid image large enough to pass validation
                # Use larger size for PNG since it compresses better than JPEG
                size = (800, 600)
                img = Image.new("RGB", size, color="blue")
                # Add noise pattern to prevent compression from shrinking file too much
                import random

                random.seed(42)  # Reproducible randomness
                pixels = img.load()
                if pixels is not None:
                    for y in range(size[1]):
                        for x in range(size[0]):
                            # Add random noise to prevent PNG compression from being too effective

                            r = (x + random.randint(0, 50)) % 256  # noqa: S311
                            g = (y + random.randint(0, 50)) % 256  # noqa: S311
                            b = ((x + y) + random.randint(0, 50)) % 256  # noqa: S311
                            pixels[x, y] = (r, g, b)
                format_name = "JPEG" if ext in (".jpg", ".jpeg") else "PNG"
                img.save(f.name, format_name, quality=95 if format_name == "JPEG" else None)
                temp_path = f.name

            try:
                response_data = {
                    "detections": [
                        {
                            "class": "person",
                            "confidence": 0.92,
                            "bbox": [100, 150, 200, 300],
                        }
                    ],
                    "processing_time_ms": 50.0,
                    "image_size": [1920, 1080],
                }

                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = response_data
                mock_response.raise_for_status = MagicMock()

                with patch.object(httpx.AsyncClient, "post", return_value=mock_response):
                    async with get_session() as session:
                        detections = await detector_client.detect_objects(
                            image_path=temp_path,
                            camera_id=sample_camera.id,
                            session=session,
                        )

                        assert len(detections) == 1
                        assert detections[0].file_type == expected_mime
            finally:
                Path(temp_path).unlink(missing_ok=True)


class TestConfidenceFiltering:
    """Tests verifying confidence threshold filtering."""

    async def test_detect_objects_filters_low_confidence(
        self, integration_db, sample_camera, temp_image_file, detector_client
    ):
        """Test that detections below confidence threshold are filtered out."""
        from backend.core.database import get_session

        # Response with detections at varying confidence levels
        response_data = {
            "detections": [
                {"class": "person", "confidence": 0.95, "bbox": [100, 150, 200, 300]},
                {"class": "car", "confidence": 0.60, "bbox": [200, 250, 150, 200]},
                {
                    "class": "dog",
                    "confidence": 0.45,
                    "bbox": [300, 350, 100, 120],
                },  # Below threshold
                {
                    "class": "cat",
                    "confidence": 0.30,
                    "bbox": [400, 450, 80, 100],
                },  # Below threshold
            ],
            "processing_time_ms": 100.0,
            "image_size": [1920, 1080],
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = response_data
        mock_response.raise_for_status = MagicMock()

        with patch.object(httpx.AsyncClient, "post", return_value=mock_response):
            async with get_session() as session:
                detections = await detector_client.detect_objects(
                    image_path=temp_image_file,
                    camera_id=sample_camera.id,
                    session=session,
                )

        # Default threshold is 0.5, so only person (0.95) and car (0.60) should pass
        assert len(detections) == 2
        object_types = [d.object_type for d in detections]
        assert "person" in object_types
        assert "car" in object_types
        assert "dog" not in object_types
        assert "cat" not in object_types

        # Verify in database as well
        async with get_session() as session:
            result = await session.execute(
                select(Detection).where(Detection.camera_id == sample_camera.id)
            )
            persisted = result.scalars().all()
            assert len(persisted) == 2

    async def test_detect_objects_all_below_threshold(
        self, integration_db, sample_camera, temp_image_file, detector_client
    ):
        """Test that no detections are stored when all are below threshold."""
        from backend.core.database import get_session

        response_data = {
            "detections": [
                {"class": "dog", "confidence": 0.40, "bbox": [100, 150, 200, 300]},
                {"class": "cat", "confidence": 0.35, "bbox": [200, 250, 150, 200]},
            ],
            "processing_time_ms": 50.0,
            "image_size": [1920, 1080],
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = response_data
        mock_response.raise_for_status = MagicMock()

        with patch.object(httpx.AsyncClient, "post", return_value=mock_response):
            async with get_session() as session:
                detections = await detector_client.detect_objects(
                    image_path=temp_image_file,
                    camera_id=sample_camera.id,
                    session=session,
                )

        assert len(detections) == 0

        # Verify nothing was stored
        async with get_session() as session:
            result = await session.execute(
                select(Detection).where(Detection.camera_id == sample_camera.id)
            )
            assert len(result.scalars().all()) == 0


class TestConnectionErrorHandling:
    """Tests for handling connection errors with DetectorUnavailableError."""

    async def test_detect_objects_handles_connection_error(
        self, integration_db, sample_camera, temp_image_file, detector_client_no_retry
    ):
        """Test that connection errors raise DetectorUnavailableError for retry handling."""
        from backend.core.database import get_session

        with patch.object(
            httpx.AsyncClient, "post", side_effect=httpx.ConnectError("Connection refused")
        ):
            async with get_session() as session:
                # Connection errors should raise DetectorUnavailableError to allow retry
                with pytest.raises(DetectorUnavailableError) as exc_info:
                    await detector_client_no_retry.detect_objects(
                        image_path=temp_image_file,
                        camera_id=sample_camera.id,
                        session=session,
                    )

                # After retry exhaustion, error message indicates failed attempts
                assert "failed after" in str(exc_info.value).lower()
                # Original error is preserved for inspection
                assert isinstance(exc_info.value.original_error, httpx.ConnectError)

        # Verify nothing was stored
        async with get_session() as session:
            result = await session.execute(
                select(Detection).where(Detection.camera_id == sample_camera.id)
            )
            assert len(result.scalars().all()) == 0


class TestTimeoutHandling:
    """Tests for handling timeout scenarios with DetectorUnavailableError."""

    async def test_detect_objects_handles_timeout(
        self, integration_db, sample_camera, temp_image_file, detector_client_no_retry
    ):
        """Test that timeouts raise DetectorUnavailableError for retry handling."""
        from backend.core.database import get_session

        with patch.object(
            httpx.AsyncClient, "post", side_effect=httpx.TimeoutException("Request timeout")
        ):
            async with get_session() as session:
                # Timeouts should raise DetectorUnavailableError to allow retry
                with pytest.raises(DetectorUnavailableError) as exc_info:
                    await detector_client_no_retry.detect_objects(
                        image_path=temp_image_file,
                        camera_id=sample_camera.id,
                        session=session,
                    )

                # After retry exhaustion, error message indicates failed attempts
                assert "failed after" in str(exc_info.value).lower()
                # Original error is preserved for inspection
                assert isinstance(exc_info.value.original_error, httpx.TimeoutException)

        # Verify nothing was stored
        async with get_session() as session:
            result = await session.execute(
                select(Detection).where(Detection.camera_id == sample_camera.id)
            )
            assert len(result.scalars().all()) == 0


class TestMultipleDetectionsSameImage:
    """Tests for handling multiple objects detected in same image."""

    async def test_detect_objects_multiple_detections_same_image(
        self, integration_db, sample_camera, temp_image_file, detector_client
    ):
        """Test handling multiple objects of same and different types in one image."""
        from backend.core.database import get_session

        response_data = {
            "detections": [
                {"class": "person", "confidence": 0.95, "bbox": [100, 150, 80, 200]},
                {"class": "person", "confidence": 0.90, "bbox": [300, 150, 85, 210]},
                {"class": "person", "confidence": 0.87, "bbox": [500, 160, 75, 195]},
                {"class": "car", "confidence": 0.92, "bbox": [700, 200, 300, 180]},
                {"class": "bicycle", "confidence": 0.78, "bbox": [150, 250, 60, 100]},
            ],
            "processing_time_ms": 175.0,
            "image_size": [1920, 1080],
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = response_data
        mock_response.raise_for_status = MagicMock()

        with patch.object(httpx.AsyncClient, "post", return_value=mock_response):
            async with get_session() as session:
                detections = await detector_client.detect_objects(
                    image_path=temp_image_file,
                    camera_id=sample_camera.id,
                    session=session,
                )

        assert len(detections) == 5

        # Count object types
        object_types = [d.object_type for d in detections]
        assert object_types.count("person") == 3
        assert object_types.count("car") == 1
        assert object_types.count("bicycle") == 1

        # All detections should have same file path and camera
        for detection in detections:
            assert detection.file_path == temp_image_file
            assert detection.camera_id == sample_camera.id
            assert detection.detected_at is not None

        # Verify persistence
        async with get_session() as session:
            result = await session.execute(
                select(Detection).where(Detection.camera_id == sample_camera.id)
            )
            persisted = result.scalars().all()
            assert len(persisted) == 5


class TestHealthCheckIntegration:
    """Tests for the health check endpoint."""

    async def test_health_check_integration_success(self, detector_client):
        """Test health check returns True when detector is healthy."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "healthy"}
        mock_response.raise_for_status = MagicMock()

        with patch.object(httpx.AsyncClient, "get", return_value=mock_response):
            result = await detector_client.health_check()

        assert result is True

    async def test_health_check_integration_connection_error(self, detector_client):
        """Test health check returns False when connection fails."""
        with patch.object(
            httpx.AsyncClient, "get", side_effect=httpx.ConnectError("Connection refused")
        ):
            result = await detector_client.health_check()

        assert result is False

    async def test_health_check_integration_timeout(self, detector_client):
        """Test health check returns False when request times out."""
        with patch.object(httpx.AsyncClient, "get", side_effect=httpx.TimeoutException("Timeout")):
            result = await detector_client.health_check()

        assert result is False

    async def test_health_check_integration_http_error(self, detector_client):
        """Test health check returns False when HTTP error returned."""
        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Service Unavailable", request=MagicMock(), response=mock_response
        )

        with patch.object(httpx.AsyncClient, "get", return_value=mock_response):
            result = await detector_client.health_check()

        assert result is False


class TestBadResponseHandling:
    """Tests for handling malformed or bad responses from detector."""

    async def test_detect_objects_handles_http_error(
        self, integration_db, sample_camera, temp_image_file, detector_client_no_retry
    ):
        """Test that HTTP 5xx errors raise DetectorUnavailableError for retry handling."""
        from backend.core.database import get_session

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Internal Server Error", request=MagicMock(), response=mock_response
        )

        with patch.object(httpx.AsyncClient, "post", return_value=mock_response):
            async with get_session() as session:
                # 5xx errors should raise DetectorUnavailableError to allow retry
                with pytest.raises(DetectorUnavailableError) as exc_info:
                    await detector_client_no_retry.detect_objects(
                        image_path=temp_image_file,
                        camera_id=sample_camera.id,
                        session=session,
                    )

                # After retry exhaustion, error message indicates failed attempts
                assert "failed after" in str(exc_info.value).lower()
                # Original error is preserved for inspection
                assert isinstance(exc_info.value.original_error, httpx.HTTPStatusError)

    async def test_detect_objects_handles_missing_detections_key(
        self, integration_db, sample_camera, temp_image_file, detector_client
    ):
        """Test handling when response is missing 'detections' key."""
        from backend.core.database import get_session

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"wrong_key": "no detections field"}
        mock_response.raise_for_status = MagicMock()

        with patch.object(httpx.AsyncClient, "post", return_value=mock_response):
            async with get_session() as session:
                detections = await detector_client.detect_objects(
                    image_path=temp_image_file,
                    camera_id=sample_camera.id,
                    session=session,
                )

        assert detections == []

    async def test_detect_objects_handles_invalid_bbox_format(
        self, integration_db, sample_camera, temp_image_file, detector_client
    ):
        """Test handling when bbox has invalid format."""
        from backend.core.database import get_session

        response_data = {
            "detections": [
                {
                    "class": "person",
                    "confidence": 0.95,
                    "bbox": [100, 150],
                },  # Invalid - only 2 values
                {"class": "car", "confidence": 0.90, "bbox": {"x": 200, "y": 300}},  # Missing w/h
                {"class": "dog", "confidence": 0.85, "bbox": [300, 400, 100, 150]},  # Valid
            ],
            "processing_time_ms": 75.0,
            "image_size": [1920, 1080],
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = response_data
        mock_response.raise_for_status = MagicMock()

        with patch.object(httpx.AsyncClient, "post", return_value=mock_response):
            async with get_session() as session:
                detections = await detector_client.detect_objects(
                    image_path=temp_image_file,
                    camera_id=sample_camera.id,
                    session=session,
                )

        # Only the valid dog detection should be stored
        assert len(detections) == 1
        assert detections[0].object_type == "dog"


class TestBboxFormatHandling:
    """Tests for handling different bbox format types (dict vs array)."""

    async def test_detect_objects_with_dict_bbox_format(
        self, integration_db, sample_camera, temp_image_file, detector_client
    ):
        """Test detection with dict bbox format from YOLO26."""
        from backend.core.database import get_session

        response_data = {
            "detections": [
                {
                    "class": "person",
                    "confidence": 0.95,
                    "bbox": {"x": 100, "y": 150, "width": 300, "height": 400},
                }
            ],
            "processing_time_ms": 50.0,
            "image_size": [1920, 1080],
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = response_data
        mock_response.raise_for_status = MagicMock()

        with patch.object(httpx.AsyncClient, "post", return_value=mock_response):
            async with get_session() as session:
                detections = await detector_client.detect_objects(
                    image_path=temp_image_file,
                    camera_id=sample_camera.id,
                    session=session,
                )

        assert len(detections) == 1
        assert detections[0].bbox_x == 100
        assert detections[0].bbox_y == 150
        assert detections[0].bbox_width == 300
        assert detections[0].bbox_height == 400

    async def test_detect_objects_with_array_bbox_format(
        self, integration_db, sample_camera, temp_image_file, detector_client
    ):
        """Test detection with array bbox format for backwards compatibility."""
        from backend.core.database import get_session

        response_data = {
            "detections": [
                {
                    "class": "person",
                    "confidence": 0.92,
                    "bbox": [200, 250, 150, 350],  # Array format [x, y, width, height]
                }
            ],
            "processing_time_ms": 50.0,
            "image_size": [1920, 1080],
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = response_data
        mock_response.raise_for_status = MagicMock()

        with patch.object(httpx.AsyncClient, "post", return_value=mock_response):
            async with get_session() as session:
                detections = await detector_client.detect_objects(
                    image_path=temp_image_file,
                    camera_id=sample_camera.id,
                    session=session,
                )

        assert len(detections) == 1
        assert detections[0].bbox_x == 200
        assert detections[0].bbox_y == 250
        assert detections[0].bbox_width == 150
        assert detections[0].bbox_height == 350


class TestFileNotFound:
    """Tests for handling missing image files."""

    async def test_detect_objects_file_not_found(
        self, integration_db, sample_camera, detector_client
    ):
        """Test handling when image file does not exist."""
        from backend.core.database import get_session

        non_existent_path = "/export/foscam/test/nonexistent_image.jpg"

        async with get_session() as session:
            detections = await detector_client.detect_objects(
                image_path=non_existent_path,
                camera_id=sample_camera.id,
                session=session,
            )

        assert detections == []


class TestEmptyDetections:
    """Tests for handling empty detection responses."""

    async def test_detect_objects_empty_detections_array(
        self, integration_db, sample_camera, temp_image_file, detector_client
    ):
        """Test handling when detector returns empty detections array."""
        from backend.core.database import get_session

        response_data = {
            "detections": [],
            "processing_time_ms": 30.0,
            "image_size": [1920, 1080],
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = response_data
        mock_response.raise_for_status = MagicMock()

        with patch.object(httpx.AsyncClient, "post", return_value=mock_response):
            async with get_session() as session:
                detections = await detector_client.detect_objects(
                    image_path=temp_image_file,
                    camera_id=sample_camera.id,
                    session=session,
                )

        assert detections == []

        # Verify nothing was stored
        async with get_session() as session:
            result = await session.execute(
                select(Detection).where(Detection.camera_id == sample_camera.id)
            )
            assert len(result.scalars().all()) == 0


class TestTimestampHandling:
    """Tests for detection timestamp handling."""

    async def test_detect_objects_sets_detected_at_timestamp(
        self, integration_db, sample_camera, temp_image_file, detector_client
    ):
        """Test that detected_at timestamp is set correctly."""
        from backend.core.database import get_session

        before_detection = datetime.now(UTC)

        response_data = {
            "detections": [
                {"class": "person", "confidence": 0.95, "bbox": [100, 150, 200, 300]},
            ],
            "processing_time_ms": 50.0,
            "image_size": [1920, 1080],
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = response_data
        mock_response.raise_for_status = MagicMock()

        with patch.object(httpx.AsyncClient, "post", return_value=mock_response):
            async with get_session() as session:
                detections = await detector_client.detect_objects(
                    image_path=temp_image_file,
                    camera_id=sample_camera.id,
                    session=session,
                )

        after_detection = datetime.now(UTC)

        assert len(detections) == 1
        detected_at = detections[0].detected_at

        # The timestamp should be between before and after detection
        # Note: detected_at may not have timezone info depending on how it's stored
        if detected_at.tzinfo is None:
            # Make comparison with naive datetimes
            before_naive = before_detection.replace(tzinfo=None)
            after_naive = after_detection.replace(tzinfo=None)
            assert before_naive <= detected_at <= after_naive
        else:
            assert before_detection <= detected_at <= after_detection


class TestBaselineUpdatesOnDetection:
    """Tests verifying that baseline updates occur during detection processing (NEM-1259)."""

    async def test_detect_objects_updates_baseline(
        self,
        integration_db,
        sample_camera,
        temp_image_file,
        detector_client,
        mock_detector_response,
    ):
        """Test that baseline is updated when detections are stored (NEM-1259).

        This test verifies the fix for the Analytics page being empty because
        update_baseline() was never called during detection processing.
        """
        from backend.core.database import get_session
        from backend.models.baseline import ActivityBaseline, ClassBaseline
        from backend.services.baseline import reset_baseline_service

        # Reset baseline service singleton to ensure clean state
        reset_baseline_service()

        # Mock HTTP call to detector
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_detector_response
        mock_response.raise_for_status = MagicMock()

        with patch.object(httpx.AsyncClient, "post", return_value=mock_response):
            async with get_session() as session:
                detections = await detector_client.detect_objects(
                    image_path=temp_image_file,
                    camera_id=sample_camera.id,
                    session=session,
                )

                assert len(detections) == 2

        # Verify baseline tables were updated
        async with get_session() as session:
            # Check ActivityBaseline records were created
            activity_result = await session.execute(
                select(ActivityBaseline).where(ActivityBaseline.camera_id == sample_camera.id)
            )
            activity_baselines = activity_result.scalars().all()

            # Should have at least 1 activity baseline entry (for the hour/day when detection occurred)
            assert len(activity_baselines) >= 1

            # Check ClassBaseline records were created
            class_result = await session.execute(
                select(ClassBaseline).where(ClassBaseline.camera_id == sample_camera.id)
            )
            class_baselines = class_result.scalars().all()

            # Should have 2 class baselines - one for "person" and one for "car"
            assert len(class_baselines) == 2

            # Verify the detected classes are present
            detected_classes = {cb.detection_class for cb in class_baselines}
            assert "person" in detected_classes
            assert "car" in detected_classes

            # Verify sample counts are greater than 0
            for cb in class_baselines:
                assert cb.sample_count >= 1
                assert cb.frequency > 0

    async def test_detect_objects_no_baseline_update_when_no_detections(
        self,
        integration_db,
        sample_camera,
        temp_image_file,
        detector_client,
    ):
        """Test that no baseline update occurs when all detections are filtered out."""
        from backend.core.database import get_session
        from backend.models.baseline import ActivityBaseline, ClassBaseline
        from backend.services.baseline import reset_baseline_service

        # Reset baseline service singleton to ensure clean state
        reset_baseline_service()

        # Response with all detections below threshold
        response_data = {
            "detections": [
                {"class": "dog", "confidence": 0.40, "bbox": [100, 150, 200, 300]},
                {"class": "cat", "confidence": 0.35, "bbox": [200, 250, 150, 200]},
            ],
            "processing_time_ms": 50.0,
            "image_size": [1920, 1080],
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = response_data
        mock_response.raise_for_status = MagicMock()

        with patch.object(httpx.AsyncClient, "post", return_value=mock_response):
            async with get_session() as session:
                detections = await detector_client.detect_objects(
                    image_path=temp_image_file,
                    camera_id=sample_camera.id,
                    session=session,
                )

        # No detections stored (all below threshold)
        assert len(detections) == 0

        # Verify no baseline records were created
        async with get_session() as session:
            activity_result = await session.execute(
                select(ActivityBaseline).where(ActivityBaseline.camera_id == sample_camera.id)
            )
            assert len(activity_result.scalars().all()) == 0

            class_result = await session.execute(
                select(ClassBaseline).where(ClassBaseline.camera_id == sample_camera.id)
            )
            assert len(class_result.scalars().all()) == 0

    async def test_detect_objects_baseline_accumulates(
        self,
        integration_db,
        sample_camera,
        temp_image_file,
        detector_client,
    ):
        """Test that multiple detections accumulate in baseline statistics."""
        from backend.core.database import get_session
        from backend.models.baseline import ClassBaseline
        from backend.services.baseline import reset_baseline_service

        # Reset baseline service singleton to ensure clean state
        reset_baseline_service()

        # First detection batch - just a person
        response_data_1 = {
            "detections": [
                {"class": "person", "confidence": 0.95, "bbox": [100, 150, 200, 300]},
            ],
            "processing_time_ms": 50.0,
            "image_size": [1920, 1080],
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = response_data_1
        mock_response.raise_for_status = MagicMock()

        with patch.object(httpx.AsyncClient, "post", return_value=mock_response):
            async with get_session() as session:
                detections = await detector_client.detect_objects(
                    image_path=temp_image_file,
                    camera_id=sample_camera.id,
                    session=session,
                )
                assert len(detections) == 1

        # Check initial sample count
        async with get_session() as session:
            result = await session.execute(
                select(ClassBaseline).where(
                    ClassBaseline.camera_id == sample_camera.id,
                    ClassBaseline.detection_class == "person",
                )
            )
            person_baseline = result.scalar_one()
            initial_sample_count = person_baseline.sample_count

        # Second detection batch - another person
        with patch.object(httpx.AsyncClient, "post", return_value=mock_response):
            async with get_session() as session:
                detections = await detector_client.detect_objects(
                    image_path=temp_image_file,
                    camera_id=sample_camera.id,
                    session=session,
                )
                assert len(detections) == 1

        # Check sample count increased
        async with get_session() as session:
            result = await session.execute(
                select(ClassBaseline).where(
                    ClassBaseline.camera_id == sample_camera.id,
                    ClassBaseline.detection_class == "person",
                )
            )
            person_baseline = result.scalar_one()
            assert person_baseline.sample_count > initial_sample_count
