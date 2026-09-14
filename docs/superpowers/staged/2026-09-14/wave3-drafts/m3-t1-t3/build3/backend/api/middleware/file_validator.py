"""File magic number validation for uploaded media files.

This module provides file validation based on magic numbers (file signatures)
to ensure uploaded files match their claimed MIME types. This is a defense-in-depth
measure that complements extension-based and PIL-based validation.

Magic number validation prevents:
- File type spoofing attacks where malicious files are disguised with wrong extensions
- Content-type confusion where claimed MIME type doesn't match actual content
- Upload of potentially dangerous file types disguised as images/videos

Supported file types:
- Images: JPEG, PNG, GIF, WebP, BMP, TIFF
- Videos: MP4 (ftyp variants), MKV/WebM (Matroska), AVI, MOV

Usage:
    # As a validation function
    is_valid = await validate_file_magic(file_content, "image/jpeg")

    # As a FastAPI dependency
    @router.post("/upload")
    async def upload_file(
        file: UploadFile = Depends(ValidatedUploadFile(allowed_types={"image/jpeg", "image/png"}))
    ):
        ...
"""

from dataclasses import dataclass
from typing import IO

from fastapi import HTTPException, UploadFile, status

from backend.core.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class MagicSignature:
    """File magic number signature definition.

    Attributes:
        magic_bytes: The magic byte sequence to match
        offset: Byte offset where the signature starts (default 0)
    """

    magic_bytes: bytes
    offset: int = 0


# Magic number signatures for supported file types
# Multiple signatures per MIME type handle format variations
MAGIC_SIGNATURES: dict[str, list[MagicSignature]] = {
    # Image formats
    "image/jpeg": [
        MagicSignature(b"\xff\xd8\xff"),  # JPEG/JFIF
    ],
    "image/png": [
        MagicSignature(b"\x89PNG\r\n\x1a\n"),  # PNG
    ],
    "image/gif": [
        MagicSignature(b"GIF87a"),  # GIF87a
        MagicSignature(b"GIF89a"),  # GIF89a
    ],
    "image/webp": [
        MagicSignature(b"RIFF", offset=0),  # RIFF container
        # WebP has RIFF....WEBP at offset 0 and 8
    ],
    "image/bmp": [
        MagicSignature(b"BM"),  # BMP
    ],
    "image/tiff": [
        MagicSignature(b"II\x2a\x00"),  # TIFF little-endian
        MagicSignature(b"MM\x00\x2a"),  # TIFF big-endian
    ],
    # Video formats
    "video/mp4": [
        # MP4/M4V with ftyp atom at various offsets
        MagicSignature(b"ftyp", offset=4),  # Standard MP4
        MagicSignature(b"ftypisom", offset=4),  # ISO Base Media
        MagicSignature(b"ftypmp4", offset=4),  # MP4 (partial match)
        MagicSignature(b"ftypM4V", offset=4),  # M4V
        MagicSignature(b"ftypmp41", offset=4),  # MP4 v1
        MagicSignature(b"ftypmp42", offset=4),  # MP4 v2
        MagicSignature(b"ftypmmp4", offset=4),  # Mobile MP4
        MagicSignature(b"ftypqt", offset=4),  # QuickTime (also .mov)
        MagicSignature(b"ftypavc1", offset=4),  # AVC/H.264
        MagicSignature(b"ftyphvc1", offset=4),  # HEVC/H.265
    ],
    "video/quicktime": [
        MagicSignature(b"ftyp", offset=4),  # QuickTime (same as MP4 container)
        MagicSignature(b"moov", offset=4),  # QuickTime without ftyp
        MagicSignature(b"mdat", offset=4),  # QuickTime data
        MagicSignature(b"wide", offset=4),  # Wide atom
        MagicSignature(b"free", offset=4),  # Free atom
    ],
    "video/x-matroska": [
        MagicSignature(b"\x1a\x45\xdf\xa3"),  # Matroska/MKV/WebM EBML header
    ],
    "video/webm": [
        MagicSignature(b"\x1a\x45\xdf\xa3"),  # WebM (Matroska container)
    ],
    "video/x-msvideo": [
        MagicSignature(b"RIFF"),  # AVI (RIFF container)
        # AVI has RIFF....AVI at positions 0 and 8
    ],
}

# Reverse mapping: extension to MIME types
EXTENSION_TO_MIME: dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
    ".mp4": "video/mp4",
    ".m4v": "video/mp4",
    ".mov": "video/quicktime",
    ".mkv": "video/x-matroska",
    ".webm": "video/webm",
    ".avi": "video/x-msvideo",
}

# MIME types that share container formats (cross-compatible)
# These MIME types can be detected as each other due to shared container formats
COMPATIBLE_MIME_TYPES: dict[str, set[str]] = {
    "video/mp4": {"video/quicktime"},
    "video/quicktime": {"video/mp4"},
    "video/x-matroska": {"video/webm"},
    "video/webm": {"video/x-matroska"},
    "video/x-msvideo": {"image/webp"},  # Both use RIFF container
    "image/webp": {"video/x-msvideo"},  # Both use RIFF container
}


def _check_signature(header: bytes, signature: MagicSignature) -> bool:
    """Check if header bytes match a magic signature.

    Args:
        header: File header bytes to check
        signature: Magic signature to match against

    Returns:
        True if header matches the signature at the specified offset
    """
    offset = signature.offset
    magic = signature.magic_bytes

    # Ensure we have enough bytes
    if len(header) < offset + len(magic):
        return False

    return header[offset : offset + len(magic)] == magic


def _check_webp_signature(header: bytes) -> bool:
    """Check for WebP file signature (RIFF + WEBP).

    WebP files have RIFF at offset 0 and WEBP at offset 8.

    Args:
        header: File header bytes (at least 12 bytes)

    Returns:
        True if header matches WebP signature
    """
    if len(header) < 12:
        return False

    return header[:4] == b"RIFF" and header[8:12] == b"WEBP"


def _check_avi_signature(header: bytes) -> bool:
    """Check for AVI file signature (RIFF + AVI).

    AVI files have RIFF at offset 0 and AVI  at offset 8.

    Args:
        header: File header bytes (at least 12 bytes)

    Returns:
        True if header matches AVI signature
    """
    if len(header) < 12:
        return False

    return header[:4] == b"RIFF" and header[8:12] == b"AVI "


def detect_mime_type(header: bytes) -> str | None:
    """Detect MIME type from file header bytes.

    Args:
        header: File header bytes (recommend at least 32 bytes)

    Returns:
        Detected MIME type or None if unknown
    """
    # Handle special cases first (RIFF container disambiguation)
    if _check_webp_signature(header):
        return "image/webp"

    if _check_avi_signature(header):
        return "video/x-msvideo"

    # Check all signatures
    for mime_type, signatures in MAGIC_SIGNATURES.items():
        # Skip RIFF-based types handled above
        if mime_type in ("image/webp", "video/x-msvideo"):
            continue

        for signature in signatures:
            if _check_signature(header, signature):
                return mime_type

    return None


def validate_file_magic_sync(
    content: bytes | IO[bytes],
    claimed_type: str,
    *,
    strict: bool = False,
) -> tuple[bool, str | None]:
    """Validate file content matches claimed MIME type (synchronous).

    Args:
        content: File content bytes or file-like object
        claimed_type: Claimed MIME type to validate against
        strict: If True, require exact MIME type match (no compatible types)

    Returns:
        Tuple of (is_valid, detected_type)
        - is_valid: True if content matches claimed type (or compatible type)
        - detected_type: The actual detected MIME type (or None if unknown)
    """
    # Read header bytes
    if isinstance(content, bytes):
        header = content[:32]
    else:
        # File-like object - read and seek back
        header = content.read(32)
        content.seek(0)

    if len(header) == 0:
        logger.warning("Empty file content provided for magic number validation")
        return False, None

    # Detect actual MIME type
    detected_type = detect_mime_type(header)

    if detected_type is None:
        logger.warning(
            "Could not detect MIME type from file magic bytes",
            extra={
                "claimed_type": claimed_type,
                "header_hex": header[:16].hex(),
            },
        )
        return False, None

    # Normalize claimed type (remove parameters)
    claimed_base = claimed_type.split(";")[0].strip().lower()

    # Exact match
    if detected_type == claimed_base:
        return True, detected_type

    # Check compatible types (unless strict mode)
    if not strict:
        compatible = COMPATIBLE_MIME_TYPES.get(detected_type, set())
        if claimed_base in compatible:
            logger.debug(
                f"File type detected as {detected_type}, accepted as compatible with {claimed_base}"
            )
            return True, detected_type

    logger.warning(
        f"File magic mismatch: claimed {claimed_base}, detected {detected_type}",
        extra={
            "claimed_type": claimed_base,
            "detected_type": detected_type,
            "header_hex": header[:16].hex(),
        },
    )
    return False, detected_type


async def validate_file_magic(
    content: bytes | IO[bytes],
    claimed_type: str,
    *,
    strict: bool = False,
) -> tuple[bool, str | None]:
    """Validate file content matches claimed MIME type (async wrapper).

    This is an async wrapper around validate_file_magic_sync for use in
    async contexts. Since magic byte validation is CPU-bound and fast,
    we don't need to run it in a thread pool.

    Args:
        content: File content bytes or file-like object
        claimed_type: Claimed MIME type to validate against
        strict: If True, require exact MIME type match (no compatible types)

    Returns:
        Tuple of (is_valid, detected_type)
    """
    return validate_file_magic_sync(content, claimed_type, strict=strict)


class ValidatedUploadFile:
    """FastAPI dependency for validated file uploads.

    This dependency validates uploaded files using magic number detection
    to ensure the file content matches the claimed Content-Type.

    Usage:
        @router.post("/upload")
        async def upload(
            file: UploadFile = Depends(ValidatedUploadFile(
                allowed_types={"image/jpeg", "image/png"}
            ))
        ):
            # file is guaranteed to be a valid image
            ...
    """

    def __init__(
        self,
        allowed_types: set[str] | None = None,
        max_size: int | None = None,
        strict: bool = False,
    ):
        """Initialize validated upload dependency.

        Args:
            allowed_types: Set of allowed MIME types (None = all supported types)
            max_size: Maximum file size in bytes (None = no limit)
            strict: If True, require exact MIME type match (no compatible types)
        """
        self.allowed_types = allowed_types or set(MAGIC_SIGNATURES.keys())
        self.max_size = max_size
        self.strict = strict

    async def __call__(self, file: UploadFile) -> UploadFile:
        """Validate uploaded file.

        Args:
            file: Uploaded file from FastAPI

        Returns:
            The validated UploadFile (seeked back to start)

        Raises:
            HTTPException: 400 if file is invalid or doesn't match claimed type
            HTTPException: 413 if file exceeds max size
        """
        # Read file content
        content = await file.read()

        # Check file size
        if self.max_size is not None and len(content) > self.max_size:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=f"File too large. Maximum size is {self.max_size} bytes.",
            )

        # Get claimed content type
        claimed_type = file.content_type or ""

        # Check if claimed type is allowed
        claimed_base = claimed_type.split(";")[0].strip().lower()
        if claimed_base and claimed_base not in self.allowed_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File type '{claimed_base}' is not allowed. "
                f"Allowed types: {', '.join(sorted(self.allowed_types))}",
            )

        # Validate magic bytes
        is_valid, detected_type = await validate_file_magic(
            content, claimed_type, strict=self.strict
        )

        if not is_valid:
            detail = "File content does not match declared type"
            if detected_type:
                detail = (
                    f"File content ({detected_type}) does not match declared type ({claimed_type})"
                )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=detail,
            )

        # Check if detected type is in allowed types
        if detected_type and detected_type not in self.allowed_types:
            # Check compatible types
            compatible_allowed = False
            if not self.strict:
                compatible = COMPATIBLE_MIME_TYPES.get(detected_type, set())
                compatible_allowed = bool(compatible & self.allowed_types)

            if not compatible_allowed:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Detected file type '{detected_type}' is not allowed. "
                    f"Allowed types: {', '.join(sorted(self.allowed_types))}",
                )

        # Reset file position for downstream processing
        await file.seek(0)

        return file


# Convenience function for simple validation
async def validate_upload_file(
    file: UploadFile,
    allowed_types: set[str] | None = None,
    max_size: int | None = None,
) -> UploadFile:
    """Validate an uploaded file.

    Convenience function that wraps ValidatedUploadFile for one-off validation.

    Args:
        file: UploadFile to validate
        allowed_types: Set of allowed MIME types
        max_size: Maximum file size in bytes

    Returns:
        The validated UploadFile

    Raises:
        HTTPException: If validation fails
    """
    validator = ValidatedUploadFile(allowed_types=allowed_types, max_size=max_size)
    return await validator(file)
