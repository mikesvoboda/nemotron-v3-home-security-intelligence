"""YOLO26 Inference Server

HTTP server wrapping YOLO26m TensorRT object detection model for home security monitoring.
Runs on NVIDIA CUDA with TensorRT acceleration for efficient inference on security camera images.

Uses Ultralytics YOLO for loading and running TensorRT engines.

Port: 8095 (configurable via PORT env var)
Expected VRAM: ~2GB

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
    torch_compile_enabled: bool | None = None
    torch_compile_mode: str | None = None


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
        """
        self.model_path = str(model_path)
        self.confidence_threshold = confidence_threshold
        self.device = device
        self.cache_clear_frequency = cache_clear_frequency
        self.cache_clear_count = 0  # Metric: total number of cache clears
        self.model: Any = None
        self.tensorrt_enabled = False

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
        logger.info(
            f"torch.compile enabled: {self.enable_torch_compile}, mode: {self.torch_compile_mode}"
        )

    def load_model(self) -> None:
        """Load the TensorRT model using Ultralytics YOLO."""
        try:
            logger.info("Loading YOLO26 TensorRT model with Ultralytics...")

            from ultralytics import YOLO

            # Load the TensorRT engine
            self.model = YOLO(self.model_path)

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
    """Health check endpoint."""
    cuda_available = torch.cuda.is_available()
    device = "cuda:0" if cuda_available else "cpu"
    vram_used = get_vram_usage() if cuda_available else None

    # Get GPU metrics (utilization, temperature, power) via pynvml
    gpu_metrics = get_gpu_metrics() if cuda_available else {}

    return HealthResponse(
        status="healthy" if model is not None and model.model is not None else "degraded",
        model_loaded=model is not None and model.model is not None,
        device=device,
        cuda_available=cuda_available,
        model_name=model.model_path if model else None,
        vram_used_gb=vram_used,
        gpu_utilization=gpu_metrics.get("gpu_utilization"),
        temperature=gpu_metrics.get("temperature"),
        power_watts=gpu_metrics.get("power_watts"),
        tensorrt_enabled=model.tensorrt_enabled if model else None,
        torch_compile_enabled=model._is_compiled if model else None,
        torch_compile_mode=model.torch_compile_mode if model and model._is_compiled else None,
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


if __name__ == "__main__":
    import uvicorn

    # Default to 0.0.0.0 to allow connections from Docker/Podman containers.
    # When AI servers run natively on host while backend runs in containers,
    # binding to 127.0.0.1 would prevent container-to-host connectivity.
    host = os.getenv("HOST", "0.0.0.0")  # noqa: S104
    port = int(os.getenv("PORT", "8095"))
    uvicorn.run(app, host=host, port=port, log_level="info")
