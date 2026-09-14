"""Tests for backend.core.security module.

Tests path validation, environment variable validation, and model integrity
checking functions for security vulnerabilities including:
- Path traversal prevention (NEM-4501, NEM-4511)
- Environment variable validation (NEM-4513)
- Safe file deletion (NEM-4514)
- Model integrity verification (NEM-4519, NEM-4478)
"""
# ruff: noqa: S108
# S108: /tmp usage is intentional in security tests to verify path validation
# S324: md5 usage is intentional to test checksum algorithm support

from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from backend.core.security import (
    ALLOWED_MODEL_EXTENSIONS,
    ALLOWED_PRELOAD_MODELS,
    DEFAULT_ALLOWED_MODEL_DIRECTORIES,
    PathSecurityError,
    compute_file_checksum,
    get_safe_torch_load_kwargs,
    is_safe_path_for_deletion,
    log_model_load_strict_false_warning,
    validate_engine_path,
    validate_model_path,
    validate_model_path_env,
    validate_onnx_model_source,
    validate_preload_models_env,
    verify_model_integrity,
)

# =============================================================================
# Path Validation Tests (NEM-4501, NEM-4511)
# =============================================================================


class TestValidateModelPath:
    """Tests for validate_model_path function."""

    def test_valid_path_within_models_directory(self) -> None:
        """Valid path within /models should be accepted."""
        # Use /tmp which is in allowed directories for testing
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

    def test_allowed_extensions_pth(self) -> None:
        """PyTorch checkpoint .pth files should be allowed."""
        with tempfile.NamedTemporaryFile(suffix=".pth", dir="/tmp", delete=False) as f:
            temp_path = f.name

        try:
            result = validate_model_path(temp_path, must_exist=True)
            assert result.suffix == ".pth"
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_allowed_extensions_onnx(self) -> None:
        """ONNX model .onnx files should be allowed."""
        with tempfile.NamedTemporaryFile(suffix=".onnx", dir="/tmp", delete=False) as f:
            temp_path = f.name

        try:
            result = validate_model_path(temp_path, must_exist=True)
            assert result.suffix == ".onnx"
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
            # Should not raise even with unusual extension
            result = validate_model_path(temp_path, allowed_extensions=frozenset())
            assert result.exists()
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_path_object_input(self) -> None:
        """Path objects should work as input."""
        with tempfile.NamedTemporaryFile(suffix=".pt", dir="/tmp", delete=False) as f:
            temp_path = Path(f.name)

        try:
            result = validate_model_path(temp_path)
            assert isinstance(result, Path)
        finally:
            temp_path.unlink(missing_ok=True)


class TestValidateEnginePath:
    """Tests for validate_engine_path function."""

    def test_valid_engine_file(self) -> None:
        """Valid .engine file should be accepted."""
        with tempfile.NamedTemporaryFile(suffix=".engine", dir="/tmp", delete=False) as f:
            temp_path = f.name

        try:
            result = validate_engine_path(temp_path)
            assert result.suffix == ".engine"
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_non_engine_extension_rejected(self) -> None:
        """Non-.engine extensions should be rejected."""
        with pytest.raises(PathSecurityError, match="Invalid file extension"):
            validate_engine_path("/tmp/model.pt")


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


# =============================================================================
# Environment Variable Validation Tests (NEM-4513)
# =============================================================================


class TestValidatePreloadModelsEnv:
    """Tests for validate_preload_models_env function."""

    def test_empty_string_returns_empty_list(self) -> None:
        """Empty string should return empty list."""
        result = validate_preload_models_env("")
        assert result == []

    def test_whitespace_only_returns_empty_list(self) -> None:
        """Whitespace-only string should return empty list."""
        result = validate_preload_models_env("   ")
        assert result == []

    def test_single_valid_model(self) -> None:
        """Single valid model name should be accepted."""
        result = validate_preload_models_env("vehicle_classifier")
        assert result == ["vehicle_classifier"]

    def test_multiple_valid_models(self) -> None:
        """Multiple valid model names should be accepted."""
        result = validate_preload_models_env("vehicle_classifier,fashion_clip")
        assert result == ["vehicle_classifier", "fashion_clip"]

    def test_models_with_whitespace(self) -> None:
        """Model names with surrounding whitespace should be trimmed."""
        result = validate_preload_models_env(" vehicle_classifier , fashion_clip ")
        assert result == ["vehicle_classifier", "fashion_clip"]

    def test_invalid_model_rejected(self) -> None:
        """Invalid model names should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid preload models"):
            validate_preload_models_env("malicious_model")

    def test_mixed_valid_invalid_rejected(self) -> None:
        """Mix of valid and invalid models should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid preload models"):
            validate_preload_models_env("vehicle_classifier,evil_model")

    def test_all_allowed_models(self) -> None:
        """All known allowed models should be accepted."""
        for model in ALLOWED_PRELOAD_MODELS:
            result = validate_preload_models_env(model)
            assert result == [model]

    def test_light_service_models(self) -> None:
        """Light service models should be accepted."""
        result = validate_preload_models_env("pose_estimator,threat_detector")
        assert result == ["pose_estimator", "threat_detector"]


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

    def test_empty_string_with_default(self) -> None:
        """Empty string with default should use default."""
        result = validate_model_path_env(
            "YOLO26_MODEL_PATH",
            "",
            default="/tmp/default.pt",
        )
        assert result is not None

    def test_invalid_path_env_rejected(self) -> None:
        """Invalid path in environment variable should raise error."""
        with pytest.raises(PathSecurityError, match="Invalid YOLO26_MODEL_PATH"):
            validate_model_path_env("YOLO26_MODEL_PATH", "/etc/passwd")

    def test_traversal_in_env_rejected(self) -> None:
        """Path traversal in environment variable should raise error."""
        with pytest.raises(PathSecurityError, match="Invalid YOLO26_MODEL_PATH"):
            validate_model_path_env("YOLO26_MODEL_PATH", "/tmp/../etc/passwd")


# =============================================================================
# Model Integrity Tests (NEM-4519)
# =============================================================================


class TestComputeFileChecksum:
    """Tests for compute_file_checksum function."""

    def test_compute_sha256_checksum(self) -> None:
        """SHA-256 checksum should be computed correctly."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"test content")
            temp_path = f.name

        try:
            result = compute_file_checksum(temp_path)
            # Verify it's a valid hex string
            assert len(result) == 64
            assert all(c in "0123456789abcdef" for c in result)
            # Verify it matches expected value
            expected = hashlib.sha256(b"test content").hexdigest()
            assert result == expected
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_compute_blake2b_checksum(self) -> None:
        """Alternative algorithm (blake2b) should work correctly."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"test content")
            temp_path = f.name

        try:
            result = compute_file_checksum(temp_path, algorithm="blake2b")
            # blake2b produces 128 hex chars by default
            assert len(result) == 128
            expected = hashlib.blake2b(b"test content").hexdigest()
            assert result == expected
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_file_not_found_raises_error(self) -> None:
        """Non-existent file should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            compute_file_checksum("/nonexistent/file.pt")


class TestVerifyModelIntegrity:
    """Tests for verify_model_integrity function."""

    def test_verify_with_matching_checksum(self) -> None:
        """Matching checksum should return True."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"model weights")
            temp_path = f.name
            expected = hashlib.sha256(b"model weights").hexdigest()

        try:
            result = verify_model_integrity(temp_path, expected_checksum=expected)
            assert result is True
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_verify_with_mismatching_checksum(self) -> None:
        """Mismatching checksum should return False."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"model weights")
            temp_path = f.name

        try:
            result = verify_model_integrity(temp_path, expected_checksum="wrong_checksum")
            assert result is False
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_verify_without_known_checksum(self) -> None:
        """Unknown checksum should return True with warning."""
        with tempfile.NamedTemporaryFile(suffix=".pt", delete=False) as f:
            f.write(b"model weights")
            temp_path = f.name

        try:
            result = verify_model_integrity(temp_path)
            # Should return True when no checksum is known
            assert result is True
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_verify_nonexistent_file(self) -> None:
        """Non-existent file should return False."""
        result = verify_model_integrity("/nonexistent/model.pt", "somechecksum")
        assert result is False


class TestLogModelLoadStrictFalseWarning:
    """Tests for log_model_load_strict_false_warning function."""

    def test_no_warning_when_no_keys(self) -> None:
        """No warning should be logged when no key mismatches."""
        with patch("backend.core.security.logger") as mock_logger:
            log_model_load_strict_false_warning("/path/model.pt")
            mock_logger.warning.assert_not_called()

    def test_warning_logged_for_missing_keys(self) -> None:
        """Warning should be logged for missing keys."""
        with patch("backend.core.security.logger") as mock_logger:
            log_model_load_strict_false_warning(
                "/path/model.pt",
                missing_keys=["layer1.weight", "layer2.bias"],
            )
            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args[0][0]
            assert "strict=False" in call_args
            assert "Missing keys" in call_args

    def test_warning_logged_for_unexpected_keys(self) -> None:
        """Warning should be logged for unexpected keys."""
        with patch("backend.core.security.logger") as mock_logger:
            log_model_load_strict_false_warning(
                "/path/model.pt",
                unexpected_keys=["extra.weight"],
            )
            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args[0][0]
            assert "Unexpected keys" in call_args


class TestGetSafeTorchLoadKwargs:
    """Tests for get_safe_torch_load_kwargs function."""

    def test_returns_weights_only_true(self) -> None:
        """Should return weights_only=True."""
        kwargs = get_safe_torch_load_kwargs()
        assert kwargs["weights_only"] is True

    def test_returns_map_location_cpu(self) -> None:
        """Should return map_location='cpu'."""
        kwargs = get_safe_torch_load_kwargs()
        assert kwargs["map_location"] == "cpu"


# =============================================================================
# ONNX Security Tests (NEM-4478)
# =============================================================================


class TestValidateOnnxModelSource:
    """Tests for validate_onnx_model_source function."""

    def test_valid_onnx_from_allowed_source(self) -> None:
        """ONNX model from allowed directory should be accepted."""
        with tempfile.NamedTemporaryFile(suffix=".onnx", dir="/tmp", delete=False) as f:
            temp_path = f.name

        try:
            result = validate_onnx_model_source(temp_path)
            assert result is True
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_onnx_from_disallowed_source_rejected(self) -> None:
        """ONNX model from disallowed directory should be rejected."""
        with pytest.raises(PathSecurityError):
            validate_onnx_model_source(
                "/etc/malicious.onnx",
                allowed_sources=("/models",),
            )

    def test_onnx_with_traversal_rejected(self) -> None:
        """ONNX path with traversal should be rejected."""
        with pytest.raises(PathSecurityError, match="Path traversal"):
            validate_onnx_model_source("/tmp/../etc/malicious.onnx")


# =============================================================================
# Constants Tests
# =============================================================================


class TestSecurityConstants:
    """Tests for security module constants."""

    def test_default_allowed_directories(self) -> None:
        """Default allowed directories should include expected paths."""
        assert "/models" in DEFAULT_ALLOWED_MODEL_DIRECTORIES
        assert "/cache" in DEFAULT_ALLOWED_MODEL_DIRECTORIES
        assert "/tmp" in DEFAULT_ALLOWED_MODEL_DIRECTORIES

    def test_allowed_model_extensions(self) -> None:
        """Allowed extensions should include common model formats."""
        assert ".pt" in ALLOWED_MODEL_EXTENSIONS
        assert ".pth" in ALLOWED_MODEL_EXTENSIONS
        assert ".onnx" in ALLOWED_MODEL_EXTENSIONS
        assert ".engine" in ALLOWED_MODEL_EXTENSIONS
        assert ".bin" in ALLOWED_MODEL_EXTENSIONS
        assert ".safetensors" in ALLOWED_MODEL_EXTENSIONS

    def test_allowed_preload_models(self) -> None:
        """Allowed preload models should include expected names."""
        assert "vehicle_classifier" in ALLOWED_PRELOAD_MODELS
        assert "fashion_clip" in ALLOWED_PRELOAD_MODELS
        assert "pose_estimator" in ALLOWED_PRELOAD_MODELS
        assert "threat_detector" in ALLOWED_PRELOAD_MODELS
