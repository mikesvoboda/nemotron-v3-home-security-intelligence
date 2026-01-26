"""Pipeline Warmup Utilities for AI Services (NEM-3816).

This module provides standardized warmup functionality for AI inference pipelines
to eliminate first-request latency. Warmup is critical for:
1. CUDA kernel compilation and caching
2. Memory allocation and buffer initialization
3. Model weight loading into GPU memory
4. torch.compile() JIT compilation (if enabled)

Usage:
    from warmup_utils import (
        warmup_pipeline,
        warmup_vision_model,
        warmup_text_model,
        WarmupConfig,
    )

    # Vision model warmup (detection, classification)
    await warmup_vision_model(model, processor, device="cuda:0")

    # Pipeline-based warmup (HuggingFace pipelines)
    await warmup_pipeline(pipeline, warmup_samples=3)

    # Custom warmup with configuration
    config = WarmupConfig(num_samples=5, clear_cache_after=True)
    await warmup_pipeline(pipeline, config=config)

References:
    - NEM-3816: Add Pipeline Warmup on Startup
    - https://pytorch.org/docs/stable/notes/cuda.html#cuda-semantics
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

import torch
from PIL import Image

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)


@dataclass
class WarmupConfig:
    """Configuration for model warmup.

    Attributes:
        num_samples: Number of warmup iterations to run.
        clear_cache_after: Whether to clear CUDA cache after warmup.
        sync_cuda: Whether to synchronize CUDA after each iteration.
        input_text: Default text input for text-based models.
        input_image_size: Size of dummy input image (width, height).
        max_new_tokens: Max tokens for text generation models.
        log_timing: Whether to log timing information.
        timeout_seconds: Maximum time for warmup (0 = no timeout).
    """

    num_samples: int = 3
    clear_cache_after: bool = True
    sync_cuda: bool = True
    input_text: str = "Warmup text for model initialization."
    input_image_size: tuple[int, int] = (640, 480)
    max_new_tokens: int = 10
    log_timing: bool = True
    timeout_seconds: float = 60.0


@dataclass
class WarmupResult:
    """Result of a warmup operation.

    Attributes:
        success: Whether warmup completed successfully.
        iterations_completed: Number of successful warmup iterations.
        total_time_ms: Total warmup time in milliseconds.
        avg_time_ms: Average time per iteration in milliseconds.
        errors: List of errors encountered during warmup.
    """

    success: bool
    iterations_completed: int
    total_time_ms: float
    avg_time_ms: float
    errors: list[str] = field(default_factory=list)


@runtime_checkable
class TransformersPipeline(Protocol):
    """Protocol for HuggingFace Transformers pipeline-like objects."""

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Run inference on the pipeline."""
        ...


@runtime_checkable
class VisionModel(Protocol):
    """Protocol for vision models with inference methods."""

    def eval(self) -> Any:
        """Set model to evaluation mode."""
        ...


def _create_dummy_image(size: tuple[int, int] = (640, 480)) -> Image.Image:
    """Create a dummy RGB image for warmup.

    Args:
        size: Image dimensions (width, height).

    Returns:
        PIL Image with random-like pattern for realistic warmup.
    """
    # Use a gray image with slight variation to simulate real input
    return Image.new("RGB", size, color=(128, 128, 128))


def _clear_cuda_cache() -> None:
    """Clear CUDA cache to free up memory after warmup."""
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        logger.debug("CUDA cache cleared after warmup")


def _sync_cuda() -> None:
    """Synchronize CUDA to ensure all operations are complete."""
    if torch.cuda.is_available():
        torch.cuda.synchronize()


async def warmup_pipeline(
    pipeline: TransformersPipeline | Callable[..., Any],
    config: WarmupConfig | None = None,
    input_text: str | None = None,
) -> WarmupResult:
    """Warm up a text-based inference pipeline (NEM-3816).

    Runs multiple warmup iterations to:
    - Compile CUDA kernels
    - Initialize memory allocations
    - Trigger torch.compile() JIT compilation

    Args:
        pipeline: HuggingFace pipeline or callable that accepts text input.
        config: Warmup configuration. Uses defaults if not provided.
        input_text: Override input text for warmup.

    Returns:
        WarmupResult with timing and status information.

    Example:
        >>> from transformers import pipeline
        >>> text_gen = pipeline("text-generation", model="...")
        >>> result = await warmup_pipeline(text_gen, warmup_samples=3)
        >>> print(f"Warmup completed in {result.total_time_ms:.0f}ms")
    """
    config = config or WarmupConfig()
    text = input_text or config.input_text

    logger.info(f"Starting pipeline warmup with {config.num_samples} iterations")

    errors: list[str] = []
    iteration_times: list[float] = []
    start_time = time.perf_counter()

    for i in range(config.num_samples):
        iteration_start = time.perf_counter()
        try:
            # Run inference in thread pool to avoid blocking event loop
            with torch.no_grad():
                # Handle both pipeline and regular callable
                await asyncio.to_thread(
                    pipeline,
                    text,
                    max_new_tokens=config.max_new_tokens,
                )

            if config.sync_cuda:
                _sync_cuda()

            iteration_ms = (time.perf_counter() - iteration_start) * 1000
            iteration_times.append(iteration_ms)

            if config.log_timing:
                logger.info(
                    f"Warmup iteration {i + 1}/{config.num_samples} complete ({iteration_ms:.1f}ms)"
                )

        except Exception as e:
            error_msg = f"Warmup iteration {i + 1} failed: {e}"
            errors.append(error_msg)
            logger.warning(error_msg)

        # Check timeout
        elapsed = time.perf_counter() - start_time
        if config.timeout_seconds > 0 and elapsed > config.timeout_seconds:
            logger.warning(f"Warmup timeout after {elapsed:.1f}s")
            break

    # Clear cache after warmup
    if config.clear_cache_after:
        _sync_cuda()
        _clear_cuda_cache()

    total_ms = (time.perf_counter() - start_time) * 1000
    avg_ms = sum(iteration_times) / len(iteration_times) if iteration_times else 0

    result = WarmupResult(
        success=len(errors) == 0,
        iterations_completed=len(iteration_times),
        total_time_ms=total_ms,
        avg_time_ms=avg_ms,
        errors=errors,
    )

    if result.success:
        logger.info(
            f"Pipeline warmup complete: {result.iterations_completed} iterations "
            f"in {result.total_time_ms:.0f}ms (avg {result.avg_time_ms:.1f}ms/iter)"
        )
    else:
        logger.warning(
            f"Pipeline warmup completed with {len(errors)} errors: "
            f"{result.iterations_completed}/{config.num_samples} successful"
        )

    return result


async def warmup_vision_model(
    model: Any,
    processor: Any | None = None,
    device: str = "cuda:0",
    config: WarmupConfig | None = None,
    inference_fn: Callable[[Any, Image.Image], Any] | None = None,
) -> WarmupResult:
    """Warm up a vision model with dummy images (NEM-3816).

    Runs multiple warmup iterations with dummy images to:
    - Compile CUDA kernels for image processing
    - Initialize memory allocations for typical input sizes
    - Trigger torch.compile() JIT compilation

    Args:
        model: Vision model (PyTorch nn.Module or similar).
        processor: Optional image processor (for HuggingFace models).
        device: Target device for tensors.
        config: Warmup configuration. Uses defaults if not provided.
        inference_fn: Custom inference function. If None, uses default flow.

    Returns:
        WarmupResult with timing and status information.

    Example:
        >>> model = AutoModelForObjectDetection.from_pretrained(...)
        >>> processor = AutoImageProcessor.from_pretrained(...)
        >>> result = await warmup_vision_model(model, processor)
    """
    config = config or WarmupConfig()

    logger.info(f"Starting vision model warmup with {config.num_samples} iterations")

    errors: list[str] = []
    iteration_times: list[float] = []
    start_time = time.perf_counter()

    # Create dummy image
    dummy_image = _create_dummy_image(config.input_image_size)

    for i in range(config.num_samples):
        iteration_start = time.perf_counter()
        try:
            if inference_fn is not None:
                # Use custom inference function
                await asyncio.to_thread(inference_fn, model, dummy_image)
            elif processor is not None:
                # HuggingFace Transformers style

                def _run_hf_inference() -> None:
                    with torch.inference_mode():
                        inputs = processor(images=dummy_image, return_tensors="pt")
                        # Move inputs to device
                        if "cuda" in device:
                            model_dtype = next(model.parameters()).dtype
                            inputs = {k: v.to(device, model_dtype) for k, v in inputs.items()}
                        _ = model(**inputs)

                await asyncio.to_thread(_run_hf_inference)
            else:
                # Direct model call (assumes model accepts PIL image or tensor)

                def _run_direct_inference() -> None:
                    with torch.inference_mode():
                        if hasattr(model, "forward"):
                            # Assume it needs a tensor
                            from torchvision import transforms

                            transform = transforms.Compose(
                                [
                                    transforms.ToTensor(),
                                    transforms.Normalize(
                                        [0.485, 0.456, 0.406], [0.229, 0.224, 0.225]
                                    ),
                                ]
                            )
                            tensor = transform(dummy_image).unsqueeze(0)
                            if "cuda" in device:
                                tensor = tensor.to(device)
                            _ = model(tensor)
                        else:
                            # Try calling directly
                            _ = model(dummy_image)

                await asyncio.to_thread(_run_direct_inference)

            if config.sync_cuda:
                _sync_cuda()

            iteration_ms = (time.perf_counter() - iteration_start) * 1000
            iteration_times.append(iteration_ms)

            if config.log_timing:
                logger.info(
                    f"Warmup iteration {i + 1}/{config.num_samples} complete ({iteration_ms:.1f}ms)"
                )

        except Exception as e:
            error_msg = f"Warmup iteration {i + 1} failed: {e}"
            errors.append(error_msg)
            logger.warning(error_msg)

        # Check timeout
        elapsed = time.perf_counter() - start_time
        if config.timeout_seconds > 0 and elapsed > config.timeout_seconds:
            logger.warning(f"Warmup timeout after {elapsed:.1f}s")
            break

    # Clear cache after warmup
    if config.clear_cache_after:
        _sync_cuda()
        _clear_cuda_cache()

    total_ms = (time.perf_counter() - start_time) * 1000
    avg_ms = sum(iteration_times) / len(iteration_times) if iteration_times else 0

    result = WarmupResult(
        success=len(errors) == 0,
        iterations_completed=len(iteration_times),
        total_time_ms=total_ms,
        avg_time_ms=avg_ms,
        errors=errors,
    )

    if result.success:
        logger.info(
            f"Vision model warmup complete: {result.iterations_completed} iterations "
            f"in {result.total_time_ms:.0f}ms (avg {result.avg_time_ms:.1f}ms/iter)"
        )
    else:
        logger.warning(
            f"Vision model warmup completed with {len(errors)} errors: "
            f"{result.iterations_completed}/{config.num_samples} successful"
        )

    return result


def warmup_model_sync(
    model: Any,
    warmup_fn: Callable[[Any], Any],
    num_samples: int = 3,
    clear_cache_after: bool = True,
) -> WarmupResult:
    """Synchronous warmup for models that don't support async (NEM-3816).

    This is a simpler synchronous version for use in model initialization
    where async is not available (e.g., in __init__ or load_model methods).

    Args:
        model: The model to warm up.
        warmup_fn: Function that runs a single inference iteration.
                   Should accept the model and return any result.
        num_samples: Number of warmup iterations.
        clear_cache_after: Whether to clear CUDA cache after warmup.

    Returns:
        WarmupResult with timing and status information.

    Example:
        >>> def warmup_fn(model):
        ...     with torch.no_grad():
        ...         return model(dummy_input)
        >>> result = warmup_model_sync(model, warmup_fn, num_samples=3)
    """
    logger.info(f"Starting synchronous warmup with {num_samples} iterations")

    errors: list[str] = []
    iteration_times: list[float] = []
    start_time = time.perf_counter()

    for i in range(num_samples):
        iteration_start = time.perf_counter()
        try:
            with torch.no_grad():
                _ = warmup_fn(model)

            _sync_cuda()

            iteration_ms = (time.perf_counter() - iteration_start) * 1000
            iteration_times.append(iteration_ms)
            logger.info(f"Warmup iteration {i + 1}/{num_samples} complete ({iteration_ms:.1f}ms)")

        except Exception as e:
            error_msg = f"Warmup iteration {i + 1} failed: {e}"
            errors.append(error_msg)
            logger.warning(error_msg)

    # Clear cache after warmup
    if clear_cache_after:
        _sync_cuda()
        _clear_cuda_cache()

    total_ms = (time.perf_counter() - start_time) * 1000
    avg_ms = sum(iteration_times) / len(iteration_times) if iteration_times else 0

    result = WarmupResult(
        success=len(errors) == 0,
        iterations_completed=len(iteration_times),
        total_time_ms=total_ms,
        avg_time_ms=avg_ms,
        errors=errors,
    )

    logger.info(
        f"Warmup complete: {result.iterations_completed}/{num_samples} successful "
        f"in {result.total_time_ms:.0f}ms"
    )

    return result
