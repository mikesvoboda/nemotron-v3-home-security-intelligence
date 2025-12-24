"""Integration tests for media file serving endpoints."""

import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def temp_foscam_dir(monkeypatch):
    """Create temporary Foscam directory structure for testing."""
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

        # Patch the settings to use our temp directory
        from backend.core.config import Settings

        def mock_get_settings():
            settings = Settings()
            settings.foscam_base_path = str(base_path)
            return settings

        monkeypatch.setattr("backend.api.routes.media.get_settings", mock_get_settings)

        yield base_path


@pytest.fixture
def temp_thumbnail_dir(tmp_path):
    """Create temporary thumbnail directory for testing."""
    # Create the directory structure relative to the actual backend location
    # We're in backend/tests/integration/test_media_api.py
    # We need to go up to backend/ root, then data/thumbnails/
    thumb_dir = Path(__file__).parent.parent.parent / "data" / "thumbnails"
    thumb_dir.mkdir(parents=True, exist_ok=True)

    # Create test thumbnails
    (thumb_dir / "thumb1.jpg").write_bytes(b"fake thumbnail 1")
    (thumb_dir / "thumb2.png").write_bytes(b"fake thumbnail 2")
    (thumb_dir / "malware.exe").write_bytes(b"fake exe")

    yield thumb_dir

    # Cleanup - remove test files
    for file in thumb_dir.glob("*"):
        if file.name in ["thumb1.jpg", "thumb2.png", "malware.exe"]:
            file.unlink()


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
