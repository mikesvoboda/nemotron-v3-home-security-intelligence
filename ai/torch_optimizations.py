"""PyTorch Optimization Utilities for AI Services.

This module provides shared utilities for optimizing PyTorch model performance:
1. torch.compile() integration for Transformers models (NEM-3375)
2. True batch inference helpers (NEM-3377)
3. Accelerate device_map utilities (NEM-3378)
4. TensorRT integration via ai.common (NEM-3838)

Usage:
    from torch_optimizations import (
        compile_model,
        get_optimal_device_map,
        BatchProcessor,
        get_compile_mode,
        get_best_optimization_backend,
    )

    # Compile a model for faster inference
    model = compile_model(model, mode="reduce-overhead")

    # Get optimal device map for multi-GPU or CPU offloading
    device_map = get_optimal_device_map(model_name)

    # Process images in optimal batches
    processor = BatchProcessor(max_batch_size=8)
    for batch in processor.create_batches(images):
        results = model(batch)

    # Check best available optimization backend
    backend = get_best_optimization_backend()
    # Returns: "tensorrt", "torch_compile", or "none"

TensorRT Optimization:
    For TensorRT-accelerated inference, use the ai.common package:

    from ai.common import TensorRTInferenceBase, TensorRTConverter

    See ai/common/AGENTS.md for full documentation.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, TypeVar

import torch

if TYPE_CHECKING:
    from collections.abc import Iterator

    from PIL import Image

logger = logging.getLogger(__name__)

# Type variable for model classes
ModelT = TypeVar("ModelT")

# Supported torch.compile modes
COMPILE_MODES = frozenset(
    {"default", "reduce-overhead", "max-autotune", "max-autotune-no-cudagraphs"}
)

# Environment variable to disable torch.compile (useful for debugging)
TORCH_COMPILE_DISABLE = os.environ.get("TORCH_COMPILE_DISABLE", "0").lower() in ("1", "true", "yes")

# Environment variable to set compile mode
TORCH_COMPILE_MODE = os.environ.get("TORCH_COMPILE_MODE", "reduce-overhead")

# Minimum VRAM (in GB) required for torch.compile to be beneficial
MIN_VRAM_FOR_COMPILE = 4.0


def is_compile_supported() -> bool:
    """Check if torch.compile is supported on the current system.

    torch.compile requires:
    - PyTorch 2.0+
    - CUDA available (CPU compilation has limited benefit)
    - Sufficient VRAM

    Returns:
        True if torch.compile is supported and beneficial, False otherwise.
    """
    if TORCH_COMPILE_DISABLE:
        logger.debug("torch.compile disabled via TORCH_COMPILE_DISABLE environment variable")
        return False

    # Check PyTorch version (requires 2.0+)
    torch_version = tuple(int(x) for x in torch.__version__.split(".")[:2])
    if torch_version < (2, 0):
        logger.debug(f"torch.compile requires PyTorch 2.0+, got {torch.__version__}")
        return False

    # Check CUDA availability
    if not torch.cuda.is_available():
        logger.debug("torch.compile disabled: CUDA not available")
        return False

    # Check available VRAM
    try:
        device_props = torch.cuda.get_device_properties(0)
        total_vram_gb = device_props.total_memory / (1024**3)
        if total_vram_gb < MIN_VRAM_FOR_COMPILE:
            logger.debug(
                f"torch.compile disabled: insufficient VRAM "
                f"({total_vram_gb:.1f}GB < {MIN_VRAM_FOR_COMPILE}GB)"
            )
            return False
    except Exception as e:
        logger.debug(f"torch.compile disabled: failed to check VRAM: {e}")
        return False

    return True


def get_compile_mode() -> str:
    """Get the torch.compile mode to use.

    Available modes:
    - "default": Good balance of compile time and speedup
    - "reduce-overhead": Optimized for inference with reduced kernel launch overhead
    - "max-autotune": Maximum optimization (longer compile time)
    - "max-autotune-no-cudagraphs": Max optimization without CUDA graphs

    Returns:
        The compile mode string to use with torch.compile().
    """
    mode = TORCH_COMPILE_MODE
    if mode not in COMPILE_MODES:
        logger.warning(f"Invalid TORCH_COMPILE_MODE '{mode}', using 'reduce-overhead'")
        return "reduce-overhead"
    return mode


def compile_model(
    model: ModelT,
    mode: str | None = None,
    fullgraph: bool = False,
    dynamic: bool = True,
    backend: str = "inductor",
) -> ModelT:
    """Compile a PyTorch model using torch.compile() for faster inference.

    This function wraps torch.compile() with sensible defaults for inference
    workloads. It gracefully falls back to the uncompiled model if compilation
    fails or is not supported.

    Args:
        model: The PyTorch model to compile.
        mode: Compilation mode. If None, uses get_compile_mode().
              Options: "default", "reduce-overhead", "max-autotune"
        fullgraph: If True, requires the entire model to be compilable.
                   If False (default), allows graph breaks.
        dynamic: If True (default), handles dynamic shapes efficiently.
                 Set to False for fixed input shapes for better optimization.
        backend: Compilation backend. Default "inductor" for best performance.

    Returns:
        The compiled model (or original model if compilation is not supported).

    Example:
        >>> model = AutoModelForObjectDetection.from_pretrained(...)
        >>> model = compile_model(model, mode="reduce-overhead")
    """
    if not is_compile_supported():
        logger.info("Skipping torch.compile (not supported or disabled)")
        return model

    if mode is None:
        mode = get_compile_mode()

    try:
        logger.info(f"Compiling model with torch.compile(mode='{mode}', dynamic={dynamic})")

        # Use torch.compile with inference-optimized settings
        compiled_model = torch.compile(  # type: ignore[call-overload]
            model,
            mode=mode,
            fullgraph=fullgraph,
            dynamic=dynamic,
            backend=backend,
        )

        logger.info("Model compiled successfully")
        return compiled_model  # type: ignore[return-value, no-any-return]

    except Exception as e:
        logger.warning(f"torch.compile failed, using uncompiled model: {e}")
        return model


def get_optimal_device_map(
    _model_name_or_path: str,
    max_memory: dict[int | str, str] | None = None,
    _offload_folder: str | None = None,
) -> dict[str, Any] | str:
    """Get optimal device_map configuration for a model.

    Uses HuggingFace Accelerate to determine the best device placement
    for a model based on available hardware.

    Args:
        _model_name_or_path: HuggingFace model name or local path (reserved for future use).
        max_memory: Optional dict specifying max memory per device.
                    Example: {0: "10GB", "cpu": "30GB"}
        _offload_folder: Optional folder for disk offloading (reserved for future use).

    Returns:
        A device_map configuration suitable for from_pretrained().
        Returns "auto" if Accelerate should determine placement automatically.

    Example:
        >>> device_map = get_optimal_device_map("microsoft/Florence-2-large")
        >>> model = AutoModel.from_pretrained(model_name, device_map=device_map)
    """
    if not torch.cuda.is_available():
        logger.info("CUDA not available, using CPU device map")
        return {"": "cpu"}

    # For single GPU setups, use simple device placement
    if torch.cuda.device_count() == 1:
        logger.debug("Single GPU detected, using device_map='auto'")
        return "auto"

    # For multi-GPU, let Accelerate determine optimal placement
    logger.info(f"Multi-GPU setup ({torch.cuda.device_count()} GPUs), using device_map='auto'")

    # If max_memory is specified, return it for use in from_pretrained
    if max_memory is not None:
        logger.debug(f"Using custom max_memory configuration: {max_memory}")

    return "auto"


def load_model_with_accelerate(
    model_class: type[ModelT],
    model_name_or_path: str,
    torch_dtype: torch.dtype = torch.float16,
    use_compile: bool = True,
    compile_mode: str | None = None,
    **kwargs: Any,
) -> ModelT:
    """Load a model with optimal device placement and optional compilation.

    This is a convenience function that combines device_map="auto" with
    torch.compile() for optimal inference performance.

    Args:
        model_class: The model class to instantiate (e.g., AutoModel).
        model_name_or_path: HuggingFace model name or local path.
        torch_dtype: Data type for model weights. Default torch.float16.
        use_compile: Whether to apply torch.compile(). Default True.
        compile_mode: Mode for torch.compile(). If None, uses environment default.
        **kwargs: Additional arguments passed to from_pretrained().

    Returns:
        The loaded (and optionally compiled) model.

    Example:
        >>> from transformers import AutoModelForCausalLM
        >>> model = load_model_with_accelerate(
        ...     AutoModelForCausalLM,
        ...     "microsoft/Florence-2-large",
        ...     trust_remote_code=True,
        ... )
    """
    # Get optimal device map
    device_map = get_optimal_device_map(model_name_or_path)

    logger.info(f"Loading {model_name_or_path} with device_map='{device_map}'")

    # Load model with Accelerate device placement
    model = model_class.from_pretrained(  # type: ignore[attr-defined]
        model_name_or_path,
        device_map=device_map,
        torch_dtype=torch_dtype,
        **kwargs,
    )

    # Set to evaluation mode
    model.eval()

    # Optionally compile the model
    if use_compile:
        model = compile_model(model, mode=compile_mode)

    return model  # type: ignore[return-value, no-any-return]


@dataclass
class BatchConfig:
    """Configuration for batch processing.

    Attributes:
        max_batch_size: Maximum number of items per batch.
        dynamic_batching: If True, adjust batch size based on input sizes.
        pad_to_max: If True, pad all batches to max_batch_size.
    """

    max_batch_size: int = 8
    dynamic_batching: bool = True
    pad_to_max: bool = False


class BatchProcessor:
    """Helper class for creating optimal batches of images for inference.

    This class helps create properly-sized batches of images for efficient
    GPU inference, handling variable batch sizes and image dimensions.

    Attributes:
        config: BatchConfig with batch processing settings.

    Example:
        >>> processor = BatchProcessor(BatchConfig(max_batch_size=8))
        >>> images = [img1, img2, ..., img20]
        >>> for batch in processor.create_batches(images):
        ...     results = model(batch)
    """

    def __init__(self, config: BatchConfig | None = None):
        """Initialize the batch processor.

        Args:
            config: Optional BatchConfig. Uses defaults if not provided.
        """
        self.config = config or BatchConfig()
        logger.debug(f"BatchProcessor initialized with max_batch_size={self.config.max_batch_size}")

    def create_batches(
        self,
        items: list[Any],
        batch_size: int | None = None,
    ) -> Iterator[list[Any]]:
        """Create batches from a list of items.

        Args:
            items: List of items to batch (e.g., PIL Images, tensors).
            batch_size: Override batch size. If None, uses config.max_batch_size.

        Yields:
            Batches of items.

        Example:
            >>> for batch in processor.create_batches(images):
            ...     tensors = preprocess(batch)
            ...     outputs = model(tensors)
        """
        if not items:
            return

        size = batch_size or self.config.max_batch_size

        for i in range(0, len(items), size):
            yield items[i : i + size]

    def get_optimal_batch_size(
        self,
        sample_image: Image.Image,
        available_vram_gb: float | None = None,
        bytes_per_pixel: float = 4.0,
    ) -> int:
        """Calculate optimal batch size based on image size and available VRAM.

        This method estimates how many images can fit in GPU memory based on
        the sample image dimensions and available VRAM.

        Args:
            sample_image: A sample image to estimate memory requirements.
            available_vram_gb: Available VRAM in GB. If None, queries GPU.
            bytes_per_pixel: Estimated bytes per pixel for processed tensors.

        Returns:
            Optimal batch size (at least 1, at most config.max_batch_size).
        """
        if not self.config.dynamic_batching:
            return self.config.max_batch_size

        # Get available VRAM
        if available_vram_gb is None:
            if torch.cuda.is_available():
                try:
                    free_mem, _ = torch.cuda.mem_get_info()
                    available_vram_gb = free_mem / (1024**3)
                except Exception:
                    available_vram_gb = 4.0  # Conservative default
            else:
                available_vram_gb = 4.0

        # Estimate memory per image
        width, height = sample_image.size
        channels = 3  # RGB
        # Account for:
        # - Input tensor
        # - Intermediate activations (rough 4x multiplier)
        # - Model gradients (not needed for inference, but buffer)
        estimated_mb_per_image = (width * height * channels * bytes_per_pixel * 4) / (1024**2)

        # Reserve 1GB for model weights and overhead
        usable_vram_mb = (available_vram_gb - 1.0) * 1024

        if estimated_mb_per_image <= 0:
            return self.config.max_batch_size

        optimal = int(usable_vram_mb / estimated_mb_per_image)

        # Clamp to valid range
        return max(1, min(optimal, self.config.max_batch_size))


def warmup_compiled_model(
    model: Any,
    sample_input: Any,
    num_warmup: int = 3,
) -> None:
    """Warm up a compiled model with sample inputs.

    torch.compile() performs JIT compilation on first execution, which can
    cause slow initial inference. This function runs warmup iterations to
    trigger compilation before production traffic.

    Args:
        model: The compiled model to warm up.
        sample_input: Sample input(s) for the model.
        num_warmup: Number of warmup iterations.

    Example:
        >>> sample = processor(images=dummy_image, return_tensors="pt")
        >>> warmup_compiled_model(model, sample, num_warmup=3)
    """
    logger.info(f"Warming up compiled model with {num_warmup} iterations")

    for i in range(num_warmup):
        try:
            with torch.no_grad():
                # Call model with appropriate unpacking based on input type
                _ = model(**sample_input) if isinstance(sample_input, dict) else model(sample_input)
            logger.debug(f"Warmup iteration {i + 1}/{num_warmup} complete")
        except Exception as e:
            logger.warning(f"Warmup iteration {i + 1} failed: {e}")

    logger.info("Model warmup complete")


def get_torch_dtype_for_device(device: str = "cuda:0") -> torch.dtype:
    """Get the optimal torch dtype for the given device.

    Uses float16 for CUDA (with tensor cores) and float32 for CPU.

    Args:
        device: Target device string (e.g., "cuda:0", "cpu").

    Returns:
        Optimal torch.dtype for the device.
    """
    if "cuda" in device and torch.cuda.is_available():
        # Check for bfloat16 support (Ampere and newer)
        if torch.cuda.is_bf16_supported():
            return torch.bfloat16
        return torch.float16
    return torch.float32


def is_tensorrt_available() -> bool:
    """Check if TensorRT optimization is available.

    This function checks for TensorRT availability via the ai.common package.

    Returns:
        True if TensorRT is installed and available, False otherwise.
    """
    try:
        from ai.common import is_tensorrt_available as _is_trt_available

        return _is_trt_available()
    except ImportError:
        logger.debug("ai.common not available, TensorRT support unavailable")
        return False


def get_best_optimization_backend() -> str:
    """Determine the best available optimization backend.

    Checks availability of optimization backends in order of preference:
    1. TensorRT (fastest, requires NVIDIA TensorRT)
    2. torch.compile (good speedup, requires PyTorch 2.0+)
    3. None (no optimization available)

    Returns:
        String indicating best available backend:
        - "tensorrt": TensorRT available (use ai.common.TensorRTInferenceBase)
        - "torch_compile": torch.compile available (use compile_model())
        - "none": No optimization available

    Example:
        >>> backend = get_best_optimization_backend()
        >>> if backend == "tensorrt":
        ...     from ai.common import TensorRTInferenceBase
        ...     # Use TensorRT base class
        >>> elif backend == "torch_compile":
        ...     model = compile_model(model)
        >>> else:
        ...     # Use unoptimized model
    """
    # Check TensorRT first (fastest option)
    if is_tensorrt_available():
        logger.debug("TensorRT available - recommended for production inference")
        return "tensorrt"

    # Check torch.compile (good alternative)
    if is_compile_supported():
        logger.debug("torch.compile available - good for flexible inference")
        return "torch_compile"

    # No optimization available
    logger.debug("No optimization backend available")
    return "none"


def get_optimization_recommendation(
    model_type: str = "detection",
    production: bool = True,
) -> dict[str, Any]:
    """Get optimization recommendations for a specific use case.

    Args:
        model_type: Type of model ("detection", "classification", "embedding")
        production: Whether this is for production deployment (vs development)

    Returns:
        Dictionary with optimization recommendations:
        - backend: Recommended backend ("tensorrt" or "torch_compile")
        - precision: Recommended precision ("fp32", "fp16", or "int8")
        - batch_size: Recommended batch size
        - dynamic_shapes: Whether to enable dynamic shape support
        - notes: Additional recommendations

    Example:
        >>> rec = get_optimization_recommendation("detection", production=True)
        >>> print(rec["backend"], rec["precision"])
        'tensorrt' 'fp16'
    """
    backend = get_best_optimization_backend()

    # Model-type specific recommendations
    recommendations: dict[str, Any] = {
        "backend": backend,
        "precision": "fp16",  # Good default for most models
        "dynamic_shapes": True,
        "notes": [],
    }

    # Adjust batch size based on model type
    batch_size_map = {
        "detection": 4,  # Detection models need more VRAM per image
        "classification": 16,  # Classification can handle larger batches
        "embedding": 32,  # Embeddings are lightweight
    }
    recommendations["batch_size"] = batch_size_map.get(model_type, 8)

    # Production vs development adjustments
    if production:
        recommendations["notes"].append("Use TensorRT for production when available")
        if backend == "tensorrt":
            recommendations["notes"].append("Consider INT8 for maximum throughput")
    else:
        recommendations["notes"].append("torch.compile is easier to debug in development")
        recommendations["dynamic_shapes"] = True  # More flexible for testing

    # Backend-specific notes
    if backend == "tensorrt":
        recommendations["notes"].append(
            "Build engine with representative input shapes for best performance"
        )
    elif backend == "torch_compile":
        recommendations["notes"].append("Run warmup iterations before benchmarking")

    return recommendations
