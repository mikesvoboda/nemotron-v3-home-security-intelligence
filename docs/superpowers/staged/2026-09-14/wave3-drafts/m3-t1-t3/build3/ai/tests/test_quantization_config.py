"""Unit tests for quantization_config module.

Tests the BitsAndBytes quantization configuration utilities (NEM-3810).
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

from quantization_config import (
    FourBitQuantType,
    QuantizationMode,
    QuantizationSettings,
    get_memory_estimate,
    get_quantization_config,
)


class TestQuantizationMode:
    """Tests for QuantizationMode enum."""

    def test_mode_values(self) -> None:
        """Test that quantization modes have correct string values."""
        assert QuantizationMode.NONE.value == "none"
        assert QuantizationMode.FOUR_BIT.value == "4bit"
        assert QuantizationMode.EIGHT_BIT.value == "8bit"

    def test_mode_from_string(self) -> None:
        """Test creating mode from string value."""
        assert QuantizationMode("none") == QuantizationMode.NONE
        assert QuantizationMode("4bit") == QuantizationMode.FOUR_BIT
        assert QuantizationMode("8bit") == QuantizationMode.EIGHT_BIT

    def test_invalid_mode_raises(self) -> None:
        """Test that invalid mode strings raise ValueError."""
        with pytest.raises(ValueError):
            QuantizationMode("invalid")


class TestFourBitQuantType:
    """Tests for FourBitQuantType enum."""

    def test_quant_type_values(self) -> None:
        """Test that 4-bit quant types have correct string values."""
        assert FourBitQuantType.NF4.value == "nf4"
        assert FourBitQuantType.FP4.value == "fp4"

    def test_quant_type_from_string(self) -> None:
        """Test creating quant type from string value."""
        assert FourBitQuantType("nf4") == FourBitQuantType.NF4
        assert FourBitQuantType("fp4") == FourBitQuantType.FP4


class TestQuantizationSettings:
    """Tests for QuantizationSettings dataclass."""

    def test_default_settings(self) -> None:
        """Test default settings values."""
        settings = QuantizationSettings()

        assert settings.mode == QuantizationMode.FOUR_BIT
        assert settings.quant_type == FourBitQuantType.NF4
        assert settings.use_double_quant is True
        assert settings.compute_dtype == torch.float16

    def test_custom_settings(self) -> None:
        """Test creating settings with custom values."""
        settings = QuantizationSettings(
            mode=QuantizationMode.EIGHT_BIT,
            quant_type=FourBitQuantType.FP4,
            use_double_quant=False,
            compute_dtype=torch.bfloat16,
        )

        assert settings.mode == QuantizationMode.EIGHT_BIT
        assert settings.quant_type == FourBitQuantType.FP4
        assert settings.use_double_quant is False
        assert settings.compute_dtype == torch.bfloat16

    def test_from_environment_defaults(self) -> None:
        """Test loading settings from environment with defaults."""
        # Clear environment variables for clean test
        with mock.patch.dict(os.environ, {}, clear=True):
            settings = QuantizationSettings.from_environment()

            # Should get defaults
            assert settings.mode == QuantizationMode.FOUR_BIT
            assert settings.quant_type == FourBitQuantType.NF4
            assert settings.use_double_quant is True
            assert settings.compute_dtype == torch.float16

    def test_from_environment_custom(self) -> None:
        """Test loading settings from environment with custom values."""
        env_vars = {
            "NEMOTRON_QUANTIZATION": "8bit",
            "NEMOTRON_4BIT_QUANT_TYPE": "fp4",
            "NEMOTRON_4BIT_DOUBLE_QUANT": "false",
            "NEMOTRON_COMPUTE_DTYPE": "bfloat16",
        }

        with mock.patch.dict(os.environ, env_vars, clear=True):
            settings = QuantizationSettings.from_environment()

            assert settings.mode == QuantizationMode.EIGHT_BIT
            assert settings.quant_type == FourBitQuantType.FP4
            assert settings.use_double_quant is False
            assert settings.compute_dtype == torch.bfloat16

    def test_from_environment_none_mode(self) -> None:
        """Test loading 'none' quantization mode from environment."""
        with mock.patch.dict(os.environ, {"NEMOTRON_QUANTIZATION": "none"}, clear=True):
            settings = QuantizationSettings.from_environment()
            assert settings.mode == QuantizationMode.NONE

    def test_from_environment_invalid_values(self) -> None:
        """Test that invalid environment values fallback to defaults."""
        env_vars = {
            "NEMOTRON_QUANTIZATION": "invalid",
            "NEMOTRON_4BIT_QUANT_TYPE": "invalid",
            "NEMOTRON_COMPUTE_DTYPE": "invalid",
        }

        with mock.patch.dict(os.environ, env_vars, clear=True):
            settings = QuantizationSettings.from_environment()

            # Should fallback to defaults
            assert settings.mode == QuantizationMode.FOUR_BIT
            assert settings.quant_type == FourBitQuantType.NF4
            assert settings.compute_dtype == torch.float16

    def test_from_environment_double_quant_enabled(self) -> None:
        """Test enabling double quantization."""
        for value in ("true", "1", "yes"):
            with mock.patch.dict(os.environ, {"NEMOTRON_4BIT_DOUBLE_QUANT": value}, clear=True):
                settings = QuantizationSettings.from_environment()
                assert settings.use_double_quant is True

    def test_from_environment_double_quant_disabled(self) -> None:
        """Test disabling double quantization."""
        for value in ("false", "0", "no"):
            with mock.patch.dict(os.environ, {"NEMOTRON_4BIT_DOUBLE_QUANT": value}, clear=True):
                settings = QuantizationSettings.from_environment()
                assert settings.use_double_quant is False


class TestGetQuantizationConfig:
    """Tests for get_quantization_config function."""

    def test_none_mode_returns_none(self) -> None:
        """Test that NONE mode returns None config."""
        config = get_quantization_config(mode=QuantizationMode.NONE)
        assert config is None

    def test_missing_bitsandbytes_raises(self) -> None:
        """Test that missing bitsandbytes raises ImportError."""
        import quantization_config as qc_module

        with (
            mock.patch.object(qc_module, "_check_bitsandbytes_available", return_value=False),
            pytest.raises(ImportError, match="bitsandbytes is required"),
        ):
            get_quantization_config(mode=QuantizationMode.FOUR_BIT)

    def test_missing_cuda_raises(self) -> None:
        """Test that missing CUDA raises RuntimeError."""
        import quantization_config as qc_module

        with (
            mock.patch.object(qc_module, "_check_bitsandbytes_available", return_value=True),
            mock.patch.object(qc_module, "_check_cuda_available", return_value=False),
            pytest.raises(RuntimeError, match="CUDA is required"),
        ):
            get_quantization_config(mode=QuantizationMode.FOUR_BIT)

    @pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA not available")
    def test_four_bit_config_structure(self) -> None:
        """Test that 4-bit config has correct structure."""
        try:
            from transformers import BitsAndBytesConfig
        except ImportError:
            pytest.skip("transformers not installed")

        try:
            import bitsandbytes
        except ImportError:
            pytest.skip("bitsandbytes not installed")

        config = get_quantization_config(mode=QuantizationMode.FOUR_BIT)

        assert config is not None
        assert isinstance(config, BitsAndBytesConfig)
        assert config.load_in_4bit is True
        assert config.bnb_4bit_quant_type == "nf4"
        assert config.bnb_4bit_use_double_quant is True


class TestGetMemoryEstimate:
    """Tests for get_memory_estimate function."""

    def test_four_bit_estimate_30b(self) -> None:
        """Test memory estimate for 30B model with 4-bit quantization."""
        estimates = get_memory_estimate(30.0, QuantizationMode.FOUR_BIT)

        # 4-bit should be ~0.55 bytes per param = ~16.5 GB for 30B
        assert 15.0 <= estimates["model_weights"] <= 18.0
        assert estimates["kv_cache_per_1k_tokens"] > 0
        assert estimates["total_min"] > estimates["model_weights"]
        assert estimates["total_recommended"] > estimates["total_min"]

    def test_eight_bit_estimate_30b(self) -> None:
        """Test memory estimate for 30B model with 8-bit quantization."""
        estimates = get_memory_estimate(30.0, QuantizationMode.EIGHT_BIT)

        # 8-bit should be ~1.1 bytes per param = ~33 GB for 30B
        assert 30.0 <= estimates["model_weights"] <= 36.0

    def test_none_estimate_30b(self) -> None:
        """Test memory estimate for 30B model without quantization."""
        estimates = get_memory_estimate(30.0, QuantizationMode.NONE)

        # FP16 should be 2 bytes per param = ~60 GB for 30B
        assert 55.0 <= estimates["model_weights"] <= 65.0

    def test_four_bit_estimate_4b(self) -> None:
        """Test memory estimate for 4B model with 4-bit quantization."""
        estimates = get_memory_estimate(4.0, QuantizationMode.FOUR_BIT)

        # 4-bit should be ~0.55 bytes per param = ~2.2 GB for 4B
        assert 2.0 <= estimates["model_weights"] <= 3.0

    def test_memory_estimate_scaling(self) -> None:
        """Test that memory estimates scale linearly with model size."""
        est_10b = get_memory_estimate(10.0, QuantizationMode.FOUR_BIT)
        est_30b = get_memory_estimate(30.0, QuantizationMode.FOUR_BIT)

        # 30B should be ~3x the weight memory of 10B
        ratio = est_30b["model_weights"] / est_10b["model_weights"]
        assert 2.8 <= ratio <= 3.2


class TestIntegration:
    """Integration tests for quantization configuration."""

    def test_settings_to_config_roundtrip(self) -> None:
        """Test that settings can create a valid config."""
        settings = QuantizationSettings(
            mode=QuantizationMode.NONE,
            quant_type=FourBitQuantType.NF4,
        )

        config = get_quantization_config(settings=settings)
        assert config is None  # NONE mode returns None

    def test_environment_to_settings_to_config(self) -> None:
        """Test full flow from environment to config."""
        with mock.patch.dict(os.environ, {"NEMOTRON_QUANTIZATION": "none"}, clear=True):
            settings = QuantizationSettings.from_environment()
            config = get_quantization_config(settings=settings)

            assert settings.mode == QuantizationMode.NONE
            assert config is None
