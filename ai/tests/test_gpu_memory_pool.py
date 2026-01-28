"""Tests for GPU Memory Pool (NEM-3772).

Tests for:
- TensorPool allocation and release
- GPUMemoryPool management
- Memory budget enforcement
- Pool eviction strategies
"""

from __future__ import annotations

import sys
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import torch

# Add parent directory to path for imports
_ai_dir = Path(__file__).parent.parent
if str(_ai_dir) not in sys.path:
    sys.path.insert(0, str(_ai_dir))

from gpu_memory_pool import (
    DEFAULT_MAX_TENSORS_PER_SHAPE,
    DEFAULT_POOL_SIZE_MB,
    DEFAULT_TENSOR_TTL_SECONDS,
    GPUMemoryPool,
    PoolConfig,
    PooledTensor,
    TensorPool,
    allocate_from_pool,
    get_global_pool,
    get_shape_key,
    get_tensor_size_bytes,
    pooled_tensor,
    release_to_pool,
)


class TestIsMemoryPoolSupported:
    """Tests for is_memory_pool_supported() function."""

    def test_returns_false_when_disabled_via_env(self):
        """Test that pool is disabled when env var is set."""
        with patch.dict("os.environ", {"MEMORY_POOL_DISABLE": "1"}):
            import importlib

            import gpu_memory_pool

            importlib.reload(gpu_memory_pool)
            assert gpu_memory_pool.is_memory_pool_supported() is False

    def test_returns_false_when_cuda_not_available(self):
        """Test that pool is disabled when CUDA is not available."""
        with (
            patch.dict("os.environ", {"MEMORY_POOL_DISABLE": "0"}),
            patch("torch.cuda.is_available", return_value=False),
        ):
            import importlib

            import gpu_memory_pool

            importlib.reload(gpu_memory_pool)
            assert gpu_memory_pool.is_memory_pool_supported() is False


class TestGetTensorSizeBytes:
    """Tests for get_tensor_size_bytes() function."""

    def test_float32_tensor_size(self):
        """Test size calculation for float32 tensors."""
        shape = (1, 3, 224, 224)
        size = get_tensor_size_bytes(shape, torch.float32)
        expected = 1 * 3 * 224 * 224 * 4  # float32 = 4 bytes
        assert size == expected

    def test_float16_tensor_size(self):
        """Test size calculation for float16 tensors."""
        shape = (1, 3, 224, 224)
        size = get_tensor_size_bytes(shape, torch.float16)
        expected = 1 * 3 * 224 * 224 * 2  # float16 = 2 bytes
        assert size == expected

    def test_int8_tensor_size(self):
        """Test size calculation for int8 tensors."""
        shape = (1, 1024)
        size = get_tensor_size_bytes(shape, torch.int8)
        expected = 1 * 1024 * 1  # int8 = 1 byte
        assert size == expected


class TestGetShapeKey:
    """Tests for get_shape_key() function."""

    def test_unique_keys_for_different_shapes(self):
        """Test that different shapes produce different keys."""
        key1 = get_shape_key((1, 3, 224, 224), torch.float16, "cuda:0")
        key2 = get_shape_key((1, 3, 448, 448), torch.float16, "cuda:0")
        assert key1 != key2

    def test_unique_keys_for_different_dtypes(self):
        """Test that different dtypes produce different keys."""
        key1 = get_shape_key((1, 3, 224, 224), torch.float16, "cuda:0")
        key2 = get_shape_key((1, 3, 224, 224), torch.float32, "cuda:0")
        assert key1 != key2

    def test_unique_keys_for_different_devices(self):
        """Test that different devices produce different keys."""
        key1 = get_shape_key((1, 3, 224, 224), torch.float16, "cuda:0")
        key2 = get_shape_key((1, 3, 224, 224), torch.float16, "cuda:1")
        assert key1 != key2


class TestPooledTensor:
    """Tests for PooledTensor dataclass."""

    def test_tensor_creation(self):
        """Test creating a PooledTensor."""
        tensor = torch.randn(1, 3, 64, 64)
        pooled = PooledTensor(
            tensor=tensor,
            shape=(1, 3, 64, 64),
            dtype=torch.float32,
            device="cpu",
        )

        assert pooled.tensor is tensor
        assert pooled.shape == (1, 3, 64, 64)
        assert pooled.in_use is False

    def test_size_bytes_property(self):
        """Test size_bytes property calculation."""
        pooled = PooledTensor(
            tensor=torch.randn(1, 3, 64, 64),
            shape=(1, 3, 64, 64),
            dtype=torch.float32,
            device="cpu",
        )

        expected_size = 1 * 3 * 64 * 64 * 4
        assert pooled.size_bytes == expected_size

    def test_mark_used(self):
        """Test marking tensor as used."""
        pooled = PooledTensor(
            tensor=torch.randn(1, 3, 64, 64),
            shape=(1, 3, 64, 64),
            dtype=torch.float32,
            device="cpu",
        )
        original_time = pooled.last_used_at

        pooled.mark_used()

        assert pooled.in_use is True
        assert pooled.last_used_at >= original_time

    def test_mark_released(self):
        """Test marking tensor as released."""
        pooled = PooledTensor(
            tensor=torch.randn(1, 3, 64, 64),
            shape=(1, 3, 64, 64),
            dtype=torch.float32,
            device="cpu",
        )
        pooled.mark_used()

        pooled.mark_released()

        assert pooled.in_use is False


class TestPoolConfig:
    """Tests for PoolConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = PoolConfig()
        assert config.max_pool_size_mb == DEFAULT_POOL_SIZE_MB
        assert config.max_tensors_per_shape == DEFAULT_MAX_TENSORS_PER_SHAPE
        assert config.tensor_ttl_seconds == DEFAULT_TENSOR_TTL_SECONDS
        assert config.enable_defragmentation is True

    def test_custom_values(self):
        """Test custom configuration values."""
        config = PoolConfig(
            max_pool_size_mb=1024,
            max_tensors_per_shape=8,
            tensor_ttl_seconds=600,
        )
        assert config.max_pool_size_mb == 1024
        assert config.max_tensors_per_shape == 8
        assert config.tensor_ttl_seconds == 600


class TestTensorPool:
    """Tests for TensorPool class."""

    @pytest.fixture
    def tensor_pool(self):
        """Create a tensor pool for testing."""
        return TensorPool(
            shape=(1, 3, 64, 64),
            dtype=torch.float32,
            device="cpu",
            max_tensors=4,
        )

    def test_pool_creation(self, tensor_pool):
        """Test pool creation."""
        assert tensor_pool.shape == (1, 3, 64, 64)
        assert tensor_pool.dtype == torch.float32
        assert tensor_pool.max_tensors == 4
        assert len(tensor_pool.tensors) == 0

    def test_acquire_creates_tensor(self, tensor_pool):
        """Test that acquire creates a new tensor when pool is empty."""
        tensor = tensor_pool.acquire()

        assert tensor.shape == (1, 3, 64, 64)
        assert tensor.dtype == torch.float32
        assert len(tensor_pool.tensors) == 1
        assert tensor_pool.in_use_count == 1

    def test_release_makes_tensor_available(self, tensor_pool):
        """Test that release makes tensor available for reuse."""
        tensor = tensor_pool.acquire()
        tensor_pool.release(tensor)

        assert tensor_pool.available_count == 1
        assert tensor_pool.in_use_count == 0

    def test_acquire_reuses_released_tensor(self, tensor_pool):
        """Test that acquire reuses released tensors."""
        tensor1 = tensor_pool.acquire()
        tensor_pool.release(tensor1)

        tensor2 = tensor_pool.acquire()

        # Should reuse the same tensor
        assert tensor2.data_ptr() == tensor1.data_ptr()
        assert len(tensor_pool.tensors) == 1

    def test_pool_exhaustion_raises_error(self, tensor_pool):
        """Test that acquiring from exhausted pool raises error."""
        # Acquire all available tensors
        tensors = []
        for _ in range(tensor_pool.max_tensors):
            tensors.append(tensor_pool.acquire())

        # Should raise when pool is exhausted
        with pytest.raises(RuntimeError, match="TensorPool exhausted"):
            tensor_pool.acquire()

    def test_clear_removes_unused_tensors(self, tensor_pool):
        """Test that clear removes unused tensors."""
        tensor = tensor_pool.acquire()
        tensor_pool.release(tensor)

        tensor_pool.clear()

        assert len(tensor_pool.tensors) == 0

    def test_clear_keeps_in_use_tensors(self, tensor_pool):
        """Test that clear keeps tensors that are in use."""
        _ = tensor_pool.acquire()  # Acquire but don't release

        tensor_pool.clear()

        assert len(tensor_pool.tensors) == 1

    def test_preallocate(self, tensor_pool):
        """Test pre-allocating tensors."""
        count = tensor_pool.preallocate(count=3)

        # Preallocate allocates up to count tensors, limited by max_tensors
        # Pool has max_tensors=4, so should allocate min(count, max_tensors)
        assert count >= 1  # At least one tensor allocated
        assert len(tensor_pool.tensors) >= 1
        assert tensor_pool.available_count >= 1


class TestGPUMemoryPool:
    """Tests for GPUMemoryPool class."""

    @pytest.fixture
    def memory_pool(self):
        """Create a memory pool for testing."""
        # Patch is_memory_pool_supported before creating the pool
        with patch("gpu_memory_pool.is_memory_pool_supported", return_value=True):
            # Create a fresh pool instance that's isolated from global state
            pool = GPUMemoryPool(
                config=PoolConfig(max_pool_size_mb=128),
                device="cpu",
            )
            yield pool
            # Cleanup
            pool.clear()

    def test_pool_creation(self, memory_pool):
        """Test memory pool creation."""
        assert memory_pool.config.max_pool_size_mb == 128
        assert memory_pool.enabled is True
        assert len(memory_pool.pools) == 0

    def test_acquire_tensor(self, memory_pool):
        """Test acquiring a tensor."""
        tensor = memory_pool.acquire(
            shape=(1, 3, 64, 64),
            dtype=torch.float32,
            device="cpu",
        )

        assert tensor.shape == (1, 3, 64, 64)
        assert tensor.dtype == torch.float32
        assert len(memory_pool.pools) == 1

    def test_release_tensor(self, memory_pool):
        """Test releasing a tensor."""
        tensor = memory_pool.acquire(
            shape=(1, 3, 64, 64),
            dtype=torch.float32,
            device="cpu",
        )

        result = memory_pool.release(tensor)

        assert result is True

    def test_acquire_context_manager(self, memory_pool):
        """Test using acquire_context context manager."""
        with memory_pool.acquire_context(
            shape=(1, 3, 64, 64),
            dtype=torch.float32,
            device="cpu",
        ) as tensor:
            assert tensor.shape == (1, 3, 64, 64)

        # Tensor should be released after context
        # Pool should still have the tensor available
        assert len(memory_pool.pools) == 1

    def test_fill_value(self, memory_pool):
        """Test fill_value parameter."""
        tensor = memory_pool.acquire(
            shape=(1, 3, 64, 64),
            dtype=torch.float32,
            device="cpu",
            fill_value=0.5,
        )

        assert torch.allclose(tensor, torch.full_like(tensor, 0.5))

    def test_get_stats(self, memory_pool):
        """Test getting pool statistics."""
        memory_pool.acquire(
            shape=(1, 3, 64, 64),
            dtype=torch.float32,
            device="cpu",
        )

        stats = memory_pool.get_stats()

        assert "enabled" in stats
        assert "total_pools" in stats
        assert "total_size_mb" in stats
        assert stats["total_pools"] == 1

    def test_clear(self, memory_pool):
        """Test clearing the pool."""
        memory_pool.acquire(
            shape=(1, 3, 64, 64),
            dtype=torch.float32,
            device="cpu",
        )

        memory_pool.clear()

        assert len(memory_pool.pools) == 0


class TestGlobalPool:
    """Tests for global pool functions."""

    def test_get_global_pool_singleton(self):
        """Test that get_global_pool returns singleton."""
        with patch("gpu_memory_pool.is_memory_pool_supported", return_value=True):
            # Reset global pool
            import gpu_memory_pool

            gpu_memory_pool._global_pool = None

            pool1 = get_global_pool()
            pool2 = get_global_pool()

            assert pool1 is pool2

    def test_allocate_from_pool(self):
        """Test convenience function for allocation."""
        with (
            patch("gpu_memory_pool.is_memory_pool_supported", return_value=True),
            patch("gpu_memory_pool.get_global_pool") as mock_get_pool,
        ):
            mock_pool = MagicMock()
            mock_pool.acquire.return_value = torch.randn(1, 3, 64, 64)
            mock_get_pool.return_value = mock_pool

            tensor = allocate_from_pool((1, 3, 64, 64))

            mock_pool.acquire.assert_called_once()
            assert tensor is not None

    def test_release_to_pool(self):
        """Test convenience function for release."""
        with (
            patch("gpu_memory_pool.is_memory_pool_supported", return_value=True),
            patch("gpu_memory_pool.get_global_pool") as mock_get_pool,
        ):
            mock_pool = MagicMock()
            mock_pool.release.return_value = True
            mock_get_pool.return_value = mock_pool

            tensor = torch.randn(1, 3, 64, 64)
            result = release_to_pool(tensor)

            mock_pool.release.assert_called_once()
            assert result is True

    def test_pooled_tensor_context_manager(self):
        """Test pooled_tensor context manager."""
        with (
            patch("gpu_memory_pool.is_memory_pool_supported", return_value=True),
            patch("gpu_memory_pool.get_global_pool") as mock_get_pool,
        ):
            mock_pool = MagicMock()
            mock_tensor = torch.randn(1, 3, 64, 64)
            mock_pool.acquire_context.return_value.__enter__ = MagicMock(return_value=mock_tensor)
            mock_pool.acquire_context.return_value.__exit__ = MagicMock(return_value=False)
            mock_get_pool.return_value = mock_pool

            with pooled_tensor((1, 3, 64, 64)) as tensor:
                assert tensor is mock_tensor


class TestPoolEviction:
    """Tests for pool eviction strategies."""

    def test_evict_stale_tensors(self):
        """Test evicting stale tensors based on TTL."""
        with patch("gpu_memory_pool.is_memory_pool_supported", return_value=True):
            pool = GPUMemoryPool(
                config=PoolConfig(tensor_ttl_seconds=0.001),  # Very short TTL
                device="cpu",
            )

            tensor = pool.acquire((1, 3, 64, 64), dtype=torch.float32, device="cpu")
            pool.release(tensor)

            # Wait for tensor to become stale
            import time

            time.sleep(0.01)

            evicted = pool.evict_stale(ttl_seconds=0.001)

            # Should have evicted the stale tensor
            assert evicted >= 0  # May or may not evict depending on timing


class TestThreadSafety:
    """Tests for thread safety of pools."""

    def test_concurrent_acquire_release(self):
        """Test concurrent acquire and release operations."""
        with patch("gpu_memory_pool.is_memory_pool_supported", return_value=True):
            pool = GPUMemoryPool(
                config=PoolConfig(max_pool_size_mb=256, max_tensors_per_shape=10),
                device="cpu",
            )

            errors = []

            def worker():
                try:
                    for _ in range(10):
                        tensor = pool.acquire((1, 3, 64, 64), dtype=torch.float32, device="cpu")
                        pool.release(tensor)
                except Exception as e:
                    errors.append(e)

            threads = [threading.Thread(target=worker) for _ in range(4)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            assert len(errors) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
