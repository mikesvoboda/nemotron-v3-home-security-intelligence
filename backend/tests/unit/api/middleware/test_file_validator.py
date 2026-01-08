"""Unit tests for file magic number validation (NEM-1618).

This module provides comprehensive tests for:
- Magic number detection for various image and video formats
- Validation against claimed MIME types
- ValidatedUploadFile FastAPI dependency
- Cross-format compatibility handling
- Edge cases and malformed files
"""

import io
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException, UploadFile

from backend.api.middleware.file_validator import (
    COMPATIBLE_MIME_TYPES,
    MAGIC_SIGNATURES,
    MagicSignature,
    ValidatedUploadFile,
    _check_avi_signature,
    _check_signature,
    _check_webp_signature,
    detect_mime_type,
    validate_file_magic,
    validate_file_magic_sync,
    validate_upload_file,
)

# =============================================================================
# Test Data - Real Magic Bytes
# =============================================================================

# Real file headers for testing
JPEG_HEADER = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
PNG_HEADER = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x01\x00"
GIF87_HEADER = b"GIF87a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00"
GIF89_HEADER = b"GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00"
WEBP_HEADER = b"RIFF\x00\x00\x00\x00WEBP\x00\x00\x00\x00"
BMP_HEADER = b"BM\x36\x00\x00\x00\x00\x00\x00\x00\x36\x00\x00\x00\x28\x00\x00\x00"
TIFF_LE_HEADER = b"II\x2a\x00\x08\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
TIFF_BE_HEADER = b"MM\x00\x2a\x00\x00\x00\x08\x00\x00\x00\x00\x00\x00\x00\x00"

# Video headers
MP4_HEADER = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42mp41\x00\x00\x00\x00"
MP4_ISOM_HEADER = b"\x00\x00\x00\x1cftypiso5\x00\x00\x02\x00iso5iso6mp41\x00\x00\x00\x00"
MKV_HEADER = b"\x1a\x45\xdf\xa3\x93\x42\x82\x88matroska\x42\x87\x81\x01"
WEBM_HEADER = b"\x1a\x45\xdf\xa3\xa3\x42\x86\x81\x01\x42\xf7\x81\x01"
AVI_HEADER = b"RIFF\x00\x00\x00\x00AVI LIST\x00\x00\x00\x00hdr1"
MOV_HEADER = b"\x00\x00\x00\x14ftypqt  \x00\x00\x00\x00qt  \x00\x00\x00\x00"


# =============================================================================
# MagicSignature Tests
# =============================================================================


class TestMagicSignature:
    """Tests for MagicSignature dataclass."""

    def test_signature_with_default_offset(self):
        """Test MagicSignature with default offset of 0."""
        sig = MagicSignature(b"\xff\xd8\xff")
        assert sig.magic_bytes == b"\xff\xd8\xff"
        assert sig.offset == 0

    def test_signature_with_custom_offset(self):
        """Test MagicSignature with custom offset."""
        sig = MagicSignature(b"ftyp", offset=4)
        assert sig.magic_bytes == b"ftyp"
        assert sig.offset == 4

    def test_signature_is_frozen(self):
        """Test that MagicSignature is immutable."""
        sig = MagicSignature(b"\xff\xd8\xff")
        with pytest.raises(AttributeError):
            sig.magic_bytes = b"changed"


# =============================================================================
# _check_signature Tests
# =============================================================================


class TestCheckSignature:
    """Tests for _check_signature helper function."""

    def test_match_at_offset_zero(self):
        """Test signature match at offset 0."""
        header = b"\xff\xd8\xff\xe0\x00\x10"
        sig = MagicSignature(b"\xff\xd8\xff")
        assert _check_signature(header, sig) is True

    def test_match_at_custom_offset(self):
        """Test signature match at custom offset."""
        header = b"\x00\x00\x00\x18ftypmp42"
        sig = MagicSignature(b"ftyp", offset=4)
        assert _check_signature(header, sig) is True

    def test_no_match_wrong_bytes(self):
        """Test signature mismatch."""
        header = b"\x89PNG\r\n\x1a\n"
        sig = MagicSignature(b"\xff\xd8\xff")
        assert _check_signature(header, sig) is False

    def test_header_too_short(self):
        """Test when header is too short for signature."""
        header = b"\xff\xd8"
        sig = MagicSignature(b"\xff\xd8\xff")
        assert _check_signature(header, sig) is False

    def test_header_too_short_for_offset(self):
        """Test when header is too short for offset."""
        header = b"\x00\x00\x00"
        sig = MagicSignature(b"ftyp", offset=4)
        assert _check_signature(header, sig) is False


# =============================================================================
# Special Signature Checks
# =============================================================================


class TestWebPSignature:
    """Tests for WebP signature detection."""

    def test_valid_webp_signature(self):
        """Test valid WebP signature detection."""
        assert _check_webp_signature(WEBP_HEADER) is True

    def test_invalid_webp_riff_only(self):
        """Test RIFF header without WEBP is not detected as WebP."""
        # AVI also uses RIFF
        assert _check_webp_signature(AVI_HEADER) is False

    def test_header_too_short(self):
        """Test header too short for WebP."""
        assert _check_webp_signature(b"RIFF\x00\x00") is False


class TestAVISignature:
    """Tests for AVI signature detection."""

    def test_valid_avi_signature(self):
        """Test valid AVI signature detection."""
        assert _check_avi_signature(AVI_HEADER) is True

    def test_invalid_avi_riff_only(self):
        """Test RIFF header without AVI is not detected as AVI."""
        assert _check_avi_signature(WEBP_HEADER) is False

    def test_header_too_short(self):
        """Test header too short for AVI."""
        assert _check_avi_signature(b"RIFF\x00\x00") is False


# =============================================================================
# detect_mime_type Tests
# =============================================================================


class TestDetectMimeType:
    """Tests for detect_mime_type function."""

    def test_detect_jpeg(self):
        """Test JPEG detection."""
        assert detect_mime_type(JPEG_HEADER) == "image/jpeg"

    def test_detect_png(self):
        """Test PNG detection."""
        assert detect_mime_type(PNG_HEADER) == "image/png"

    def test_detect_gif87(self):
        """Test GIF87a detection."""
        assert detect_mime_type(GIF87_HEADER) == "image/gif"

    def test_detect_gif89(self):
        """Test GIF89a detection."""
        assert detect_mime_type(GIF89_HEADER) == "image/gif"

    def test_detect_webp(self):
        """Test WebP detection."""
        assert detect_mime_type(WEBP_HEADER) == "image/webp"

    def test_detect_bmp(self):
        """Test BMP detection."""
        assert detect_mime_type(BMP_HEADER) == "image/bmp"

    def test_detect_tiff_little_endian(self):
        """Test TIFF little-endian detection."""
        assert detect_mime_type(TIFF_LE_HEADER) == "image/tiff"

    def test_detect_tiff_big_endian(self):
        """Test TIFF big-endian detection."""
        assert detect_mime_type(TIFF_BE_HEADER) == "image/tiff"

    def test_detect_mp4(self):
        """Test MP4 detection."""
        assert detect_mime_type(MP4_HEADER) == "video/mp4"

    def test_detect_mp4_isom(self):
        """Test MP4 ISOM variant detection."""
        # ISO base media format is common for MP4
        result = detect_mime_type(MP4_ISOM_HEADER)
        assert result in ("video/mp4", "video/quicktime")

    def test_detect_mkv(self):
        """Test MKV/Matroska detection."""
        result = detect_mime_type(MKV_HEADER)
        assert result in ("video/x-matroska", "video/webm")

    def test_detect_webm(self):
        """Test WebM detection."""
        result = detect_mime_type(WEBM_HEADER)
        assert result in ("video/x-matroska", "video/webm")

    def test_detect_avi(self):
        """Test AVI detection."""
        assert detect_mime_type(AVI_HEADER) == "video/x-msvideo"

    def test_detect_mov(self):
        """Test MOV/QuickTime detection."""
        result = detect_mime_type(MOV_HEADER)
        assert result in ("video/mp4", "video/quicktime")

    def test_unknown_format(self):
        """Test unknown format returns None."""
        unknown_header = b"UNKNOWN_FORMAT_12345678"
        assert detect_mime_type(unknown_header) is None

    def test_empty_header(self):
        """Test empty header returns None."""
        assert detect_mime_type(b"") is None


# =============================================================================
# validate_file_magic_sync Tests
# =============================================================================


class TestValidateFileMagicSync:
    """Tests for validate_file_magic_sync function."""

    def test_valid_jpeg(self):
        """Test valid JPEG validation."""
        is_valid, detected = validate_file_magic_sync(JPEG_HEADER, "image/jpeg")
        assert is_valid is True
        assert detected == "image/jpeg"

    def test_valid_png(self):
        """Test valid PNG validation."""
        is_valid, detected = validate_file_magic_sync(PNG_HEADER, "image/png")
        assert is_valid is True
        assert detected == "image/png"

    def test_valid_mp4(self):
        """Test valid MP4 validation."""
        is_valid, detected = validate_file_magic_sync(MP4_HEADER, "video/mp4")
        assert is_valid is True
        assert detected == "video/mp4"

    def test_mismatch_jpeg_as_png(self):
        """Test JPEG content claimed as PNG."""
        is_valid, detected = validate_file_magic_sync(JPEG_HEADER, "image/png")
        assert is_valid is False
        assert detected == "image/jpeg"

    def test_mismatch_png_as_jpeg(self):
        """Test PNG content claimed as JPEG."""
        is_valid, detected = validate_file_magic_sync(PNG_HEADER, "image/jpeg")
        assert is_valid is False
        assert detected == "image/png"

    def test_compatible_types_mp4_quicktime(self):
        """Test compatible types: MP4 and QuickTime share container."""
        # MOV can be detected as MP4 due to shared ftyp structure
        is_valid, _detected = validate_file_magic_sync(MOV_HEADER, "video/mp4")
        assert is_valid is True

    def test_compatible_types_mkv_webm(self):
        """Test compatible types: MKV and WebM share Matroska container."""
        is_valid, _detected = validate_file_magic_sync(MKV_HEADER, "video/webm")
        assert is_valid is True

    def test_strict_mode_rejects_compatible(self):
        """Test strict mode rejects compatible types."""
        # In strict mode, detected type must exactly match claimed type
        is_valid, detected = validate_file_magic_sync(MKV_HEADER, "video/webm", strict=True)
        # MKV header is detected as video/x-matroska, not video/webm exactly
        # Since they share the same signature, this depends on order in dict
        # Either way, strict mode only accepts exact match
        if detected != "video/webm":
            assert is_valid is False

    def test_content_type_with_parameters(self):
        """Test Content-Type with charset/boundary parameters."""
        is_valid, detected = validate_file_magic_sync(JPEG_HEADER, "image/jpeg; charset=utf-8")
        assert is_valid is True
        assert detected == "image/jpeg"

    def test_file_like_object(self):
        """Test validation with file-like object."""
        file_obj = io.BytesIO(PNG_HEADER + b"\x00" * 100)
        is_valid, detected = validate_file_magic_sync(file_obj, "image/png")
        assert is_valid is True
        assert detected == "image/png"
        # File should be seeked back to start
        assert file_obj.tell() == 0

    def test_empty_content(self):
        """Test validation with empty content."""
        is_valid, detected = validate_file_magic_sync(b"", "image/jpeg")
        assert is_valid is False
        assert detected is None

    def test_unknown_format(self):
        """Test validation with unknown format."""
        is_valid, detected = validate_file_magic_sync(b"UNKNOWNFORMAT", "image/jpeg")
        assert is_valid is False
        assert detected is None


# =============================================================================
# validate_file_magic Async Tests
# =============================================================================


class TestValidateFileMagicAsync:
    """Tests for async validate_file_magic function."""

    @pytest.mark.asyncio
    async def test_valid_jpeg_async(self):
        """Test valid JPEG validation (async)."""
        is_valid, detected = await validate_file_magic(JPEG_HEADER, "image/jpeg")
        assert is_valid is True
        assert detected == "image/jpeg"

    @pytest.mark.asyncio
    async def test_mismatch_async(self):
        """Test mismatch detection (async)."""
        is_valid, detected = await validate_file_magic(JPEG_HEADER, "image/png")
        assert is_valid is False
        assert detected == "image/jpeg"


# =============================================================================
# ValidatedUploadFile Tests
# =============================================================================


class TestValidatedUploadFile:
    """Tests for ValidatedUploadFile dependency."""

    @pytest.fixture
    def mock_upload_file(self):
        """Create a mock UploadFile for testing."""

        def _create(content: bytes, content_type: str, filename: str = "test.jpg"):
            mock = MagicMock(spec=UploadFile)
            mock.content_type = content_type
            mock.filename = filename

            # Create async methods
            async def mock_read():
                return content

            async def mock_seek(_pos):
                pass

            mock.read = mock_read
            mock.seek = mock_seek
            return mock

        return _create

    @pytest.mark.asyncio
    async def test_valid_upload(self, mock_upload_file):
        """Test valid file upload passes validation."""
        file = mock_upload_file(JPEG_HEADER + b"\x00" * 100, "image/jpeg")
        validator = ValidatedUploadFile(allowed_types={"image/jpeg", "image/png"})

        result = await validator(file)
        assert result is file

    @pytest.mark.asyncio
    async def test_type_mismatch_raises_400(self, mock_upload_file):
        """Test type mismatch raises 400 error."""
        # JPEG content but claimed as PNG
        file = mock_upload_file(JPEG_HEADER + b"\x00" * 100, "image/png")
        validator = ValidatedUploadFile(allowed_types={"image/jpeg", "image/png"})

        with pytest.raises(HTTPException) as exc_info:
            await validator(file)

        assert exc_info.value.status_code == 400
        assert "does not match" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_disallowed_claimed_type_raises_400(self, mock_upload_file):
        """Test disallowed claimed type raises 400 error."""
        file = mock_upload_file(JPEG_HEADER + b"\x00" * 100, "image/tiff")
        validator = ValidatedUploadFile(allowed_types={"image/jpeg", "image/png"})

        with pytest.raises(HTTPException) as exc_info:
            await validator(file)

        assert exc_info.value.status_code == 400
        assert "not allowed" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_max_size_exceeded_raises_413(self, mock_upload_file):
        """Test file exceeding max size raises 413 error."""
        large_content = JPEG_HEADER + b"\x00" * 10000
        file = mock_upload_file(large_content, "image/jpeg")
        validator = ValidatedUploadFile(
            allowed_types={"image/jpeg"},
            max_size=1000,
        )

        with pytest.raises(HTTPException) as exc_info:
            await validator(file)

        # HTTP 413 Content Too Large (formerly Request Entity Too Large)
        assert exc_info.value.status_code == 413
        assert "too large" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_all_supported_types_allowed(self, mock_upload_file):
        """Test default allows all supported types."""
        file = mock_upload_file(PNG_HEADER + b"\x00" * 100, "image/png")
        validator = ValidatedUploadFile()  # No allowed_types = all supported

        result = await validator(file)
        assert result is file

    @pytest.mark.asyncio
    async def test_empty_content_type_rejected(self, mock_upload_file):
        """Test file with empty content type is rejected when validation is performed."""
        file = mock_upload_file(JPEG_HEADER + b"\x00" * 100, "")
        validator = ValidatedUploadFile(allowed_types={"image/jpeg"})

        # Empty claimed type fails validation because claimed != detected
        # This is expected security behavior - we require explicit content type
        with pytest.raises(HTTPException) as exc_info:
            await validator(file)

        assert exc_info.value.status_code == 400
        assert "does not match" in exc_info.value.detail


# =============================================================================
# validate_upload_file Convenience Function Tests
# =============================================================================


class TestValidateUploadFileFunction:
    """Tests for validate_upload_file convenience function."""

    @pytest.mark.asyncio
    async def test_convenience_function_valid(self):
        """Test convenience function with valid upload."""
        mock = MagicMock(spec=UploadFile)
        mock.content_type = "image/jpeg"
        mock.filename = "test.jpg"

        async def mock_read():
            return JPEG_HEADER + b"\x00" * 100

        async def mock_seek(_pos):
            pass

        mock.read = mock_read
        mock.seek = mock_seek

        result = await validate_upload_file(
            mock,
            allowed_types={"image/jpeg"},
        )
        assert result is mock

    @pytest.mark.asyncio
    async def test_convenience_function_invalid(self):
        """Test convenience function with invalid upload."""
        mock = MagicMock(spec=UploadFile)
        mock.content_type = "image/png"  # Claimed PNG
        mock.filename = "test.png"

        async def mock_read():
            return JPEG_HEADER + b"\x00" * 100  # But actually JPEG

        async def mock_seek(_pos):
            pass

        mock.read = mock_read
        mock.seek = mock_seek

        with pytest.raises(HTTPException):
            await validate_upload_file(
                mock,
                allowed_types={"image/jpeg", "image/png"},
            )


# =============================================================================
# MAGIC_SIGNATURES Configuration Tests
# =============================================================================


class TestMagicSignaturesConfiguration:
    """Tests for MAGIC_SIGNATURES configuration."""

    def test_image_types_present(self):
        """Test all expected image types are configured."""
        expected_image_types = {
            "image/jpeg",
            "image/png",
            "image/gif",
            "image/webp",
            "image/bmp",
            "image/tiff",
        }
        actual_image_types = {k for k in MAGIC_SIGNATURES if k.startswith("image/")}
        assert expected_image_types == actual_image_types

    def test_video_types_present(self):
        """Test all expected video types are configured."""
        expected_video_types = {
            "video/mp4",
            "video/quicktime",
            "video/x-matroska",
            "video/webm",
            "video/x-msvideo",
        }
        actual_video_types = {k for k in MAGIC_SIGNATURES if k.startswith("video/")}
        assert expected_video_types == actual_video_types

    def test_compatible_types_bidirectional(self):
        """Test compatible types mapping is bidirectional."""
        for mime_type, compatible_set in COMPATIBLE_MIME_TYPES.items():
            for compatible in compatible_set:
                # Each compatible type should list the original type as compatible
                assert mime_type in COMPATIBLE_MIME_TYPES.get(compatible, set()), (
                    f"{compatible} should list {mime_type} as compatible"
                )
