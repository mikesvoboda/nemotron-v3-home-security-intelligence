"""FlashAttention-2 Configuration for LLM Models.

This module provides utilities for configuring FlashAttention-2 for
HuggingFace Transformers models, providing 2-4x speedup for attention layers.

Supports:
- FlashAttention-2 detection and availability checking
- GPU compatibility verification (Ampere or newer, SM >= 80)
- Graceful fallback to standard attention when unavailable
- Environment variable configuration

Environment Variables:
- NEMOTRON_USE_FLASH_ATTENTION: Enable/disable FlashAttention-2 ("true", "false")

Requirements:
- flash-attn>=2.5.0 (optional dependency, needs CUDA to compile)
- Compatible GPU: NVIDIA Ampere (A100, A10, RTX 30xx) or newer
- torch>=2.0.0 with CUDA support

Usage:
    from flash_attention_config import (
        is_flash_attention_available,
        get_attention_implementation,
        FlashAttentionSettings,
    )

    # Check availability
    if is_flash_attention_available():
        print("FlashAttention-2 is available!")

    # Get attention implementation for model loading
    attn_impl = get_attention_implementation()
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        attn_implementation=attn_impl,
        ...
    )

References:
- NEM-3811: FlashAttention-2 integration
- https://github.com/Dao-AILab/flash-attention
- https://huggingface.co/docs/transformers/perf_infer_gpu_one#flashattention-2
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Literal

import torch

logger = logging.getLogger(__name__)

# Minimum compute capability for FlashAttention-2 (Ampere and newer)
MIN_FLASH_ATTENTION_COMPUTE_CAPABILITY = (8, 0)

# Environment variable to control FlashAttention-2 usage
FLASH_ATTENTION_ENV_VAR = "NEMOTRON_USE_FLASH_ATTENTION"


def _check_flash_attn_installed() -> bool:
    """Check if flash-attn package is installed.

    Returns:
        True if flash-attn can be imported, False otherwise.
    """
    try:
        import flash_attn

        return True
    except ImportError:
        return False


def _check_gpu_compatibility() -> tuple[bool, str]:
    """Check if the GPU supports FlashAttention-2.

    FlashAttention-2 requires NVIDIA Ampere (SM 8.0) or newer GPUs.
    Compatible GPUs include:
    - A100, A10, A30, A40 (data center)
    - RTX 3090, 3080, 3070, 3060 (consumer Ampere)
    - RTX 4090, 4080, 4070, 4060 (consumer Ada Lovelace)
    - H100, H200 (data center Hopper)

    Returns:
        Tuple of (is_compatible, reason_message).
    """
    if not torch.cuda.is_available():
        return False, "CUDA is not available"

    try:
        device_props = torch.cuda.get_device_properties(0)
        compute_cap = (device_props.major, device_props.minor)

        if compute_cap < MIN_FLASH_ATTENTION_COMPUTE_CAPABILITY:
            return False, (
                f"GPU compute capability {compute_cap[0]}.{compute_cap[1]} "
                f"is below minimum {MIN_FLASH_ATTENTION_COMPUTE_CAPABILITY[0]}."
                f"{MIN_FLASH_ATTENTION_COMPUTE_CAPABILITY[1]} "
                f"(Ampere or newer required). GPU: {device_props.name}"
            )

        return True, (
            f"GPU {device_props.name} with compute capability "
            f"{compute_cap[0]}.{compute_cap[1]} supports FlashAttention-2"
        )

    except Exception as e:
        return False, f"Failed to check GPU compatibility: {e}"


def _check_pytorch_version() -> tuple[bool, str]:
    """Check if PyTorch version supports FlashAttention-2.

    FlashAttention-2 integration in HuggingFace Transformers requires
    PyTorch 2.0 or newer.

    Returns:
        Tuple of (is_compatible, reason_message).
    """
    try:
        version_parts = torch.__version__.split(".")[:2]
        major = int(version_parts[0])

        if major < 2:
            return False, (
                f"PyTorch version {torch.__version__} is below minimum 2.0 "
                "required for FlashAttention-2"
            )

        return True, f"PyTorch {torch.__version__} supports FlashAttention-2"

    except Exception as e:
        return False, f"Failed to check PyTorch version: {e}"


def is_flash_attention_available() -> bool:
    """Check if FlashAttention-2 is available and can be used.

    This function performs comprehensive checks:
    1. flash-attn package is installed
    2. CUDA is available
    3. GPU is Ampere (SM 8.0) or newer
    4. PyTorch 2.0+ is installed

    Returns:
        True if FlashAttention-2 can be used, False otherwise.

    Example:
        >>> if is_flash_attention_available():
        ...     print("FlashAttention-2 available!")
        ...     attn_impl = "flash_attention_2"
        ... else:
        ...     print("Using standard attention")
        ...     attn_impl = "sdpa"
    """
    # Check flash-attn installation
    if not _check_flash_attn_installed():
        logger.debug("FlashAttention-2 unavailable: flash-attn package not installed")
        return False

    # Check PyTorch version
    pytorch_ok, pytorch_msg = _check_pytorch_version()
    if not pytorch_ok:
        logger.debug(f"FlashAttention-2 unavailable: {pytorch_msg}")
        return False

    # Check GPU compatibility
    gpu_ok, gpu_msg = _check_gpu_compatibility()
    if not gpu_ok:
        logger.debug(f"FlashAttention-2 unavailable: {gpu_msg}")
        return False

    logger.debug(f"FlashAttention-2 available: {gpu_msg}")
    return True


def get_flash_attention_version() -> str | None:
    """Get the installed flash-attn version.

    Returns:
        Version string if flash-attn is installed, None otherwise.
    """
    try:
        import flash_attn

        return getattr(flash_attn, "__version__", "unknown")
    except ImportError:
        return None


@dataclass
class FlashAttentionSettings:
    """Settings for FlashAttention-2 configuration.

    Attributes:
        enabled: Whether FlashAttention-2 is enabled (may be overridden by availability).
        sliding_window: Optional sliding window size for long context optimization.
    """

    enabled: bool = True
    sliding_window: int | None = None

    @classmethod
    def from_environment(cls) -> FlashAttentionSettings:
        """Create settings from environment variables.

        Environment Variables:
            NEMOTRON_USE_FLASH_ATTENTION: "true" or "false" (default: "true")

        Returns:
            FlashAttentionSettings configured from environment.
        """
        # Parse enabled flag (default to True for auto-detection)
        enabled_str = os.environ.get(FLASH_ATTENTION_ENV_VAR, "true").lower()
        enabled = enabled_str in ("true", "1", "yes")

        return cls(enabled=enabled)


AttentionImplementation = Literal["flash_attention_2", "sdpa", "eager"]


def get_attention_implementation(
    settings: FlashAttentionSettings | None = None,
    force_eager: bool = False,
) -> AttentionImplementation:
    """Get the attention implementation to use for model loading.

    This function determines the best available attention implementation:
    1. FlashAttention-2 (if available and enabled) - fastest
    2. SDPA (Scaled Dot Product Attention) - good fallback for PyTorch 2.0+
    3. Eager attention - standard implementation

    Args:
        settings: Optional FlashAttentionSettings. If None, loads from environment.
        force_eager: If True, always returns "eager" regardless of availability.

    Returns:
        Attention implementation string for use with attn_implementation parameter.

    Example:
        >>> attn_impl = get_attention_implementation()
        >>> model = AutoModelForCausalLM.from_pretrained(
        ...     model_name,
        ...     attn_implementation=attn_impl,
        ...     ...
        ... )
    """
    if force_eager:
        logger.info("Using eager attention (forced)")
        return "eager"

    # Get settings from environment if not provided
    if settings is None:
        settings = FlashAttentionSettings.from_environment()

    # Check if FlashAttention is enabled in settings
    if not settings.enabled:
        logger.info("FlashAttention-2 disabled via configuration, falling back to SDPA")
        return "sdpa"

    # Check if FlashAttention-2 is actually available
    if is_flash_attention_available():
        version = get_flash_attention_version()
        logger.info(f"Using FlashAttention-2 (version {version})")
        return "flash_attention_2"

    # Fall back to SDPA (available in PyTorch 2.0+)
    pytorch_ok, _ = _check_pytorch_version()
    if pytorch_ok:
        logger.info(
            "FlashAttention-2 not available, falling back to SDPA (Scaled Dot Product Attention)"
        )
        return "sdpa"

    # Last resort: eager attention
    logger.info("Using eager attention (no optimized attention available)")
    return "eager"


def log_attention_info() -> None:
    """Log information about attention implementation availability.

    Useful for debugging and startup diagnostics.
    """
    logger.info("=== Attention Implementation Status ===")

    # Check flash-attn installation
    if _check_flash_attn_installed():
        version = get_flash_attention_version()
        logger.info(f"  flash-attn: installed (version {version})")
    else:
        logger.info("  flash-attn: not installed")
        logger.info("    Install with: pip install flash-attn --no-build-isolation")

    # Check PyTorch version
    pytorch_ok, pytorch_msg = _check_pytorch_version()
    logger.info(f"  PyTorch: {pytorch_msg}")

    # Check GPU compatibility
    gpu_ok, gpu_msg = _check_gpu_compatibility()
    logger.info(f"  GPU: {gpu_msg}")

    # Overall status
    if is_flash_attention_available():
        logger.info("  Status: FlashAttention-2 AVAILABLE (2-4x attention speedup)")
    else:
        logger.info("  Status: FlashAttention-2 NOT AVAILABLE (using fallback)")

    # Check environment setting
    settings = FlashAttentionSettings.from_environment()
    env_status = "enabled" if settings.enabled else "disabled"
    logger.info(f"  {FLASH_ATTENTION_ENV_VAR}: {env_status}")

    logger.info("========================================")
