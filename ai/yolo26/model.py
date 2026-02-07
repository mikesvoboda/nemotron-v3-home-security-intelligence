"""YOLO26 Inference Server

HTTP server wrapping YOLO26m TensorRT object detection model for home security monitoring.
Runs on NVIDIA CUDA with TensorRT acceleration for efficient inference on security camera images.

Uses Ultralytics YOLO for loading and running TensorRT engines.

Port: 8095 (configurable via PORT env var)
Expected VRAM: ~2GB

TensorRT Version Compatibility (NEM-3871):
    TensorRT engines are version-specific and may fail to load if created with
    a different TensorRT version than the runtime. This module automatically:
    - Detects TensorRT version mismatches on engine load
    - Deletes stale engine files when version mismatch detected
    - Rebuilds the engine from the source .pt file if available

    Environment Variables:
    - YOLO26_AUTO_REBUILD: Enable auto-rebuild on version mismatch (default: "true")
    - YOLO26_PT_MODEL_PATH: Path to .pt source model for rebuilding (default: derived from engine path)

torch.compile Support (NEM-3773):
    Set TORCH_COMPILE_ENABLED=true to enable PyTorch 2.0+ graph optimization.
    This provides 15-30% speedup with automatic kernel fusion.
    Note: torch.compile is only applied when using PyTorch models (.pt),
    not TensorRT engines (.engine) which are already optimized.

    Environment Variables:
    - TORCH_COMPILE_ENABLED: Enable compilation (default: "true")
    - TORCH_COMPILE_MODE: Mode ("default", "reduce-overhead", "max-autotune")
    - TORCH_COMPILE_BACKEND: Backend ("inductor", "cudagraphs", etc.)
    - TORCH_COMPILE_CACHE_DIR: Cache directory for compiled graphs
"""

import base64
import binascii
import io
import logging
import os
import re
import shutil
import sys
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import torch
from fastapi import FastAPI, File, HTTPException, UploadFile

# =============================================================================
# Pre-compiled Regex Patterns for TensorRT Error Detection (NEM-4517)
# =============================================================================
# These patterns are pre-compiled at module load time for O(1) matching
# instead of O(n) pattern list iteration on every error check.

# TensorRT version mismatch patterns (single compiled regex)
_TENSORRT_VERSION_MISMATCH_PATTERN = re.compile(
    r"|".join(
        re.escape(p)
        for p in [
            "older plan file",
            "newer plan file",
            "deserialization",
            "failed due to an old",
            "version mismatch",
            "incompatible",
            "exported with a different version",
            "deserializecudaengine",
        ]
    ),
    re.IGNORECASE,
)

# TensorRT fallback patterns (single compiled regex)
_TENSORRT_FALLBACK_PATTERN = re.compile(
    r"|".join(
        re.escape(p)
        for p in [
            # TensorRT not installed
            "tensorrt is not available",
            "no module named 'tensorrt'",
            "tensorrt library not found",
            # Engine loading failures
            "failed to load tensorrt",
            "failed to load engine",
            "cannot load tensorrt engine",
            # GPU architecture mismatch
            "no kernel image is available for execution",
            "cuda error: no kernel image",
            # File not found
            "engine file not found",
            "engine not found",
        ]
    ),
    re.IGNORECASE,
)
from fastapi.responses import JSONResponse, Response
from PIL import Image, UnidentifiedImageError
from prometheus_client import generate_latest
from pydantic import BaseModel, ConfigDict, Field

# Add ai directory to path for compile_utils import
_ai_dir = Path(__file__).parent.parent
if str(_ai_dir) not in sys.path:
    sys.path.insert(0, str(_ai_dir))

from compile_utils import CompileConfig, compile_model, is_compile_available
from gpu_oom_handler import (
    GPUOOMHandler,
    check_gpu_memory_health,
    check_memory_available,
)

# Import metrics from the metrics module
from metrics import (
    DETECTIONS_PER_IMAGE,
    GPU_MEMORY_USED_GB,
    GPU_POWER_WATTS,
    GPU_TEMPERATURE,
    GPU_UTILIZATION,
    INFERENCE_LATENCY_SECONDS,
    INFERENCE_REQUESTS_TOTAL,
    MODEL_LOADED,
    get_vram_usage_bytes,
    record_batch_size,
    record_detections,
    record_error,
    record_inference,
    update_vram_bytes,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# GPU OOM handler for this service (NEM-4996)
_oom_handler = GPUOOMHandler(service_name="yolo26")

# Security-relevant classes for home monitoring
# YOLO uses COCO class names - map to our security-relevant subset
SECURITY_CLASSES = {"person", "car", "truck", "dog", "cat", "bird", "bicycle", "motorcycle", "bus"}

# COCO class ID to name mapping for security-relevant classes
COCO_CLASSES = {
    0: "person",
    1: "bicycle",
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck",
    14: "bird",
    15: "cat",
    16: "dog",
}

# Class-specific confidence thresholds tuned for home security (NEM-4522)
# Asymmetric cost model: missing a person/threat is worse than a false positive.
# Enrichment pipeline filters false positives downstream, so we favor recall for
# high-priority classes (person, pets) and precision for high-FP classes (vehicles).
#
# Configurable via YOLO26_CLASS_THRESHOLDS env var (JSON dict).
# Any class not in the override dict falls back to these defaults.
_DEFAULT_CLASS_CONFIDENCE_THRESHOLDS: dict[str, float] = {
    "person": 0.45,  # Lower — catch potential threats; FPs filtered by enrichment
    "car": 0.70,  # Higher — reflections/shadows cause frequent false positives
    "truck": 0.70,  # Same rationale as car
    "bus": 0.70,  # Same rationale as car
    "motorcycle": 0.65,  # Medium — fewer shadow FPs than cars but still common
    "bicycle": 0.65,  # Medium-high — common false positives from shadows
    "dog": 0.55,  # Lower — household pets should be reliably detected
    "cat": 0.55,  # Lower — household pets should be reliably detected
    "bird": 0.55,  # Slightly above default — occasional motion FPs
}


def _load_class_confidence_thresholds() -> dict[str, float]:
    """Load class-specific confidence thresholds, with optional env var overrides.

    Reads YOLO26_CLASS_THRESHOLDS environment variable (JSON dict) and merges
    with defaults. Environment overrides take precedence.

    Returns:
        Merged dict of class name -> confidence threshold.
    """
    import json as _json

    thresholds = dict(_DEFAULT_CLASS_CONFIDENCE_THRESHOLDS)
    env_overrides = os.environ.get("YOLO26_CLASS_THRESHOLDS", "").strip()
    if env_overrides:
        try:
            overrides = _json.loads(env_overrides)
            if isinstance(overrides, dict):
                for cls_name, value in overrides.items():
                    fval = float(value)
                    if 0.0 <= fval <= 1.0:
                        thresholds[cls_name] = fval
                    else:
                        logger.warning(f"Ignoring out-of-range threshold for {cls_name}: {fval}")
                logger.info(
                    f"Applied {len(overrides)} class threshold overrides from YOLO26_CLASS_THRESHOLDS"
                )
            else:
                logger.warning("YOLO26_CLASS_THRESHOLDS must be a JSON object, ignoring")
        except (ValueError, _json.JSONDecodeError) as e:
            logger.warning(f"Failed to parse YOLO26_CLASS_THRESHOLDS: {e}, using defaults")
    return thresholds


CLASS_CONFIDENCE_THRESHOLDS: dict[str, float] = _load_class_confidence_thresholds()

# TODO(NEM-future): Temporal confidence filtering / multi-frame consistency.
# For MARGINAL-tier detections (confidence < 0.60), require confirmation across
# N consecutive frames before accepting. This would further reduce false positives
# for low-threshold classes (person @ 0.45) without sacrificing recall for genuine
# detections that persist across frames. Implementation would require frame-level
# tracking state per camera (see FrameBuffer in backend/services/frame_buffer.py).

# Size limits for image uploads (10MB is reasonable for security camera images)
MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024  # 10MB
# Base64 encoding increases size by ~33%, so pre-decode limit is ~13.3MB
MAX_BASE64_SIZE_BYTES = int(MAX_IMAGE_SIZE_BYTES * 4 / 3) + 100  # ~13.3MB + padding

# Supported image file extensions (case-insensitive)
SUPPORTED_IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"})

# Magic bytes for image format detection
# These are the first few bytes that identify image file formats
IMAGE_MAGIC_BYTES: dict[bytes, str] = {
    b"\xff\xd8\xff": "JPEG",  # JPEG images
    b"\x89PNG\r\n\x1a\n": "PNG",  # PNG images
    b"GIF87a": "GIF",  # GIF87a
    b"GIF89a": "GIF",  # GIF89a
    b"BM": "BMP",  # BMP images
    b"RIFF": "WEBP",  # WEBP (RIFF container, need to check for WEBP)
}


def validate_image_magic_bytes(image_bytes: bytes) -> tuple[bool, str]:  # noqa: PLR0911
    """Validate image data by checking magic bytes (file signature).

    This provides an early check before passing to PIL, catching obvious
    non-image files like text files, videos, or corrupted data.

    Args:
        image_bytes: Raw image file bytes

    Returns:
        Tuple of (is_valid, detected_format_or_error_message)
    """
    if not image_bytes:
        return False, "Empty image data"

    if len(image_bytes) < 8:
        return False, "Image data too small to be a valid image"

    # Check for known image magic bytes
    for magic, fmt in IMAGE_MAGIC_BYTES.items():
        if image_bytes.startswith(magic):
            # Special case for WEBP: RIFF container must contain "WEBP"
            if fmt == "WEBP":
                if len(image_bytes) >= 12 and image_bytes[8:12] == b"WEBP":
                    return True, "WEBP"
                # It's a RIFF file but not WEBP (could be AVI, WAV, etc.)
                continue
            return True, fmt

    # Check for common non-image file signatures to provide better errors
    # Text files often start with common ASCII characters or BOM
    if image_bytes[:3] in (b"\xef\xbb\xbf", b"\xff\xfe", b"\xfe\xff"):  # UTF-8/16 BOM
        return False, "Text file (BOM detected), not an image"

    # Check if it looks like plain text (mostly printable ASCII)
    sample = image_bytes[:256]
    printable_count = sum(1 for b in sample if 32 <= b <= 126 or b in (9, 10, 13))
    if printable_count > len(sample) * 0.85:
        return False, "Text file detected, not an image"

    # Common video format signatures
    if image_bytes[:4] == b"\x00\x00\x00\x1c" or image_bytes[4:8] == b"ftyp":
        return False, "Video file (MP4/MOV), not an image"
    if image_bytes[:4] == b"\x1aE\xdf\xa3":  # EBML (Matroska/WebM)
        return False, "Video file (MKV/WebM), not an image"
    if image_bytes[:4] == b"RIFF" and len(image_bytes) >= 12:
        if image_bytes[8:12] == b"AVI ":
            return False, "Video file (AVI), not an image"
        if image_bytes[8:12] == b"WAVE":
            return False, "Audio file (WAV), not an image"

    return False, "Unknown file format, not a recognized image type"


def validate_file_extension(filename: str | None) -> tuple[bool, str]:
    """Validate that the file extension indicates an image file.

    Args:
        filename: The filename to check (can be None)

    Returns:
        Tuple of (is_valid, error_message_or_empty)
    """
    if not filename:
        return True, ""  # No filename to validate

    ext = Path(filename).suffix.lower()
    if not ext:
        return True, ""  # No extension to validate

    if ext not in SUPPORTED_IMAGE_EXTENSIONS:
        return False, (
            f"Unsupported file extension '{ext}'. "
            f"Supported formats: {', '.join(sorted(SUPPORTED_IMAGE_EXTENSIONS))}"
        )

    return True, ""


# =============================================================================
# TensorRT Version Checking Utilities (NEM-3871)
# =============================================================================


def get_tensorrt_version() -> str | None:
    """Get the installed TensorRT version.

    Returns:
        TensorRT version string (e.g., "10.14.1.48") or None if TensorRT is not installed.
    """
    try:
        import tensorrt as trt

        return str(trt.__version__)
    except ImportError:
        logger.debug("TensorRT not installed")
        return None
    except Exception as e:
        logger.warning(f"Error getting TensorRT version: {e}")
        return None


def is_tensorrt_version_mismatch_error(error: Exception) -> bool:
    """Check if an exception indicates a TensorRT version mismatch.

    Uses pre-compiled regex pattern for O(1) matching (NEM-4517).

    Args:
        error: The exception to check.

    Returns:
        True if the error indicates a TensorRT version mismatch, False otherwise.
    """
    return bool(_TENSORRT_VERSION_MISMATCH_PATTERN.search(str(error)))


def is_tensorrt_fallback_error(error: Exception) -> bool:
    """Check if an exception indicates TensorRT is unavailable and should fall back to PyTorch.

    Uses pre-compiled regex pattern for O(1) matching (NEM-4517).

    This function identifies errors that indicate TensorRT cannot be used, such as:
    - TensorRT not being installed
    - TensorRT library not found
    - Engine file not found
    - GPU architecture mismatch (kernel not available)
    - General TensorRT loading failures

    These are distinct from version mismatch errors (which may be resolvable by rebuild)
    and from resource errors like OOM (which indicate system issues, not TensorRT issues).

    Args:
        error: The exception to check.

    Returns:
        True if the error indicates TensorRT is unavailable and PyTorch fallback should be used.
    """
    # Check for fallback patterns using pre-compiled regex
    if _TENSORRT_FALLBACK_PATTERN.search(str(error)):
        return True

    # Also check if it's a FileNotFoundError for engine files
    return isinstance(error, FileNotFoundError)


def get_pt_model_path_for_engine(engine_path: str) -> str | None:
    """Derive the .pt model path from a TensorRT engine path.

    TensorRT engines are typically named like:
    - yolo26m_fp16.engine -> yolo26m.pt
    - yolo26m.engine -> yolo26m.pt

    Security (NEM-4511): All paths are validated to prevent path traversal
    attacks. Only paths within allowed model directories are returned.

    Args:
        engine_path: Path to the TensorRT engine file.

    Returns:
        Path to the corresponding .pt file if it exists and is valid, None otherwise.
    """
    from security import PathSecurityError, validate_model_path

    engine_path_obj = Path(engine_path)

    # Remove precision suffix if present (e.g., _fp16, _int8, _fp32)
    stem = engine_path_obj.stem
    stem = re.sub(r"_(fp16|fp32|int8)$", "", stem, flags=re.IGNORECASE)

    # Define candidate paths to check
    candidate_paths = [
        # Same directory
        engine_path_obj.parent / f"{stem}.pt",
        # Parent directory
        engine_path_obj.parent.parent / f"{stem}.pt",
        # Common model paths
        Path(f"/models/yolo26/{stem}.pt"),
        Path(f"/models/yolo26/exports/{stem}.pt"),
    ]

    for pt_path in candidate_paths:
        if not pt_path.exists():
            continue

        # Validate the path for security (NEM-4511)
        try:
            validated_path = validate_model_path(
                str(pt_path),
                allowed_extensions=frozenset({".pt", ".pth"}),
                must_exist=True,
            )
            logger.debug(f"Found valid .pt model path: {validated_path}")
            return str(validated_path)
        except PathSecurityError as e:
            logger.warning(f"Rejected unsafe model path {pt_path}: {e}")
            continue

    return None


def rebuild_tensorrt_engine(
    pt_model_path: str,
    engine_output_path: str,
    imgsz: int = 640,
    half: bool = True,
) -> bool:
    """Rebuild a TensorRT engine from a PyTorch model.

    NEM-4516: Uses file-based locking to prevent concurrent rebuilds from
    multiple processes. This prevents file corruption and wasted resources
    from duplicate rebuild operations.

    Args:
        pt_model_path: Path to the source PyTorch model (.pt file).
        engine_output_path: Path to write the rebuilt engine.
        imgsz: Image size for export (default: 640).
        half: Use FP16 precision (default: True).

    Returns:
        True if rebuild succeeded, False otherwise.
    """
    import fcntl

    try:
        from ultralytics import YOLO

        # NEM-4516: Acquire file lock to prevent concurrent rebuilds
        # The engine_output_path is already validated via validate_model_path
        lock_file_path = f"{engine_output_path}.lock"
        lock_file = None

        try:
            # Create lock file (path derived from validated engine_output_path)
            lock_file = open(lock_file_path, "w")  # noqa: SIM115 # nosemgrep: path-traversal-open

            # Try to acquire exclusive lock (non-blocking)
            # If another process is rebuilding, this will raise BlockingIOError
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

            # Double-check if engine exists after acquiring lock
            # Another process might have built it while we were waiting
            if Path(engine_output_path).exists():
                logger.info(
                    f"TensorRT engine already exists at {engine_output_path}, skipping rebuild"
                )
                return True

            logger.info(f"Rebuilding TensorRT engine from {pt_model_path}...")
            logger.info(f"  Output: {engine_output_path}")
            logger.info(f"  Image size: {imgsz}")
            logger.info(f"  FP16: {half}")

            # Load the PyTorch model
            model = YOLO(pt_model_path)

            # Export to TensorRT
            start_time = time.time()
            exported_path = model.export(
                format="engine",
                imgsz=imgsz,
                half=half,
                device=0 if torch.cuda.is_available() else "cpu",
                dynamic=False,
                simplify=True,
                workspace=4,  # 4GB workspace
            )
            export_time = time.time() - start_time

            # Move exported file to target location if needed
            exported_path_obj = Path(str(exported_path))
            target_path = Path(engine_output_path)

            if exported_path_obj != target_path:
                # Ensure parent directory exists
                target_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(exported_path_obj), str(target_path))

            logger.info(f"TensorRT engine rebuilt successfully in {export_time:.1f}s")
            trt_version = get_tensorrt_version()
            logger.info(f"Engine built with TensorRT version: {trt_version}")

            return True

        except BlockingIOError:
            # Another process is rebuilding, wait briefly and check if engine exists
            logger.info("Another process is rebuilding engine, waiting...")
            time.sleep(1)  # Brief wait
            if Path(engine_output_path).exists():
                logger.info("Engine rebuilt by another process")
                return True
            logger.warning("Engine rebuild in progress by another process, returning False")
            return False

        finally:
            # Release lock and clean up
            if lock_file is not None:
                try:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                    lock_file.close()
                    # Try to remove lock file
                    try:
                        Path(lock_file_path).unlink(missing_ok=True)
                    except Exception as cleanup_err:
                        logger.debug(f"Lock file cleanup failed: {cleanup_err}")
                except Exception as e:
                    logger.debug(f"Failed to release lock: {e}")

    except Exception as e:
        logger.error(f"Failed to rebuild TensorRT engine: {e}")
        return False


def delete_stale_engine(engine_path: str) -> bool:
    """Delete a stale TensorRT engine file.

    Security (NEM-4514): Validates that the path is within allowed directories
    and has an expected file extension before deletion. This prevents arbitrary
    file deletion through path manipulation.

    Args:
        engine_path: Path to the engine file to delete.

    Returns:
        True if deletion succeeded, False otherwise.
    """
    from security import is_safe_path_for_deletion

    try:
        # Validate path before deletion (NEM-4514)
        if not is_safe_path_for_deletion(
            engine_path,
            allowed_extensions=frozenset({".engine"}),
        ):
            logger.error(
                f"Refusing to delete file at unsafe path: {engine_path}. "
                "Path must be within allowed directories and have .engine extension."
            )
            return False

        engine_path_obj = Path(engine_path)
        if engine_path_obj.exists():
            engine_path_obj.unlink()
            logger.info(f"Deleted stale TensorRT engine: {engine_path}")
            return True
        return False
    except Exception as e:
        logger.error(f"Failed to delete stale engine {engine_path}: {e}")
        return False


class BoundingBox(BaseModel):
    """Bounding box coordinates."""

    x: int = Field(..., description="Top-left x coordinate")
    y: int = Field(..., description="Top-left y coordinate")
    width: int = Field(..., description="Box width")
    height: int = Field(..., description="Box height")


# =============================================================================
# Detection Confidence Quality Indicators (NEM-5502, NEM-5503, NEM-5504)
# =============================================================================
# These quality indicators help Nemotron distinguish between high-confidence
# and marginal detections, providing richer context for risk assessment.


from dataclasses import dataclass as python_dataclass
from enum import Enum


class ConfidenceQuality(str, Enum):
    """Quality tier for detection confidence scores.

    Provides semantic meaning to raw confidence values, helping the LLM
    understand the reliability of each detection.

    Tiers:
        EXCELLENT: >= 0.90 - Very high confidence, highly reliable
        GOOD: >= 0.75 - Solid detection, trustworthy
        MODERATE: >= 0.60 - Acceptable but verify with context
        MARGINAL: < 0.60 - Low confidence, treat with caution
    """

    EXCELLENT = "excellent"
    GOOD = "good"
    MODERATE = "moderate"
    MARGINAL = "marginal"


def compute_confidence_quality(confidence: float) -> ConfidenceQuality:
    """Compute the quality tier for a detection confidence score.

    Args:
        confidence: Detection confidence score between 0 and 1.

    Returns:
        ConfidenceQuality enum value indicating the quality tier.

    Examples:
        >>> compute_confidence_quality(0.95)
        <ConfidenceQuality.EXCELLENT: 'excellent'>
        >>> compute_confidence_quality(0.82)
        <ConfidenceQuality.GOOD: 'good'>
        >>> compute_confidence_quality(0.65)
        <ConfidenceQuality.MODERATE: 'moderate'>
        >>> compute_confidence_quality(0.45)
        <ConfidenceQuality.MARGINAL: 'marginal'>
    """
    if confidence >= 0.90:
        return ConfidenceQuality.EXCELLENT
    elif confidence >= 0.75:
        return ConfidenceQuality.GOOD
    elif confidence >= 0.60:
        return ConfidenceQuality.MODERATE
    else:
        return ConfidenceQuality.MARGINAL


def get_confidence_explanation(quality: ConfidenceQuality, confidence: float) -> str:
    """Generate a human-readable explanation of the confidence quality.

    Args:
        quality: The computed ConfidenceQuality tier.
        confidence: The raw confidence score.

    Returns:
        String explanation suitable for LLM prompt context.
    """
    explanations = {
        ConfidenceQuality.EXCELLENT: f"Very high confidence ({confidence:.0%}) - highly reliable detection",
        ConfidenceQuality.GOOD: f"Good confidence ({confidence:.0%}) - solid detection",
        ConfidenceQuality.MODERATE: f"Moderate confidence ({confidence:.0%}) - verify with visual context",
        ConfidenceQuality.MARGINAL: f"MARGINAL confidence ({confidence:.0%}) - treat with caution, may be false positive",
    }
    return explanations[quality]


@python_dataclass
class SpatialContext:
    """Spatial context for a detection within the frame.

    Provides information about where the detection is located in the frame
    and its relative size, which can indicate detection reliability.

    Attributes:
        relative_position: Position in frame as 9-grid (e.g., "top-left", "center")
        size_relative_to_frame: Detection area as fraction of frame area (0-1)
        is_at_boundary: True if detection bbox touches frame edge
        position_description: Human-readable position description
    """

    relative_position: str
    size_relative_to_frame: float
    is_at_boundary: bool
    position_description: str


def compute_spatial_context(
    bbox_x: int,
    bbox_y: int,
    bbox_width: int,
    bbox_height: int,
    frame_width: int,
    frame_height: int,
    boundary_threshold: int = 5,
) -> SpatialContext:
    """Compute spatial context for a detection bounding box.

    Analyzes where the detection is located within the frame and its
    relative size, providing context for detection reliability.

    Args:
        bbox_x: Top-left x coordinate of bounding box.
        bbox_y: Top-left y coordinate of bounding box.
        bbox_width: Width of bounding box.
        bbox_height: Height of bounding box.
        frame_width: Width of the frame/image.
        frame_height: Height of the frame/image.
        boundary_threshold: Pixels from edge to consider "at boundary".

    Returns:
        SpatialContext with position and size information.

    Examples:
        >>> ctx = compute_spatial_context(10, 10, 100, 200, 1920, 1080)
        >>> ctx.relative_position
        'top-left'
        >>> ctx.is_at_boundary
        False
    """
    # Calculate center of bounding box
    center_x = bbox_x + bbox_width / 2
    center_y = bbox_y + bbox_height / 2

    # Determine position in 9-grid
    x_third = frame_width / 3
    y_third = frame_height / 3

    if center_x < x_third:
        h_pos = "left"
    elif center_x < 2 * x_third:
        h_pos = "center"
    else:
        h_pos = "right"

    if center_y < y_third:
        v_pos = "top"
    elif center_y < 2 * y_third:
        v_pos = "middle"
    else:
        v_pos = "bottom"

    # Combine position
    if h_pos == "center" and v_pos == "middle":
        relative_position = "center"
    elif h_pos == "center":
        relative_position = v_pos
    elif v_pos == "middle":
        relative_position = h_pos
    else:
        relative_position = f"{v_pos}-{h_pos}"

    # Calculate size relative to frame
    bbox_area = bbox_width * bbox_height
    frame_area = frame_width * frame_height
    size_relative = bbox_area / frame_area if frame_area > 0 else 0.0

    # Check if at boundary
    is_at_boundary = (
        bbox_x <= boundary_threshold
        or bbox_y <= boundary_threshold
        or (bbox_x + bbox_width) >= (frame_width - boundary_threshold)
        or (bbox_y + bbox_height) >= (frame_height - boundary_threshold)
    )

    # Generate position description
    size_desc = "large" if size_relative >= 0.10 else "medium" if size_relative >= 0.02 else "small"
    boundary_note = " (at frame edge)" if is_at_boundary else ""
    position_description = f"{size_desc} object in {relative_position} of frame{boundary_note}"

    return SpatialContext(
        relative_position=relative_position,
        size_relative_to_frame=size_relative,
        is_at_boundary=is_at_boundary,
        position_description=position_description,
    )


@python_dataclass
class EnhancedDetection:
    """Enhanced detection with quality indicators and spatial context.

    Combines raw detection data with computed quality metrics to provide
    richer context for LLM-based risk assessment.

    Attributes:
        class_name: Detected object class (e.g., "person", "car").
        confidence: Raw confidence score (0-1).
        bbox: Bounding box as dict with x, y, width, height.
        confidence_quality: Computed quality tier.
        confidence_explanation: Human-readable confidence explanation.
        relative_position: Position in frame (9-grid).
        size_relative_to_frame: Detection size as fraction of frame.
        is_at_boundary: True if detection touches frame edge.
        spatial_description: Human-readable spatial description.
    """

    class_name: str
    confidence: float
    bbox: dict[str, int]
    confidence_quality: ConfidenceQuality
    confidence_explanation: str
    relative_position: str
    size_relative_to_frame: float
    is_at_boundary: bool
    spatial_description: str

    @classmethod
    def from_detection(
        cls,
        class_name: str,
        confidence: float,
        bbox: dict[str, int],
        frame_width: int,
        frame_height: int,
    ) -> EnhancedDetection:
        """Create an EnhancedDetection from raw detection data.

        Args:
            class_name: Detected object class.
            confidence: Detection confidence score (0-1).
            bbox: Bounding box dict with x, y, width, height keys.
            frame_width: Width of the frame/image.
            frame_height: Height of the frame/image.

        Returns:
            EnhancedDetection with computed quality indicators.
        """
        quality = compute_confidence_quality(confidence)
        explanation = get_confidence_explanation(quality, confidence)

        spatial = compute_spatial_context(
            bbox_x=bbox.get("x", 0),
            bbox_y=bbox.get("y", 0),
            bbox_width=bbox.get("width", 0),
            bbox_height=bbox.get("height", 0),
            frame_width=frame_width,
            frame_height=frame_height,
        )

        return cls(
            class_name=class_name,
            confidence=confidence,
            bbox=bbox,
            confidence_quality=quality,
            confidence_explanation=explanation,
            relative_position=spatial.relative_position,
            size_relative_to_frame=spatial.size_relative_to_frame,
            is_at_boundary=spatial.is_at_boundary,
            spatial_description=spatial.position_description,
        )

    def to_prompt_context(self) -> str:
        """Format detection for LLM prompt context.

        Returns:
            Multi-line string with detection details and quality indicators.
        """
        lines = [
            f"- {self.class_name.upper()}: {self.confidence_explanation}",
            f"  Position: {self.spatial_description}",
        ]

        # Add warning for marginal detections
        if self.confidence_quality == ConfidenceQuality.MARGINAL:
            lines.append("  WARNING: Low confidence detection - verify before acting")

        # Add warning for boundary detections
        if self.is_at_boundary:
            lines.append("  NOTE: Object at frame boundary - may be partially visible")

        return "\n".join(lines)


def enhance_detections(
    detections: list[dict[str, Any]],
    frame_width: int,
    frame_height: int,
) -> list[EnhancedDetection]:
    """Enhance a list of raw detections with quality indicators.

    Args:
        detections: List of detection dicts with class, confidence, bbox.
        frame_width: Width of the frame/image.
        frame_height: Height of the frame/image.

    Returns:
        List of EnhancedDetection objects with computed quality metrics.
    """
    enhanced = []
    for det in detections:
        class_name = det.get("class", det.get("class_name", "unknown"))
        confidence = det.get("confidence", 0.0)
        bbox = det.get("bbox", {"x": 0, "y": 0, "width": 0, "height": 0})

        # Handle bbox as dict or as BoundingBox model
        if hasattr(bbox, "model_dump"):
            bbox = bbox.model_dump()
        elif not isinstance(bbox, dict):
            bbox = {"x": 0, "y": 0, "width": 0, "height": 0}

        enhanced.append(
            EnhancedDetection.from_detection(
                class_name=class_name,
                confidence=confidence,
                bbox=bbox,
                frame_width=frame_width,
                frame_height=frame_height,
            )
        )

    return enhanced


class Detection(BaseModel):
    """Single object detection result."""

    model_config = ConfigDict(populate_by_name=True)

    class_name: str = Field(..., alias="class", description="Detected object class")
    confidence: float = Field(..., description="Detection confidence score (0-1)")
    bbox: BoundingBox = Field(..., description="Bounding box coordinates")


class TrackedDetection(BaseModel):
    """Single object detection result with tracking information."""

    model_config = ConfigDict(populate_by_name=True)

    class_name: str = Field(..., alias="class", description="Detected object class")
    confidence: float = Field(..., description="Detection confidence score (0-1)")
    bbox: BoundingBox = Field(..., description="Bounding box coordinates")
    track_id: int | None = Field(
        None, description="Unique track ID for object tracking (None if no track assigned yet)"
    )


class DetectionResponse(BaseModel):
    """Response format for detection endpoint."""

    detections: list[Detection] = Field(
        default_factory=list, description="List of detected objects"
    )
    inference_time_ms: float = Field(..., description="Inference time in milliseconds")
    image_width: int = Field(..., description="Original image width")
    image_height: int = Field(..., description="Original image height")


class TrackingResponse(BaseModel):
    """Response format for tracking endpoint."""

    detections: list[TrackedDetection] = Field(
        default_factory=list, description="List of tracked objects with track IDs"
    )
    inference_time_ms: float = Field(..., description="Inference time in milliseconds")
    image_width: int = Field(..., description="Original image width")
    image_height: int = Field(..., description="Original image height")


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    model_loaded: bool
    device: str
    cuda_available: bool
    model_name: str | None = None
    vram_used_gb: float | None = None
    gpu_utilization: float | None = None
    temperature: int | None = None
    power_watts: float | None = None
    tensorrt_enabled: bool | None = None
    tensorrt_version: str | None = None
    torch_compile_enabled: bool | None = None
    torch_compile_mode: str | None = None
    gpu_memory_health: str | None = None
    gpu_memory_allocated_mb: float | None = None
    gpu_memory_total_mb: float | None = None
    gpu_memory_utilization_pct: float | None = None
    gpu_memory_message: str | None = None


class YOLO26Model:
    """YOLO26 model wrapper using Ultralytics YOLO with TensorRT."""

    def __init__(
        self,
        model_path: str | Path,
        confidence_threshold: float = 0.5,
        device: str = "cuda:0",
        cache_clear_frequency: int = 1,
        enable_torch_compile: bool | None = None,
        torch_compile_mode: str | None = None,
        auto_rebuild: bool | None = None,
        pt_model_path: str | None = None,
    ):
        """Initialize YOLO26 model.

        Args:
            model_path: Path to TensorRT engine file (.engine) or PyTorch model (.pt)
            confidence_threshold: Minimum confidence for detections
            device: Device to run inference on (cuda:0, cpu)
            cache_clear_frequency: Clear CUDA cache every N detections.
                                   Set to 0 to disable cache clearing.
                                   Default is 1 (clear after every detection).
            enable_torch_compile: Enable torch.compile() for automatic kernel fusion (NEM-3773).
                                 If None, reads from TORCH_COMPILE_ENABLED env var.
                                 Note: Only applies to PyTorch models, not TensorRT engines.
            torch_compile_mode: Compilation mode ("default", "reduce-overhead", "max-autotune").
                               If None, reads from TORCH_COMPILE_MODE env var.
            auto_rebuild: Enable automatic TensorRT engine rebuild on version mismatch (NEM-3871).
                         If None, reads from YOLO26_AUTO_REBUILD env var (default: True).
            pt_model_path: Path to source .pt model for rebuilding TensorRT engines.
                          If None, reads from YOLO26_PT_MODEL_PATH env var or derives from engine path.
        """
        self.model_path = str(model_path)
        self.confidence_threshold = confidence_threshold
        self.device = device
        self.cache_clear_frequency = cache_clear_frequency
        self.cache_clear_count = 0  # Metric: total number of cache clears
        self.model: Any = None
        self.tensorrt_enabled = False

        # TensorRT auto-rebuild configuration (NEM-3871)
        if auto_rebuild is None:
            auto_rebuild = os.environ.get("YOLO26_AUTO_REBUILD", "true").lower() == "true"
        self.auto_rebuild = auto_rebuild

        if pt_model_path is None:
            pt_model_path = os.environ.get("YOLO26_PT_MODEL_PATH")
        self.pt_model_path = pt_model_path

        # torch.compile configuration (NEM-3773)
        if enable_torch_compile is None:
            enable_torch_compile = os.environ.get("TORCH_COMPILE_ENABLED", "true").lower() == "true"
        self.enable_torch_compile = enable_torch_compile

        if torch_compile_mode is None:
            torch_compile_mode = os.environ.get("TORCH_COMPILE_MODE", "reduce-overhead")
        self.torch_compile_mode = torch_compile_mode

        # torch.compile state
        self._is_compiled = False
        self._compile_config: CompileConfig | None = None

        logger.info(f"Initializing YOLO26 model from {self.model_path}")
        logger.info(f"Device: {device}, Confidence threshold: {confidence_threshold}")
        logger.info(f"CUDA cache clear frequency: {cache_clear_frequency}")
        logger.info(f"TensorRT auto-rebuild: {self.auto_rebuild}")
        logger.info(
            f"torch.compile enabled: {self.enable_torch_compile}, mode: {self.torch_compile_mode}"
        )
        # Log TensorRT version for diagnostics
        trt_version = get_tensorrt_version()
        if trt_version:
            logger.info(f"TensorRT runtime version: {trt_version}")

    def load_model(self) -> None:
        """Load the TensorRT model using Ultralytics YOLO.

        Handles TensorRT issues (NEM-3871, NEM-3882) by:
        1. Detecting version mismatch errors during engine load
        2. Deleting the stale engine file
        3. Rebuilding the engine from the source .pt file if available
        4. Falling back to the .pt model if rebuild fails or is disabled

        TensorRT to PyTorch fallback (NEM-3882):
        When TensorRT is unavailable or fails to load (not due to version mismatch),
        the service gracefully falls back to PyTorch:
        - TensorRT not installed
        - TensorRT library not found
        - Engine file not found
        - GPU architecture mismatch
        """
        try:
            logger.info("Loading YOLO26 TensorRT model with Ultralytics...")

            from ultralytics import YOLO

            # Attempt to load the model
            try:
                self.model = YOLO(self.model_path)
            except Exception as load_error:
                # Check if this is a TensorRT engine that failed to load
                if self.model_path.endswith(".engine"):
                    # Check if this is a version mismatch (may be recoverable via rebuild)
                    if is_tensorrt_version_mismatch_error(load_error):
                        logger.warning(f"TensorRT version mismatch detected: {load_error}")
                        trt_version = get_tensorrt_version()
                        logger.warning(f"Current TensorRT runtime version: {trt_version}")

                        # Attempt to rebuild if auto_rebuild is enabled
                        if self.auto_rebuild:
                            self._handle_tensorrt_version_mismatch()
                        else:
                            logger.error(
                                "TensorRT auto-rebuild is disabled. "
                                "Set YOLO26_AUTO_REBUILD=true to enable automatic engine rebuilding."
                            )
                            raise

                    # Check if TensorRT is unavailable and we should fall back to PyTorch
                    elif is_tensorrt_fallback_error(load_error):
                        logger.warning(
                            f"TensorRT unavailable or failed to load: {load_error}. "
                            "Attempting fallback to PyTorch model."
                        )
                        self._handle_tensorrt_fallback_to_pytorch(load_error)

                    else:
                        # Unknown error, re-raise
                        raise
                else:
                    raise

            # Check if TensorRT is being used
            if self.model_path.endswith(".engine"):
                self.tensorrt_enabled = True
                logger.info("TensorRT engine loaded successfully")
                # Note: torch.compile is not applied to TensorRT engines
                # as they are already graph-optimized
                if self.enable_torch_compile:
                    logger.info(
                        "torch.compile skipped for TensorRT engine "
                        "(TensorRT already provides graph optimization)"
                    )
            else:
                logger.info("YOLO model loaded (non-TensorRT format)")
                # Apply torch.compile() for PyTorch models (NEM-3773)
                if self.enable_torch_compile and is_compile_available():
                    self._apply_torch_compile()

            # Verify CUDA availability
            if "cuda" in self.device and torch.cuda.is_available():
                logger.info(f"Model loaded on {self.device}")
            else:
                self.device = "cpu"
                logger.info("CUDA not available, using CPU")

            # Warmup inference
            self._warmup()
            logger.info("Model loaded and warmed up successfully")

        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise

    def _handle_tensorrt_version_mismatch(self) -> None:
        """Handle TensorRT version mismatch by rebuilding the engine.

        This method:
        1. Deletes the stale engine file
        2. Finds or uses the configured source .pt model
        3. Rebuilds the TensorRT engine
        4. Loads the rebuilt engine

        Raises:
            RuntimeError: If the engine cannot be rebuilt or loaded.
        """
        from ultralytics import YOLO

        engine_path = self.model_path

        # Find the source .pt model
        pt_path = self.pt_model_path or get_pt_model_path_for_engine(engine_path)

        if pt_path is None:
            logger.error(
                f"Cannot rebuild TensorRT engine: no source .pt model found for {engine_path}. "
                "Set YOLO26_PT_MODEL_PATH to specify the source model path."
            )
            raise RuntimeError(
                f"TensorRT version mismatch and no source model available for {engine_path}"
            )

        logger.info(f"Found source model for rebuild: {pt_path}")

        # Delete the stale engine file
        delete_stale_engine(engine_path)

        # Determine precision from engine filename
        half = "_fp16" in engine_path.lower() or "_int8" not in engine_path.lower()

        # Rebuild the engine
        success = rebuild_tensorrt_engine(
            pt_model_path=pt_path,
            engine_output_path=engine_path,
            imgsz=640,
            half=half,
        )

        if not success:
            logger.error("Failed to rebuild TensorRT engine, falling back to .pt model")
            # Fall back to using the .pt model directly
            self.model_path = pt_path
            self.model = YOLO(pt_path)
            self.tensorrt_enabled = False
            logger.info(f"Loaded fallback PyTorch model from {pt_path}")
            return

        # Load the rebuilt engine
        logger.info(f"Loading rebuilt TensorRT engine from {engine_path}...")
        self.model = YOLO(engine_path)
        self.tensorrt_enabled = True
        logger.info("Rebuilt TensorRT engine loaded successfully")

    def _handle_tensorrt_fallback_to_pytorch(self, original_error: Exception) -> None:
        """Handle fallback from TensorRT to PyTorch when TensorRT is unavailable.

        This method is called when TensorRT fails to load due to reasons other than
        version mismatch (e.g., TensorRT not installed, GPU architecture mismatch).

        It attempts to find and load the corresponding PyTorch model (.pt file).

        Args:
            original_error: The original exception that triggered the fallback.

        Raises:
            RuntimeError: If no fallback PyTorch model is available.
        """
        from ultralytics import YOLO

        engine_path = self.model_path

        # Find the source .pt model
        pt_path = self.pt_model_path or get_pt_model_path_for_engine(engine_path)

        # NEM-4507: Add explicit None check before attempting to load
        if pt_path is None:
            error_msg = (
                f"Cannot fallback to PyTorch: no .pt model found for {engine_path}. "
                "Set YOLO26_PT_MODEL_PATH environment variable to specify the fallback model path."
            )
            logger.error(error_msg)
            # Re-raise with informative message
            raise RuntimeError(error_msg) from original_error

        logger.info(f"Found fallback PyTorch model: {pt_path}")

        try:
            # Attempt to load the PyTorch model
            self.model = YOLO(pt_path)
            self.model_path = pt_path
            self.tensorrt_enabled = False
            logger.info(
                f"Successfully fell back to PyTorch model from {pt_path}. "
                "TensorRT is disabled for this session."
            )
        except Exception as fallback_error:
            logger.error(f"Failed to load fallback PyTorch model {pt_path}: {fallback_error}")
            # Re-raise the original error since fallback also failed
            raise original_error from fallback_error

    def _apply_torch_compile(self) -> None:
        """Apply torch.compile() to the underlying PyTorch model for automatic kernel fusion.

        This method wraps the model with torch.compile() using the configured mode.
        If compilation fails, it falls back to eager execution gracefully.

        Note: This only applies to PyTorch models (.pt), not TensorRT engines (.engine)
        which are already optimized at the graph level.

        Expected speedup: 15-30% on supported operations.
        """
        try:
            # Configure compilation
            self._compile_config = CompileConfig(
                enabled=True,
                mode=self.torch_compile_mode,
                backend="inductor",
                fullgraph=False,  # Allow graph breaks for complex models
                dynamic=True,  # Support variable input sizes
            )

            logger.info(
                f"Applying torch.compile() to YOLO26 model "
                f"(mode={self.torch_compile_mode}, backend=inductor)"
            )

            # For Ultralytics YOLO, we need to compile the underlying model
            # The YOLO wrapper exposes the model through .model attribute
            if hasattr(self.model, "model") and self.model.model is not None:
                self.model.model = compile_model(
                    self.model.model,
                    config=self._compile_config,
                    model_name="YOLO26-backbone",
                )
                self._is_compiled = True
                logger.info("torch.compile() applied successfully to YOLO26 backbone")
            else:
                logger.warning(
                    "Could not access YOLO model backbone for torch.compile(). "
                    "Using default eager execution."
                )

        except Exception as e:
            logger.warning(
                f"Failed to apply torch.compile() to YOLO26: {e}. Falling back to eager execution."
            )
            self._is_compiled = False

    def _warmup(self, num_iterations: int = 3) -> None:
        """Warmup the model with dummy inputs."""
        logger.info(f"Warming up model with {num_iterations} iterations...")

        # Create a dummy image
        dummy_image = Image.new("RGB", (640, 480), color=(128, 128, 128))

        for i in range(num_iterations):
            try:
                _ = self.detect(dummy_image)
                logger.info(f"Warmup iteration {i + 1}/{num_iterations} complete")
            except Exception as e:
                logger.warning(f"Warmup iteration {i + 1} failed: {e}")

        logger.info("Warmup complete")

    def _clear_cuda_cache(self) -> None:
        """Clear CUDA cache to prevent memory fragmentation.

        Only clears cache when:
        - cache_clear_frequency > 0 (not disabled)
        - CUDA is available
        - Device is CUDA (not CPU)
        """
        if self.cache_clear_frequency > 0 and "cuda" in self.device and torch.cuda.is_available():
            torch.cuda.empty_cache()
            self.cache_clear_count += 1
            logger.debug(f"CUDA cache cleared (total clears: {self.cache_clear_count})")

    def detect(self, image: Image.Image) -> tuple[list[dict[str, Any]], float]:
        """Run object detection on an image.

        Args:
            image: PIL Image to detect objects in

        Returns:
            Tuple of (detections list, inference_time_ms)

        Raises:
            torch.cuda.OutOfMemoryError: If GPU runs out of memory during inference.
                The OOM is handled (logged, cache cleared, metrics recorded) and
                then re-raised so the caller can return an appropriate HTTP response.

        Note:
            CUDA cache is cleared after each detection to prevent memory fragmentation.
            This can be controlled via cache_clear_frequency parameter.
        """
        if self.model is None:
            raise RuntimeError("Model not loaded")

        start_time = time.perf_counter()

        try:
            # Pre-inference memory guard (NEM-4996)
            # YOLO26 typically needs ~500MB for inference
            if not check_memory_available(required_mb=500.0):
                logger.warning("Low GPU memory before YOLO26 inference, clearing cache proactively")
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()

            # Convert to RGB if needed
            if image.mode != "RGB":
                image = image.convert("RGB")

            # Run inference with Ultralytics YOLO
            # The model handles preprocessing internally
            results = self.model.predict(
                source=image,
                conf=self.confidence_threshold,
                verbose=False,
                device=self.device,
            )

            # Process results
            detections = []
            if results and len(results) > 0:
                result = results[0]
                boxes = result.boxes

                if boxes is not None and len(boxes) > 0:
                    for box in boxes:
                        # Get class ID and name
                        class_id = int(box.cls.item())
                        class_name = COCO_CLASSES.get(class_id)

                        # Filter to security-relevant classes
                        if class_name is None or class_name not in SECURITY_CLASSES:
                            continue

                        # Get confidence
                        confidence = float(box.conf.item())

                        # Apply class-specific confidence threshold (NEM-4522)
                        # Use class-specific threshold if defined, otherwise use default
                        class_threshold = CLASS_CONFIDENCE_THRESHOLDS.get(
                            class_name, self.confidence_threshold
                        )
                        if confidence < class_threshold:
                            continue

                        # Get bounding box coordinates (xyxy format)
                        x1, y1, x2, y2 = box.xyxy[0].tolist()

                        detections.append(
                            {
                                "class": class_name,
                                "confidence": confidence,
                                "bbox": {
                                    "x": int(x1),
                                    "y": int(y1),
                                    "width": int(x2 - x1),
                                    "height": int(y2 - y1),
                                },
                            }
                        )

            inference_time_ms = (time.perf_counter() - start_time) * 1000

            return detections, inference_time_ms
        except torch.cuda.OutOfMemoryError:
            # NEM-4996: Handle GPU OOM gracefully
            _oom_handler.handle_oom("detect")
            raise
        finally:
            # Clear CUDA cache to prevent memory fragmentation
            self._clear_cuda_cache()

    def detect_batch(self, images: list[Image.Image]) -> tuple[list[list[dict[str, Any]]], float]:
        """Run batch object detection on multiple images.

        Args:
            images: List of PIL Images

        Returns:
            Tuple of (list of detections per image, total_inference_time_ms)

        Note:
            CUDA cache is cleared every N images based on cache_clear_frequency.
            Individual detect() calls have their cache clearing disabled during batch
            processing to allow for batch-level cache management.
        """
        start_time = time.perf_counter()
        all_detections = []

        # Store original frequency and temporarily disable per-detection cache clearing
        # to manage cache clearing at batch level
        original_frequency = self.cache_clear_frequency
        self.cache_clear_frequency = 0  # Disable per-detection cache clearing

        try:
            # Process each image
            for i, image in enumerate(images):
                detections, _ = self.detect(image)
                all_detections.append(detections)

                # Clear cache every N images based on original frequency setting
                # Skip if cache clearing is disabled (original_frequency == 0)
                if original_frequency > 0 and (i + 1) % original_frequency == 0:
                    # Temporarily restore frequency to allow _clear_cuda_cache to work
                    self.cache_clear_frequency = original_frequency
                    self._clear_cuda_cache()
                    self.cache_clear_frequency = 0  # Re-disable for next iteration
        finally:
            # Restore original frequency
            self.cache_clear_frequency = original_frequency

        total_time_ms = (time.perf_counter() - start_time) * 1000

        return all_detections, total_time_ms

    def track(
        self,
        image: Image.Image,
        tracker: str = "botsort.yaml",
        persist: bool = True,
    ) -> tuple[list[dict[str, Any]], float]:
        """Run object tracking on an image.

        Uses Ultralytics' built-in tracking to maintain object IDs across frames.
        Unlike detect(), this method maintains tracker state between calls when
        persist=True, allowing consistent track IDs across video frames.

        Args:
            image: PIL Image to track objects in
            tracker: Tracker configuration file ('botsort.yaml' or 'bytetrack.yaml')
            persist: If True, maintain track IDs across frames (default: True)

        Returns:
            Tuple of (detections list with track_ids, inference_time_ms)

        Note:
            - Track IDs may be None for detections that haven't been assigned a track yet
            - CUDA cache is cleared after each tracking call to prevent memory fragmentation
        """
        if self.model is None:
            raise RuntimeError("Model not loaded")

        start_time = time.perf_counter()

        try:
            # Convert to RGB if needed
            if image.mode != "RGB":
                image = image.convert("RGB")

            # Run tracking with Ultralytics YOLO
            results = self.model.track(
                source=image,
                tracker=tracker,
                conf=self.confidence_threshold,
                persist=persist,
                verbose=False,
                device=self.device,
            )

            # Process results
            detections = []
            if results and len(results) > 0:
                result = results[0]
                boxes = result.boxes

                if boxes is not None and len(boxes) > 0:
                    # Get track IDs if available
                    track_ids = None
                    if boxes.id is not None:
                        track_ids = boxes.id.int().cpu().tolist()

                    for idx, box in enumerate(boxes):
                        # Get class ID and name
                        class_id = int(box.cls.item())
                        class_name = COCO_CLASSES.get(class_id)

                        # Filter to security-relevant classes
                        if class_name is None or class_name not in SECURITY_CLASSES:
                            continue

                        # Get confidence
                        confidence = float(box.conf.item())

                        # Apply class-specific confidence threshold (NEM-4522)
                        # Use class-specific threshold if defined, otherwise use default
                        class_threshold = CLASS_CONFIDENCE_THRESHOLDS.get(
                            class_name, self.confidence_threshold
                        )
                        if confidence < class_threshold:
                            continue

                        # Get bounding box coordinates (xyxy format)
                        x1, y1, x2, y2 = box.xyxy[0].tolist()

                        # Get track ID for this detection
                        track_id = None
                        if track_ids is not None and idx < len(track_ids):
                            track_id = track_ids[idx]

                        detections.append(
                            {
                                "class": class_name,
                                "confidence": confidence,
                                "bbox": {
                                    "x": int(x1),
                                    "y": int(y1),
                                    "width": int(x2 - x1),
                                    "height": int(y2 - y1),
                                },
                                "track_id": track_id,
                            }
                        )

            inference_time_ms = (time.perf_counter() - start_time) * 1000

            return detections, inference_time_ms
        except torch.cuda.OutOfMemoryError:
            # NEM-4996: Handle GPU OOM gracefully
            _oom_handler.handle_oom("track")
            raise
        finally:
            # Clear CUDA cache to prevent memory fragmentation
            self._clear_cuda_cache()


# Global model instance
model: YOLO26Model | None = None


def get_vram_usage() -> float | None:
    """Get VRAM usage in GB."""
    try:
        if torch.cuda.is_available():
            return float(torch.cuda.memory_allocated()) / (1024**3)
    except Exception as e:
        logger.warning(f"Failed to get VRAM usage: {e}")
    return None


def get_gpu_metrics() -> dict[str, float | int | None]:
    """Get GPU metrics using pynvml.

    Returns a dictionary containing:
    - gpu_utilization: GPU utilization percentage (0-100)
    - temperature: GPU temperature in Celsius
    - power_watts: GPU power usage in Watts

    All values will be None if pynvml is unavailable or an error occurs.
    """
    result: dict[str, float | int | None] = {
        "gpu_utilization": None,
        "temperature": None,
        "power_watts": None,
    }

    if not torch.cuda.is_available():
        return result

    try:
        import pynvml

        pynvml.nvmlInit()
        try:
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)

            # Get GPU utilization
            try:
                utilization = pynvml.nvmlDeviceGetUtilizationRates(handle)
                result["gpu_utilization"] = float(utilization.gpu)
            except pynvml.NVMLError as e:
                logger.debug(f"Failed to get GPU utilization: {e}")

            # Get temperature
            try:
                temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
                result["temperature"] = int(temp)
            except pynvml.NVMLError as e:
                logger.debug(f"Failed to get GPU temperature: {e}")

            # Get power usage
            try:
                power_mw = pynvml.nvmlDeviceGetPowerUsage(handle)
                result["power_watts"] = float(power_mw) / 1000.0
            except pynvml.NVMLError as e:
                logger.debug(f"Failed to get GPU power usage: {e}")

        finally:
            pynvml.nvmlShutdown()

    except ImportError:
        logger.debug("pynvml not installed, GPU metrics unavailable")
    except Exception as e:
        logger.debug(f"Failed to get GPU metrics via pynvml: {e}")

    return result


def _prebuild_yolo26_engine(pt_model_path: str) -> str | None:
    """Pre-build TensorRT engine from a .pt model at startup (NEM-4999).

    Checks if a pre-built engine exists for the current GPU architecture.
    If not, builds the engine before the server starts serving requests.
    This front-loads the TensorRT compilation to startup time instead of
    deferring it to the first inference request.

    The engine is saved with a metadata sidecar file that records the GPU
    architecture and TensorRT version, enabling validation on future startups.

    Args:
        pt_model_path: Path to the PyTorch .pt model file.

    Returns:
        Path to the TensorRT engine if pre-build succeeded, None otherwise.
    """
    try:
        from build_engine import build_tensorrt_engine
        from tensorrt_prebuild import validate_prebuilt_engine
    except ImportError as e:
        logger.warning(f"Pre-build utilities not available: {e}")
        return None

    # Derive engine path from model path
    pt_path = Path(pt_model_path)
    engine_dir = pt_path.parent / "exports"
    engine_dir.mkdir(parents=True, exist_ok=True)
    engine_path = str(engine_dir / f"{pt_path.stem}_fp16.engine")

    # Check if engine already exists and is valid for this GPU
    if Path(engine_path).exists():
        result = validate_prebuilt_engine(engine_path)
        if result.is_valid:
            logger.info(f"Pre-built TensorRT engine is valid: {engine_path}")
            return engine_path
        else:
            logger.warning(f"Pre-built engine invalid: {result.reason}")
            logger.info("Rebuilding TensorRT engine for current GPU...")
            # Delete stale engine
            try:
                Path(engine_path).unlink()
            except OSError as e:
                logger.warning(f"Failed to delete stale engine: {e}")

    # Check if source .pt model exists
    if not pt_path.exists():
        logger.warning(f"Source model not found: {pt_model_path}")
        return None

    # Build the engine
    logger.info(f"Pre-building TensorRT engine from {pt_model_path}...")
    logger.info("This is a one-time operation that may take 1-5 minutes.")
    success = build_tensorrt_engine(
        model_path=pt_model_path,
        output_path=engine_path,
        imgsz=640,
        half=True,
    )

    if success and Path(engine_path).exists():
        return engine_path
    else:
        logger.warning("TensorRT engine pre-build failed, falling back to PyTorch model")
        return None


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    """Lifespan context manager for FastAPI app."""
    global model

    from security import PathSecurityError, validate_model_path_env

    # Startup
    logger.info("Starting YOLO26 Detection Server...")

    # Load model configuration from environment or defaults
    # Validate model path from environment variable (NEM-4513)
    default_model_path = "/models/yolo26/exports/yolo26m_fp16.engine"
    try:
        model_path = validate_model_path_env(
            "YOLO26_MODEL_PATH",
            os.environ.get("YOLO26_MODEL_PATH"),
            default=default_model_path,
        )
        if model_path is None:
            model_path = default_model_path
    except PathSecurityError as e:
        logger.error(f"Invalid YOLO26_MODEL_PATH environment variable: {e}")
        logger.error("Falling back to default model path")
        model_path = default_model_path

    confidence_threshold = float(os.environ.get("YOLO26_CONFIDENCE", "0.5"))
    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    # Cache clear frequency: default 1 (every detection), 0 to disable
    cache_clear_frequency = int(os.environ.get("YOLO26_CACHE_CLEAR_FREQUENCY", "1"))

    # TensorRT engine pre-build at startup (NEM-4999)
    # When YOLO26_PREBUILD_ENGINE=true and model_path points to a .pt file,
    # pre-build the TensorRT engine before loading the model. This eliminates
    # cold-start latency on first inference by front-loading the engine build
    # to container startup time.
    prebuild_enabled = os.environ.get("YOLO26_PREBUILD_ENGINE", "true").lower() in (
        "true",
        "1",
        "yes",
    )
    if prebuild_enabled and model_path.endswith(".pt") and torch.cuda.is_available():
        engine_path = _prebuild_yolo26_engine(model_path)
        if engine_path:
            logger.info(f"Using pre-built TensorRT engine: {engine_path}")
            model_path = engine_path

    try:
        model = YOLO26Model(
            model_path=model_path,
            confidence_threshold=confidence_threshold,
            device=device,
            cache_clear_frequency=cache_clear_frequency,
        )
        model.load_model()
        logger.info("Model loaded successfully")
    except FileNotFoundError:
        logger.warning(f"Model not found at {model_path}")
        logger.warning(
            "Server will start but detection endpoints will fail until model is available"
        )
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        logger.warning("Server will start but detection endpoints will fail")

    yield

    # Shutdown
    logger.info("Shutting down YOLO26 Detection Server...")
    if model is not None and hasattr(model, "model") and model.model is not None:
        del model.model
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


# Create FastAPI app
app = FastAPI(
    title="YOLO26 Detection Server",
    description="Object detection service for home security monitoring using YOLO26 TensorRT",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint.

    Includes GPU memory health monitoring (NEM-4996):
    - gpu_memory_health: "healthy" / "warning" (>80%) / "critical" (>95%)
    - gpu_memory_allocated_mb: Current GPU memory allocation
    - gpu_memory_total_mb: Total GPU memory
    - gpu_memory_utilization_pct: Memory utilization percentage
    """
    cuda_available = torch.cuda.is_available()
    device = "cuda:0" if cuda_available else "cpu"
    vram_used = get_vram_usage() if cuda_available else None

    # Get GPU metrics (utilization, temperature, power) via pynvml
    gpu_metrics = get_gpu_metrics() if cuda_available else {}

    # NEM-4996: GPU memory health monitoring
    gpu_health = check_gpu_memory_health()

    # Determine overall status: model health AND GPU memory health
    model_loaded = model is not None and model.model is not None
    if not model_loaded or gpu_health.status.value == "critical":
        status = "degraded"
    else:
        status = "healthy"

    return HealthResponse(
        status=status,
        model_loaded=model_loaded,
        device=device,
        cuda_available=cuda_available,
        model_name=model.model_path if model else None,
        vram_used_gb=vram_used,
        gpu_utilization=gpu_metrics.get("gpu_utilization"),
        temperature=gpu_metrics.get("temperature"),
        power_watts=gpu_metrics.get("power_watts"),
        tensorrt_enabled=model.tensorrt_enabled if model else None,
        tensorrt_version=get_tensorrt_version(),
        torch_compile_enabled=model._is_compiled if model else None,
        torch_compile_mode=model.torch_compile_mode if model and model._is_compiled else None,
        gpu_memory_health=gpu_health.status.value,
        gpu_memory_allocated_mb=gpu_health.memory_stats.allocated_mb
        if gpu_health.memory_stats
        else None,
        gpu_memory_total_mb=gpu_health.memory_stats.total_mb if gpu_health.memory_stats else None,
        gpu_memory_utilization_pct=gpu_health.memory_stats.utilization_pct
        if gpu_health.memory_stats
        else None,
        gpu_memory_message=gpu_health.message,
    )


@app.get("/metrics")
async def metrics() -> Response:
    """Prometheus metrics endpoint.

    Returns metrics in Prometheus text format for scraping.
    Updates GPU metrics gauges before returning.
    """
    # Update model status gauge
    MODEL_LOADED.set(1 if model is not None and model.model is not None else 0)

    # Update GPU metrics gauges
    if torch.cuda.is_available():
        vram_used = get_vram_usage()
        if vram_used is not None:
            GPU_MEMORY_USED_GB.set(vram_used)

        # Update VRAM in bytes (new metric)
        vram_bytes = get_vram_usage_bytes()
        if vram_bytes is not None:
            update_vram_bytes(vram_bytes)

        gpu_metrics = get_gpu_metrics()
        if gpu_metrics.get("gpu_utilization") is not None:
            GPU_UTILIZATION.set(gpu_metrics["gpu_utilization"])
        if gpu_metrics.get("temperature") is not None:
            GPU_TEMPERATURE.set(gpu_metrics["temperature"])
        if gpu_metrics.get("power_watts") is not None:
            GPU_POWER_WATTS.set(gpu_metrics["power_watts"])

    return Response(content=generate_latest(), media_type="text/plain; charset=utf-8")


@app.post("/detect", response_model=DetectionResponse)
async def detect_objects(
    file: UploadFile = File(None), image_base64: str | None = None
) -> DetectionResponse:
    """Detect objects in an image.

    Accepts either:
    - Multipart file upload (file parameter)
    - Base64-encoded image (image_base64 parameter)

    Returns:
        Detection results with bounding boxes and confidence scores

    Raises:
        HTTPException 400: Invalid image file (corrupted, truncated, or not an image)
        HTTPException 413: Image size exceeds maximum allowed size
        HTTPException 503: Model not loaded
    """
    if model is None or model.model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    # Track filename for error reporting
    filename = file.filename if file else "base64_image"

    try:
        # Load image from file or base64 with size validation
        if file:
            # Validate file extension first
            ext_valid, ext_error = validate_file_extension(file.filename)
            if not ext_valid:
                logger.warning(
                    f"Invalid file extension for: {filename}. {ext_error}",
                    extra={"source_file": filename, "error": ext_error},
                )
                raise HTTPException(
                    status_code=400, detail=f"Invalid file '{filename}': {ext_error}"
                )

            image_bytes = await file.read()
            # Validate decoded image size
            if len(image_bytes) > MAX_IMAGE_SIZE_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail=f"Image size ({len(image_bytes)} bytes) exceeds maximum "
                    f"allowed size ({MAX_IMAGE_SIZE_BYTES} bytes / "
                    f"{MAX_IMAGE_SIZE_BYTES // (1024 * 1024)}MB)",
                )

            # Validate magic bytes before passing to PIL
            magic_valid, magic_result = validate_image_magic_bytes(image_bytes)
            if not magic_valid:
                logger.warning(
                    f"Invalid image magic bytes for: {filename}. {magic_result}",
                    extra={"source_file": filename, "error": magic_result},
                )
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid image file '{filename}': {magic_result}. "
                    f"Supported formats: JPEG, PNG, GIF, BMP, WEBP.",
                )

            image = Image.open(io.BytesIO(image_bytes))
        elif image_base64:
            # Validate base64 string size BEFORE decoding to prevent DoS
            if len(image_base64) > MAX_BASE64_SIZE_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail=f"Base64 image data size ({len(image_base64)} bytes) exceeds "
                    f"maximum allowed size ({MAX_BASE64_SIZE_BYTES} bytes). "
                    f"Maximum decoded image size: {MAX_IMAGE_SIZE_BYTES // (1024 * 1024)}MB",
                )
            try:
                image_bytes = base64.b64decode(image_base64)
            except binascii.Error as e:
                raise HTTPException(status_code=400, detail=f"Invalid base64 encoding: {e}") from e
            # Validate decoded image size (base64 can decode to larger or smaller)
            if len(image_bytes) > MAX_IMAGE_SIZE_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail=f"Decoded image size ({len(image_bytes)} bytes) exceeds maximum "
                    f"allowed size ({MAX_IMAGE_SIZE_BYTES} bytes / "
                    f"{MAX_IMAGE_SIZE_BYTES // (1024 * 1024)}MB)",
                )

            # Validate magic bytes before passing to PIL
            magic_valid, magic_result = validate_image_magic_bytes(image_bytes)
            if not magic_valid:
                logger.warning(
                    f"Invalid image magic bytes for: {filename}. {magic_result}",
                    extra={"source_file": filename, "error": magic_result},
                )
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid image file '{filename}': {magic_result}. "
                    f"Supported formats: JPEG, PNG, GIF, BMP, WEBP.",
                )

            image = Image.open(io.BytesIO(image_bytes))
        else:
            raise HTTPException(
                status_code=400, detail="Either 'file' or 'image_base64' must be provided"
            )

        # Get original dimensions
        img_width, img_height = image.size

        # Run detection with metrics tracking
        start_time = time.perf_counter()
        detections, inference_time_ms = model.detect(image)
        latency_seconds = time.perf_counter() - start_time

        # Record metrics using helper functions (records both new and legacy metrics)
        record_inference(endpoint="detect", duration_seconds=latency_seconds, success=True)
        DETECTIONS_PER_IMAGE.observe(len(detections))

        # Record per-class detection counts
        record_detections(detections)

        return DetectionResponse(
            detections=[Detection(**d) for d in detections],
            inference_time_ms=inference_time_ms,
            image_width=img_width,
            image_height=img_height,
        )

    except HTTPException:
        record_inference(endpoint="detect", duration_seconds=0, success=False)
        record_error(error_type="http_error")
        raise
    except torch.cuda.OutOfMemoryError as e:
        # NEM-4996: Handle GPU OOM gracefully with 503 + Retry-After
        record_inference(endpoint="detect", duration_seconds=0, success=False)
        record_error(error_type="gpu_oom")
        raise HTTPException(
            status_code=503,
            detail="GPU out of memory during detection. The service is temporarily "
            "unable to process requests. Please retry after a short delay.",
            headers={"Retry-After": "5"},
        ) from e
    except UnidentifiedImageError as e:
        # Handle corrupted/invalid image files - return 400 Bad Request
        record_inference(endpoint="detect", duration_seconds=0, success=False)
        record_error(error_type="invalid_image")
        logger.warning(
            f"Invalid image file received: {filename}. "
            f"File may be corrupted, truncated, or not a valid image format. Error: {e}",
            extra={"source_file": filename, "error": str(e)},
        )
        raise HTTPException(
            status_code=400,
            detail=f"Invalid image file '{filename}': Cannot identify image format. "
            f"File may be corrupted, truncated, or not a supported image type "
            f"(supported: JPEG, PNG, GIF, BMP, WEBP).",
        ) from e
    except OSError as e:
        # Handle truncated or corrupted images that PIL can partially read
        # This catches "image file is truncated" errors
        record_inference(endpoint="detect", duration_seconds=0, success=False)
        record_error(error_type="corrupted_image")
        logger.warning(
            f"Corrupted image file received: {filename}. Error: {e}",
            extra={"source_file": filename, "error": str(e)},
        )
        raise HTTPException(
            status_code=400,
            detail=f"Corrupted image file '{filename}': {e!s}",
        ) from e
    except Exception as e:
        record_inference(endpoint="detect", duration_seconds=0, success=False)
        record_error(error_type="detection_error")
        logger.error(f"Detection failed for {filename}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Detection failed: {e!s}") from e


@app.post("/track", response_model=TrackingResponse)
async def track_objects(
    file: UploadFile = File(None),
    image_base64: str | None = None,
    tracker: str = "botsort.yaml",
    persist: bool = True,
) -> TrackingResponse:
    """Track objects in an image with persistent track IDs.

    Similar to /detect, but uses Ultralytics' built-in tracking to maintain
    object IDs across sequential frames. Track IDs persist between requests
    when persist=True (default).

    Accepts either:
    - Multipart file upload (file parameter)
    - Base64-encoded image (image_base64 parameter)

    Args:
        file: Image file upload
        image_base64: Base64-encoded image data
        tracker: Tracker configuration ('botsort.yaml' or 'bytetrack.yaml')
        persist: If True, maintain track IDs across frames (default: True)

    Returns:
        Tracking results with bounding boxes, confidence scores, and track IDs

    Raises:
        HTTPException 400: Invalid image file (corrupted, truncated, or not an image)
        HTTPException 413: Image size exceeds maximum allowed size
        HTTPException 503: Model not loaded
    """
    if model is None or model.model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    # Track filename for error reporting
    filename = file.filename if file else "base64_image"

    try:
        # Load image from file or base64 with size validation
        if file:
            # Validate file extension first
            ext_valid, ext_error = validate_file_extension(file.filename)
            if not ext_valid:
                logger.warning(
                    f"Invalid file extension for: {filename}. {ext_error}",
                    extra={"source_file": filename, "error": ext_error},
                )
                raise HTTPException(
                    status_code=400, detail=f"Invalid file '{filename}': {ext_error}"
                )

            image_bytes = await file.read()
            # Validate decoded image size
            if len(image_bytes) > MAX_IMAGE_SIZE_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail=f"Image size ({len(image_bytes)} bytes) exceeds maximum "
                    f"allowed size ({MAX_IMAGE_SIZE_BYTES} bytes / "
                    f"{MAX_IMAGE_SIZE_BYTES // (1024 * 1024)}MB)",
                )

            # Validate magic bytes before passing to PIL
            magic_valid, magic_result = validate_image_magic_bytes(image_bytes)
            if not magic_valid:
                logger.warning(
                    f"Invalid image magic bytes for: {filename}. {magic_result}",
                    extra={"source_file": filename, "error": magic_result},
                )
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid image file '{filename}': {magic_result}. "
                    f"Supported formats: JPEG, PNG, GIF, BMP, WEBP.",
                )

            image = Image.open(io.BytesIO(image_bytes))
        elif image_base64:
            # Validate base64 string size BEFORE decoding to prevent DoS
            if len(image_base64) > MAX_BASE64_SIZE_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail=f"Base64 image data size ({len(image_base64)} bytes) exceeds "
                    f"maximum allowed size ({MAX_BASE64_SIZE_BYTES} bytes). "
                    f"Maximum decoded image size: {MAX_IMAGE_SIZE_BYTES // (1024 * 1024)}MB",
                )
            try:
                image_bytes = base64.b64decode(image_base64)
            except binascii.Error as e:
                raise HTTPException(status_code=400, detail=f"Invalid base64 encoding: {e}") from e
            # Validate decoded image size (base64 can decode to larger or smaller)
            if len(image_bytes) > MAX_IMAGE_SIZE_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail=f"Decoded image size ({len(image_bytes)} bytes) exceeds maximum "
                    f"allowed size ({MAX_IMAGE_SIZE_BYTES} bytes / "
                    f"{MAX_IMAGE_SIZE_BYTES // (1024 * 1024)}MB)",
                )

            # Validate magic bytes before passing to PIL
            magic_valid, magic_result = validate_image_magic_bytes(image_bytes)
            if not magic_valid:
                logger.warning(
                    f"Invalid image magic bytes for: {filename}. {magic_result}",
                    extra={"source_file": filename, "error": magic_result},
                )
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid image file '{filename}': {magic_result}. "
                    f"Supported formats: JPEG, PNG, GIF, BMP, WEBP.",
                )

            image = Image.open(io.BytesIO(image_bytes))
        else:
            raise HTTPException(
                status_code=400, detail="Either 'file' or 'image_base64' must be provided"
            )

        # Get original dimensions
        img_width, img_height = image.size

        # Run tracking with metrics tracking
        start_time = time.perf_counter()
        detections, inference_time_ms = model.track(image, tracker=tracker, persist=persist)
        latency_seconds = time.perf_counter() - start_time

        # Record metrics
        INFERENCE_LATENCY_SECONDS.labels(endpoint="track").observe(latency_seconds)
        DETECTIONS_PER_IMAGE.observe(len(detections))
        INFERENCE_REQUESTS_TOTAL.labels(endpoint="track", status="success").inc()

        return TrackingResponse(
            detections=[TrackedDetection(**d) for d in detections],
            inference_time_ms=inference_time_ms,
            image_width=img_width,
            image_height=img_height,
        )

    except HTTPException:
        INFERENCE_REQUESTS_TOTAL.labels(endpoint="track", status="error").inc()
        raise
    except UnidentifiedImageError as e:
        # Handle corrupted/invalid image files - return 400 Bad Request
        INFERENCE_REQUESTS_TOTAL.labels(endpoint="track", status="error").inc()
        logger.warning(
            f"Invalid image file received: {filename}. "
            f"File may be corrupted, truncated, or not a valid image format. Error: {e}",
            extra={"source_file": filename, "error": str(e)},
        )
        raise HTTPException(
            status_code=400,
            detail=f"Invalid image file '{filename}': Cannot identify image format. "
            f"File may be corrupted, truncated, or not a supported image type "
            f"(supported: JPEG, PNG, GIF, BMP, WEBP).",
        ) from e
    except OSError as e:
        # Handle truncated or corrupted images that PIL can partially read
        # This catches "image file is truncated" errors
        INFERENCE_REQUESTS_TOTAL.labels(endpoint="track", status="error").inc()
        logger.warning(
            f"Corrupted image file received: {filename}. Error: {e}",
            extra={"source_file": filename, "error": str(e)},
        )
        raise HTTPException(
            status_code=400,
            detail=f"Corrupted image file '{filename}': {e!s}",
        ) from e
    except Exception as e:
        INFERENCE_REQUESTS_TOTAL.labels(endpoint="track", status="error").inc()
        logger.error(f"Tracking failed for {filename}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Tracking failed: {e!s}") from e


@app.post("/detect/batch")
async def detect_objects_batch(files: list[UploadFile] = File(...)) -> JSONResponse:
    """Batch detection endpoint for multiple images.

    Args:
        files: List of image files to process

    Returns:
        JSON response with detections for each image

    Raises:
        HTTPException 400: One or more files are invalid images
        HTTPException 413: One or more files exceed maximum size
        HTTPException 503: Model not loaded
    """
    if model is None or model.model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    try:
        # Load all images with size validation
        images: list[Image.Image] = []
        for idx, file in enumerate(files):
            # Validate file extension first
            ext_valid, ext_error = validate_file_extension(file.filename)
            if not ext_valid:
                logger.warning(
                    f"Invalid file extension in batch: {file.filename} (index {idx}). {ext_error}",
                    extra={"source_file": file.filename, "index": idx, "error": ext_error},
                )
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid file at index {idx} ({file.filename}): {ext_error}",
                )

            image_bytes = await file.read()
            # Validate each file's size
            if len(image_bytes) > MAX_IMAGE_SIZE_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail=f"Image {idx} ({file.filename}) size ({len(image_bytes)} bytes) "
                    f"exceeds maximum allowed size ({MAX_IMAGE_SIZE_BYTES} bytes / "
                    f"{MAX_IMAGE_SIZE_BYTES // (1024 * 1024)}MB)",
                )

            # Validate magic bytes before passing to PIL
            magic_valid, magic_result = validate_image_magic_bytes(image_bytes)
            if not magic_valid:
                logger.warning(
                    f"Invalid image magic bytes in batch: {file.filename} (index {idx}). {magic_result}",
                    extra={"source_file": file.filename, "index": idx, "error": magic_result},
                )
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid image file at index {idx} ({file.filename}): {magic_result}. "
                    f"Supported formats: JPEG, PNG, GIF, BMP, WEBP.",
                )

            try:
                image = Image.open(io.BytesIO(image_bytes))
                images.append(image)
            except UnidentifiedImageError as e:
                logger.warning(
                    f"Invalid image file in batch: {file.filename} (index {idx}). "
                    f"File may be corrupted, truncated, or not a valid image format. Error: {e}",
                    extra={"source_file": file.filename, "index": idx, "error": str(e)},
                )
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid image file at index {idx} ({file.filename}): "
                    f"Cannot identify image format. File may be corrupted, truncated, "
                    f"or not a supported image type.",
                ) from e
            except OSError as e:
                logger.warning(
                    f"Corrupted image file in batch: {file.filename} (index {idx}). Error: {e}",
                    extra={"source_file": file.filename, "index": idx, "error": str(e)},
                )
                raise HTTPException(
                    status_code=400,
                    detail=f"Corrupted image file at index {idx} ({file.filename}): {e!s}",
                ) from e

        # Record batch size
        record_batch_size(batch_size=len(images))

        # Run batch detection with metrics tracking
        start_time = time.perf_counter()
        all_detections, total_time_ms = model.detect_batch(images)
        latency_seconds = time.perf_counter() - start_time

        # Record metrics
        record_inference(endpoint="detect_batch", duration_seconds=latency_seconds, success=True)

        # Record per-class detection counts for all detections
        for detections in all_detections:
            record_detections(detections)
            DETECTIONS_PER_IMAGE.observe(len(detections))

        # Format response
        results = []
        for idx, (image, detections) in enumerate(zip(images, all_detections, strict=False)):  # type: ignore[assignment]
            results.append(
                {
                    "index": idx,
                    "filename": files[idx].filename,
                    "image_width": image.size[0],
                    "image_height": image.size[1],
                    "detections": detections,
                }
            )

        return JSONResponse(
            content={
                "results": results,
                "total_inference_time_ms": total_time_ms,
                "num_images": len(images),
            }
        )

    except HTTPException:
        record_inference(endpoint="detect_batch", duration_seconds=0, success=False)
        record_error(error_type="http_error")
        raise
    except Exception as e:
        record_inference(endpoint="detect_batch", duration_seconds=0, success=False)
        record_error(error_type="batch_detection_error")
        logger.error(f"Batch detection failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Batch detection failed: {e!s}") from e


if __name__ == "__main__":
    import uvicorn

    # Default to 0.0.0.0 to allow connections from Docker/Podman containers.
    # When AI servers run natively on host while backend runs in containers,
    # binding to 127.0.0.1 would prevent container-to-host connectivity.
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8095"))
    uvicorn.run(app, host=host, port=port, log_level="info")
