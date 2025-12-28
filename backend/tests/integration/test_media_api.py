"""Integration tests for media file serving endpoints.

Performance optimization: Fixtures use module scope to avoid recreating
test directories and client for each test (21 tests). This reduces
overall test time significantly while maintaining test isolation
since all tests only read from the test directories.
"""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.main import app


@pytest.fixture(scope="module")
def module_temp_foscam_dir():
    """Create temporary Foscam directory structure once per module.

    This fixture is module-scoped to avoid recreating test files for each test.
    All tests in this module only read from these directories.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        base_path = Path(tmpdir)
        camera_dir = base_path / "test_camera"
        camera_dir.mkdir()

        # Create test files
        (camera_dir / "test_image.jpg").write_bytes(b"fake jpg data")
        (camera_dir / "test_video.mp4").write_bytes(b"fake mp4 data")
        (camera_dir / "test_image.png").write_bytes(b"fake png data")

        # Create subdirectory with file
        subdir = camera_dir / "subdir"
        subdir.mkdir()
        (subdir / "nested.jpg").write_bytes(b"nested jpg")

        # Create disallowed file types
        (camera_dir / "malware.exe").write_bytes(b"fake exe")
        (camera_dir / "script.sh").write_bytes(b"fake script")

        yield base_path


@pytest.fixture(scope="module")
def module_thumbnail_dir():
    """Create temporary thumbnail directory once per module.

    This fixture is module-scoped to avoid recreating test files for each test.
    All tests in this module only read from this directory.

    Uses tempfile.TemporaryDirectory for proper cleanup without leaking
    filesystem artifacts into the actual backend/data directory.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        thumb_dir = Path(tmpdir) / "thumbnails"
        thumb_dir.mkdir(parents=True, exist_ok=True)

        # Create test thumbnails
        (thumb_dir / "thumb1.jpg").write_bytes(b"fake thumbnail 1")
        (thumb_dir / "thumb2.png").write_bytes(b"fake thumbnail 2")
        (thumb_dir / "malware.exe").write_bytes(b"fake exe")

        yield thumb_dir
        # Cleanup happens automatically via TemporaryDirectory context manager


@pytest.fixture(scope="module")
def client(module_temp_foscam_dir, module_thumbnail_dir):
    """Create test client with mocked background services (module-scoped).

    Using module scope significantly reduces test time by avoiding
    21 separate TestClient setup/teardown cycles.

    Patches both foscam_base_path and thumbnail directory to use temp directories.
    """
    # Mock background services that have 5-second intervals to avoid slow teardown
    mock_system_broadcaster = MagicMock()
    mock_system_broadcaster.start_broadcasting = AsyncMock()
    mock_system_broadcaster.stop_broadcasting = AsyncMock()

    mock_gpu_monitor = MagicMock()
    mock_gpu_monitor.start = AsyncMock()
    mock_gpu_monitor.stop = AsyncMock()

    mock_cleanup_service = MagicMock()
    mock_cleanup_service.start = AsyncMock()
    mock_cleanup_service.stop = AsyncMock()

    # Create mock settings that uses our temp directory
    from backend.core.config import Settings

    def mock_get_settings():
        settings = Settings()
        settings.foscam_base_path = str(module_temp_foscam_dir)
        return settings

    # Store original serve_thumbnail to create patched version
    from backend.api.routes import media as media_module

    original_serve_thumbnail = media_module.serve_thumbnail

    async def patched_serve_thumbnail(filename: str):
        """Patched version that uses temp thumbnail directory."""
        from fastapi import HTTPException
        from fastapi.responses import FileResponse

        from backend.api.routes.media import ALLOWED_TYPES, _validate_and_resolve_path

        full_path = _validate_and_resolve_path(module_thumbnail_dir, filename)
        content_type = ALLOWED_TYPES[full_path.suffix.lower()]
        return FileResponse(
            path=str(full_path),
            media_type=content_type,
            filename=full_path.name,
        )

    # Patch background services, settings, and thumbnail endpoint to avoid slow teardown
    with (
        patch("backend.main.get_system_broadcaster", return_value=mock_system_broadcaster),
        patch("backend.main.GPUMonitor", return_value=mock_gpu_monitor),
        patch("backend.main.CleanupService", return_value=mock_cleanup_service),
        patch("backend.api.routes.media.get_settings", mock_get_settings),
        patch.object(media_module, "serve_thumbnail", patched_serve_thumbnail),
        TestClient(app) as test_client,
    ):
        yield test_client


@pytest.fixture
def temp_foscam_dir(module_temp_foscam_dir):
    """Alias fixture for backward compatibility with existing tests.

    Delegates to module-scoped fixture.
    """
    return module_temp_foscam_dir


@pytest.fixture
def temp_thumbnail_dir(module_thumbnail_dir):
    """Alias fixture for backward compatibility with existing tests.

    Delegates to module-scoped fixture.
    """
    return module_thumbnail_dir


class TestCameraFileServing:
    """Tests for camera file serving endpoint."""

    def test_serve_valid_image(self, client, temp_foscam_dir):
        """Test serving a valid JPG image file."""
        response = client.get("/api/media/cameras/test_camera/test_image.jpg")

        assert response.status_code == 200
        assert response.headers["content-type"] == "image/jpeg"
        assert response.content == b"fake jpg data"

    def test_serve_valid_png(self, client, temp_foscam_dir):
        """Test serving a valid PNG image file."""
        response = client.get("/api/media/cameras/test_camera/test_image.png")

        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"
        assert response.content == b"fake png data"

    def test_serve_valid_video(self, client, temp_foscam_dir):
        """Test serving a valid MP4 video file."""
        response = client.get("/api/media/cameras/test_camera/test_video.mp4")

        assert response.status_code == 200
        assert response.headers["content-type"] == "video/mp4"
        assert response.content == b"fake mp4 data"

    def test_serve_nested_file(self, client, temp_foscam_dir):
        """Test serving a file from a subdirectory."""
        response = client.get("/api/media/cameras/test_camera/subdir/nested.jpg")

        assert response.status_code == 200
        assert response.headers["content-type"] == "image/jpeg"
        assert response.content == b"nested jpg"

    def test_nonexistent_file_returns_404(self, client, temp_foscam_dir):
        """Test that requesting a non-existent file returns 404."""
        response = client.get("/api/media/cameras/test_camera/nonexistent.jpg")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "error" in data["detail"]
        assert "File not found" in data["detail"]["error"]
        assert data["detail"]["path"] == "nonexistent.jpg"

    def test_nonexistent_camera_returns_404(self, client, temp_foscam_dir):
        """Test that requesting from a non-existent camera returns 404."""
        response = client.get("/api/media/cameras/nonexistent_camera/test.jpg")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "error" in data["detail"]

    def test_path_traversal_blocked(self, client, temp_foscam_dir):
        """Test that path traversal attempts are blocked."""
        # Try to access a file outside the camera directory by traversing up
        # Test path traversal in the filename parameter itself
        # The fixture already creates subdir with a nested.jpg file

        # Try to traverse up from within the filename parameter
        response = client.get("/api/media/cameras/test_camera/subdir/../../../secret.jpg")

        # Should be blocked - either 403 (traversal detected) or 404 (path not found/normalized away)
        # Both indicate the security is working - the important thing is it doesn't return 200
        assert response.status_code in [403, 404]

    def test_path_traversal_with_encoded_chars_blocked(self, client, temp_foscam_dir):
        """Test that encoded path traversal attempts are blocked."""
        response = client.get("/api/media/cameras/test_camera/..%2F..%2Fetc%2Fpasswd")

        # FastAPI decodes the URL, so our validation should catch it
        assert response.status_code == 403

    def test_absolute_path_blocked(self, client, temp_foscam_dir):
        """Test that absolute paths are blocked."""
        response = client.get("/api/media/cameras/test_camera//etc/passwd")

        assert response.status_code == 403
        data = response.json()
        assert "detail" in data
        assert "error" in data["detail"]

    def test_disallowed_file_type_exe(self, client, temp_foscam_dir):
        """Test that .exe files are blocked."""
        response = client.get("/api/media/cameras/test_camera/malware.exe")

        assert response.status_code == 403
        data = response.json()
        assert "detail" in data
        assert "error" in data["detail"]
        assert "File type not allowed" in data["detail"]["error"]
        assert ".exe" in data["detail"]["error"]

    def test_disallowed_file_type_sh(self, client, temp_foscam_dir):
        """Test that .sh files are blocked."""
        response = client.get("/api/media/cameras/test_camera/script.sh")

        assert response.status_code == 403
        data = response.json()
        assert "detail" in data
        assert "error" in data["detail"]
        assert "File type not allowed" in data["detail"]["error"]
        assert ".sh" in data["detail"]["error"]


class TestThumbnailServing:
    """Tests for thumbnail serving endpoint."""

    def test_serve_valid_thumbnail_jpg(self, client, temp_thumbnail_dir):
        """Test serving a valid JPG thumbnail."""
        response = client.get("/api/media/thumbnails/thumb1.jpg")

        assert response.status_code == 200
        assert response.headers["content-type"] == "image/jpeg"
        assert response.content == b"fake thumbnail 1"

    def test_serve_valid_thumbnail_png(self, client, temp_thumbnail_dir):
        """Test serving a valid PNG thumbnail."""
        response = client.get("/api/media/thumbnails/thumb2.png")

        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"
        assert response.content == b"fake thumbnail 2"

    def test_nonexistent_thumbnail_returns_404(self, client, temp_thumbnail_dir):
        """Test that requesting a non-existent thumbnail returns 404."""
        response = client.get("/api/media/thumbnails/nonexistent.jpg")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "error" in data["detail"]
        assert "File not found" in data["detail"]["error"]

    def test_path_traversal_blocked_in_thumbnails(self, client, temp_thumbnail_dir):
        """Test that path traversal is blocked in thumbnail requests."""
        # Test that .. in the filename itself is blocked
        response = client.get("/api/media/thumbnails/../../etc/passwd")

        # Should be blocked - either 403 (traversal detected) or 404 (path not found/normalized away)
        # Both indicate security is working - the important thing is it doesn't return 200
        assert response.status_code in [403, 404]

    def test_disallowed_thumbnail_file_type(self, client, temp_thumbnail_dir):
        """Test that disallowed file types are blocked for thumbnails."""
        # The fixture creates malware.exe in the thumbnails directory
        response = client.get("/api/media/thumbnails/malware.exe")

        # Should return 403 because file type is not allowed
        # (checked before file existence in our validation)
        assert response.status_code == 403
        data = response.json()
        assert "detail" in data
        assert "error" in data["detail"]
        assert "File type not allowed" in data["detail"]["error"]


class TestContentTypeHeaders:
    """Tests for proper content-type headers."""

    def test_jpg_content_type(self, client, temp_foscam_dir):
        """Test that JPG files have correct content-type."""
        response = client.get("/api/media/cameras/test_camera/test_image.jpg")
        assert response.headers["content-type"] == "image/jpeg"

    def test_png_content_type(self, client, temp_foscam_dir):
        """Test that PNG files have correct content-type."""
        response = client.get("/api/media/cameras/test_camera/test_image.png")
        assert response.headers["content-type"] == "image/png"

    def test_mp4_content_type(self, client, temp_foscam_dir):
        """Test that MP4 files have correct content-type."""
        response = client.get("/api/media/cameras/test_camera/test_video.mp4")
        assert response.headers["content-type"] == "video/mp4"


class TestCompatMediaRoute:
    """Tests for compatibility media route: /api/media/{path}."""

    def test_compat_camera_file_served(self, client, temp_foscam_dir):
        """Compatibility route supports cameras/<camera>/<file>."""
        response = client.get("/api/media/cameras/test_camera/test_image.jpg")
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/jpeg"
        assert response.content == b"fake jpg data"

    def test_compat_thumbnail_served(self, client, temp_thumbnail_dir):
        """Compatibility route supports thumbnails/<file>."""
        response = client.get("/api/media/thumbnails/thumb1.jpg")
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/jpeg"
        assert response.content == b"fake thumbnail 1"
