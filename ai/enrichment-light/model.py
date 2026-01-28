"""Lightweight Enrichment Service for GPU 1 (A400 4GB).

HTTP server hosting small, efficient models suitable for the secondary GPU:
- Pose Estimator: YOLOv8n-pose (~300MB, TensorRT-optimized)
- Threat Detector: YOLOv8n weapon detection (~400MB, TensorRT-optimized)
- Person Re-ID: OSNet-x0.25 embeddings (~100MB)
- Pet Classifier: Cat/dog classification (~200MB)
- Depth Estimator: Monocular depth estimation (~150MB)

Port: 8096 (configurable via PORT env var)
Expected VRAM: ~1.2GB total (with TensorRT optimization)
"""

import asyncio
import base64
import binascii
import io
import logging
import os
import sys
import time
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import torch
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from PIL import Image, UnidentifiedImageError
from prometheus_client import Counter, Gauge, Histogram, generate_latest
from pydantic import BaseModel, Field

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# =============================================================================
# Pyroscope Continuous Profiling (NEM-3921)
# =============================================================================
def init_profiling() -> None:
    """Initialize Pyroscope continuous profiling for ai-enrichment-light service.

    This function configures Pyroscope for continuous CPU profiling of the
    lightweight enrichment service. It enables identification of performance
    bottlenecks in model inference and request handling.

    Configuration is via environment variables:
    - PYROSCOPE_ENABLED: Enable/disable profiling (default: true)
    - PYROSCOPE_URL: Pyroscope server address (default: http://pyroscope:4040)
    - SERVICE_NAME: Service name in Pyroscope (default: ai-enrichment-light)
    - GPU_TIER: GPU tier tag for filtering (default: light)
    - ENVIRONMENT: Environment tag (default: production)

    The function gracefully handles:
    - Missing pyroscope-io package (ImportError)
    - Unsupported Python versions (pyroscope-io native lib requires Python 3.9-3.12)
    - Configuration errors (logs warning, doesn't fail startup)
    """
    if os.getenv("PYROSCOPE_ENABLED", "true").lower() != "true":
        logger.info("Pyroscope profiling disabled (PYROSCOPE_ENABLED != true)")
        return

    # pyroscope-io native library is compiled for Python 3.9-3.12
    # Python 3.13+ has ABI changes that cause SIGABRT crashes
    python_version = sys.version_info[:2]
    if python_version >= (3, 13):
        logger.info(
            f"Pyroscope profiling skipped: Python {python_version[0]}.{python_version[1]} "
            "not supported by pyroscope-io native library (requires 3.9-3.12)"
        )
        return

    try:
        import pyroscope

        service_name = os.getenv("SERVICE_NAME", "ai-enrichment-light")
        pyroscope_server = os.getenv("PYROSCOPE_URL", "http://pyroscope:4040")

        pyroscope.configure(
            application_name=service_name,
            server_address=pyroscope_server,
            tags={
                "service": service_name,
                "environment": os.getenv("ENVIRONMENT", "production"),
                "gpu_tier": os.getenv("GPU_TIER", "light"),
            },
            oncpu=True,
            gil_only=False,  # Profile all threads, not just GIL-holding threads
            enable_logging=True,
        )
        logger.info(f"Pyroscope profiling initialized: {service_name} -> {pyroscope_server}")
    except ImportError:
        logger.debug("Pyroscope profiling skipped: pyroscope-io not installed")
    except Exception as e:
        logger.warning(f"Failed to initialize Pyroscope profiling: {e}")


# Initialize profiling early (before model loading)
init_profiling()

# Track service start time for uptime calculation
SERVICE_START_TIME = datetime.now(UTC)

# =============================================================================
# Prometheus Metrics
# =============================================================================
INFERENCE_REQUESTS_TOTAL = Counter(
    "enrichment_light_inference_requests_total",
    "Total number of inference requests",
    ["endpoint", "status"],
)

INFERENCE_LATENCY_SECONDS = Histogram(
    "enrichment_light_inference_latency_seconds",
    "Inference latency in seconds",
    ["endpoint"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)

GPU_MEMORY_USED_GB = Gauge(
    "enrichment_light_gpu_memory_used_gb",
    "GPU memory used in GB",
)

MODEL_LOADED = Gauge(
    "enrichment_light_model_loaded",
    "Whether a model is loaded (1) or not (0)",
    ["model"],
)

# Size limits for image uploads
MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024  # 10MB
MAX_BASE64_SIZE_BYTES = int(MAX_IMAGE_SIZE_BYTES * 4 / 3) + 100


def validate_model_path(path: str) -> str:
    """Validate model path to prevent path traversal attacks."""
    if ".." in path:
        raise ValueError(f"Invalid model path: path traversal sequences not allowed: {path}")
    if path.startswith("/") or path.startswith("./"):
        return str(Path(path).resolve())
    return path


# =============================================================================
# Pet Classifier (ResNet-18)
# =============================================================================
PET_LABELS = ["cat", "dog"]


class PetClassifier:
    """ResNet-18 Cat/Dog classification model wrapper."""

    def __init__(self, model_path: str, device: str = "cuda:0"):
        self.model_path = validate_model_path(model_path)
        self.device = device
        self.model: Any = None
        self.processor: Any = None
        logger.info(f"Initializing PetClassifier from {self.model_path}")

    def load_model(self) -> None:
        """Load the ResNet-18 pet classifier model."""
        from transformers import AutoImageProcessor, AutoModelForImageClassification

        logger.info("Loading Pet Classifier model...")
        self.processor = AutoImageProcessor.from_pretrained(self.model_path)
        self.model = AutoModelForImageClassification.from_pretrained(self.model_path)

        if "cuda" in self.device and torch.cuda.is_available():
            self.model = self.model.to(self.device).half()
            logger.info(f"PetClassifier loaded on {self.device} with fp16")
        else:
            self.device = "cpu"
            logger.info("PetClassifier using CPU")

        self.model.eval()
        logger.info("PetClassifier loaded successfully")

    def classify(self, image: Image.Image) -> dict[str, Any]:
        """Classify whether an image contains a cat or dog."""
        if self.model is None or self.processor is None:
            raise RuntimeError("Model not loaded")

        inputs = self.processor(images=image, return_tensors="pt")
        model_dtype = next(self.model.parameters()).dtype
        if next(self.model.parameters()).is_cuda:
            inputs = {k: v.to(self.device, model_dtype) for k, v in inputs.items()}

        with torch.inference_mode():
            outputs = self.model(**inputs)
            logits = outputs.logits

        probs = torch.nn.functional.softmax(logits, dim=-1)[0]
        pred_idx = int(probs.argmax().item())
        confidence = float(probs[pred_idx].item())

        if hasattr(self.model.config, "id2label") and self.model.config.id2label:
            raw_label = self.model.config.id2label.get(str(pred_idx), PET_LABELS[pred_idx])
            if raw_label.endswith("s"):
                raw_label = raw_label[:-1]
        else:
            raw_label = PET_LABELS[pred_idx]

        return {
            "pet_type": raw_label,
            "breed": "unknown",
            "confidence": round(confidence, 4),
            "is_household_pet": True,
            "cat_score": round(float(probs[0].item()), 4),
            "dog_score": round(float(probs[1].item()), 4),
        }

    def unload(self) -> None:
        """Unload model and free memory."""
        if self.model is not None:
            del self.model
            self.model = None
        if self.processor is not None:
            del self.processor
            self.processor = None
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


# =============================================================================
# Depth Estimator (Depth Anything V2 Small)
# =============================================================================
class DepthEstimator:
    """Depth Anything V2 Small monocular depth estimation model wrapper."""

    def __init__(self, model_path: str, device: str = "cuda:0"):
        self.model_path = validate_model_path(model_path)
        self.device = device
        self.model: Any = None
        self.processor: Any = None
        logger.info(f"Initializing DepthEstimator from {self.model_path}")

    def load_model(self) -> None:
        """Load the Depth Anything V2 model."""
        from transformers import AutoImageProcessor, AutoModelForDepthEstimation

        logger.info("Loading Depth Anything V2 model...")
        self.processor = AutoImageProcessor.from_pretrained(self.model_path)
        self.model = AutoModelForDepthEstimation.from_pretrained(self.model_path)

        if "cuda" in self.device and torch.cuda.is_available():
            self.model = self.model.to(self.device)
            logger.info(f"DepthEstimator loaded on {self.device}")
        else:
            self.device = "cpu"
            logger.info("DepthEstimator using CPU")

        self.model.eval()
        logger.info("DepthEstimator loaded successfully")

    def estimate_depth(self, image: Image.Image) -> dict[str, Any]:
        """Estimate depth map for an image."""
        if self.model is None or self.processor is None:
            raise RuntimeError("Model not loaded")

        rgb_image = image.convert("RGB") if image.mode != "RGB" else image
        inputs = self.processor(images=rgb_image, return_tensors="pt")
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        with torch.inference_mode():
            outputs = self.model(**inputs)
            predicted_depth = outputs.predicted_depth

        prediction = torch.nn.functional.interpolate(
            predicted_depth.unsqueeze(1),
            size=rgb_image.size[::-1],
            mode="bicubic",
            align_corners=False,
        ).squeeze()

        depth_array = prediction.cpu().numpy()
        min_val = float(depth_array.min())
        max_val = float(depth_array.max())

        if max_val - min_val > 0:
            normalized_depth = (depth_array - min_val) / (max_val - min_val)
        else:
            normalized_depth = np.zeros_like(depth_array)

        depth_uint8 = (normalized_depth * 255).astype(np.uint8)
        depth_image = Image.fromarray(depth_uint8, mode="L")

        buffer = io.BytesIO()
        depth_image.save(buffer, format="PNG")
        depth_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

        return {
            "depth_map_base64": depth_base64,
            "min_depth": round(min_val, 4),
            "max_depth": round(max_val, 4),
            "mean_depth": round(float(np.mean(normalized_depth)), 4),
        }

    def unload(self) -> None:
        """Unload model and free memory."""
        if self.model is not None:
            del self.model
            self.model = None
        if self.processor is not None:
            del self.processor
            self.processor = None
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


# =============================================================================
# Global Model Instances
# =============================================================================
# Models can be loaded resident at startup or on-demand based on ENRICHMENT_PRELOAD_MODELS
pose_estimator: Any = None
threat_detector: Any = None
person_reid: Any = None
pet_classifier: PetClassifier | None = None
depth_estimator: DepthEstimator | None = None


def get_device() -> str:
    """Get the CUDA device to use."""
    if torch.cuda.is_available():
        return "cuda:0"
    return "cpu"


def _should_load_model(model_name: str) -> bool:
    """Check if a model should be loaded on this service based on configuration.

    Configuration is driven by ENRICHMENT_<MODEL>_SERVICE environment variables.
    Models default to 'light' service for this lightweight enrichment service.

    Args:
        model_name: Model identifier (pose, threat, reid, pet, depth)

    Returns:
        True if model should be loaded on this service
    """
    env_var = f"ENRICHMENT_{model_name.upper()}_SERVICE"
    service = os.environ.get(env_var, "light").lower()
    return service == "light"


def _should_preload_model(model_name: str) -> bool:
    """Check if a model should be preloaded at startup based on ENRICHMENT_PRELOAD_MODELS.

    Args:
        model_name: Model identifier (pose_estimator, threat_detector, person_reid,
                   pet_classifier, depth_estimator)

    Returns:
        True if model should be preloaded at startup
    """
    preload_models = os.environ.get("ENRICHMENT_PRELOAD_MODELS", "").strip()
    if not preload_models:
        # Empty means no preloading - all on-demand
        return False
    model_list = [m.strip() for m in preload_models.split(",") if m.strip()]
    return model_name in model_list


def load_all_models() -> None:
    """Load models assigned to this service based on preload configuration.

    Model assignment is controlled via environment variables:
    - ENRICHMENT_POSE_SERVICE: 'light' or 'heavy' (default: 'light')
    - ENRICHMENT_THREAT_SERVICE: 'light' or 'heavy' (default: 'light')
    - ENRICHMENT_REID_SERVICE: 'light' or 'heavy' (default: 'light')
    - ENRICHMENT_PET_SERVICE: 'light' or 'heavy' (default: 'light')
    - ENRICHMENT_DEPTH_SERVICE: 'light' or 'heavy' (default: 'light')

    Preloading (resident vs on-demand) is controlled via:
    - ENRICHMENT_PRELOAD_MODELS: comma-separated list of models to load at startup
      Available: pose_estimator, threat_detector, person_reid, pet_classifier, depth_estimator

    Only models assigned to 'light' AND listed in ENRICHMENT_PRELOAD_MODELS will be loaded.
    """
    global pose_estimator, threat_detector, person_reid, pet_classifier, depth_estimator

    device = get_device()
    preload_config = os.environ.get("ENRICHMENT_PRELOAD_MODELS", "")
    logger.info(f"Loading models on {device}... (preload config: '{preload_config}')")

    # Load Pose Estimator (if assigned to light service AND in preload list)
    if _should_load_model("pose") and _should_preload_model("pose_estimator"):
        pose_path = os.environ.get("POSE_MODEL_PATH", "/models/yolov8n-pose/yolov8n-pose.pt")
        try:
            from models.pose_estimator import PoseEstimator

            pose_estimator = PoseEstimator(model_path=pose_path, device=device)
            pose_estimator.load_model()
            MODEL_LOADED.labels(model="pose_estimator").set(1)
            logger.info("Pose estimator loaded (resident)")
        except Exception as e:
            logger.error(f"Failed to load pose estimator: {e}")
            MODEL_LOADED.labels(model="pose_estimator").set(0)
    elif not _should_load_model("pose"):
        logger.info("Pose estimator skipped (assigned to heavy service)")
        MODEL_LOADED.labels(model="pose_estimator").set(0)
    else:
        logger.info("Pose estimator deferred (on-demand loading)")
        MODEL_LOADED.labels(model="pose_estimator").set(0)

    # Load Threat Detector (if assigned to light service AND in preload list)
    if _should_load_model("threat") and _should_preload_model("threat_detector"):
        threat_path = os.environ.get(
            "THREAT_MODEL_PATH", "/models/threat-detection-yolov8n/weights/best.pt"
        )
        try:
            from models.threat_detector import ThreatDetector

            threat_detector = ThreatDetector(model_path=threat_path, device=device)
            threat_detector.load_model()
            MODEL_LOADED.labels(model="threat_detector").set(1)
            logger.info("Threat detector loaded (resident)")
        except Exception as e:
            logger.error(f"Failed to load threat detector: {e}")
            MODEL_LOADED.labels(model="threat_detector").set(0)
    elif not _should_load_model("threat"):
        logger.info("Threat detector skipped (assigned to heavy service)")
        MODEL_LOADED.labels(model="threat_detector").set(0)
    else:
        logger.info("Threat detector deferred (on-demand loading)")
        MODEL_LOADED.labels(model="threat_detector").set(0)

    # Load Person Re-ID (if assigned to light service AND in preload list)
    if _should_load_model("reid") and _should_preload_model("person_reid"):
        reid_path = os.environ.get("REID_MODEL_PATH", "/models/osnet-x0-25/osnet_x0_25.pth")
        try:
            from models.person_reid import PersonReID

            person_reid = PersonReID(model_path=reid_path, device=device)
            person_reid.load_model()
            MODEL_LOADED.labels(model="person_reid").set(1)
            logger.info("Person Re-ID loaded (resident)")
        except Exception as e:
            logger.error(f"Failed to load person Re-ID: {e}")
            MODEL_LOADED.labels(model="person_reid").set(0)
    elif not _should_load_model("reid"):
        logger.info("Person Re-ID skipped (assigned to heavy service)")
        MODEL_LOADED.labels(model="person_reid").set(0)
    else:
        logger.info("Person Re-ID deferred (on-demand loading)")
        MODEL_LOADED.labels(model="person_reid").set(0)

    # Load Pet Classifier (if assigned to light service AND in preload list)
    if _should_load_model("pet") and _should_preload_model("pet_classifier"):
        pet_path = os.environ.get("PET_MODEL_PATH", "/models/pet-classifier")
        try:
            pet_classifier = PetClassifier(model_path=pet_path, device=device)
            pet_classifier.load_model()
            MODEL_LOADED.labels(model="pet_classifier").set(1)
            logger.info("Pet classifier loaded (resident)")
        except Exception as e:
            logger.error(f"Failed to load pet classifier: {e}")
            MODEL_LOADED.labels(model="pet_classifier").set(0)
    elif not _should_load_model("pet"):
        logger.info("Pet classifier skipped (assigned to heavy service)")
        MODEL_LOADED.labels(model="pet_classifier").set(0)
    else:
        logger.info("Pet classifier deferred (on-demand loading)")
        MODEL_LOADED.labels(model="pet_classifier").set(0)

    # Load Depth Estimator (if assigned to light service AND in preload list)
    if _should_load_model("depth") and _should_preload_model("depth_estimator"):
        depth_path = os.environ.get("DEPTH_MODEL_PATH", "/models/depth-anything-v2-small")
        try:
            depth_estimator = DepthEstimator(model_path=depth_path, device=device)
            depth_estimator.load_model()
            MODEL_LOADED.labels(model="depth_estimator").set(1)
            logger.info("Depth estimator loaded (resident)")
        except Exception as e:
            logger.error(f"Failed to load depth estimator: {e}")
            MODEL_LOADED.labels(model="depth_estimator").set(0)
    elif not _should_load_model("depth"):
        logger.info("Depth estimator skipped (assigned to heavy service)")
        MODEL_LOADED.labels(model="depth_estimator").set(0)
    else:
        logger.info("Depth estimator deferred (on-demand loading)")
        MODEL_LOADED.labels(model="depth_estimator").set(0)

    # Update GPU memory metric
    if torch.cuda.is_available():
        mem_used = torch.cuda.memory_allocated() / 1e9
        GPU_MEMORY_USED_GB.set(mem_used)
        logger.info(f"GPU memory used: {mem_used:.2f} GB")


def warmup_models() -> None:
    """Run warmup inference on all loaded models."""
    logger.info("Running model warmup...")
    dummy_image = Image.new("RGB", (640, 480), color=(128, 128, 128))

    if pose_estimator is not None:
        try:
            pose_estimator.estimate_pose(dummy_image)
            logger.info("Pose estimator warmup complete")
        except Exception as e:
            logger.warning(f"Pose estimator warmup failed: {e}")

    if threat_detector is not None:
        try:
            threat_detector.detect_threats(dummy_image)
            logger.info("Threat detector warmup complete")
        except Exception as e:
            logger.warning(f"Threat detector warmup failed: {e}")

    if person_reid is not None:
        try:
            person_reid.extract_embedding(dummy_image)
            logger.info("Person Re-ID warmup complete")
        except Exception as e:
            logger.warning(f"Person Re-ID warmup failed: {e}")

    if pet_classifier is not None:
        try:
            pet_classifier.classify(dummy_image)
            logger.info("Pet classifier warmup complete")
        except Exception as e:
            logger.warning(f"Pet classifier warmup failed: {e}")

    if depth_estimator is not None:
        try:
            depth_estimator.estimate_depth(dummy_image)
            logger.info("Depth estimator warmup complete")
        except Exception as e:
            logger.warning(f"Depth estimator warmup failed: {e}")

    logger.info("Model warmup complete")


# =============================================================================
# FastAPI Application
# =============================================================================
@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Application lifespan manager."""
    logger.info("Starting Lightweight Enrichment Service...")
    load_all_models()
    warmup_models()
    logger.info("Lightweight Enrichment Service ready")
    yield
    logger.info("Shutting down Lightweight Enrichment Service...")


app = FastAPI(
    title="Lightweight Enrichment Service",
    description="Small, efficient models for GPU 1 (A400 4GB)",
    version="1.0.0",
    lifespan=lifespan,
)


# =============================================================================
# Pydantic Models
# =============================================================================
class ImageRequest(BaseModel):
    """Request model for image-based endpoints."""

    image_base64: str = Field(..., description="Base64-encoded image data")


class PoseResponse(BaseModel):
    """Response model for pose estimation.

    Compatible with heavy service format for config-driven routing.
    """

    keypoints: list[dict[str, Any]] = Field(default_factory=list)
    posture: str = Field(default="unknown")
    alerts: list[str] = Field(default_factory=list, description="Security-relevant pose alerts")
    inference_time_ms: float = Field(default=0.0)


class ThreatResponse(BaseModel):
    """Response model for threat detection."""

    threats_detected: list[dict[str, Any]] = Field(default_factory=list)
    is_threat: bool = Field(default=False)
    max_confidence: float = Field(default=0.0)
    inference_time_ms: float = Field(default=0.0)


class ReIDResponse(BaseModel):
    """Response model for person re-identification."""

    embedding: list[float] = Field(default_factory=list)
    embedding_dim: int = Field(default=512)
    inference_time_ms: float = Field(default=0.0)


class PetResponse(BaseModel):
    """Response model for pet classification."""

    pet_type: str = Field(default="unknown")
    breed: str = Field(default="unknown")
    confidence: float = Field(default=0.0)
    is_household_pet: bool = Field(default=True)
    inference_time_ms: float = Field(default=0.0)


class DepthResponse(BaseModel):
    """Response model for depth estimation."""

    depth_map_base64: str = Field(default="")
    min_depth: float = Field(default=0.0)
    max_depth: float = Field(default=1.0)
    mean_depth: float = Field(default=0.5)
    inference_time_ms: float = Field(default=0.0)


class HealthResponse(BaseModel):
    """Response model for health check."""

    status: str
    models_loaded: dict[str, bool]
    gpu_available: bool
    gpu_memory_used_gb: float
    uptime_seconds: float


# =============================================================================
# Helper Functions
# =============================================================================
def decode_image(image_base64: str) -> Image.Image:
    """Decode base64 image data to PIL Image."""
    if len(image_base64) > MAX_BASE64_SIZE_BYTES:
        raise HTTPException(status_code=413, detail="Image too large")

    try:
        image_bytes = base64.b64decode(image_base64)
    except binascii.Error as e:
        raise HTTPException(status_code=400, detail=f"Invalid base64 encoding: {e}") from e

    try:
        image = Image.open(io.BytesIO(image_bytes))
        return image.convert("RGB")
    except UnidentifiedImageError as e:
        raise HTTPException(status_code=400, detail=f"Cannot identify image format: {e}") from e


# =============================================================================
# API Endpoints
# =============================================================================
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    gpu_mem = 0.0
    if torch.cuda.is_available():
        gpu_mem = torch.cuda.memory_allocated() / 1e9

    uptime = (datetime.now(UTC) - SERVICE_START_TIME).total_seconds()

    return HealthResponse(
        status="healthy",
        models_loaded={
            "pose_estimator": pose_estimator is not None,
            "threat_detector": threat_detector is not None,
            "person_reid": person_reid is not None,
            "pet_classifier": pet_classifier is not None,
            "depth_estimator": depth_estimator is not None,
        },
        gpu_available=torch.cuda.is_available(),
        gpu_memory_used_gb=round(gpu_mem, 3),
        uptime_seconds=round(uptime, 1),
    )


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(content=generate_latest(), media_type="text/plain")


@app.post("/pose-analyze", response_model=PoseResponse)
async def analyze_pose(request: ImageRequest):
    """Analyze body pose keypoints from an image.

    Endpoint name matches heavy service for config-driven routing compatibility.
    """
    if pose_estimator is None:
        raise HTTPException(status_code=503, detail="Pose estimator not loaded")

    start_time = time.perf_counter()
    try:
        image = decode_image(request.image_base64)
        result = await asyncio.to_thread(pose_estimator.estimate_pose, image)
        inference_ms = (time.perf_counter() - start_time) * 1000

        INFERENCE_REQUESTS_TOTAL.labels(endpoint="pose-analyze", status="success").inc()
        INFERENCE_LATENCY_SECONDS.labels(endpoint="pose-analyze").observe(inference_ms / 1000)

        # Convert PoseResult dataclass to response format
        keypoints = [
            {"name": kp.name, "x": kp.x, "y": kp.y, "confidence": kp.confidence}
            for kp in result.keypoints
        ]
        return PoseResponse(
            keypoints=keypoints,
            posture=result.pose_class,
            alerts=["suspicious_pose"] if result.is_suspicious else [],
            inference_time_ms=round(inference_ms, 2),
        )
    except HTTPException:
        raise
    except Exception as e:
        INFERENCE_REQUESTS_TOTAL.labels(endpoint="pose-analyze", status="error").inc()
        logger.error(f"Pose analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/threat-detect", response_model=ThreatResponse)
async def detect_threats(request: ImageRequest):
    """Detect weapons and threats in an image."""
    if threat_detector is None:
        raise HTTPException(status_code=503, detail="Threat detector not loaded")

    start_time = time.perf_counter()
    try:
        image = decode_image(request.image_base64)
        result = await asyncio.to_thread(threat_detector.detect_threats, image)
        inference_ms = (time.perf_counter() - start_time) * 1000

        INFERENCE_REQUESTS_TOTAL.labels(endpoint="threat-detect", status="success").inc()
        INFERENCE_LATENCY_SECONDS.labels(endpoint="threat-detect").observe(inference_ms / 1000)

        # Convert ThreatResult dataclass to response format
        threats = [t.to_dict() for t in result.threats]
        max_conf = max((t.confidence for t in result.threats), default=0.0)
        return ThreatResponse(
            threats_detected=threats,
            is_threat=result.has_threat,
            max_confidence=max_conf,
            inference_time_ms=round(inference_ms, 2),
        )
    except HTTPException:
        raise
    except Exception as e:
        INFERENCE_REQUESTS_TOTAL.labels(endpoint="threat-detect", status="error").inc()
        logger.error(f"Threat detection error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/person-reid", response_model=ReIDResponse)
async def extract_reid_embedding(request: ImageRequest):
    """Extract person re-identification embedding."""
    if person_reid is None:
        raise HTTPException(status_code=503, detail="Person Re-ID not loaded")

    start_time = time.perf_counter()
    try:
        image = decode_image(request.image_base64)
        result = await asyncio.to_thread(person_reid.extract_embedding, image)
        inference_ms = (time.perf_counter() - start_time) * 1000

        INFERENCE_REQUESTS_TOTAL.labels(endpoint="person-reid", status="success").inc()
        INFERENCE_LATENCY_SECONDS.labels(endpoint="person-reid").observe(inference_ms / 1000)

        embedding = result.get("embedding", [])
        return ReIDResponse(
            embedding=embedding,
            embedding_dim=len(embedding),
            inference_time_ms=round(inference_ms, 2),
        )
    except HTTPException:
        raise
    except Exception as e:
        INFERENCE_REQUESTS_TOTAL.labels(endpoint="person-reid", status="error").inc()
        logger.error(f"Person Re-ID error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/pet-classify", response_model=PetResponse)
async def classify_pet(request: ImageRequest):
    """Classify cat or dog from an image."""
    if pet_classifier is None:
        raise HTTPException(status_code=503, detail="Pet classifier not loaded")

    start_time = time.perf_counter()
    try:
        image = decode_image(request.image_base64)
        result = await asyncio.to_thread(pet_classifier.classify, image)
        inference_ms = (time.perf_counter() - start_time) * 1000

        INFERENCE_REQUESTS_TOTAL.labels(endpoint="pet-classify", status="success").inc()
        INFERENCE_LATENCY_SECONDS.labels(endpoint="pet-classify").observe(inference_ms / 1000)

        return PetResponse(
            pet_type=result.get("pet_type", "unknown"),
            breed=result.get("breed", "unknown"),
            confidence=result.get("confidence", 0.0),
            is_household_pet=result.get("is_household_pet", True),
            inference_time_ms=round(inference_ms, 2),
        )
    except HTTPException:
        raise
    except Exception as e:
        INFERENCE_REQUESTS_TOTAL.labels(endpoint="pet-classify", status="error").inc()
        logger.error(f"Pet classification error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/depth-estimate", response_model=DepthResponse)
async def estimate_depth(request: ImageRequest):
    """Estimate monocular depth from an image."""
    if depth_estimator is None:
        raise HTTPException(status_code=503, detail="Depth estimator not loaded")

    start_time = time.perf_counter()
    try:
        image = decode_image(request.image_base64)
        result = await asyncio.to_thread(depth_estimator.estimate_depth, image)
        inference_ms = (time.perf_counter() - start_time) * 1000

        INFERENCE_REQUESTS_TOTAL.labels(endpoint="depth-estimate", status="success").inc()
        INFERENCE_LATENCY_SECONDS.labels(endpoint="depth-estimate").observe(inference_ms / 1000)

        return DepthResponse(
            depth_map_base64=result.get("depth_map_base64", ""),
            min_depth=result.get("min_depth", 0.0),
            max_depth=result.get("max_depth", 1.0),
            mean_depth=result.get("mean_depth", 0.5),
            inference_time_ms=round(inference_ms, 2),
        )
    except HTTPException:
        raise
    except Exception as e:
        INFERENCE_REQUESTS_TOTAL.labels(endpoint="depth-estimate", status="error").inc()
        logger.error(f"Depth estimation error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


# =============================================================================
# Main Entry Point
# =============================================================================
if __name__ == "__main__":
    import uvicorn

    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8096"))

    logger.info(f"Starting Lightweight Enrichment Service on {host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="info")
