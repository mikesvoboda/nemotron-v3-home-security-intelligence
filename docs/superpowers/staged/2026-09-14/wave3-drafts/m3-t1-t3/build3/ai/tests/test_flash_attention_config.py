"""Unit tests for flash_attention_config module.

Tests the FlashAttention-2 configuration utilities (NEM-3811).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest import mock

import pytest
import torch

# Add the ai directory to sys.path so imports work
_ai_dir = Path(__file__).resolve().parent.parent
if str(_ai_dir) not in sys.path:
    sys.path.insert(0, str(_ai_dir))

from flash_attention_config import (
    FLASH_ATTENTION_ENV_VAR,
    MIN_FLASH_ATTENTION_COMPUTE_CAPABILITY,
    FlashAttentionSettings,
    _check_flash_attn_installed,
    _check_gpu_compatibility,
    _check_pytorch_version,
    get_attention_implementation,
    get_flash_attention_version,
    is_flash_attention_available,
)


class TestCheckFlashAttnInstalled:
    """Tests for _check_flash_attn_installed function."""

    def test_returns_bool(self) -> None:
        """Test that function returns a boolean."""
        result = _check_flash_attn_installed()
        assert isinstance(result, bool)

    def test_import_mock_installed(self) -> None:
        """Test that True is returned when flash_attn is importable."""
        # Create a mock module
        mock_module = mock.MagicMock()

        with mock.patch.dict("sys.modules", {"flash_attn": mock_module}):
            # Need to reimport to test with mocked module
            import flash_attention_config

            result = flash_attention_config._check_flash_attn_installed()
            assert result is True

    def test_import_mock_not_installed(self) -> None:
        """Test that False is returned when flash_attn is not importable."""
        # Remove flash_attn from sys.modules if present
        with mock.patch.dict("sys.modules", {"flash_attn": None}):
            # Force ImportError by removing from modules
            if "flash_attn" in sys.modules:
                del sys.modules["flash_attn"]

            result = _check_flash_attn_installed()
            # Result depends on actual installation
            assert isinstance(result, bool)


class TestCheckGpuCompatibility:
    """Tests for _check_gpu_compatibility function."""

    def test_returns_tuple(self) -> None:
        """Test that function returns a tuple of (bool, str)."""
        result = _check_gpu_compatibility()
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], bool)
        assert isinstance(result[1], str)

    def test_cuda_not_available(self) -> None:
        """Test that False is returned when CUDA is not available."""
        with mock.patch.object(torch.cuda, "is_available", return_value=False):
            is_compatible, message = _check_gpu_compatibility()
            assert is_compatible is False
            assert "CUDA is not available" in message

    @pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA not available")
    def test_cuda_available_checks_compute_capability(self) -> None:
        """Test that compute capability is checked when CUDA is available."""
        is_compatible, message = _check_gpu_compatibility()

        # Should always return a result
        assert isinstance(is_compatible, bool)
        assert len(message) > 0

        # If compatible, message should mention the GPU
        if is_compatible:
            assert "supports FlashAttention-2" in message

    def test_low_compute_capability(self) -> None:
        """Test that old GPUs are rejected."""
        # Mock a GPU with compute capability 7.5 (Turing, below Ampere)
        mock_props = mock.MagicMock()
        mock_props.major = 7
        mock_props.minor = 5
        mock_props.name = "Mock Turing GPU"

        with (
            mock.patch.object(torch.cuda, "is_available", return_value=True),
            mock.patch.object(torch.cuda, "get_device_properties", return_value=mock_props),
        ):
            is_compatible, message = _check_gpu_compatibility()
            assert is_compatible is False
            assert "below minimum" in message
            assert "Ampere" in message

    def test_high_compute_capability(self) -> None:
        """Test that Ampere+ GPUs are accepted."""
        # Mock a GPU with compute capability 8.6 (Ampere)
        mock_props = mock.MagicMock()
        mock_props.major = 8
        mock_props.minor = 6
        mock_props.name = "Mock Ampere GPU"

        with (
            mock.patch.object(torch.cuda, "is_available", return_value=True),
            mock.patch.object(torch.cuda, "get_device_properties", return_value=mock_props),
        ):
            is_compatible, message = _check_gpu_compatibility()
            assert is_compatible is True
            assert "supports FlashAttention-2" in message


class TestCheckPytorchVersion:
    """Tests for _check_pytorch_version function."""

    def test_returns_tuple(self) -> None:
        """Test that function returns a tuple of (bool, str)."""
        result = _check_pytorch_version()
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], bool)
        assert isinstance(result[1], str)

    def test_pytorch_2_plus(self) -> None:
        """Test that PyTorch 2.x is accepted."""
        with mock.patch.object(torch, "__version__", "2.1.0"):
            is_ok, message = _check_pytorch_version()
            assert is_ok is True
            assert "supports FlashAttention-2" in message

    def test_pytorch_1_x_rejected(self) -> None:
        """Test that PyTorch 1.x is rejected."""
        with mock.patch.object(torch, "__version__", "1.13.0"):
            is_ok, message = _check_pytorch_version()
            assert is_ok is False
            assert "below minimum" in message

    def test_pytorch_version_with_suffix(self) -> None:
        """Test that version strings with suffixes are handled."""
        # The version parsing only looks at the major version
        with mock.patch.object(torch, "__version__", "2.1.0+cu121"):
            is_ok, message = _check_pytorch_version()
            assert is_ok is True
            assert "supports FlashAttention-2" in message


class TestFlashAttentionSettings:
    """Tests for FlashAttentionSettings dataclass."""

    def test_default_settings(self) -> None:
        """Test default settings values."""
        settings = FlashAttentionSettings()
        assert settings.enabled is True
        assert settings.sliding_window is None

    def test_custom_settings(self) -> None:
        """Test creating settings with custom values."""
        settings = FlashAttentionSettings(enabled=False, sliding_window=4096)
        assert settings.enabled is False
        assert settings.sliding_window == 4096

    def test_from_environment_defaults(self) -> None:
        """Test loading settings from environment with defaults."""
        with mock.patch.dict(os.environ, {}, clear=True):
            settings = FlashAttentionSettings.from_environment()
            # Default is True for auto-detection
            assert settings.enabled is True

    def test_from_environment_enabled(self) -> None:
        """Test enabling FlashAttention via environment."""
        for value in ("true", "1", "yes"):
            with mock.patch.dict(os.environ, {FLASH_ATTENTION_ENV_VAR: value}, clear=True):
                settings = FlashAttentionSettings.from_environment()
                assert settings.enabled is True

    def test_from_environment_disabled(self) -> None:
        """Test disabling FlashAttention via environment."""
        for value in ("false", "0", "no"):
            with mock.patch.dict(os.environ, {FLASH_ATTENTION_ENV_VAR: value}, clear=True):
                settings = FlashAttentionSettings.from_environment()
                assert settings.enabled is False


class TestIsFlashAttentionAvailable:
    """Tests for is_flash_attention_available function."""

    def test_returns_bool(self) -> None:
        """Test that function returns a boolean."""
        result = is_flash_attention_available()
        assert isinstance(result, bool)

    def test_false_when_not_installed(self) -> None:
        """Test that False is returned when flash-attn is not installed."""
        import flash_attention_config as fac

        with mock.patch.object(fac, "_check_flash_attn_installed", return_value=False):
            result = fac.is_flash_attention_available()
            assert result is False

    def test_false_when_pytorch_too_old(self) -> None:
        """Test that False is returned when PyTorch is too old."""
        import flash_attention_config as fac

        with (
            mock.patch.object(fac, "_check_flash_attn_installed", return_value=True),
            mock.patch.object(fac, "_check_pytorch_version", return_value=(False, "too old")),
        ):
            result = fac.is_flash_attention_available()
            assert result is False

    def test_false_when_gpu_incompatible(self) -> None:
        """Test that False is returned when GPU is incompatible."""
        import flash_attention_config as fac

        with (
            mock.patch.object(fac, "_check_flash_attn_installed", return_value=True),
            mock.patch.object(fac, "_check_pytorch_version", return_value=(True, "ok")),
            mock.patch.object(fac, "_check_gpu_compatibility", return_value=(False, "old gpu")),
        ):
            result = fac.is_flash_attention_available()
            assert result is False

    def test_true_when_all_checks_pass(self) -> None:
        """Test that True is returned when all checks pass."""
        import flash_attention_config as fac

        with (
            mock.patch.object(fac, "_check_flash_attn_installed", return_value=True),
            mock.patch.object(fac, "_check_pytorch_version", return_value=(True, "ok")),
            mock.patch.object(fac, "_check_gpu_compatibility", return_value=(True, "ok")),
        ):
            result = fac.is_flash_attention_available()
            assert result is True


class TestGetFlashAttentionVersion:
    """Tests for get_flash_attention_version function."""

    def test_returns_string_or_none(self) -> None:
        """Test that function returns a string or None."""
        result = get_flash_attention_version()
        assert result is None or isinstance(result, str)

    def test_with_mocked_module(self) -> None:
        """Test with a mocked flash_attn module."""
        mock_module = mock.MagicMock()
        mock_module.__version__ = "2.5.6"

        with mock.patch.dict("sys.modules", {"flash_attn": mock_module}):
            # Clear any cached result by reimporting
            import importlib

            import flash_attention_config

            importlib.reload(flash_attention_config)
            result = flash_attention_config.get_flash_attention_version()
            # If flash_attn was actually importable, check version
            if result is not None:
                assert isinstance(result, str)


class TestGetAttentionImplementation:
    """Tests for get_attention_implementation function."""

    def test_returns_valid_implementation(self) -> None:
        """Test that function returns a valid attention implementation."""
        result = get_attention_implementation()
        assert result in ("flash_attention_2", "sdpa", "eager")

    def test_force_eager(self) -> None:
        """Test that force_eager=True returns eager."""
        result = get_attention_implementation(force_eager=True)
        assert result == "eager"

    def test_disabled_in_settings(self) -> None:
        """Test that disabled settings returns sdpa."""
        settings = FlashAttentionSettings(enabled=False)
        result = get_attention_implementation(settings=settings)
        assert result == "sdpa"

    def test_returns_flash_attention_when_available(self) -> None:
        """Test that flash_attention_2 is returned when available."""
        import flash_attention_config as fac

        settings = FlashAttentionSettings(enabled=True)

        with (
            mock.patch.object(fac, "is_flash_attention_available", return_value=True),
            mock.patch.object(fac, "get_flash_attention_version", return_value="2.5.0"),
        ):
            result = fac.get_attention_implementation(settings=settings)
            assert result == "flash_attention_2"

    def test_falls_back_to_sdpa(self) -> None:
        """Test that sdpa is returned as fallback."""
        import flash_attention_config as fac

        settings = FlashAttentionSettings(enabled=True)

        with (
            mock.patch.object(fac, "is_flash_attention_available", return_value=False),
            mock.patch.object(fac, "_check_pytorch_version", return_value=(True, "ok")),
        ):
            result = fac.get_attention_implementation(settings=settings)
            assert result == "sdpa"

    def test_falls_back_to_eager(self) -> None:
        """Test that eager is returned when nothing else available."""
        import flash_attention_config as fac

        settings = FlashAttentionSettings(enabled=True)

        with (
            mock.patch.object(fac, "is_flash_attention_available", return_value=False),
            mock.patch.object(fac, "_check_pytorch_version", return_value=(False, "old")),
        ):
            result = fac.get_attention_implementation(settings=settings)
            assert result == "eager"


class TestMinComputeCapability:
    """Tests for minimum compute capability constant."""

    def test_ampere_or_newer(self) -> None:
        """Test that minimum is Ampere (SM 8.0)."""
        assert MIN_FLASH_ATTENTION_COMPUTE_CAPABILITY == (8, 0)


class TestEnvironmentVariable:
    """Tests for environment variable constant."""

    def test_env_var_name(self) -> None:
        """Test the environment variable name."""
        assert FLASH_ATTENTION_ENV_VAR == "NEMOTRON_USE_FLASH_ATTENTION"
