"""Florence-2 Vision-Language Server

HTTP server wrapping Florence-2-large model for vision-language queries.
Supports attribute extraction from security camera images.

Port: 8092 (configurable via PORT env var)
Expected VRAM: ~1.2GB
"""

import base64
import binascii
import io
import logging
import os
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

import torch
from fastapi import FastAPI, HTTPException
from PIL import Image
from pydantic import BaseModel, Field
from transformers import AutoModelForCausalLM, AutoProcessor

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

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


class ExtractRequest(BaseModel):
    """Request format for extract endpoint."""

    image: str = Field(..., description="Base64 encoded image")
    prompt: str = Field(
        default="<CAPTION>",
        description="Florence-2 prompt (e.g., <CAPTION>, <DETAILED_CAPTION>, <MORE_DETAILED_CAPTION>)",
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


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    model: str
    model_loaded: bool
    device: str
    cuda_available: bool
    vram_used_gb: float | None = None


class Florence2Model:
    """Florence-2 model wrapper using HuggingFace Transformers."""

    def __init__(
        self,
        model_path: str,
        device: str = "cuda:0",
    ):
        """Initialize Florence-2 model.

        Args:
            model_path: Path to HuggingFace model directory or model name
            device: Device to run inference on (cuda:0, cpu)
        """
        self.model_path = model_path
        self.device = device
        self.model: Any = None
        self.processor: Any = None

        logger.info(f"Initializing Florence-2 model from {self.model_path}")
        logger.info(f"Device: {device}")

    def load_model(self) -> None:
        """Load the model into memory using HuggingFace Transformers."""
        try:
            logger.info("Loading Florence-2 model with HuggingFace Transformers...")

            # Determine device and dtype
            if "cuda" in self.device and torch.cuda.is_available():
                dtype = torch.float16
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
        with torch.no_grad():
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
        with torch.no_grad():
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
    global model  # noqa: PLW0603

    # Startup
    logger.info("Starting Florence-2 Vision-Language Server...")

    # Load model configuration from environment or defaults
    model_path = os.environ.get("FLORENCE_MODEL_PATH", "/models/florence-2-large")
    device = "cuda:0" if torch.cuda.is_available() else "cpu"

    try:
        model = Florence2Model(
            model_path=model_path,
            device=device,
        )
        model.load_model()
        logger.info("Model loaded successfully")
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

    Returns:
        Extraction results with the generated text response
    """
    if model is None or model.model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    try:
        # Validate prompt
        if request.prompt not in SUPPORTED_PROMPTS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported prompt: {request.prompt}. "
                f"Supported prompts: {', '.join(sorted(SUPPORTED_PROMPTS))}",
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

        # Run extraction
        result, inference_time_ms = model.extract(image, request.prompt)

        return ExtractResponse(
            result=result,
            prompt_used=request.prompt,
            inference_time_ms=inference_time_ms,
        )

    except HTTPException:
        raise
    except Exception as e:
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


if __name__ == "__main__":
    import uvicorn

    # Default to 0.0.0.0 to allow connections from Docker/Podman containers.
    # When AI servers run natively on host while backend runs in containers,
    # binding to 127.0.0.1 would prevent container-to-host connectivity.
    host = os.getenv("HOST", "0.0.0.0")  # noqa: S104
    port = int(os.getenv("PORT", "8092"))
    uvicorn.run(app, host=host, port=port, log_level="info")
