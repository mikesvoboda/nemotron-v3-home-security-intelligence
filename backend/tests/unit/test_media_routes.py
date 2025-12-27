"""Unit tests for backend.api.routes.media endpoints.

These tests cover the media file serving routes including:
- Camera file serving
- Thumbnail serving
- Compatibility path routing
- Path traversal protection
- File type validation
- Error handling
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from backend.api.routes import media as media_routes
from backend.api.routes.media import (
    ALLOWED_TYPES,
    _validate_and_resolve_path,
    serve_camera_file,
    serve_media_compat,
    serve_thumbnail,
)


# =============================================================================
# ALLOWED_TYPES Constants Tests
# =============================================================================


class TestAllowedTypes:
    """Tests for the ALLOWED_TYPES constant."""

    def test_allowed_types_includes_common_image_formats(self) -> None:
        """Test that common image formats are in allowed types."""
        assert ".jpg" in ALLOWED_TYPES
        assert ".jpeg" in ALLOWED_TYPES
        assert ".png" in ALLOWED_TYPES
        assert ".gif" in ALLOWED_TYPES

    def test_allowed_types_includes_common_video_formats(self) -> None:
        """Test that common video formats are in allowed types."""
        assert ".mp4" in ALLOWED_TYPES
        assert ".avi" in ALLOWED_TYPES
        assert ".webm" in ALLOWED_TYPES

    def test_allowed_types_have_correct_content_types(self) -> None:
        """Test that allowed types map to correct content-type values."""
        assert ALLOWED_TYPES[".jpg"] == "image/jpeg"
        assert ALLOWED_TYPES[".jpeg"] == "image/jpeg"
        assert ALLOWED_TYPES[".png"] == "image/png"
        assert ALLOWED_TYPES[".gif"] == "image/gif"
        assert ALLOWED_TYPES[".mp4"] == "video/mp4"
        assert ALLOWED_TYPES[".avi"] == "video/x-msvideo"
        assert ALLOWED_TYPES[".webm"] == "video/webm"


# =============================================================================
# _validate_and_resolve_path Tests
# =============================================================================


class TestValidateAndResolvePath:
    """Tests for the _validate_and_resolve_path helper function."""

    def test_rejects_path_with_double_dots(self, tmp_path: Path) -> None:
        """Test that path traversal via .. is rejected."""
        with pytest.raises(HTTPException) as exc_info:
            _validate_and_resolve_path(tmp_path, "../etc/passwd")

        assert exc_info.value.status_code == 403
        assert "Path traversal detected" in exc_info.value.detail["error"]
        assert exc_info.value.detail["path"] == "../etc/passwd"

    def test_rejects_path_starting_with_slash(self, tmp_path: Path) -> None:
        """Test that absolute paths starting with / are rejected."""
        with pytest.raises(HTTPException) as exc_info:
            _validate_and_resolve_path(tmp_path, "/etc/passwd")

        assert exc_info.value.status_code == 403
        assert "Path traversal detected" in exc_info.value.detail["error"]
        assert exc_info.value.detail["path"] == "/etc/passwd"

    def test_rejects_path_with_embedded_double_dots(self, tmp_path: Path) -> None:
        """Test that paths with embedded .. sequences are rejected."""
        with pytest.raises(HTTPException) as exc_info:
            _validate_and_resolve_path(tmp_path, "subdir/../../../etc/passwd")

        assert exc_info.value.status_code == 403
        assert "Path traversal detected" in exc_info.value.detail["error"]

    def test_rejects_nonexistent_file(self, tmp_path: Path) -> None:
        """Test that nonexistent files return 404."""
        with pytest.raises(HTTPException) as exc_info:
            _validate_and_resolve_path(tmp_path, "nonexistent.jpg")

        assert exc_info.value.status_code == 404
        assert "File not found" in exc_info.value.detail["error"]
        assert exc_info.value.detail["path"] == "nonexistent.jpg"

    def test_rejects_directory_instead_of_file(self, tmp_path: Path) -> None:
        """Test that directories are rejected (must be a file)."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()

        with pytest.raises(HTTPException) as exc_info:
            _validate_and_resolve_path(tmp_path, "subdir")

        assert exc_info.value.status_code == 404
        assert "File not found" in exc_info.value.detail["error"]

    def test_rejects_disallowed_file_type(self, tmp_path: Path) -> None:
        """Test that files with disallowed extensions are rejected."""
        # Create a file with disallowed extension
        test_file = tmp_path / "test.exe"
        test_file.write_text("malicious content")

        with pytest.raises(HTTPException) as exc_info:
            _validate_and_resolve_path(tmp_path, "test.exe")

        assert exc_info.value.status_code == 403
        assert "File type not allowed" in exc_info.value.detail["error"]
        assert ".exe" in exc_info.value.detail["error"]

    def test_rejects_file_outside_base_via_symlink(self, tmp_path: Path) -> None:
        """Test that symlinks pointing outside base directory are rejected."""
        # Create a file outside the base path
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            external_file = Path(f.name)
            external_file.write_bytes(b"external content")

        try:
            # Create symlink inside base path pointing to external file
            symlink = tmp_path / "symlink.jpg"
            symlink.symlink_to(external_file)

            with pytest.raises(HTTPException) as exc_info:
                _validate_and_resolve_path(tmp_path, "symlink.jpg")

            assert exc_info.value.status_code == 403
            assert "outside allowed directory" in exc_info.value.detail["error"]
        finally:
            external_file.unlink()

    def test_accepts_valid_jpg_file(self, tmp_path: Path) -> None:
        """Test that a valid .jpg file is accepted."""
        test_file = tmp_path / "test.jpg"
        test_file.write_bytes(b"fake jpeg content")

        result = _validate_and_resolve_path(tmp_path, "test.jpg")

        assert result == test_file.resolve()

    def test_accepts_valid_jpeg_file(self, tmp_path: Path) -> None:
        """Test that a valid .jpeg file is accepted."""
        test_file = tmp_path / "test.jpeg"
        test_file.write_bytes(b"fake jpeg content")

        result = _validate_and_resolve_path(tmp_path, "test.jpeg")

        assert result == test_file.resolve()

    def test_accepts_valid_png_file(self, tmp_path: Path) -> None:
        """Test that a valid .png file is accepted."""
        test_file = tmp_path / "test.png"
        test_file.write_bytes(b"fake png content")

        result = _validate_and_resolve_path(tmp_path, "test.png")

        assert result == test_file.resolve()

    def test_accepts_valid_gif_file(self, tmp_path: Path) -> None:
        """Test that a valid .gif file is accepted."""
        test_file = tmp_path / "test.gif"
        test_file.write_bytes(b"fake gif content")

        result = _validate_and_resolve_path(tmp_path, "test.gif")

        assert result == test_file.resolve()

    def test_accepts_valid_mp4_file(self, tmp_path: Path) -> None:
        """Test that a valid .mp4 file is accepted."""
        test_file = tmp_path / "test.mp4"
        test_file.write_bytes(b"fake mp4 content")

        result = _validate_and_resolve_path(tmp_path, "test.mp4")

        assert result == test_file.resolve()

    def test_accepts_valid_avi_file(self, tmp_path: Path) -> None:
        """Test that a valid .avi file is accepted."""
        test_file = tmp_path / "test.avi"
        test_file.write_bytes(b"fake avi content")

        result = _validate_and_resolve_path(tmp_path, "test.avi")

        assert result == test_file.resolve()

    def test_accepts_valid_webm_file(self, tmp_path: Path) -> None:
        """Test that a valid .webm file is accepted."""
        test_file = tmp_path / "test.webm"
        test_file.write_bytes(b"fake webm content")

        result = _validate_and_resolve_path(tmp_path, "test.webm")

        assert result == test_file.resolve()

    def test_accepts_file_in_subdirectory(self, tmp_path: Path) -> None:
        """Test that files in subdirectories are accepted."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        test_file = subdir / "test.jpg"
        test_file.write_bytes(b"fake jpeg content")

        result = _validate_and_resolve_path(tmp_path, "subdir/test.jpg")

        assert result == test_file.resolve()

    def test_accepts_file_in_nested_subdirectory(self, tmp_path: Path) -> None:
        """Test that files in nested subdirectories are accepted."""
        subdir = tmp_path / "level1" / "level2"
        subdir.mkdir(parents=True)
        test_file = subdir / "test.jpg"
        test_file.write_bytes(b"fake jpeg content")

        result = _validate_and_resolve_path(tmp_path, "level1/level2/test.jpg")

        assert result == test_file.resolve()

    def test_case_insensitive_extension_validation(self, tmp_path: Path) -> None:
        """Test that file extension validation is case-insensitive."""
        test_file = tmp_path / "test.JPG"
        test_file.write_bytes(b"fake jpeg content")

        result = _validate_and_resolve_path(tmp_path, "test.JPG")

        assert result == test_file.resolve()

    def test_rejects_disallowed_uppercase_extension(self, tmp_path: Path) -> None:
        """Test that disallowed extensions are rejected regardless of case."""
        test_file = tmp_path / "test.EXE"
        test_file.write_text("malicious content")

        with pytest.raises(HTTPException) as exc_info:
            _validate_and_resolve_path(tmp_path, "test.EXE")

        assert exc_info.value.status_code == 403
        assert "File type not allowed" in exc_info.value.detail["error"]


# =============================================================================
# serve_camera_file Tests
# =============================================================================


class TestServeCameraFile:
    """Tests for the serve_camera_file endpoint."""

    @pytest.mark.asyncio
    async def test_rejects_camera_id_with_double_dots(self) -> None:
        """Test that camera IDs with path traversal are rejected."""
        with pytest.raises(HTTPException) as exc_info:
            await serve_camera_file(camera_id="../etc", filename="passwd")

        assert exc_info.value.status_code == 403
        assert "Invalid camera identifier" in exc_info.value.detail["error"]
        assert exc_info.value.detail["path"] == "../etc"

    @pytest.mark.asyncio
    async def test_rejects_camera_id_starting_with_slash(self) -> None:
        """Test that camera IDs starting with / are rejected."""
        with pytest.raises(HTTPException) as exc_info:
            await serve_camera_file(camera_id="/etc", filename="passwd")

        assert exc_info.value.status_code == 403
        assert "Invalid camera identifier" in exc_info.value.detail["error"]
        assert exc_info.value.detail["path"] == "/etc"

    @pytest.mark.asyncio
    async def test_serves_valid_camera_file(self, tmp_path: Path) -> None:
        """Test that a valid camera file is served correctly."""
        # Create camera directory and test file
        camera_dir = tmp_path / "front_door"
        camera_dir.mkdir()
        test_file = camera_dir / "image.jpg"
        test_file.write_bytes(b"fake jpeg content")

        # Mock settings to use tmp_path as base
        mock_settings = MagicMock()
        mock_settings.foscam_base_path = str(tmp_path)

        with patch.object(media_routes, "get_settings", return_value=mock_settings):
            response = await serve_camera_file(
                camera_id="front_door", filename="image.jpg"
            )

        assert response.path == str(test_file)
        assert response.media_type == "image/jpeg"
        assert response.filename == "image.jpg"

    @pytest.mark.asyncio
    async def test_serves_camera_file_with_subdirectory(self, tmp_path: Path) -> None:
        """Test that files in camera subdirectories are served correctly."""
        # Create camera directory with subdirectory
        camera_dir = tmp_path / "garage" / "2024-01"
        camera_dir.mkdir(parents=True)
        test_file = camera_dir / "capture.png"
        test_file.write_bytes(b"fake png content")

        mock_settings = MagicMock()
        mock_settings.foscam_base_path = str(tmp_path)

        with patch.object(media_routes, "get_settings", return_value=mock_settings):
            response = await serve_camera_file(
                camera_id="garage", filename="2024-01/capture.png"
            )

        assert response.path == str(test_file)
        assert response.media_type == "image/png"
        assert response.filename == "capture.png"

    @pytest.mark.asyncio
    async def test_returns_404_for_nonexistent_camera_file(
        self, tmp_path: Path
    ) -> None:
        """Test that 404 is returned for nonexistent files."""
        camera_dir = tmp_path / "backyard"
        camera_dir.mkdir()

        mock_settings = MagicMock()
        mock_settings.foscam_base_path = str(tmp_path)

        with (
            patch.object(media_routes, "get_settings", return_value=mock_settings),
            pytest.raises(HTTPException) as exc_info,
        ):
            await serve_camera_file(camera_id="backyard", filename="nonexistent.jpg")

        assert exc_info.value.status_code == 404
        assert "File not found" in exc_info.value.detail["error"]

    @pytest.mark.asyncio
    async def test_serves_video_file_with_correct_content_type(
        self, tmp_path: Path
    ) -> None:
        """Test that video files are served with correct content type."""
        camera_dir = tmp_path / "driveway"
        camera_dir.mkdir()
        test_file = camera_dir / "recording.mp4"
        test_file.write_bytes(b"fake mp4 content")

        mock_settings = MagicMock()
        mock_settings.foscam_base_path = str(tmp_path)

        with patch.object(media_routes, "get_settings", return_value=mock_settings):
            response = await serve_camera_file(
                camera_id="driveway", filename="recording.mp4"
            )

        assert response.media_type == "video/mp4"


# =============================================================================
# serve_thumbnail Tests
# =============================================================================


class TestServeThumbnail:
    """Tests for the serve_thumbnail endpoint."""

    @pytest.mark.asyncio
    async def test_rejects_path_traversal_in_filename(self) -> None:
        """Test that path traversal in thumbnail filename is rejected."""
        with pytest.raises(HTTPException) as exc_info:
            await serve_thumbnail(filename="../../../etc/passwd")

        assert exc_info.value.status_code == 403
        assert "Path traversal detected" in exc_info.value.detail["error"]

    @pytest.mark.asyncio
    async def test_rejects_absolute_path_in_filename(self) -> None:
        """Test that absolute paths in thumbnail filename are rejected."""
        with pytest.raises(HTTPException) as exc_info:
            await serve_thumbnail(filename="/etc/passwd")

        assert exc_info.value.status_code == 403
        assert "Path traversal detected" in exc_info.value.detail["error"]

    @pytest.mark.asyncio
    async def test_serves_valid_thumbnail(self, tmp_path: Path) -> None:
        """Test that a valid thumbnail is served correctly."""
        # Create thumbnail file
        test_file = tmp_path / "thumb_123.jpg"
        test_file.write_bytes(b"fake thumbnail content")

        # Mock the thumbnail base path
        with patch.object(
            media_routes, "_validate_and_resolve_path"
        ) as mock_validate, patch.object(
            media_routes.Path, "__truediv__", return_value=tmp_path
        ):
            mock_validate.return_value = test_file

            response = await serve_thumbnail(filename="thumb_123.jpg")

        assert response.path == str(test_file)
        assert response.media_type == "image/jpeg"
        assert response.filename == "thumb_123.jpg"

    @pytest.mark.asyncio
    async def test_returns_404_for_nonexistent_thumbnail(self) -> None:
        """Test that 404 is returned for nonexistent thumbnails."""
        # The actual thumbnail directory is determined by the module path
        # We'll test by mocking _validate_and_resolve_path to raise 404
        with patch.object(
            media_routes, "_validate_and_resolve_path"
        ) as mock_validate, pytest.raises(HTTPException) as exc_info:
            mock_validate.side_effect = HTTPException(
                status_code=404,
                detail={
                    "error": "File not found",
                    "path": "nonexistent.jpg",
                },
            )

            await serve_thumbnail(filename="nonexistent.jpg")

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_serves_png_thumbnail(self, tmp_path: Path) -> None:
        """Test that PNG thumbnails are served with correct content type."""
        test_file = tmp_path / "thumb_456.png"
        test_file.write_bytes(b"fake png thumbnail")

        with patch.object(
            media_routes, "_validate_and_resolve_path"
        ) as mock_validate:
            mock_validate.return_value = test_file

            response = await serve_thumbnail(filename="thumb_456.png")

        assert response.media_type == "image/png"


# =============================================================================
# serve_media_compat Tests
# =============================================================================


class TestServeMediaCompat:
    """Tests for the serve_media_compat compatibility endpoint."""

    @pytest.mark.asyncio
    async def test_routes_cameras_path_to_serve_camera_file(
        self, tmp_path: Path
    ) -> None:
        """Test that cameras/ paths are routed to serve_camera_file."""
        camera_dir = tmp_path / "front_door"
        camera_dir.mkdir()
        test_file = camera_dir / "image.jpg"
        test_file.write_bytes(b"fake jpeg")

        mock_settings = MagicMock()
        mock_settings.foscam_base_path = str(tmp_path)

        with patch.object(media_routes, "get_settings", return_value=mock_settings):
            response = await serve_media_compat(path="cameras/front_door/image.jpg")

        assert response.path == str(test_file)
        assert response.media_type == "image/jpeg"

    @pytest.mark.asyncio
    async def test_routes_thumbnails_path_to_serve_thumbnail(
        self, tmp_path: Path
    ) -> None:
        """Test that thumbnails/ paths are routed to serve_thumbnail."""
        test_file = tmp_path / "thumb.jpg"
        test_file.write_bytes(b"fake thumbnail")

        with patch.object(
            media_routes, "_validate_and_resolve_path"
        ) as mock_validate:
            mock_validate.return_value = test_file

            response = await serve_media_compat(path="thumbnails/thumb.jpg")

        assert response.path == str(test_file)
        assert response.media_type == "image/jpeg"

    @pytest.mark.asyncio
    async def test_returns_404_for_unsupported_path(self) -> None:
        """Test that unsupported paths return 404."""
        with pytest.raises(HTTPException) as exc_info:
            await serve_media_compat(path="unknown/path/file.jpg")

        assert exc_info.value.status_code == 404
        assert "Unsupported media path" in exc_info.value.detail["error"]

    @pytest.mark.asyncio
    async def test_returns_404_for_empty_path(self) -> None:
        """Test that empty paths return 404."""
        with pytest.raises(HTTPException) as exc_info:
            await serve_media_compat(path="")

        assert exc_info.value.status_code == 404
        assert "Unsupported media path" in exc_info.value.detail["error"]

    @pytest.mark.asyncio
    async def test_returns_404_for_cameras_without_filename(self) -> None:
        """Test that cameras/ without proper path structure returns 404."""
        with pytest.raises(HTTPException) as exc_info:
            await serve_media_compat(path="cameras/front_door")

        assert exc_info.value.status_code == 404
        assert "File not found" in exc_info.value.detail["error"]

    @pytest.mark.asyncio
    async def test_strips_leading_slashes_from_path(self, tmp_path: Path) -> None:
        """Test that leading slashes are stripped from the path."""
        camera_dir = tmp_path / "garage"
        camera_dir.mkdir()
        test_file = camera_dir / "snap.jpg"
        test_file.write_bytes(b"fake jpeg")

        mock_settings = MagicMock()
        mock_settings.foscam_base_path = str(tmp_path)

        with patch.object(media_routes, "get_settings", return_value=mock_settings):
            response = await serve_media_compat(path="/cameras/garage/snap.jpg")

        assert response.path == str(test_file)

    @pytest.mark.asyncio
    async def test_routes_cameras_with_subdirectory(self, tmp_path: Path) -> None:
        """Test that cameras paths with subdirectories are handled correctly."""
        camera_dir = tmp_path / "backyard" / "2024" / "01" / "15"
        camera_dir.mkdir(parents=True)
        test_file = camera_dir / "motion.mp4"
        test_file.write_bytes(b"fake video")

        mock_settings = MagicMock()
        mock_settings.foscam_base_path = str(tmp_path)

        with patch.object(media_routes, "get_settings", return_value=mock_settings):
            response = await serve_media_compat(
                path="cameras/backyard/2024/01/15/motion.mp4"
            )

        assert response.path == str(test_file)
        assert response.media_type == "video/mp4"

    @pytest.mark.asyncio
    async def test_returns_404_for_root_cameras_path(self) -> None:
        """Test that just 'cameras' without camera_id returns 404."""
        with pytest.raises(HTTPException) as exc_info:
            await serve_media_compat(path="cameras/")

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_returns_404_for_random_prefix(self) -> None:
        """Test that paths with random prefixes return 404."""
        with pytest.raises(HTTPException) as exc_info:
            await serve_media_compat(path="random/prefix/file.jpg")

        assert exc_info.value.status_code == 404
        assert "Unsupported media path" in exc_info.value.detail["error"]

    @pytest.mark.asyncio
    async def test_handles_thumbnails_at_root(self, tmp_path: Path) -> None:
        """Test thumbnails path at root level."""
        test_file = tmp_path / "detection_abc.png"
        test_file.write_bytes(b"fake detection thumbnail")

        with patch.object(
            media_routes, "_validate_and_resolve_path"
        ) as mock_validate:
            mock_validate.return_value = test_file

            response = await serve_media_compat(path="thumbnails/detection_abc.png")

        assert response.filename == "detection_abc.png"


# =============================================================================
# Router Configuration Tests
# =============================================================================


class TestRouterConfiguration:
    """Tests for the router configuration."""

    def test_router_has_correct_prefix(self) -> None:
        """Test that the router has the correct prefix."""
        assert media_routes.router.prefix == "/api/media"

    def test_router_has_media_tag(self) -> None:
        """Test that the router has the media tag."""
        assert "media" in media_routes.router.tags


# =============================================================================
# Edge Cases and Security Tests
# =============================================================================


class TestEdgeCasesAndSecurity:
    """Additional edge case and security tests."""

    def test_rejects_null_byte_injection_in_path(self, tmp_path: Path) -> None:
        """Test that null bytes in paths are handled safely."""
        # Null byte injection attempt - should be rejected or handled safely
        # Python's pathlib handles this, but we verify behavior
        test_file = tmp_path / "test.jpg"
        test_file.write_bytes(b"content")

        # Path with null byte - this could be used to bypass checks
        # Most systems will reject or truncate at null byte
        malicious_path = "test.jpg\x00.exe"

        # Either raises or safely resolves
        try:
            result = _validate_and_resolve_path(tmp_path, malicious_path)
            # If it doesn't raise, verify it's the jpg file
            assert result.suffix.lower() in ALLOWED_TYPES
        except (HTTPException, ValueError):
            # Expected - null bytes should be rejected
            pass

    def test_rejects_url_encoded_traversal(self, tmp_path: Path) -> None:
        """Test that URL-encoded path traversal is handled.

        Note: FastAPI typically decodes URL encoding before the handler,
        so this tests the decoded form.
        """
        # %2e%2e = ..
        # After URL decoding by FastAPI, this becomes ".."
        with pytest.raises(HTTPException) as exc_info:
            _validate_and_resolve_path(tmp_path, "..%2f..%2fetc%2fpasswd")

        # The path contains ".." so should be rejected
        assert exc_info.value.status_code == 403

    def test_handles_very_long_filename(self, tmp_path: Path) -> None:
        """Test handling of very long filenames."""
        # Create a file with a long name (within filesystem limits)
        long_name = "a" * 200 + ".jpg"

        with pytest.raises(HTTPException) as exc_info:
            _validate_and_resolve_path(tmp_path, long_name)

        # Should return 404 since file doesn't exist
        assert exc_info.value.status_code == 404

    def test_handles_unicode_filename(self, tmp_path: Path) -> None:
        """Test handling of Unicode characters in filenames."""
        test_file = tmp_path / "image_\u4e2d\u6587.jpg"
        test_file.write_bytes(b"unicode filename content")

        result = _validate_and_resolve_path(tmp_path, "image_\u4e2d\u6587.jpg")

        assert result == test_file.resolve()

    def test_handles_spaces_in_filename(self, tmp_path: Path) -> None:
        """Test handling of spaces in filenames."""
        test_file = tmp_path / "my image file.jpg"
        test_file.write_bytes(b"file with spaces")

        result = _validate_and_resolve_path(tmp_path, "my image file.jpg")

        assert result == test_file.resolve()

    def test_handles_special_characters_in_filename(self, tmp_path: Path) -> None:
        """Test handling of special characters in filenames."""
        # Characters that are typically allowed in filenames
        test_file = tmp_path / "image_2024-01-15_12-30-45.jpg"
        test_file.write_bytes(b"dated file")

        result = _validate_and_resolve_path(
            tmp_path, "image_2024-01-15_12-30-45.jpg"
        )

        assert result == test_file.resolve()

    @pytest.mark.asyncio
    async def test_camera_id_with_special_characters(self, tmp_path: Path) -> None:
        """Test camera IDs with special but valid characters."""
        # Camera ID with underscores and hyphens (valid)
        camera_dir = tmp_path / "front-door_1"
        camera_dir.mkdir()
        test_file = camera_dir / "capture.jpg"
        test_file.write_bytes(b"content")

        mock_settings = MagicMock()
        mock_settings.foscam_base_path = str(tmp_path)

        with patch.object(media_routes, "get_settings", return_value=mock_settings):
            response = await serve_camera_file(
                camera_id="front-door_1", filename="capture.jpg"
            )

        assert response.path == str(test_file)

    def test_empty_filename_rejected(self, tmp_path: Path) -> None:
        """Test that empty filenames are handled."""
        # Empty filename should fail path validation
        with pytest.raises(HTTPException) as exc_info:
            _validate_and_resolve_path(tmp_path, "")

        # Empty path resolves to directory, which should fail is_file() check
        assert exc_info.value.status_code == 404

    def test_dot_only_filename_rejected(self, tmp_path: Path) -> None:
        """Test that '.' as filename is rejected."""
        with pytest.raises(HTTPException) as exc_info:
            _validate_and_resolve_path(tmp_path, ".")

        # '.' resolves to directory
        assert exc_info.value.status_code == 404

    def test_hidden_file_allowed_if_correct_extension(self, tmp_path: Path) -> None:
        """Test that hidden files (starting with .) are allowed if extension is valid."""
        test_file = tmp_path / ".hidden.jpg"
        test_file.write_bytes(b"hidden file content")

        result = _validate_and_resolve_path(tmp_path, ".hidden.jpg")

        assert result == test_file.resolve()


# =============================================================================
# Content Type Tests
# =============================================================================


class TestContentTypes:
    """Tests for correct content type handling."""

    @pytest.mark.asyncio
    async def test_jpg_content_type(self, tmp_path: Path) -> None:
        """Test that .jpg files get image/jpeg content type."""
        camera_dir = tmp_path / "cam"
        camera_dir.mkdir()
        test_file = camera_dir / "test.jpg"
        test_file.write_bytes(b"content")

        mock_settings = MagicMock()
        mock_settings.foscam_base_path = str(tmp_path)

        with patch.object(media_routes, "get_settings", return_value=mock_settings):
            response = await serve_camera_file(camera_id="cam", filename="test.jpg")

        assert response.media_type == "image/jpeg"

    @pytest.mark.asyncio
    async def test_jpeg_content_type(self, tmp_path: Path) -> None:
        """Test that .jpeg files get image/jpeg content type."""
        camera_dir = tmp_path / "cam"
        camera_dir.mkdir()
        test_file = camera_dir / "test.jpeg"
        test_file.write_bytes(b"content")

        mock_settings = MagicMock()
        mock_settings.foscam_base_path = str(tmp_path)

        with patch.object(media_routes, "get_settings", return_value=mock_settings):
            response = await serve_camera_file(camera_id="cam", filename="test.jpeg")

        assert response.media_type == "image/jpeg"

    @pytest.mark.asyncio
    async def test_png_content_type(self, tmp_path: Path) -> None:
        """Test that .png files get image/png content type."""
        camera_dir = tmp_path / "cam"
        camera_dir.mkdir()
        test_file = camera_dir / "test.png"
        test_file.write_bytes(b"content")

        mock_settings = MagicMock()
        mock_settings.foscam_base_path = str(tmp_path)

        with patch.object(media_routes, "get_settings", return_value=mock_settings):
            response = await serve_camera_file(camera_id="cam", filename="test.png")

        assert response.media_type == "image/png"

    @pytest.mark.asyncio
    async def test_gif_content_type(self, tmp_path: Path) -> None:
        """Test that .gif files get image/gif content type."""
        camera_dir = tmp_path / "cam"
        camera_dir.mkdir()
        test_file = camera_dir / "test.gif"
        test_file.write_bytes(b"content")

        mock_settings = MagicMock()
        mock_settings.foscam_base_path = str(tmp_path)

        with patch.object(media_routes, "get_settings", return_value=mock_settings):
            response = await serve_camera_file(camera_id="cam", filename="test.gif")

        assert response.media_type == "image/gif"

    @pytest.mark.asyncio
    async def test_mp4_content_type(self, tmp_path: Path) -> None:
        """Test that .mp4 files get video/mp4 content type."""
        camera_dir = tmp_path / "cam"
        camera_dir.mkdir()
        test_file = camera_dir / "test.mp4"
        test_file.write_bytes(b"content")

        mock_settings = MagicMock()
        mock_settings.foscam_base_path = str(tmp_path)

        with patch.object(media_routes, "get_settings", return_value=mock_settings):
            response = await serve_camera_file(camera_id="cam", filename="test.mp4")

        assert response.media_type == "video/mp4"

    @pytest.mark.asyncio
    async def test_avi_content_type(self, tmp_path: Path) -> None:
        """Test that .avi files get video/x-msvideo content type."""
        camera_dir = tmp_path / "cam"
        camera_dir.mkdir()
        test_file = camera_dir / "test.avi"
        test_file.write_bytes(b"content")

        mock_settings = MagicMock()
        mock_settings.foscam_base_path = str(tmp_path)

        with patch.object(media_routes, "get_settings", return_value=mock_settings):
            response = await serve_camera_file(camera_id="cam", filename="test.avi")

        assert response.media_type == "video/x-msvideo"

    @pytest.mark.asyncio
    async def test_webm_content_type(self, tmp_path: Path) -> None:
        """Test that .webm files get video/webm content type."""
        camera_dir = tmp_path / "cam"
        camera_dir.mkdir()
        test_file = camera_dir / "test.webm"
        test_file.write_bytes(b"content")

        mock_settings = MagicMock()
        mock_settings.foscam_base_path = str(tmp_path)

        with patch.object(media_routes, "get_settings", return_value=mock_settings):
            response = await serve_camera_file(camera_id="cam", filename="test.webm")

        assert response.media_type == "video/webm"
