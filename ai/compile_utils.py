"""Torch Compile Utilities for Model Optimization.

This module provides utilities for applying torch.compile() to AI models
for improved inference performance. Supports PyTorch 2.0+ compilation
with automatic fallback for incompatible operations.

Key features:
- Automatic backend selection (inductor, cudagraphs, eager)
- Compilation caching for faster subsequent loads
- Safe fallback when compilation fails
- Mode selection for latency vs throughput optimization

Environment Variables:
- TORCH_COMPILE_ENABLED: Enable/disable compilation (default: "true")
- TORCH_COMPILE_MODE: Compilation mode (default: "reduce-overhead")
  Options: "default", "reduce-overhead", "max-autotune"
- TORCH_COMPILE_BACKEND: Backend to use (default: "inductor")
  Options: "inductor", "cudagraphs", "eager", "aot_eager"
- TORCH_COMPILE_CACHE_DIR: Directory for compilation cache

Usage:
    from compile_utils import compile_model, CompileConfig

    # Simple usage with defaults
    model = compile_model(model)

    # Custom configuration
    config = CompileConfig(mode="max-autotune", backend="inductor")
    model = compile_model(model, config=config)

References:
- PyTorch Compile: https://pytorch.org/docs/stable/torch.compiler.html
- Inductor Backend: https://pytorch.org/docs/stable/torch.compiler_inductor.html
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import torch

logger = logging.getLogger(__name__)


class CompileMode(str, Enum):
    """torch.compile() mode options.

    - DEFAULT: Balanced performance and compilation time
    - REDUCE_OVERHEAD: Optimized for reducing Python overhead (good for inference)
    - MAX_AUTOTUNE: Maximum autotuning for best performance (longer compile time)
    """

    DEFAULT = "default"
    REDUCE_OVERHEAD = "reduce-overhead"
    MAX_AUTOTUNE = "max-autotune"


class CompileBackend(str, Enum):
    """torch.compile() backend options.

    - INDUCTOR: TorchInductor (default, best general performance)
    - CUDAGRAPHS: CUDA Graphs for reduced kernel launch overhead
    - EAGER: No compilation (for debugging)
    - AOT_EAGER: Ahead-of-time tracing without compilation
    """

    INDUCTOR = "inductor"
    CUDAGRAPHS = "cudagraphs"
    EAGER = "eager"
    AOT_EAGER = "aot_eager"


@dataclass
class CompileConfig:
    """Configuration for torch.compile().

    Attributes:
        enabled: Whether to enable compilation
        mode: Compilation mode (default, reduce-overhead, max-autotune)
        backend: Compilation backend (inductor, cudagraphs, etc.)
        fullgraph: Whether to compile the full graph (stricter, faster)
        dynamic: Whether to enable dynamic shape support
        options: Additional backend-specific options
    """

    enabled: bool = True
    mode: CompileMode | str = CompileMode.REDUCE_OVERHEAD
    backend: CompileBackend | str = CompileBackend.INDUCTOR
    fullgraph: bool = False
    dynamic: bool = False
    options: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> CompileConfig:
        """Create CompileConfig from environment variables.

        Reads:
        - TORCH_COMPILE_ENABLED: "true" or "false"
        - TORCH_COMPILE_MODE: mode string
        - TORCH_COMPILE_BACKEND: backend string
        - TORCH_COMPILE_FULLGRAPH: "true" or "false"
        - TORCH_COMPILE_DYNAMIC: "true" or "false"
        """
        enabled = os.environ.get("TORCH_COMPILE_ENABLED", "true").lower() == "true"
        mode = os.environ.get("TORCH_COMPILE_MODE", CompileMode.REDUCE_OVERHEAD.value)
        backend = os.environ.get("TORCH_COMPILE_BACKEND", CompileBackend.INDUCTOR.value)
        fullgraph = os.environ.get("TORCH_COMPILE_FULLGRAPH", "false").lower() == "true"
        dynamic = os.environ.get("TORCH_COMPILE_DYNAMIC", "false").lower() == "true"

        return cls(
            enabled=enabled,
            mode=mode,
            backend=backend,
            fullgraph=fullgraph,
            dynamic=dynamic,
        )


def is_compile_available() -> bool:
    """Check if torch.compile() is available.

    Returns:
        True if PyTorch version supports torch.compile() (2.0+)
    """
    # torch.compile requires PyTorch 2.0+
    version_parts = torch.__version__.split(".")
    try:
        major = int(version_parts[0])
        return major >= 2
    except (ValueError, IndexError):
        logger.warning(f"Could not parse PyTorch version: {torch.__version__}")
        return False


def compile_model(
    model: torch.nn.Module,
    config: CompileConfig | None = None,
    model_name: str | None = None,
) -> torch.nn.Module:
    """Apply torch.compile() to a model with safe fallback.

    This function wraps torch.compile() with:
    - Version checking (requires PyTorch 2.0+)
    - Automatic fallback on compilation errors
    - Logging for debugging compilation issues

    Args:
        model: PyTorch model to compile
        config: Compilation configuration (uses env vars if None)
        model_name: Optional model name for logging

    Returns:
        Compiled model if successful, original model otherwise
    """
    if config is None:
        config = CompileConfig.from_env()

    name = model_name or model.__class__.__name__

    # Check if compilation is enabled
    if not config.enabled:
        logger.debug(f"torch.compile() disabled for {name}")
        return model

    # Check PyTorch version
    if not is_compile_available():
        logger.warning(
            f"torch.compile() not available (requires PyTorch 2.0+). "
            f"Current version: {torch.__version__}. Skipping compilation for {name}."
        )
        return model

    # Resolve mode and backend to string values
    mode = config.mode.value if isinstance(config.mode, CompileMode) else config.mode
    backend = config.backend.value if isinstance(config.backend, CompileBackend) else config.backend

    logger.info(
        f"Compiling {name} with torch.compile() "
        f"(mode={mode}, backend={backend}, fullgraph={config.fullgraph})"
    )

    try:
        compiled_model = torch.compile(
            model,
            mode=mode,
            backend=backend,
            fullgraph=config.fullgraph,
            dynamic=config.dynamic,
            options=config.options if config.options else None,
        )
        logger.info(f"Successfully compiled {name}")
        return compiled_model  # type: ignore[return-value]

    except Exception as e:
        logger.warning(
            f"Failed to compile {name} with torch.compile(): {e}. Falling back to eager execution."
        )
        return model


def compile_for_inference(
    model: torch.nn.Module,
    model_name: str | None = None,
) -> torch.nn.Module:
    """Compile a model optimized for inference.

    Uses reduce-overhead mode which is optimized for:
    - Low latency inference
    - Reduced Python overhead
    - Good for real-time applications

    Args:
        model: PyTorch model to compile
        model_name: Optional model name for logging

    Returns:
        Compiled model optimized for inference
    """
    config = CompileConfig(
        enabled=True,
        mode=CompileMode.REDUCE_OVERHEAD,
        backend=CompileBackend.INDUCTOR,
        fullgraph=False,
        dynamic=False,
    )
    return compile_model(model, config=config, model_name=model_name)


def compile_for_throughput(
    model: torch.nn.Module,
    model_name: str | None = None,
) -> torch.nn.Module:
    """Compile a model optimized for throughput.

    Uses max-autotune mode which:
    - Performs extensive autotuning
    - Longer compilation time
    - Best for batch processing

    Args:
        model: PyTorch model to compile
        model_name: Optional model name for logging

    Returns:
        Compiled model optimized for throughput
    """
    config = CompileConfig(
        enabled=True,
        mode=CompileMode.MAX_AUTOTUNE,
        backend=CompileBackend.INDUCTOR,
        fullgraph=False,
        dynamic=True,  # Enable dynamic shapes for varying batch sizes
    )
    return compile_model(model, config=config, model_name=model_name)


def warmup_compiled_model(
    model: torch.nn.Module,
    sample_input: torch.Tensor | dict[str, torch.Tensor],
    num_warmup: int = 3,
) -> None:
    """Warmup a compiled model to trigger JIT compilation.

    The first inference after torch.compile() triggers actual compilation.
    This function runs a few warmup iterations to ensure the model is
    fully compiled before production use.

    Args:
        model: Compiled PyTorch model
        sample_input: Sample input tensor or dict of tensors
        num_warmup: Number of warmup iterations (default: 3)
    """
    logger.debug(f"Running {num_warmup} warmup iterations for compiled model")

    model.eval()
    with torch.no_grad():
        for i in range(num_warmup):
            _ = model(**sample_input) if isinstance(sample_input, dict) else model(sample_input)
            logger.debug(f"Warmup iteration {i + 1}/{num_warmup} complete")

    logger.debug("Compiled model warmup complete")
