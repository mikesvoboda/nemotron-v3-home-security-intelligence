"""Unit tests for MIME type utilities."""

import pytest

from backend.core.mime_types import (
    DEFAULT_IMAGE_MIME,
    DEFAULT_VIDEO_MIME,
    EXTENSION_TO_MIME,
    extension_to_mime,
    get_mime_type,
    get_mime_type_with_default,
    is_image_mime_type,
    is_supported_mime_type,
    is_video_mime_type,
    normalize_file_type,
)


class TestExtensionToMimeMapping:
    """Tests for the EXTENSION_TO_MIME mapping."""

    def test_jpeg_extension_mapped_correctly(self) -> None:
        """Test .jpg and .jpeg both map to image/jpeg."""
        assert EXTENSION_TO_MIME[".jpg"] == "image/jpeg"
        assert EXTENSION_TO_MIME[".jpeg"] == "image/jpeg"

    def test_png_extension_mapped_correctly(self) -> None:
        """Test .png maps to image/png."""
        assert EXTENSION_TO_MIME[".png"] == "image/png"

    def test_video_extensions_mapped_correctly(self) -> None:
        """Test all video extensions map to correct MIME types."""
        assert EXTENSION_TO_MIME[".mp4"] == "video/mp4"
        assert EXTENSION_TO_MIME[".mkv"] == "video/x-matroska"
        assert EXTENSION_TO_MIME[".avi"] == "video/x-msvideo"
        assert EXTENSION_TO_MIME[".mov"] == "video/quicktime"


class TestGetMimeType:
    """Tests for get_mime_type function."""

    @pytest.mark.parametrize(
        ("file_path", "expected_mime"),
        [
            ("/path/to/image.jpg", "image/jpeg"),
            ("/path/to/image.jpeg", "image/jpeg"),
            ("/path/to/image.png", "image/png"),
            ("/path/to/video.mp4", "video/mp4"),
            ("/path/to/video.mkv", "video/x-matroska"),
            ("/path/to/video.avi", "video/x-msvideo"),
            ("/path/to/video.mov", "video/quicktime"),
        ],
    )
    def test_returns_correct_mime_type_for_supported_files(
        self, file_path: str, expected_mime: str
    ) -> None:
        """Test correct MIME type is returned for supported file extensions."""
        assert get_mime_type(file_path) == expected_mime

    def test_returns_none_for_unsupported_extension(self) -> None:
        """Test None is returned for unsupported file extensions."""
        assert get_mime_type("/path/to/file.txt") is None
        assert get_mime_type("/path/to/file.pdf") is None
        assert get_mime_type("/path/to/file.webm") is None

    def test_case_insensitive_extension(self) -> None:
        """Test extension matching is case-insensitive."""
        assert get_mime_type("/path/to/image.JPG") == "image/jpeg"
        assert get_mime_type("/path/to/image.JPEG") == "image/jpeg"
        assert get_mime_type("/path/to/video.MP4") == "video/mp4"


class TestGetMimeTypeWithDefault:
    """Tests for get_mime_type_with_default function."""

    def test_returns_mime_type_for_supported_file(self) -> None:
        """Test correct MIME type is returned for supported files."""
        assert get_mime_type_with_default("/path/to/image.jpg") == "image/jpeg"
        assert get_mime_type_with_default("/path/to/video.mp4") == "video/mp4"

    def test_returns_default_for_unsupported_file(self) -> None:
        """Test default is returned for unsupported files."""
        assert get_mime_type_with_default("/path/to/file.txt") == DEFAULT_IMAGE_MIME

    def test_custom_default_is_used(self) -> None:
        """Test custom default is used when provided."""
        assert (
            get_mime_type_with_default("/path/to/file.txt", "application/octet-stream")
            == "application/octet-stream"
        )


class TestIsImageMimeType:
    """Tests for is_image_mime_type function."""

    @pytest.mark.parametrize(
        "mime_type",
        ["image/jpeg", "image/png", "image/gif", "image/webp"],
    )
    def test_returns_true_for_image_mime_types(self, mime_type: str) -> None:
        """Test True is returned for image MIME types."""
        assert is_image_mime_type(mime_type) is True

    @pytest.mark.parametrize(
        "mime_type",
        ["video/mp4", "video/x-matroska", "application/json", "text/plain"],
    )
    def test_returns_false_for_non_image_mime_types(self, mime_type: str) -> None:
        """Test False is returned for non-image MIME types."""
        assert is_image_mime_type(mime_type) is False

    def test_returns_false_for_none(self) -> None:
        """Test False is returned for None."""
        assert is_image_mime_type(None) is False


class TestIsVideoMimeType:
    """Tests for is_video_mime_type function."""

    @pytest.mark.parametrize(
        "mime_type",
        ["video/mp4", "video/x-matroska", "video/x-msvideo", "video/quicktime"],
    )
    def test_returns_true_for_video_mime_types(self, mime_type: str) -> None:
        """Test True is returned for video MIME types."""
        assert is_video_mime_type(mime_type) is True

    @pytest.mark.parametrize(
        "mime_type",
        ["image/jpeg", "image/png", "application/json", "text/plain"],
    )
    def test_returns_false_for_non_video_mime_types(self, mime_type: str) -> None:
        """Test False is returned for non-video MIME types."""
        assert is_video_mime_type(mime_type) is False

    def test_returns_false_for_none(self) -> None:
        """Test False is returned for None."""
        assert is_video_mime_type(None) is False


class TestIsSupportedMimeType:
    """Tests for is_supported_mime_type function."""

    @pytest.mark.parametrize(
        "mime_type",
        [
            "image/jpeg",
            "image/png",
            "video/mp4",
            "video/x-matroska",
            "video/x-msvideo",
            "video/quicktime",
        ],
    )
    def test_returns_true_for_supported_mime_types(self, mime_type: str) -> None:
        """Test True is returned for supported MIME types."""
        assert is_supported_mime_type(mime_type) is True

    @pytest.mark.parametrize(
        "mime_type",
        ["image/gif", "video/webm", "application/json", "text/plain"],
    )
    def test_returns_false_for_unsupported_mime_types(self, mime_type: str) -> None:
        """Test False is returned for unsupported MIME types."""
        assert is_supported_mime_type(mime_type) is False

    def test_returns_false_for_none(self) -> None:
        """Test False is returned for None."""
        assert is_supported_mime_type(None) is False


class TestExtensionToMime:
    """Tests for extension_to_mime function."""

    def test_extension_with_dot(self) -> None:
        """Test extension with leading dot."""
        assert extension_to_mime(".jpg") == "image/jpeg"
        assert extension_to_mime(".mp4") == "video/mp4"

    def test_extension_without_dot(self) -> None:
        """Test extension without leading dot."""
        assert extension_to_mime("jpg") == "image/jpeg"
        assert extension_to_mime("mp4") == "video/mp4"

    def test_case_insensitive(self) -> None:
        """Test extension matching is case-insensitive."""
        assert extension_to_mime("JPG") == "image/jpeg"
        assert extension_to_mime(".MP4") == "video/mp4"

    def test_unsupported_extension(self) -> None:
        """Test None is returned for unsupported extensions."""
        assert extension_to_mime("txt") is None
        assert extension_to_mime(".pdf") is None


class TestNormalizeFileType:
    """Tests for normalize_file_type function."""

    def test_already_valid_mime_type(self) -> None:
        """Test that valid MIME types are returned unchanged."""
        assert normalize_file_type("image/jpeg") == "image/jpeg"
        assert normalize_file_type("video/mp4") == "video/mp4"

    def test_extension_with_dot(self) -> None:
        """Test extension with leading dot is normalized."""
        assert normalize_file_type(".jpg") == "image/jpeg"
        assert normalize_file_type(".mp4") == "video/mp4"

    def test_extension_without_dot(self) -> None:
        """Test extension without leading dot is normalized."""
        assert normalize_file_type("jpg") == "image/jpeg"
        assert normalize_file_type("mp4") == "video/mp4"

    def test_fallback_to_file_path(self) -> None:
        """Test fallback to file path when file_type is invalid."""
        assert normalize_file_type("invalid", "/path/to/file.jpg") == "image/jpeg"
        assert normalize_file_type("unknown", "/path/to/file.mp4") == "video/mp4"

    def test_none_file_type_with_file_path(self) -> None:
        """Test None file_type falls back to file path."""
        assert normalize_file_type(None, "/path/to/file.jpg") == "image/jpeg"
        assert normalize_file_type(None, "/path/to/video.mp4") == "video/mp4"

    def test_none_returns_none_without_file_path(self) -> None:
        """Test None is returned when both file_type and file_path are None/empty."""
        assert normalize_file_type(None) is None
        assert normalize_file_type(None, None) is None

    def test_invalid_file_type_and_path(self) -> None:
        """Test None is returned when both file_type and file_path are invalid."""
        assert normalize_file_type("invalid", "/path/to/file.txt") is None

    @pytest.mark.parametrize(
        ("file_type", "file_path", "expected"),
        [
            (".jpeg", None, "image/jpeg"),
            (".png", None, "image/png"),
            (".mkv", None, "video/x-matroska"),
            (".avi", None, "video/x-msvideo"),
            (".mov", None, "video/quicktime"),
            ("jpeg", "/path/to/file.png", "image/jpeg"),  # file_type takes precedence
            (None, "/path/to/video.mkv", "video/x-matroska"),
        ],
    )
    def test_various_inputs(
        self, file_type: str | None, file_path: str | None, expected: str | None
    ) -> None:
        """Test various input combinations."""
        assert normalize_file_type(file_type, file_path) == expected


class TestDefaultConstants:
    """Tests for default MIME type constants."""

    def test_default_image_mime(self) -> None:
        """Test DEFAULT_IMAGE_MIME is image/jpeg."""
        assert DEFAULT_IMAGE_MIME == "image/jpeg"

    def test_default_video_mime(self) -> None:
        """Test DEFAULT_VIDEO_MIME is video/mp4."""
        assert DEFAULT_VIDEO_MIME == "video/mp4"
