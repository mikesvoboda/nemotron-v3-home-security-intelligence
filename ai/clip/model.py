"""CLIP Embedding Server.

HTTP server wrapping CLIP ViT-L model for generating embeddings
used in entity re-identification across cameras.

Port: 8093 (configurable via PORT env var)
Expected VRAM: ~800MB (PyTorch) / ~600MB (TensorRT)

TensorRT Support:
    Set CLIP_USE_TENSORRT=true and CLIP_ENGINE_PATH=/path/to/engine.engine
    to use TensorRT acceleration (1.5-2x faster inference).
    TensorRT engine is auto-exported on first run if not found.
    Falls back to PyTorch automatically if TensorRT export fails or is unavailable.

Environment Variables:
    CLIP_MODEL_PATH: HuggingFace model path (default: /models/clip-vit-l)
    CLIP_USE_TENSORRT: Enable TensorRT backend (true/false, default: true)
    CLIP_ENGINE_PATH: Path to TensorRT engine (auto-generated if not exists)
    HOST: Bind address (default: 0.0.0.0)
    PORT: Server port (default: 8093)
    PYROSCOPE_ENABLED: Enable/disable profiling (default: true)
    PYROSCOPE_URL: Pyroscope server address (default: http://pyroscope:4040)
"""

import os


def init_profiling() -> None:
    """Initialize Pyroscope continuous profiling for CLIP embedding service.

    This function configures Pyroscope for continuous profiling of the CLIP
    service. It enables CPU profiling to identify performance bottlenecks
    in embedding extraction and image processing.

    Configuration is via environment variables:
    - PYROSCOPE_ENABLED: Enable/disable profiling (default: true)
    - PYROSCOPE_URL: Pyroscope server address (default: http://pyroscope:4040)
    - ENVIRONMENT: Environment tag for profiles (default: production)

    The function gracefully handles:
    - Missing pyroscope-io package (ImportError)
    - Unsupported Python versions (pyroscope-io native lib requires Python 3.9-3.12)
    - Configuration errors (logs warning, doesn't fail startup)
    """
    if os.getenv("PYROSCOPE_ENABLED", "true").lower() != "true":
        print("Pyroscope profiling disabled (PYROSCOPE_ENABLED != true)")
        return

    try:
        import pyroscope

        pyroscope_server = os.getenv("PYROSCOPE_URL", "http://pyroscope:4040")

        pyroscope.configure(
            application_name="ai-clip",
            server_address=pyroscope_server,
            tags={
                "service": "ai-clip",
                "environment": os.getenv("ENVIRONMENT", "production"),
            },
            oncpu=True,
            gil_only=False,  # Profile all threads, not just GIL-holding threads
            enable_logging=True,
        )
        print(f"Pyroscope profiling initialized: server={pyroscope_server}")
    except ImportError:
        print("Pyroscope profiling skipped: pyroscope-io not installed")
    except Exception as e:
        print(f"Failed to initialize Pyroscope profiling: {e}")


# Initialize profiling before any other imports to capture startup overhead
init_profiling()

import base64
import binascii
import io
import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from enum import Enum
from typing import Any

import torch
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from PIL import Image
from prometheus_client import Counter, Gauge, Histogram, generate_latest
from pydantic import BaseModel, Field, field_validator
from transformers import CLIPModel, CLIPProcessor

# =============================================================================
# Surveillance-Specific Prompt Templates for Ensembling (NEM-3029)
# =============================================================================
# These templates provide surveillance camera context to improve CLIP's
# zero-shot classification accuracy by 5-10%. The model was trained primarily
# on web images, so adding surveillance context helps bridge the domain gap.


class CameraType(str, Enum):
    """Camera types for template selection.

    Different camera types benefit from different prompt templates to match
    the visual characteristics of their footage.
    """

    STANDARD = "standard"  # General surveillance camera
    NIGHT_VISION = "night_vision"  # IR/night vision camera
    OUTDOOR = "outdoor"  # Outdoor security camera
    INDOOR = "indoor"  # Indoor security camera
    DOORBELL = "doorbell"  # Doorbell camera (typically wide-angle, elevated)


# Base surveillance templates used for all camera types
SURVEILLANCE_TEMPLATES: list[str] = [
    "a surveillance camera photo of {}",
    "a security camera image showing {}",
    "a CCTV footage frame of {}",
    "a home security camera view of {}",
    "a low resolution security camera image of {}",
]

# Camera-type-specific templates for optimized accuracy
CAMERA_TYPE_TEMPLATES: dict[CameraType, list[str]] = {
    CameraType.STANDARD: SURVEILLANCE_TEMPLATES,
    CameraType.NIGHT_VISION: [
        "a night vision camera image of {}",
        "an infrared security camera photo of {}",
        "a grayscale night vision footage of {}",
        "a low-light security camera view of {}",
        "an IR camera surveillance image of {}",
    ],
    CameraType.OUTDOOR: [
        "an outdoor security camera photo of {}",
        "a surveillance camera outdoor image of {}",
        "a driveway security camera view of {}",
        "a yard security camera footage of {}",
        "an exterior CCTV image of {}",
    ],
    CameraType.INDOOR: [
        "an indoor security camera photo of {}",
        "a home surveillance camera view of {}",
        "an interior CCTV footage of {}",
        "a room security camera image of {}",
        "an indoor monitoring camera view of {}",
    ],
    CameraType.DOORBELL: [
        "a doorbell camera photo of {}",
        "a front door security camera view of {}",
        "a porch camera surveillance image of {}",
        "an elevated doorbell camera footage of {}",
        "a wide-angle doorbell camera view of {}",
    ],
}

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# =============================================================================
# Prometheus Metrics
# =============================================================================
# Total inference requests
INFERENCE_REQUESTS_TOTAL = Counter(
    "clip_inference_requests_total",
    "Total number of inference requests",
    ["endpoint", "status"],
)

# Inference latency histogram (buckets tuned for typical inference times)
INFERENCE_LATENCY_SECONDS = Histogram(
    "clip_inference_latency_seconds",
    "Inference latency in seconds",
    ["endpoint"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)

# Model status gauge (1 = loaded, 0 = not loaded)
MODEL_LOADED = Gauge(
    "clip_model_loaded",
    "Whether the model is loaded (1) or not (0)",
)

# GPU metrics gauges
GPU_MEMORY_USED_GB = Gauge(
    "clip_gpu_memory_used_gb",
    "GPU memory used in GB",
)

# Backend type gauge (0 = pytorch, 1 = tensorrt)
BACKEND_TYPE = Gauge(
    "clip_backend_type",
    "Inference backend type (0=pytorch, 1=tensorrt)",
)

# Size limits for image uploads (10MB is reasonable for security camera images)
MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024  # 10MB
# Base64 encoding increases size by ~33%, so pre-decode limit is ~13.3MB
MAX_BASE64_SIZE_BYTES = int(MAX_IMAGE_SIZE_BYTES * 4 / 3) + 100  # ~13.3MB + padding

# Maximum image dimension (width or height) to prevent excessive memory usage (NEM-1358)
MAX_IMAGE_DIMENSION = 4096

# Allowed image formats for validation (NEM-1358)
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "GIF", "BMP", "WEBP", "MPO"}

# CLIP ViT-L embedding dimension
EMBEDDING_DIMENSION = 768


def validate_clip_max_batch_texts_size(value: int) -> int:
    """Validate CLIP_MAX_BATCH_TEXTS_SIZE environment variable at startup (NEM-1357).

    Args:
        value: The value to validate

    Returns:
        The validated value

    Raises:
        ValueError: If value is less than 1
    """
    if value < 1:
        raise ValueError(
            f"CLIP_MAX_BATCH_TEXTS_SIZE must be at least 1, got {value}. "
            "This controls the maximum number of text descriptions per batch request."
        )
    if value > 1000:
        logger.warning(
            f"CLIP_MAX_BATCH_TEXTS_SIZE is set to {value}, which exceeds 1000. "
            "Large batch sizes may cause memory issues or slow response times."
        )
    return value


# Maximum batch size for batch similarity requests to prevent resource exhaustion (NEM-1101)
# This limits the number of text descriptions that can be compared against a single image
# in one request. Configurable via environment variable.
_raw_max_batch_texts_size = int(os.environ.get("CLIP_MAX_BATCH_TEXTS_SIZE", "100"))
MAX_BATCH_TEXTS_SIZE = validate_clip_max_batch_texts_size(_raw_max_batch_texts_size)


class EmbedRequest(BaseModel):
    """Request format for embed endpoint."""

    image: str = Field(..., description="Base64 encoded image")

    @field_validator("image")
    @classmethod
    def validate_base64_image(cls, v: str) -> str:
        """Validate base64 image data (NEM-1358).

        Validates:
        - Base64 string size (must be <= ~13.3MB to decode to <= 10MB)
        - Valid base64 encoding
        - Decoded data is a valid image
        - Image dimensions <= 4096x4096
        - Image format is supported (JPEG, PNG, GIF, BMP, WebP)

        Args:
            v: Base64 encoded image string

        Returns:
            The validated base64 string

        Raises:
            ValueError: If validation fails
        """
        # Check base64 string size before decoding
        if len(v) > MAX_BASE64_SIZE_BYTES:
            raise ValueError(
                f"Base64 image data size ({len(v)} bytes) exceeds maximum allowed "
                f"({MAX_BASE64_SIZE_BYTES} bytes). Maximum decoded image size is "
                f"{MAX_IMAGE_SIZE_BYTES // (1024 * 1024)}MB."
            )

        # Try to decode base64
        try:
            image_bytes = base64.b64decode(v)
        except (binascii.Error, ValueError) as e:
            raise ValueError(
                f"Invalid base64 encoding: {e}. "
                "Please ensure the image data is properly base64 encoded."
            ) from e

        # Check decoded size
        if len(image_bytes) > MAX_IMAGE_SIZE_BYTES:
            raise ValueError(
                f"Decoded image size ({len(image_bytes)} bytes) exceeds maximum allowed "
                f"({MAX_IMAGE_SIZE_BYTES} bytes / {MAX_IMAGE_SIZE_BYTES // (1024 * 1024)}MB)."
            )

        # Try to open as an image
        try:
            image = Image.open(io.BytesIO(image_bytes))
        except Exception as e:
            raise ValueError(
                f"Invalid image data: could not decode as image. {e}. "
                "Please ensure the data is a valid image file (JPEG, PNG, GIF, BMP, WebP)."
            ) from e

        # Check image format
        if image.format and image.format.upper() not in ALLOWED_IMAGE_FORMATS:
            raise ValueError(
                f"Unsupported image format: {image.format}. "
                f"Supported formats are: {', '.join(sorted(ALLOWED_IMAGE_FORMATS))}."
            )

        # Check dimensions
        width, height = image.size
        if width > MAX_IMAGE_DIMENSION or height > MAX_IMAGE_DIMENSION:
            raise ValueError(
                f"Image dimensions ({width}x{height}) exceed maximum allowed "
                f"({MAX_IMAGE_DIMENSION}x{MAX_IMAGE_DIMENSION}). "
                "Please resize the image before uploading."
            )

        return v


class EmbedResponse(BaseModel):
    """Response format for embed endpoint."""

    embedding: list[float] = Field(..., description="768-dimensional CLIP embedding")
    inference_time_ms: float = Field(..., description="Inference time in milliseconds")


class AnomalyScoreRequest(BaseModel):
    """Request format for anomaly-score endpoint."""

    image: str = Field(..., description="Base64 encoded image to analyze")
    baseline_embedding: list[float] = Field(
        ..., description=f"{EMBEDDING_DIMENSION}-dimensional baseline embedding"
    )


class AnomalyScoreResponse(BaseModel):
    """Response format for anomaly-score endpoint."""

    anomaly_score: float = Field(
        ..., ge=0.0, le=1.0, description="Anomaly score (0 = normal, 1 = highly anomalous)"
    )
    similarity_to_baseline: float = Field(
        ..., ge=-1.0, le=1.0, description="Cosine similarity to baseline (-1 to 1)"
    )
    inference_time_ms: float = Field(..., description="Inference time in milliseconds")


class ClassifyRequest(BaseModel):
    """Request format for zero-shot classification endpoint."""

    image: str = Field(..., description="Base64 encoded image")
    labels: list[str] = Field(..., description="List of text labels to classify against")
    use_ensemble: bool = Field(
        default=True,
        description="Use prompt ensembling for improved accuracy (default: True)",
    )
    camera_type: CameraType = Field(
        default=CameraType.STANDARD,
        description="Camera type for template selection (only used when use_ensemble=True)",
    )


class ClassifyResponse(BaseModel):
    """Response format for zero-shot classification endpoint."""

    scores: dict[str, float] = Field(..., description="Classification scores for each label")
    top_label: str = Field(..., description="Label with highest score")
    inference_time_ms: float = Field(..., description="Inference time in milliseconds")
    ensemble_metadata: dict[str, Any] | None = Field(
        default=None,
        description="Ensemble details when use_ensemble=True (templates_used, num_templates, etc.)",
    )


class SimilarityRequest(BaseModel):
    """Request format for image-text similarity endpoint."""

    image: str = Field(..., description="Base64 encoded image")
    text: str = Field(..., description="Text description to compare against")


class SimilarityResponse(BaseModel):
    """Response format for image-text similarity endpoint."""

    similarity: float = Field(..., description="Cosine similarity score between image and text")
    inference_time_ms: float = Field(..., description="Inference time in milliseconds")


class BatchSimilarityRequest(BaseModel):
    """Request format for batch image-text similarity endpoint."""

    image: str = Field(..., description="Base64 encoded image")
    texts: list[str] = Field(..., description="List of text descriptions to compare against")

    @field_validator("texts")
    @classmethod
    def validate_batch_size(cls, v: list[str]) -> list[str]:
        """Validate that the batch size does not exceed the maximum allowed.

        This prevents resource exhaustion attacks through oversized batch requests.
        See NEM-1101 for details.
        """
        if len(v) > MAX_BATCH_TEXTS_SIZE:
            raise ValueError(
                f"Batch size {len(v)} exceeds maximum allowed size of {MAX_BATCH_TEXTS_SIZE}. "
                f"Please reduce the number of texts in your request."
            )
        return v


class BatchSimilarityResponse(BaseModel):
    """Response format for batch image-text similarity endpoint."""

    similarities: dict[str, float] = Field(
        ..., description="Similarity scores for each text description"
    )
    inference_time_ms: float = Field(..., description="Inference time in milliseconds")


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    model: str
    model_loaded: bool
    device: str
    cuda_available: bool
    vram_used_gb: float | None = None
    embedding_dimension: int = EMBEDDING_DIMENSION
    backend: str = "pytorch"  # 'pytorch' or 'tensorrt'
    tensorrt_engine_path: str | None = None


class CLIPEmbeddingModel:
    """CLIP ViT-L model wrapper for generating embeddings.

    Supports both PyTorch and TensorRT backends. TensorRT provides 1.5-2x
    speedup for embedding extraction but requires a pre-built engine file.

    Attributes:
        model_path: Path to HuggingFace model.
        device: CUDA device to use.
        use_tensorrt: Whether to use TensorRT backend.
        tensorrt_engine_path: Path to TensorRT engine (if TensorRT enabled).
        backend_type: Current backend type ('pytorch' or 'tensorrt').
    """

    def __init__(
        self,
        model_path: str,
        device: str = "cuda:0",
        use_tensorrt: bool | None = None,
        tensorrt_engine_path: str | None = None,
    ):
        """Initialize CLIP model.

        Args:
            model_path: Path to HuggingFace model directory or model name
            device: Device to run inference on (cuda:0, cpu)
            use_tensorrt: Use TensorRT backend. If None, reads from CLIP_USE_TENSORRT.
            tensorrt_engine_path: Path to TensorRT engine. If None, reads CLIP_ENGINE_PATH.
        """
        self.model_path = model_path
        self.device = device
        self.model: Any = None
        self.processor: Any = None

        # TensorRT backend objects
        self._tensorrt_backend: Any = None
        self.backend_type: str = "pytorch"

        # Determine TensorRT settings from params or environment
        if use_tensorrt is None:
            use_tensorrt = os.environ.get("CLIP_USE_TENSORRT", "false").lower() in (
                "true",
                "1",
                "yes",
            )
        self.use_tensorrt = use_tensorrt

        if tensorrt_engine_path is None:
            tensorrt_engine_path = os.environ.get("CLIP_ENGINE_PATH")
        self.tensorrt_engine_path = tensorrt_engine_path

        logger.info(f"Initializing CLIP model from {self.model_path}")
        logger.info(f"Device: {device}")
        logger.info(f"TensorRT enabled: {self.use_tensorrt}")
        if self.tensorrt_engine_path:
            logger.info(f"TensorRT engine: {self.tensorrt_engine_path}")

    def load_model(self) -> None:
        """Load the model into memory.

        If TensorRT is enabled and the engine file exists, uses TensorRT backend.
        Otherwise falls back to PyTorch with HuggingFace Transformers.
        """
        # Try TensorRT first if enabled
        if self.use_tensorrt and self.tensorrt_engine_path:
            if self._try_load_tensorrt():
                return  # Successfully loaded TensorRT

        # Fall back to PyTorch
        self._load_pytorch()

    def _auto_export_tensorrt(self) -> str | None:
        """Auto-export TensorRT engine if it doesn't exist.

        Exports the CLIP vision encoder to ONNX and converts to TensorRT.
        This is a one-time operation on first startup.

        Returns:
            Path to the TensorRT engine if successful, None otherwise.
        """
        try:
            from export_onnx import CLIPVisionONNXExporter, convert_to_tensorrt

            logger.info("TensorRT engine not found, attempting auto-export...")
            logger.info(f"  Model path: {self.model_path}")
            logger.info(f"  Target engine: {self.tensorrt_engine_path}")

            # Determine output directory from engine path
            from pathlib import Path

            engine_path = Path(self.tensorrt_engine_path)  # type: ignore[arg-type]
            output_dir = engine_path.parent
            onnx_path = output_dir / "vision_encoder.onnx"

            # Step 1: Export to ONNX if needed
            if not onnx_path.exists():
                logger.info("Step 1/2: Exporting CLIP vision encoder to ONNX...")
                exporter = CLIPVisionONNXExporter(model_path=self.model_path)
                exporter.load_model()
                exporter.export(
                    output_path=str(onnx_path),
                    dynamic_batch=True,
                    max_batch_size=8,
                )
                logger.info(f"ONNX export complete: {onnx_path}")
            else:
                logger.info(f"Step 1/2: ONNX model already exists: {onnx_path}")

            # Step 2: Convert to TensorRT
            logger.info("Step 2/2: Converting ONNX to TensorRT FP16...")
            result_path = convert_to_tensorrt(
                onnx_path=str(onnx_path),
                output_path=str(engine_path),
                precision="fp16",
                max_batch_size=8,
                workspace_gb=2,
            )

            logger.info(f"TensorRT engine exported successfully: {result_path}")
            return result_path

        except ImportError as e:
            logger.warning(f"TensorRT export dependencies not available: {e}")
            return None
        except Exception as e:
            logger.warning(f"TensorRT auto-export failed: {e}")
            logger.info("Falling back to PyTorch inference")
            return None

    def _try_load_tensorrt(self) -> bool:
        """Attempt to load TensorRT backend.

        If TensorRT engine doesn't exist, attempts to auto-export it.
        Falls back to PyTorch if export fails or TensorRT is unavailable.

        Returns:
            True if TensorRT loaded successfully, False otherwise.
        """
        try:
            # Check if engine file exists, auto-export if not
            if not os.path.exists(self.tensorrt_engine_path):  # type: ignore[arg-type]
                logger.info(f"TensorRT engine not found: {self.tensorrt_engine_path}")
                # Attempt auto-export
                exported_path = self._auto_export_tensorrt()
                if exported_path is None:
                    logger.warning("TensorRT auto-export failed, falling back to PyTorch")
                    return False
                # Update engine path if export returned a different path
                self.tensorrt_engine_path = exported_path

            # Import TensorRT backend
            from tensorrt_inference import CLIPTensorRTInference

            logger.info("Loading CLIP with TensorRT backend...")
            self._tensorrt_backend = CLIPTensorRTInference(
                engine_path=self.tensorrt_engine_path,  # type: ignore[arg-type]
                device=self.device,
            )
            self.backend_type = "tensorrt"

            # Still need processor for text encoding (classify, similarity endpoints)
            self.processor = CLIPProcessor.from_pretrained(self.model_path)

            logger.info("TensorRT backend loaded successfully")
            logger.info(f"  Engine: {self.tensorrt_engine_path}")
            logger.info(f"  Device: {self.device}")
            return True

        except ImportError as e:
            logger.warning(f"TensorRT import failed: {e}, falling back to PyTorch")
            return False
        except Exception as e:
            logger.warning(f"TensorRT load failed: {e}, falling back to PyTorch")
            return False

    def _load_pytorch(self) -> None:
        """Load PyTorch backend with HuggingFace Transformers."""
        try:
            logger.info("Loading CLIP model with HuggingFace Transformers (PyTorch)...")

            # Determine device and dtype
            if "cuda" in self.device and torch.cuda.is_available():
                dtype = torch.float16
            else:
                self.device = "cpu"
                dtype = torch.float32

            # Load processor
            self.processor = CLIPProcessor.from_pretrained(self.model_path)

            # Try to load with SDPA (Scaled Dot-Product Attention) for 15-40% faster inference
            # SDPA requires PyTorch 2.0+ and compatible hardware
            try:
                self.model = CLIPModel.from_pretrained(
                    self.model_path,
                    torch_dtype=dtype,
                    attn_implementation="sdpa",
                )
                logger.info("CLIP loaded with SDPA attention (optimized)")
            except (ValueError, ImportError) as e:
                # Fall back to default attention if SDPA is not supported
                logger.warning(f"SDPA not available, falling back to default attention: {e}")
                self.model = CLIPModel.from_pretrained(
                    self.model_path,
                    torch_dtype=dtype,
                )

            # Move model to device
            if "cuda" in self.device:
                self.model = self.model.to(self.device)
                logger.info(f"Model loaded on {self.device}")
            else:
                logger.info("CUDA not available, using CPU")

            # Set model to evaluation mode
            self.model.eval()
            self.backend_type = "pytorch"

            # Warmup inference
            self._warmup()
            logger.info("PyTorch backend loaded and warmed up successfully")

        except Exception as e:
            logger.error(f"Failed to load PyTorch model: {e}")
            raise

    def _warmup(self, num_iterations: int = 3) -> None:
        """Warmup the model with dummy inputs."""
        logger.info(f"Warming up model with {num_iterations} iterations...")

        # Create a dummy image
        dummy_image = Image.new("RGB", (224, 224), color=(128, 128, 128))

        for i in range(num_iterations):
            try:
                _ = self.extract_embedding(dummy_image)
                logger.info(f"Warmup iteration {i + 1}/{num_iterations} complete")
            except Exception as e:
                logger.warning(f"Warmup iteration {i + 1} failed: {e}")

        logger.info("Warmup complete")

    @staticmethod
    def _extract_features_tensor(features: Any) -> torch.Tensor:
        """Extract tensor from model output (handles transformers 5.0+ API changes).

        In transformers 5.0+, get_image_features() and get_text_features() return
        BaseModelOutputWithPooling objects instead of raw tensors. This helper
        handles both the old (tensor) and new (object) return types.

        Args:
            features: Output from get_image_features() or get_text_features(),
                     can be a tensor (transformers <5.0) or BaseModelOutputWithPooling
                     (transformers >=5.0).

        Returns:
            The features as a torch.Tensor.

        Raises:
            TypeError: If features type is not recognized.
        """
        # Direct tensor return type (older transformers versions)
        if isinstance(features, torch.Tensor):
            return features

        # Object return type with pooler_output attribute (transformers 5.0+)
        if hasattr(features, "pooler_output") and features.pooler_output is not None:
            return features.pooler_output
        elif hasattr(features, "last_hidden_state"):
            # Fallback to CLS token from last_hidden_state
            return features.last_hidden_state[:, 0, :]
        else:
            raise TypeError(f"Unexpected features type: {type(features)}. Cannot extract tensor.")

    def extract_embedding(self, image: Image.Image) -> tuple[list[float], float]:
        """Generate a 768-dimensional embedding from an image.

        Uses TensorRT backend if available, otherwise PyTorch.

        Args:
            image: PIL Image to process

        Returns:
            Tuple of (embedding list, inference_time_ms)
        """
        # Use TensorRT backend if available
        if self._tensorrt_backend is not None:
            result: tuple[list[float], float] = self._tensorrt_backend.extract_embedding(image)
            return result

        # PyTorch backend
        if self.model is None or self.processor is None:
            raise RuntimeError("Model not loaded")

        start_time = time.perf_counter()

        # Convert to RGB if needed
        if image.mode != "RGB":
            image = image.convert("RGB")

        # Preprocess image
        inputs = self.processor(images=image, return_tensors="pt")

        # Move inputs to device with correct dtype
        model_dtype = next(self.model.parameters()).dtype
        inputs = {k: v.to(self.device, model_dtype) for k, v in inputs.items()}

        # Generate embedding
        with torch.inference_mode():
            raw_features = self.model.get_image_features(**inputs)
            image_features = self._extract_features_tensor(raw_features)

            # Normalize embedding with epsilon to prevent division by zero (NEM-1100)
            epsilon = 1e-8
            image_features = image_features / (
                torch.norm(image_features, p=2, dim=-1, keepdim=True) + epsilon
            )

        # Convert to list
        embedding: list[float] = image_features[0].cpu().float().numpy().tolist()

        inference_time_ms = (time.perf_counter() - start_time) * 1000

        return embedding, inference_time_ms

    def compute_anomaly_score(
        self, image: Image.Image, baseline_embedding: list[float]
    ) -> tuple[float, float, float]:
        """Compute anomaly score by comparing image embedding to baseline.

        The anomaly score is computed as: 1 - cosine_similarity
        This means:
        - 0.0 = identical to baseline (no anomaly)
        - 1.0 = completely different from baseline (high anomaly)
        - 2.0 = opposite direction (theoretically maximum anomaly)

        In practice, scores are clamped to [0, 1] for usability.
        Uses TensorRT backend if available.

        Args:
            image: PIL Image to analyze
            baseline_embedding: 768-dimensional baseline embedding to compare against

        Returns:
            Tuple of (anomaly_score, similarity, inference_time_ms)
        """
        # Use TensorRT backend if available
        if self._tensorrt_backend is not None:
            result: tuple[float, float, float] = self._tensorrt_backend.compute_anomaly_score(
                image, baseline_embedding
            )
            return result

        start_time = time.perf_counter()

        # Extract embedding for current image (PyTorch path)
        current_embedding, _ = self.extract_embedding(image)

        # Convert to tensors for cosine similarity computation
        current_tensor = torch.tensor(current_embedding, dtype=torch.float32)
        baseline_tensor = torch.tensor(baseline_embedding, dtype=torch.float32)

        # Ensure embeddings are normalized (they should be from extract_embedding)
        # Add epsilon to prevent division by zero for zero vectors (NEM-1100)
        epsilon = 1e-8
        current_norm = current_tensor / (current_tensor.norm(p=2) + epsilon)
        baseline_norm = baseline_tensor / (baseline_tensor.norm(p=2) + epsilon)

        # Compute cosine similarity (dot product of normalized vectors)
        similarity = float(torch.dot(current_norm, baseline_norm).item())

        # Compute anomaly score: 1 - similarity, clamped to [0, 1]
        # similarity of 1.0 -> anomaly of 0.0 (identical)
        # similarity of 0.0 -> anomaly of 1.0 (orthogonal)
        # similarity of -1.0 -> anomaly of 2.0, but we clamp to 1.0
        anomaly_score = max(0.0, min(1.0, 1.0 - similarity))

        inference_time_ms = (time.perf_counter() - start_time) * 1000

        return anomaly_score, similarity, inference_time_ms

    def classify(
        self, image: Image.Image, labels: list[str]
    ) -> tuple[dict[str, float], str, float]:
        """Classify an image against a list of text labels using zero-shot classification.

        Uses CLIP's text encoder and image encoder to compute similarity scores,
        then applies softmax to normalize scores to sum to 1.0.

        Args:
            image: PIL Image to classify
            labels: List of text labels to classify against

        Returns:
            Tuple of (scores dict, top_label, inference_time_ms)
        """
        if self.model is None or self.processor is None:
            raise RuntimeError("Model not loaded")

        if not labels:
            raise ValueError("Labels list cannot be empty")

        start_time = time.perf_counter()

        # Convert to RGB if needed
        if image.mode != "RGB":
            image = image.convert("RGB")

        # Preprocess image and text
        inputs = self.processor(
            images=image,
            text=labels,
            return_tensors="pt",
            padding=True,
        )

        # Move inputs to device with correct dtype
        model_dtype = next(self.model.parameters()).dtype
        inputs = {k: v.to(self.device, model_dtype) for k, v in inputs.items()}

        # Generate logits
        with torch.inference_mode():
            outputs = self.model(**inputs)
            logits_per_image = outputs.logits_per_image

            # Apply softmax to normalize scores
            probs = torch.softmax(logits_per_image, dim=-1)

        # Convert to dict
        scores_list = probs[0].cpu().float().numpy().tolist()
        scores = dict(zip(labels, scores_list, strict=True))

        # Find top label
        top_idx = int(probs[0].argmax().item())
        top_label = labels[top_idx]

        inference_time_ms = (time.perf_counter() - start_time) * 1000

        return scores, top_label, inference_time_ms

    def classify_with_ensemble(
        self,
        image: Image.Image,
        labels: list[str],
        camera_type: CameraType = CameraType.STANDARD,
        templates: list[str] | None = None,
    ) -> tuple[dict[str, float], str, float, dict[str, Any]]:
        """Classify an image using prompt template ensembling for improved accuracy.

        This method improves zero-shot classification accuracy by 5-10% by:
        1. Using surveillance-context prompt templates instead of bare labels
        2. Averaging embeddings across multiple template variations
        3. Optionally using camera-type-specific templates

        The ensemble approach helps bridge the domain gap between CLIP's training
        data (primarily web images) and surveillance footage.

        Args:
            image: PIL Image to classify
            labels: List of text labels to classify against
            camera_type: Type of camera for template selection (default: STANDARD)
            templates: Optional custom templates (overrides camera_type selection).
                      Must contain '{}' placeholder for the label.

        Returns:
            Tuple of:
            - scores: dict mapping labels to probabilities (sum to 1.0)
            - top_label: label with highest score
            - inference_time_ms: total inference time
            - metadata: dict with ensemble details (templates_used, num_templates)
        """
        if self.model is None or self.processor is None:
            raise RuntimeError("Model not loaded")

        if not labels:
            raise ValueError("Labels list cannot be empty")

        start_time = time.perf_counter()

        # Select templates based on camera type or use custom templates
        selected_templates = (
            templates
            if templates is not None
            else CAMERA_TYPE_TEMPLATES.get(camera_type, SURVEILLANCE_TEMPLATES)
        )

        # Validate templates contain placeholder
        for template in selected_templates:
            if "{}" not in template:
                raise ValueError(f"Template must contain '{{}}' placeholder: {template}")

        # Convert to RGB if needed
        if image.mode != "RGB":
            image = image.convert("RGB")

        # Preprocess image once
        image_inputs = self.processor(images=image, return_tensors="pt")
        model_dtype = next(self.model.parameters()).dtype
        image_inputs = {k: v.to(self.device, model_dtype) for k, v in image_inputs.items()}

        # Get image features
        with torch.inference_mode():
            raw_image_features = self.model.get_image_features(**image_inputs)
            image_features = self._extract_features_tensor(raw_image_features)
            # Normalize image features with epsilon for numerical stability
            epsilon = 1e-8
            image_features = image_features / (
                torch.norm(image_features, p=2, dim=-1, keepdim=True) + epsilon
            )

        # Collect text embeddings for all template-label combinations
        all_template_embeddings: list[torch.Tensor] = []

        for template in selected_templates:
            # Generate prompts for all labels using this template
            prompts = [template.format(label) for label in labels]

            # Encode text prompts
            text_inputs = self.processor(text=prompts, return_tensors="pt", padding=True)
            text_inputs = {k: v.to(self.device, model_dtype) for k, v in text_inputs.items()}

            with torch.inference_mode():
                raw_text_features = self.model.get_text_features(**text_inputs)
                text_features = self._extract_features_tensor(raw_text_features)
                # Normalize text features with epsilon
                text_features = text_features / (
                    torch.norm(text_features, p=2, dim=-1, keepdim=True) + epsilon
                )

            all_template_embeddings.append(text_features)

        # Stack and average across templates: (num_templates, num_labels, embedding_dim)
        stacked_embeddings = torch.stack(all_template_embeddings, dim=0)
        # Average across templates -> (num_labels, embedding_dim)
        ensemble_embeddings = stacked_embeddings.mean(dim=0)

        # Re-normalize the averaged embeddings
        ensemble_embeddings = ensemble_embeddings / (
            torch.norm(ensemble_embeddings, p=2, dim=-1, keepdim=True) + epsilon
        )

        # Compute similarities: (1, num_labels)
        with torch.inference_mode():
            similarities = image_features @ ensemble_embeddings.T

            # Apply softmax to get probabilities
            probs = torch.softmax(similarities, dim=-1)

        # Convert to dict
        scores_list = probs[0].cpu().float().numpy().tolist()
        scores = dict(zip(labels, scores_list, strict=True))

        # Find top label
        top_idx = int(probs[0].argmax().item())
        top_label = labels[top_idx]

        inference_time_ms = (time.perf_counter() - start_time) * 1000

        # Build metadata
        metadata = {
            "templates_used": selected_templates,
            "num_templates": len(selected_templates),
            "camera_type": camera_type.value
            if isinstance(camera_type, CameraType)
            else camera_type,
            "ensemble_method": "mean",
        }

        return scores, top_label, inference_time_ms, metadata

    def compute_similarity(self, image: Image.Image, text: str) -> tuple[float, float]:
        """Compute cosine similarity between an image and a text description.

        Args:
            image: PIL Image to compare
            text: Text description to compare against

        Returns:
            Tuple of (similarity score, inference_time_ms)
        """
        if self.model is None or self.processor is None:
            raise RuntimeError("Model not loaded")

        start_time = time.perf_counter()

        # Convert to RGB if needed
        if image.mode != "RGB":
            image = image.convert("RGB")

        # Preprocess image
        image_inputs = self.processor(images=image, return_tensors="pt")
        model_dtype = next(self.model.parameters()).dtype
        image_inputs = {k: v.to(self.device, model_dtype) for k, v in image_inputs.items()}

        # Preprocess text
        text_inputs = self.processor(text=[text], return_tensors="pt", padding=True)
        text_inputs = {k: v.to(self.device, model_dtype) for k, v in text_inputs.items()}

        # Generate embeddings
        with torch.inference_mode():
            raw_image_features = self.model.get_image_features(**image_inputs)
            raw_text_features = self.model.get_text_features(**text_inputs)
            image_features = self._extract_features_tensor(raw_image_features)
            text_features = self._extract_features_tensor(raw_text_features)

            # Normalize embeddings with epsilon to prevent division by zero (NEM-1100)
            epsilon = 1e-8
            image_features = image_features / (
                torch.norm(image_features, p=2, dim=-1, keepdim=True) + epsilon
            )
            text_features = text_features / (
                torch.norm(text_features, p=2, dim=-1, keepdim=True) + epsilon
            )

            # Compute cosine similarity
            similarity = (image_features @ text_features.T)[0, 0].cpu().float().item()

        inference_time_ms = (time.perf_counter() - start_time) * 1000

        return similarity, inference_time_ms

    def compute_batch_similarity(
        self, image: Image.Image, texts: list[str]
    ) -> tuple[dict[str, float], float]:
        """Compute cosine similarity between an image and multiple text descriptions.

        Args:
            image: PIL Image to compare
            texts: List of text descriptions to compare against

        Returns:
            Tuple of (similarities dict, inference_time_ms)
        """
        if self.model is None or self.processor is None:
            raise RuntimeError("Model not loaded")

        if not texts:
            raise ValueError("Texts list cannot be empty")

        start_time = time.perf_counter()

        # Convert to RGB if needed
        if image.mode != "RGB":
            image = image.convert("RGB")

        # Preprocess image
        image_inputs = self.processor(images=image, return_tensors="pt")
        model_dtype = next(self.model.parameters()).dtype
        image_inputs = {k: v.to(self.device, model_dtype) for k, v in image_inputs.items()}

        # Preprocess texts
        text_inputs = self.processor(text=texts, return_tensors="pt", padding=True)
        text_inputs = {k: v.to(self.device, model_dtype) for k, v in text_inputs.items()}

        # Generate embeddings
        with torch.inference_mode():
            raw_image_features = self.model.get_image_features(**image_inputs)
            raw_text_features = self.model.get_text_features(**text_inputs)
            image_features = self._extract_features_tensor(raw_image_features)
            text_features = self._extract_features_tensor(raw_text_features)

            # Normalize embeddings with epsilon to prevent division by zero (NEM-1100)
            epsilon = 1e-8
            image_features = image_features / (
                torch.norm(image_features, p=2, dim=-1, keepdim=True) + epsilon
            )
            text_features = text_features / (
                torch.norm(text_features, p=2, dim=-1, keepdim=True) + epsilon
            )

            # Compute cosine similarities (1, num_texts)
            similarities_tensor = (image_features @ text_features.T)[0]

        # Convert to dict
        similarities_list = similarities_tensor.cpu().float().numpy().tolist()
        similarities = dict(zip(texts, similarities_list, strict=True))

        inference_time_ms = (time.perf_counter() - start_time) * 1000

        return similarities, inference_time_ms


# Global model instance
model: CLIPEmbeddingModel | None = None


def get_vram_usage() -> float | None:
    """Get VRAM usage in GB."""
    try:
        if torch.cuda.is_available():
            return torch.cuda.memory_allocated() / (1024**3)
    except Exception as e:
        logger.warning(f"Failed to get VRAM usage: {e}")
    return None


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Lifespan context manager for FastAPI app."""
    global model

    # Startup
    logger.info("Starting CLIP Embedding Server...")

    # Load model configuration from environment or defaults
    model_path = os.environ.get("CLIP_MODEL_PATH", "/models/clip-vit-l")
    device = "cuda:0" if torch.cuda.is_available() else "cpu"

    try:
        model = CLIPEmbeddingModel(
            model_path=model_path,
            device=device,
        )
        model.load_model()
        logger.info("Model loaded successfully")
    except FileNotFoundError:
        logger.warning(f"Model not found at {model_path}")
        logger.warning("Server will start but embed endpoints will fail until model is available")
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        logger.warning("Server will start but embed endpoints will fail")

    yield

    # Shutdown
    logger.info("Shutting down CLIP Embedding Server...")
    if model is not None and hasattr(model, "model") and model.model is not None:
        del model.model
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


# Create FastAPI app
app = FastAPI(
    title="CLIP Embedding Server",
    description="Embedding service for entity re-identification using CLIP ViT-L",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint."""
    cuda_available = torch.cuda.is_available()
    device = "cuda:0" if cuda_available else "cpu"
    vram_used = get_vram_usage() if cuda_available else None

    # Determine if model is loaded (either PyTorch or TensorRT)
    model_loaded = model is not None and (
        model.model is not None or model._tensorrt_backend is not None
    )
    backend_type = model.backend_type if model is not None else "pytorch"
    engine_path = model.tensorrt_engine_path if model is not None else None

    return HealthResponse(
        status="healthy" if model_loaded else "degraded",
        model="clip-vit-large-patch14",
        model_loaded=model_loaded,
        device=device,
        cuda_available=cuda_available,
        vram_used_gb=vram_used,
        embedding_dimension=EMBEDDING_DIMENSION,
        backend=backend_type,
        tensorrt_engine_path=engine_path,
    )


@app.get("/metrics")
async def metrics() -> Response:
    """Prometheus metrics endpoint.

    Returns metrics in Prometheus text format for scraping.
    Updates GPU metrics gauges before returning.
    """
    # Update model status gauge (either PyTorch or TensorRT)
    model_loaded = model is not None and (
        model.model is not None or model._tensorrt_backend is not None
    )
    MODEL_LOADED.set(1 if model_loaded else 0)

    # Update backend type gauge (0=pytorch, 1=tensorrt)
    if model is not None:
        BACKEND_TYPE.set(1 if model.backend_type == "tensorrt" else 0)

    # Update GPU metrics gauges
    if torch.cuda.is_available():
        vram_used = get_vram_usage()
        if vram_used is not None:
            GPU_MEMORY_USED_GB.set(vram_used)

    return Response(content=generate_latest(), media_type="text/plain; charset=utf-8")


@app.post("/embed", response_model=EmbedResponse)
async def embed(request: EmbedRequest) -> EmbedResponse:
    """Generate CLIP embedding from an image.

    Accepts a base64-encoded image and returns a 768-dimensional embedding
    suitable for cosine similarity comparisons.

    Returns:
        Embedding results with the 768-dim vector and inference time
    """
    # Check if model is loaded (either PyTorch or TensorRT)
    model_loaded = model is not None and (
        model.model is not None or model._tensorrt_backend is not None
    )
    if not model_loaded:
        raise HTTPException(status_code=503, detail="Model not loaded")

    try:
        # Validate base64 string size BEFORE decoding to prevent DoS
        if len(request.image) > MAX_BASE64_SIZE_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"Base64 image data size ({len(request.image)} bytes) exceeds "
                f"maximum allowed size ({MAX_BASE64_SIZE_BYTES} bytes). "
                f"Maximum decoded image size: {MAX_IMAGE_SIZE_BYTES // (1024 * 1024)}MB",
            )

        # Decode base64 image
        try:
            image_bytes = base64.b64decode(request.image)
        except binascii.Error as e:
            raise HTTPException(status_code=400, detail=f"Invalid base64 encoding: {e}") from e

        # Validate decoded image size
        if len(image_bytes) > MAX_IMAGE_SIZE_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"Decoded image size ({len(image_bytes)} bytes) exceeds maximum "
                f"allowed size ({MAX_IMAGE_SIZE_BYTES} bytes / "
                f"{MAX_IMAGE_SIZE_BYTES // (1024 * 1024)}MB)",
            )

        # Open image
        try:
            image = Image.open(io.BytesIO(image_bytes))
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid image data: {e}") from e

        # Generate embedding with metrics tracking
        start_time = time.perf_counter()
        assert model is not None  # Already checked at start of function
        embedding, inference_time_ms = model.extract_embedding(image)
        latency_seconds = time.perf_counter() - start_time

        # Record metrics
        INFERENCE_LATENCY_SECONDS.labels(endpoint="embed").observe(latency_seconds)
        INFERENCE_REQUESTS_TOTAL.labels(endpoint="embed", status="success").inc()

        return EmbedResponse(
            embedding=embedding,
            inference_time_ms=inference_time_ms,
        )

    except HTTPException:
        INFERENCE_REQUESTS_TOTAL.labels(endpoint="embed", status="error").inc()
        raise
    except Exception as e:
        INFERENCE_REQUESTS_TOTAL.labels(endpoint="embed", status="error").inc()
        logger.error(f"Embedding extraction failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Embedding extraction failed: {e!s}") from e


def _decode_and_validate_image(image_b64: str) -> Image.Image:
    """Decode and validate a base64-encoded image.

    Args:
        image_b64: Base64-encoded image string

    Returns:
        PIL Image

    Raises:
        HTTPException: If image is invalid or too large
    """
    # Validate base64 string size BEFORE decoding to prevent DoS
    if len(image_b64) > MAX_BASE64_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Base64 image data size ({len(image_b64)} bytes) exceeds "
            f"maximum allowed size ({MAX_BASE64_SIZE_BYTES} bytes). "
            f"Maximum decoded image size: {MAX_IMAGE_SIZE_BYTES // (1024 * 1024)}MB",
        )

    # Decode base64 image
    try:
        image_bytes = base64.b64decode(image_b64)
    except binascii.Error as e:
        raise HTTPException(status_code=400, detail=f"Invalid base64 encoding: {e}") from e

    # Validate decoded image size
    if len(image_bytes) > MAX_IMAGE_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Decoded image size ({len(image_bytes)} bytes) exceeds maximum "
            f"allowed size ({MAX_IMAGE_SIZE_BYTES} bytes / "
            f"{MAX_IMAGE_SIZE_BYTES // (1024 * 1024)}MB)",
        )

    # Open image
    try:
        return Image.open(io.BytesIO(image_bytes))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image data: {e}") from e


@app.post("/anomaly-score", response_model=AnomalyScoreResponse)
async def anomaly_score(request: AnomalyScoreRequest) -> AnomalyScoreResponse:
    """Compute scene anomaly score by comparing image to baseline embedding.

    The anomaly score indicates how different the current frame is from the
    baseline (average of "normal" frames). This is useful for detecting:
    - New objects appearing in frame
    - Significant scene changes
    - Unexpected activity patterns

    Args:
        request: Contains base64-encoded image and baseline embedding

    Returns:
        Anomaly score (0-1), similarity to baseline, and inference time
    """
    if model is None or model.model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    try:
        # Validate baseline embedding dimension
        if len(request.baseline_embedding) != EMBEDDING_DIMENSION:
            raise HTTPException(
                status_code=400,
                detail=f"Baseline embedding must have {EMBEDDING_DIMENSION} dimensions, "
                f"got {len(request.baseline_embedding)}",
            )

        # Decode and validate image
        image = _decode_and_validate_image(request.image)

        # Compute anomaly score
        score, similarity, inference_time_ms = model.compute_anomaly_score(
            image, request.baseline_embedding
        )

        return AnomalyScoreResponse(
            anomaly_score=score,
            similarity_to_baseline=similarity,
            inference_time_ms=inference_time_ms,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Anomaly score computation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Anomaly score computation failed: {e!s}"
        ) from e


@app.post("/classify", response_model=ClassifyResponse)
async def classify(request: ClassifyRequest) -> ClassifyResponse:
    """Classify an image against a list of text labels using zero-shot classification.

    Uses CLIP's text and image encoders to compute similarity scores between
    the image and each label. Scores are normalized using softmax to sum to 1.0.

    By default, this endpoint uses prompt template ensembling for improved accuracy
    (5-10% improvement on surveillance footage). Set use_ensemble=False to disable.

    Args:
        request: Classification request with base64 image, text labels, and options

    Returns:
        Classification results with scores for each label, top label, inference time,
        and ensemble metadata (when use_ensemble=True)
    """
    if model is None or model.model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    try:
        # Validate labels
        if not request.labels:
            raise HTTPException(status_code=400, detail="Labels list cannot be empty")

        # Decode and validate image
        image = _decode_and_validate_image(request.image)

        # Use ensemble classification by default for improved accuracy
        if request.use_ensemble:
            scores, top_label, inference_time_ms, metadata = model.classify_with_ensemble(
                image, request.labels, camera_type=request.camera_type
            )
            return ClassifyResponse(
                scores=scores,
                top_label=top_label,
                inference_time_ms=inference_time_ms,
                ensemble_metadata=metadata,
            )
        else:
            # Fall back to simple classification without ensembling
            scores, top_label, inference_time_ms = model.classify(image, request.labels)
            return ClassifyResponse(
                scores=scores,
                top_label=top_label,
                inference_time_ms=inference_time_ms,
                ensemble_metadata=None,
            )

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Classification failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Classification failed: {e!s}") from e


@app.post("/similarity", response_model=SimilarityResponse)
async def similarity(request: SimilarityRequest) -> SimilarityResponse:
    """Compute cosine similarity between an image and a text description.

    Uses CLIP's text and image encoders to generate embeddings, then computes
    cosine similarity between the normalized embeddings.

    Args:
        request: Similarity request with base64 image and text description

    Returns:
        Similarity score and inference time
    """
    if model is None or model.model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    try:
        # Decode and validate image
        image = _decode_and_validate_image(request.image)

        # Compute similarity
        sim_score, inference_time_ms = model.compute_similarity(image, request.text)

        return SimilarityResponse(
            similarity=sim_score,
            inference_time_ms=inference_time_ms,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Similarity computation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Similarity computation failed: {e!s}") from e


@app.post("/batch-similarity", response_model=BatchSimilarityResponse)
async def batch_similarity(request: BatchSimilarityRequest) -> BatchSimilarityResponse:
    """Compute cosine similarity between an image and multiple text descriptions.

    Uses CLIP's text and image encoders to generate embeddings, then computes
    cosine similarity between the image embedding and each text embedding.

    Args:
        request: Batch similarity request with base64 image and list of text descriptions

    Returns:
        Similarity scores for each text and inference time
    """
    if model is None or model.model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    try:
        # Validate texts
        if not request.texts:
            raise HTTPException(status_code=400, detail="Texts list cannot be empty")

        # Decode and validate image
        image = _decode_and_validate_image(request.image)

        # Compute similarities
        similarities, inference_time_ms = model.compute_batch_similarity(image, request.texts)

        return BatchSimilarityResponse(
            similarities=similarities,
            inference_time_ms=inference_time_ms,
        )

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Batch similarity computation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Batch similarity computation failed: {e!s}"
        ) from e


if __name__ == "__main__":
    import uvicorn

    # Default to 0.0.0.0 to allow connections from Docker/Podman containers.
    # When AI servers run natively on host while backend runs in containers,
    # binding to 127.0.0.1 would prevent container-to-host connectivity.
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8093"))
    uvicorn.run(app, host=host, port=port, log_level="info")
