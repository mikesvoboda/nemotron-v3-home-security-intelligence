"""Quantization Configuration for LLM Models.

This module provides utilities for configuring BitsAndBytes quantization
for HuggingFace Transformers models.

Supports:
- 4-bit quantization (NF4, FP4) for maximum memory savings
- 8-bit quantization for balance of memory and quality
- Double quantization for additional memory savings
- Compute dtype selection for optimal performance

Environment Variables:
- NEMOTRON_QUANTIZATION: Quantization mode ("4bit", "8bit", "none")
- NEMOTRON_4BIT_QUANT_TYPE: 4-bit quantization type ("nf4", "fp4")
- NEMOTRON_4BIT_DOUBLE_QUANT: Enable double quantization ("true", "false")
- NEMOTRON_COMPUTE_DTYPE: Compute dtype ("float16", "bfloat16", "float32")

Usage:
    from quantization_config import (
        get_quantization_config,
        QuantizationMode,
    )

    # Get BitsAndBytesConfig for model loading
    bnb_config = get_quantization_config(mode=QuantizationMode.FOUR_BIT)

    # Load model with quantization
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        quantization_config=bnb_config,
        device_map="auto",
    )

References:
- NEM-3810: BitsAndBytes 4-bit quantization
- https://huggingface.co/docs/transformers/main_classes/quantization
- https://github.com/TimDettmers/bitsandbytes
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from enum import Enum

import torch

logger = logging.getLogger(__name__)


class QuantizationMode(Enum):
    """Quantization mode for model loading.

    Attributes:
        NONE: No quantization (full precision or native fp16/bf16)
        FOUR_BIT: 4-bit quantization (NF4/FP4) - maximum memory savings
        EIGHT_BIT: 8-bit quantization - balance of memory and quality
    """

    NONE = "none"
    FOUR_BIT = "4bit"
    EIGHT_BIT = "8bit"


class FourBitQuantType(Enum):
    """4-bit quantization type.

    Attributes:
        NF4: Normal Float 4 - optimized for normally distributed weights
             Best for most LLMs as weights tend to be normally distributed.
        FP4: Float Point 4 - standard 4-bit floating point
             May work better for some models with non-normal weight distributions.
    """

    NF4 = "nf4"
    FP4 = "fp4"


@dataclass
class QuantizationSettings:
    """Settings for model quantization.

    Attributes:
        mode: Quantization mode (none, 4bit, 8bit)
        quant_type: Type of 4-bit quantization (nf4, fp4)
        use_double_quant: Enable double quantization for additional memory savings
        compute_dtype: Data type for computation during inference
        bnb_4bit_use_double_quant: Whether to use nested quantization
    """

    mode: QuantizationMode = QuantizationMode.FOUR_BIT
    quant_type: FourBitQuantType = FourBitQuantType.NF4
    use_double_quant: bool = True
    compute_dtype: torch.dtype = torch.float16

    @classmethod
    def from_environment(cls) -> QuantizationSettings:
        """Create settings from environment variables.

        Environment Variables:
            NEMOTRON_QUANTIZATION: "4bit", "8bit", or "none"
            NEMOTRON_4BIT_QUANT_TYPE: "nf4" or "fp4"
            NEMOTRON_4BIT_DOUBLE_QUANT: "true" or "false"
            NEMOTRON_COMPUTE_DTYPE: "float16", "bfloat16", or "float32"

        Returns:
            QuantizationSettings configured from environment.
        """
        # Parse quantization mode
        mode_str = os.environ.get("NEMOTRON_QUANTIZATION", "4bit").lower()
        try:
            mode = QuantizationMode(mode_str)
        except ValueError:
            logger.warning(f"Invalid NEMOTRON_QUANTIZATION '{mode_str}', using '4bit'")
            mode = QuantizationMode.FOUR_BIT

        # Parse 4-bit quant type
        quant_type_str = os.environ.get("NEMOTRON_4BIT_QUANT_TYPE", "nf4").lower()
        try:
            quant_type = FourBitQuantType(quant_type_str)
        except ValueError:
            logger.warning(f"Invalid NEMOTRON_4BIT_QUANT_TYPE '{quant_type_str}', using 'nf4'")
            quant_type = FourBitQuantType.NF4

        # Parse double quantization flag
        double_quant_str = os.environ.get("NEMOTRON_4BIT_DOUBLE_QUANT", "true").lower()
        use_double_quant = double_quant_str in ("true", "1", "yes")

        # Parse compute dtype
        compute_dtype_str = os.environ.get("NEMOTRON_COMPUTE_DTYPE", "float16").lower()
        dtype_map = {
            "float16": torch.float16,
            "fp16": torch.float16,
            "bfloat16": torch.bfloat16,
            "bf16": torch.bfloat16,
            "float32": torch.float32,
            "fp32": torch.float32,
        }
        compute_dtype = dtype_map.get(compute_dtype_str, torch.float16)
        if compute_dtype_str not in dtype_map:
            logger.warning(f"Invalid NEMOTRON_COMPUTE_DTYPE '{compute_dtype_str}', using 'float16'")

        return cls(
            mode=mode,
            quant_type=quant_type,
            use_double_quant=use_double_quant,
            compute_dtype=compute_dtype,
        )


def _check_bitsandbytes_available() -> bool:
    """Check if bitsandbytes is available.

    Returns:
        True if bitsandbytes can be imported, False otherwise.
    """
    try:
        import bitsandbytes

        return True
    except ImportError:
        return False


def _check_cuda_available() -> bool:
    """Check if CUDA is available for quantization.

    BitsAndBytes requires CUDA for quantized inference.

    Returns:
        True if CUDA is available, False otherwise.
    """
    return torch.cuda.is_available()


def get_quantization_config(
    mode: QuantizationMode | None = None,
    settings: QuantizationSettings | None = None,
):
    """Get BitsAndBytesConfig for model quantization.

    This function creates a BitsAndBytesConfig object that can be passed
    to AutoModelForCausalLM.from_pretrained() for quantized model loading.

    Args:
        mode: Quantization mode. If None, uses settings.mode or environment.
        settings: Full quantization settings. If None, loads from environment.

    Returns:
        BitsAndBytesConfig for quantized loading, or None if quantization
        is disabled or unavailable.

    Raises:
        ImportError: If bitsandbytes is not installed and quantization is requested.
        RuntimeError: If CUDA is not available and quantization is requested.

    Example:
        >>> config = get_quantization_config(mode=QuantizationMode.FOUR_BIT)
        >>> model = AutoModelForCausalLM.from_pretrained(
        ...     "nvidia/Nemotron-3-Nano-30B-A3B",
        ...     quantization_config=config,
        ...     device_map="auto",
        ... )
    """
    # Get settings from environment if not provided
    if settings is None:
        settings = QuantizationSettings.from_environment()

    # Override mode if explicitly provided
    if mode is not None:
        settings.mode = mode

    # Return None for no quantization
    if settings.mode == QuantizationMode.NONE:
        logger.info("Quantization disabled, using full precision")
        return None

    # Check prerequisites
    if not _check_bitsandbytes_available():
        raise ImportError(
            "bitsandbytes is required for quantization but not installed. "
            "Install with: pip install bitsandbytes>=0.44.0 "
            "or: uv sync --extra quantization"
        )

    if not _check_cuda_available():
        raise RuntimeError(
            "CUDA is required for BitsAndBytes quantization but not available. "
            "Set NEMOTRON_QUANTIZATION=none for CPU inference."
        )

    # Import BitsAndBytesConfig (deferred to avoid import errors when not installed)
    from transformers import BitsAndBytesConfig

    if settings.mode == QuantizationMode.FOUR_BIT:
        logger.info(
            f"Configuring 4-bit quantization: "
            f"quant_type={settings.quant_type.value}, "
            f"double_quant={settings.use_double_quant}, "
            f"compute_dtype={settings.compute_dtype}"
        )

        return BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=settings.compute_dtype,
            bnb_4bit_quant_type=settings.quant_type.value,
            bnb_4bit_use_double_quant=settings.use_double_quant,
        )

    elif settings.mode == QuantizationMode.EIGHT_BIT:
        logger.info("Configuring 8-bit quantization")

        return BitsAndBytesConfig(
            load_in_8bit=True,
            llm_int8_enable_fp32_cpu_offload=True,  # Enable CPU offload for large models
        )

    # Should not reach here
    return None


def get_memory_estimate(
    model_params_billions: float,
    mode: QuantizationMode,
) -> dict[str, float]:
    """Estimate memory requirements for different quantization modes.

    This provides rough estimates based on the number of model parameters.
    Actual memory usage may vary based on context length, batch size, and
    model architecture.

    Args:
        model_params_billions: Number of model parameters in billions.
        mode: Quantization mode to estimate for.

    Returns:
        Dictionary with memory estimates in GB:
        - "model_weights": Estimated model weight memory
        - "kv_cache_per_1k_tokens": KV cache per 1K tokens
        - "total_min": Minimum total memory estimate
        - "total_recommended": Recommended memory for comfortable operation

    Example:
        >>> estimates = get_memory_estimate(30.0, QuantizationMode.FOUR_BIT)
        >>> print(f"Minimum VRAM: {estimates['total_min']:.1f} GB")
        Minimum VRAM: 17.5 GB
    """
    params = model_params_billions

    # Bytes per parameter for different quantization modes
    if mode == QuantizationMode.FOUR_BIT:
        # 4-bit: 0.5 bytes per param + overhead (~10%)
        bytes_per_param = 0.55
    elif mode == QuantizationMode.EIGHT_BIT:
        # 8-bit: 1 byte per param + overhead (~10%)
        bytes_per_param = 1.1
    else:
        # Full precision (float16): 2 bytes per param
        bytes_per_param = 2.0

    # Calculate model weights memory in GB
    model_weights_gb = params * bytes_per_param

    # KV cache estimate (rough: ~0.1 GB per 1K tokens for 30B model in fp16)
    # Scales linearly with model size
    kv_cache_per_1k = 0.1 * (params / 30.0) * (bytes_per_param / 0.55)

    # Total estimates
    # Minimum: model + small context (4K tokens)
    total_min = model_weights_gb + (kv_cache_per_1k * 4)

    # Recommended: model + larger context (32K tokens) + overhead
    total_recommended = model_weights_gb + (kv_cache_per_1k * 32) + 2.0

    return {
        "model_weights": round(model_weights_gb, 2),
        "kv_cache_per_1k_tokens": round(kv_cache_per_1k, 3),
        "total_min": round(total_min, 2),
        "total_recommended": round(total_recommended, 2),
    }


def log_memory_info() -> None:
    """Log current GPU memory information.

    Useful for debugging memory issues during model loading.
    """
    if not torch.cuda.is_available():
        logger.info("CUDA not available - no GPU memory info")
        return

    for i in range(torch.cuda.device_count()):
        props = torch.cuda.get_device_properties(i)
        total_gb = props.total_memory / (1024**3)
        allocated_gb = torch.cuda.memory_allocated(i) / (1024**3)
        reserved_gb = torch.cuda.memory_reserved(i) / (1024**3)
        free_gb = total_gb - reserved_gb

        logger.info(
            f"GPU {i} ({props.name}): "
            f"Total={total_gb:.1f}GB, "
            f"Allocated={allocated_gb:.1f}GB, "
            f"Reserved={reserved_gb:.1f}GB, "
            f"Free={free_gb:.1f}GB"
        )
