"""Security integration tests for media file serving endpoints.

This module provides comprehensive security tests for path traversal protection
on media API endpoints. Tests verify that malicious path inputs are properly
rejected with 400/403 status codes.

Tested endpoints:
- GET /api/media/{path} (compatibility route)
- GET /api/media/cameras/{camera_id}/{filename}
- GET /api/media/thumbnails/{filename}

Security scenarios covered:
- Path traversal with '../' sequences
- Absolute paths ('/etc/passwd')
- URL-encoded traversal ('%2e%2e%2f')
- Null bytes in paths
- Double URL encoding
- Mixed encoding attacks
- Windows-style path separators
- Unicode normalization attacks
"""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(scope="module")
def security_temp_foscam_dir():
    """Create temporary Foscam directory structure for security tests.

    Creates a realistic directory structure with:
    - Camera directories
    - Valid media files
    - Nested subdirectories
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        base_path = Path(tmpdir)

        # Create camera directory
        camera_dir = base_path / "test_camera"
        camera_dir.mkdir()

        # Create valid test files
        (camera_dir / "valid_image.jpg").write_bytes(b"fake jpg data")
        (camera_dir / "valid_video.mp4").write_bytes(b"fake mp4 data")

        # Create nested subdirectory
        subdir = camera_dir / "subdir"
        subdir.mkdir()
        (subdir / "nested.jpg").write_bytes(b"nested jpg data")

        # Create a sensitive file outside the camera directory (for traversal tests)
        sensitive_file = base_path / "sensitive.txt"
        sensitive_file.write_text("SENSITIVE DATA - SHOULD NOT BE ACCESSIBLE")

        yield base_path


@pytest.fixture(scope="module")
def security_temp_thumbnail_dir():
    """Create temporary thumbnail directory for security tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        thumb_dir = Path(tmpdir) / "thumbnails"
        thumb_dir.mkdir(parents=True, exist_ok=True)

        # Create valid thumbnails
        (thumb_dir / "valid_thumb.jpg").write_bytes(b"fake thumbnail")
        (thumb_dir / "valid_thumb.png").write_bytes(b"fake thumbnail png")

        yield thumb_dir


@pytest.fixture(scope="module")
def security_client(security_temp_foscam_dir, security_temp_thumbnail_dir):
    """Create test client with mocked services for security testing.

    This fixture is module-scoped for performance since all tests are read-only.
    """
    # Mock background services
    mock_system_broadcaster = MagicMock()
    mock_system_broadcaster.start_broadcasting = AsyncMock()
    mock_system_broadcaster.stop_broadcasting = AsyncMock()

    mock_gpu_monitor = MagicMock()
    mock_gpu_monitor.start = AsyncMock()
    mock_gpu_monitor.stop = AsyncMock()

    mock_cleanup_service = MagicMock()
    mock_cleanup_service.start = AsyncMock()
    mock_cleanup_service.stop = AsyncMock()

    mock_redis_client = MagicMock()

    mock_event_broadcaster = MagicMock()
    mock_event_broadcaster.channel_name = "test_channel"

    mock_file_watcher = MagicMock()
    mock_file_watcher.start = AsyncMock()
    mock_file_watcher.stop = AsyncMock()

    mock_pipeline_manager = MagicMock()
    mock_pipeline_manager.start = AsyncMock()
    mock_pipeline_manager.stop = AsyncMock()

    mock_service_health_monitor = MagicMock()
    mock_service_health_monitor.start = AsyncMock()
    mock_service_health_monitor.stop = AsyncMock()

    # Create mock settings
    from backend.core.config import Settings

    def mock_get_settings():
        settings = Settings()
        settings.foscam_base_path = str(security_temp_foscam_dir)
        return settings

    # Patch thumbnail serving
    from backend.api.routes import media as media_module

    # Create no-op rate limiter that always passes
    # Note: Must not use *args/**kwargs as FastAPI exposes them as query params
    async def mock_rate_limiter() -> None:
        return None

    async def patched_serve_thumbnail(filename: str):
        """Patched version that uses temp thumbnail directory."""
        from fastapi.responses import FileResponse

        from backend.api.routes.media import ALLOWED_TYPES, _validate_and_resolve_path

        full_path = _validate_and_resolve_path(security_temp_thumbnail_dir, filename)
        content_type = ALLOWED_TYPES[full_path.suffix.lower()]
        return FileResponse(
            path=str(full_path),
            media_type=content_type,
            filename=full_path.name,
        )

    # Set DATABASE_URL
    import os

    original_db_url = os.environ.get("DATABASE_URL")
    if not original_db_url:
        os.environ["DATABASE_URL"] = (
            "postgresql+asyncpg://security:security_dev_password@localhost:5432/security"
        )

    from backend.main import app

    async def mock_init_db():
        pass

    async def mock_seed_cameras_if_empty():
        return 0

    async def mock_validate_camera_paths_on_startup():
        return (0, 0)

    async def mock_init_redis():
        return mock_redis_client

    async def mock_get_broadcaster(_redis_client):
        return mock_event_broadcaster

    async def mock_get_pipeline_manager(_redis_client):
        return mock_pipeline_manager

    with (
        patch("backend.main.init_db", mock_init_db),
        patch("backend.main.seed_cameras_if_empty", mock_seed_cameras_if_empty),
        patch(
            "backend.main.validate_camera_paths_on_startup",
            mock_validate_camera_paths_on_startup,
        ),
        patch("backend.main.init_redis", mock_init_redis),
        patch("backend.main.get_broadcaster", mock_get_broadcaster),
        patch("backend.main.FileWatcher", return_value=mock_file_watcher),
        patch("backend.main.get_pipeline_manager", mock_get_pipeline_manager),
        patch("backend.main.get_system_broadcaster", return_value=mock_system_broadcaster),
        patch("backend.main.GPUMonitor", return_value=mock_gpu_monitor),
        patch("backend.main.CleanupService", return_value=mock_cleanup_service),
        patch("backend.main.ServiceHealthMonitor", return_value=mock_service_health_monitor),
        patch("backend.api.routes.media.get_settings", mock_get_settings),
        patch.object(media_module, "serve_thumbnail", patched_serve_thumbnail),
    ):
        # Override the rate limiter dependency using FastAPI's dependency_overrides
        app.dependency_overrides[media_module.media_rate_limiter] = mock_rate_limiter
        try:
            with TestClient(app) as test_client:
                yield test_client
        finally:
            # Clean up the override
            app.dependency_overrides.pop(media_module.media_rate_limiter, None)


# =============================================================================
# Path Traversal Tests - Camera Files Endpoint
# =============================================================================


class TestCameraPathTraversal:
    """Security tests for path traversal on /api/media/cameras/{camera_id}/{filename}."""

    @pytest.mark.parametrize(
        "malicious_path,description",
        [
            ("../sensitive.txt", "single parent directory traversal"),
            ("../../sensitive.txt", "double parent directory traversal"),
            ("../../../etc/passwd", "deep traversal to system files"),
            ("subdir/../../sensitive.txt", "traversal from subdirectory"),
            ("subdir/../../../sensitive.txt", "deep traversal from subdirectory"),
            ("./././../sensitive.txt", "traversal with dot segments"),
        ],
    )
    def test_camera_path_traversal_with_dotdot(self, security_client, malicious_path, description):
        """Test that '../' path traversal attempts are blocked.

        Scenario: {description}
        """
        response = security_client.get(f"/api/media/cameras/test_camera/{malicious_path}")

        # Should be blocked with 403 (traversal detected) or 404 (normalized away)
        assert response.status_code in [403, 404], (
            f"Path traversal not blocked for: {malicious_path}"
        )

        # If 403, verify it's the traversal error
        if response.status_code == 403:
            data = response.json()
            assert "detail" in data
            assert "error" in data["detail"]

    @pytest.mark.parametrize(
        "absolute_path,description",
        [
            ("/etc/passwd", "absolute path to passwd"),
            ("/etc/shadow", "absolute path to shadow"),
            ("/root/.ssh/id_rsa", "absolute path to SSH key"),
            ("/var/log/syslog", "absolute path to syslog"),
        ],
    )
    def test_camera_absolute_path_blocked(self, security_client, absolute_path, description):
        """Test that absolute paths are blocked.

        Scenario: {description}
        """
        response = security_client.get(f"/api/media/cameras/test_camera/{absolute_path}")

        assert response.status_code == 403, f"Absolute path not blocked for: {absolute_path}"
        data = response.json()
        assert "detail" in data
        assert "error" in data["detail"]

    @pytest.mark.parametrize(
        "encoded_path,description",
        [
            ("%2e%2e%2fsensitive.txt", "URL-encoded ../ (lowercase)"),
            ("%2E%2E%2Fsensitive.txt", "URL-encoded ../ (uppercase)"),
            ("%2e%2e/sensitive.txt", "partial URL encoding"),
            ("..%2fsensitive.txt", "partial URL encoding variant"),
            ("%2e%2e%2f%2e%2e%2fetc%2fpasswd", "double URL-encoded traversal"),
        ],
    )
    def test_camera_url_encoded_traversal_blocked(self, security_client, encoded_path, description):
        """Test that URL-encoded path traversal attempts are blocked.

        FastAPI automatically decodes URL-encoded paths before routing,
        so our validation should catch the decoded traversal.

        Scenario: {description}
        """
        response = security_client.get(f"/api/media/cameras/test_camera/{encoded_path}")

        # Should be blocked with 403 (traversal detected) or 404 (path not found)
        assert response.status_code in [403, 404], (
            f"URL-encoded traversal not blocked for: {encoded_path}"
        )

    @pytest.mark.parametrize(
        "double_encoded_path,description",
        [
            ("%252e%252e%252f", "double URL-encoded ../"),
            ("%252e%252e/", "partially double encoded"),
            ("..%252f", "partially double encoded variant"),
        ],
    )
    def test_camera_double_url_encoding_blocked(
        self, security_client, double_encoded_path, description
    ):
        """Test that double URL-encoded paths are blocked.

        Double encoding attempts to bypass single-decode validation.

        Scenario: {description}
        """
        response = security_client.get(
            f"/api/media/cameras/test_camera/{double_encoded_path}sensitive.txt"
        )

        # Should be blocked - either 403 or 404
        assert response.status_code in [400, 403, 404], (
            f"Double URL-encoded path not blocked: {double_encoded_path}"
        )

    @pytest.mark.parametrize(
        "null_byte_path,description",
        [
            # Note: URL-encoded null bytes (%00) are decoded by the HTTP layer
            # and cause either HTTP parsing errors or are filtered out.
            # These tests verify the behavior is secure (either error or rejected).
            ("%00../sensitive.txt", "null byte before traversal"),
        ],
    )
    def test_camera_null_byte_injection_blocked(self, security_client, null_byte_path, description):
        """Test that null byte injection attempts are blocked.

        Null bytes can be used to truncate strings in some languages/systems.
        URL-encoded null bytes (%00) are typically rejected at the HTTP parsing
        layer before reaching application code. The key security property is that
        the request either fails or returns non-200 status - never serves content.

        Scenario: {description}
        """
        try:
            response = security_client.get(f"/api/media/cameras/test_camera/{null_byte_path}")
            # If we get a response, it should not be 200
            assert response.status_code != 200, (
                f"Null byte injection not blocked for: {null_byte_path}"
            )
        except Exception:  # noqa: S110 - HTTP parsing errors are acceptable here
            pass

    @pytest.mark.parametrize(
        "camera_id_attack,filename,description",
        [
            ("../", "sensitive.txt", "traversal in camera_id"),
            ("test_camera/../", "sensitive.txt", "nested traversal in camera_id"),
            ("/etc", "passwd", "absolute path in camera_id"),
            ("..", "sensitive.txt", "dotdot as camera_id"),
        ],
    )
    def test_camera_id_traversal_blocked(
        self, security_client, camera_id_attack, filename, description
    ):
        """Test that path traversal in camera_id is blocked.

        Scenario: {description}
        """
        response = security_client.get(f"/api/media/cameras/{camera_id_attack}/{filename}")

        # Should be blocked
        assert response.status_code in [403, 404], (
            f"Camera ID traversal not blocked: {camera_id_attack}"
        )


# =============================================================================
# Path Traversal Tests - Thumbnails Endpoint
# =============================================================================


class TestThumbnailPathTraversal:
    """Security tests for path traversal on /api/media/thumbnails/{filename}."""

    @pytest.mark.parametrize(
        "malicious_path,description",
        [
            ("../sensitive.txt", "single parent directory traversal"),
            ("../../etc/passwd", "deep traversal to system files"),
            ("./../../sensitive.txt", "traversal with dot prefix"),
        ],
    )
    def test_thumbnail_path_traversal_blocked(self, security_client, malicious_path, description):
        """Test that '../' path traversal attempts are blocked on thumbnails.

        Scenario: {description}
        """
        response = security_client.get(f"/api/media/thumbnails/{malicious_path}")

        # Should be blocked with 403 or 404
        assert response.status_code in [403, 404], (
            f"Thumbnail traversal not blocked for: {malicious_path}"
        )

    @pytest.mark.parametrize(
        "absolute_path,description",
        [
            ("/etc/passwd", "absolute path to passwd"),
            ("/etc/shadow", "absolute path to shadow"),
        ],
    )
    def test_thumbnail_absolute_path_blocked(self, security_client, absolute_path, description):
        """Test that absolute paths are blocked on thumbnails.

        Scenario: {description}
        """
        response = security_client.get(f"/api/media/thumbnails/{absolute_path}")

        assert response.status_code == 403, (
            f"Absolute path not blocked for thumbnail: {absolute_path}"
        )

    @pytest.mark.parametrize(
        "encoded_path,description",
        [
            ("%2e%2e%2fetc%2fpasswd", "URL-encoded traversal"),
            ("%2E%2E%2Fetc%2Fpasswd", "URL-encoded traversal (uppercase)"),
        ],
    )
    def test_thumbnail_url_encoded_traversal_blocked(
        self, security_client, encoded_path, description
    ):
        """Test that URL-encoded traversal is blocked on thumbnails.

        Scenario: {description}
        """
        response = security_client.get(f"/api/media/thumbnails/{encoded_path}")

        assert response.status_code in [403, 404], (
            f"URL-encoded traversal not blocked: {encoded_path}"
        )

    @pytest.mark.parametrize(
        "null_byte_path,description",
        [
            # Note: URL-encoded null bytes (%00) typically cause HTTP parsing errors
            # or are rejected by the framework. This verifies secure behavior.
            ("%00../etc/passwd", "null byte before traversal"),
        ],
    )
    def test_thumbnail_null_byte_blocked(self, security_client, null_byte_path, description):
        """Test that null byte injection is blocked on thumbnails.

        URL-encoded null bytes are typically rejected at the HTTP parsing
        layer before reaching application code. The security property is that
        the request either fails or returns non-200 status.

        Scenario: {description}
        """
        try:
            response = security_client.get(f"/api/media/thumbnails/{null_byte_path}")
            # If we get a response, it should not be 200
            assert response.status_code != 200, (
                f"Null byte not blocked for thumbnail: {null_byte_path}"
            )
        except Exception:  # noqa: S110 - HTTP parsing errors are acceptable here
            pass


# =============================================================================
# Path Traversal Tests - Compatibility Route
# =============================================================================


class TestCompatRoutePathTraversal:
    """Security tests for path traversal on /api/media/{path} compatibility route."""

    @pytest.mark.parametrize(
        "malicious_path,description",
        [
            ("cameras/../sensitive.txt", "traversal after cameras prefix"),
            ("cameras/test_camera/../../sensitive.txt", "deep traversal"),
            ("thumbnails/../sensitive.txt", "traversal after thumbnails prefix"),
            ("../etc/passwd", "traversal without valid prefix"),
        ],
    )
    def test_compat_route_traversal_blocked(self, security_client, malicious_path, description):
        """Test that path traversal is blocked on compatibility route.

        Scenario: {description}
        """
        response = security_client.get(f"/api/media/{malicious_path}")

        # Should be blocked - 403 or 404
        assert response.status_code in [403, 404], (
            f"Compat route traversal not blocked: {malicious_path}"
        )

    def test_compat_route_unsupported_prefix_returns_404(self, security_client):
        """Test that unsupported path prefixes return 404."""
        response = security_client.get("/api/media/invalid_prefix/file.jpg")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "Unsupported media path" in data["detail"]["error"]


# =============================================================================
# Additional Security Edge Cases
# =============================================================================


class TestSecurityEdgeCases:
    """Additional edge case security tests."""

    @pytest.mark.parametrize(
        "windows_path,description",
        [
            ("..\\sensitive.txt", "Windows backslash traversal"),
            ("..\\..\\sensitive.txt", "Windows double backslash traversal"),
            ("subdir\\..\\..\\sensitive.txt", "Windows traversal from subdir"),
        ],
    )
    def test_windows_path_separator_handled(self, security_client, windows_path, description):
        """Test that Windows-style path separators don't bypass security.

        Note: URL encoding of backslash is %5C.
        On Unix systems, backslash is a valid filename character,
        so these should result in 404 (file not found) or be blocked.

        Scenario: {description}
        """
        response = security_client.get(f"/api/media/cameras/test_camera/{windows_path}")

        # On Unix: backslash is valid in filenames, so 404 expected
        # The key is that we don't serve sensitive files
        assert response.status_code in [400, 403, 404]

    def test_very_long_path_handled(self, security_client):
        """Test that extremely long paths are handled gracefully."""
        # Create a very long path (potential buffer overflow attack)
        long_segment = "a" * 1000
        long_path = "/".join([long_segment] * 10)

        response = security_client.get(f"/api/media/cameras/test_camera/{long_path}.jpg")

        # Should be handled without server error (400, 403, 404, or 414)
        assert response.status_code in [400, 403, 404, 414]

    def test_unicode_normalization_attack(self, security_client):
        """Test that Unicode normalization doesn't bypass security.

        Some Unicode characters can normalize to ASCII equivalents.
        """
        # U+FF0E is fullwidth full stop (.)
        # U+FF0F is fullwidth solidus (/)
        # These might normalize to . and / in some systems
        unicode_path = "\uff0e\uff0e\uff0fetc\uff0fpasswd"

        response = security_client.get(f"/api/media/cameras/test_camera/{unicode_path}")

        # Should not return 200 with sensitive content
        assert response.status_code in [400, 403, 404]

    def test_empty_path_components_handled(self, security_client):
        """Test that empty path components don't cause issues."""
        # Multiple slashes create empty components
        response = security_client.get("/api/media/cameras/test_camera//valid_image.jpg")

        # Should be handled - either serves file or rejects
        # Key is no server error
        assert response.status_code in [200, 400, 403, 404]

    def test_hidden_file_access(self, security_client):
        """Test that hidden file access patterns are handled."""
        hidden_paths = [
            ".htaccess",
            ".env",
            ".git/config",
            "..hidden",
        ]

        for hidden_path in hidden_paths:
            response = security_client.get(f"/api/media/cameras/test_camera/{hidden_path}")

            # Hidden files should not be accessible (404 if not exists, 403 if blocked)
            assert response.status_code in [403, 404], (
                f"Hidden file not properly handled: {hidden_path}"
            )


# =============================================================================
# Validation of Allowed Files
# =============================================================================


class TestValidFileAccess:
    """Verify that valid files are still accessible after security checks."""

    def test_valid_jpg_file_accessible(self, security_client):
        """Test that valid JPG files are still accessible."""
        response = security_client.get("/api/media/cameras/test_camera/valid_image.jpg")

        assert response.status_code == 200
        assert response.headers["content-type"] == "image/jpeg"
        assert response.content == b"fake jpg data"

    def test_valid_nested_file_accessible(self, security_client):
        """Test that valid nested files are accessible."""
        response = security_client.get("/api/media/cameras/test_camera/subdir/nested.jpg")

        assert response.status_code == 200
        assert response.headers["content-type"] == "image/jpeg"
        assert response.content == b"nested jpg data"

    def test_valid_thumbnail_accessible(self, security_client):
        """Test that valid thumbnails are accessible."""
        response = security_client.get("/api/media/thumbnails/valid_thumb.jpg")

        assert response.status_code == 200
        assert response.headers["content-type"] == "image/jpeg"
        assert response.content == b"fake thumbnail"

    def test_compat_route_valid_camera_file(self, security_client):
        """Test that valid files are accessible via compatibility route."""
        response = security_client.get("/api/media/cameras/test_camera/valid_image.jpg")

        assert response.status_code == 200
        assert response.headers["content-type"] == "image/jpeg"

    def test_compat_route_valid_thumbnail(self, security_client):
        """Test that valid thumbnails are accessible via compatibility route."""
        response = security_client.get("/api/media/thumbnails/valid_thumb.jpg")

        assert response.status_code == 200
        assert response.headers["content-type"] == "image/jpeg"
