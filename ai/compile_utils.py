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


def setup_compile_cache(cache_dir: str | None = None) -> str:
    """Configure torch.compile() cache directory for faster subsequent loads.

    The compilation cache stores compiled artifacts to avoid recompilation
    on subsequent runs. This significantly reduces startup time (from minutes
    to seconds) when using the same model and input shapes.

    Args:
        cache_dir: Directory for compilation cache. If None, reads from
                  TORCH_COMPILE_CACHE_DIR env var or uses system temp.

    Returns:
        The configured cache directory path.
    """
    import tempfile
    from pathlib import Path

    if cache_dir is None:
        cache_dir = os.environ.get(
            "TORCH_COMPILE_CACHE_DIR",
            str(Path(tempfile.gettempdir()) / "torch_compile_cache"),
        )

    # Set the inductor cache directory
    os.environ["TORCHINDUCTOR_CACHE_DIR"] = cache_dir

    # Also set the general torch dynamo cache
    os.environ["TORCH_COMPILE_DEBUG_DIR"] = str(Path(cache_dir) / "debug")

    # Create cache directory if it doesn't exist
    Path(cache_dir).mkdir(parents=True, exist_ok=True)

    logger.info(f"torch.compile() cache directory: {cache_dir}")
    return cache_dir


def benchmark_compile_modes(
    model: torch.nn.Module,
    sample_input: torch.Tensor | dict[str, torch.Tensor],
    num_iterations: int = 100,
    num_warmup: int = 10,
) -> dict[str, dict[str, float]]:
    """Benchmark different torch.compile() modes to find optimal configuration.

    Compares inference latency across different compilation modes:
    - eager: No compilation (baseline)
    - default: Standard compilation
    - reduce-overhead: Optimized for inference latency
    - max-autotune: Maximum autotuning for best throughput

    Args:
        model: PyTorch model to benchmark
        sample_input: Sample input tensor or dict of tensors
        num_iterations: Number of benchmark iterations (default: 100)
        num_warmup: Number of warmup iterations before timing (default: 10)

    Returns:
        Dict mapping mode names to latency statistics:
        {
            "eager": {"mean_ms": X, "std_ms": Y, "min_ms": Z, "max_ms": W},
            "default": {...},
            "reduce-overhead": {...},
            "max-autotune": {...},
        }
    """
    import copy
    import statistics
    import time

    if not is_compile_available():
        logger.warning("torch.compile() not available, cannot benchmark modes")
        return {}

    results: dict[str, dict[str, float]] = {}

    modes = [
        ("eager", None),  # No compilation
        ("default", CompileMode.DEFAULT),
        ("reduce-overhead", CompileMode.REDUCE_OVERHEAD),
        ("max-autotune", CompileMode.MAX_AUTOTUNE),
    ]

    for mode_name, mode in modes:
        logger.info(f"Benchmarking mode: {mode_name}")

        # Create fresh model copy for each mode
        test_model = copy.deepcopy(model)
        test_model.eval()

        # Apply compilation if not eager mode
        if mode is not None:
            config = CompileConfig(
                enabled=True,
                mode=mode,
                backend=CompileBackend.INDUCTOR,
                fullgraph=False,
                dynamic=True,
            )
            test_model = compile_model(
                test_model, config=config, model_name=f"benchmark-{mode_name}"
            )

        # Warmup
        logger.debug(f"Warming up {mode_name} mode...")
        test_model.eval()
        with torch.no_grad():
            for _ in range(num_warmup):
                if isinstance(sample_input, dict):
                    _ = test_model(**sample_input)
                else:
                    _ = test_model(sample_input)

        # Synchronize CUDA before timing
        if torch.cuda.is_available():
            torch.cuda.synchronize()

        # Benchmark
        latencies = []
        with torch.no_grad():
            for _ in range(num_iterations):
                start = time.perf_counter()
                if isinstance(sample_input, dict):
                    _ = test_model(**sample_input)
                else:
                    _ = test_model(sample_input)

                # Synchronize CUDA for accurate timing
                if torch.cuda.is_available():
                    torch.cuda.synchronize()

                elapsed_ms = (time.perf_counter() - start) * 1000
                latencies.append(elapsed_ms)

        # Calculate statistics
        results[mode_name] = {
            "mean_ms": statistics.mean(latencies),
            "std_ms": statistics.stdev(latencies) if len(latencies) > 1 else 0.0,
            "min_ms": min(latencies),
            "max_ms": max(latencies),
            "p50_ms": statistics.median(latencies),
            "p95_ms": sorted(latencies)[int(len(latencies) * 0.95)],
        }

        logger.info(
            f"  {mode_name}: mean={results[mode_name]['mean_ms']:.2f}ms, "
            f"p50={results[mode_name]['p50_ms']:.2f}ms, "
            f"p95={results[mode_name]['p95_ms']:.2f}ms"
        )

        # Cleanup
        del test_model
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    # Log speedup summary
    if "eager" in results and len(results) > 1:
        eager_mean = results["eager"]["mean_ms"]
        logger.info("\nSpeedup summary vs eager baseline:")
        for mode_name, stats in results.items():
            if mode_name != "eager":
                speedup = eager_mean / stats["mean_ms"]
                logger.info(f"  {mode_name}: {speedup:.2f}x speedup")

    return results
