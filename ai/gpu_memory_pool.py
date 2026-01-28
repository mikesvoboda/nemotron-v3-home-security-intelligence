"""GPU Memory Pool for Tensor Allocation (NEM-3772).

This module provides GPU memory pooling utilities to reduce allocation/deallocation
overhead during inference. Memory pools pre-allocate tensors and reuse them across
inference calls, avoiding the overhead of cudaMalloc/cudaFree.

Key features:
- Pre-allocated tensor pools for common shapes
- Automatic pool management with LRU eviction
- Thread-safe allocation with async support
- Shape-specific pools for optimized reuse
- Integration with PyTorch's CUDA caching allocator

Performance benefits:
- Reduced allocation latency (avoid cudaMalloc overhead)
- Improved memory locality
- Reduced memory fragmentation
- More predictable inference times

Usage:
    from ai.gpu_memory_pool import (
        GPUMemoryPool,
        TensorPool,
        get_global_pool,
        allocate_from_pool,
    )

    # Using global pool
    pool = get_global_pool()
    tensor = pool.acquire((batch_size, channels, height, width), dtype=torch.float16)
    # ... use tensor ...
    pool.release(tensor)

    # Using context manager
    with pool.acquire_context((1, 3, 640, 480)) as tensor:
        # Use tensor
        pass  # Automatically released

References:
    - NEM-3772: Implement GPU Memory Pool for Tensor Allocation
    - https://pytorch.org/docs/stable/notes/cuda.html#memory-management
"""

from __future__ import annotations

import logging
import os
import threading
import time
from collections import OrderedDict
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

import torch

logger = logging.getLogger(__name__)

# Environment variable to disable memory pooling (useful for debugging)
MEMORY_POOL_DISABLE = os.environ.get("MEMORY_POOL_DISABLE", "0").lower() in (
    "1",
    "true",
    "yes",
)

# Default pool configuration
DEFAULT_POOL_SIZE_MB = 512  # Maximum pool size in MB
DEFAULT_MAX_TENSORS_PER_SHAPE = 4  # Max tensors cached per shape
DEFAULT_TENSOR_TTL_SECONDS = 300  # Tensor eviction after 5 minutes of non-use


def is_memory_pool_supported() -> bool:
    """Check if GPU memory pooling is supported.

    Returns:
        True if memory pooling can be used.
    """
    if MEMORY_POOL_DISABLE:
        logger.debug("Memory pool disabled via MEMORY_POOL_DISABLE environment variable")
        return False

    if not torch.cuda.is_available():
        logger.debug("Memory pool disabled: CUDA not available")
        return False

    return True


def get_tensor_size_bytes(shape: tuple[int, ...], dtype: torch.dtype) -> int:
    """Calculate the size of a tensor in bytes.

    Args:
        shape: Tensor shape.
        dtype: Tensor data type.

    Returns:
        Size in bytes.
    """
    numel = 1
    for dim in shape:
        numel *= dim

    # Get element size based on dtype
    element_size = torch.tensor([], dtype=dtype).element_size()
    return numel * element_size


def get_shape_key(
    shape: tuple[int, ...],
    dtype: torch.dtype,
    device: str | torch.device,
) -> str:
    """Generate a unique key for a tensor configuration.

    Args:
        shape: Tensor shape.
        dtype: Tensor data type.
        device: Target device.

    Returns:
        Unique string key.
    """
    return f"{shape}_{dtype}_{device}"


@dataclass
class PooledTensor:
    """A tensor managed by the memory pool.

    Attributes:
        tensor: The underlying PyTorch tensor.
        shape: Original allocated shape.
        dtype: Tensor data type.
        device: Tensor device.
        allocated_at: Timestamp of allocation.
        last_used_at: Timestamp of last use.
        in_use: Whether the tensor is currently in use.
    """

    tensor: torch.Tensor
    shape: tuple[int, ...]
    dtype: torch.dtype
    device: str
    allocated_at: float = field(default_factory=time.time)
    last_used_at: float = field(default_factory=time.time)
    in_use: bool = False

    @property
    def size_bytes(self) -> int:
        """Get tensor size in bytes."""
        return get_tensor_size_bytes(self.shape, self.dtype)

    def mark_used(self) -> None:
        """Mark the tensor as currently in use."""
        self.in_use = True
        self.last_used_at = time.time()

    def mark_released(self) -> None:
        """Mark the tensor as available."""
        self.in_use = False
        self.last_used_at = time.time()


@dataclass
class PoolConfig:
    """Configuration for the GPU memory pool.

    Attributes:
        max_pool_size_mb: Maximum total pool size in megabytes.
        max_tensors_per_shape: Maximum tensors to cache per shape.
        tensor_ttl_seconds: Time-to-live for unused tensors.
        enable_defragmentation: Whether to enable memory defragmentation.
        preallocate_common_shapes: Shapes to preallocate at startup.
    """

    max_pool_size_mb: float = DEFAULT_POOL_SIZE_MB
    max_tensors_per_shape: int = DEFAULT_MAX_TENSORS_PER_SHAPE
    tensor_ttl_seconds: float = DEFAULT_TENSOR_TTL_SECONDS
    enable_defragmentation: bool = True
    preallocate_common_shapes: list[tuple[tuple[int, ...], torch.dtype]] = field(
        default_factory=list
    )


class TensorPool:
    """Pool of pre-allocated tensors for a specific shape and dtype.

    This class manages a collection of tensors with the same shape and dtype,
    allowing them to be reused across inference calls.

    Attributes:
        shape: Tensor shape for this pool.
        dtype: Tensor data type.
        device: Target device.
        max_tensors: Maximum number of tensors in the pool.
        tensors: List of pooled tensors.
    """

    def __init__(
        self,
        shape: tuple[int, ...],
        dtype: torch.dtype,
        device: str = "cuda:0",
        max_tensors: int = DEFAULT_MAX_TENSORS_PER_SHAPE,
    ) -> None:
        """Initialize the tensor pool.

        Args:
            shape: Tensor shape.
            dtype: Tensor data type.
            device: Target device.
            max_tensors: Maximum tensors to maintain.
        """
        self.shape = shape
        self.dtype = dtype
        self.device = device
        self.max_tensors = max_tensors
        self.tensors: list[PooledTensor] = []
        self._lock = threading.Lock()

        logger.debug(f"Created TensorPool for shape={shape}, dtype={dtype}, device={device}")

    @property
    def tensor_size_bytes(self) -> int:
        """Get size of each tensor in bytes."""
        return get_tensor_size_bytes(self.shape, self.dtype)

    @property
    def total_size_bytes(self) -> int:
        """Get total size of all tensors in pool."""
        return len(self.tensors) * self.tensor_size_bytes

    @property
    def available_count(self) -> int:
        """Get number of available (not in use) tensors."""
        with self._lock:
            return sum(1 for t in self.tensors if not t.in_use)

    @property
    def in_use_count(self) -> int:
        """Get number of tensors currently in use."""
        with self._lock:
            return sum(1 for t in self.tensors if t.in_use)

    def _allocate_new(self) -> PooledTensor:
        """Allocate a new tensor.

        Returns:
            Newly allocated PooledTensor.
        """
        tensor = torch.empty(
            self.shape,
            dtype=self.dtype,
            device=self.device,
        )
        return PooledTensor(
            tensor=tensor,
            shape=self.shape,
            dtype=self.dtype,
            device=self.device,
        )

    def acquire(self) -> torch.Tensor:
        """Acquire a tensor from the pool.

        If no free tensor is available, a new one is allocated
        (up to the maximum pool size).

        Returns:
            A tensor from the pool.

        Raises:
            RuntimeError: If pool is full and all tensors are in use.
        """
        with self._lock:
            # Try to find a free tensor
            for pooled in self.tensors:
                if not pooled.in_use:
                    pooled.mark_used()
                    return pooled.tensor

            # No free tensor, allocate new one if under limit
            if len(self.tensors) < self.max_tensors:
                pooled = self._allocate_new()
                pooled.mark_used()
                self.tensors.append(pooled)
                logger.debug(f"Allocated new tensor in pool (total: {len(self.tensors)})")
                return pooled.tensor

            # Pool is full, all tensors in use
            raise RuntimeError(
                f"TensorPool exhausted: all {self.max_tensors} tensors are in use. "
                f"Consider increasing max_tensors or releasing unused tensors."
            )

    def release(self, tensor: torch.Tensor) -> bool:
        """Release a tensor back to the pool.

        Args:
            tensor: The tensor to release.

        Returns:
            True if the tensor was found and released, False otherwise.
        """
        with self._lock:
            for pooled in self.tensors:
                if pooled.tensor.data_ptr() == tensor.data_ptr():
                    pooled.mark_released()
                    return True
            return False

    def clear(self) -> None:
        """Clear all tensors from the pool."""
        with self._lock:
            # Only clear tensors not in use
            self.tensors = [t for t in self.tensors if t.in_use]
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

    def evict_stale(self, ttl_seconds: float) -> int:
        """Evict tensors that haven't been used recently.

        Args:
            ttl_seconds: Time-to-live threshold.

        Returns:
            Number of tensors evicted.
        """
        with self._lock:
            now = time.time()
            evicted = 0
            remaining = []

            for pooled in self.tensors:
                # Keep if in use or recently used
                if pooled.in_use or (now - pooled.last_used_at) < ttl_seconds:
                    remaining.append(pooled)
                else:
                    evicted += 1

            self.tensors = remaining
            return evicted

    def preallocate(self, count: int = 1) -> int:
        """Pre-allocate tensors in the pool.

        Args:
            count: Number of tensors to pre-allocate.

        Returns:
            Number of tensors actually allocated.
        """
        with self._lock:
            allocated = 0
            while len(self.tensors) < min(self.max_tensors, len(self.tensors) + count):
                pooled = self._allocate_new()
                self.tensors.append(pooled)
                allocated += 1
            return allocated


class GPUMemoryPool:
    """Main GPU memory pool manager.

    This class manages multiple TensorPools, one for each unique
    (shape, dtype, device) combination. It provides a unified interface
    for acquiring and releasing tensors with automatic pool management.

    Usage:
        pool = GPUMemoryPool(config=PoolConfig(max_pool_size_mb=1024))
        tensor = pool.acquire((1, 3, 640, 480), dtype=torch.float16)
        # ... use tensor ...
        pool.release(tensor)

    Attributes:
        config: Pool configuration.
        pools: Dictionary of TensorPools by shape key.
        enabled: Whether pooling is enabled.
    """

    def __init__(
        self,
        config: PoolConfig | None = None,
        device: str = "cuda:0",
    ) -> None:
        """Initialize the memory pool manager.

        Args:
            config: Pool configuration.
            device: Default device.
        """
        self.config = config or PoolConfig()
        self.device = device
        self.pools: OrderedDict[str, TensorPool] = OrderedDict()
        self.enabled = is_memory_pool_supported()
        self._lock = threading.Lock()
        self._tensor_to_key: dict[int, str] = {}  # data_ptr -> key mapping

        if self.enabled:
            logger.info(f"GPU memory pool initialized (max_size={self.config.max_pool_size_mb}MB)")
            # Preallocate common shapes
            for shape, dtype in self.config.preallocate_common_shapes:
                self._get_or_create_pool(shape, dtype, device).preallocate(1)
        else:
            logger.info("GPU memory pool disabled")

    def _get_or_create_pool(
        self,
        shape: tuple[int, ...],
        dtype: torch.dtype,
        device: str,
    ) -> TensorPool:
        """Get or create a TensorPool for the given configuration.

        Args:
            shape: Tensor shape.
            dtype: Tensor data type.
            device: Target device.

        Returns:
            TensorPool for the configuration.
        """
        key = get_shape_key(shape, dtype, device)

        with self._lock:
            if key not in self.pools:
                # Check if we need to evict old pools
                self._evict_if_needed(shape, dtype)

                self.pools[key] = TensorPool(
                    shape=shape,
                    dtype=dtype,
                    device=device,
                    max_tensors=self.config.max_tensors_per_shape,
                )
                # Move to end (most recently used)
                self.pools.move_to_end(key)

            return self.pools[key]

    def _evict_if_needed(
        self,
        new_shape: tuple[int, ...],
        new_dtype: torch.dtype,
    ) -> None:
        """Evict old pools if adding a new one would exceed budget.

        Args:
            new_shape: Shape of new tensor.
            new_dtype: Dtype of new tensor.
        """
        new_size = get_tensor_size_bytes(new_shape, new_dtype)
        max_bytes = int(self.config.max_pool_size_mb * 1024 * 1024)

        # Calculate current total size
        current_size = sum(pool.total_size_bytes for pool in self.pools.values())

        # Evict oldest pools (LRU) until we have room
        while current_size + new_size > max_bytes and self.pools:
            # Get oldest pool (first in OrderedDict)
            oldest_key = next(iter(self.pools))
            oldest_pool = self.pools[oldest_key]

            # Skip if has tensors in use
            if oldest_pool.in_use_count > 0:
                # Move to end and try next
                self.pools.move_to_end(oldest_key)
                continue

            # Remove the pool
            current_size -= oldest_pool.total_size_bytes
            del self.pools[oldest_key]
            logger.debug(f"Evicted pool for shape key: {oldest_key}")

    def _total_size_bytes_unlocked(self) -> int:
        """Get total size of all pools in bytes (assumes lock is held)."""
        return sum(pool.total_size_bytes for pool in self.pools.values())

    @property
    def total_size_bytes(self) -> int:
        """Get total size of all pools in bytes."""
        with self._lock:
            return self._total_size_bytes_unlocked()

    @property
    def total_size_mb(self) -> float:
        """Get total size of all pools in megabytes."""
        with self._lock:
            return self._total_size_bytes_unlocked() / (1024 * 1024)

    def acquire(
        self,
        shape: tuple[int, ...],
        dtype: torch.dtype = torch.float16,
        device: str | None = None,
        fill_value: float | None = None,
    ) -> torch.Tensor:
        """Acquire a tensor from the pool.

        If pooling is disabled, creates a new tensor directly.

        Args:
            shape: Desired tensor shape.
            dtype: Tensor data type.
            device: Target device (uses default if None).
            fill_value: Optional value to fill the tensor with.

        Returns:
            A tensor of the requested shape and type.
        """
        device = device or self.device

        if not self.enabled:
            tensor = torch.empty(shape, dtype=dtype, device=device)
            if fill_value is not None:
                tensor.fill_(fill_value)
            return tensor

        pool = self._get_or_create_pool(shape, dtype, device)
        tensor = pool.acquire()

        # Track tensor for release
        with self._lock:
            self._tensor_to_key[tensor.data_ptr()] = get_shape_key(shape, dtype, device)

        if fill_value is not None:
            tensor.fill_(fill_value)

        return tensor

    def release(self, tensor: torch.Tensor) -> bool:
        """Release a tensor back to the pool.

        Args:
            tensor: The tensor to release.

        Returns:
            True if released successfully, False if tensor not from pool.
        """
        if not self.enabled:
            return False

        data_ptr = tensor.data_ptr()

        with self._lock:
            if data_ptr not in self._tensor_to_key:
                return False

            key = self._tensor_to_key[data_ptr]
            del self._tensor_to_key[data_ptr]

            if key in self.pools:
                return self.pools[key].release(tensor)

        return False

    @contextmanager
    def acquire_context(
        self,
        shape: tuple[int, ...],
        dtype: torch.dtype = torch.float16,
        device: str | None = None,
        fill_value: float | None = None,
    ) -> Iterator[torch.Tensor]:
        """Context manager for acquiring and automatically releasing a tensor.

        Args:
            shape: Desired tensor shape.
            dtype: Tensor data type.
            device: Target device.
            fill_value: Optional fill value.

        Yields:
            Acquired tensor.
        """
        tensor = self.acquire(shape, dtype, device, fill_value)
        try:
            yield tensor
        finally:
            self.release(tensor)

    def clear(self) -> None:
        """Clear all pools."""
        with self._lock:
            for pool in self.pools.values():
                pool.clear()
            self.pools.clear()
            self._tensor_to_key.clear()

            if torch.cuda.is_available():
                torch.cuda.empty_cache()

        logger.info("GPU memory pool cleared")

    def evict_stale(self, ttl_seconds: float | None = None) -> int:
        """Evict stale tensors from all pools.

        Args:
            ttl_seconds: Time-to-live threshold. Uses config if None.

        Returns:
            Total number of tensors evicted.
        """
        ttl = ttl_seconds if ttl_seconds is not None else self.config.tensor_ttl_seconds
        total_evicted = 0

        with self._lock:
            for pool in self.pools.values():
                total_evicted += pool.evict_stale(ttl)

        if total_evicted > 0:
            logger.debug(f"Evicted {total_evicted} stale tensors from pool")

        return total_evicted

    def get_stats(self) -> dict[str, Any]:
        """Get pool statistics.

        Returns:
            Dictionary with pool statistics.
        """
        with self._lock:
            pools_info = []
            for _key, pool in self.pools.items():
                pools_info.append(
                    {
                        "shape": pool.shape,
                        "dtype": str(pool.dtype),
                        "device": pool.device,
                        "total_tensors": len(pool.tensors),
                        "available": pool.available_count,
                        "in_use": pool.in_use_count,
                        "size_mb": pool.total_size_bytes / (1024 * 1024),
                    }
                )

            total_mb = self._total_size_bytes_unlocked() / (1024 * 1024)
            return {
                "enabled": self.enabled,
                "total_pools": len(self.pools),
                "total_size_mb": total_mb,
                "max_size_mb": self.config.max_pool_size_mb,
                "utilization_percent": (
                    total_mb / self.config.max_pool_size_mb * 100
                    if self.config.max_pool_size_mb > 0
                    else 0
                ),
                "pools": pools_info,
            }


# Global pool instance
_global_pool: GPUMemoryPool | None = None
_global_pool_lock = threading.Lock()


def get_global_pool(config: PoolConfig | None = None) -> GPUMemoryPool:
    """Get or create the global GPU memory pool.

    Args:
        config: Optional configuration for initial creation.

    Returns:
        The global GPUMemoryPool instance.
    """
    global _global_pool

    with _global_pool_lock:
        if _global_pool is None:
            _global_pool = GPUMemoryPool(config=config)
        return _global_pool


def allocate_from_pool(
    shape: tuple[int, ...],
    dtype: torch.dtype = torch.float16,
    device: str = "cuda:0",
) -> torch.Tensor:
    """Convenience function to allocate from the global pool.

    Args:
        shape: Tensor shape.
        dtype: Tensor data type.
        device: Target device.

    Returns:
        Allocated tensor.
    """
    return get_global_pool().acquire(shape, dtype, device)


def release_to_pool(tensor: torch.Tensor) -> bool:
    """Convenience function to release to the global pool.

    Args:
        tensor: Tensor to release.

    Returns:
        True if released successfully.
    """
    return get_global_pool().release(tensor)


@contextmanager
def pooled_tensor(
    shape: tuple[int, ...],
    dtype: torch.dtype = torch.float16,
    device: str = "cuda:0",
) -> Iterator[torch.Tensor]:
    """Context manager for using a pooled tensor.

    Args:
        shape: Tensor shape.
        dtype: Tensor data type.
        device: Target device.

    Yields:
        Pooled tensor.
    """
    with get_global_pool().acquire_context(shape, dtype, device) as tensor:
        yield tensor
