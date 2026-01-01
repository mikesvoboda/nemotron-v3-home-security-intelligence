"""CLIP Embedding Server

HTTP server wrapping CLIP ViT-L model for generating embeddings
used in entity re-identification across cameras.

Port: 8093 (configurable via PORT env var)
Expected VRAM: ~800MB
"""

import base64
import binascii
import io
import logging
import os
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import torch
from fastapi import FastAPI, HTTPException
from PIL import Image
from pydantic import BaseModel, Field
from transformers import CLIPModel, CLIPProcessor

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Size limits for image uploads (10MB is reasonable for security camera images)
MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024  # 10MB
# Base64 encoding increases size by ~33%, so pre-decode limit is ~13.3MB
MAX_BASE64_SIZE_BYTES = int(MAX_IMAGE_SIZE_BYTES * 4 / 3) + 100  # ~13.3MB + padding

# CLIP ViT-L embedding dimension
EMBEDDING_DIMENSION = 768


class EmbedRequest(BaseModel):
    """Request format for embed endpoint."""

    image: str = Field(..., description="Base64 encoded image")


class EmbedResponse(BaseModel):
    """Response format for embed endpoint."""

    embedding: list[float] = Field(..., description="768-dimensional CLIP embedding")
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


class CLIPEmbeddingModel:
    """CLIP ViT-L model wrapper for generating embeddings."""

    def __init__(
        self,
        model_path: str,
        device: str = "cuda:0",
    ):
        """Initialize CLIP model.

        Args:
            model_path: Path to HuggingFace model directory or model name
            device: Device to run inference on (cuda:0, cpu)
        """
        self.model_path = model_path
        self.device = device
        self.model: Any = None
        self.processor: Any = None

        logger.info(f"Initializing CLIP model from {self.model_path}")
        logger.info(f"Device: {device}")

    def load_model(self) -> None:
        """Load the model into memory using HuggingFace Transformers."""
        try:
            logger.info("Loading CLIP model with HuggingFace Transformers...")

            # Determine device and dtype
            if "cuda" in self.device and torch.cuda.is_available():
                dtype = torch.float16
            else:
                self.device = "cpu"
                dtype = torch.float32

            # Load processor
            self.processor = CLIPProcessor.from_pretrained(self.model_path)

            # Load model with appropriate settings
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
        dummy_image = Image.new("RGB", (224, 224), color=(128, 128, 128))

        for i in range(num_iterations):
            try:
                _ = self.extract_embedding(dummy_image)
                logger.info(f"Warmup iteration {i + 1}/{num_iterations} complete")
            except Exception as e:
                logger.warning(f"Warmup iteration {i + 1} failed: {e}")

        logger.info("Warmup complete")

    def extract_embedding(self, image: Image.Image) -> tuple[list[float], float]:
        """Generate a 768-dimensional embedding from an image.

        Args:
            image: PIL Image to process

        Returns:
            Tuple of (embedding list, inference_time_ms)
        """
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
        with torch.no_grad():
            image_features = self.model.get_image_features(**inputs)

            # Normalize embedding
            image_features = image_features / image_features.norm(p=2, dim=-1, keepdim=True)

        # Convert to list
        embedding: list[float] = image_features[0].cpu().float().numpy().tolist()

        inference_time_ms = (time.perf_counter() - start_time) * 1000

        return embedding, inference_time_ms


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
    global model  # noqa: PLW0603

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

    return HealthResponse(
        status="healthy" if model is not None and model.model is not None else "degraded",
        model="clip-vit-large-patch14",
        model_loaded=model is not None and model.model is not None,
        device=device,
        cuda_available=cuda_available,
        vram_used_gb=vram_used,
        embedding_dimension=EMBEDDING_DIMENSION,
    )


@app.post("/embed", response_model=EmbedResponse)
async def embed(request: EmbedRequest) -> EmbedResponse:
    """Generate CLIP embedding from an image.

    Accepts a base64-encoded image and returns a 768-dimensional embedding
    suitable for cosine similarity comparisons.

    Returns:
        Embedding results with the 768-dim vector and inference time
    """
    if model is None or model.model is None:
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

        # Generate embedding
        embedding, inference_time_ms = model.extract_embedding(image)

        return EmbedResponse(
            embedding=embedding,
            inference_time_ms=inference_time_ms,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Embedding extraction failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Embedding extraction failed: {e!s}") from e


if __name__ == "__main__":
    import uvicorn

    # Default to 0.0.0.0 to allow connections from Docker/Podman containers.
    # When AI servers run natively on host while backend runs in containers,
    # binding to 127.0.0.1 would prevent container-to-host connectivity.
    host = os.getenv("HOST", "0.0.0.0")  # noqa: S104
    port = int(os.getenv("PORT", "8093"))
    uvicorn.run(app, host=host, port=port, log_level="info")
