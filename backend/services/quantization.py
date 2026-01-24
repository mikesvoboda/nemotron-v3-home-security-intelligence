"""Model quantization utilities for memory-efficient inference.

This module provides quantization utilities to reduce VRAM usage and improve
inference throughput for AI models in the security monitoring pipeline.

Quantization Strategies:

1. **INT8 Quantization** (via torch.ao.quantization):
   - 2-4x memory reduction for low-priority models
   - Suitable for: auxiliary classifiers, feature extractors
   - CPU and CUDA support
   - Minor accuracy impact (typically <1% for classification tasks)

2. **4-bit Quantization** (via bitsandbytes):
   - 4x memory reduction for large language models
   - Suitable for: Nemotron LLM, other transformer-based models
   - Uses NormalFloat4 (NF4) quantization for optimal accuracy
   - Requires CUDA and bitsandbytes package

Usage Examples:

    # INT8 quantization for a ViT classifier
    from backend.services.quantization import apply_int8_quantization

    model = AutoModelForImageClassification.from_pretrained(path)
    model_int8 = apply_int8_quantization(
        model,
        calibration_data=calibration_images,
        backend="x86"  # or "qnnpack" for ARM
    )

    # 4-bit quantization config for LLMs
    from backend.services.quantization import get_bnb_4bit_config

    config = get_bnb_4bit_config()
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        quantization_config=config
    )

Supported Models for INT8:
    - vit-age-classifier (~200MB -> ~50MB)
    - vit-gender-classifier (~200MB -> ~50MB)
    - pet-classifier (~200MB -> ~50MB)
    - osnet-x0-25 (~100MB -> ~25MB)
    - threat-detection-yolov8n (~300MB -> ~75MB)

Supported Models for 4-bit:
    - Nemotron LLM (~21.7GB -> ~5.4GB)
    - Other transformer-based LLMs

NEM-3373: INT8 quantization for low-priority models
NEM-3376: bitsandbytes 4-bit quantization for LLMs
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, Protocol

from backend.core.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

logger = get_logger(__name__)


class QuantizationBackend(str, Enum):
    """Supported quantization backends for INT8."""

    X86 = "x86"  # For x86_64 CPUs (Intel, AMD)
    QNNPACK = "qnnpack"  # For ARM/mobile CPUs
    FBGEMM = "fbgemm"  # Facebook optimized backend for server CPUs
    ONEDNN = "onednn"  # Intel oneAPI Deep Neural Network Library


class QuantizationType(str, Enum):
    """Quantization precision types."""

    INT8 = "int8"  # 8-bit integer quantization
    INT4 = "int4"  # 4-bit integer quantization (bitsandbytes)
    FP16 = "fp16"  # 16-bit floating point (half precision)
    FP8 = "fp8"  # 8-bit floating point (experimental)


@dataclass(slots=True)
class QuantizationResult:
    """Result from model quantization.

    Attributes:
        model: The quantized model instance
        original_size_mb: Original model size in megabytes
        quantized_size_mb: Quantized model size in megabytes
        compression_ratio: Compression ratio (original / quantized)
        quantization_type: Type of quantization applied
        backend: Quantization backend used (for INT8)
    """

    model: Any
    original_size_mb: float
    quantized_size_mb: float
    compression_ratio: float
    quantization_type: QuantizationType
    backend: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "original_size_mb": round(self.original_size_mb, 2),
            "quantized_size_mb": round(self.quantized_size_mb, 2),
            "compression_ratio": round(self.compression_ratio, 2),
            "quantization_type": self.quantization_type.value,
            "backend": self.backend,
        }


class QuantizableModel(Protocol):
    """Protocol for models that support quantization."""

    def eval(self) -> Any:
        """Set model to evaluation mode."""
        ...


def _is_bitsandbytes_available() -> bool:
    """Check if bitsandbytes package is available.

    Returns:
        True if bitsandbytes is installed and CUDA is available, False otherwise.
    """
    try:
        import importlib.util

        if importlib.util.find_spec("bitsandbytes") is None:
            return False

        # bitsandbytes requires CUDA
        import torch

        return bool(torch.cuda.is_available())
    except (ImportError, ModuleNotFoundError):
        return False


def _get_model_size_mb(model: Any) -> float:
    """Estimate model size in megabytes.

    Args:
        model: PyTorch model

    Returns:
        Estimated size in megabytes
    """
    try:
        import torch

        total_params: int = sum(p.numel() for p in model.parameters())
        # Assume fp32 (4 bytes per parameter) if dtype not available
        param_size = 4
        for p in model.parameters():
            if p.dtype == torch.float16:
                param_size = 2
            elif p.dtype == torch.int8:
                param_size = 1
            break
        return float(total_params * param_size) / (1024 * 1024)
    except Exception:
        return 0.0


def get_optimal_backend() -> QuantizationBackend:
    """Determine the optimal quantization backend for the current platform.

    Returns:
        QuantizationBackend enum value for the current platform
    """
    import platform

    machine = platform.machine().lower()

    if machine in ("arm64", "aarch64"):
        return QuantizationBackend.QNNPACK
    elif machine in ("x86_64", "amd64"):
        # Check for Intel vs AMD for potential oneDNN optimization
        try:
            import cpuinfo

            cpu_info = cpuinfo.get_cpu_info()
            vendor = cpu_info.get("vendor_id_raw", "").lower()
            if "intel" in vendor:
                return QuantizationBackend.ONEDNN
        except ImportError:
            pass
        return QuantizationBackend.X86
    else:
        # Default to x86 backend
        return QuantizationBackend.X86


def get_bnb_4bit_config(
    compute_dtype: str = "float16",
    quant_type: str = "nf4",
    use_double_quant: bool = True,
) -> Any:
    """Get BitsAndBytes 4-bit quantization configuration.

    This configuration is optimized for loading large language models
    like Nemotron with minimal VRAM usage while preserving accuracy.

    Args:
        compute_dtype: Compute dtype for 4-bit base matrices.
            Options: "float16", "bfloat16", "float32"
        quant_type: Quantization data type.
            Options: "nf4" (NormalFloat4), "fp4" (FloatingPoint4)
        use_double_quant: Enable double quantization for additional memory savings.
            Quantizes the quantization constants for ~0.4 bits/parameter savings.

    Returns:
        BitsAndBytesConfig instance for use with from_pretrained()

    Raises:
        ImportError: If bitsandbytes is not installed
        RuntimeError: If CUDA is not available

    Example:
        config = get_bnb_4bit_config()
        model = AutoModelForCausalLM.from_pretrained(
            "nvidia/Nemotron-Mini-4B-Instruct",
            quantization_config=config,
            device_map="auto"
        )
    """
    if not _is_bitsandbytes_available():
        raise ImportError(
            "bitsandbytes package not installed or CUDA not available. "
            "Install with: pip install bitsandbytes"
        )

    try:
        import torch
        from transformers import BitsAndBytesConfig

        # Map string dtype to torch dtype
        dtype_map = {
            "float16": torch.float16,
            "bfloat16": torch.bfloat16,
            "float32": torch.float32,
        }

        if compute_dtype not in dtype_map:
            raise ValueError(
                f"Invalid compute_dtype: {compute_dtype}. Options: {list(dtype_map.keys())}"
            )

        if quant_type not in ("nf4", "fp4"):
            raise ValueError(f"Invalid quant_type: {quant_type}. Options: 'nf4', 'fp4'")

        config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type=quant_type,
            bnb_4bit_compute_dtype=dtype_map[compute_dtype],
            bnb_4bit_use_double_quant=use_double_quant,
        )

        logger.info(
            f"Created BitsAndBytes 4-bit config: "
            f"quant_type={quant_type}, compute_dtype={compute_dtype}, "
            f"double_quant={use_double_quant}"
        )

        return config

    except ImportError as e:
        logger.error("Failed to import transformers BitsAndBytesConfig")
        raise ImportError(
            "transformers package with BitsAndBytesConfig support required. "
            "Install with: pip install transformers>=4.30.0"
        ) from e


def get_bnb_8bit_config(
    llm_int8_threshold: float = 6.0,
    llm_int8_has_fp16_weight: bool = False,
) -> Any:
    """Get BitsAndBytes 8-bit quantization configuration.

    8-bit quantization provides a balance between memory savings and accuracy,
    with less aggressive compression than 4-bit.

    Args:
        llm_int8_threshold: Threshold for outlier detection.
            Values above this use fp16 for better accuracy.
        llm_int8_has_fp16_weight: Keep weights in fp16 format.
            Uses more memory but may improve accuracy.

    Returns:
        BitsAndBytesConfig instance for use with from_pretrained()

    Raises:
        ImportError: If bitsandbytes is not installed
        RuntimeError: If CUDA is not available
    """
    if not _is_bitsandbytes_available():
        raise ImportError(
            "bitsandbytes package not installed or CUDA not available. "
            "Install with: pip install bitsandbytes"
        )

    try:
        from transformers import BitsAndBytesConfig

        config = BitsAndBytesConfig(
            load_in_8bit=True,
            llm_int8_threshold=llm_int8_threshold,
            llm_int8_has_fp16_weight=llm_int8_has_fp16_weight,
        )

        logger.info(
            f"Created BitsAndBytes 8-bit config: "
            f"threshold={llm_int8_threshold}, fp16_weight={llm_int8_has_fp16_weight}"
        )

        return config

    except ImportError as e:
        logger.error("Failed to import transformers BitsAndBytesConfig")
        raise ImportError(
            "transformers package with BitsAndBytesConfig support required. "
            "Install with: pip install transformers>=4.30.0"
        ) from e


def apply_dynamic_int8_quantization(
    model: Any,
    backend: QuantizationBackend | str = QuantizationBackend.X86,
) -> QuantizationResult:
    """Apply dynamic INT8 quantization to a PyTorch model.

    Dynamic quantization quantizes weights ahead of time and activations
    dynamically at inference time. This is the simplest form of quantization
    and works well for LSTM, Transformer, and most classification models.

    Args:
        model: PyTorch model to quantize
        backend: Quantization backend to use

    Returns:
        QuantizationResult with the quantized model and metrics

    Raises:
        ImportError: If torch is not installed
        RuntimeError: If quantization fails

    Example:
        model = AutoModelForImageClassification.from_pretrained(path)
        result = apply_dynamic_int8_quantization(model)
        quantized_model = result.model
    """
    try:
        import torch
        import torch.ao.quantization as quant

        # Convert backend enum to string if needed
        backend_str = backend.value if isinstance(backend, QuantizationBackend) else backend

        # Get original size
        original_size = _get_model_size_mb(model)

        # Set model to eval mode
        model.eval()

        # Set quantization backend
        torch.backends.quantized.engine = backend_str

        # Apply dynamic quantization to Linear and LSTM layers
        # These are the most common layers in classification models
        quantized_model = quant.quantize_dynamic(
            model,
            {torch.nn.Linear, torch.nn.LSTM},
            dtype=torch.qint8,
        )

        # Get quantized size
        quantized_size = _get_model_size_mb(quantized_model)

        # Calculate compression ratio
        compression_ratio = original_size / quantized_size if quantized_size > 0 else 1.0

        logger.info(
            f"Dynamic INT8 quantization complete: "
            f"{original_size:.1f}MB -> {quantized_size:.1f}MB "
            f"({compression_ratio:.2f}x compression)"
        )

        return QuantizationResult(
            model=quantized_model,
            original_size_mb=original_size,
            quantized_size_mb=quantized_size,
            compression_ratio=compression_ratio,
            quantization_type=QuantizationType.INT8,
            backend=backend_str,
        )

    except ImportError as e:
        logger.error("torch not installed for INT8 quantization")
        raise ImportError("torch package required for INT8 quantization") from e

    except Exception as e:
        logger.error(f"INT8 quantization failed: {e}", exc_info=True)
        raise RuntimeError(f"Failed to apply INT8 quantization: {e}") from e


def apply_static_int8_quantization(
    model: Any,
    calibration_fn: Callable[[Any], None],
    backend: QuantizationBackend | str = QuantizationBackend.X86,
) -> QuantizationResult:
    """Apply static INT8 quantization with calibration.

    Static quantization requires calibration data to determine the optimal
    quantization parameters. This typically provides better accuracy than
    dynamic quantization but requires representative calibration samples.

    Args:
        model: PyTorch model to quantize
        calibration_fn: Function that runs calibration data through the model.
            Should call model(inputs) with representative samples.
        backend: Quantization backend to use

    Returns:
        QuantizationResult with the quantized model and metrics

    Raises:
        ImportError: If torch is not installed
        RuntimeError: If quantization fails

    Example:
        def calibrate(model):
            for batch in calibration_loader:
                model(batch)

        result = apply_static_int8_quantization(model, calibrate)
    """
    try:
        import torch
        import torch.ao.quantization as quant

        # Convert backend enum to string if needed
        backend_str = backend.value if isinstance(backend, QuantizationBackend) else backend

        # Get original size
        original_size = _get_model_size_mb(model)

        # Set model to eval mode
        model.eval()

        # Set quantization backend
        torch.backends.quantized.engine = backend_str

        # Get default quantization config for the backend
        model.qconfig = quant.get_default_qconfig(backend_str)

        # Prepare model for calibration
        # This inserts observers to collect activation statistics
        model_prepared = quant.prepare(model)

        # Run calibration
        logger.info("Running calibration for static INT8 quantization...")
        with torch.no_grad():
            calibration_fn(model_prepared)

        # Convert to quantized model
        quantized_model = quant.convert(model_prepared)

        # Get quantized size
        quantized_size = _get_model_size_mb(quantized_model)

        # Calculate compression ratio
        compression_ratio = original_size / quantized_size if quantized_size > 0 else 1.0

        logger.info(
            f"Static INT8 quantization complete: "
            f"{original_size:.1f}MB -> {quantized_size:.1f}MB "
            f"({compression_ratio:.2f}x compression)"
        )

        return QuantizationResult(
            model=quantized_model,
            original_size_mb=original_size,
            quantized_size_mb=quantized_size,
            compression_ratio=compression_ratio,
            quantization_type=QuantizationType.INT8,
            backend=backend_str,
        )

    except ImportError as e:
        logger.error("torch not installed for INT8 quantization")
        raise ImportError("torch package required for INT8 quantization") from e

    except Exception as e:
        logger.error(f"Static INT8 quantization failed: {e}", exc_info=True)
        raise RuntimeError(f"Failed to apply static INT8 quantization: {e}") from e


async def apply_int8_quantization_async(
    model: Any,
    calibration_data: Sequence[Any] | None = None,
    backend: QuantizationBackend | str = QuantizationBackend.X86,
    use_static: bool = False,
) -> QuantizationResult:
    """Async wrapper for INT8 quantization.

    Runs quantization in a thread pool to avoid blocking the event loop.

    Args:
        model: PyTorch model to quantize
        calibration_data: Optional calibration samples for static quantization
        backend: Quantization backend to use
        use_static: Use static quantization if calibration_data provided

    Returns:
        QuantizationResult with the quantized model and metrics
    """
    loop = asyncio.get_event_loop()

    if use_static and calibration_data is not None:

        def calibration_fn(prepared_model: Any) -> None:
            for sample in calibration_data:
                prepared_model(sample)

        return await loop.run_in_executor(
            None,
            lambda: apply_static_int8_quantization(model, calibration_fn, backend),
        )
    else:
        return await loop.run_in_executor(
            None, lambda: apply_dynamic_int8_quantization(model, backend)
        )


# Model quantization recommendations
# Maps model names to recommended quantization settings
QUANTIZATION_RECOMMENDATIONS: dict[str, dict[str, Any]] = {
    # Low-priority classification models - good candidates for INT8
    "vit-age-classifier": {
        "type": QuantizationType.INT8,
        "method": "dynamic",
        "expected_compression": 3.5,
        "accuracy_impact": "minimal (<1%)",
    },
    "vit-gender-classifier": {
        "type": QuantizationType.INT8,
        "method": "dynamic",
        "expected_compression": 3.5,
        "accuracy_impact": "minimal (<1%)",
    },
    "pet-classifier": {
        "type": QuantizationType.INT8,
        "method": "dynamic",
        "expected_compression": 3.0,
        "accuracy_impact": "minimal (<1%)",
    },
    "osnet-x0-25": {
        "type": QuantizationType.INT8,
        "method": "dynamic",
        "expected_compression": 3.0,
        "accuracy_impact": "minimal (<2%)",
    },
    "threat-detection-yolov8n": {
        "type": QuantizationType.INT8,
        "method": "static",  # Static recommended for detection models
        "expected_compression": 3.0,
        "accuracy_impact": "low (<3% mAP)",
    },
    # Large language models - 4-bit quantization
    "nemotron": {
        "type": QuantizationType.INT4,
        "method": "bitsandbytes",
        "expected_compression": 4.0,
        "accuracy_impact": "low (<5% perplexity)",
    },
    # Medium priority models - FP16 for GPU, INT8 optional
    "violence-detection": {
        "type": QuantizationType.FP16,
        "method": "native",
        "expected_compression": 2.0,
        "accuracy_impact": "none",
    },
    "weather-classification": {
        "type": QuantizationType.FP16,
        "method": "native",
        "expected_compression": 2.0,
        "accuracy_impact": "none",
    },
}


def get_quantization_recommendation(model_name: str) -> dict[str, Any] | None:
    """Get recommended quantization settings for a model.

    Args:
        model_name: Name of the model from Model Zoo

    Returns:
        Dictionary with recommended settings, or None if not found

    Example:
        rec = get_quantization_recommendation("vit-age-classifier")
        if rec and rec["type"] == QuantizationType.INT8:
            model = apply_dynamic_int8_quantization(model)
    """
    return QUANTIZATION_RECOMMENDATIONS.get(model_name)


def is_quantization_supported(model_name: str) -> bool:
    """Check if a model has quantization recommendations.

    Args:
        model_name: Name of the model from Model Zoo

    Returns:
        True if quantization is recommended for this model
    """
    return model_name in QUANTIZATION_RECOMMENDATIONS
