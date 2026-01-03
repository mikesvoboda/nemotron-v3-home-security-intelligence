"""RT-DETRv2 Inference Server

HTTP server wrapping RT-DETRv2 object detection model for home security monitoring.
Runs on NVIDIA CUDA for efficient inference on security camera images.

Uses HuggingFace Transformers for model loading and inference.

Port: 8090 (configurable via PORT env var)
Expected VRAM: ~3GB
"""

import base64
import binascii
import io
import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import torch
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field
from transformers import AutoImageProcessor, AutoModelForObjectDetection

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Security-relevant classes for home monitoring
SECURITY_CLASSES = {"person", "car", "truck", "dog", "cat", "bird", "bicycle", "motorcycle", "bus"}

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


def validate_image_magic_bytes(image_bytes: bytes) -> tuple[bool, str]:  # noqa: PLR0911, PLR0912
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

    class_name: str = Field(..., alias="class", description="Detected object class")
    confidence: float = Field(..., description="Detection confidence score (0-1)")
    bbox: BoundingBox = Field(..., description="Bounding box coordinates")

    class Config:
        populate_by_name = True


class DetectionResponse(BaseModel):
    """Response format for detection endpoint."""

    detections: list[Detection] = Field(
        default_factory=list, description="List of detected objects"
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


class RTDETRv2Model:
    """RT-DETRv2 model wrapper using HuggingFace Transformers."""

    def __init__(
        self,
        model_path: str | Path,
        confidence_threshold: float = 0.5,
        device: str = "cuda:0",
    ):
        """Initialize RT-DETRv2 model.

        Args:
            model_path: Path to HuggingFace model directory or model name
            confidence_threshold: Minimum confidence for detections
            device: Device to run inference on (cuda:0, cpu)
        """
        self.model_path = str(model_path)
        self.confidence_threshold = confidence_threshold
        self.device = device
        self.model = None
        self.processor = None

        logger.info(f"Initializing RT-DETRv2 model from {self.model_path}")
        logger.info(f"Device: {device}, Confidence threshold: {confidence_threshold}")

    def load_model(self) -> None:
        """Load the model into memory using HuggingFace Transformers."""
        try:
            logger.info("Loading RT-DETRv2 model with HuggingFace Transformers...")

            # Load image processor and model
            self.processor = AutoImageProcessor.from_pretrained(self.model_path)
            self.model = AutoModelForObjectDetection.from_pretrained(self.model_path)

            # Move model to device
            if "cuda" in self.device and torch.cuda.is_available():
                self.model = self.model.to(self.device)
                logger.info(f"Model loaded on {self.device}")
            else:
                self.device = "cpu"
                logger.info("CUDA not available, using CPU")

            # Set model to evaluation mode
            self.model.eval()

            # Warmup inference
            self._warmup()
            logger.info("Model loaded and warmed up successfully")

        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise

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

    def detect(self, image: Image.Image) -> tuple[list[dict[str, Any]], float]:
        """Run object detection on an image.

        Args:
            image: PIL Image to detect objects in

        Returns:
            Tuple of (detections list, inference_time_ms)
        """
        if self.model is None or self.processor is None:
            raise RuntimeError("Model not loaded")

        start_time = time.perf_counter()

        # Convert to RGB if needed
        if image.mode != "RGB":
            image = image.convert("RGB")

        original_size = image.size  # (width, height)

        # Preprocess image
        inputs = self.processor(images=image, return_tensors="pt")

        # Move inputs to device
        if "cuda" in self.device:
            inputs = {k: v.to(self.device) for k, v in inputs.items()}

        # Run inference
        with torch.no_grad():
            outputs = self.model(**inputs)

        # Post-process results
        target_sizes = torch.tensor([[original_size[1], original_size[0]]])  # height, width
        if "cuda" in self.device:
            target_sizes = target_sizes.to(self.device)

        results = self.processor.post_process_object_detection(
            outputs,
            target_sizes=target_sizes,
            threshold=self.confidence_threshold,
        )[0]

        # Convert to detection format
        detections = []
        for score, label, box in zip(
            results["scores"], results["labels"], results["boxes"], strict=False
        ):
            # Get class name from model config
            class_name = self.model.config.id2label[label.item()]

            # Filter to security-relevant classes
            if class_name not in SECURITY_CLASSES:
                continue

            # Convert box coordinates
            x1, y1, x2, y2 = box.tolist()
            detections.append(
                {
                    "class": class_name,
                    "confidence": float(score),
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

    def detect_batch(self, images: list[Image.Image]) -> tuple[list[list[dict[str, Any]]], float]:
        """Run batch object detection on multiple images.

        Args:
            images: List of PIL Images

        Returns:
            Tuple of (list of detections per image, total_inference_time_ms)
        """
        start_time = time.perf_counter()
        all_detections = []

        # Process each image
        for image in images:
            detections, _ = self.detect(image)
            all_detections.append(detections)

        total_time_ms = (time.perf_counter() - start_time) * 1000

        return all_detections, total_time_ms


# Global model instance
model: RTDETRv2Model | None = None


def get_vram_usage() -> float | None:
    """Get VRAM usage in GB."""
    try:
        if torch.cuda.is_available():
            return torch.cuda.memory_allocated() / (1024**3)
    except Exception as e:
        logger.warning(f"Failed to get VRAM usage: {e}")
    return None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Lifespan context manager for FastAPI app."""
    global model  # noqa: PLW0603

    # Startup
    logger.info("Starting RT-DETRv2 Detection Server...")

    # Load model configuration from environment or defaults
    model_path = os.environ.get("RTDETR_MODEL_PATH", "/export/ai_models/rt-detrv2/rtdetr_v2_r101vd")
    confidence_threshold = float(os.environ.get("RTDETR_CONFIDENCE", "0.5"))
    device = "cuda:0" if torch.cuda.is_available() else "cpu"

    try:
        model = RTDETRv2Model(
            model_path=model_path,
            confidence_threshold=confidence_threshold,
            device=device,
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
    logger.info("Shutting down RT-DETRv2 Detection Server...")
    if model is not None and hasattr(model, "model") and model.model is not None:
        del model.model
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


# Create FastAPI app
app = FastAPI(
    title="RT-DETRv2 Detection Server",
    description="Object detection service for home security monitoring using HuggingFace Transformers",
    version="2.0.0",
    lifespan=lifespan,
)


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint."""
    cuda_available = torch.cuda.is_available()
    device = "cuda:0" if cuda_available else "cpu"
    vram_used = get_vram_usage() if cuda_available else None

    return HealthResponse(
        status="healthy" if model is not None and model.model is not None else "degraded",
        model_loaded=model is not None and model.model is not None,
        device=device,
        cuda_available=cuda_available,
        model_name=model.model_path if model else None,
        vram_used_gb=vram_used,
    )


@app.post("/detect", response_model=DetectionResponse)
async def detect_objects(  # noqa: PLR0912
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

        # Run detection
        detections, inference_time_ms = model.detect(image)

        return DetectionResponse(
            detections=[Detection(**d) for d in detections],
            inference_time_ms=inference_time_ms,
            image_width=img_width,
            image_height=img_height,
        )

    except HTTPException:
        raise
    except UnidentifiedImageError as e:
        # Handle corrupted/invalid image files - return 400 Bad Request
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
        logger.warning(
            f"Corrupted image file received: {filename}. Error: {e}",
            extra={"source_file": filename, "error": str(e)},
        )
        raise HTTPException(
            status_code=400,
            detail=f"Corrupted image file '{filename}': {e!s}",
        ) from e
    except Exception as e:
        logger.error(f"Detection failed for {filename}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Detection failed: {e!s}") from e


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

        # Run batch detection
        all_detections, total_time_ms = model.detect_batch(images)

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
        raise
    except Exception as e:
        logger.error(f"Batch detection failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Batch detection failed: {e!s}") from e


if __name__ == "__main__":
    import uvicorn

    # Default to 0.0.0.0 to allow connections from Docker/Podman containers.
    # When AI servers run natively on host while backend runs in containers,
    # binding to 127.0.0.1 would prevent container-to-host connectivity.
    host = os.getenv("HOST", "0.0.0.0")  # noqa: S104
    port = int(os.getenv("PORT", "8090"))
    uvicorn.run(app, host=host, port=port, log_level="info")
