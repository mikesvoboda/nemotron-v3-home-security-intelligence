"""CLIP adapter for the AI Gateway (backed by SigLIP 2 Base).

Translates the existing CLIP REST API (JSON with base64 images) into
Triton gRPC inference calls against the ``clip`` ONNX model (SigLIP 2 vision encoder).

The underlying model was swapped from CLIP ViT-L/14 (1.2GB) to SigLIP 2
Base patch16-224 (178MB FP16) to save 1,035MB VRAM on the A400.

Endpoints:
    POST /embed             - Generate 768-dim embedding from image
    POST /classify          - Zero-shot classification against text labels
    POST /similarity        - Image-text cosine similarity
    POST /batch-similarity  - Image vs multiple texts similarity
    POST /anomaly-score     - Anomaly detection vs baseline embedding
    GET  /health            - Model health check

Design notes on text encoding:
    The Triton ``clip`` model only handles the SigLIP 2 vision encoder.
    For endpoints that require text encoding (classify, similarity,
    batch-similarity), the gateway uses a Triton ``clip_text`` ONNX model
    (SigLIP 2 text encoder, quantized, on CPU) with the SigLIP tokenizer,
    or falls back to an in-process SigLIP 2 text encoder on CPU.

The backend's CLIPClient sends JSON payloads with base64 images and expects
JSON responses matching the existing ai-clip service format.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

import numpy as np
import torch
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ai.gateway.triton_client import TritonClientError, get_triton_client
from ai.gateway.utils import decode_base64_image, l2_normalize, preprocess_clip

logger = logging.getLogger(__name__)

router = APIRouter()

# Model configuration
VISION_MODEL_NAME = "clip"
TEXT_MODEL_NAME = "clip_text"
EMBEDDING_DIMENSION = 768
MAX_TEXT_LENGTH = 64  # SigLIP 2 standard context length (CLIP was 77)

# ---------------------------------------------------------------------------
# SigLIP 2 tokenizer (lazy-loaded, CPU-only, lightweight)
# ---------------------------------------------------------------------------

_tokenizer_lock = threading.Lock()
_clip_tokenizer: Any = None
_tokenizer_failed: bool = False

# SigLIP 2 tokenizer source — prefers local download, falls back to HuggingFace
_SIGLIP2_TOKENIZER_PATH = "/models/zoo/siglip2-base-patch16-224"
_SIGLIP2_TOKENIZER_HF = "google/siglip2-base-patch16-224"


def _ensure_tokenizer() -> bool:
    """Lazy-init the SigLIP 2 tokenizer.

    This only loads the tokenizer, not the full model.
    Thread-safe via a module-level lock.
    """
    global _clip_tokenizer, _tokenizer_failed

    if _clip_tokenizer is not None:
        return True
    if _tokenizer_failed:
        return False

    with _tokenizer_lock:
        if _clip_tokenizer is not None:
            return True
        if _tokenizer_failed:
            return False

        try:
            from transformers import AutoTokenizer

            logger.info("Loading SigLIP 2 tokenizer for Triton text encoder...")
            candidate: Any = None
            try:
                candidate = AutoTokenizer.from_pretrained(_SIGLIP2_TOKENIZER_PATH)
            except Exception:
                candidate = AutoTokenizer.from_pretrained(_SIGLIP2_TOKENIZER_HF)
            _clip_tokenizer = candidate
            logger.info("SigLIP 2 tokenizer loaded successfully")
            return True
        except Exception:
            _clip_tokenizer = None
            _tokenizer_failed = True
            logger.warning(
                "Failed to load SigLIP 2 tokenizer. "
                "classify/similarity/batch-similarity will return placeholder results.",
                exc_info=True,
            )
            return False


# ---------------------------------------------------------------------------
# In-process SigLIP 2 text encoder (lazy-loaded, CPU-only fallback)
# ---------------------------------------------------------------------------

_text_encoder_lock = threading.Lock()
_text_model: torch.nn.Module | None = None
_text_tokenizer: Any = None
_text_encoder_failed: bool = False


def _ensure_text_encoder() -> bool:
    """Lazy-init the SigLIP 2 text encoder and tokenizer.

    Returns True if the text encoder is available, False otherwise.
    Thread-safe via a module-level lock.
    """
    global _text_model, _text_tokenizer, _text_encoder_failed

    if _text_model is not None:
        return True
    if _text_encoder_failed:
        return False

    with _text_encoder_lock:
        # Double-check after acquiring lock
        if _text_model is not None:
            return True
        if _text_encoder_failed:
            return False

        try:
            from transformers import AutoModel, AutoTokenizer

            logger.info("Loading SigLIP 2 text encoder (CPU)...")
            candidate_model: torch.nn.Module | None = None
            candidate_tokenizer: Any = None
            try:
                model = AutoModel.from_pretrained(_SIGLIP2_TOKENIZER_PATH)
            except Exception:
                model = AutoModel.from_pretrained(_SIGLIP2_TOKENIZER_HF)
            model = model.eval().cpu()
            candidate_model = model
            try:
                tokenizer = AutoTokenizer.from_pretrained(_SIGLIP2_TOKENIZER_PATH)
            except Exception:
                tokenizer = AutoTokenizer.from_pretrained(_SIGLIP2_TOKENIZER_HF)
            candidate_tokenizer = tokenizer
            # Only publish globals after both model and tokenizer are ready.
            _text_model = candidate_model
            _text_tokenizer = candidate_tokenizer
            logger.info("SigLIP 2 text encoder loaded successfully")
            return True
        except Exception:
            _text_model = None
            _text_tokenizer = None
            _text_encoder_failed = True
            logger.warning(
                "Failed to load SigLIP 2 text encoder. "
                "classify/similarity/batch-similarity will return placeholder results.",
                exc_info=True,
            )
            return False


def _encode_texts_siglip(texts: list[str]) -> np.ndarray:
    """Encode text strings to L2-normalized 768-dim embeddings using SigLIP 2.

    Assumes _ensure_text_encoder() has already returned True.

    Args:
        texts: List of text strings.

    Returns:
        Numpy array of shape (len(texts), 768) with L2-normalized embeddings.
    """
    if _text_model is None or _text_tokenizer is None:
        raise RuntimeError("SigLIP text encoder is not initialized")
    tokens = _text_tokenizer(
        texts,
        return_tensors="pt",
        padding="max_length",
        max_length=MAX_TEXT_LENGTH,
        truncation=True,
    )
    with torch.no_grad():
        text_features = _text_model.get_text_features(**tokens)
        # L2-normalize
        text_features = text_features / (text_features.norm(dim=-1, keepdim=True) + 1e-8)
    return text_features.cpu().float().numpy()


# ---------------------------------------------------------------------------
# Request / Response schemas (match existing ai-clip API exactly)
# ---------------------------------------------------------------------------


class EmbedRequest(BaseModel):
    image: str = Field(..., description="Base64 encoded image")


class EmbedResponse(BaseModel):
    embedding: list[float] = Field(..., description="768-dimensional CLIP embedding")
    inference_time_ms: float = Field(..., description="Inference time in milliseconds")


class ClassifyRequest(BaseModel):
    image: str = Field(..., description="Base64 encoded image")
    labels: list[str] = Field(..., description="List of text labels to classify against")
    use_ensemble: bool = Field(default=True)
    camera_type: str = Field(default="standard")


class ClassifyResponse(BaseModel):
    scores: dict[str, float] = Field(...)
    top_label: str = Field(...)
    inference_time_ms: float = Field(...)
    ensemble_metadata: dict[str, Any] | None = None


class SimilarityRequest(BaseModel):
    image: str = Field(..., description="Base64 encoded image")
    text: str = Field(..., description="Text description")


class SimilarityResponse(BaseModel):
    similarity: float = Field(...)
    inference_time_ms: float = Field(...)


class BatchSimilarityRequest(BaseModel):
    image: str = Field(..., description="Base64 encoded image")
    texts: list[str] = Field(..., description="List of text descriptions")


class BatchSimilarityResponse(BaseModel):
    similarities: dict[str, float] = Field(...)
    inference_time_ms: float = Field(...)


class AnomalyScoreRequest(BaseModel):
    image: str = Field(..., description="Base64 encoded image")
    baseline_embedding: list[float] = Field(...)


class AnomalyScoreResponse(BaseModel):
    anomaly_score: float = Field(...)
    similarity_to_baseline: float = Field(...)
    inference_time_ms: float = Field(...)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_image_embedding(image_b64: str) -> tuple[list[float], float]:
    """Extract image embedding via Triton SigLIP 2 vision encoder.

    Args:
        image_b64: Base64-encoded image.

    Returns:
        Tuple of (normalized embedding, inference_time_ms).
    """
    start = time.monotonic()
    triton = get_triton_client()

    try:
        image_np = decode_base64_image(image_b64)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    tensor = preprocess_clip(image_np)

    try:
        result = await triton.infer(
            model_name=VISION_MODEL_NAME,
            inputs={"pixel_values": tensor},
            outputs=["pooler_output"],
        )
    except TritonClientError as e:
        raise HTTPException(status_code=503, detail=f"CLIP inference failed: {e}") from e

    raw_embedding = result["pooler_output"][0].tolist()
    embedding = l2_normalize(raw_embedding)
    inference_time_ms = (time.monotonic() - start) * 1000

    return embedding, inference_time_ms


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    a_np = np.array(a, dtype=np.float32)
    b_np = np.array(b, dtype=np.float32)
    dot = float(np.dot(a_np, b_np))
    norm_a = float(np.linalg.norm(a_np))
    norm_b = float(np.linalg.norm(b_np))
    if norm_a < 1e-8 or norm_b < 1e-8:
        return 0.0
    return dot / (norm_a * norm_b)


async def _get_text_embeddings(texts: list[str]) -> np.ndarray:
    """Get text embeddings for classify/similarity endpoints.

    Resolution order:
    1. Triton ``clip_text`` ONNX model with tokenized inputs (if deployed)
    2. In-process SigLIP 2 text encoder on CPU (lazy-loaded)
    3. Zero-vector fallback (non-functional placeholder)

    Args:
        texts: List of text strings to encode.

    Returns:
        Numpy array of shape (len(texts), EMBEDDING_DIMENSION) with L2-normalized embeddings.
    """
    triton = get_triton_client()

    # Try Triton text encoder model first (SigLIP 2 ONNX with tokenized inputs)
    try:
        if await triton.is_model_ready(TEXT_MODEL_NAME) and _ensure_tokenizer():
            if _clip_tokenizer is None:
                raise RuntimeError("SigLIP tokenizer unavailable after initialization")
            tokens = _clip_tokenizer(
                texts,
                return_tensors="np",
                padding="max_length",
                max_length=MAX_TEXT_LENGTH,
                truncation=True,
            )
            input_ids = tokens["input_ids"].astype(np.int64)
            # SigLIP 2 text model only takes input_ids (no attention_mask)
            result = await triton.infer(
                model_name=TEXT_MODEL_NAME,
                inputs={
                    "input_ids": input_ids,
                },
                outputs=["pooler_output"],
            )
            embeddings = result["pooler_output"]
            norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
            norms = np.maximum(norms, 1e-8)
            return embeddings / norms
    except Exception as e:
        logger.debug("Triton clip_text model not available: %s", e)

    # Try in-process SigLIP 2 text encoder (CPU)
    if _ensure_text_encoder():
        try:
            return _encode_texts_siglip(texts)
        except Exception as e:
            logger.warning("In-process SigLIP text encoding failed: %s", e, exc_info=True)

    # Final fallback: zero embeddings
    logger.warning(
        "No SigLIP 2 text encoder available (Triton or in-process). "
        "classify/similarity/batch-similarity will return placeholder results."
    )
    return np.zeros((len(texts), EMBEDDING_DIMENSION), dtype=np.float32)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/embed", response_model=EmbedResponse)
async def embed(request: EmbedRequest) -> EmbedResponse:
    """Generate CLIP embedding from an image.

    Matches the existing ai-clip /embed endpoint exactly.
    """
    embedding, inference_time_ms = await _get_image_embedding(request.image)

    if len(embedding) != EMBEDDING_DIMENSION:
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected embedding dimension: {len(embedding)} != {EMBEDDING_DIMENSION}",
        )

    return EmbedResponse(
        embedding=embedding,
        inference_time_ms=round(inference_time_ms, 2),
    )


@router.post("/classify", response_model=ClassifyResponse)
async def classify(request: ClassifyRequest) -> ClassifyResponse:
    """Classify an image against text labels using zero-shot classification.

    Matches the existing ai-clip /classify endpoint.
    """
    if not request.labels:
        raise HTTPException(status_code=400, detail="Labels list cannot be empty")

    start = time.monotonic()

    # Get image embedding
    image_embedding, _ = await _get_image_embedding(request.image)
    image_np = np.array(image_embedding, dtype=np.float32).reshape(1, -1)

    # Get text embeddings
    text_embeddings = await _get_text_embeddings(request.labels)

    if not np.any(text_embeddings):
        raise HTTPException(
            status_code=503,
            detail="CLIP text encoder unavailable; classification temporarily disabled",
        )

    # Compute similarities and softmax
    similarities = (image_np @ text_embeddings.T)[0]

    # Softmax normalization
    exp_sims = np.exp(similarities - np.max(similarities))
    probs = exp_sims / (exp_sims.sum() + 1e-8)

    scores = {label: round(float(probs[i]), 6) for i, label in enumerate(request.labels)}
    top_idx = int(np.argmax(probs))
    top_label = request.labels[top_idx]

    inference_time_ms = (time.monotonic() - start) * 1000

    return ClassifyResponse(
        scores=scores,
        top_label=top_label,
        inference_time_ms=round(inference_time_ms, 2),
        ensemble_metadata=None,
    )


@router.post("/similarity", response_model=SimilarityResponse)
async def similarity(request: SimilarityRequest) -> SimilarityResponse:
    """Compute cosine similarity between an image and a text description.

    Matches the existing ai-clip /similarity endpoint.
    """
    start = time.monotonic()

    image_embedding, _ = await _get_image_embedding(request.image)
    text_embeddings = await _get_text_embeddings([request.text])
    text_embedding = text_embeddings[0].tolist()

    sim = _cosine_similarity(image_embedding, text_embedding)
    inference_time_ms = (time.monotonic() - start) * 1000

    return SimilarityResponse(
        similarity=round(sim, 6),
        inference_time_ms=round(inference_time_ms, 2),
    )


@router.post("/batch-similarity", response_model=BatchSimilarityResponse)
async def batch_similarity(request: BatchSimilarityRequest) -> BatchSimilarityResponse:
    """Compute similarity between an image and multiple text descriptions.

    Matches the existing ai-clip /batch-similarity endpoint.
    """
    if not request.texts:
        raise HTTPException(status_code=400, detail="Texts list cannot be empty")

    start = time.monotonic()

    image_embedding, _ = await _get_image_embedding(request.image)
    image_np = np.array(image_embedding, dtype=np.float32).reshape(1, -1)
    text_embeddings = await _get_text_embeddings(request.texts)

    if not np.any(text_embeddings):
        raise HTTPException(
            status_code=503,
            detail="CLIP text encoder unavailable; batch similarity temporarily disabled",
        )

    sims = (image_np @ text_embeddings.T)[0]
    similarities = {text: round(float(sims[i]), 6) for i, text in enumerate(request.texts)}

    inference_time_ms = (time.monotonic() - start) * 1000

    return BatchSimilarityResponse(
        similarities=similarities,
        inference_time_ms=round(inference_time_ms, 2),
    )


@router.post("/anomaly-score", response_model=AnomalyScoreResponse)
async def anomaly_score(request: AnomalyScoreRequest) -> AnomalyScoreResponse:
    """Compute scene anomaly score by comparing image to baseline embedding.

    Matches the existing ai-clip /anomaly-score endpoint.
    """
    if len(request.baseline_embedding) != EMBEDDING_DIMENSION:
        raise HTTPException(
            status_code=400,
            detail=f"Baseline embedding must have {EMBEDDING_DIMENSION} dimensions, "
            f"got {len(request.baseline_embedding)}",
        )

    start = time.monotonic()

    image_embedding, _ = await _get_image_embedding(request.image)
    sim = _cosine_similarity(image_embedding, request.baseline_embedding)
    anomaly = max(0.0, min(1.0, 1.0 - sim))

    inference_time_ms = (time.monotonic() - start) * 1000

    return AnomalyScoreResponse(
        anomaly_score=round(anomaly, 6),
        similarity_to_baseline=round(sim, 6),
        inference_time_ms=round(inference_time_ms, 2),
    )


@router.get("/health")
async def health() -> dict[str, Any]:
    """Health check for the CLIP model."""
    triton = get_triton_client()
    vision_ready = await triton.is_model_ready(VISION_MODEL_NAME)
    text_ready = await triton.is_model_ready(TEXT_MODEL_NAME)
    return {
        "status": "healthy" if vision_ready else "degraded",
        "model": "siglip2-base-patch16-224",
        "model_loaded": vision_ready,
        "text_encoder_loaded": text_ready,
        "embedding_dimension": EMBEDDING_DIMENSION,
    }
