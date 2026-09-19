"""Unit tests for media API routes.

Tests the media file serving endpoints with comprehensive coverage:
- GET /api/media/{path:path} - Compatibility route
- GET /api/media/cameras/{camera_id}/{filename} - Camera files
- GET /api/media/thumbnails/{filename} - Thumbnails
- GET /api/media/clips/{filename} - Video clips
- serve_detection_image() - Detection images (internal function)

These tests follow TDD methodology - comprehensive coverage of happy paths,
error cases, and edge cases with proper mocking.

Coverage focus:
- Path traversal protection
- File type validation
- File not found scenarios
- Permission errors
- Database interactions for detections
- Alternate path resolution for seeded data
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from backend.api.routes.media import (
    ALLOWED_TYPES,
    MAX_PATH_LENGTH,
    _is_path_within,
    _try_alternate_path,
    _validate_and_resolve_path,
)
from backend.models.detection import Detection


class TestValidateAndResolvePath:
    """Tests for _validate_and_resolve_path helper function."""

    def test_valid_path_success(self, tmp_path: Path) -> None:
        """Test validating a valid file path succeeds."""
        # Create test file
        test_file = tmp_path / "test.jpg"
        test_file.write_text("test")

        result = _validate_and_resolve_path(tmp_path, "test.jpg")

        assert result == test_file.resolve()

    def test_path_too_long_returns_414(self, tmp_path: Path) -> None:
        """Test path exceeding MAX_PATH_LENGTH returns 414."""
        long_path = "a" * (MAX_PATH_LENGTH + 1)

        with pytest.raises(HTTPException) as exc_info:
            _validate_and_resolve_path(tmp_path, long_path)

        assert exc_info.value.status_code == 414
        assert "Path too long" in str(exc_info.value.detail)

    def test_path_traversal_with_dots_returns_403(self, tmp_path: Path) -> None:
        """Test path traversal attempt with .. returns 403."""
        with pytest.raises(HTTPException) as exc_info:
            _validate_and_resolve_path(tmp_path, "../etc/passwd")

        assert exc_info.value.status_code == 403
        assert "Path traversal detected" in str(exc_info.value.detail)

    def test_path_starting_with_slash_returns_403(self, tmp_path: Path) -> None:
        """Test absolute path attempt returns 403."""
        with pytest.raises(HTTPException) as exc_info:
            _validate_and_resolve_path(tmp_path, "/etc/passwd")

        assert exc_info.value.status_code == 403
        assert "Path traversal detected" in str(exc_info.value.detail)

    def test_resolve_os_error_returns_400(self, tmp_path: Path) -> None:
        """Test OSError during path resolution returns 400."""
        with patch.object(Path, "resolve", side_effect=OSError("Filesystem error"), autospec=True):
            with pytest.raises(HTTPException) as exc_info:
                _validate_and_resolve_path(tmp_path, "test.jpg")

            assert exc_info.value.status_code == 400
            assert "Invalid path: OSError" in str(exc_info.value.detail)

    def test_resolve_value_error_returns_400(self, tmp_path: Path) -> None:
        """Test ValueError during path resolution returns 400."""
        with patch.object(Path, "resolve", side_effect=ValueError("Invalid path"), autospec=True):
            with pytest.raises(HTTPException) as exc_info:
                _validate_and_resolve_path(tmp_path, "test.jpg")

            assert exc_info.value.status_code == 400
            assert "Invalid path: ValueError" in str(exc_info.value.detail)

    def test_path_outside_base_returns_403(self, tmp_path: Path) -> None:
        """Test path outside base directory returns 403."""
        # Create a file outside the base directory
        other_dir = tmp_path.parent / "other"
        other_dir.mkdir(exist_ok=True)
        test_file = other_dir / "test.jpg"
        test_file.write_text("test")

        # Create a symlink that points outside the base directory
        # This is a realistic path traversal scenario. tmp_path always lives on
        # a symlink-supporting filesystem, so this is unconditional — the old
        # try/except + else:pytest.skip fallback was an unregistered imperative
        # skip that tripped the suppression ratchet on every run (WP5.4).
        symlink = tmp_path / "escape.jpg"
        symlink.symlink_to(test_file)

        with pytest.raises(HTTPException) as exc_info:
            _validate_and_resolve_path(tmp_path, "escape.jpg")

        assert exc_info.value.status_code == 403
        assert "Access denied - path outside allowed directory" in str(exc_info.value.detail)

    def test_file_not_found_returns_404(self, tmp_path: Path) -> None:
        """Test non-existent file returns 404."""
        with pytest.raises(HTTPException) as exc_info:
            _validate_and_resolve_path(tmp_path, "nonexistent.jpg")

        assert exc_info.value.status_code == 404
        assert "File not found" in str(exc_info.value.detail)

    def test_directory_not_file_returns_404(self, tmp_path: Path) -> None:
        """Test directory instead of file returns 404."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()

        with pytest.raises(HTTPException) as exc_info:
            _validate_and_resolve_path(tmp_path, "subdir")

        assert exc_info.value.status_code == 404
        assert "File not found" in str(exc_info.value.detail)

    def test_disallowed_file_type_returns_403(self, tmp_path: Path) -> None:
        """Test disallowed file type returns 403."""
        test_file = tmp_path / "test.exe"
        test_file.write_text("test")

        with pytest.raises(HTTPException) as exc_info:
            _validate_and_resolve_path(tmp_path, "test.exe")

        assert exc_info.value.status_code == 403
        assert "File type not allowed" in str(exc_info.value.detail)

    def test_all_allowed_file_types_pass(self, tmp_path: Path) -> None:
        """Test all allowed file types are accepted."""
        for ext in ALLOWED_TYPES:
            test_file = tmp_path / f"test{ext}"
            test_file.write_text("test")

            result = _validate_and_resolve_path(tmp_path, f"test{ext}")
            assert result == test_file.resolve()


class TestIsPathWithin:
    """Tests for _is_path_within helper function."""

    def test_path_within_base_returns_true(self, tmp_path: Path) -> None:
        """Test path within base directory returns True."""
        subpath = tmp_path / "subdir" / "file.jpg"

        result = _is_path_within(subpath, tmp_path)

        assert result is True

    def test_path_outside_base_returns_false(self, tmp_path: Path) -> None:
        """Test path outside base directory returns False."""
        other_path = tmp_path.parent / "other" / "file.jpg"

        result = _is_path_within(other_path, tmp_path)

        assert result is False

    def test_path_same_as_base_returns_true(self, tmp_path: Path) -> None:
        """Test path equal to base returns True."""
        result = _is_path_within(tmp_path, tmp_path)

        assert result is True


class TestTryAlternatePath:
    """Tests for _try_alternate_path helper function."""

    def test_non_seeded_path_returns_none(self, tmp_path: Path) -> None:
        """Test non-seeded path returns None."""
        result = _try_alternate_path("/some/other/path/file.jpg", tmp_path)

        assert result is None

    def test_seeded_path_file_exists_returns_path(self, tmp_path: Path) -> None:
        """Test seeded path with existing file returns alternate path."""
        # Create alternate file
        alt_file = tmp_path / "front_door" / "image.jpg"
        alt_file.parent.mkdir(parents=True)
        alt_file.write_text("test")

        result = _try_alternate_path("/app/data/cameras/front_door/image.jpg", tmp_path)

        assert result == alt_file.resolve()

    def test_seeded_path_file_not_exists_returns_none(self, tmp_path: Path) -> None:
        """Test seeded path with non-existent file returns None."""
        result = _try_alternate_path("/app/data/cameras/front_door/missing.jpg", tmp_path)

        assert result is None

    def test_seeded_path_directory_not_file_returns_none(self, tmp_path: Path) -> None:
        """Test seeded path pointing to directory returns None."""
        # Create directory instead of file
        alt_dir = tmp_path / "front_door"
        alt_dir.mkdir(parents=True)

        result = _try_alternate_path("/app/data/cameras/front_door", tmp_path)

        assert result is None

    def test_seeded_path_outside_base_returns_none(self, tmp_path: Path) -> None:
        """Test seeded path resolving outside base returns None."""
        # Create a file outside base path
        other_dir = tmp_path.parent / "outside"
        other_dir.mkdir(exist_ok=True)
        outside_file = other_dir / "image.jpg"
        outside_file.write_text("test")

        # Try to use path traversal in the relative portion
        result = _try_alternate_path("/app/data/cameras/../../outside/image.jpg", tmp_path)

        assert result is None


class TestServeCameraFile:
    """Tests for GET /api/media/cameras/{camera_id}/{filename} endpoint."""

    @pytest.mark.asyncio
    async def test_serve_camera_file_success(self, tmp_path: Path) -> None:
        """Test successfully serving a camera file."""
        from fastapi.responses import FileResponse

        from backend.api.routes.media import serve_camera_file

        # Create test file
        camera_dir = tmp_path / "front_door"
        camera_dir.mkdir()
        test_file = camera_dir / "image.jpg"
        test_file.write_text("test image")

        with patch("backend.api.routes.media.get_settings", autospec=True) as mock_settings:
            mock_settings.return_value.foscam_base_path = str(tmp_path)

            result = await serve_camera_file(
                camera_id="front_door",
                filename="image.jpg",
                _rate_limit=None,
            )

        assert isinstance(result, FileResponse)
        assert result.path == str(test_file)
        assert result.media_type == "image/jpeg"

    @pytest.mark.asyncio
    async def test_serve_camera_file_invalid_camera_id_returns_403(self) -> None:
        """Test invalid camera_id with path traversal returns 403."""
        from backend.api.routes.media import serve_camera_file

        with pytest.raises(HTTPException) as exc_info:
            await serve_camera_file(
                camera_id="../../../etc",
                filename="passwd",
                _rate_limit=None,
            )

        assert exc_info.value.status_code == 403
        assert "Invalid camera identifier" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_serve_camera_file_camera_id_starts_with_slash_returns_403(self) -> None:
        """Test camera_id starting with slash returns 403."""
        from backend.api.routes.media import serve_camera_file

        with pytest.raises(HTTPException) as exc_info:
            await serve_camera_file(
                camera_id="/absolute/path",
                filename="image.jpg",
                _rate_limit=None,
            )

        assert exc_info.value.status_code == 403
        assert "Invalid camera identifier" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_serve_camera_file_not_found_returns_404(self, tmp_path: Path) -> None:
        """Test non-existent camera file returns 404."""
        from backend.api.routes.media import serve_camera_file

        with patch("backend.api.routes.media.get_settings", autospec=True) as mock_settings:
            mock_settings.return_value.foscam_base_path = str(tmp_path)

            with pytest.raises(HTTPException) as exc_info:
                await serve_camera_file(
                    camera_id="front_door",
                    filename="nonexistent.jpg",
                    _rate_limit=None,
                )

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_serve_camera_file_subdirectory_path(self, tmp_path: Path) -> None:
        """Test serving file from subdirectory within camera folder."""
        from fastapi.responses import FileResponse

        from backend.api.routes.media import serve_camera_file

        # Create nested structure
        camera_dir = tmp_path / "front_door" / "2025" / "01"
        camera_dir.mkdir(parents=True)
        test_file = camera_dir / "image.jpg"
        test_file.write_text("test")

        with patch("backend.api.routes.media.get_settings", autospec=True) as mock_settings:
            mock_settings.return_value.foscam_base_path = str(tmp_path)

            result = await serve_camera_file(
                camera_id="front_door",
                filename="2025/01/image.jpg",
                _rate_limit=None,
            )

        assert isinstance(result, FileResponse)
        assert result.path == str(test_file)


class TestServeThumbnail:
    """Tests for GET /api/media/thumbnails/{filename} endpoint."""

    @pytest.mark.asyncio
    async def test_serve_thumbnail_success(self, tmp_path: Path) -> None:
        """Test successfully serving a thumbnail."""
        from fastapi.responses import FileResponse

        from backend.api.routes.media import serve_thumbnail

        # Create thumbnail file
        test_file = tmp_path / "thumbnail.jpg"
        test_file.write_text("thumbnail data")

        with patch("backend.api.routes.media.Path", autospec=True) as mock_path_class:
            # Mock the base path calculation
            base_path_mock = MagicMock()
            base_path_mock.__truediv__ = lambda self, x: tmp_path if x == "thumbnails" else self

            file_parent = MagicMock()
            file_parent.parent = MagicMock()
            file_parent.parent.parent = base_path_mock

            mock_path_class.__file__ = str(tmp_path / "routes" / "media.py")
            mock_path_class.return_value = file_parent

            # Patch _validate_and_resolve_path to return our test file
            with patch(
                "backend.api.routes.media._validate_and_resolve_path",
                return_value=test_file.resolve(),
                autospec=True,
            ):
                result = await serve_thumbnail(
                    filename="thumbnail.jpg",
                    _rate_limit=None,
                )

        assert isinstance(result, FileResponse)
        assert result.media_type == "image/jpeg"

    @pytest.mark.asyncio
    async def test_serve_thumbnail_not_found_returns_404(self) -> None:
        """Test non-existent thumbnail returns 404."""
        from backend.api.routes.media import serve_thumbnail

        with patch(
            "backend.api.routes.media._validate_and_resolve_path",
            side_effect=HTTPException(status_code=404, detail={"error": "File not found"}),
            autospec=True,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await serve_thumbnail(
                    filename="nonexistent.jpg",
                    _rate_limit=None,
                )

        assert exc_info.value.status_code == 404


class TestServeDetectionImage:
    """Tests for serve_detection_image internal function."""

    @pytest.mark.asyncio
    async def test_serve_detection_image_success(self, tmp_path: Path) -> None:
        """Test successfully serving a detection image."""
        from fastapi.responses import FileResponse

        from backend.api.routes.media import serve_detection_image

        # Create test file
        camera_dir = tmp_path / "front_door"
        camera_dir.mkdir()
        test_file = camera_dir / "image.jpg"
        test_file.write_text("detection image")

        # Mock database session
        mock_db = AsyncMock()
        mock_detection = MagicMock(spec=Detection)
        mock_detection.id = 1
        mock_detection.camera_id = "front_door"
        mock_detection.file_path = "image.jpg"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_detection
        mock_db.execute.return_value = mock_result

        with patch("backend.api.routes.media.get_settings", autospec=True) as mock_settings:
            mock_settings.return_value.foscam_base_path = str(tmp_path)

            result = await serve_detection_image(
                detection_id=1,
                db=mock_db,
            )

        assert isinstance(result, FileResponse)
        assert result.path == str(test_file)
        assert result.media_type == "image/jpeg"

    @pytest.mark.asyncio
    async def test_serve_detection_image_not_found_returns_404(self) -> None:
        """Test non-existent detection returns 404."""
        from backend.api.routes.media import serve_detection_image

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await serve_detection_image(
                detection_id=999,
                db=mock_db,
            )

        assert exc_info.value.status_code == 404
        assert "Detection not found" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_serve_detection_image_no_file_path_returns_404(self) -> None:
        """Test detection without file_path returns 404."""
        from backend.api.routes.media import serve_detection_image

        mock_db = AsyncMock()
        mock_detection = MagicMock(spec=Detection)
        mock_detection.id = 1
        mock_detection.file_path = None

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_detection
        mock_db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await serve_detection_image(
                detection_id=1,
                db=mock_db,
            )

        assert exc_info.value.status_code == 404
        assert "Detection has no associated file" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_serve_detection_image_absolute_path(self, tmp_path: Path) -> None:
        """Test detection with absolute file path."""
        from fastapi.responses import FileResponse

        from backend.api.routes.media import serve_detection_image

        # Create test file at absolute path
        test_file = tmp_path / "image.jpg"
        test_file.write_text("detection image")

        mock_db = AsyncMock()
        mock_detection = MagicMock(spec=Detection)
        mock_detection.id = 1
        mock_detection.camera_id = "front_door"
        mock_detection.file_path = str(test_file)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_detection
        mock_db.execute.return_value = mock_result

        with patch("backend.api.routes.media.get_settings", autospec=True) as mock_settings:
            mock_settings.return_value.foscam_base_path = str(tmp_path)

            result = await serve_detection_image(
                detection_id=1,
                db=mock_db,
            )

        assert isinstance(result, FileResponse)
        assert result.path == str(test_file)

    @pytest.mark.asyncio
    async def test_serve_detection_image_outside_allowed_dir_returns_403(
        self, tmp_path: Path
    ) -> None:
        """Test detection file outside allowed directory returns 403."""
        from backend.api.routes.media import serve_detection_image

        # Create file outside base path
        outside_dir = tmp_path.parent / "outside"
        outside_dir.mkdir(exist_ok=True)
        outside_file = outside_dir / "image.jpg"
        outside_file.write_text("test")

        mock_db = AsyncMock()
        mock_detection = MagicMock(spec=Detection)
        mock_detection.id = 1
        mock_detection.camera_id = "front_door"
        mock_detection.file_path = str(outside_file)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_detection
        mock_db.execute.return_value = mock_result

        with patch("backend.api.routes.media.get_settings", autospec=True) as mock_settings:
            mock_settings.return_value.foscam_base_path = str(tmp_path)

            with pytest.raises(HTTPException) as exc_info:
                await serve_detection_image(
                    detection_id=1,
                    db=mock_db,
                )

        assert exc_info.value.status_code == 403
        assert "Access denied - file outside allowed directory" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_serve_detection_image_relative_path_success(self, tmp_path: Path) -> None:
        """Test detection with relative file path works correctly."""
        from fastapi.responses import FileResponse

        from backend.api.routes.media import serve_detection_image

        # Create test file at relative location
        camera_dir = tmp_path / "front_door"
        camera_dir.mkdir(parents=True)
        test_file = camera_dir / "image.jpg"
        test_file.write_text("test")

        mock_db = AsyncMock()
        mock_detection = MagicMock(spec=Detection)
        mock_detection.id = 1
        mock_detection.camera_id = "front_door"
        # Use relative path (typical for non-seeded data)
        mock_detection.file_path = "image.jpg"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_detection
        mock_db.execute.return_value = mock_result

        with patch("backend.api.routes.media.get_settings", autospec=True) as mock_settings:
            mock_settings.return_value.foscam_base_path = str(tmp_path)

            result = await serve_detection_image(
                detection_id=1,
                db=mock_db,
            )

        assert isinstance(result, FileResponse)
        assert result.path == str(test_file.resolve())

    @pytest.mark.asyncio
    async def test_serve_detection_image_file_not_on_disk_returns_404(self, tmp_path: Path) -> None:
        """Test detection file not found on disk returns 404."""
        from backend.api.routes.media import serve_detection_image

        mock_db = AsyncMock()
        mock_detection = MagicMock(spec=Detection)
        mock_detection.id = 1
        mock_detection.camera_id = "front_door"
        mock_detection.file_path = "nonexistent.jpg"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_detection
        mock_db.execute.return_value = mock_result

        with patch("backend.api.routes.media.get_settings", autospec=True) as mock_settings:
            mock_settings.return_value.foscam_base_path = str(tmp_path)

            with pytest.raises(HTTPException) as exc_info:
                await serve_detection_image(
                    detection_id=1,
                    db=mock_db,
                )

        assert exc_info.value.status_code == 404
        assert "File not found on disk" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_serve_detection_image_disallowed_file_type_returns_403(
        self, tmp_path: Path
    ) -> None:
        """Test detection file with disallowed type returns 403."""
        from backend.api.routes.media import serve_detection_image

        # Create file with disallowed extension
        test_file = tmp_path / "front_door" / "malware.exe"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("test")

        mock_db = AsyncMock()
        mock_detection = MagicMock(spec=Detection)
        mock_detection.id = 1
        mock_detection.camera_id = "front_door"
        mock_detection.file_path = "malware.exe"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_detection
        mock_db.execute.return_value = mock_result

        with patch("backend.api.routes.media.get_settings", autospec=True) as mock_settings:
            mock_settings.return_value.foscam_base_path = str(tmp_path)

            with pytest.raises(HTTPException) as exc_info:
                await serve_detection_image(
                    detection_id=1,
                    db=mock_db,
                )

        assert exc_info.value.status_code == 403
        assert "File type not allowed" in str(exc_info.value.detail)


class TestServeClip:
    """Tests for GET /api/media/clips/{filename} endpoint."""

    @pytest.mark.asyncio
    async def test_serve_clip_success(self, tmp_path: Path) -> None:
        """Test successfully serving a video clip."""
        from fastapi.responses import FileResponse

        from backend.api.routes.media import serve_clip

        # Create test clip file
        test_file = tmp_path / "123_clip.mp4"
        test_file.write_text("video data")

        # Mock clip generator
        mock_clip_gen = MagicMock()
        mock_clip_gen.clips_directory = tmp_path

        # Pass mock service directly to route handler (DI refactor pattern)
        with patch(
            "backend.api.routes.media._validate_and_resolve_path",
            return_value=test_file.resolve(),
            autospec=True,
        ):
            result = await serve_clip(
                filename="123_clip.mp4",
                _rate_limit=None,
                clip_generator=mock_clip_gen,
            )

        assert isinstance(result, FileResponse)
        assert result.media_type == "video/mp4"

    @pytest.mark.asyncio
    async def test_serve_clip_not_found_returns_404(self) -> None:
        """Test non-existent clip returns 404."""
        from backend.api.routes.media import serve_clip

        mock_clip_gen = MagicMock()
        mock_clip_gen.clips_directory = Path("/clips")

        # Pass mock service directly to route handler (DI refactor pattern)
        with patch(
            "backend.api.routes.media._validate_and_resolve_path",
            side_effect=HTTPException(status_code=404, detail={"error": "File not found"}),
            autospec=True,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await serve_clip(
                    filename="nonexistent.mp4",
                    _rate_limit=None,
                    clip_generator=mock_clip_gen,
                )

        assert exc_info.value.status_code == 404


class TestServeMediaCompat:
    """Tests for GET /api/media/{path:path} compatibility route."""

    @pytest.mark.asyncio
    async def test_compat_cameras_path_routes_to_serve_camera_file(self, tmp_path: Path) -> None:
        """Test cameras/* path routes to serve_camera_file."""
        from fastapi.responses import FileResponse

        from backend.api.routes.media import serve_media_compat

        camera_dir = tmp_path / "front_door"
        camera_dir.mkdir()
        test_file = camera_dir / "image.jpg"
        test_file.write_text("test")

        with patch("backend.api.routes.media.get_settings", autospec=True) as mock_settings:
            mock_settings.return_value.foscam_base_path = str(tmp_path)

            result = await serve_media_compat(
                path="cameras/front_door/image.jpg",
                _rate_limit=None,
            )

        assert isinstance(result, FileResponse)

    @pytest.mark.asyncio
    async def test_compat_cameras_path_missing_camera_returns_404(self) -> None:
        """Test cameras/* path without camera_id returns 404."""
        from backend.api.routes.media import serve_media_compat

        with pytest.raises(HTTPException) as exc_info:
            await serve_media_compat(
                path="cameras/front_door",  # Missing filename
                _rate_limit=None,
            )

        assert exc_info.value.status_code == 404
        assert "File not found" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_compat_thumbnails_path_routes_to_serve_thumbnail(self) -> None:
        """Test thumbnails/* path routes to serve_thumbnail."""
        from backend.api.routes.media import serve_media_compat

        with patch("backend.api.routes.media.serve_thumbnail", autospec=True) as mock_serve:
            mock_serve.return_value = MagicMock()

            await serve_media_compat(
                path="thumbnails/thumb.jpg",
                _rate_limit=None,
            )

        mock_serve.assert_called_once_with(filename="thumb.jpg")

    @pytest.mark.asyncio
    async def test_compat_detections_path_routes_to_serve_detection_image(
        self, tmp_path: Path
    ) -> None:
        """Test detections/* path routes to serve_detection_image."""
        from backend.api.routes.media import serve_media_compat

        # Create test file
        test_file = tmp_path / "front_door" / "image.jpg"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("test")

        # Mock database to return detection
        mock_detection = MagicMock(spec=Detection)
        mock_detection.id = 123
        mock_detection.camera_id = "front_door"
        mock_detection.file_path = "image.jpg"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_detection

        # Patch get_db to yield our mock db
        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result
        mock_db.close = AsyncMock()

        async def mock_get_db():
            yield mock_db

        with patch("backend.api.routes.media.get_settings", autospec=True) as mock_settings:
            mock_settings.return_value.foscam_base_path = str(tmp_path)

            with patch("backend.api.routes.media.get_db", mock_get_db):
                result = await serve_media_compat(
                    path="detections/123",
                    _rate_limit=None,
                )

        from fastapi.responses import FileResponse

        assert isinstance(result, FileResponse)
        mock_db.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_compat_detections_invalid_id_returns_404(self) -> None:
        """Test detections/* with invalid ID returns 404."""
        from backend.api.routes.media import serve_media_compat

        with pytest.raises(HTTPException) as exc_info:
            await serve_media_compat(
                path="detections/not_a_number",
                _rate_limit=None,
            )

        assert exc_info.value.status_code == 404
        assert "Invalid detection ID" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_compat_clips_path_routes_to_serve_clip(self) -> None:
        """Test clips/* path routes to serve_clip with clip_generator dependency."""
        from backend.api.routes.media import serve_media_compat
        from backend.services.clip_generator import ClipGenerator

        with patch("backend.api.routes.media.serve_clip", autospec=True) as mock_serve:
            mock_serve.return_value = MagicMock()

            await serve_media_compat(
                path="clips/123_clip.mp4",
                _rate_limit=None,
            )

        # Verify serve_clip was called with filename and clip_generator
        mock_serve.assert_called_once()
        call_kwargs = mock_serve.call_args.kwargs
        assert call_kwargs["filename"] == "123_clip.mp4"
        assert isinstance(call_kwargs["clip_generator"], ClipGenerator)

    @pytest.mark.asyncio
    async def test_compat_unsupported_path_returns_404(self) -> None:
        """Test unsupported path prefix returns 404."""
        from backend.api.routes.media import serve_media_compat

        with pytest.raises(HTTPException) as exc_info:
            await serve_media_compat(
                path="unsupported/path",
                _rate_limit=None,
            )

        assert exc_info.value.status_code == 404
        assert "Unsupported media path" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_compat_path_with_leading_slash_stripped(self, tmp_path: Path) -> None:
        """Test path with leading slash is stripped correctly."""
        from backend.api.routes.media import serve_media_compat

        with patch("backend.api.routes.media.serve_thumbnail", autospec=True) as mock_serve:
            mock_serve.return_value = MagicMock()

            await serve_media_compat(
                path="/thumbnails/thumb.jpg",  # Leading slash
                _rate_limit=None,
            )

        # Should strip leading slash and route correctly
        mock_serve.assert_called_once_with(filename="thumb.jpg")

    @pytest.mark.asyncio
    async def test_compat_detections_db_unavailable_returns_500(self) -> None:
        """Test detections/* with unavailable database returns 500."""
        from backend.api.routes.media import serve_media_compat

        # Create an empty async generator using a class
        class EmptyAsyncGenerator:
            """Async generator that yields nothing (simulates unavailable DB)."""

            def __aiter__(self):
                return self

            async def __anext__(self):
                raise StopAsyncIteration

        with patch("backend.api.routes.media.get_db", lambda: EmptyAsyncGenerator()):
            with pytest.raises(HTTPException) as exc_info:
                await serve_media_compat(
                    path="detections/123",
                    _rate_limit=None,
                )

        assert exc_info.value.status_code == 500
        assert "Database connection unavailable" in str(exc_info.value.detail)


# =============================================================================
# WP4.4 kill tests — surviving-mutant clusters (triage dossier:
# .wp25-feed/wp44-triage/media.md, clusters V2-V4, T1-T2, S1-S5, S7)
# =============================================================================


class TestWp44MediaGaps:
    """NEM-2662 host prefixes, error-detail contract, and serve boundary gaps."""

    def test_host_prefix_translation_both_variants_case_sensitive(self, tmp_path: Path) -> None:
        """Both host prefixes translate; XX-clobber / upper-case variants must NOT match.

        Kills _try_alternate_path mutmut_15-_18 (T1/T2): the only unit
        coverage for the NEM-2662 host-path translation.
        """
        alt_file = tmp_path / "front_door" / "image.jpg"
        alt_file.parent.mkdir(parents=True)
        alt_file.write_text("test")

        for prefix in ("/export/foscam/", "/mnt/foscam/"):
            result = _try_alternate_path(f"{prefix}front_door/image.jpg", tmp_path)
            assert result == alt_file.resolve(), f"{prefix} must be a recognized host prefix"

        # startswith() is case-sensitive: upper-cased prefixes (mutants) must return None
        assert _try_alternate_path("/EXPORT/FOSCAM/front_door/image.jpg", tmp_path) is None
        assert _try_alternate_path("/MNT/FOSCAM/front_door/image.jpg", tmp_path) is None

    def test_error_detail_path_truncation_boundary(self, tmp_path: Path) -> None:
        """The [:100] + '...' truncation expression is pinned at both sites (414, 400).

        Kills V2/V3 mutmut_13/_44/_45/_48/_50 family: slice 100->101,
        >100->>=100/>101, 'XX...XX' suffix, forced branch conditions.
        """
        # 414 site: only reachable with len > MAX_PATH_LENGTH, so pin truncation only.
        long_path = "b" * (MAX_PATH_LENGTH + 900)
        with pytest.raises(HTTPException) as exc_info:
            _validate_and_resolve_path(tmp_path, long_path)
        assert exc_info.value.status_code == 414
        assert exc_info.value.detail["path"] == "b" * 100 + "..."

        # 400 site (resolve() raises): three boundary lengths.
        with patch.object(Path, "resolve", side_effect=ValueError("boom"), autospec=True):
            with pytest.raises(HTTPException) as exc_info_100:
                _validate_and_resolve_path(tmp_path, "d" * 96 + ".jpg")
            with pytest.raises(HTTPException) as exc_info_101:
                _validate_and_resolve_path(tmp_path, "d" * 97 + ".jpg")
            with pytest.raises(HTTPException) as exc_info_150:
                _validate_and_resolve_path(tmp_path, "c" * 150)

        assert exc_info_100.value.status_code == 400
        assert exc_info_100.value.detail["path"] == "d" * 96 + ".jpg"
        assert exc_info_101.value.status_code == 400
        assert exc_info_101.value.detail["path"] == "d" * 97 + ".jp" + "..."
        assert exc_info_150.value.status_code == 400
        assert exc_info_150.value.detail["path"] == "c" * 100 + "..."

    def test_error_detail_error_field_exact_strings(self, tmp_path: Path) -> None:
        """detail['error'] must EQUAL the message (==, not `in str(detail)`).

        Kills V4 mutmut_30/_60/_74 — XX-clobbered messages survive substring
        asserts because str(dict) still contains the inner text.
        """
        with pytest.raises(HTTPException) as exc:
            _validate_and_resolve_path(tmp_path, "../etc/passwd")
        assert exc.value.status_code == 403
        assert exc.value.detail["error"] == "Path traversal detected"

        with pytest.raises(HTTPException) as exc:
            _validate_and_resolve_path(tmp_path, "nonexistent.jpg")
        assert exc.value.status_code == 404
        assert exc.value.detail["error"] == "File not found"

        # outside-base (symlink escape, same shape as test_path_outside_base_returns_403)
        other_dir = tmp_path.parent / "other_exact"
        other_dir.mkdir(exist_ok=True)
        escape_target = other_dir / "t.jpg"
        escape_target.write_text("t")
        symlink = tmp_path / "escape_exact.jpg"
        try:
            symlink.symlink_to(escape_target)
        except OSError:
            pytest.skip("Symlinks not supported on this filesystem")
        with pytest.raises(HTTPException) as exc:
            _validate_and_resolve_path(tmp_path, "escape_exact.jpg")
        assert exc.value.status_code == 403
        assert exc.value.detail["error"] == "Access denied - path outside allowed directory"

    @pytest.mark.asyncio
    async def test_serve_detection_image_host_path_end_to_end(self, tmp_path: Path) -> None:
        """Detections seeded with host paths serve from the container base (NEM-2662).

        Kills serve_detection_image mutmut_43 (alt call disabled -> 403/404)
        and _45 (None base -> TypeError).
        """
        from fastapi.responses import FileResponse

        from backend.api.routes.media import serve_detection_image

        test_file = tmp_path / "front_door" / "image.jpg"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("detection image")

        mock_db = AsyncMock()
        mock_detection = MagicMock(spec=Detection)
        mock_detection.id = 1
        mock_detection.camera_id = "front_door"
        # factory-shaped host path (tests/factories.py:110)
        mock_detection.file_path = "/export/foscam/front_door/image.jpg"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_detection
        mock_db.execute.return_value = mock_result

        with patch("backend.api.routes.media.get_settings", autospec=True) as mock_settings:
            mock_settings.return_value.foscam_base_path = str(tmp_path)

            result = await serve_detection_image(detection_id=1, db=mock_db)

        assert isinstance(result, FileResponse)
        assert result.path == str(test_file.resolve())

    @pytest.mark.asyncio
    async def test_serve_detection_image_data_cameras_directory_is_allowed(
        self, tmp_path: Path
    ) -> None:
        """<root>/data/cameras is the second allowlisted root of the 403 boundary check.

        data_path = Path(media.__file__).parent.parent.parent.parent / "data"
        / "cameras" is computed at call time; pin __file__ and shape tmp_path
        to the same layout. Any segment clobber (S2 mutmut_39-_42) makes the
        boundary check reject -> 403 instead of serving.
        """
        from fastapi.responses import FileResponse

        from backend.api.routes.media import serve_detection_image

        # 4 .parent hops from x/api/routes/media.py land on tmp_path itself
        routes_dir = tmp_path / "x" / "api" / "routes"
        # parents must exist for Path(__file__).resolve() to succeed
        routes_dir.mkdir(parents=True)
        data_cameras = tmp_path / "data" / "cameras"
        data_cameras.mkdir(parents=True)
        (routes_dir / "media.py").write_text("")  # anchors Path(__file__)
        test_file = data_cameras / "seeded.jpg"
        test_file.write_text("detection image")

        mock_db = AsyncMock()
        mock_detection = MagicMock(spec=Detection)
        mock_detection.id = 1
        mock_detection.camera_id = "front_door"
        mock_detection.file_path = str(test_file)  # absolute: within data_path, NOT foscam base

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_detection
        mock_db.execute.return_value = mock_result

        foscam_base = tmp_path / "foscam"
        foscam_base.mkdir()

        with (
            patch("backend.api.routes.media.__file__", str(routes_dir / "media.py")),
            patch("backend.api.routes.media.get_settings", autospec=True) as mock_settings,
        ):
            mock_settings.return_value.foscam_base_path = str(foscam_base)

            result = await serve_detection_image(detection_id=1, db=mock_db)

        assert isinstance(result, FileResponse)
        assert result.path == str(test_file.resolve())

    @pytest.mark.asyncio
    async def test_serve_detection_image_query_filters_on_detection_id(
        self, tmp_path: Path
    ) -> None:
        """The lookup must actually filter on Detection.id (S3 mutmut_2/_4/_5).

        A stubbed AsyncMock otherwise hides execute(None)/select(None)/
        where(None)/!= — a wrong detection's image gets served.
        """
        from backend.api.routes.media import serve_detection_image

        test_file = tmp_path / "front_door" / "image.jpg"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("detection image")

        mock_db = AsyncMock()
        mock_detection = MagicMock(spec=Detection)
        mock_detection.id = 7
        mock_detection.camera_id = "front_door"
        mock_detection.file_path = "image.jpg"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_detection
        mock_db.execute.return_value = mock_result

        with patch("backend.api.routes.media.get_settings", autospec=True) as mock_settings:
            mock_settings.return_value.foscam_base_path = str(tmp_path)

            await serve_detection_image(detection_id=7, db=mock_db)

        assert mock_db.execute.await_count == 1
        stmt = mock_db.execute.await_args.args[0]
        sql = str(stmt.compile())  # 'detections.id = :id_1'; != mutant -> 'detections.id != :id_1'
        assert "detections.id = " in sql
        assert "!=" not in sql
        # select(None) keeps the WHERE clause but renders 'SELECT NULL AS anon_1'
        # — pin the real detections.* projection (kills mutmut_4)
        assert "NULL AS" not in sql.upper()
        assert "detections.file_path" in sql

    @pytest.mark.asyncio
    async def test_serve_detection_image_directory_named_like_image_returns_404(
        self, tmp_path: Path
    ) -> None:
        """exists-or-isfile guard must stay `or` (S5 mutmut_49/_77).

        A DIRECTORY named snapshot.jpg is not a file -> 404. With or->and the
        guard passes and the .jpg suffix sails through to a FileResponse.
        """
        from backend.api.routes.media import serve_detection_image

        fake_dir = tmp_path / "front_door" / "snapshot.jpg"
        fake_dir.mkdir(parents=True)

        mock_db = AsyncMock()
        mock_detection = MagicMock(spec=Detection)
        mock_detection.id = 1
        mock_detection.camera_id = "front_door"
        mock_detection.file_path = "snapshot.jpg"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_detection
        mock_db.execute.return_value = mock_result

        with patch("backend.api.routes.media.get_settings", autospec=True) as mock_settings:
            mock_settings.return_value.foscam_base_path = str(tmp_path)

            with pytest.raises(HTTPException) as exc_info:
                await serve_detection_image(detection_id=1, db=mock_db)

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail["error"] == "File not found on disk"

    @pytest.mark.asyncio
    async def test_serve_detection_image_response_preserves_filename_and_disposition(
        self, tmp_path: Path
    ) -> None:
        """FileResponse must carry filename=full_path.name -> Content-Disposition header.

        Kills S7 mutmut_105/_107/_108: filename=None mutants drop the header
        (media_type re-guesses from path and looks fine — only these asserts kill).
        """
        from fastapi.responses import FileResponse

        from backend.api.routes.media import serve_detection_image

        test_file = tmp_path / "front_door" / "image.jpg"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("detection image")

        mock_db = AsyncMock()
        mock_detection = MagicMock(spec=Detection)
        mock_detection.id = 1
        mock_detection.camera_id = "front_door"
        mock_detection.file_path = "image.jpg"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_detection
        mock_db.execute.return_value = mock_result

        with patch("backend.api.routes.media.get_settings", autospec=True) as mock_settings:
            mock_settings.return_value.foscam_base_path = str(tmp_path)

            result = await serve_detection_image(detection_id=1, db=mock_db)

        assert isinstance(result, FileResponse)
        assert result.filename == "image.jpg"
        assert result.media_type == "image/jpeg"
        assert 'filename="image.jpg"' in result.headers["content-disposition"]

    @pytest.mark.asyncio
    async def test_serve_detection_image_error_fields_exact(self, tmp_path: Path) -> None:
        """All four serve_detection_image error sites pinned with == (S1 mutmut_16/_29/_74...)."""
        from backend.api.routes.media import serve_detection_image

        def mock_db_for(detection: object | None) -> AsyncMock:
            db = AsyncMock()
            result = MagicMock()
            result.scalar_one_or_none.return_value = detection
            db.execute.return_value = result
            return db

        with patch("backend.api.routes.media.get_settings", autospec=True) as mock_settings:
            mock_settings.return_value.foscam_base_path = str(tmp_path)

            # 1) not found
            with pytest.raises(HTTPException) as exc:
                await serve_detection_image(detection_id=999, db=mock_db_for(None))
            assert exc.value.status_code == 404
            assert exc.value.detail["error"] == "Detection not found"

            # 2) no file path
            det = MagicMock(spec=Detection)
            det.id, det.camera_id, det.file_path = 1, "front_door", None
            with pytest.raises(HTTPException) as exc:
                await serve_detection_image(detection_id=1, db=mock_db_for(det))
            assert exc.value.status_code == 404
            assert exc.value.detail["error"] == "Detection has no associated file"

            # 3) outside allowed directory
            outside = tmp_path.parent / "outside_exact"
            outside.mkdir(exist_ok=True)
            (outside / "x.jpg").write_text("x")
            det2 = MagicMock(spec=Detection)
            det2.id, det2.camera_id, det2.file_path = 1, "front_door", str(outside / "x.jpg")
            with pytest.raises(HTTPException) as exc:
                await serve_detection_image(detection_id=1, db=mock_db_for(det2))
            assert exc.value.status_code == 403
            assert exc.value.detail["error"] == "Access denied - file outside allowed directory"

            # 4) file not on disk
            det3 = MagicMock(spec=Detection)
            det3.id, det3.camera_id, det3.file_path = 1, "front_door", "missing.jpg"
            with pytest.raises(HTTPException) as exc:
                await serve_detection_image(detection_id=1, db=mock_db_for(det3))
            assert exc.value.status_code == 404
            assert exc.value.detail["error"] == "File not found on disk"
