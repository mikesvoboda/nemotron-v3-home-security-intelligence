"""TensorRT Pre-build Engine Validation Utilities (NEM-4999).

Shared utilities for validating pre-built TensorRT engines at container startup.
Used by YOLO26, CLIP, and enrichment-light services to check if a pre-built
engine matches the current GPU before loading it.

TensorRT engines are GPU-architecture-specific. An engine built on one GPU
(e.g., RTX A5500 / sm_86) will not work on a different architecture
(e.g., RTX A400 / sm_75). This module provides:

1. Engine metadata reading (from .metadata.json sidecar files)
2. GPU architecture matching (compare build-time vs runtime SM version)
3. Logging of match/mismatch status for diagnostics

Usage:
    from tensorrt_prebuild import validate_prebuilt_engine

    result = validate_prebuilt_engine("/path/to/model.engine")
    if result.is_valid:
        # Load the pre-built engine directly (fast startup)
        ...
    else:
        # Rebuild engine at runtime (slow startup, logged as warning)
        logger.warning(f"Pre-built engine invalid: {result.reason}")
        ...
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class EngineValidationResult:
    """Result of validating a pre-built TensorRT engine.

    Attributes:
        is_valid: True if the engine can be used on the current GPU.
        engine_path: Path to the engine file.
        reason: Human-readable explanation of the result.
        build_compute_cap: GPU compute capability the engine was built for.
        runtime_compute_cap: GPU compute capability of the current runtime GPU.
        build_trt_version: TensorRT version used to build the engine.
        runtime_trt_version: TensorRT version in the current runtime.
    """

    is_valid: bool
    engine_path: str
    reason: str
    build_compute_cap: str | None = None
    runtime_compute_cap: str | None = None
    build_trt_version: str | None = None
    runtime_trt_version: str | None = None


def get_runtime_compute_capability() -> str | None:
    """Get the compute capability of the current GPU.

    Returns:
        Compute capability string (e.g., '86'), or None if no GPU.
    """
    try:
        import torch

        if torch.cuda.is_available():
            props = torch.cuda.get_device_properties(0)
            return f"{props.major}{props.minor}"
    except Exception:
        return None
    return None


def get_runtime_tensorrt_version() -> str | None:
    """Get the TensorRT version in the current runtime.

    Returns:
        TensorRT version string, or None if not installed.
    """
    try:
        import tensorrt as trt

        return str(trt.__version__)
    except ImportError:
        return None


def read_engine_metadata(engine_path: str) -> dict | None:
    """Read the metadata sidecar file for a pre-built engine.

    Args:
        engine_path: Path to the TensorRT engine file.

    Returns:
        Metadata dict if found, None otherwise.
    """
    metadata_path = engine_path + ".metadata.json"
    try:
        if Path(metadata_path).exists():
            with open(Path(metadata_path).resolve()) as f:  # nosemgrep: path-traversal-open
                return json.load(f)
    except Exception as e:
        logger.debug(f"Failed to read engine metadata: {e}")
    return None


def validate_prebuilt_engine(engine_path: str) -> EngineValidationResult:
    """Validate that a pre-built TensorRT engine is compatible with the current GPU.

    Checks:
    1. Engine file exists
    2. Metadata sidecar file exists (indicates pre-built engine)
    3. GPU compute capability matches (sm_XX must be identical)
    4. TensorRT major version matches (optional, logs warning on mismatch)

    Args:
        engine_path: Path to the TensorRT engine file.

    Returns:
        EngineValidationResult with validation status and details.
    """
    # Check engine file exists
    if not Path(engine_path).exists():
        return EngineValidationResult(
            is_valid=False,
            engine_path=engine_path,
            reason=f"Engine file not found: {engine_path}",
        )

    # Read metadata
    metadata = read_engine_metadata(engine_path)
    if metadata is None:
        # No metadata means this is likely a runtime-built engine (not pre-built)
        # or an older engine without metadata. Treat as valid to preserve
        # backward compatibility with existing engines.
        logger.info(
            f"No metadata found for engine {engine_path}. "
            "Assuming runtime-built engine, skipping validation."
        )
        return EngineValidationResult(
            is_valid=True,
            engine_path=engine_path,
            reason="No metadata (assumed runtime-built, validation skipped)",
        )

    build_cc = metadata.get("compute_capability")
    build_trt = metadata.get("tensorrt_version")
    runtime_cc = get_runtime_compute_capability()
    runtime_trt = get_runtime_tensorrt_version()

    # Check GPU compute capability match
    if build_cc and runtime_cc and build_cc != runtime_cc:
        reason = (
            f"GPU architecture mismatch: engine built for sm_{build_cc} "
            f"but runtime GPU is sm_{runtime_cc}. "
            "Engine will be rebuilt at runtime."
        )
        logger.warning(reason)
        return EngineValidationResult(
            is_valid=False,
            engine_path=engine_path,
            reason=reason,
            build_compute_cap=build_cc,
            runtime_compute_cap=runtime_cc,
            build_trt_version=build_trt,
            runtime_trt_version=runtime_trt,
        )

    # Check TensorRT major version match (warn but don't fail)
    if build_trt and runtime_trt:
        build_major = build_trt.split(".")[0]
        runtime_major = runtime_trt.split(".")[0]
        if build_major != runtime_major:
            logger.warning(
                f"TensorRT major version mismatch: engine built with TRT {build_trt} "
                f"but runtime has TRT {runtime_trt}. Engine may need rebuild."
            )
            return EngineValidationResult(
                is_valid=False,
                engine_path=engine_path,
                reason=(
                    f"TensorRT version mismatch: built with {build_trt}, runtime is {runtime_trt}"
                ),
                build_compute_cap=build_cc,
                runtime_compute_cap=runtime_cc,
                build_trt_version=build_trt,
                runtime_trt_version=runtime_trt,
            )

    # All checks passed
    build_gpu = metadata.get("gpu_name", "unknown")
    build_time = metadata.get("build_time", "unknown")
    logger.info(
        f"Pre-built TensorRT engine validated: {engine_path} "
        f"(built on {build_gpu} at {build_time}, sm_{build_cc}, TRT {build_trt})"
    )

    return EngineValidationResult(
        is_valid=True,
        engine_path=engine_path,
        reason="Pre-built engine matches runtime GPU",
        build_compute_cap=build_cc,
        runtime_compute_cap=runtime_cc,
        build_trt_version=build_trt,
        runtime_trt_version=runtime_trt,
    )
