"""MIME type utilities for media file handling.

This module provides a centralized mapping between file extensions and MIME types
for consistent handling across the application. All media file type detection
should use these utilities rather than ad-hoc extension checking.

Supported media types:
- Images: .jpg, .jpeg, .png
- Videos: .mp4, .mkv, .avi, .mov
"""

from pathlib import Path

# MIME type mappings
# Images
IMAGE_MIME_TYPES: dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}

# Videos
VIDEO_MIME_TYPES: dict[str, str] = {
    ".mp4": "video/mp4",
    ".mkv": "video/x-matroska",
    ".avi": "video/x-msvideo",
    ".mov": "video/quicktime",
}

# Combined mapping
EXTENSION_TO_MIME: dict[str, str] = {**IMAGE_MIME_TYPES, **VIDEO_MIME_TYPES}

# Reverse mapping (MIME type to primary extension)
MIME_TO_EXTENSION: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "video/mp4": ".mp4",
    "video/x-matroska": ".mkv",
    "video/x-msvideo": ".avi",
    "video/quicktime": ".mov",
}

# Default MIME types by category
DEFAULT_IMAGE_MIME = "image/jpeg"
DEFAULT_VIDEO_MIME = "video/mp4"


def get_mime_type(file_path: str | Path) -> str | None:
    """Get MIME type for a file based on its extension.

    Args:
        file_path: Path to the file (string or Path object)

    Returns:
        MIME type string (e.g., "image/jpeg", "video/mp4") or None if unsupported
    """
    suffix = Path(file_path).suffix.lower()
    return EXTENSION_TO_MIME.get(suffix)


def get_mime_type_with_default(file_path: str | Path, default: str = DEFAULT_IMAGE_MIME) -> str:
    """Get MIME type for a file with a fallback default.

    Args:
        file_path: Path to the file (string or Path object)
        default: Default MIME type if extension is not recognized

    Returns:
        MIME type string
    """
    return get_mime_type(file_path) or default


def is_image_mime_type(mime_type: str | None) -> bool:
    """Check if a MIME type is an image type.

    Args:
        mime_type: MIME type string to check

    Returns:
        True if MIME type is an image type
    """
    if not mime_type:
        return False
    return mime_type.startswith("image/")


def is_video_mime_type(mime_type: str | None) -> bool:
    """Check if a MIME type is a video type.

    Args:
        mime_type: MIME type string to check

    Returns:
        True if MIME type is a video type
    """
    if not mime_type:
        return False
    return mime_type.startswith("video/")


def is_supported_mime_type(mime_type: str | None) -> bool:
    """Check if a MIME type is supported by the application.

    Args:
        mime_type: MIME type string to check

    Returns:
        True if MIME type is supported (in MIME_TO_EXTENSION mapping)
    """
    if not mime_type:
        return False
    return mime_type in MIME_TO_EXTENSION


def extension_to_mime(extension: str) -> str | None:
    """Convert a file extension to its MIME type.

    Args:
        extension: File extension with or without leading dot (e.g., ".jpg" or "jpg")

    Returns:
        MIME type string or None if extension is not recognized
    """
    # Normalize extension to have leading dot and be lowercase
    ext = extension.lower()
    if not ext.startswith("."):
        ext = f".{ext}"
    return EXTENSION_TO_MIME.get(ext)


def normalize_file_type(file_type: str | None, file_path: str | None = None) -> str | None:
    """Normalize a file_type value to MIME type format.

    Handles both MIME types and file extensions, returning a consistent MIME type.
    This is useful for migrating existing data that may contain mixed formats.

    Args:
        file_type: Original file_type value (could be MIME type or extension)
        file_path: Optional file path to derive MIME type if file_type is invalid

    Returns:
        Normalized MIME type string, or None if cannot be determined
    """
    if not file_type:
        # Fall back to file path if available
        if file_path:
            return get_mime_type(file_path)
        return None

    # Already a valid MIME type?
    if "/" in file_type and is_supported_mime_type(file_type):
        return file_type

    # Try to convert from extension
    mime_type = extension_to_mime(file_type)
    if mime_type:
        return mime_type

    # Fall back to file path if available
    if file_path:
        return get_mime_type(file_path)

    return None
