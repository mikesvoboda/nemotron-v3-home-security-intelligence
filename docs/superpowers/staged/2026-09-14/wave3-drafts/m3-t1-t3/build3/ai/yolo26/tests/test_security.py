"""Tests for ai/yolo26/security.py module.

Tests path validation and environment variable validation functions
for security vulnerabilities including:
- Path traversal prevention (NEM-4501, NEM-4511)
- Safe file deletion (NEM-4514)
- Environment variable validation (NEM-4513)
"""
# ruff: noqa: S108
# S108: /tmp usage is intentional in security tests to verify path validation works correctly

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pytest

# Add parent directory to path for import
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from security import (
    ALLOWED_MODEL_DIRECTORIES,
    ALLOWED_MODEL_EXTENSIONS,
    PathSecurityError,
    is_safe_path_for_deletion,
    validate_model_path,
    validate_model_path_env,
)


class TestValidateModelPath:
    """Tests for validate_model_path function."""

    def test_valid_path_within_tmp_directory(self) -> None:
        """Valid path within /tmp should be accepted."""
        with tempfile.NamedTemporaryFile(suffix=".pt", dir="/tmp", delete=False) as f:
            temp_path = f.name

        try:
            result = validate_model_path(temp_path)
            assert result == Path(temp_path).resolve()
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_path_traversal_rejected(self) -> None:
        """Paths containing '..' should be rejected."""
        with pytest.raises(PathSecurityError, match="Path traversal detected"):
            validate_model_path("/models/../etc/passwd")

    def test_path_traversal_middle_rejected(self) -> None:
        """Paths with traversal in the middle should be rejected."""
        with pytest.raises(PathSecurityError, match="Path traversal detected"):
            validate_model_path("/models/subdir/../../../etc/passwd")

    def test_null_byte_injection_rejected(self) -> None:
        """Paths with null bytes should be rejected."""
        with pytest.raises(PathSecurityError, match="Null byte detected"):
            validate_model_path("/models/model.pt\x00.txt")

    def test_path_outside_allowed_directories_rejected(self) -> None:
        """Paths outside allowed directories should be rejected."""
        with pytest.raises(PathSecurityError, match="not within allowed directories"):
            validate_model_path("/etc/passwd", allowed_extensions=frozenset())

    def test_invalid_extension_rejected(self) -> None:
        """Files with invalid extensions should be rejected."""
        with pytest.raises(PathSecurityError, match="Invalid file extension"):
            validate_model_path("/tmp/model.exe")

    def test_allowed_extensions_pt(self) -> None:
        """PyTorch .pt files should be allowed."""
        with tempfile.NamedTemporaryFile(suffix=".pt", dir="/tmp", delete=False) as f:
            temp_path = f.name

        try:
            result = validate_model_path(temp_path, must_exist=True)
            assert result.suffix == ".pt"
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_allowed_extensions_engine(self) -> None:
        """TensorRT .engine files should be allowed."""
        with tempfile.NamedTemporaryFile(suffix=".engine", dir="/tmp", delete=False) as f:
            temp_path = f.name

        try:
            result = validate_model_path(temp_path, must_exist=True)
            assert result.suffix == ".engine"
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_must_exist_file_not_found(self) -> None:
        """Non-existent file with must_exist=True should raise error."""
        with pytest.raises(PathSecurityError, match="does not exist"):
            validate_model_path("/tmp/nonexistent_model.pt", must_exist=True)

    def test_custom_allowed_directories(self) -> None:
        """Custom allowed directories should work."""
        custom_dirs = ("/custom/models",)
        with pytest.raises(PathSecurityError, match="not within allowed directories"):
            validate_model_path(
                "/tmp/model.pt",
                allowed_directories=custom_dirs,
            )

    def test_empty_extensions_skips_check(self) -> None:
        """Empty allowed_extensions should skip extension check."""
        with tempfile.NamedTemporaryFile(suffix=".xyz", dir="/tmp", delete=False) as f:
            temp_path = f.name

        try:
            result = validate_model_path(temp_path, allowed_extensions=frozenset())
            assert result.exists()
        finally:
            Path(temp_path).unlink(missing_ok=True)


class TestIsSafePathForDeletion:
    """Tests for is_safe_path_for_deletion function."""

    def test_safe_engine_path(self) -> None:
        """Safe engine path should return True."""
        assert is_safe_path_for_deletion(
            "/tmp/model.engine",
            allowed_extensions=frozenset({".engine"}),
        )

    def test_unsafe_path_traversal(self) -> None:
        """Path with traversal should return False."""
        assert not is_safe_path_for_deletion("/tmp/../etc/passwd")

    def test_unsafe_outside_allowed_dir(self) -> None:
        """Path outside allowed directories should return False."""
        assert not is_safe_path_for_deletion(
            "/etc/passwd",
            allowed_extensions=frozenset(),
        )

    def test_unsafe_wrong_extension(self) -> None:
        """Path with wrong extension should return False."""
        assert not is_safe_path_for_deletion(
            "/tmp/important.sh",
            allowed_extensions=frozenset({".engine"}),
        )


class TestValidateModelPathEnv:
    """Tests for validate_model_path_env function."""

    def test_valid_path_env(self) -> None:
        """Valid path in environment variable should be accepted."""
        result = validate_model_path_env("YOLO26_MODEL_PATH", "/tmp/model.pt")
        assert result == str(Path("/tmp/model.pt").resolve())

    def test_none_with_default(self) -> None:
        """None value with default should use default."""
        result = validate_model_path_env(
            "YOLO26_MODEL_PATH",
            None,
            default="/tmp/default.pt",
        )
        assert result is not None
        assert "default.pt" in result

    def test_none_without_default(self) -> None:
        """None value without default should return None."""
        result = validate_model_path_env("YOLO26_MODEL_PATH", None)
        assert result is None

    def test_invalid_path_env_rejected(self) -> None:
        """Invalid path in environment variable should raise error."""
        with pytest.raises(PathSecurityError, match="Invalid YOLO26_MODEL_PATH"):
            validate_model_path_env("YOLO26_MODEL_PATH", "/etc/passwd")

    def test_traversal_in_env_rejected(self) -> None:
        """Path traversal in environment variable should raise error."""
        with pytest.raises(PathSecurityError, match="Invalid YOLO26_MODEL_PATH"):
            validate_model_path_env("YOLO26_MODEL_PATH", "/tmp/../etc/passwd")


class TestSecurityConstants:
    """Tests for security module constants."""

    def test_default_allowed_directories(self) -> None:
        """Default allowed directories should include expected paths."""
        assert "/models" in ALLOWED_MODEL_DIRECTORIES
        assert "/cache" in ALLOWED_MODEL_DIRECTORIES
        assert "/tmp" in ALLOWED_MODEL_DIRECTORIES

    def test_allowed_model_extensions(self) -> None:
        """Allowed extensions should include common model formats."""
        assert ".pt" in ALLOWED_MODEL_EXTENSIONS
        assert ".pth" in ALLOWED_MODEL_EXTENSIONS
        assert ".onnx" in ALLOWED_MODEL_EXTENSIONS
        assert ".engine" in ALLOWED_MODEL_EXTENSIONS
