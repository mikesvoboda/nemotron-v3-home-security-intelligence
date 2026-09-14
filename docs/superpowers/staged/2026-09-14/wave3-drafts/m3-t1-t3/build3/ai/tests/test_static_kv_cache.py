"""Tests for StaticCache KV Cache Optimization (NEM-3814).

Tests for:
- StaticCache creation and configuration
- Cache size estimation
- StaticCacheManager functionality
- StaticCacheWrapper for generation
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import torch

# Add parent directory to path for imports
_ai_dir = Path(__file__).parent.parent
if str(_ai_dir) not in sys.path:
    sys.path.insert(0, str(_ai_dir))

from static_kv_cache import (
    CacheType,
    StaticCacheConfig,
    StaticCacheManager,
    StaticCacheWrapper,
    create_static_cache,
    estimate_cache_size_bytes,
    estimate_cache_size_mb,
    estimate_optimal_cache_length,
    get_cache_for_generation,
    get_model_cache_config,
)


class TestIsStaticCacheSupported:
    """Tests for is_static_cache_supported() function."""

    def test_returns_false_when_disabled_via_env(self):
        """Test that static cache is disabled when env var is set."""
        with patch.dict("os.environ", {"STATIC_CACHE_DISABLE": "1"}):
            import importlib

            import static_kv_cache

            importlib.reload(static_kv_cache)
            assert static_kv_cache.is_static_cache_supported() is False

    def test_returns_true_when_static_cache_available(self):
        """Test that static cache is enabled when StaticCache is available."""
        with (
            patch.dict("os.environ", {"STATIC_CACHE_DISABLE": "0"}),
            patch.dict("sys.modules", {"transformers": MagicMock()}),
            patch("static_kv_cache.is_static_cache_supported") as mock_supported,
        ):
            mock_supported.return_value = True
            assert mock_supported() is True


class TestCacheType:
    """Tests for CacheType enum."""

    def test_cache_types(self):
        """Test that all cache types are defined."""
        assert CacheType.STATIC.value == "static"
        assert CacheType.DYNAMIC.value == "dynamic"
        assert CacheType.SLIDING_WINDOW.value == "sliding_window"
        assert CacheType.QUANTIZED.value == "quantized"


class TestEstimateCacheSizeBytes:
    """Tests for estimate_cache_size_bytes() function."""

    def test_basic_calculation(self):
        """Test basic cache size calculation."""
        # 32 layers, 8 kv heads, 128 head dim, batch 1, seq 2048
        size = estimate_cache_size_bytes(
            num_layers=32,
            num_kv_heads=8,
            head_dim=128,
            max_batch_size=1,
            max_cache_len=2048,
            dtype=torch.float16,
        )

        # Expected: 32 * 2 * 1 * 8 * 2048 * 128 * 2 bytes
        expected = 32 * 2 * 1 * 8 * 2048 * 128 * 2
        assert size == expected

    def test_larger_batch_size(self):
        """Test that batch size scales linearly."""
        size_1 = estimate_cache_size_bytes(
            num_layers=32,
            num_kv_heads=8,
            head_dim=128,
            max_batch_size=1,
            max_cache_len=2048,
            dtype=torch.float16,
        )
        size_4 = estimate_cache_size_bytes(
            num_layers=32,
            num_kv_heads=8,
            head_dim=128,
            max_batch_size=4,
            max_cache_len=2048,
            dtype=torch.float16,
        )

        assert size_4 == size_1 * 4

    def test_float32_vs_float16(self):
        """Test that float32 is double the size of float16."""
        size_fp16 = estimate_cache_size_bytes(
            num_layers=32,
            num_kv_heads=8,
            head_dim=128,
            max_batch_size=1,
            max_cache_len=2048,
            dtype=torch.float16,
        )
        size_fp32 = estimate_cache_size_bytes(
            num_layers=32,
            num_kv_heads=8,
            head_dim=128,
            max_batch_size=1,
            max_cache_len=2048,
            dtype=torch.float32,
        )

        assert size_fp32 == size_fp16 * 2


class TestEstimateCacheSizeMB:
    """Tests for estimate_cache_size_mb() function."""

    def test_mb_conversion(self):
        """Test conversion from bytes to megabytes."""
        size_mb = estimate_cache_size_mb(
            num_layers=32,
            num_kv_heads=8,
            head_dim=128,
            max_batch_size=1,
            max_cache_len=2048,
            dtype=torch.float16,
        )

        size_bytes = estimate_cache_size_bytes(
            num_layers=32,
            num_kv_heads=8,
            head_dim=128,
            max_batch_size=1,
            max_cache_len=2048,
            dtype=torch.float16,
        )

        assert size_mb == size_bytes / (1024 * 1024)


class TestStaticCacheConfig:
    """Tests for StaticCacheConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = StaticCacheConfig()
        assert config.max_batch_size == 1
        assert config.max_cache_len == 2048
        assert config.dtype == torch.float16
        assert config.device == "cuda:0"
        assert config.cache_type == CacheType.STATIC

    def test_custom_values(self):
        """Test custom configuration values."""
        config = StaticCacheConfig(
            max_batch_size=4,
            max_cache_len=4096,
            dtype=torch.bfloat16,
            device="cuda:1",
        )
        assert config.max_batch_size == 4
        assert config.max_cache_len == 4096
        assert config.dtype == torch.bfloat16
        assert config.device == "cuda:1"


class TestGetModelCacheConfig:
    """Tests for get_model_cache_config() function."""

    def test_extracts_config(self):
        """Test extracting cache config from model."""
        mock_model = MagicMock()
        mock_model.config.num_hidden_layers = 32
        mock_model.config.num_attention_heads = 32
        mock_model.config.num_key_value_heads = 8
        mock_model.config.hidden_size = 4096

        config = get_model_cache_config(mock_model)

        assert config["num_hidden_layers"] == 32
        assert config["num_attention_heads"] == 32
        assert config["num_key_value_heads"] == 8
        assert config["head_dim"] == 128  # 4096 / 32

    def test_handles_missing_kv_heads(self):
        """Test handling model without num_key_value_heads."""
        mock_model = MagicMock()
        mock_model.config.num_hidden_layers = 32
        mock_model.config.num_attention_heads = 32
        mock_model.config.hidden_size = 4096
        # Remove num_key_value_heads
        del mock_model.config.num_key_value_heads

        config = get_model_cache_config(mock_model)

        # Should fall back to num_attention_heads
        assert config["num_key_value_heads"] == 32


class TestStaticCacheManager:
    """Tests for StaticCacheManager class."""

    @pytest.fixture
    def cache_manager(self):
        """Create a cache manager for testing."""
        config = StaticCacheConfig(
            max_batch_size=1,
            max_cache_len=1024,
            dtype=torch.float16,
        )
        return StaticCacheManager(config=config)

    def test_initialization(self, cache_manager):
        """Test manager initialization."""
        assert cache_manager.config.max_batch_size == 1
        assert cache_manager.config.max_cache_len == 1024
        assert cache_manager.cache is None

    def test_reset_cache_when_none(self, cache_manager):
        """Test resetting cache when no cache exists."""
        # Should not raise
        cache_manager.reset_cache()
        assert cache_manager.cache is None

    def test_get_cache_returns_none_initially(self, cache_manager):
        """Test that get_cache returns None before creation."""
        assert cache_manager.get_cache() is None

    def test_estimate_memory_usage_without_model(self, cache_manager):
        """Test memory estimation without model config."""
        result = cache_manager.estimate_memory_usage()

        assert "estimated_mb" in result
        assert result["estimated_mb"] == 0
        assert "error" in result


class TestEstimateOptimalCacheLength:
    """Tests for estimate_optimal_cache_length() function."""

    def test_basic_estimation(self):
        """Test basic cache length estimation."""
        mock_model = MagicMock()
        mock_model.config.num_hidden_layers = 32
        mock_model.config.num_attention_heads = 32
        mock_model.config.num_key_value_heads = 8
        mock_model.config.hidden_size = 4096

        length = estimate_optimal_cache_length(
            available_memory_mb=1024,
            model=mock_model,
            batch_size=1,
            dtype=torch.float16,
        )

        # Should return a positive integer
        assert length > 0
        assert isinstance(length, int)

    def test_minimum_length_enforced(self):
        """Test that minimum cache length is enforced."""
        mock_model = MagicMock()
        mock_model.config.num_hidden_layers = 32
        mock_model.config.num_attention_heads = 32
        mock_model.config.num_key_value_heads = 8
        mock_model.config.hidden_size = 4096

        # Very small memory should still return minimum
        length = estimate_optimal_cache_length(
            available_memory_mb=0.001,
            model=mock_model,
            batch_size=1,
            dtype=torch.float16,
        )

        assert length >= 128  # Minimum enforced


class TestStaticCacheWrapper:
    """Tests for StaticCacheWrapper class."""

    @pytest.fixture
    def mock_model(self):
        """Create a mock model for testing."""
        model = MagicMock()
        model.config.num_hidden_layers = 32
        model.config.num_attention_heads = 32
        model.config.num_key_value_heads = 8
        model.config.hidden_size = 4096
        model.parameters.return_value = iter([torch.randn(10, dtype=torch.float16)])
        model.generate.return_value = torch.tensor([[1, 2, 3, 4, 5]])
        return model

    def test_wrapper_initialization(self, mock_model):
        """Test wrapper initialization."""
        with patch("static_kv_cache.is_static_cache_supported", return_value=False):
            wrapper = StaticCacheWrapper(
                model=mock_model,
                max_batch_size=1,
                max_cache_len=2048,
            )

            assert wrapper.model is mock_model
            # Static cache may not be available
            assert isinstance(wrapper._static_cache_available, bool)

    def test_generate_fallback_to_dynamic(self, mock_model):
        """Test generation with fallback to dynamic cache."""
        with patch("static_kv_cache.is_static_cache_supported", return_value=False):
            wrapper = StaticCacheWrapper(
                model=mock_model,
                fallback_to_dynamic=True,
            )

            input_ids = torch.tensor([[1, 2, 3]])
            output = wrapper.generate(input_ids, max_new_tokens=10)

            mock_model.generate.assert_called()
            assert output is not None

    def test_cache_info(self, mock_model):
        """Test getting cache info."""
        with patch("static_kv_cache.is_static_cache_supported", return_value=False):
            wrapper = StaticCacheWrapper(
                model=mock_model,
                max_batch_size=1,
                max_cache_len=2048,
            )

            info = wrapper.cache_info

            assert "static_cache_available" in info
            assert "cache_type" in info


class TestCreateStaticCache:
    """Tests for create_static_cache() function."""

    def test_raises_when_not_supported(self):
        """Test that it raises ImportError when StaticCache not available."""
        mock_model = MagicMock()

        with (
            patch("static_kv_cache.is_static_cache_supported", return_value=False),
            pytest.raises(ImportError, match="StaticCache not available"),
        ):
            create_static_cache(mock_model)


class TestGetCacheForGeneration:
    """Tests for get_cache_for_generation() function."""

    @pytest.fixture
    def mock_model(self):
        """Create a mock model for testing."""
        model = MagicMock()
        model.config.num_hidden_layers = 32
        model.config.num_attention_heads = 32
        model.config.num_key_value_heads = 8
        model.config.hidden_size = 4096
        model.parameters.return_value = iter([torch.randn(10, dtype=torch.float16)])
        return model

    def test_returns_dynamic_when_static_not_supported(self, mock_model):
        """Test returning dynamic cache when static not supported."""
        with patch("static_kv_cache.is_static_cache_supported", return_value=False):
            cache, kwargs = get_cache_for_generation(
                mock_model,
                max_new_tokens=100,
                input_length=50,
                use_static=True,
            )

            assert cache is None
            assert kwargs["use_cache"] is True

    def test_returns_static_when_supported(self, mock_model):
        """Test returning static cache when supported."""
        with (
            patch("static_kv_cache.is_static_cache_supported", return_value=True),
            patch("static_kv_cache.create_static_cache") as mock_create,
        ):
            mock_cache = MagicMock()
            mock_create.return_value = mock_cache

            cache, kwargs = get_cache_for_generation(
                mock_model,
                max_new_tokens=100,
                input_length=50,
                use_static=True,
            )

            assert cache is mock_cache
            assert kwargs["past_key_values"] is mock_cache

    def test_cache_length_calculation(self, mock_model):
        """Test that cache length is calculated correctly."""
        with (
            patch("static_kv_cache.is_static_cache_supported", return_value=True),
            patch("static_kv_cache.create_static_cache") as mock_create,
        ):
            mock_create.return_value = MagicMock()

            get_cache_for_generation(
                mock_model,
                max_new_tokens=100,
                input_length=50,
                use_static=True,
            )

            # Check the max_cache_len argument
            call_args = mock_create.call_args
            # Should be input_length + max_new_tokens * 1.1 = 165
            expected_len = int((50 + 100) * 1.1)
            assert call_args.kwargs["max_cache_len"] == expected_len


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
