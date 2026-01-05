"""Integration tests for detections API endpoints.

Uses shared fixtures from conftest.py:
- integration_db: Clean SQLite test database
- mock_redis: Mock Redis client
- db_session: AsyncSession for database
- client: httpx AsyncClient with test app
"""

import uuid
from datetime import datetime

import pytest


# Alias for backward compatibility - tests use async_client but conftest provides client
@pytest.fixture
async def async_client(client):
    """Alias for shared client fixture for backward compatibility."""
    yield client


@pytest.fixture
async def clean_detections(integration_db):
    """Delete detections and related tables data before test runs for proper isolation.

    This ensures tests that expect specific detection counts start with empty tables.
    Uses DELETE instead of TRUNCATE to avoid AccessExclusiveLock deadlocks
    when tests run in parallel with xdist.
    """
    from sqlalchemy import text

    from backend.core.database import get_engine

    async with get_engine().begin() as conn:
        # Delete in order respecting foreign key constraints
        await conn.execute(text("DELETE FROM detections"))  # nosemgrep: avoid-sqlalchemy-text
        await conn.execute(text("DELETE FROM events"))  # nosemgrep: avoid-sqlalchemy-text
        await conn.execute(text("DELETE FROM cameras"))  # nosemgrep: avoid-sqlalchemy-text

    yield

    # Cleanup after test too (best effort)
    try:
        async with get_engine().begin() as conn:
            await conn.execute(text("DELETE FROM detections"))  # nosemgrep: avoid-sqlalchemy-text
            await conn.execute(text("DELETE FROM events"))  # nosemgrep: avoid-sqlalchemy-text
            await conn.execute(text("DELETE FROM cameras"))  # nosemgrep: avoid-sqlalchemy-text
    except Exception:  # noqa: S110 - ignore cleanup errors
        pass


@pytest.fixture
async def sample_camera(integration_db):
    """Create a sample camera in the database.

    Uses unique names and folder paths to prevent conflicts with unique constraints.
    """
    from backend.core.database import get_session
    from backend.models.camera import Camera

    camera_id = str(uuid.uuid4())
    unique_suffix = uuid.uuid4().hex[:8]
    async with get_session() as db:
        camera = Camera(
            id=camera_id,
            name=f"Front Door {unique_suffix}",
            folder_path=f"/export/foscam/front_door_{unique_suffix}",
            status="online",
        )
        db.add(camera)
        await db.commit()
        await db.refresh(camera)
        yield camera


@pytest.fixture
async def sample_detection(integration_db, sample_camera):
    """Create a sample detection in the database."""
    from backend.core.database import get_session
    from backend.models.detection import Detection

    async with get_session() as db:
        detection = Detection(
            camera_id=sample_camera.id,
            file_path="/export/foscam/front_door/test_image.jpg",
            file_type="image/jpeg",
            detected_at=datetime(2025, 12, 23, 12, 0, 0),
            object_type="person",
            confidence=0.95,
            bbox_x=100,
            bbox_y=150,
            bbox_width=200,
            bbox_height=400,
        )
        db.add(detection)
        await db.commit()
        await db.refresh(detection)
        yield detection


class TestListDetections:
    """Tests for GET /api/detections endpoint."""

    async def test_list_detections_empty(self, async_client, clean_detections):
        """Test listing detections when none exist."""
        response = await async_client.get("/api/detections")
        assert response.status_code == 200
        data = response.json()
        assert data["detections"] == []
        assert data["count"] == 0

    async def test_list_detections_with_data(self, async_client, sample_detection):
        """Test listing detections when data exists."""
        response = await async_client.get("/api/detections")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] >= 1
        assert len(data["detections"]) >= 1

    async def test_list_detections_filter_by_camera(self, async_client, sample_detection):
        """Test filtering detections by camera_id."""
        response = await async_client.get(f"/api/detections?camera_id={sample_detection.camera_id}")
        assert response.status_code == 200
        data = response.json()
        for detection in data["detections"]:
            assert detection["camera_id"] == sample_detection.camera_id

    async def test_list_detections_filter_by_object_type(self, async_client, sample_detection):
        """Test filtering detections by object_type."""
        response = await async_client.get("/api/detections?object_type=person")
        assert response.status_code == 200
        data = response.json()
        for detection in data["detections"]:
            assert detection["object_type"] == "person"

    async def test_list_detections_filter_by_min_confidence(self, async_client, sample_detection):
        """Test filtering detections by minimum confidence."""
        response = await async_client.get("/api/detections?min_confidence=0.9")
        assert response.status_code == 200
        data = response.json()
        for detection in data["detections"]:
            assert detection["confidence"] >= 0.9

    async def test_list_detections_pagination(self, async_client, sample_detection):
        """Test pagination parameters."""
        response = await async_client.get("/api/detections?limit=10&offset=0")
        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 10
        assert data["offset"] == 0

    async def test_list_detections_invalid_confidence(self, async_client):
        """Test validation of confidence parameter."""
        response = await async_client.get("/api/detections?min_confidence=1.5")
        assert response.status_code == 422  # Validation error


class TestGetDetection:
    """Tests for GET /api/detections/{detection_id} endpoint."""

    async def test_get_detection_success(self, async_client, sample_detection):
        """Test getting a detection by ID."""
        response = await async_client.get(f"/api/detections/{sample_detection.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_detection.id
        assert data["camera_id"] == sample_detection.camera_id
        assert data["object_type"] == sample_detection.object_type

    async def test_get_detection_not_found(self, async_client):
        """Test getting a non-existent detection returns 404."""
        response = await async_client.get("/api/detections/99999")
        assert response.status_code == 404


class TestGetDetectionImage:
    """Tests for GET /api/detections/{detection_id}/image endpoint."""

    async def test_get_detection_image_not_found(self, async_client):
        """Test getting image for non-existent detection returns 404."""
        response = await async_client.get("/api/detections/99999/image")
        assert response.status_code == 404

    async def test_get_detection_image_no_file(self, async_client, sample_detection):
        """Test getting image when source file doesn't exist."""
        response = await async_client.get(f"/api/detections/{sample_detection.id}/image")
        # Should return 404 since the test file doesn't actually exist
        assert response.status_code == 404


class TestGetDetectionStats:
    """Tests for GET /api/detections/stats endpoint (NEM-1128).

    This endpoint returns aggregate statistics about detections including:
    - Total detection count
    - Detection counts grouped by object class (person, car, truck, etc.)
    - Average confidence score
    """

    async def test_get_detection_stats_empty(self, async_client, clean_detections):
        """Test getting stats when no detections exist."""
        response = await async_client.get("/api/detections/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["total_detections"] == 0
        assert data["detections_by_class"] == {}
        assert data["average_confidence"] is None

    async def test_get_detection_stats_with_single_detection(self, async_client, sample_detection):
        """Test getting stats with a single detection."""
        response = await async_client.get("/api/detections/stats")
        assert response.status_code == 200
        data = response.json()
        # Should have at least the detection created by fixture
        assert data["total_detections"] >= 1
        assert "person" in data["detections_by_class"]
        assert data["detections_by_class"]["person"] >= 1
        assert data["average_confidence"] is not None
        assert 0 <= data["average_confidence"] <= 1

    async def test_get_detection_stats_class_distribution(
        self, async_client, clean_detections, integration_db
    ):
        """Test that stats correctly groups detections by class."""
        import uuid

        from backend.core.database import get_session
        from backend.models.camera import Camera
        from backend.models.detection import Detection

        # First verify database is empty after clean_detections
        response = await async_client.get("/api/detections/stats")
        assert response.status_code == 200
        assert response.json()["total_detections"] == 0

        # Create camera first (required for FK constraint)
        camera_id = str(uuid.uuid4())
        unique_suffix = uuid.uuid4().hex[:8]
        async with get_session() as db:
            camera = Camera(
                id=camera_id,
                name=f"Test Camera {unique_suffix}",
                folder_path=f"/export/foscam/test_{unique_suffix}",
                status="online",
            )
            db.add(camera)
            await db.commit()

        # Create detections with different object types
        async with get_session() as db:
            detections_data = [
                ("person", 0.95),
                ("person", 0.90),
                ("person", 0.85),
                ("car", 0.92),
                ("car", 0.88),
                ("truck", 0.80),
            ]
            for obj_type, conf in detections_data:
                detection = Detection(
                    camera_id=camera_id,
                    file_path=f"/export/foscam/test_{obj_type}_{conf}.jpg",
                    file_type="image/jpeg",
                    detected_at=datetime(2025, 12, 23, 12, 0, 0),
                    object_type=obj_type,
                    confidence=conf,
                    bbox_x=100,
                    bbox_y=150,
                    bbox_width=200,
                    bbox_height=400,
                )
                db.add(detection)
            await db.commit()

        response = await async_client.get("/api/detections/stats")
        assert response.status_code == 200
        data = response.json()

        # Verify total count
        assert data["total_detections"] == 6

        # Verify class distribution
        assert data["detections_by_class"]["person"] == 3
        assert data["detections_by_class"]["car"] == 2
        assert data["detections_by_class"]["truck"] == 1

        # Verify average confidence (sum: 0.95+0.90+0.85+0.92+0.88+0.80 = 5.30, avg = 0.883...)
        assert data["average_confidence"] is not None
        assert 0.88 <= data["average_confidence"] <= 0.89

    async def test_get_detection_stats_response_schema(self, async_client, sample_detection):
        """Test that the response conforms to the expected schema."""
        response = await async_client.get("/api/detections/stats")
        assert response.status_code == 200
        data = response.json()

        # Verify required fields exist
        assert "total_detections" in data
        assert "detections_by_class" in data
        assert "average_confidence" in data

        # Verify field types
        assert isinstance(data["total_detections"], int)
        assert isinstance(data["detections_by_class"], dict)
        assert data["average_confidence"] is None or isinstance(data["average_confidence"], float)


class TestGetDetectionEnrichment:
    """Tests for GET /api/detections/{detection_id}/enrichment endpoint."""

    async def test_get_enrichment_success_with_data(
        self, async_client, sample_camera, integration_db
    ):
        """Test getting enrichment data for detection with enrichment."""
        from backend.core.database import get_session
        from backend.models.detection import Detection

        enrichment_data = {
            "license_plates": [
                {
                    "confidence": 0.92,
                    "text": "ABC-1234",
                    "ocr_confidence": 0.88,
                    "bbox": [100.0, 200.0, 300.0, 250.0],
                }
            ],
            "faces": [{"confidence": 0.85, "bbox": [50, 60, 150, 200]}],
            "vehicle_classifications": {
                "det_1": {
                    "vehicle_type": "sedan",
                    "confidence": 0.91,
                    "is_commercial": False,
                }
            },
            "clothing_classifications": {
                "det_1": {
                    "top_category": "t-shirt",
                    "raw_description": "red t-shirt, blue jeans",
                    "is_suspicious": False,
                    "is_service_uniform": False,
                }
            },
            "violence_detection": {
                "is_violent": False,
                "confidence": 0.12,
            },
            "image_quality": {
                "quality_score": 85.0,
                "is_blurry": False,
                "is_low_quality": False,
                "quality_issues": [],
            },
            "pet_classifications": {
                "det_1": {
                    "animal_type": "dog",
                    "confidence": 0.94,
                    "is_household_pet": True,
                }
            },
            "processing_time_ms": 125.5,
        }

        async with get_session() as db:
            detection = Detection(
                camera_id=sample_camera.id,
                file_path="/export/foscam/front_door/enriched_image.jpg",
                file_type="image/jpeg",
                detected_at=datetime(2025, 12, 23, 12, 0, 0),
                object_type="car",
                confidence=0.92,
                bbox_x=100,
                bbox_y=150,
                bbox_width=200,
                bbox_height=400,
                enrichment_data=enrichment_data,
            )
            db.add(detection)
            await db.commit()
            await db.refresh(detection)
            detection_id = detection.id

        response = await async_client.get(f"/api/detections/{detection_id}/enrichment")
        assert response.status_code == 200
        data = response.json()

        # Verify required fields
        assert data["detection_id"] == detection_id
        assert data["enriched_at"] is not None

        # Verify license plate data
        assert data["license_plate"]["detected"] is True
        assert data["license_plate"]["text"] == "ABC-1234"
        assert data["license_plate"]["confidence"] == 0.92

        # Verify face detection
        assert data["face"]["detected"] is True
        assert data["face"]["count"] == 1

        # Verify vehicle data
        assert data["vehicle"]["type"] == "sedan"
        assert data["vehicle"]["confidence"] == 0.91
        assert data["vehicle"]["is_commercial"] is False

        # Verify clothing data
        assert data["clothing"]["upper"] == "red t-shirt"
        assert data["clothing"]["lower"] == "blue jeans"

        # Verify violence data
        assert data["violence"]["detected"] is False
        assert data["violence"]["score"] == 0.12

        # Verify image quality
        assert data["image_quality"]["score"] == 85.0
        assert data["image_quality"]["is_blurry"] is False

        # Verify pet data
        assert data["pet"]["detected"] is True
        assert data["pet"]["type"] == "dog"

        # Verify processing time
        assert data["processing_time_ms"] == 125.5

    async def test_get_enrichment_success_no_data(self, async_client, sample_detection):
        """Test getting enrichment for detection with no enrichment data."""
        response = await async_client.get(f"/api/detections/{sample_detection.id}/enrichment")
        assert response.status_code == 200
        data = response.json()

        # Verify required fields present with defaults
        assert data["detection_id"] == sample_detection.id
        assert data["license_plate"]["detected"] is False
        assert data["face"]["detected"] is False
        assert data["face"]["count"] == 0
        assert data["violence"]["detected"] is False
        assert data["violence"]["score"] == 0.0
        assert data["vehicle"] is None
        assert data["clothing"] is None
        assert data["pet"] is None
        assert data["errors"] == []

    async def test_get_enrichment_not_found(self, async_client):
        """Test getting enrichment for non-existent detection returns 404."""
        response = await async_client.get("/api/detections/99999/enrichment")
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()

    async def test_get_enrichment_with_errors(self, async_client, sample_camera, integration_db):
        """Test enrichment response includes sanitized error messages."""
        from backend.core.database import get_session
        from backend.models.detection import Detection

        enrichment_data = {
            "errors": [
                "License plate detection failed: /internal/path/to/file.jpg",
                "Face detection timeout on 192.168.1.100:8080",
            ],
        }

        async with get_session() as db:
            detection = Detection(
                camera_id=sample_camera.id,
                file_path="/export/foscam/front_door/error_image.jpg",
                file_type="image/jpeg",
                detected_at=datetime(2025, 12, 23, 12, 0, 0),
                object_type="person",
                confidence=0.85,
                bbox_x=100,
                bbox_y=150,
                bbox_width=200,
                bbox_height=400,
                enrichment_data=enrichment_data,
            )
            db.add(detection)
            await db.commit()
            await db.refresh(detection)
            detection_id = detection.id

        response = await async_client.get(f"/api/detections/{detection_id}/enrichment")
        assert response.status_code == 200
        data = response.json()

        # Errors should be sanitized (no paths or IPs)
        assert len(data["errors"]) == 2
        # Sanitized errors should be generic
        for error in data["errors"]:
            assert "/internal/path" not in error
            assert "192.168" not in error


class TestGetDetectionImageAdvanced:
    """Advanced tests for GET /api/detections/{detection_id}/image endpoint."""

    async def test_get_detection_image_with_missing_source_file(
        self, async_client, sample_camera, integration_db
    ):
        """Test image endpoint when source file doesn't exist."""
        from backend.core.database import get_session
        from backend.models.detection import Detection

        async with get_session() as db:
            detection = Detection(
                camera_id=sample_camera.id,
                file_path="/nonexistent/path/missing_image.jpg",
                file_type="image/jpeg",
                detected_at=datetime(2025, 12, 23, 12, 0, 0),
                object_type="person",
                confidence=0.95,
                bbox_x=100,
                bbox_y=150,
                bbox_width=200,
                bbox_height=400,
            )
            db.add(detection)
            await db.commit()
            await db.refresh(detection)
            detection_id = detection.id

        response = await async_client.get(f"/api/detections/{detection_id}/image")
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()

    async def test_get_detection_image_invalid_id(self, async_client):
        """Test image endpoint with invalid detection ID format."""
        response = await async_client.get("/api/detections/not_a_number/image")
        assert response.status_code == 422  # Validation error


class TestStreamDetectionVideo:
    """Tests for GET /api/detections/{detection_id}/video endpoint."""

    async def test_stream_video_not_found(self, async_client):
        """Test streaming video for non-existent detection returns 404."""
        response = await async_client.get("/api/detections/99999/video")
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()

    async def test_stream_video_not_a_video(self, async_client, sample_detection):
        """Test streaming for an image detection returns 400."""
        # sample_detection has media_type=None (defaults to image)
        response = await async_client.get(f"/api/detections/{sample_detection.id}/video")
        assert response.status_code == 400
        data = response.json()
        assert "not a video" in data["detail"].lower()

    async def test_stream_video_missing_file(self, async_client, sample_camera, integration_db):
        """Test streaming video when file doesn't exist returns 404."""
        from backend.core.database import get_session
        from backend.models.detection import Detection

        async with get_session() as db:
            detection = Detection(
                camera_id=sample_camera.id,
                file_path="/nonexistent/video.mp4",
                file_type="video/mp4",
                media_type="video",
                detected_at=datetime(2025, 12, 23, 12, 0, 0),
                object_type="person",
                confidence=0.95,
                bbox_x=100,
                bbox_y=150,
                bbox_width=200,
                bbox_height=400,
                duration=30.0,
            )
            db.add(detection)
            await db.commit()
            await db.refresh(detection)
            detection_id = detection.id

        response = await async_client.get(f"/api/detections/{detection_id}/video")
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()

    async def test_stream_video_with_invalid_range_header(
        self, async_client, sample_camera, integration_db, tmp_path
    ):
        """Test streaming video with invalid Range header returns 416."""
        from backend.core.database import get_session
        from backend.models.detection import Detection

        # Create a temporary video file
        video_file = tmp_path / "test_video.mp4"
        video_file.write_bytes(b"fake video content for testing" * 100)  # ~3KB

        async with get_session() as db:
            detection = Detection(
                camera_id=sample_camera.id,
                file_path=str(video_file),
                file_type="video/mp4",
                media_type="video",
                detected_at=datetime(2025, 12, 23, 12, 0, 0),
                object_type="person",
                confidence=0.95,
                bbox_x=100,
                bbox_y=150,
                bbox_width=200,
                bbox_height=400,
                duration=30.0,
            )
            db.add(detection)
            await db.commit()
            await db.refresh(detection)
            detection_id = detection.id

        # Invalid range format
        response = await async_client.get(
            f"/api/detections/{detection_id}/video",
            headers={"Range": "invalid_range_format"},
        )
        assert response.status_code == 416

    async def test_stream_video_with_valid_range_header(
        self, async_client, sample_camera, integration_db, tmp_path
    ):
        """Test streaming video with valid Range header returns 206 Partial Content."""
        from backend.core.database import get_session
        from backend.models.detection import Detection

        # Create a temporary video file
        video_file = tmp_path / "test_video.mp4"
        video_content = b"fake video content for testing" * 100
        video_file.write_bytes(video_content)

        async with get_session() as db:
            detection = Detection(
                camera_id=sample_camera.id,
                file_path=str(video_file),
                file_type="video/mp4",
                media_type="video",
                detected_at=datetime(2025, 12, 23, 12, 0, 0),
                object_type="person",
                confidence=0.95,
                bbox_x=100,
                bbox_y=150,
                bbox_width=200,
                bbox_height=400,
                duration=30.0,
            )
            db.add(detection)
            await db.commit()
            await db.refresh(detection)
            detection_id = detection.id

        # Request first 100 bytes
        response = await async_client.get(
            f"/api/detections/{detection_id}/video",
            headers={"Range": "bytes=0-99"},
        )
        assert response.status_code == 206
        assert "Content-Range" in response.headers
        assert response.headers["Content-Range"].startswith("bytes 0-99/")
        assert len(response.content) == 100

    async def test_stream_video_full_content(
        self, async_client, sample_camera, integration_db, tmp_path
    ):
        """Test streaming full video without Range header returns 200."""
        from backend.core.database import get_session
        from backend.models.detection import Detection

        # Create a temporary video file
        video_file = tmp_path / "test_full_video.mp4"
        video_content = b"fake video content"
        video_file.write_bytes(video_content)

        async with get_session() as db:
            detection = Detection(
                camera_id=sample_camera.id,
                file_path=str(video_file),
                file_type="video/mp4",
                media_type="video",
                detected_at=datetime(2025, 12, 23, 12, 0, 0),
                object_type="person",
                confidence=0.95,
                bbox_x=100,
                bbox_y=150,
                bbox_width=200,
                bbox_height=400,
                duration=10.0,
            )
            db.add(detection)
            await db.commit()
            await db.refresh(detection)
            detection_id = detection.id

        response = await async_client.get(f"/api/detections/{detection_id}/video")
        assert response.status_code == 200
        assert "Accept-Ranges" in response.headers
        assert response.headers["Accept-Ranges"] == "bytes"
        assert response.content == video_content


class TestGetVideoThumbnail:
    """Tests for GET /api/detections/{detection_id}/video/thumbnail endpoint."""

    async def test_get_video_thumbnail_not_found(self, async_client):
        """Test getting thumbnail for non-existent detection returns 404."""
        response = await async_client.get("/api/detections/99999/video/thumbnail")
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()

    async def test_get_video_thumbnail_not_a_video(self, async_client, sample_detection):
        """Test getting thumbnail for image detection returns 400."""
        response = await async_client.get(f"/api/detections/{sample_detection.id}/video/thumbnail")
        assert response.status_code == 400
        data = response.json()
        assert "not a video" in data["detail"].lower()

    async def test_get_video_thumbnail_missing_video_file(
        self, async_client, sample_camera, integration_db
    ):
        """Test getting thumbnail when video file doesn't exist returns 404."""
        from backend.core.database import get_session
        from backend.models.detection import Detection

        async with get_session() as db:
            detection = Detection(
                camera_id=sample_camera.id,
                file_path="/nonexistent/video_for_thumbnail.mp4",
                file_type="video/mp4",
                media_type="video",
                detected_at=datetime(2025, 12, 23, 12, 0, 0),
                object_type="person",
                confidence=0.95,
                bbox_x=100,
                bbox_y=150,
                bbox_width=200,
                bbox_height=400,
                duration=30.0,
            )
            db.add(detection)
            await db.commit()
            await db.refresh(detection)
            detection_id = detection.id

        response = await async_client.get(f"/api/detections/{detection_id}/video/thumbnail")
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()

    async def test_get_video_thumbnail_with_existing_thumbnail(
        self, async_client, sample_camera, integration_db, tmp_path
    ):
        """Test getting thumbnail when thumbnail already exists."""
        from backend.core.database import get_session
        from backend.models.detection import Detection

        # Create thumbnail file
        thumbnail_file = tmp_path / "existing_thumbnail.jpg"
        # Write minimal valid JPEG data
        thumbnail_file.write_bytes(
            b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9"
        )

        async with get_session() as db:
            detection = Detection(
                camera_id=sample_camera.id,
                file_path="/some/video.mp4",  # Doesn't need to exist if thumbnail exists
                file_type="video/mp4",
                media_type="video",
                detected_at=datetime(2025, 12, 23, 12, 0, 0),
                object_type="person",
                confidence=0.95,
                bbox_x=100,
                bbox_y=150,
                bbox_width=200,
                bbox_height=400,
                duration=30.0,
                thumbnail_path=str(thumbnail_file),
            )
            db.add(detection)
            await db.commit()
            await db.refresh(detection)
            detection_id = detection.id

        response = await async_client.get(f"/api/detections/{detection_id}/video/thumbnail")
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/jpeg"
        assert "Cache-Control" in response.headers
