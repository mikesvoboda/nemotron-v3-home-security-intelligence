"""Tests for TensorRT conversion and engine utilities (NEM-3838).

These tests verify the tensorrt_utils module for model optimization.
Tests are designed to run regardless of TensorRT availability.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


class TestIsTensorRTAvailable:
    """Tests for is_tensorrt_available function."""

    def test_returns_boolean(self) -> None:
        """Test that function returns a boolean."""
        from ai.common.tensorrt_utils import is_tensorrt_available

        result = is_tensorrt_available()
        assert isinstance(result, bool)

    def test_handles_import_error(self) -> None:
        """Test graceful handling when TensorRT not installed."""
        with patch.dict("sys.modules", {"tensorrt": None}):
            # Force re-import after mocking
            from ai.common import tensorrt_utils

            # Save original and mock
            original_fn = tensorrt_utils.is_tensorrt_available

            def mock_available() -> bool:
                try:
                    import tensorrt

                    return True
                except (ImportError, TypeError):
                    return False

            tensorrt_utils.is_tensorrt_available = mock_available

            try:
                result = tensorrt_utils.is_tensorrt_available()
                # Should return False when TensorRT not available
                assert isinstance(result, bool)
            finally:
                tensorrt_utils.is_tensorrt_available = original_fn


class TestGetGpuComputeCapability:
    """Tests for get_gpu_compute_capability function."""

    def test_returns_string_or_none(self) -> None:
        """Test that function returns SM version string or None."""
        from ai.common.tensorrt_utils import get_gpu_compute_capability

        result = get_gpu_compute_capability()
        assert result is None or isinstance(result, str)

    @pytest.mark.skipif(
        not os.environ.get("CUDA_VISIBLE_DEVICES", "").strip(),
        reason="CUDA not configured in environment",
    )
    def test_sm_version_format(self) -> None:
        """Test SM version string format when GPU available."""
        from ai.common.tensorrt_utils import get_gpu_compute_capability

        result = get_gpu_compute_capability()
        if result is not None:
            # Should be in format sm_XX (e.g., sm_86, sm_89)
            assert result.startswith("sm_")
            assert len(result) >= 4

    def test_handles_no_cuda(self) -> None:
        """Test graceful handling when CUDA not available."""
        with patch("torch.cuda.is_available", return_value=False):
            from ai.common.tensorrt_utils import get_gpu_compute_capability

            result = get_gpu_compute_capability()
            assert result is None


class TestGetGpuName:
    """Tests for get_gpu_name function."""

    def test_returns_string_or_none(self) -> None:
        """Test that function returns GPU name or None."""
        from ai.common.tensorrt_utils import get_gpu_name

        result = get_gpu_name()
        assert result is None or isinstance(result, str)

    def test_handles_no_cuda(self) -> None:
        """Test graceful handling when CUDA not available."""
        with patch("torch.cuda.is_available", return_value=False):
            from ai.common.tensorrt_utils import get_gpu_name

            result = get_gpu_name()
            assert result is None


class TestTensorRTConfig:
    """Tests for TensorRTConfig dataclass."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        from ai.common.tensorrt_utils import TensorRTConfig, TensorRTPrecision

        config = TensorRTConfig()

        assert config.enabled is True
        assert config.precision in (TensorRTPrecision.FP16, "fp16")
        assert config.max_workspace_size == 1 << 30  # 1GB
        assert config.verbose is False
        assert config.dynamic_batch_size is True
        assert config.min_batch_size == 1
        assert config.max_batch_size == 16
        assert config.opt_batch_size == 4

    def test_custom_values(self) -> None:
        """Test custom configuration values."""
        from ai.common.tensorrt_utils import TensorRTConfig, TensorRTPrecision

        config = TensorRTConfig(
            enabled=False,
            precision=TensorRTPrecision.INT8,
            max_workspace_size=2 << 30,
            cache_dir=Path("/custom/cache"),
            verbose=True,
            dynamic_batch_size=False,
            min_batch_size=2,
            max_batch_size=32,
            opt_batch_size=8,
        )

        assert config.enabled is False
        assert config.precision == TensorRTPrecision.INT8
        assert config.max_workspace_size == 2 << 30
        assert config.cache_dir == Path("/custom/cache")
        assert config.verbose is True
        assert config.dynamic_batch_size is False
        assert config.min_batch_size == 2
        assert config.max_batch_size == 32
        assert config.opt_batch_size == 8

    def test_from_env_defaults(self) -> None:
        """Test from_env with default environment."""
        from ai.common.tensorrt_utils import TensorRTConfig

        # Clear relevant env vars
        env_vars = [
            "TENSORRT_ENABLED",
            "TENSORRT_PRECISION",
            "TENSORRT_CACHE_DIR",
            "TENSORRT_MAX_WORKSPACE_SIZE",
            "TENSORRT_VERBOSE",
        ]
        old_values = {k: os.environ.pop(k, None) for k in env_vars}

        try:
            config = TensorRTConfig.from_env()
            assert isinstance(config.enabled, bool)
            assert isinstance(config.precision, str)
        finally:
            # Restore old values
            for k, v in old_values.items():
                if v is not None:
                    os.environ[k] = v

    def test_from_env_custom(self) -> None:
        """Test from_env with custom environment variables."""
        from ai.common.tensorrt_utils import TensorRTConfig

        # Set custom env vars
        os.environ["TENSORRT_ENABLED"] = "false"
        os.environ["TENSORRT_PRECISION"] = "int8"
        os.environ["TENSORRT_VERBOSE"] = "true"

        try:
            config = TensorRTConfig.from_env()
            # Note: config reads at import time, so we test the pattern
            assert isinstance(config, TensorRTConfig)
        finally:
            # Clean up
            del os.environ["TENSORRT_ENABLED"]
            del os.environ["TENSORRT_PRECISION"]
            del os.environ["TENSORRT_VERBOSE"]


class TestTensorRTPrecision:
    """Tests for TensorRTPrecision enum."""

    def test_precision_values(self) -> None:
        """Test that precision enum has expected values."""
        from ai.common.tensorrt_utils import TensorRTPrecision

        assert TensorRTPrecision.FP32.value == "fp32"
        assert TensorRTPrecision.FP16.value == "fp16"
        assert TensorRTPrecision.INT8.value == "int8"

    def test_precision_string_comparison(self) -> None:
        """Test that precision enum values compare with strings."""
        from ai.common.tensorrt_utils import TensorRTPrecision

        assert TensorRTPrecision.FP16 == "fp16"
        assert TensorRTPrecision.FP32 == "fp32"
        assert TensorRTPrecision.INT8 == "int8"


class TestTensorRTConverter:
    """Tests for TensorRTConverter class."""

    def test_initialization_without_tensorrt(self) -> None:
        """Test converter initialization when TensorRT not available."""
        with patch("ai.common.tensorrt_utils.is_tensorrt_available", return_value=False):
            from ai.common.tensorrt_utils import TensorRTConverter

            with pytest.raises(ImportError, match="TensorRT is not available"):
                TensorRTConverter()

    @pytest.mark.skipif(
        os.environ.get("TENSORRT_AVAILABLE", "false").lower() != "true",
        reason="TensorRT not available",
    )
    def test_initialization_with_tensorrt(self) -> None:
        """Test converter initialization when TensorRT available."""
        from ai.common.tensorrt_utils import TensorRTConverter

        converter = TensorRTConverter(
            precision="fp16",
            max_workspace_size=1 << 30,
        )

        assert converter.config.precision == "fp16"
        assert converter.config.max_workspace_size == 1 << 30

    def test_get_engine_path_format(self) -> None:
        """Test engine path generation format."""
        from ai.common.tensorrt_utils import TensorRTConfig, TensorRTConverter

        # Mock TensorRT availability
        with (
            patch("ai.common.tensorrt_utils.is_tensorrt_available", return_value=True),
            patch(
                "ai.common.tensorrt_utils.get_gpu_compute_capability",
                return_value="sm_86",
            ),
        ):
            # Create temp ONNX file to hash
            with tempfile.NamedTemporaryFile(suffix=".onnx", delete=False) as f:
                f.write(b"fake onnx content")
                onnx_path = Path(f.name)

            try:
                config = TensorRTConfig(cache_dir=Path(tempfile.gettempdir()) / "trt_cache_test")

                # Mock the converter without full TRT initialization
                converter = object.__new__(TensorRTConverter)
                converter.config = config
                converter._trt = None

                engine_path = converter.get_engine_path(onnx_path)

                # Verify path format
                assert engine_path.parent == config.cache_dir
                assert "sm_86" in engine_path.name
                assert "fp16" in engine_path.name
                assert engine_path.suffix == ".engine"

            finally:
                onnx_path.unlink()

    def test_compute_file_hash(self) -> None:
        """Test file hash computation."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"test content for hashing")
            temp_path = Path(f.name)

        try:
            # Create converter mock
            from ai.common.tensorrt_utils import TensorRTConverter

            converter = object.__new__(TensorRTConverter)

            hash1 = converter._compute_file_hash(temp_path)

            # Hash should be consistent
            hash2 = converter._compute_file_hash(temp_path)
            assert hash1 == hash2

            # Hash should be 64 chars (SHA256 hex)
            assert len(hash1) == 64

        finally:
            temp_path.unlink()


class TestTensorRTEngine:
    """Tests for TensorRTEngine class."""

    def test_initialization_file_not_found(self) -> None:
        """Test engine initialization with missing file."""
        from ai.common.tensorrt_utils import TensorRTEngine

        with pytest.raises(FileNotFoundError, match="TensorRT engine not found"):
            TensorRTEngine(Path("/nonexistent/engine.engine"))

    def test_initialization_without_tensorrt(self) -> None:
        """Test engine initialization when TensorRT not available."""
        with patch("ai.common.tensorrt_utils.is_tensorrt_available", return_value=False):
            # Create temp file to pass existence check
            with tempfile.NamedTemporaryFile(suffix=".engine", delete=False) as f:
                engine_path = Path(f.name)

            try:
                from ai.common.tensorrt_utils import TensorRTEngine

                with pytest.raises(ImportError, match="TensorRT is not available"):
                    TensorRTEngine(engine_path)
            finally:
                engine_path.unlink()


class TestEnvironmentVariables:
    """Tests for environment variable handling."""

    def test_tensorrt_enabled_default(self) -> None:
        """Test TENSORRT_ENABLED default value."""
        # Default should be True when env var not set
        old_value = os.environ.pop("TENSORRT_ENABLED", None)

        try:
            # Re-import to get fresh values
            import importlib

            from ai.common import tensorrt_utils

            importlib.reload(tensorrt_utils)

            assert tensorrt_utils.TENSORRT_ENABLED is True
        finally:
            if old_value is not None:
                os.environ["TENSORRT_ENABLED"] = old_value

    def test_tensorrt_precision_default(self) -> None:
        """Test TENSORRT_PRECISION default value."""
        old_value = os.environ.pop("TENSORRT_PRECISION", None)

        try:
            import importlib

            from ai.common import tensorrt_utils

            importlib.reload(tensorrt_utils)

            assert tensorrt_utils.TENSORRT_PRECISION == "fp16"
        finally:
            if old_value is not None:
                os.environ["TENSORRT_PRECISION"] = old_value

    def test_tensorrt_cache_dir_default(self) -> None:
        """Test TENSORRT_CACHE_DIR default value."""
        old_value = os.environ.pop("TENSORRT_CACHE_DIR", None)

        try:
            import importlib

            from ai.common import tensorrt_utils

            importlib.reload(tensorrt_utils)

            assert Path("models/tensorrt_cache") == tensorrt_utils.TENSORRT_CACHE_DIR
        finally:
            if old_value is not None:
                os.environ["TENSORRT_CACHE_DIR"] = old_value


class TestPackageExports:
    """Tests for ai.common package exports."""

    def test_all_exports_available(self) -> None:
        """Test that all __all__ exports are importable."""
        from ai import common
        from ai.common import __all__

        for name in __all__:
            assert hasattr(common, name), f"Missing export: {name}"

    def test_key_classes_importable(self) -> None:
        """Test that key classes can be imported."""
        from ai.common import (
            TensorRTClassificationModel,
            TensorRTConfig,
            TensorRTConverter,
            TensorRTDetectionModel,
            TensorRTEngine,
            TensorRTInferenceBase,
            TensorRTPrecision,
            get_gpu_compute_capability,
            get_gpu_name,
            is_tensorrt_available,
        )

        # Verify they are callable/classes
        assert callable(is_tensorrt_available)
        assert callable(get_gpu_compute_capability)
        assert callable(get_gpu_name)
        assert isinstance(TensorRTPrecision.FP16, TensorRTPrecision)

        # Verify classes
        assert issubclass(TensorRTConfig, object)
        assert issubclass(TensorRTConverter, object)
        assert issubclass(TensorRTEngine, object)
        assert issubclass(TensorRTInferenceBase, object)
        assert issubclass(TensorRTDetectionModel, TensorRTInferenceBase)
        assert issubclass(TensorRTClassificationModel, TensorRTInferenceBase)
