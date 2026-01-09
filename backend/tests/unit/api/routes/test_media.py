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
        with patch.object(Path, "resolve", side_effect=OSError("Filesystem error")):
            with pytest.raises(HTTPException) as exc_info:
                _validate_and_resolve_path(tmp_path, "test.jpg")

            assert exc_info.value.status_code == 400
            assert "Invalid path: OSError" in str(exc_info.value.detail)

    def test_resolve_value_error_returns_400(self, tmp_path: Path) -> None:
        """Test ValueError during path resolution returns 400."""
        with patch.object(Path, "resolve", side_effect=ValueError("Invalid path")):
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
        # This is a realistic path traversal scenario
        symlink = tmp_path / "escape.jpg"
        try:
            symlink.symlink_to(test_file)
        except OSError:
            # Fall back to a different approach if symlinks not supported
            pass

        if symlink.exists():
            with pytest.raises(HTTPException) as exc_info:
                _validate_and_resolve_path(tmp_path, "escape.jpg")

            assert exc_info.value.status_code == 403
            assert "Access denied - path outside allowed directory" in str(exc_info.value.detail)
        else:
            # Skip this test if symlinks are not supported
            pytest.skip("Symlinks not supported on this filesystem")

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

        with patch("backend.api.routes.media.get_settings") as mock_settings:
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

        with patch("backend.api.routes.media.get_settings") as mock_settings:
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

        with patch("backend.api.routes.media.get_settings") as mock_settings:
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

        with patch("backend.api.routes.media.Path") as mock_path_class:
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

        with patch("backend.api.routes.media.get_settings") as mock_settings:
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

        with patch("backend.api.routes.media.get_settings") as mock_settings:
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

        with patch("backend.api.routes.media.get_settings") as mock_settings:
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

        with patch("backend.api.routes.media.get_settings") as mock_settings:
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

        with patch("backend.api.routes.media.get_settings") as mock_settings:
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

        with patch("backend.api.routes.media.get_settings") as mock_settings:
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

        # Pass clip_generator directly via DI parameter
        with patch(
            "backend.api.routes.media._validate_and_resolve_path",
            return_value=test_file.resolve(),
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

        # Pass clip_generator directly via DI parameter
        with patch(
            "backend.api.routes.media._validate_and_resolve_path",
            side_effect=HTTPException(status_code=404, detail={"error": "File not found"}),
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

        with patch("backend.api.routes.media.get_settings") as mock_settings:
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

        with patch("backend.api.routes.media.serve_thumbnail") as mock_serve:
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

        with patch("backend.api.routes.media.get_settings") as mock_settings:
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
        """Test clips/* path routes to serve_clip."""
        from backend.api.routes.media import serve_media_compat

        with patch("backend.api.routes.media.serve_clip") as mock_serve:
            mock_serve.return_value = MagicMock()

            await serve_media_compat(
                path="clips/123_clip.mp4",
                _rate_limit=None,
            )

        mock_serve.assert_called_once_with(filename="123_clip.mp4")

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

        with patch("backend.api.routes.media.serve_thumbnail") as mock_serve:
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
