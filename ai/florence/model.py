"""Florence-2 Vision-Language Server

HTTP server wrapping Florence-2-large model for vision-language queries.
Supports attribute extraction from security camera images.

Supports torch.compile() for optimized inference (NEM-3375).
Supports Accelerate device_map for automatic device placement (NEM-3378).
Implements true batch inference for vision models (NEM-3377).
Supports Pyroscope continuous profiling (NEM-3920).

Port: 8092 (configurable via PORT env var)
Expected VRAM: ~1.2GB
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import io
import logging
import os
import sys
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import torch
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from PIL import Image
from prometheus_client import Counter, Gauge, Histogram, generate_latest
from pydantic import BaseModel, Field
from transformers import AutoModelForCausalLM, AutoProcessor

# Add parent directory to path for shared utilities
_ai_dir = Path(__file__).parent.parent
if str(_ai_dir) not in sys.path:
    sys.path.insert(0, str(_ai_dir))

from torch_optimizations import (
    BatchConfig,
    BatchProcessor,
    compile_model,
    get_optimal_device_map,
    get_torch_dtype_for_device,
    is_compile_supported,
)

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
    "florence_inference_requests_total",
    "Total number of inference requests",
    ["endpoint", "status"],
)

# Inference latency histogram (buckets tuned for typical inference times)
INFERENCE_LATENCY_SECONDS = Histogram(
    "florence_inference_latency_seconds",
    "Inference latency in seconds",
    ["endpoint"],
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0],
)

# Model status gauge (1 = loaded, 0 = not loaded)
MODEL_LOADED = Gauge(
    "florence_model_loaded",
    "Whether the model is loaded (1) or not (0)",
)

# GPU metrics gauges
GPU_MEMORY_USED_GB = Gauge(
    "florence_gpu_memory_used_gb",
    "GPU memory used in GB",
)

# Size limits for image uploads (10MB is reasonable for security camera images)
MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024  # 10MB
# Base64 encoding increases size by ~33%, so pre-decode limit is ~13.3MB
MAX_BASE64_SIZE_BYTES = int(MAX_IMAGE_SIZE_BYTES * 4 / 3) + 100  # ~13.3MB + padding

# Supported Florence-2 prompts
SUPPORTED_PROMPTS = {
    "<CAPTION>",
    "<DETAILED_CAPTION>",
    "<MORE_DETAILED_CAPTION>",
    "<OD>",
    "<DENSE_REGION_CAPTION>",
    "<REGION_PROPOSAL>",
    "<OCR>",
    "<OCR_WITH_REGION>",
}

# Region-based task prompts (NEM-3911)
# These require additional location/text inputs
REGION_TO_DESCRIPTION_PROMPT = "<REGION_TO_DESCRIPTION>"
CAPTION_TO_PHRASE_GROUNDING_PROMPT = "<CAPTION_TO_PHRASE_GROUNDING>"

# VQA prompt prefix - VQA prompts have format: <VQA>question text
VQA_PROMPT_PREFIX = "<VQA>"

# Open vocabulary detection prompt
OPEN_VOCABULARY_DETECTION_PROMPT = "<OPEN_VOCABULARY_DETECTION>"

# Security-relevant objects for open vocabulary detection
# These objects are commonly relevant in home security contexts
SECURITY_OBJECTS = [
    "person",
    "face",
    "mask",
    "hoodie",
    "backpack",
    "package",
    "weapon",
    "knife",
    "gun",
    "crowbar",
    "tool",
    "vehicle",
    "car",
    "truck",
    "van",
    "motorcycle",
    "bicycle",
    "dog",
    "cat",
    "uniform",
    "badge",
    "clipboard",
]

# Pre-formatted security objects prompt for Florence-2
SECURITY_OBJECTS_PROMPT = "Detect: " + ", ".join(SECURITY_OBJECTS)


class ExtractRequest(BaseModel):
    """Request format for extract endpoint."""

    image: str = Field(..., description="Base64 encoded image")
    prompt: str = Field(
        default="<CAPTION>",
        description="Florence-2 prompt (e.g., <CAPTION>, <DETAILED_CAPTION>, <VQA>What color is the car?)",
    )


class ExtractResponse(BaseModel):
    """Response format for extract endpoint."""

    result: str = Field(..., description="Florence-2 generated text response")
    prompt_used: str = Field(..., description="The prompt that was used")
    inference_time_ms: float = Field(..., description="Inference time in milliseconds")


class ImageRequest(BaseModel):
    """Request format for endpoints that only need an image."""

    image: str = Field(..., description="Base64 encoded image")


class OCRResponse(BaseModel):
    """Response format for OCR endpoint."""

    text: str = Field(..., description="Extracted text from the image")
    inference_time_ms: float = Field(..., description="Inference time in milliseconds")


class OCRRegion(BaseModel):
    """A text region with bounding box coordinates."""

    text: str = Field(..., description="Text content in this region")
    bbox: list[float] = Field(
        ...,
        description="Bounding box as [x1, y1, x2, y2, x3, y3, x4, y4] (quadrilateral corners)",
    )


class OCRWithRegionsResponse(BaseModel):
    """Response format for OCR with regions endpoint."""

    regions: list[OCRRegion] = Field(..., description="List of text regions with bounding boxes")
    inference_time_ms: float = Field(..., description="Inference time in milliseconds")


class Detection(BaseModel):
    """A detected object with bounding box and confidence score."""

    label: str = Field(..., description="Object label/class")
    bbox: list[float] = Field(..., description="Bounding box as [x1, y1, x2, y2]")
    score: float = Field(default=1.0, description="Confidence score (0-1)")


class DetectResponse(BaseModel):
    """Response format for object detection endpoint."""

    detections: list[Detection] = Field(..., description="List of detected objects")
    inference_time_ms: float = Field(..., description="Inference time in milliseconds")


class CaptionedRegion(BaseModel):
    """A region with its caption and bounding box."""

    caption: str = Field(..., description="Caption describing this region")
    bbox: list[float] = Field(..., description="Bounding box as [x1, y1, x2, y2]")


class DenseCaptionResponse(BaseModel):
    """Response format for dense region captioning endpoint."""

    regions: list[CaptionedRegion] = Field(..., description="List of captioned regions")
    inference_time_ms: float = Field(..., description="Inference time in milliseconds")


class SecurityObjectDetection(BaseModel):
    """A detected security-relevant object with bounding box and confidence."""

    label: str = Field(..., description="Object label from security vocabulary")
    bbox: list[float] = Field(..., description="Bounding box as [x1, y1, x2, y2]")
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Detection confidence score (0-1)"
    )


class SecurityObjectsResponse(BaseModel):
    """Response format for security objects detection endpoint."""

    detections: list[SecurityObjectDetection] = Field(
        ..., description="List of detected security-relevant objects"
    )
    objects_queried: list[str] = Field(
        ..., description="List of security objects that were searched for"
    )
    inference_time_ms: float = Field(..., description="Inference time in milliseconds")


class SceneAnalysisRequest(BaseModel):
    """Request format for comprehensive scene analysis endpoint."""

    image: str = Field(..., description="Base64 encoded image")


class SceneAnalysisResponse(BaseModel):
    """Response format for comprehensive scene analysis.

    Structured output suitable for Nemotron prompt consumption.
    Contains detailed caption, region descriptions, and OCR results.
    """

    caption: str = Field(..., description="Detailed scene description from MORE_DETAILED_CAPTION")
    regions: list[CaptionedRegion] = Field(
        default_factory=list, description="Dense region captions with bounding boxes"
    )
    text_regions: list[OCRRegion] = Field(
        default_factory=list, description="OCR text with bounding box regions"
    )
    inference_time_ms: float = Field(..., description="Total inference time in milliseconds")
    task_times_ms: dict[str, float] = Field(
        default_factory=dict, description="Individual task inference times"
    )


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    model: str
    model_loaded: bool
    device: str
    cuda_available: bool
    vram_used_gb: float | None = None


# =============================================================================
# Region Description and Phrase Grounding Models (NEM-3911)
# =============================================================================


class BoundingBox(BaseModel):
    """A bounding box with x1, y1, x2, y2 coordinates.

    Coordinates are in pixel values relative to image dimensions.
    x1, y1 is the top-left corner and x2, y2 is the bottom-right corner.
    """

    x1: float = Field(..., ge=0, description="Left edge x-coordinate")
    y1: float = Field(..., ge=0, description="Top edge y-coordinate")
    x2: float = Field(..., ge=0, description="Right edge x-coordinate")
    y2: float = Field(..., ge=0, description="Bottom edge y-coordinate")

    def model_post_init(self, __context: Any) -> None:
        """Validate that x1 < x2 and y1 < y2."""
        if self.x1 >= self.x2:
            raise ValueError(f"x1 ({self.x1}) must be less than x2 ({self.x2})")
        if self.y1 >= self.y2:
            raise ValueError(f"y1 ({self.y1}) must be less than y2 ({self.y2})")

    def as_list(self) -> list[float]:
        """Return bounding box as [x1, y1, x2, y2] list."""
        return [self.x1, self.y1, self.x2, self.y2]

    @classmethod
    def from_list(cls, bbox: list[float]) -> BoundingBox:
        """Create BoundingBox from [x1, y1, x2, y2] list."""
        if len(bbox) != 4:
            raise ValueError(f"Expected 4 coordinates, got {len(bbox)}")
        return cls(x1=bbox[0], y1=bbox[1], x2=bbox[2], y2=bbox[3])


class RegionDescriptionRequest(BaseModel):
    """Request format for region description endpoint (NEM-3911).

    Given an image and one or more bounding box regions, describe what's
    in each specific region.
    """

    image: str = Field(..., description="Base64 encoded image")
    regions: list[BoundingBox] = Field(
        ...,
        min_length=1,
        description="List of bounding box regions to describe (at least one required)",
    )


class RegionDescriptionResponse(BaseModel):
    """Response format for region description endpoint (NEM-3911).

    Returns a caption for each input region along with the original
    bounding box coordinates.
    """

    descriptions: list[CaptionedRegion] = Field(
        ..., description="List of region descriptions with bounding boxes"
    )
    inference_time_ms: float = Field(..., description="Total inference time in milliseconds")


class GroundedPhrase(BaseModel):
    """A phrase with its grounded bounding boxes (NEM-3911).

    When a phrase matches multiple objects in the image, multiple bboxes
    are returned. If the phrase has no matches, bboxes will be empty.
    """

    phrase: str = Field(..., description="The text phrase that was searched for")
    bboxes: list[list[float]] = Field(
        default_factory=list,
        description="List of bounding boxes where this phrase was found, each as [x1, y1, x2, y2]",
    )
    confidence_scores: list[float] = Field(
        default_factory=list,
        description="Confidence scores for each bounding box (0-1)",
    )


class PhraseGroundingRequest(BaseModel):
    """Request format for phrase grounding endpoint (NEM-3911).

    Given an image and text descriptions, find the bounding boxes of
    objects matching each description.
    """

    image: str = Field(..., description="Base64 encoded image")
    phrases: list[str] = Field(
        ...,
        min_length=1,
        description="List of text phrases to ground in the image (at least one required)",
    )

    def model_post_init(self, __context: Any) -> None:
        """Validate that no phrases are empty strings."""
        for i, phrase in enumerate(self.phrases):
            if not phrase or not phrase.strip():
                raise ValueError(f"Phrase at index {i} cannot be empty")


class PhraseGroundingResponse(BaseModel):
    """Response format for phrase grounding endpoint (NEM-3911).

    Returns grounding results for each input phrase. Phrases with no
    matches will have empty bboxes lists.
    """

    grounded_phrases: list[GroundedPhrase] = Field(
        ..., description="Grounding results for each input phrase"
    )
    inference_time_ms: float = Field(..., description="Total inference time in milliseconds")


class Florence2Model:
    """Florence-2 model wrapper using HuggingFace Transformers.

    Supports:
    - torch.compile() for optimized inference (NEM-3375)
    - Accelerate device_map for automatic device placement (NEM-3378)
    - True batch inference with optimal batching (NEM-3377)
    """

    def __init__(
        self,
        model_path: str,
        device: str = "cuda:0",
        use_compile: bool = True,
        use_accelerate: bool = True,
        max_batch_size: int = 4,
    ):
        """Initialize Florence-2 model.

        Args:
            model_path: Path to HuggingFace model directory or model name
            device: Device to run inference on (cuda:0, cpu)
            use_compile: Whether to use torch.compile() for optimization (NEM-3375).
            use_accelerate: Whether to use Accelerate device_map (NEM-3378).
            max_batch_size: Maximum batch size for batch inference (NEM-3377).
        """
        self.model_path = model_path
        self.device = device
        self.model: Any = None
        self.processor: Any = None
        self.use_compile = use_compile
        self.use_accelerate = use_accelerate
        self.is_compiled = False

        # Batch processing configuration (NEM-3377)
        self.batch_processor = BatchProcessor(BatchConfig(max_batch_size=max_batch_size))

        logger.info(f"Initializing Florence-2 model from {self.model_path}")
        logger.info(f"Device: {device}")
        logger.info(f"torch.compile enabled: {use_compile}, Accelerate enabled: {use_accelerate}")

    def load_model(self) -> None:
        """Load the model into memory using HuggingFace Transformers.

        Supports:
        - Accelerate device_map for automatic device placement (NEM-3378)
        - torch.compile() for optimized inference (NEM-3375)
        """
        try:
            logger.info("Loading Florence-2 model with HuggingFace Transformers...")

            # Determine device and dtype
            if "cuda" in self.device and torch.cuda.is_available():
                dtype = get_torch_dtype_for_device(self.device)
            else:
                self.device = "cpu"
                dtype = torch.float32

            # Load processor
            self.processor = AutoProcessor.from_pretrained(
                self.model_path,
                trust_remote_code=True,
            )

            # Load model with appropriate settings
            # Use eager attention implementation to avoid SDPA compatibility issues
            # with Florence-2's custom model code
            if self.use_accelerate and "cuda" in self.device:
                device_map = get_optimal_device_map(self.model_path)
                logger.info(f"Loading model with device_map='{device_map}'")
                self.model = AutoModelForCausalLM.from_pretrained(
                    self.model_path,
                    device_map=device_map,
                    torch_dtype=dtype,
                    trust_remote_code=True,
                    attn_implementation="eager",
                )
            else:
                # Traditional loading with manual device placement
                self.model = AutoModelForCausalLM.from_pretrained(
                    self.model_path,
                    torch_dtype=dtype,
                    trust_remote_code=True,
                    attn_implementation="eager",
                )
                # Move model to device
                if "cuda" in self.device:
                    self.model = self.model.to(self.device)
                    logger.info(f"Model loaded on {self.device}")
                else:
                    logger.info("CUDA not available, using CPU")

            # Set model to evaluation mode
            self.model.eval()

            # Apply torch.compile() for optimized inference (NEM-3375)
            # Note: Florence-2 with trust_remote_code may have compilation issues,
            # so we wrap in try-except
            if self.use_compile and is_compile_supported():
                try:
                    logger.info("Applying torch.compile() for optimized inference...")
                    self.model = compile_model(self.model, mode="reduce-overhead")
                    self.is_compiled = True
                except Exception as e:
                    logger.warning(f"torch.compile() failed for Florence-2: {e}")
                    logger.info("Continuing with uncompiled model")
            else:
                logger.info("torch.compile() not applied (disabled or not supported)")

            # Warmup inference (important for compiled models)
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
                _ = self.extract(dummy_image, "<CAPTION>")
                logger.info(f"Warmup iteration {i + 1}/{num_iterations} complete")
            except Exception as e:
                logger.warning(f"Warmup iteration {i + 1} failed: {e}")

        logger.info("Warmup complete")

    def extract(self, image: Image.Image, prompt: str) -> tuple[str, float]:
        """Run Florence-2 inference on an image with a prompt.

        Args:
            image: PIL Image to process
            prompt: Florence-2 task prompt

        Returns:
            Tuple of (generated text, inference_time_ms)
        """
        if self.model is None or self.processor is None:
            raise RuntimeError("Model not loaded")

        start_time = time.perf_counter()

        # Convert to RGB if needed
        if image.mode != "RGB":
            image = image.convert("RGB")

        # Preprocess image and prompt
        inputs = self.processor(
            text=prompt,
            images=image,
            return_tensors="pt",
        )

        # Move inputs to device with correct dtype
        # Per HuggingFace docs, call .to() on the BatchEncoding object directly
        model_dtype = next(self.model.parameters()).dtype
        inputs = inputs.to(self.device, model_dtype)

        # Run inference using greedy decoding with cache disabled
        # The Florence-2 model's prepare_inputs_for_generation has a bug with past_key_values
        # Disabling cache avoids the issue
        with torch.inference_mode():
            generated_ids = self.model.generate(
                input_ids=inputs["input_ids"],
                pixel_values=inputs["pixel_values"],
                max_new_tokens=1024,
                early_stopping=False,
                do_sample=False,
                num_beams=1,
                use_cache=False,  # Disable KV cache to avoid past_key_values bug
            )

        # Decode the generated text
        generated_text = self.processor.batch_decode(generated_ids, skip_special_tokens=False)[0]

        # Post-process to extract the result
        parsed_result = self.processor.post_process_generation(
            generated_text,
            task=prompt,
            image_size=(image.width, image.height),
        )

        # Extract the text result from parsed output
        if prompt in parsed_result:
            result = parsed_result[prompt]
            # Handle different output formats
            if isinstance(result, str):
                final_result = result
            elif isinstance(result, dict):
                # For structured outputs, convert to string
                final_result = str(result)
            elif isinstance(result, list):
                final_result = " ".join(str(item) for item in result)
            else:
                final_result = str(result)
        else:
            final_result = generated_text

        inference_time_ms = (time.perf_counter() - start_time) * 1000

        return final_result, inference_time_ms

    def extract_raw(self, image: Image.Image, prompt: str) -> tuple[Any, float]:
        """Run Florence-2 inference and return raw parsed result.

        This method returns the raw parsed output from Florence-2's post-processing,
        which can be a dict, list, or string depending on the prompt type.

        Args:
            image: PIL Image to process
            prompt: Florence-2 task prompt

        Returns:
            Tuple of (raw parsed result, inference_time_ms)
        """
        if self.model is None or self.processor is None:
            raise RuntimeError("Model not loaded")

        start_time = time.perf_counter()

        # Convert to RGB if needed
        if image.mode != "RGB":
            image = image.convert("RGB")

        # Preprocess image and prompt
        inputs = self.processor(
            text=prompt,
            images=image,
            return_tensors="pt",
        )

        # Move inputs to device with correct dtype
        model_dtype = next(self.model.parameters()).dtype
        inputs = inputs.to(self.device, model_dtype)

        # Run inference
        with torch.inference_mode():
            generated_ids = self.model.generate(
                input_ids=inputs["input_ids"],
                pixel_values=inputs["pixel_values"],
                max_new_tokens=1024,
                early_stopping=False,
                do_sample=False,
                num_beams=1,
                use_cache=False,
            )

        # Decode the generated text
        generated_text = self.processor.batch_decode(generated_ids, skip_special_tokens=False)[0]

        # Post-process to extract the result
        parsed_result = self.processor.post_process_generation(
            generated_text,
            task=prompt,
            image_size=(image.width, image.height),
        )

        inference_time_ms = (time.perf_counter() - start_time) * 1000

        # Return the raw parsed result for the given prompt
        if prompt in parsed_result:
            return parsed_result[prompt], inference_time_ms
        return parsed_result, inference_time_ms


# Global model instance
model: Florence2Model | None = None


def init_profiling() -> None:
    """Initialize Pyroscope continuous profiling for ai-florence service.

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
        logger.info("Pyroscope profiling disabled (PYROSCOPE_ENABLED != true)")
        return

    try:
        import pyroscope

        pyroscope_server = os.getenv("PYROSCOPE_URL", "http://pyroscope:4040")
        pyroscope.configure(
            application_name="ai-florence",
            server_address=pyroscope_server,
            tags={
                "service": "ai-florence",
                "environment": os.getenv("ENVIRONMENT", "production"),
            },
            oncpu=True,
            gil_only=False,
            enable_logging=True,
        )
        logger.info(f"Pyroscope profiling initialized: server={pyroscope_server}")
    except ImportError:
        logger.debug("Pyroscope profiling skipped: pyroscope-io not installed")
    except Exception as e:
        logger.warning(f"Failed to initialize Pyroscope profiling: {e}")


def get_vram_usage() -> float | None:
    """Get VRAM usage in GB."""
    try:
        if torch.cuda.is_available():
            return torch.cuda.memory_allocated() / (1024**3)
    except Exception as e:
        logger.warning(f"Failed to get VRAM usage: {e}")
    return None


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    """Lifespan context manager for FastAPI app."""
    global model

    # Initialize Pyroscope continuous profiling (NEM-3920)
    # Must be done early to capture profiling data from the entire startup
    init_profiling()

    # Startup
    logger.info("Starting Florence-2 Vision-Language Server...")

    # Load model configuration from environment or defaults
    model_path = os.environ.get("FLORENCE_MODEL_PATH", "/models/florence-2-large")
    device = "cuda:0" if torch.cuda.is_available() else "cpu"

    # torch.compile settings (NEM-3375)
    use_compile = os.environ.get("FLORENCE_USE_COMPILE", "1").lower() in ("1", "true", "yes")
    # Accelerate device_map settings (NEM-3378)
    use_accelerate = os.environ.get("FLORENCE_USE_ACCELERATE", "1").lower() in ("1", "true", "yes")
    # Batch inference settings (NEM-3377)
    max_batch_size = int(os.environ.get("FLORENCE_MAX_BATCH_SIZE", "4"))

    try:
        model = Florence2Model(
            model_path=model_path,
            device=device,
            use_compile=use_compile,
            use_accelerate=use_accelerate,
            max_batch_size=max_batch_size,
        )
        model.load_model()
        logger.info("Model loaded successfully")
        if model.is_compiled:
            logger.info("Model is using torch.compile() optimization")
    except FileNotFoundError:
        logger.warning(f"Model not found at {model_path}")
        logger.warning("Server will start but extract endpoints will fail until model is available")
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        logger.warning("Server will start but extract endpoints will fail")

    yield

    # Shutdown
    logger.info("Shutting down Florence-2 Vision-Language Server...")
    if model is not None and hasattr(model, "model") and model.model is not None:
        del model.model
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


# Create FastAPI app
app = FastAPI(
    title="Florence-2 Vision-Language Server",
    description="Vision-language service for attribute extraction using Florence-2-large",
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
        status="healthy" if model is not None and model.model is not None else "degraded",
        model="florence-2-large",
        model_loaded=model is not None and model.model is not None,
        device=device,
        cuda_available=cuda_available,
        vram_used_gb=vram_used,
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

    return Response(content=generate_latest(), media_type="text/plain; charset=utf-8")


@app.post("/extract", response_model=ExtractResponse)
async def extract(request: ExtractRequest) -> ExtractResponse:
    """Extract information from an image using Florence-2.

    Accepts a base64-encoded image and a Florence-2 prompt.

    Supported prompts:
    - <CAPTION>: Brief image caption
    - <DETAILED_CAPTION>: Detailed image description
    - <MORE_DETAILED_CAPTION>: Very detailed image description
    - <OD>: Object detection
    - <DENSE_REGION_CAPTION>: Dense region captioning
    - <REGION_PROPOSAL>: Region proposals
    - <OCR>: Optical character recognition
    - <OCR_WITH_REGION>: OCR with region information
    - <VQA>question: Visual question answering (question text follows the tag)

    Returns:
        Extraction results with the generated text response
    """
    if model is None or model.model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    try:
        # Validate prompt - check exact match or VQA prefix (case-insensitive)
        # Use upper() for validation to prevent case-sensitivity bypass attacks
        normalized_prompt = request.prompt.upper()
        is_vqa_prompt = normalized_prompt.startswith(VQA_PROMPT_PREFIX.upper())
        normalized_supported = {p.upper() for p in SUPPORTED_PROMPTS}
        if not is_vqa_prompt and normalized_prompt not in normalized_supported:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported prompt: {request.prompt}. "
                f"Supported prompts: {', '.join(sorted(SUPPORTED_PROMPTS))}, "
                f"or VQA format: {VQA_PROMPT_PREFIX}<question>",
            )

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

        # Run extraction with metrics tracking
        start_time = time.perf_counter()
        result, inference_time_ms = model.extract(image, request.prompt)
        latency_seconds = time.perf_counter() - start_time

        # Record metrics
        INFERENCE_LATENCY_SECONDS.labels(endpoint="extract").observe(latency_seconds)
        INFERENCE_REQUESTS_TOTAL.labels(endpoint="extract", status="success").inc()

        return ExtractResponse(
            result=result,
            prompt_used=request.prompt,
            inference_time_ms=inference_time_ms,
        )

    except HTTPException:
        INFERENCE_REQUESTS_TOTAL.labels(endpoint="extract", status="error").inc()
        raise
    except Exception as e:
        INFERENCE_REQUESTS_TOTAL.labels(endpoint="extract", status="error").inc()
        logger.error(f"Extraction failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Extraction failed: {e!s}") from e


def _decode_image(image_b64: str) -> Image.Image:
    """Decode a base64 image string to PIL Image.

    Args:
        image_b64: Base64 encoded image string

    Returns:
        PIL Image object

    Raises:
        HTTPException: If the image is invalid or too large
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


@app.post("/ocr", response_model=OCRResponse)
async def ocr(request: ImageRequest) -> OCRResponse:
    """Extract all text from an image using OCR.

    Uses Florence-2's <OCR> prompt to extract text content from the image.

    Returns:
        OCR results with extracted text
    """
    if model is None or model.model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    try:
        image = _decode_image(request.image)

        # Run OCR extraction
        result, inference_time_ms = model.extract(image, "<OCR>")

        return OCRResponse(
            text=result,
            inference_time_ms=inference_time_ms,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"OCR extraction failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"OCR extraction failed: {e!s}") from e


@app.post("/ocr-with-regions", response_model=OCRWithRegionsResponse)
async def ocr_with_regions(request: ImageRequest) -> OCRWithRegionsResponse:
    """Extract text with bounding box regions from an image.

    Uses Florence-2's <OCR_WITH_REGION> prompt to extract text along with
    quadrilateral bounding boxes for each text region.

    Returns:
        OCR results with text regions and their bounding boxes
    """
    if model is None or model.model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    try:
        image = _decode_image(request.image)

        # Run OCR with regions extraction
        raw_result, inference_time_ms = model.extract_raw(image, "<OCR_WITH_REGION>")

        # Parse the result - Florence-2 returns {'quad_boxes': [...], 'labels': [...]}
        regions: list[OCRRegion] = []

        if isinstance(raw_result, dict):
            quad_boxes = raw_result.get("quad_boxes", [])
            labels = raw_result.get("labels", [])

            for i, label in enumerate(labels):
                bbox = quad_boxes[i] if i < len(quad_boxes) else []
                # Flatten the quad box if it's nested
                if bbox and isinstance(bbox[0], list):
                    bbox = [coord for point in bbox for coord in point]
                regions.append(OCRRegion(text=label, bbox=bbox))

        return OCRWithRegionsResponse(
            regions=regions,
            inference_time_ms=inference_time_ms,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"OCR with regions extraction failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"OCR with regions extraction failed: {e!s}"
        ) from e


@app.post("/detect", response_model=DetectResponse)
async def detect(request: ImageRequest) -> DetectResponse:
    """Detect objects with bounding boxes in an image.

    Uses Florence-2's <OD> (Object Detection) prompt to detect objects
    and return their labels with bounding boxes.

    Returns:
        Detection results with object labels and bounding boxes
    """
    if model is None or model.model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    try:
        image = _decode_image(request.image)

        # Run object detection
        raw_result, inference_time_ms = model.extract_raw(image, "<OD>")

        # Parse the result - Florence-2 returns {'bboxes': [...], 'labels': [...]}
        detections: list[Detection] = []

        if isinstance(raw_result, dict):
            bboxes = raw_result.get("bboxes", [])
            labels = raw_result.get("labels", [])

            for i, label in enumerate(labels):
                bbox = bboxes[i] if i < len(bboxes) else []
                # Florence-2 OD doesn't return scores, so default to 1.0
                detections.append(Detection(label=label, bbox=bbox, score=1.0))

        return DetectResponse(
            detections=detections,
            inference_time_ms=inference_time_ms,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Object detection failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Object detection failed: {e!s}") from e


@app.post("/dense-caption", response_model=DenseCaptionResponse)
async def dense_caption(request: ImageRequest) -> DenseCaptionResponse:
    """Generate captions for all regions in an image.

    Uses Florence-2's <DENSE_REGION_CAPTION> prompt to identify regions
    in the image and generate captions for each one.

    Returns:
        Dense captioning results with region captions and bounding boxes
    """
    if model is None or model.model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    try:
        image = _decode_image(request.image)

        # Run dense region captioning
        raw_result, inference_time_ms = model.extract_raw(image, "<DENSE_REGION_CAPTION>")

        # Parse the result - Florence-2 returns {'bboxes': [...], 'labels': [...]}
        regions: list[CaptionedRegion] = []

        if isinstance(raw_result, dict):
            bboxes = raw_result.get("bboxes", [])
            labels = raw_result.get("labels", [])

            for i, label in enumerate(labels):
                bbox = bboxes[i] if i < len(bboxes) else []
                regions.append(CaptionedRegion(caption=label, bbox=bbox))

        return DenseCaptionResponse(
            regions=regions,
            inference_time_ms=inference_time_ms,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Dense captioning failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Dense captioning failed: {e!s}") from e


@app.post("/analyze-scene", response_model=SceneAnalysisResponse)
async def analyze_scene(request: SceneAnalysisRequest) -> SceneAnalysisResponse:
    """Comprehensive scene analysis using cascaded Florence-2 prompts.

    Runs multiple Florence-2 tasks to extract maximum scene context:
    1. MORE_DETAILED_CAPTION - Rich scene description
    2. DENSE_REGION_CAPTION - Per-region captions with bounding boxes
    3. OCR_WITH_REGION - Text extraction with locations

    Tasks 2 and 3 (DENSE_REGION_CAPTION and OCR_WITH_REGION) run in parallel
    since they are independent and don't depend on each other's results.

    The structured output is designed for Nemotron prompt consumption,
    providing comprehensive scene understanding for risk assessment.

    Returns:
        SceneAnalysisResponse with caption, regions, text_regions, and timing info
    """
    if model is None or model.model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    try:
        # Decode image once for all tasks
        image = _decode_image(request.image)
        start_time = time.perf_counter()
        task_times: dict[str, float] = {}

        # Step 1: Get detailed caption (must complete first as it's the primary output)
        caption_result, caption_time = model.extract(image, "<MORE_DETAILED_CAPTION>")
        task_times["caption"] = caption_time

        # Step 2 & 3: Run DENSE_REGION_CAPTION and OCR_WITH_REGION in parallel
        # These tasks are independent and can execute concurrently
        async def run_dense_regions() -> tuple[list[CaptionedRegion], float]:
            """Run dense region captioning in thread pool."""
            raw_result, time_ms = await asyncio.to_thread(
                model.extract_raw, image, "<DENSE_REGION_CAPTION>"
            )
            regions: list[CaptionedRegion] = []
            if isinstance(raw_result, dict):
                bboxes = raw_result.get("bboxes", [])
                labels = raw_result.get("labels", [])
                for i, label in enumerate(labels):
                    bbox = bboxes[i] if i < len(bboxes) else []
                    regions.append(CaptionedRegion(caption=label, bbox=bbox))
            return regions, time_ms

        async def run_ocr_with_regions() -> tuple[list[OCRRegion], float]:
            """Run OCR with regions in thread pool."""
            raw_result, time_ms = await asyncio.to_thread(
                model.extract_raw, image, "<OCR_WITH_REGION>"
            )
            text_regions: list[OCRRegion] = []
            if isinstance(raw_result, dict):
                quad_boxes = raw_result.get("quad_boxes", [])
                labels = raw_result.get("labels", [])
                for i, label in enumerate(labels):
                    bbox = quad_boxes[i] if i < len(quad_boxes) else []
                    # Flatten the quad box if it's nested
                    if bbox and isinstance(bbox[0], list):
                        bbox = [coord for point in bbox for coord in point]
                    text_regions.append(OCRRegion(text=label, bbox=bbox))
            return text_regions, time_ms

        # Execute parallel tasks
        (regions, regions_time), (text_regions, ocr_time) = await asyncio.gather(
            run_dense_regions(),
            run_ocr_with_regions(),
        )

        task_times["dense_regions"] = regions_time
        task_times["ocr_with_regions"] = ocr_time

        # Calculate total time
        total_time_ms = (time.perf_counter() - start_time) * 1000

        # Record metrics
        INFERENCE_LATENCY_SECONDS.labels(endpoint="analyze_scene").observe(total_time_ms / 1000)
        INFERENCE_REQUESTS_TOTAL.labels(endpoint="analyze_scene", status="success").inc()

        return SceneAnalysisResponse(
            caption=caption_result,
            regions=regions,
            text_regions=text_regions,
            inference_time_ms=total_time_ms,
            task_times_ms=task_times,
        )

    except HTTPException:
        INFERENCE_REQUESTS_TOTAL.labels(endpoint="analyze_scene", status="error").inc()
        raise
    except Exception as e:
        INFERENCE_REQUESTS_TOTAL.labels(endpoint="analyze_scene", status="error").inc()
        logger.error(f"Scene analysis failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Scene analysis failed: {e!s}") from e


@app.post("/detect_security_objects", response_model=SecurityObjectsResponse)
async def detect_security_objects(request: ImageRequest) -> SecurityObjectsResponse:
    """Detect security-relevant objects using open vocabulary detection.

    Uses Florence-2's <OPEN_VOCABULARY_DETECTION> task with a predefined
    vocabulary of security-relevant objects (person, face, mask, weapon,
    vehicle, package, etc.).

    This endpoint is optimized for home security monitoring scenarios
    where detecting specific object categories is more important than
    general object detection.

    Returns:
        SecurityObjectsResponse with list of detected objects, bounding boxes,
        and confidence scores.
    """
    if model is None or model.model is None:
        INFERENCE_REQUESTS_TOTAL.labels(endpoint="detect_security_objects", status="error").inc()
        raise HTTPException(status_code=503, detail="Model not loaded")

    try:
        image = _decode_image(request.image)

        # Run open vocabulary detection with security objects prompt
        # Florence-2 expects: <OPEN_VOCABULARY_DETECTION>object1, object2, ...
        prompt = f"{OPEN_VOCABULARY_DETECTION_PROMPT}{SECURITY_OBJECTS_PROMPT}"

        start_time = time.perf_counter()
        raw_result, inference_time_ms = model.extract_raw(image, prompt)
        latency_seconds = time.perf_counter() - start_time

        # Parse the result - Florence-2 returns {'bboxes': [...], 'bboxes_labels': [...]}
        # for open vocabulary detection
        detections: list[SecurityObjectDetection] = []

        if isinstance(raw_result, dict):
            # Open vocabulary detection may use different keys
            bboxes = raw_result.get("bboxes") or raw_result.get("boxes") or []
            labels = raw_result.get("bboxes_labels") or raw_result.get("labels") or []

            for i, label in enumerate(labels):
                bbox = bboxes[i] if i < len(bboxes) else []
                # Florence-2 open vocabulary detection doesn't return scores,
                # so we default to 1.0 for detected objects
                detections.append(
                    SecurityObjectDetection(
                        label=label,
                        bbox=bbox,
                        confidence=1.0,
                    )
                )

        # Record metrics
        INFERENCE_LATENCY_SECONDS.labels(endpoint="detect_security_objects").observe(
            latency_seconds
        )
        INFERENCE_REQUESTS_TOTAL.labels(endpoint="detect_security_objects", status="success").inc()

        return SecurityObjectsResponse(
            detections=detections,
            objects_queried=SECURITY_OBJECTS.copy(),
            inference_time_ms=inference_time_ms,
        )

    except HTTPException:
        INFERENCE_REQUESTS_TOTAL.labels(endpoint="detect_security_objects", status="error").inc()
        raise
    except Exception as e:
        INFERENCE_REQUESTS_TOTAL.labels(endpoint="detect_security_objects", status="error").inc()
        logger.error(f"Security objects detection failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Security objects detection failed: {e!s}"
        ) from e


# =============================================================================
# Region Description and Phrase Grounding Endpoints (NEM-3911)
# =============================================================================


@app.post("/describe-region", response_model=RegionDescriptionResponse)
async def describe_region(request: RegionDescriptionRequest) -> RegionDescriptionResponse:
    """Describe what's in a specific bounding box region of an image.

    Given an image and one or more bounding box regions, this endpoint uses
    Florence-2's <REGION_TO_DESCRIPTION> task to generate a textual description
    of what's contained within each specified region.

    This is useful for:
    - Getting detailed descriptions of detected objects
    - Understanding context within a specific area of the image
    - Enriching YOLO26 detections with natural language descriptions

    Args:
        request: RegionDescriptionRequest with image and regions to describe

    Returns:
        RegionDescriptionResponse with description for each input region

    Example:
        Given a YOLO26 detection of a person at [100, 150, 300, 400],
        this endpoint can describe: "a person wearing a blue jacket and
        holding a brown package"
    """
    if model is None or model.model is None:
        INFERENCE_REQUESTS_TOTAL.labels(endpoint="describe_region", status="error").inc()
        raise HTTPException(status_code=503, detail="Model not loaded")

    try:
        image = _decode_image(request.image)
        start_time = time.perf_counter()

        descriptions: list[CaptionedRegion] = []

        # Process each region
        for region in request.regions:
            # Florence-2 REGION_TO_DESCRIPTION expects format:
            # <REGION_TO_DESCRIPTION><loc_x1><loc_y1><loc_x2><loc_y2>
            # where loc values are normalized to 0-999 range
            bbox = region.as_list()

            # Normalize bbox coordinates to Florence-2's 0-999 range
            # Florence-2 expects coordinates as integers in [0, 999] range
            # representing percentage of image dimension * 10
            img_width, img_height = image.size
            norm_x1 = int(bbox[0] / img_width * 999)
            norm_y1 = int(bbox[1] / img_height * 999)
            norm_x2 = int(bbox[2] / img_width * 999)
            norm_y2 = int(bbox[3] / img_height * 999)

            # Build the location-aware prompt
            prompt = f"{REGION_TO_DESCRIPTION_PROMPT}<loc_{norm_x1}><loc_{norm_y1}><loc_{norm_x2}><loc_{norm_y2}>"

            # Run inference
            result, _time_ms = model.extract_raw(image, prompt)

            # Parse the result - Florence-2 returns the description as a string
            description = ""
            if isinstance(result, str):
                description = result
            elif isinstance(result, dict) and REGION_TO_DESCRIPTION_PROMPT in result:
                description = str(result[REGION_TO_DESCRIPTION_PROMPT])
            elif isinstance(result, dict):
                # Try to get any text result
                description = str(result.get("description", result.get("text", str(result))))

            descriptions.append(CaptionedRegion(caption=description, bbox=bbox))

        # Calculate total time
        total_time_ms = (time.perf_counter() - start_time) * 1000

        # Record metrics
        INFERENCE_LATENCY_SECONDS.labels(endpoint="describe_region").observe(total_time_ms / 1000)
        INFERENCE_REQUESTS_TOTAL.labels(endpoint="describe_region", status="success").inc()

        return RegionDescriptionResponse(
            descriptions=descriptions,
            inference_time_ms=total_time_ms,
        )

    except HTTPException:
        INFERENCE_REQUESTS_TOTAL.labels(endpoint="describe_region", status="error").inc()
        raise
    except Exception as e:
        INFERENCE_REQUESTS_TOTAL.labels(endpoint="describe_region", status="error").inc()
        logger.error(f"Region description failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Region description failed: {e!s}") from e


@app.post("/phrase-grounding", response_model=PhraseGroundingResponse)
async def phrase_grounding(request: PhraseGroundingRequest) -> PhraseGroundingResponse:
    """Find objects in an image matching text descriptions (phrase grounding).

    Given an image and one or more text phrases, this endpoint uses
    Florence-2's <CAPTION_TO_PHRASE_GROUNDING> task to locate bounding boxes
    of objects that match each phrase description.

    This is useful for:
    - Finding specific objects described in natural language
    - Verifying presence of particular items or people
    - Targeted search for security-relevant objects by description

    Args:
        request: PhraseGroundingRequest with image and phrases to find

    Returns:
        PhraseGroundingResponse with bounding boxes for each matched phrase

    Example:
        Given the phrase "person in blue jacket", this endpoint returns
        bounding boxes of all persons wearing blue jackets in the image.
        If no match is found, bboxes will be empty for that phrase.
    """
    if model is None or model.model is None:
        INFERENCE_REQUESTS_TOTAL.labels(endpoint="phrase_grounding", status="error").inc()
        raise HTTPException(status_code=503, detail="Model not loaded")

    try:
        image = _decode_image(request.image)
        start_time = time.perf_counter()

        grounded_phrases: list[GroundedPhrase] = []

        # Process each phrase
        for phrase in request.phrases:
            # Florence-2 CAPTION_TO_PHRASE_GROUNDING expects format:
            # <CAPTION_TO_PHRASE_GROUNDING>phrase text here
            # This is a ML model prompt, not HTML rendering - semgrep false positive
            prompt = f"{CAPTION_TO_PHRASE_GROUNDING_PROMPT}{phrase}"  # nosemgrep

            # Run inference
            raw_result, _time_ms = model.extract_raw(image, prompt)

            # Parse the result - Florence-2 returns {'bboxes': [...], 'labels': [...]}
            bboxes: list[list[float]] = []
            confidence_scores: list[float] = []

            if isinstance(raw_result, dict):
                # Get bboxes - may be nested or flat
                result_bboxes = raw_result.get("bboxes", [])
                # Note: result_labels are not used since we already have the phrase

                # Florence-2 phrase grounding returns all matches for the phrase
                for bbox in result_bboxes:
                    if isinstance(bbox, list):
                        bboxes.append(bbox)
                        # Florence-2 doesn't return confidence for phrase grounding
                        # so we default to 1.0
                        confidence_scores.append(1.0)

            grounded_phrases.append(
                GroundedPhrase(
                    phrase=phrase,
                    bboxes=bboxes,
                    confidence_scores=confidence_scores,
                )
            )

        # Calculate total time
        total_time_ms = (time.perf_counter() - start_time) * 1000

        # Record metrics
        INFERENCE_LATENCY_SECONDS.labels(endpoint="phrase_grounding").observe(total_time_ms / 1000)
        INFERENCE_REQUESTS_TOTAL.labels(endpoint="phrase_grounding", status="success").inc()

        return PhraseGroundingResponse(
            grounded_phrases=grounded_phrases,
            inference_time_ms=total_time_ms,
        )

    except HTTPException:
        INFERENCE_REQUESTS_TOTAL.labels(endpoint="phrase_grounding", status="error").inc()
        raise
    except Exception as e:
        INFERENCE_REQUESTS_TOTAL.labels(endpoint="phrase_grounding", status="error").inc()
        logger.error(f"Phrase grounding failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Phrase grounding failed: {e!s}") from e


if __name__ == "__main__":
    import uvicorn

    # Default to 0.0.0.0 to allow connections from Docker/Podman containers.
    # When AI servers run natively on host while backend runs in containers,
    # binding to 127.0.0.1 would prevent container-to-host connectivity.
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8092"))
    uvicorn.run(app, host=host, port=port, log_level="info")
