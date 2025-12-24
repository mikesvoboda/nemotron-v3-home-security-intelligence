"""RT-DETRv2 Inference Server

HTTP server wrapping RT-DETRv2 object detection model for home security monitoring.
Runs on NVIDIA CUDA for efficient inference on security camera images.

Port: 8001
Expected VRAM: ~4GB
"""

import base64
import io
import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import numpy as np
import onnxruntime as ort
import torch
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from PIL import Image
from pydantic import BaseModel, Field

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# COCO class names - filter to security-relevant classes
COCO_CLASSES = [
    "person",
    "bicycle",
    "car",
    "motorcycle",
    "airplane",
    "bus",
    "train",
    "truck",
    "boat",
    "traffic light",
    "fire hydrant",
    "stop sign",
    "parking meter",
    "bench",
    "bird",
    "cat",
    "dog",
    "horse",
    "sheep",
    "cow",
    "elephant",
    "bear",
    "zebra",
    "giraffe",
    "backpack",
    "umbrella",
    "handbag",
    "tie",
    "suitcase",
    "frisbee",
    "skis",
    "snowboard",
    "sports ball",
    "kite",
    "baseball bat",
    "baseball glove",
    "skateboard",
    "surfboard",
    "tennis racket",
    "bottle",
    "wine glass",
    "cup",
    "fork",
    "knife",
    "spoon",
    "bowl",
    "banana",
    "apple",
    "sandwich",
    "orange",
    "broccoli",
    "carrot",
    "hot dog",
    "pizza",
    "donut",
    "cake",
    "chair",
    "couch",
    "potted plant",
    "bed",
    "dining table",
    "toilet",
    "tv",
    "laptop",
    "mouse",
    "remote",
    "keyboard",
    "cell phone",
    "microwave",
    "oven",
    "toaster",
    "sink",
    "refrigerator",
    "book",
    "clock",
    "vase",
    "scissors",
    "teddy bear",
    "hair drier",
    "toothbrush",
]

# Security-relevant classes for home monitoring
SECURITY_CLASSES = {"person", "car", "truck", "dog", "cat", "bird", "bicycle", "motorcycle"}


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
    vram_used_gb: float | None = None


class RTDETRv2Model:
    """RT-DETRv2 model wrapper for object detection."""

    def __init__(
        self,
        model_path: str | Path,
        confidence_threshold: float = 0.5,
        device: str = "cuda:0",
        use_onnx: bool = True,
    ):
        """Initialize RT-DETRv2 model.

        Args:
            model_path: Path to model file (.onnx or .pth)
            confidence_threshold: Minimum confidence for detections
            device: Device to run inference on (cuda:0, cpu)
            use_onnx: Use ONNX Runtime for faster inference
        """
        self.model_path = Path(model_path)
        self.confidence_threshold = confidence_threshold
        self.device = device
        self.use_onnx = use_onnx
        self.model = None
        self.session = None
        self.input_size = (640, 640)  # RT-DETR typical input size

        logger.info(f"Initializing RT-DETRv2 model from {self.model_path}")
        logger.info(
            f"Device: {device}, Use ONNX: {use_onnx}, Confidence threshold: {confidence_threshold}"
        )

    def load_model(self) -> None:
        """Load the model into memory."""
        if not self.model_path.exists():
            raise FileNotFoundError(f"Model file not found: {self.model_path}")

        try:
            if self.use_onnx and self.model_path.suffix == ".onnx":
                self._load_onnx_model()
            else:
                self._load_pytorch_model()

            # Warmup inference
            self._warmup()
            logger.info("Model loaded and warmed up successfully")

        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise

    def _load_onnx_model(self) -> None:
        """Load ONNX model with ONNX Runtime."""
        logger.info("Loading ONNX model...")

        # Configure ONNX Runtime providers
        providers = []
        if "cuda" in self.device and torch.cuda.is_available():
            providers.append(
                (
                    "CUDAExecutionProvider",
                    {
                        "device_id": int(self.device.split(":")[-1]) if ":" in self.device else 0,
                        "arena_extend_strategy": "kSameAsRequested",
                        "cudnn_conv_algo_search": "DEFAULT",
                    },
                )
            )
        providers.append("CPUExecutionProvider")

        self.session = ort.InferenceSession(str(self.model_path), providers=providers)

        logger.info(f"ONNX Runtime providers: {self.session.get_providers()}")

    def _load_pytorch_model(self) -> None:
        """Load PyTorch model."""
        logger.info("Loading PyTorch model...")

        # This is a placeholder - actual RT-DETRv2 loading would use the specific model class
        # from the RT-DETR repository
        try:
            # Placeholder: Load a pretrained model
            # In production, this would load the actual RT-DETRv2 checkpoint
            self.model = torch.load(self.model_path, map_location=self.device)
            self.model.eval()

            if "cuda" in self.device and torch.cuda.is_available():
                self.model = self.model.to(self.device)

        except Exception as e:
            logger.error(f"PyTorch model loading failed: {e}")
            raise

    def _warmup(self, num_iterations: int = 5) -> None:
        """Warmup the model with dummy inputs."""
        logger.info(f"Warming up model with {num_iterations} iterations...")

        dummy_image = np.random.randint(0, 255, (*self.input_size, 3), dtype=np.uint8)
        dummy_pil = Image.fromarray(dummy_image)

        for i in range(num_iterations):
            try:
                _ = self.detect(dummy_pil)
                logger.info(f"Warmup iteration {i + 1}/{num_iterations} complete")
            except Exception as e:
                logger.warning(f"Warmup iteration {i + 1} failed: {e}")

        logger.info("Warmup complete")

    def preprocess_image(self, image: Image.Image) -> tuple[np.ndarray, tuple[int, int]]:
        """Preprocess image for model input.

        Args:
            image: PIL Image

        Returns:
            Tuple of (preprocessed image array, original size)
        """
        original_size = image.size  # (width, height)

        # Convert to RGB if needed
        if image.mode != "RGB":
            image = image.convert("RGB")

        # Resize to model input size
        image_resized = image.resize(self.input_size, Image.BILINEAR)

        # Convert to numpy array and normalize
        img_array = np.array(image_resized, dtype=np.float32)
        img_array = img_array / 255.0  # Normalize to [0, 1]

        # Transpose to CHW format (channels, height, width)
        img_array = np.transpose(img_array, (2, 0, 1))

        # Add batch dimension
        img_array = np.expand_dims(img_array, axis=0)

        return img_array, original_size

    def postprocess_detections(
        self, outputs: Any, original_size: tuple[int, int], image_size: tuple[int, int]
    ) -> list[dict[str, Any]]:
        """Postprocess model outputs to detection format.

        Args:
            outputs: Model output (ONNX or PyTorch)
            original_size: Original image size (width, height)
            image_size: Model input size (width, height)

        Returns:
            List of detection dictionaries
        """
        detections = []

        # Parse ONNX outputs
        if isinstance(outputs, list):
            # ONNX Runtime returns a list of arrays
            # RT-DETR typically outputs: [boxes, scores, labels]
            if len(outputs) >= 3:
                boxes = outputs[0]  # Shape: (batch, num_boxes, 4)
                scores = outputs[1]  # Shape: (batch, num_boxes)
                labels = outputs[2]  # Shape: (batch, num_boxes)

                # Process batch (assume batch_size=1)
                for box, score, label in zip(boxes[0], scores[0], labels[0], strict=False):
                    if score < self.confidence_threshold:
                        continue

                    # Convert label to class name
                    class_idx = int(label)
                    if class_idx >= len(COCO_CLASSES):
                        continue

                    class_name = COCO_CLASSES[class_idx]

                    # Filter to security-relevant classes
                    if class_name not in SECURITY_CLASSES:
                        continue

                    # Scale bounding box to original image size
                    x1, y1, x2, y2 = box
                    x1 = int(x1 * original_size[0] / image_size[0])
                    y1 = int(y1 * original_size[1] / image_size[1])
                    x2 = int(x2 * original_size[0] / image_size[0])
                    y2 = int(y2 * original_size[1] / image_size[1])

                    detections.append(
                        {
                            "class": class_name,
                            "confidence": float(score),
                            "bbox": {"x": x1, "y": y1, "width": x2 - x1, "height": y2 - y1},
                        }
                    )

        # Parse PyTorch outputs
        elif isinstance(outputs, dict):
            boxes = outputs.get("boxes", [])
            scores = outputs.get("scores", [])
            labels = outputs.get("labels", [])

            for box, score, label in zip(boxes, scores, labels, strict=False):
                if score < self.confidence_threshold:
                    continue

                class_idx = int(label)
                if class_idx >= len(COCO_CLASSES):
                    continue

                class_name = COCO_CLASSES[class_idx]

                if class_name not in SECURITY_CLASSES:
                    continue

                x1, y1, x2, y2 = box
                x1 = int(x1 * original_size[0] / image_size[0])
                y1 = int(y1 * original_size[1] / image_size[1])
                x2 = int(x2 * original_size[0] / image_size[0])
                y2 = int(y2 * original_size[1] / image_size[1])

                detections.append(
                    {
                        "class": class_name,
                        "confidence": float(score),
                        "bbox": {"x": x1, "y": y1, "width": x2 - x1, "height": y2 - y1},
                    }
                )

        return detections

    def detect(self, image: Image.Image) -> tuple[list[dict[str, Any]], float]:
        """Run object detection on an image.

        Args:
            image: PIL Image to detect objects in

        Returns:
            Tuple of (detections list, inference_time_ms)
        """
        start_time = time.perf_counter()

        # Preprocess
        img_array, original_size = self.preprocess_image(image)

        # Run inference
        if self.session is not None:
            # ONNX Runtime inference
            input_name = self.session.get_inputs()[0].name
            outputs = self.session.run(None, {input_name: img_array})
        elif self.model is not None:
            # PyTorch inference
            with torch.no_grad():
                img_tensor = torch.from_numpy(img_array)
                if "cuda" in self.device:
                    img_tensor = img_tensor.to(self.device)
                outputs = self.model(img_tensor)
        else:
            raise RuntimeError("Model not loaded")

        # Postprocess
        detections = self.postprocess_detections(outputs, original_size, self.input_size)

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
        # TODO: Implement true batch processing for better efficiency
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
        import pynvml

        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        info = pynvml.nvmlDeviceGetMemoryInfo(handle)
        return info.used / (1024**3)  # Convert to GB
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
    model_path = Path(
        os.getenv("MODEL_PATH", str(Path(__file__).parent / "rtdetrv2_r50vd.onnx"))
    ).expanduser()
    confidence_threshold = float(os.getenv("CONFIDENCE_THRESHOLD", "0.5"))
    device = os.getenv("DEVICE", "cuda:0" if torch.cuda.is_available() else "cpu")

    try:
        model = RTDETRv2Model(
            model_path=model_path,
            confidence_threshold=confidence_threshold,
            device=device,
            use_onnx=model_path.suffix == ".onnx",
        )
        model.load_model()
        logger.info("Model loaded successfully")
    except FileNotFoundError:
        logger.warning(f"Model file not found at {model_path}")
        logger.warning(
            "Server will start but detection endpoints will fail until model is available"
        )
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        logger.warning("Server will start but detection endpoints will fail")

    yield

    # Shutdown
    logger.info("Shutting down RT-DETRv2 Detection Server...")


# Create FastAPI app
app = FastAPI(
    title="RT-DETRv2 Detection Server",
    description="Object detection service for home security monitoring",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint."""
    cuda_available = torch.cuda.is_available()
    device = "cuda:0" if cuda_available else "cpu"
    vram_used = get_vram_usage() if cuda_available else None

    return HealthResponse(
        status="healthy" if model is not None else "degraded",
        model_loaded=model is not None,
        device=device,
        cuda_available=cuda_available,
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
    if model is None:
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
    if model is None:
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
