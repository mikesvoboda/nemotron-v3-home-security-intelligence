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


def _postprocess_pose(output: np.ndarray, conf_threshold: float = 0.25) -> list[dict[str, Any]]:
    """Post-process YOLOv8-pose output tensor to keypoint dicts.

    Args:
        output: Raw model output, shape (1, 56, 8400).
        conf_threshold: Minimum confidence to keep a detection.

    Returns:
        List of dicts with 'keypoints' list.
    """
    preds = output[0]
    if preds.shape[0] < preds.shape[1]:
        preds = preds.T  # (8400, 56)

    confidences = preds[:, 4]
    mask = confidences >= conf_threshold
    preds = preds[mask]

    if len(preds) == 0:
        return []

    COCO_KEYPOINT_NAMES = [
        "nose",
        "left_eye",
        "right_eye",
        "left_ear",
        "right_ear",
        "left_shoulder",
        "right_shoulder",
        "left_elbow",
        "right_elbow",
        "left_wrist",
        "right_wrist",
        "left_hip",
        "right_hip",
        "left_knee",
        "right_knee",
        "left_ankle",
        "right_ankle",
    ]

    results = []
    for det in preds:
        kp_data = det[5:]
        keypoints = []
        for i in range(17):
            keypoints.append(
                {
                    "name": COCO_KEYPOINT_NAMES[i],
                    "x": round(float(kp_data[i * 3]), 1),
                    "y": round(float(kp_data[i * 3 + 1]), 1),
                    "confidence": round(float(kp_data[i * 3 + 2]), 4),
                }
            )
        results.append({"keypoints": keypoints})

    return results


def _postprocess_threat(output: np.ndarray, conf_threshold: float = 0.25) -> list[dict[str, Any]]:
    """Post-process YOLOv8 threat detection output tensor.

    Args:
        output: Raw model output, shape (1, 8, 8400).
            8 = 4 box + 4 class scores.
        conf_threshold: Minimum confidence to keep a detection.

    Returns:
        List of detection dicts with class, confidence, bbox.
    """
    THREAT_CLASSES = ["knife", "pistol", "rifle", "threat_object"]

    preds = output[0]
    if preds.shape[0] < preds.shape[1]:
        preds = preds.T  # (8400, 8)

    boxes_cxcywh = preds[:, :4]
    class_scores = preds[:, 4:]

    class_ids = np.argmax(class_scores, axis=1)
    confidences = np.array([class_scores[i, class_ids[i]] for i in range(len(class_ids))])

    mask = confidences >= conf_threshold
    boxes_cxcywh = boxes_cxcywh[mask]
    class_ids = class_ids[mask]
    confidences = confidences[mask]

    if len(confidences) == 0:
        return []

    detections = []
    for i in range(len(confidences)):
        cx, cy, w, h = boxes_cxcywh[i]
        cls_id = int(class_ids[i])
        cls_name = THREAT_CLASSES[cls_id] if cls_id < len(THREAT_CLASSES) else f"threat_{cls_id}"
        detections.append(
            {
                "class": cls_name,
                "confidence": round(float(confidences[i]), 4),
                "bbox": {
                    "x": round(float(cx - w / 2)),
                    "y": round(float(cy - h / 2)),
                    "width": round(float(w)),
                    "height": round(float(h)),
                },
            }
        )

    return detections


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
        from ai.gateway.utils import preprocess_yolo

        image_bytes = decode_base64_to_bytes(request.image)
        input_tensor = preprocess_yolo(image_bytes, 640)

        result = await triton.infer(
            model_name="pose",
            inputs={"images": input_tensor.astype(np.float32)},
            outputs=["output0"],
        )

        keypoints = _postprocess_pose(result["output0"])

        inference_time_ms = (time.monotonic() - start) * 1000

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
        from ai.gateway.utils import preprocess_yolo

        image_bytes = decode_base64_to_bytes(request.image)
        input_tensor = preprocess_yolo(image_bytes, 640)

        result = await triton.infer(
            model_name="threat",
            inputs={"images": input_tensor.astype(np.float32)},
            outputs=["output0"],
        )

        detections = _postprocess_threat(result["output0"])

        inference_time_ms = (time.monotonic() - start) * 1000

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
            outputs=["embedding"],
        )

        embedding = result["embedding"][0].tolist()

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
            outputs=["depth_map"],
        )

        depth_map = result["depth_map"][0]
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
