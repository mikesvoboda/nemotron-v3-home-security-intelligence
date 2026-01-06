"""Integration tests for video streaming with HTTP Range header support.

Tests the following endpoints:
- GET /api/detections/{detection_id}/video (video streaming with Range support)
- GET /api/detections/{detection_id}/video/thumbnail (video thumbnail extraction)

Test scenarios:
- Non-video detection returns 400
- Missing video file handling
- Partial content (206) with Range header
- Full content (200) without Range header
- Range not satisfiable (416)
- Various Range formats: bytes=0-, bytes=-500, bytes=0-999
"""

import tempfile
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from backend.tests.integration.test_helpers import get_error_message


# Alias for backward compatibility - tests use async_client but conftest provides client
@pytest.fixture
async def async_client(client):
    """Alias for shared client fixture for backward compatibility."""
    yield client


@pytest.fixture
async def sample_camera(integration_db):
    """Create a sample camera in the database."""
    from backend.core.database import get_session
    from backend.models.camera import Camera

    camera_id = str(uuid.uuid4())
    async with get_session() as db:
        camera = Camera(
            id=camera_id,
            name="Video Test Camera",
            folder_path="/export/foscam/video_test",
            status="online",
        )
        db.add(camera)
        await db.commit()
        await db.refresh(camera)
        yield camera


@pytest.fixture
async def image_detection(integration_db, sample_camera):
    """Create a detection for an image (not video)."""
    from backend.core.database import get_session
    from backend.models.detection import Detection

    async with get_session() as db:
        detection = Detection(
            camera_id=sample_camera.id,
            file_path="/export/foscam/video_test/test_image.jpg",
            file_type="image/jpeg",
            media_type="image",  # Explicitly set to image
            object_type="person",
            confidence=0.95,
        )
        db.add(detection)
        await db.commit()
        await db.refresh(detection)
        yield detection


@pytest.fixture
async def video_detection_missing_file(integration_db, sample_camera):
    """Create a video detection where the file doesn't exist."""
    from backend.core.database import get_session
    from backend.models.detection import Detection

    async with get_session() as db:
        detection = Detection(
            camera_id=sample_camera.id,
            file_path="/nonexistent/path/test_video.mp4",
            file_type="video/mp4",
            media_type="video",
            object_type="person",
            confidence=0.9,
            duration=10.5,
            video_codec="h264",
            video_width=1920,
            video_height=1080,
        )
        db.add(detection)
        await db.commit()
        await db.refresh(detection)
        yield detection


@pytest.fixture
def temp_video_file():
    """Create a temporary video file for testing.

    Creates a file with known content for testing Range requests.
    File size is 10000 bytes for easy range calculations.
    """
    # Create a temp file with predictable content
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        # Write exactly 10000 bytes of repeating pattern
        # This makes it easy to verify Range requests return correct bytes
        content = b"0123456789" * 1000  # 10000 bytes
        f.write(content)
        temp_path = f.name

    yield temp_path

    # Cleanup
    temp_path_obj = Path(temp_path)
    if temp_path_obj.exists():
        temp_path_obj.unlink()


@pytest.fixture
async def video_detection_with_file(integration_db, sample_camera, temp_video_file):
    """Create a video detection with an actual test file."""
    from backend.core.database import get_session
    from backend.models.detection import Detection

    async with get_session() as db:
        detection = Detection(
            camera_id=sample_camera.id,
            file_path=temp_video_file,
            file_type="video/mp4",
            media_type="video",
            object_type="person",
            confidence=0.9,
            duration=10.5,
            video_codec="h264",
            video_width=1920,
            video_height=1080,
        )
        db.add(detection)
        await db.commit()
        await db.refresh(detection)
        yield detection


class TestVideoStreamingNonVideoDetection:
    """Tests for attempting to stream non-video detections."""

    async def test_stream_image_detection_returns_400(self, async_client, image_detection):
        """Test streaming an image detection returns 400 Bad Request."""
        response = await async_client.get(f"/api/detections/{image_detection.id}/video")
        assert response.status_code == 400
        data = response.json()
        error_msg = get_error_message(data)
        assert "not a video" in error_msg.lower()

    async def test_video_thumbnail_for_image_returns_400(self, async_client, image_detection):
        """Test getting video thumbnail for image detection returns 400."""
        response = await async_client.get(f"/api/detections/{image_detection.id}/video/thumbnail")
        assert response.status_code == 400
        data = response.json()
        error_msg = get_error_message(data)
        assert "not a video" in error_msg.lower()


class TestVideoStreamingMissingFile:
    """Tests for video detections with missing files."""

    async def test_stream_video_file_not_found(self, async_client, video_detection_missing_file):
        """Test streaming when video file doesn't exist returns 404."""
        response = await async_client.get(
            f"/api/detections/{video_detection_missing_file.id}/video"
        )
        assert response.status_code == 404
        data = response.json()
        error_msg = get_error_message(data)
        assert "not found" in error_msg.lower()

    async def test_video_thumbnail_file_not_found(self, async_client, video_detection_missing_file):
        """Test video thumbnail when file doesn't exist returns 404."""
        response = await async_client.get(
            f"/api/detections/{video_detection_missing_file.id}/video/thumbnail"
        )
        assert response.status_code == 404


class TestVideoStreamingNonexistentDetection:
    """Tests for non-existent detection IDs."""

    async def test_stream_nonexistent_detection_returns_404(self, async_client, integration_db):
        """Test streaming a non-existent detection returns 404."""
        response = await async_client.get("/api/detections/99999/video")
        assert response.status_code == 404

    async def test_thumbnail_nonexistent_detection_returns_404(self, async_client, integration_db):
        """Test video thumbnail for non-existent detection returns 404."""
        response = await async_client.get("/api/detections/99999/video/thumbnail")
        assert response.status_code == 404


class TestVideoStreamingFullContent:
    """Tests for full content (200) video streaming without Range header."""

    async def test_full_video_returns_200(self, async_client, video_detection_with_file):
        """Test streaming full video returns 200 OK."""
        response = await async_client.get(f"/api/detections/{video_detection_with_file.id}/video")
        assert response.status_code == 200

    async def test_full_video_content_length(self, async_client, video_detection_with_file):
        """Test full video has correct Content-Length header."""
        response = await async_client.get(f"/api/detections/{video_detection_with_file.id}/video")
        assert response.status_code == 200
        assert "content-length" in response.headers
        assert int(response.headers["content-length"]) == 10000

    async def test_full_video_accept_ranges_header(self, async_client, video_detection_with_file):
        """Test full video has Accept-Ranges: bytes header."""
        response = await async_client.get(f"/api/detections/{video_detection_with_file.id}/video")
        assert response.status_code == 200
        assert response.headers.get("accept-ranges") == "bytes"

    async def test_full_video_content_type(self, async_client, video_detection_with_file):
        """Test full video has correct content type."""
        response = await async_client.get(f"/api/detections/{video_detection_with_file.id}/video")
        assert response.status_code == 200
        assert "video/mp4" in response.headers.get("content-type", "")

    async def test_full_video_content(self, async_client, video_detection_with_file):
        """Test full video returns correct content."""
        response = await async_client.get(f"/api/detections/{video_detection_with_file.id}/video")
        assert response.status_code == 200
        content = response.content
        assert len(content) == 10000
        # Verify it's our test pattern
        assert content == b"0123456789" * 1000


class TestVideoStreamingPartialContent:
    """Tests for partial content (206) with Range header."""

    async def test_range_request_returns_206(self, async_client, video_detection_with_file):
        """Test Range request returns 206 Partial Content."""
        response = await async_client.get(
            f"/api/detections/{video_detection_with_file.id}/video",
            headers={"Range": "bytes=0-999"},
        )
        assert response.status_code == 206

    async def test_range_first_1000_bytes(self, async_client, video_detection_with_file):
        """Test Range: bytes=0-999 returns first 1000 bytes."""
        response = await async_client.get(
            f"/api/detections/{video_detection_with_file.id}/video",
            headers={"Range": "bytes=0-999"},
        )
        assert response.status_code == 206
        content = response.content
        assert len(content) == 1000
        # First 1000 bytes should be "0123456789" * 100
        assert content == b"0123456789" * 100

    async def test_range_content_range_header(self, async_client, video_detection_with_file):
        """Test Content-Range header is correct for Range request."""
        response = await async_client.get(
            f"/api/detections/{video_detection_with_file.id}/video",
            headers={"Range": "bytes=0-999"},
        )
        assert response.status_code == 206
        content_range = response.headers.get("content-range")
        assert content_range == "bytes 0-999/10000"

    async def test_range_content_length_header(self, async_client, video_detection_with_file):
        """Test Content-Length header is correct for Range request."""
        response = await async_client.get(
            f"/api/detections/{video_detection_with_file.id}/video",
            headers={"Range": "bytes=0-999"},
        )
        assert response.status_code == 206
        assert int(response.headers.get("content-length", 0)) == 1000

    async def test_range_middle_bytes(self, async_client, video_detection_with_file):
        """Test Range for middle portion of file."""
        response = await async_client.get(
            f"/api/detections/{video_detection_with_file.id}/video",
            headers={"Range": "bytes=1000-1999"},
        )
        assert response.status_code == 206
        content = response.content
        assert len(content) == 1000
        # Bytes 1000-1999 should also be "0123456789" * 100
        assert content == b"0123456789" * 100
        assert response.headers.get("content-range") == "bytes 1000-1999/10000"


class TestVideoStreamingRangeFormats:
    """Tests for various Range header formats."""

    async def test_range_open_ended(self, async_client, video_detection_with_file):
        """Test Range: bytes=9000- (from byte 9000 to end)."""
        response = await async_client.get(
            f"/api/detections/{video_detection_with_file.id}/video",
            headers={"Range": "bytes=9000-"},
        )
        assert response.status_code == 206
        content = response.content
        assert len(content) == 1000  # 10000 - 9000 = 1000 bytes
        assert response.headers.get("content-range") == "bytes 9000-9999/10000"

    async def test_range_suffix_last_500_bytes(self, async_client, video_detection_with_file):
        """Test Range: bytes=-500 (last 500 bytes)."""
        response = await async_client.get(
            f"/api/detections/{video_detection_with_file.id}/video", headers={"Range": "bytes=-500"}
        )
        assert response.status_code == 206
        content = response.content
        assert len(content) == 500
        # Last 500 bytes: starts at 9500
        assert response.headers.get("content-range") == "bytes 9500-9999/10000"

    async def test_range_suffix_larger_than_file(self, async_client, video_detection_with_file):
        """Test Range: bytes=-20000 (suffix larger than file returns entire file)."""
        response = await async_client.get(
            f"/api/detections/{video_detection_with_file.id}/video",
            headers={"Range": "bytes=-20000"},
        )
        assert response.status_code == 206
        content = response.content
        assert len(content) == 10000  # Returns entire file
        assert response.headers.get("content-range") == "bytes 0-9999/10000"

    async def test_range_exact_last_byte(self, async_client, video_detection_with_file):
        """Test Range: bytes=9999-9999 (single last byte)."""
        response = await async_client.get(
            f"/api/detections/{video_detection_with_file.id}/video",
            headers={"Range": "bytes=9999-9999"},
        )
        assert response.status_code == 206
        content = response.content
        assert len(content) == 1
        assert content == b"9"  # Last byte of pattern "0123456789"
        assert response.headers.get("content-range") == "bytes 9999-9999/10000"

    async def test_range_from_zero_to_end(self, async_client, video_detection_with_file):
        """Test Range: bytes=0- (entire file from byte 0)."""
        response = await async_client.get(
            f"/api/detections/{video_detection_with_file.id}/video", headers={"Range": "bytes=0-"}
        )
        assert response.status_code == 206
        content = response.content
        assert len(content) == 10000
        assert response.headers.get("content-range") == "bytes 0-9999/10000"


class TestVideoStreamingRangeNotSatisfiable:
    """Tests for Range Not Satisfiable (416) responses."""

    async def test_range_start_beyond_file(self, async_client, video_detection_with_file):
        """Test Range with start position beyond file size returns 416."""
        response = await async_client.get(
            f"/api/detections/{video_detection_with_file.id}/video",
            headers={"Range": "bytes=20000-"},
        )
        # When start > end (clamped to file_size - 1), it should return 416
        # The implementation clamps end to file_size - 1 (9999), so start=20000 > end=9999
        assert response.status_code == 416
        # Should have Content-Range header indicating file size
        assert "content-range" in response.headers
        assert "/10000" in response.headers["content-range"]

    async def test_range_invalid_format(self, async_client, video_detection_with_file):
        """Test Range with invalid format returns 416."""
        response = await async_client.get(
            f"/api/detections/{video_detection_with_file.id}/video",
            headers={"Range": "invalid-range"},
        )
        assert response.status_code == 416


class TestVideoThumbnail:
    """Tests for video thumbnail endpoint."""

    async def test_thumbnail_nonexistent_detection(self, async_client, integration_db):
        """Test thumbnail for non-existent detection returns 404."""
        response = await async_client.get("/api/detections/99999/video/thumbnail")
        assert response.status_code == 404

    async def test_thumbnail_for_image_detection(self, async_client, image_detection):
        """Test thumbnail for image detection returns 400."""
        response = await async_client.get(f"/api/detections/{image_detection.id}/video/thumbnail")
        assert response.status_code == 400

    async def test_thumbnail_with_existing_thumbnail(self, async_client, video_detection_with_file):
        """Test thumbnail returns existing thumbnail when available."""
        # Create a temporary thumbnail file
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            # Write minimal JPEG header for testing
            jpeg_content = (
                b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
                b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t"
                b"\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a"
                b"\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9telecomms"
                b"\xff\xd9"
            )
            f.write(jpeg_content)
            thumbnail_path = f.name

        try:
            # Update detection with thumbnail path
            from backend.core.database import get_session

            async with get_session() as db:
                from sqlalchemy import select

                from backend.models.detection import Detection

                result = await db.execute(
                    select(Detection).where(Detection.id == video_detection_with_file.id)
                )
                detection = result.scalar_one()
                detection.thumbnail_path = thumbnail_path
                await db.commit()

            response = await async_client.get(
                f"/api/detections/{video_detection_with_file.id}/video/thumbnail"
            )
            assert response.status_code == 200
            assert "image/jpeg" in response.headers.get("content-type", "")
        finally:
            thumbnail_path_obj = Path(thumbnail_path)
            if thumbnail_path_obj.exists():
                thumbnail_path_obj.unlink()

    async def test_thumbnail_generation_failure(self, async_client, video_detection_with_file):
        """Test thumbnail generation failure returns 500."""
        # Mock the video processor to return None (generation failure)
        with patch(
            "backend.api.routes.detections.video_processor.extract_thumbnail_for_detection",
            new_callable=AsyncMock,
            return_value=None,
        ):
            response = await async_client.get(
                f"/api/detections/{video_detection_with_file.id}/video/thumbnail"
            )
            assert response.status_code == 500
            data = response.json()
            error_msg = get_error_message(data)
        assert "failed" in error_msg.lower()


class TestVideoStreamingCaching:
    """Tests for caching headers on video streaming."""

    async def test_full_video_cache_control(self, async_client, video_detection_with_file):
        """Test full video has Cache-Control header."""
        response = await async_client.get(f"/api/detections/{video_detection_with_file.id}/video")
        assert response.status_code == 200
        assert "cache-control" in response.headers
        assert "public" in response.headers["cache-control"]

    async def test_partial_video_cache_control(self, async_client, video_detection_with_file):
        """Test partial video has Cache-Control header."""
        response = await async_client.get(
            f"/api/detections/{video_detection_with_file.id}/video",
            headers={"Range": "bytes=0-999"},
        )
        assert response.status_code == 206
        assert "cache-control" in response.headers


class TestVideoStreamingEdgeCases:
    """Tests for edge cases in video streaming."""

    async def test_range_end_beyond_file(self, async_client, video_detection_with_file):
        """Test Range with end position beyond file size is clamped."""
        response = await async_client.get(
            f"/api/detections/{video_detection_with_file.id}/video",
            headers={"Range": "bytes=9000-50000"},
        )
        assert response.status_code == 206
        content = response.content
        # End should be clamped to 9999
        assert len(content) == 1000
        assert response.headers.get("content-range") == "bytes 9000-9999/10000"

    async def test_empty_range_suffix(self, async_client, video_detection_with_file):
        """Test Range: bytes=0- with implicit end."""
        response = await async_client.get(
            f"/api/detections/{video_detection_with_file.id}/video", headers={"Range": "bytes=0-"}
        )
        assert response.status_code == 206
        assert len(response.content) == 10000

    async def test_small_chunk_request(self, async_client, video_detection_with_file):
        """Test very small Range request (1 byte)."""
        response = await async_client.get(
            f"/api/detections/{video_detection_with_file.id}/video", headers={"Range": "bytes=0-0"}
        )
        assert response.status_code == 206
        content = response.content
        assert len(content) == 1
        assert content == b"0"  # First byte of pattern
        assert response.headers.get("content-range") == "bytes 0-0/10000"
