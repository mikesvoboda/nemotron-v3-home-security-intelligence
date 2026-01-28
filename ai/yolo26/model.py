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
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import torch
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse, Response
from PIL import Image, UnidentifiedImageError
from prometheus_client import generate_latest
from pydantic import BaseModel, ConfigDict, Field

# Add ai directory to path for compile_utils import
_ai_dir = Path(__file__).parent.parent
if str(_ai_dir) not in sys.path:
    sys.path.insert(0, str(_ai_dir))

from compile_utils import CompileConfig, compile_model, is_compile_available  # noqa: E402

# Import metrics from the metrics module
from metrics import (  # noqa: E402
    DETECTIONS_PER_IMAGE,
    GPU_MEMORY_USED_GB,
    GPU_POWER_WATTS,
    GPU_TEMPERATURE,
    GPU_UTILIZATION,
    INFERENCE_LATENCY_SECONDS,
    INFERENCE_REQUESTS_TOTAL,
    MODEL_INFERENCE_HEALTHY,
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

        return trt.__version__
    except ImportError:
        logger.debug("TensorRT not installed")
        return None
    except Exception as e:
        logger.warning(f"Error getting TensorRT version: {e}")
        return None


def is_tensorrt_version_mismatch_error(error: Exception) -> bool:
    """Check if an exception indicates a TensorRT version mismatch or engine load failure.

    Args:
        error: The exception to check.

    Returns:
        True if the error indicates a TensorRT version mismatch or engine load failure,
        False otherwise.

    Note:
        NEM-3877: Added detection of 'NoneType' object has no attribute
        'create_execution_context' error which occurs when TensorRT engine
        was built with a different TensorRT version than the runtime.
    """
    error_str = str(error).lower()
    # Common TensorRT version mismatch error patterns
    mismatch_patterns = [
        "older plan file",
        "newer plan file",
        "deserialization",
        "failed due to an old",
        "version mismatch",
        "incompatible",
        "exported with a different version",
        "deserializecudaengine",
        # NEM-3877: TensorRT engine fails to load when built with different version
        "'nonetype' object has no attribute 'create_execution_context'",
        "create_execution_context",
    ]
    return any(pattern in error_str for pattern in mismatch_patterns)


def get_pt_model_path_for_engine(engine_path: str) -> str | None:
    """Derive the .pt model path from a TensorRT engine path.

    TensorRT engines are typically named like:
    - yolo26m_fp16.engine -> yolo26m.pt
    - yolo26m.engine -> yolo26m.pt

    Args:
        engine_path: Path to the TensorRT engine file.

    Returns:
        Path to the corresponding .pt file if it exists, None otherwise.
    """
    engine_path_obj = Path(engine_path)

    # Remove precision suffix if present (e.g., _fp16, _int8, _fp32)
    stem = engine_path_obj.stem
    stem = re.sub(r"_(fp16|fp32|int8)$", "", stem, flags=re.IGNORECASE)

    # Look for .pt file in same directory
    pt_path = engine_path_obj.parent / f"{stem}.pt"
    if pt_path.exists():
        return str(pt_path)

    # Look for .pt file in parent directory
    pt_path = engine_path_obj.parent.parent / f"{stem}.pt"
    if pt_path.exists():
        return str(pt_path)

    # Check common model paths
    common_paths = [
        f"/models/yolo26/{stem}.pt",
        f"/models/yolo26/exports/{stem}.pt",
    ]
    for path in common_paths:
        if Path(path).exists():
            return path

    return None


def rebuild_tensorrt_engine(
    pt_model_path: str,
    engine_output_path: str,
    imgsz: int = 640,
    half: bool = True,
) -> bool:
    """Rebuild a TensorRT engine from a PyTorch model.

    Args:
        pt_model_path: Path to the source PyTorch model (.pt file).
        engine_output_path: Path to write the rebuilt engine.
        imgsz: Image size for export (default: 640).
        half: Use FP16 precision (default: True).

    Returns:
        True if rebuild succeeded, False otherwise.
    """
    try:
        from ultralytics import YOLO

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
        exported_path = Path(str(exported_path))
        target_path = Path(engine_output_path)

        if exported_path != target_path:
            # Ensure parent directory exists
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(exported_path), str(target_path))

        logger.info(f"TensorRT engine rebuilt successfully in {export_time:.1f}s")
        trt_version = get_tensorrt_version()
        logger.info(f"Engine built with TensorRT version: {trt_version}")

        return True

    except Exception as e:
        logger.error(f"Failed to rebuild TensorRT engine: {e}")
        return False


def delete_stale_engine(engine_path: str) -> bool:
    """Delete a stale TensorRT engine file.

    Args:
        engine_path: Path to the engine file to delete.

    Returns:
        True if deletion succeeded, False otherwise.
    """
    try:
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


# =============================================================================
# Instance Segmentation Models (NEM-3912)
# =============================================================================


class MaskRLE(BaseModel):
    """Run-length encoded mask data."""

    counts: list[int] = Field(..., description="RLE counts (alternating zeros and ones)")
    size: list[int] = Field(..., description="Mask dimensions [height, width]")


class SegmentationDetection(BaseModel):
    """Single object detection result with instance segmentation mask."""

    model_config = ConfigDict(populate_by_name=True)

    class_name: str = Field(..., alias="class", description="Detected object class")
    confidence: float = Field(..., description="Detection confidence score (0-1)")
    bbox: BoundingBox = Field(..., description="Bounding box coordinates")
    mask_rle: dict[str, Any] | None = Field(None, description="Run-length encoded binary mask")
    mask_polygon: list[list[float]] | None = Field(
        None, description="Polygon contours for the mask [[x1,y1,x2,y2,...], ...]"
    )


class SegmentationResponse(BaseModel):
    """Response format for segmentation endpoint."""

    detections: list[SegmentationDetection] = Field(
        default_factory=list, description="List of detected objects with masks"
    )
    inference_time_ms: float = Field(..., description="Inference time in milliseconds")
    image_width: int = Field(..., description="Original image width")
    image_height: int = Field(..., description="Original image height")


# =============================================================================
# Mask Encoding Utilities (NEM-3912)
# =============================================================================


def encode_mask_to_rle(mask: Any) -> dict[str, Any]:
    """Encode a binary mask to run-length encoding (RLE).

    Uses COCO-style RLE format where counts alternate between:
    - Count of zeros
    - Count of ones
    - Count of zeros
    - ...

    The first count is always the number of zeros before the first one
    (or the total length if there are no ones).

    Args:
        mask: Binary numpy array where 1/255 indicates foreground.

    Returns:
        Dictionary with 'counts' (list of run lengths) and 'size' [height, width].
    """
    import numpy as np

    # Ensure binary mask (0 or 1)
    binary_mask = (mask > 0).astype(np.uint8)
    flat = binary_mask.flatten(order="F")  # Column-major (Fortran) order for COCO compatibility

    n = len(flat)
    if n == 0:
        return {"counts": [], "size": list(mask.shape)}

    # Find positions where value changes (0->1 or 1->0)
    # By comparing each element with its predecessor (using 0 as virtual predecessor)
    # diff will be non-zero at positions where a transition occurs
    diff = np.diff(np.concatenate([[0], flat, [0]]))
    change_positions = np.where(diff != 0)[0]

    # If no changes, the mask is all zeros or all ones
    if len(change_positions) == 0:
        return {"counts": [n], "size": list(mask.shape)}

    # Add boundary positions (0 at start, n at end) if not already present
    # This ensures we capture the full run lengths
    if change_positions[0] != 0:
        change_positions = np.concatenate([[0], change_positions])
    if change_positions[-1] != n:
        change_positions = np.concatenate([change_positions, [n]])

    # Compute run lengths from change positions
    counts = np.diff(change_positions).tolist()

    return {
        "counts": counts,
        "size": list(mask.shape),  # [height, width]
    }


def decode_rle_to_mask(rle: dict[str, Any]) -> Any:
    """Decode run-length encoding back to binary mask.

    Args:
        rle: Dictionary with 'counts' and 'size' keys.

    Returns:
        Binary numpy array.
    """
    import numpy as np

    height, width = rle["size"]
    counts = rle["counts"]

    # Reconstruct flat mask from RLE
    flat = np.zeros(height * width, dtype=np.uint8)
    pos = 0
    value = 0  # Start with zeros

    for count in counts:
        flat[pos : pos + count] = value
        pos += count
        value = 1 - value  # Toggle between 0 and 1

    # Reshape to original dimensions (column-major order)
    return flat.reshape((height, width), order="F")


def mask_to_polygon(mask: Any, simplify_tolerance: float = 1.0) -> list[list[float]]:
    """Convert binary mask to polygon contours.

    Args:
        mask: Binary numpy array where 1/255 indicates foreground.
        simplify_tolerance: Douglas-Peucker simplification tolerance.

    Returns:
        List of polygon contours, each as [x1, y1, x2, y2, ...].
    """
    import cv2
    import numpy as np

    # Ensure binary mask (0 or 255)
    binary_mask = ((mask > 0) * 255).astype(np.uint8)

    # Find contours
    contours, _ = cv2.findContours(binary_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    polygons = []
    for contour in contours:
        # Simplify contour
        epsilon = simplify_tolerance
        approx = cv2.approxPolyDP(contour, epsilon, True)

        # Flatten to [x1, y1, x2, y2, ...] format
        if len(approx) >= 3:  # Need at least 3 points for a polygon
            flat_coords = approx.flatten().tolist()
            polygons.append(flat_coords)

    return polygons


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
    # NEM-3878: Track whether inference has been tested on startup
    inference_tested: bool | None = None
    # NEM-3877: Track which backend is actively being used
    active_backend: str | None = None


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
        # NEM-3878: Track whether inference has been tested and is working
        self.inference_healthy = False
        # NEM-3877: Track which backend is actively being used (None until loaded)
        self.active_backend: str | None = None

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

        Handles TensorRT version mismatches (NEM-3871) by:
        1. Detecting version mismatch errors during engine load
        2. Deleting the stale engine file
        3. Rebuilding the engine from the source .pt file if available
        4. Falling back to the .pt model if rebuild fails or is disabled

        NEM-3877: Added automatic fallback to PyTorch when TensorRT fails.
        """
        try:
            logger.info("Loading YOLO26 TensorRT model with Ultralytics...")

            from ultralytics import YOLO

            # Attempt to load the model
            try:
                self.model = YOLO(self.model_path)
            except Exception as load_error:
                # Check if this is a TensorRT version mismatch or engine load failure
                if self.model_path.endswith(".engine") and is_tensorrt_version_mismatch_error(
                    load_error
                ):
                    logger.warning(f"TensorRT engine load failed: {load_error}")
                    trt_version = get_tensorrt_version()
                    logger.warning(f"Current TensorRT runtime version: {trt_version}")

                    # Attempt to rebuild if auto_rebuild is enabled
                    if self.auto_rebuild:
                        self._handle_tensorrt_version_mismatch()
                    else:
                        # NEM-3877: Fall back to PyTorch model directly
                        logger.warning(
                            "TensorRT auto-rebuild is disabled. "
                            "Attempting fallback to PyTorch model..."
                        )
                        self._fallback_to_pytorch()
                else:
                    raise

            # Check if TensorRT is being used
            if self.model_path.endswith(".engine"):
                self.tensorrt_enabled = True
                self.active_backend = "tensorrt"
                logger.info("TensorRT engine loaded successfully")
                logger.info(f"Active backend: {self.active_backend}")
                # Note: torch.compile is not applied to TensorRT engines
                # as they are already graph-optimized
                if self.enable_torch_compile:
                    logger.info(
                        "torch.compile skipped for TensorRT engine "
                        "(TensorRT already provides graph optimization)"
                    )
            else:
                self.tensorrt_enabled = False
                self.active_backend = "pytorch"
                logger.info("YOLO model loaded (non-TensorRT format)")
                logger.info(f"Active backend: {self.active_backend}")
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

    def _fallback_to_pytorch(self) -> None:
        """Fall back to PyTorch model when TensorRT engine fails to load.

        NEM-3877: This method attempts to load the .pt model file when the
        TensorRT engine fails to load due to version mismatch or other issues.

        Raises:
            RuntimeError: If no fallback .pt model is available.
        """
        from ultralytics import YOLO

        # Find the source .pt model
        pt_path = self.pt_model_path or get_pt_model_path_for_engine(self.model_path)

        if pt_path is None:
            raise RuntimeError(
                f"TensorRT engine failed and no fallback .pt model available for {self.model_path}. "
                "Set YOLO26_PT_MODEL_PATH to specify the source model path."
            )

        logger.info(f"Falling back to PyTorch model: {pt_path}")

        # Load the PyTorch model
        self.model = YOLO(pt_path)
        self.model_path = pt_path
        self.tensorrt_enabled = False
        self.active_backend = "pytorch"

        logger.info(f"Successfully loaded fallback PyTorch model from {pt_path}")

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
        """Warmup the model with dummy inputs.

        NEM-3878: This method now validates that inference actually works
        by setting inference_healthy based on warmup success/failure.
        """
        logger.info(f"Warming up model with {num_iterations} iterations...")

        # Create a dummy image
        dummy_image = Image.new("RGB", (640, 480), color=(128, 128, 128))

        warmup_success = False
        for i in range(num_iterations):
            try:
                _ = self.detect(dummy_image)
                logger.info(f"Warmup iteration {i + 1}/{num_iterations} complete")
                warmup_success = True  # At least one iteration succeeded
            except Exception as e:
                logger.warning(f"Warmup iteration {i + 1} failed: {e}")

        # NEM-3878: Set inference_healthy based on whether ANY warmup iteration succeeded
        if warmup_success:
            self.inference_healthy = True
            logger.info("Warmup complete - inference validated successfully")
        else:
            self.inference_healthy = False
            logger.error("Warmup FAILED - all inference attempts failed")

        # Update Prometheus metric
        MODEL_INFERENCE_HEALTHY.set(1 if self.inference_healthy else 0)

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

        Note:
            CUDA cache is cleared after each detection to prevent memory fragmentation.
            This can be controlled via cache_clear_frequency parameter.
        """
        if self.model is None:
            raise RuntimeError("Model not loaded")

        start_time = time.perf_counter()

        try:
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
        finally:
            # Clear CUDA cache to prevent memory fragmentation
            self._clear_cuda_cache()

    def segment(self, image: Image.Image) -> tuple[list[dict[str, Any]], float]:
        """Run instance segmentation on an image (NEM-3912).

        Performs object detection with instance-level segmentation masks.
        Uses the same YOLO model but extracts mask data from results.

        Args:
            image: PIL Image to segment objects in

        Returns:
            Tuple of (segmentation detections list, inference_time_ms)
            Each detection includes:
            - class: Object class name
            - confidence: Detection confidence
            - bbox: Bounding box {x, y, width, height}
            - mask_rle: Run-length encoded mask
            - mask_polygon: Polygon contours for the mask

        Note:
            This method requires a segmentation-capable YOLO model (yolo*-seg.pt).
            If the model doesn't support segmentation, masks will be None.
        """
        if self.model is None:
            raise RuntimeError("Model not loaded")

        start_time = time.perf_counter()

        try:
            # Convert to RGB if needed
            if image.mode != "RGB":
                image = image.convert("RGB")

            # Run inference with Ultralytics YOLO
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
                masks = getattr(result, "masks", None)

                if boxes is not None and len(boxes) > 0:
                    for idx, box in enumerate(boxes):
                        # Get class ID and name
                        class_id = int(box.cls.item())
                        class_name = COCO_CLASSES.get(class_id)

                        # Filter to security-relevant classes
                        if class_name is None or class_name not in SECURITY_CLASSES:
                            continue

                        # Get confidence
                        confidence = float(box.conf.item())

                        # Get bounding box coordinates (xyxy format)
                        x1, y1, x2, y2 = box.xyxy[0].tolist()

                        # Extract mask data if available
                        mask_rle = None
                        mask_polygon = None

                        if masks is not None and len(masks) > idx:
                            try:
                                # Get binary mask as numpy array
                                mask_data = masks.data[idx].cpu().numpy()

                                # Encode mask to RLE
                                mask_rle = encode_mask_to_rle(mask_data)

                                # Convert to polygon contours
                                if masks.xy is not None and len(masks.xy) > idx:
                                    # Use Ultralytics' polygon representation
                                    polygon_coords = masks.xy[idx]
                                    if polygon_coords is not None and len(polygon_coords) > 0:
                                        mask_polygon = [polygon_coords.flatten().tolist()]
                                else:
                                    # Fallback: compute polygon from mask
                                    mask_polygon = mask_to_polygon(mask_data)
                            except Exception as mask_error:
                                logger.warning(
                                    f"Failed to extract mask for detection {idx}: {mask_error}"
                                )

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
                                "mask_rle": mask_rle,
                                "mask_polygon": mask_polygon,
                            }
                        )

            inference_time_ms = (time.perf_counter() - start_time) * 1000

            return detections, inference_time_ms
        finally:
            # Clear CUDA cache to prevent memory fragmentation
            self._clear_cuda_cache()


# Global model instance
model: YOLO26Model | None = None


def get_vram_usage() -> float | None:
    """Get VRAM usage in GB."""
    try:
        if torch.cuda.is_available():
            return torch.cuda.memory_allocated() / (1024**3)
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


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Lifespan context manager for FastAPI app."""
    global model  # noqa: PLW0603

    # Startup
    logger.info("Starting YOLO26 Detection Server...")

    # Load model configuration from environment or defaults
    model_path = os.environ.get("YOLO26_MODEL_PATH", "/models/yolo26/exports/yolo26m_fp16.engine")
    confidence_threshold = float(os.environ.get("YOLO26_CONFIDENCE", "0.5"))
    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    # Cache clear frequency: default 1 (every detection), 0 to disable
    cache_clear_frequency = int(os.environ.get("YOLO26_CACHE_CLEAR_FREQUENCY", "1"))

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

    NEM-3878: Updated to check inference_healthy for determining health status.
    The endpoint now reports "unhealthy" if inference warmup failed, even if
    the model object exists. This catches cases where the TensorRT engine
    loads but fails during actual inference.
    """
    cuda_available = torch.cuda.is_available()
    device = "cuda:0" if cuda_available else "cpu"
    vram_used = get_vram_usage() if cuda_available else None

    # Get GPU metrics (utilization, temperature, power) via pynvml
    gpu_metrics = get_gpu_metrics() if cuda_available else {}

    # NEM-3878: Check inference_healthy in addition to model existence
    model_loaded = model is not None and model.model is not None
    inference_healthy = getattr(model, "inference_healthy", False) if model else False

    # Status is only "healthy" if model is loaded AND inference has been validated
    if model_loaded and inference_healthy:
        status = "healthy"
    elif model_loaded and not inference_healthy:
        status = "unhealthy"  # Model loaded but inference failed
    else:
        status = "degraded"  # Model not loaded

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
        # NEM-3878: Include inference_tested field
        inference_tested=inference_healthy,
        # NEM-3877: Include active_backend field
        active_backend=getattr(model, "active_backend", None) if model else None,
    )


@app.get("/metrics")
async def metrics() -> Response:
    """Prometheus metrics endpoint.

    Returns metrics in Prometheus text format for scraping.
    Updates GPU metrics gauges before returning.
    """
    # Update model status gauge
    MODEL_LOADED.set(1 if model is not None and model.model is not None else 0)

    # NEM-3878: Update model inference health gauge
    inference_healthy = getattr(model, "inference_healthy", False) if model else False
    MODEL_INFERENCE_HEALTHY.set(1 if inference_healthy else 0)

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
        images = []
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
        for idx, (image, detections) in enumerate(zip(images, all_detections, strict=False)):
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


@app.post("/segment", response_model=SegmentationResponse)
async def segment_objects(
    file: UploadFile = File(None), image_base64: str | None = None
) -> SegmentationResponse:
    """Instance segmentation endpoint (NEM-3912).

    Performs object detection with instance-level segmentation masks.
    Useful for:
    - Privacy masking (blur/obscure detected persons)
    - Improved Re-ID embeddings (extract foreground only)
    - Precise object boundaries for analytics

    Accepts either:
    - Multipart file upload (file parameter)
    - Base64-encoded image (image_base64 parameter)

    Returns:
        Segmentation results with bounding boxes, confidence scores, and masks

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

        # Run segmentation with metrics tracking
        start_time = time.perf_counter()
        detections, inference_time_ms = model.segment(image)
        latency_seconds = time.perf_counter() - start_time

        # Record metrics
        record_inference(endpoint="segment", duration_seconds=latency_seconds, success=True)
        DETECTIONS_PER_IMAGE.observe(len(detections))

        # Record per-class detection counts
        record_detections(detections)

        return SegmentationResponse(
            detections=[SegmentationDetection(**d) for d in detections],
            inference_time_ms=inference_time_ms,
            image_width=img_width,
            image_height=img_height,
        )

    except HTTPException:
        record_inference(endpoint="segment", duration_seconds=0, success=False)
        record_error(error_type="http_error")
        raise
    except UnidentifiedImageError as e:
        record_inference(endpoint="segment", duration_seconds=0, success=False)
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
        record_inference(endpoint="segment", duration_seconds=0, success=False)
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
        record_inference(endpoint="segment", duration_seconds=0, success=False)
        record_error(error_type="segmentation_error")
        logger.error(f"Segmentation failed for {filename}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Segmentation failed: {e!s}") from e


# =============================================================================
# Pose Estimation Endpoints (NEM-3910)
# =============================================================================

# Global pose model instance
pose_model: Any = None


def get_pose_model():
    """Get or initialize the global pose model.

    Lazily initializes the pose model on first access.
    """
    global pose_model  # noqa: PLW0603

    if pose_model is None:
        try:
            from pose_estimation import YOLO26PoseModel

            pose_model_path = os.environ.get("YOLO26_POSE_MODEL_PATH", "yolo11n-pose.pt")
            pose_confidence = float(os.environ.get("YOLO26_POSE_CONFIDENCE", "0.5"))
            loitering_threshold = float(os.environ.get("LOITERING_THRESHOLD_SECONDS", "30"))
            device = "cuda:0" if torch.cuda.is_available() else "cpu"

            pose_model = YOLO26PoseModel(
                model_path=pose_model_path,
                confidence_threshold=pose_confidence,
                device=device,
                loitering_threshold_seconds=loitering_threshold,
            )
            pose_model.load_model()
            logger.info(f"Pose model loaded: {pose_model_path}")
        except Exception as e:
            logger.error(f"Failed to load pose model: {e}")
            raise

    return pose_model


@app.get("/pose/health")
async def pose_health_check():
    """Health check for pose estimation service.

    Returns:
        JSON with pose model status
    """
    try:
        pm = get_pose_model()
        return {
            "status": "healthy" if pm.inference_healthy else "unhealthy",
            "model_loaded": pm.model is not None,
            "model_path": pm.model_path,
            "device": pm.device,
            "inference_healthy": pm.inference_healthy,
        }
    except Exception as e:
        return {
            "status": "unavailable",
            "model_loaded": False,
            "error": str(e),
        }


@app.post("/pose/detect")
async def detect_poses(
    file: UploadFile = File(None),
    image_base64: str | None = None,
) -> JSONResponse:
    """Detect human poses in an image.

    NEM-3910: Pose estimation endpoint using YOLO-pose model.

    Accepts either:
    - Multipart file upload (file parameter)
    - Base64-encoded image (image_base64 parameter)

    Returns:
        JSON with pose detections including keypoints and behavior analysis

    Raises:
        HTTPException 400: Invalid image file
        HTTPException 413: Image size exceeds maximum
        HTTPException 503: Pose model not loaded
    """
    # Track filename for error reporting
    filename = file.filename if file else "base64_image"

    try:
        pm = get_pose_model()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Pose model not available: {e}") from e

    try:
        # Load image from file or base64
        if file:
            # Validate file extension
            ext_valid, ext_error = validate_file_extension(file.filename)
            if not ext_valid:
                raise HTTPException(
                    status_code=400, detail=f"Invalid file '{filename}': {ext_error}"
                )

            image_bytes = await file.read()
            if len(image_bytes) > MAX_IMAGE_SIZE_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail=f"Image size exceeds maximum ({MAX_IMAGE_SIZE_BYTES // (1024 * 1024)}MB)",
                )

            # Validate magic bytes
            magic_valid, magic_result = validate_image_magic_bytes(image_bytes)
            if not magic_valid:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid image file '{filename}': {magic_result}",
                )

            image = Image.open(io.BytesIO(image_bytes))
        elif image_base64:
            if len(image_base64) > MAX_BASE64_SIZE_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail="Base64 data exceeds maximum size",
                )
            try:
                image_bytes = base64.b64decode(image_base64)
            except binascii.Error as e:
                raise HTTPException(status_code=400, detail=f"Invalid base64: {e}") from e

            if len(image_bytes) > MAX_IMAGE_SIZE_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail="Decoded image exceeds maximum size",
                )

            magic_valid, magic_result = validate_image_magic_bytes(image_bytes)
            if not magic_valid:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid image: {magic_result}",
                )

            image = Image.open(io.BytesIO(image_bytes))
        else:
            raise HTTPException(status_code=400, detail="Either 'file' or 'image_base64' required")

        # Get image dimensions
        img_width, img_height = image.size

        # Run pose detection
        timestamp_ms = time.time() * 1000
        detections, inference_time_ms = pm.detect_poses(image, timestamp_ms=timestamp_ms)

        # Collect alerts from detections
        alerts = []
        for det in detections:
            behavior = det.get("behavior", {})
            person_id = det.get("person_id", 0)
            if behavior.get("is_fallen"):
                alerts.append(f"Fall detected (person {person_id})")
            if behavior.get("is_aggressive"):
                alerts.append(f"Aggressive behavior (person {person_id})")
            if behavior.get("is_loitering"):
                duration = behavior.get("loitering_duration_seconds", 0)
                alerts.append(f"Loitering detected (person {person_id}): {duration:.0f}s")

        return JSONResponse(
            content={
                "detections": detections,
                "inference_time_ms": inference_time_ms,
                "image_width": img_width,
                "image_height": img_height,
                "alerts": alerts,
            }
        )

    except HTTPException:
        raise
    except UnidentifiedImageError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid image file '{filename}': Cannot identify format",
        ) from e
    except Exception as e:
        logger.error(f"Pose detection failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Pose detection failed: {e!s}") from e


@app.post("/pose/analyze")
async def analyze_poses(
    file: UploadFile = File(None),
    image_base64: str | None = None,
) -> JSONResponse:
    """Analyze poses for security-relevant behaviors.

    NEM-3910: Behavior analysis endpoint that detects:
    - Falls (person lying horizontally)
    - Aggressive behavior (raised arms, rapid movement)
    - Loitering (stationary person exceeding time threshold)

    This is an alias for /pose/detect with emphasis on behavior analysis.
    """
    return await detect_poses(file=file, image_base64=image_base64)


if __name__ == "__main__":
    import uvicorn

    # Default to 0.0.0.0 to allow connections from Docker/Podman containers.
    # When AI servers run natively on host while backend runs in containers,
    # binding to 127.0.0.1 would prevent container-to-host connectivity.
    host = os.getenv("HOST", "0.0.0.0")  # noqa: S104
    port = int(os.getenv("PORT", "8095"))
    uvicorn.run(app, host=host, port=port, log_level="info")
