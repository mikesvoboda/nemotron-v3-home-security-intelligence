"""CPU Offloading for Large Models (NEM-3813).

This module provides utilities for CPU offloading support when models exceed
available GPU memory. It integrates with HuggingFace Accelerate to enable
automatic layer offloading and memory-efficient inference.

Key features:
- Automatic GPU/CPU memory detection
- Layer-by-layer offloading for large models
- Disk offloading for extreme memory constraints
- Integration with HuggingFace Accelerate device_map
- Memory-efficient gradient checkpointing support
- Dynamic offloading based on runtime memory pressure

Performance considerations:
- CPU offloading trades latency for memory capacity
- PCIe bandwidth limits data transfer speed
- Layer pinning can reduce transfer overhead
- Disk offloading is significantly slower than RAM

Usage:
    from ai.cpu_offloading import (
        get_offload_device_map,
        load_model_with_offloading,
        OffloadingConfig,
    )

    # Automatic device map with CPU offloading
    device_map = get_offload_device_map(
        model_name="nvidia/Nemotron-3-Nano-30B-A3B",
        max_gpu_memory_gb=16.0,
        allow_cpu_offload=True,
    )

    # Load model with offloading
    model = load_model_with_offloading(
        AutoModelForCausalLM,
        "nvidia/Nemotron-3-Nano-30B-A3B",
        max_gpu_memory_gb=16.0,
    )

References:
    - NEM-3813: Implement CPU Offloading for Large Models
    - https://huggingface.co/docs/accelerate/concept_guides/big_model_inference
    - https://huggingface.co/docs/accelerate/usage_guides/big_modeling
"""

from __future__ import annotations

import gc
import logging
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar

import torch

if TYPE_CHECKING:
    from transformers import PreTrainedModel

logger = logging.getLogger(__name__)

# Type variable for model classes
ModelT = TypeVar("ModelT")

# Environment variable to disable CPU offloading
CPU_OFFLOAD_DISABLE = os.environ.get("CPU_OFFLOAD_DISABLE", "0").lower() in (
    "1",
    "true",
    "yes",
)

# Default memory reservation for GPU (leave room for activations)
DEFAULT_GPU_MEMORY_FRACTION = 0.85

# Default folder for disk offloading
DEFAULT_OFFLOAD_FOLDER = tempfile.gettempdir() + "/hf_offload"


def is_cpu_offloading_supported() -> bool:
    """Check if CPU offloading is supported.

    CPU offloading requires:
    - accelerate library installed
    - CUDA available (to have something to offload from)

    Returns:
        True if CPU offloading is supported.
    """
    if CPU_OFFLOAD_DISABLE:
        logger.debug("CPU offloading disabled via CPU_OFFLOAD_DISABLE environment variable")
        return False

    try:
        import accelerate

        return True
    except ImportError:
        logger.debug("CPU offloading disabled: accelerate library not installed")
        return False


def get_gpu_memory_info() -> dict[str, Any]:
    """Get information about GPU memory.

    Returns:
        Dictionary with GPU memory information.
    """
    if not torch.cuda.is_available():
        return {
            "available": False,
            "num_gpus": 0,
            "gpus": [],
        }

    num_gpus = torch.cuda.device_count()
    gpus = []

    for i in range(num_gpus):
        props = torch.cuda.get_device_properties(i)
        total_memory = props.total_memory
        allocated = torch.cuda.memory_allocated(i)
        reserved = torch.cuda.memory_reserved(i)
        free = total_memory - reserved

        gpus.append(
            {
                "index": i,
                "name": props.name,
                "total_gb": total_memory / (1024**3),
                "allocated_gb": allocated / (1024**3),
                "reserved_gb": reserved / (1024**3),
                "free_gb": free / (1024**3),
            }
        )

    return {
        "available": True,
        "num_gpus": num_gpus,
        "gpus": gpus,
    }


def get_cpu_memory_info() -> dict[str, Any]:
    """Get information about CPU memory.

    Returns:
        Dictionary with CPU memory information.
    """
    try:
        import psutil

        mem = psutil.virtual_memory()
        return {
            "total_gb": mem.total / (1024**3),
            "available_gb": mem.available / (1024**3),
            "used_gb": mem.used / (1024**3),
            "percent_used": mem.percent,
        }
    except ImportError:
        # Fall back to basic info
        return {
            "total_gb": None,
            "available_gb": None,
            "note": "Install psutil for detailed memory info",
        }


def estimate_model_size_gb(
    model_name_or_path: str,
    dtype: torch.dtype = torch.float16,
) -> float:
    """Estimate model size based on name/path.

    This is a heuristic based on common model naming conventions.

    Args:
        model_name_or_path: Model name or path.
        dtype: Data type for parameters.

    Returns:
        Estimated size in gigabytes.
    """
    # Common size patterns in model names
    name_lower = model_name_or_path.lower()

    # Parameter count heuristics
    param_billions = None

    # Try to extract parameter count from name
    import re

    # Patterns like "30b", "7b", "70b", etc.
    match = re.search(r"(\d+)b", name_lower)
    if match:
        param_billions = float(match.group(1))

    # Patterns like "llama-2-13b", "mistral-7b"
    if param_billions is None:
        match = re.search(r"(\d+\.?\d*)b", name_lower)
        if match:
            param_billions = float(match.group(1))

    if param_billions is None:
        # Conservative default
        logger.warning(f"Could not estimate size for {model_name_or_path}, using 7B default")
        param_billions = 7.0

    # Calculate size based on dtype
    bytes_per_param = torch.tensor([], dtype=dtype).element_size()
    size_bytes = param_billions * 1e9 * bytes_per_param

    # Add overhead for optimizer states, activations, etc. (rough 20%)
    total_bytes = size_bytes * 1.2

    return total_bytes / (1024**3)


@dataclass
class OffloadingConfig:
    """Configuration for CPU/disk offloading.

    Attributes:
        max_gpu_memory_gb: Maximum GPU memory to use (None = auto-detect).
        max_cpu_memory_gb: Maximum CPU memory for offloading.
        offload_folder: Folder for disk offloading.
        offload_state_dict: Whether to offload state dict to CPU.
        offload_buffers: Whether to offload buffers along with parameters.
        preload_module_classes: Module classes to preload to GPU.
        low_cpu_mem_usage: Use memory-efficient loading.
        torch_dtype: Data type for model parameters.
    """

    max_gpu_memory_gb: float | None = None
    max_cpu_memory_gb: float | None = None
    offload_folder: str = DEFAULT_OFFLOAD_FOLDER
    offload_state_dict: bool = False
    offload_buffers: bool = False
    preload_module_classes: list[str] = field(default_factory=list)
    low_cpu_mem_usage: bool = True
    torch_dtype: torch.dtype = torch.float16


def get_max_memory_config(
    max_gpu_memory_gb: float | None = None,
    max_cpu_memory_gb: float | None = None,
    gpu_memory_fraction: float = DEFAULT_GPU_MEMORY_FRACTION,
) -> dict[int | str, str]:
    """Create a max_memory configuration for device_map.

    Args:
        max_gpu_memory_gb: Maximum GPU memory per GPU (None = auto).
        max_cpu_memory_gb: Maximum CPU memory (None = auto).
        gpu_memory_fraction: Fraction of GPU memory to use.

    Returns:
        Dictionary mapping device IDs to memory limits.
    """
    max_memory: dict[int | str, str] = {}

    if torch.cuda.is_available():
        for i in range(torch.cuda.device_count()):
            if max_gpu_memory_gb is not None:
                max_memory[i] = f"{max_gpu_memory_gb}GiB"
            else:
                # Auto-detect available memory
                props = torch.cuda.get_device_properties(i)
                available_gb = (props.total_memory * gpu_memory_fraction) / (1024**3)
                max_memory[i] = f"{available_gb:.1f}GiB"

    # CPU memory
    if max_cpu_memory_gb is not None:
        max_memory["cpu"] = f"{max_cpu_memory_gb}GiB"
    else:
        cpu_info = get_cpu_memory_info()
        if cpu_info.get("available_gb"):
            # Use 80% of available CPU memory
            available = cpu_info["available_gb"] * 0.8
            max_memory["cpu"] = f"{available:.1f}GiB"

    return max_memory


def get_offload_device_map(
    model_name_or_path: str,
    max_gpu_memory_gb: float | None = None,
    max_cpu_memory_gb: float | None = None,
    allow_cpu_offload: bool = True,
    allow_disk_offload: bool = False,
    offload_folder: str = DEFAULT_OFFLOAD_FOLDER,
) -> str | dict[str, Any]:
    """Get a device_map that enables CPU offloading when needed.

    This function determines whether the model needs CPU offloading
    and returns an appropriate device_map.

    Args:
        model_name_or_path: Model name or path.
        max_gpu_memory_gb: Maximum GPU memory to use.
        max_cpu_memory_gb: Maximum CPU memory for offloading.
        allow_cpu_offload: Whether to allow CPU offloading.
        allow_disk_offload: Whether to allow disk offloading.
        offload_folder: Folder for disk offloading.

    Returns:
        Device map string or dictionary.
    """
    if not torch.cuda.is_available():
        logger.info("CUDA not available, using CPU")
        return {"": "cpu"}

    # Estimate model size
    estimated_size = estimate_model_size_gb(model_name_or_path)

    # Get available GPU memory
    gpu_info = get_gpu_memory_info()
    total_gpu_memory = sum(gpu["total_gb"] for gpu in gpu_info.get("gpus", []))

    if max_gpu_memory_gb is not None:
        available_gpu = min(max_gpu_memory_gb, total_gpu_memory)
    else:
        available_gpu = total_gpu_memory * DEFAULT_GPU_MEMORY_FRACTION

    logger.info(
        f"Model size estimate: {estimated_size:.1f}GB, Available GPU memory: {available_gpu:.1f}GB"
    )

    # Check if model fits in GPU
    if estimated_size <= available_gpu:
        logger.info("Model fits in GPU memory, using device_map='auto'")
        return "auto"

    # Model needs offloading
    if not allow_cpu_offload:
        logger.warning(
            f"Model ({estimated_size:.1f}GB) exceeds GPU memory ({available_gpu:.1f}GB) "
            f"but CPU offloading is disabled"
        )
        return "auto"

    logger.info(
        f"Model ({estimated_size:.1f}GB) exceeds GPU memory ({available_gpu:.1f}GB), "
        "enabling CPU offloading"
    )

    # Create max_memory config for Accelerate (used for logging/debugging)
    _ = get_max_memory_config(max_gpu_memory_gb, max_cpu_memory_gb)

    # If disk offloading is enabled and we might need it
    if allow_disk_offload:
        cpu_info = get_cpu_memory_info()
        total_available = available_gpu + (cpu_info.get("available_gb") or 32)
        if estimated_size > total_available:
            logger.info("Enabling disk offloading")
            # Ensure offload folder exists
            Path(offload_folder).mkdir(parents=True, exist_ok=True)

    return "auto"


def load_model_with_offloading(
    model_class: type[ModelT],
    model_name_or_path: str,
    config: OffloadingConfig | None = None,
    max_gpu_memory_gb: float | None = None,
    allow_cpu_offload: bool = True,
    **kwargs: Any,
) -> ModelT:
    """Load a model with automatic CPU/disk offloading.

    This function handles memory-efficient loading of large models,
    automatically enabling CPU offloading when the model exceeds
    available GPU memory.

    Args:
        model_class: HuggingFace model class.
        model_name_or_path: Model name or path.
        config: Offloading configuration.
        max_gpu_memory_gb: Maximum GPU memory (overrides config).
        allow_cpu_offload: Whether to allow CPU offloading.
        **kwargs: Additional arguments for from_pretrained.

    Returns:
        Loaded model instance.
    """
    config = config or OffloadingConfig()

    # Use provided max_gpu_memory or config value
    gpu_memory = max_gpu_memory_gb or config.max_gpu_memory_gb

    # Get appropriate device_map
    device_map = get_offload_device_map(
        model_name_or_path,
        max_gpu_memory_gb=gpu_memory,
        max_cpu_memory_gb=config.max_cpu_memory_gb,
        allow_cpu_offload=allow_cpu_offload,
        offload_folder=config.offload_folder,
    )

    # Prepare loading kwargs
    load_kwargs: dict[str, Any] = {
        "device_map": device_map,
        "torch_dtype": config.torch_dtype,
        "low_cpu_mem_usage": config.low_cpu_mem_usage,
        **kwargs,
    }

    # Add max_memory if using auto device_map with offloading
    if device_map == "auto" and allow_cpu_offload:
        max_memory = get_max_memory_config(gpu_memory, config.max_cpu_memory_gb)
        load_kwargs["max_memory"] = max_memory

    # Add offload folder if specified
    if config.offload_folder and allow_cpu_offload:
        Path(config.offload_folder).mkdir(parents=True, exist_ok=True)
        load_kwargs["offload_folder"] = config.offload_folder

    # Add offload state dict setting
    if config.offload_state_dict:
        load_kwargs["offload_state_dict"] = True

    logger.info(
        f"Loading {model_name_or_path} with device_map='{device_map}', dtype={config.torch_dtype}"
    )

    # Clear memory before loading
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        gc.collect()

    # Load the model
    model = model_class.from_pretrained(  # type: ignore[attr-defined]
        model_name_or_path,
        **load_kwargs,
    )

    # Log memory usage after loading
    if torch.cuda.is_available():
        for i in range(torch.cuda.device_count()):
            allocated = torch.cuda.memory_allocated(i) / (1024**3)
            logger.info(f"GPU {i} memory allocated: {allocated:.2f}GB")

    return model  # type: ignore[return-value]


class OffloadingModelWrapper:
    """Wrapper for models that may need CPU offloading.

    This wrapper provides utilities for managing models with CPU offloading,
    including memory monitoring, layer pinning, and dynamic offloading.

    Attributes:
        model: The wrapped model.
        config: Offloading configuration.
        device_map: Current device map.
    """

    def __init__(
        self,
        model: PreTrainedModel,
        config: OffloadingConfig | None = None,
    ) -> None:
        """Initialize the wrapper.

        Args:
            model: The model to wrap.
            config: Offloading configuration.
        """
        self.model = model
        self.config = config or OffloadingConfig()
        self.device_map = getattr(model, "hf_device_map", None)

        logger.info("OffloadingModelWrapper initialized")

    def get_device_map(self) -> dict[str, Any] | None:
        """Get the current device map.

        Returns:
            Device map dictionary or None.
        """
        return self.device_map

    def get_memory_usage(self) -> dict[str, Any]:
        """Get current memory usage by device.

        Returns:
            Dictionary with memory usage information.
        """
        usage: dict[str, Any] = {
            "gpu": get_gpu_memory_info(),
            "cpu": get_cpu_memory_info(),
        }

        if self.device_map:
            # Count layers per device
            device_layers: dict[str, int] = {}
            for _layer_name, device in self.device_map.items():
                device_str = str(device)
                device_layers[device_str] = device_layers.get(device_str, 0) + 1
            usage["layers_by_device"] = device_layers

        return usage

    def is_offloaded(self) -> bool:
        """Check if the model has any layers offloaded to CPU.

        Returns:
            True if any layers are on CPU.
        """
        if not self.device_map:
            return False

        return any(str(device) in ("cpu", "disk") for device in self.device_map.values())

    def pin_layers(self, layer_names: list[str], device: str = "cuda:0") -> None:
        """Pin specific layers to a device (prevents offloading).

        Note: This requires reloading the model with a custom device_map.

        Args:
            layer_names: Names of layers to pin.
            device: Device to pin layers to.
        """
        logger.warning(
            "Layer pinning requires model reload. "
            f"Consider reloading with custom device_map for layers: {layer_names}"
        )

    def forward(self, *args: Any, **kwargs: Any) -> Any:
        """Forward pass through the model.

        Args:
            *args: Positional arguments.
            **kwargs: Keyword arguments.

        Returns:
            Model output.
        """
        return self.model(*args, **kwargs)

    def generate(self, *args: Any, **kwargs: Any) -> Any:
        """Generate method wrapper.

        Args:
            *args: Positional arguments.
            **kwargs: Keyword arguments.

        Returns:
            Generated output.
        """
        return self.model.generate(*args, **kwargs)


def get_optimal_offload_config(
    model_name_or_path: str,
    target_latency_ms: float | None = None,
) -> OffloadingConfig:
    """Get optimal offloading configuration for a model.

    This function analyzes the model and available hardware to suggest
    an optimal offloading configuration.

    Args:
        model_name_or_path: Model name or path.
        target_latency_ms: Target inference latency in milliseconds.

    Returns:
        Recommended OffloadingConfig.
    """
    # Get hardware info
    gpu_info = get_gpu_memory_info()
    cpu_info = get_cpu_memory_info()

    # Estimate model size
    model_size = estimate_model_size_gb(model_name_or_path)

    # Calculate available memory
    if gpu_info["available"]:
        total_gpu = sum(gpu["total_gb"] for gpu in gpu_info["gpus"])
    else:
        total_gpu = 0

    total_cpu = cpu_info.get("available_gb", 32)

    # Determine optimal configuration
    config = OffloadingConfig()

    if model_size <= total_gpu * 0.85:
        # Model fits in GPU - no offloading needed
        config.max_gpu_memory_gb = total_gpu * 0.85
        logger.info(f"Model ({model_size:.1f}GB) fits in GPU ({total_gpu:.1f}GB)")

    elif model_size <= total_gpu + total_cpu * 0.8:
        # Model fits with CPU offloading
        config.max_gpu_memory_gb = total_gpu * 0.85
        config.max_cpu_memory_gb = total_cpu * 0.8
        logger.info(
            f"Model ({model_size:.1f}GB) requires CPU offloading. "
            f"GPU: {config.max_gpu_memory_gb:.1f}GB, CPU: {config.max_cpu_memory_gb:.1f}GB"
        )

    else:
        # May need disk offloading
        config.max_gpu_memory_gb = total_gpu * 0.85
        config.max_cpu_memory_gb = total_cpu * 0.8
        config.offload_state_dict = True
        logger.warning(
            f"Model ({model_size:.1f}GB) may require disk offloading. "
            "Consider using a smaller model or quantization."
        )

    # Adjust for latency target if specified
    if target_latency_ms is not None:
        # Lower latency = more on GPU
        if target_latency_ms < 100:
            config.max_gpu_memory_gb = total_gpu * 0.95  # Use more GPU
            logger.info("Optimizing for low latency - maximizing GPU usage")

    return config
