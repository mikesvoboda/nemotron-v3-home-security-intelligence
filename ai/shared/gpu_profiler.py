"""GPU Profiling utility for AI services.

Provides selective PyTorch profiling with export to Chrome trace format.
Enable by setting PYTORCH_PROFILE_ENABLED=true in your environment.

Usage:
    from ai.shared import gpu_profile, should_profile

    # Automatic sampling (respects PYTORCH_PROFILE_RATE)
    with gpu_profile("yolo26_inference", trace_id="abc123"):
        result = model(input_tensor)

    # Manual check
    if should_profile():
        # Profile this request
        pass

Environment Variables:
    PYTORCH_PROFILE_ENABLED: Enable/disable GPU profiling (default: "false")
    PYTORCH_PROFILE_RATE: Sample rate 0.0-1.0 (default: 0.05 = 5%)
    PYTORCH_PROFILE_DIR: Output directory for traces (default: "/tmp/profiles")

Viewing Traces:
    1. Copy trace files from container: podman cp ai-yolo26:/tmp/profiles ./profiles
    2. Open https://ui.perfetto.dev in Chrome
    3. Drag and drop the .json trace file
"""

from __future__ import annotations

import logging
import os
import random
import time
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

logger = logging.getLogger(__name__)

# Configuration from environment
PROFILE_SAMPLE_RATE = float(os.getenv("PYTORCH_PROFILE_RATE", "0.05"))
PROFILE_OUTPUT_DIR = Path(os.getenv("PYTORCH_PROFILE_DIR", "/tmp/profiles"))  # noqa: S108
PROFILE_ENABLED = os.getenv("PYTORCH_PROFILE_ENABLED", "false").lower() == "true"


def should_profile() -> bool:
    """Determine if this request should be profiled.

    Returns True if:
    1. PYTORCH_PROFILE_ENABLED is set to "true"
    2. CUDA is available (requires torch)
    3. Random sampling passes based on PYTORCH_PROFILE_RATE

    Returns:
        bool: True if this request should be profiled
    """
    if not PROFILE_ENABLED:
        return False

    try:
        import torch

        if not torch.cuda.is_available():
            return False
    except ImportError:
        return False

    # nosemgrep: insecure-random - Not security-sensitive; sampling for profiling
    return random.random() < PROFILE_SAMPLE_RATE  # noqa: S311


@contextmanager
def gpu_profile(
    name: str,
    trace_id: str | None = None,
    record_shapes: bool = True,
    profile_memory: bool = True,
) -> Generator[None]:
    """Context manager for GPU profiling.

    Profiles CUDA kernel timing, memory transfers, and tensor operations
    when conditions are met (enabled, CUDA available, sampling passes).
    Exports Chrome trace format for viewing in Perfetto UI.

    Args:
        name: Profile name (e.g., "yolo26_inference", "clip_embedding")
        trace_id: Optional trace ID for correlation with distributed tracing
        record_shapes: Record tensor shapes in profile (default: True)
        profile_memory: Track memory allocation (default: True)

    Yields:
        None

    Example:
        with gpu_profile("detection", trace_id=request_id):
            detections = model.detect(image)
    """
    if not should_profile():
        yield
        return

    try:
        import torch
    except ImportError:
        yield
        return

    PROFILE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    activities = [torch.profiler.ProfilerActivity.CPU]
    if torch.cuda.is_available():
        activities.append(torch.profiler.ProfilerActivity.CUDA)

    with torch.profiler.profile(
        activities=activities,
        record_shapes=record_shapes,
        profile_memory=profile_memory,
        with_stack=False,  # Too expensive for production
    ) as prof:
        yield

    # Export trace with timestamp and optional trace_id
    timestamp = int(time.time() * 1000)
    trace_suffix = f"_{trace_id}" if trace_id else ""
    filename = f"{name}{trace_suffix}_{timestamp}.json"
    output_path = PROFILE_OUTPUT_DIR / filename

    prof.export_chrome_trace(str(output_path))
    logger.info("GPU profile saved: %s", output_path)

    # Log summary of top CUDA operations
    try:
        summary = prof.key_averages().table(sort_by="cuda_time_total", row_limit=5)
        logger.info("GPU profile summary for %s:\n%s", name, summary)
    except Exception as e:
        # Don't fail if summary generation fails
        logger.debug("Could not generate profile summary: %s", e)
