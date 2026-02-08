"""Enrichment light adapter for the AI Gateway.

Translates the existing ai-enrichment-light REST API into Triton gRPC
inference calls against lightweight models:

    /pose-analyze    -> Triton ``pose`` model (TensorRT)
    /threat-detect   -> Triton ``threat`` model (TensorRT)
    /person-reid     -> Triton ``reid`` model (ONNX Runtime)
    /pet-classify    -> Triton ``pet`` model (ONNX Runtime)
    /depth-estimate  -> Triton ``depth`` model (ONNX Runtime)

The backend's EnrichmentClient sends JSON payloads with base64 images to
the enrichment-light service (port 8096) and expects JSON responses
matching the current format.
"""

from __future__ import annotations

import base64
import io
import json
import logging
import time
from typing import Any

import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ai.gateway.triton_client import TritonClientError, get_triton_client
from ai.gateway.utils import decode_base64_image, decode_base64_to_bytes

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / Response schemas (match existing ai-enrichment-light API)
# ---------------------------------------------------------------------------


class ImageRequest(BaseModel):
    image: str = Field(..., description="Base64 encoded image")


class BBoxRequest(BaseModel):
    image: str = Field(..., description="Base64 encoded image")
    bbox: dict[str, float] | None = Field(default=None)


class PoseResponse(BaseModel):
    keypoints: list[dict[str, Any]] = Field(...)
    num_people: int = Field(...)
    body_orientation: str | None = Field(default=None)
    pose_quality: str | None = Field(default=None)
    inference_time_ms: float = Field(...)


class ThreatResponse(BaseModel):
    threat_detected: bool = Field(...)
    threat_type: str | None = Field(default=None)
    confidence: float = Field(...)
    detections: list[dict[str, Any]] = Field(default_factory=list)
    inference_time_ms: float = Field(...)


class ReIDResponse(BaseModel):
    embedding: list[float] = Field(...)
    embedding_dimension: int = Field(...)
    inference_time_ms: float = Field(...)


class PetResponse(BaseModel):
    pet_type: str = Field(...)
    breed: str = Field(...)
    confidence: float = Field(...)
    is_household_pet: bool = Field(...)
    cat_score: float = Field(default=0.0)
    dog_score: float = Field(default=0.0)
    inference_time_ms: float = Field(...)


class DepthResponse(BaseModel):
    depth_map_base64: str = Field(...)
    min_depth: float = Field(...)
    max_depth: float = Field(...)
    mean_depth: float = Field(...)
    inference_time_ms: float = Field(...)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _softmax(x: np.ndarray) -> np.ndarray:
    """Compute softmax over a 1D array."""
    e = np.exp(x - np.max(x))
    return e / (e.sum() + 1e-8)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/pose-analyze", response_model=PoseResponse)
async def pose_analyze(request: BBoxRequest) -> PoseResponse:
    """Analyze human pose keypoints from an image.

    Uses the YOLO-Pose TensorRT model via Triton for fast keypoint detection.
    """
    start = time.monotonic()
    triton = get_triton_client()

    try:
        image_bytes = decode_base64_to_bytes(request.image)
        image_input = np.array([image_bytes], dtype=object)

        result = await triton.infer(
            model_name="pose",
            inputs={"INPUT_IMAGE": image_input},
            outputs=["OUTPUT_KEYPOINTS"],
        )

        raw = result["OUTPUT_KEYPOINTS"]
        if raw.dtype == object:
            keypoints_data = json.loads(
                raw[0].decode("utf-8") if isinstance(raw[0], bytes) else str(raw[0])
            )
        else:
            keypoints_data = []

        inference_time_ms = (time.monotonic() - start) * 1000

        keypoints = keypoints_data if isinstance(keypoints_data, list) else []

        return PoseResponse(
            keypoints=keypoints,
            num_people=len(keypoints),
            body_orientation=None,
            pose_quality=None,
            inference_time_ms=round(inference_time_ms, 2),
        )
    except TritonClientError as e:
        raise HTTPException(status_code=503, detail=f"Pose analysis failed: {e}") from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/threat-detect", response_model=ThreatResponse)
async def threat_detect(request: BBoxRequest) -> ThreatResponse:
    """Detect weapons or threats in an image.

    Uses the YOLO weapon detection TensorRT model via Triton.
    """
    start = time.monotonic()
    triton = get_triton_client()

    try:
        image_bytes = decode_base64_to_bytes(request.image)
        image_input = np.array([image_bytes], dtype=object)

        result = await triton.infer(
            model_name="threat",
            inputs={"INPUT_IMAGE": image_input},
            outputs=["OUTPUT_DETECTIONS"],
        )

        raw = result["OUTPUT_DETECTIONS"]
        if raw.dtype == object:
            detections_data = json.loads(
                raw[0].decode("utf-8") if isinstance(raw[0], bytes) else str(raw[0])
            )
        else:
            detections_data = []

        inference_time_ms = (time.monotonic() - start) * 1000

        detections = detections_data if isinstance(detections_data, list) else []
        threat_detected = len(detections) > 0
        threat_type = detections[0].get("class", None) if threat_detected else None
        confidence = detections[0].get("confidence", 0.0) if threat_detected else 0.0

        return ThreatResponse(
            threat_detected=threat_detected,
            threat_type=threat_type,
            confidence=round(confidence, 4),
            detections=detections,
            inference_time_ms=round(inference_time_ms, 2),
        )
    except TritonClientError as e:
        raise HTTPException(status_code=503, detail=f"Threat detection failed: {e}") from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/person-reid", response_model=ReIDResponse)
async def person_reid(request: BBoxRequest) -> ReIDResponse:
    """Generate person re-identification embedding.

    Uses the OSNet ONNX model via Triton to produce a compact embedding
    for matching the same person across different cameras.
    """
    start = time.monotonic()
    triton = get_triton_client()

    try:
        image_np = decode_base64_image(request.image)
        from PIL import Image

        # OSNet expects 256x128 input
        pil_img = Image.fromarray(image_np).resize((128, 256))
        arr = np.array(pil_img, dtype=np.float32) / 255.0
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        arr = (arr - mean) / std
        tensor = arr.transpose(2, 0, 1)[np.newaxis, ...].astype(np.float32)

        result = await triton.infer(
            model_name="reid",
            inputs={"input": tensor},
            outputs=["output"],
        )

        embedding = result["output"][0].tolist()

        # L2 normalize
        import math

        norm = math.sqrt(sum(x * x for x in embedding))
        if norm > 1e-8:
            embedding = [x / norm for x in embedding]

        inference_time_ms = (time.monotonic() - start) * 1000

        return ReIDResponse(
            embedding=embedding,
            embedding_dimension=len(embedding),
            inference_time_ms=round(inference_time_ms, 2),
        )
    except TritonClientError as e:
        raise HTTPException(status_code=503, detail=f"Person ReID failed: {e}") from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/pet-classify", response_model=PetResponse)
async def pet_classify(request: BBoxRequest) -> PetResponse:
    """Classify cat/dog from an animal crop."""
    start = time.monotonic()
    triton = get_triton_client()

    try:
        image_np = decode_base64_image(request.image)
        from PIL import Image

        pil_img = Image.fromarray(image_np).resize((224, 224))
        arr = np.array(pil_img, dtype=np.float32) / 255.0
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        arr = (arr - mean) / std
        tensor = arr.transpose(2, 0, 1)[np.newaxis, ...].astype(np.float32)

        result = await triton.infer(
            model_name="pet",
            inputs={"input": tensor},
            outputs=["output"],
        )

        logits = result["output"][0]
        probs = _softmax(logits)
        labels = ["cat", "dog"]
        pred_idx = int(np.argmax(probs))

        inference_time_ms = (time.monotonic() - start) * 1000

        return PetResponse(
            pet_type=labels[pred_idx] if pred_idx < len(labels) else "unknown",
            breed="unknown",
            confidence=round(float(probs[pred_idx]), 4),
            is_household_pet=True,
            cat_score=round(float(probs[0]), 4) if len(probs) > 0 else 0.0,
            dog_score=round(float(probs[1]), 4) if len(probs) > 1 else 0.0,
            inference_time_ms=round(inference_time_ms, 2),
        )
    except TritonClientError as e:
        raise HTTPException(status_code=503, detail=f"Pet classification failed: {e}") from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/depth-estimate", response_model=DepthResponse)
async def depth_estimate(request: ImageRequest) -> DepthResponse:
    """Estimate monocular depth from an image."""
    start = time.monotonic()
    triton = get_triton_client()

    try:
        image_np = decode_base64_image(request.image)
        from PIL import Image as PILImage

        pil_img = PILImage.fromarray(image_np).resize((518, 518))
        arr = np.array(pil_img, dtype=np.float32) / 255.0
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        arr = (arr - mean) / std
        tensor = arr.transpose(2, 0, 1)[np.newaxis, ...].astype(np.float32)

        result = await triton.infer(
            model_name="depth",
            inputs={"input": tensor},
            outputs=["output"],
        )

        depth_map = result["output"][0]
        if depth_map.ndim > 2:
            depth_map = depth_map.squeeze()

        min_d = float(depth_map.min())
        max_d = float(depth_map.max())
        mean_d = float(depth_map.mean())

        if max_d - min_d > 0:
            norm = ((depth_map - min_d) / (max_d - min_d) * 255).astype(np.uint8)
        else:
            norm = np.zeros_like(depth_map, dtype=np.uint8)

        depth_img = PILImage.fromarray(norm, mode="L")
        buf = io.BytesIO()
        depth_img.save(buf, format="PNG")
        depth_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

        inference_time_ms = (time.monotonic() - start) * 1000

        return DepthResponse(
            depth_map_base64=depth_b64,
            min_depth=round(min_d, 4),
            max_depth=round(max_d, 4),
            mean_depth=round(mean_d, 4),
            inference_time_ms=round(inference_time_ms, 2),
        )
    except TritonClientError as e:
        raise HTTPException(status_code=503, detail=f"Depth estimation failed: {e}") from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/health")
async def health() -> dict[str, Any]:
    """Health check for enrichment-light models."""
    triton = get_triton_client()

    models = ["pose", "threat", "reid", "pet", "depth"]
    statuses: dict[str, bool] = {}
    for model in models:
        statuses[model] = await triton.is_model_ready(model)

    all_ready = all(statuses.values())

    return {
        "status": "healthy" if all_ready else "degraded",
        "models": statuses,
    }
