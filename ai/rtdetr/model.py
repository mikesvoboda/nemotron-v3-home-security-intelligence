"""RT-DETRv2 Inference Server

HTTP server wrapping RT-DETRv2 object detection model for home security monitoring.
Runs on NVIDIA CUDA for efficient inference on security camera images.

Uses HuggingFace Transformers for model loading and inference.

Port: 8001
Expected VRAM: ~3GB
"""

import base64
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
from PIL import Image
from pydantic import BaseModel, Field
from transformers import AutoImageProcessor, AutoModelForObjectDetection

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Security-relevant classes for home monitoring
SECURITY_CLASSES = {"person", "car", "truck", "dog", "cat", "bird", "bicycle", "motorcycle", "bus"}


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
    model_path = os.environ.get(
        "RTDETR_MODEL_PATH",
        "/export/ai_models/rt-detrv2/rtdetr_v2_r101vd"
    )
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
async def detect_objects(
    file: UploadFile = File(None), image_base64: str | None = None
) -> DetectionResponse:
    """Detect objects in an image.

    Accepts either:
    - Multipart file upload (file parameter)
    - Base64-encoded image (image_base64 parameter)

    Returns:
        Detection results with bounding boxes and confidence scores
    """
    if model is None or model.model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    try:
        # Load image from file or base64
        if file:
            image_bytes = await file.read()
            image = Image.open(io.BytesIO(image_bytes))
        elif image_base64:
            image_bytes = base64.b64decode(image_base64)
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
    except Exception as e:
        logger.error(f"Detection failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Detection failed: {e!s}") from e


@app.post("/detect/batch")
async def detect_objects_batch(files: list[UploadFile] = File(...)) -> JSONResponse:
    """Batch detection endpoint for multiple images.

    Args:
        files: List of image files to process

    Returns:
        JSON response with detections for each image
    """
    if model is None or model.model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    try:
        # Load all images
        images = []
        for file in files:
            image_bytes = await file.read()
            image = Image.open(io.BytesIO(image_bytes))
            images.append(image)

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

    except Exception as e:
        logger.error(f"Batch detection failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Batch detection failed: {e!s}") from e


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")  # noqa: S104
    port = int(os.getenv("PORT", "8001"))
    uvicorn.run(app, host=host, port=port, log_level="info")
