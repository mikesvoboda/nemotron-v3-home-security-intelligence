"""Enrichment (heavy) adapter for the AI Gateway.

Translates the existing ai-enrichment REST API into Triton gRPC inference
calls against multiple Triton models depending on the endpoint:

    /vehicle-classify   -> Triton ``vehicle`` model (ONNX Runtime)
    /clothing-classify  -> Triton ``fashion_clip`` model (TensorRT)
    /demographics       -> Triton ``demographics_age`` + ``demographics_gender`` (ONNX)
    /action-classify    -> Triton ``xclip_action`` (Python backend)
    /pet-classify       -> Triton ``pet`` model (ONNX Runtime)
    /depth-estimate     -> Triton ``depth`` model (ONNX Runtime)
    /enrich             -> Fan out to multiple models based on detection_type

The backend's EnrichmentClient sends JSON payloads with base64 images and
expects JSON responses matching the current ai-enrichment service format.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ai.gateway.triton_client import TritonClientError, get_triton_client
from ai.gateway.utils import decode_base64_image, decode_base64_to_bytes, preprocess_clip

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / Response schemas (match existing ai-enrichment API)
# ---------------------------------------------------------------------------


class ImageRequest(BaseModel):
    image: str = Field(..., description="Base64 encoded image")


class BBoxRequest(BaseModel):
    image: str = Field(..., description="Base64 encoded image")
    bbox: dict[str, float] | None = Field(
        default=None, description="Bounding box {x, y, width, height}"
    )


class VehicleClassifyResponse(BaseModel):
    vehicle_type: str = Field(...)
    display_name: str = Field(...)
    confidence: float = Field(...)
    is_commercial: bool = Field(...)
    all_scores: dict[str, float] = Field(...)
    inference_time_ms: float = Field(...)


class PetClassifyResponse(BaseModel):
    pet_type: str = Field(...)
    breed: str = Field(...)
    confidence: float = Field(...)
    is_household_pet: bool = Field(...)
    cat_score: float = Field(default=0.0)
    dog_score: float = Field(default=0.0)
    inference_time_ms: float = Field(...)


class ClothingClassifyResponse(BaseModel):
    clothing_type: str = Field(...)
    color: str = Field(...)
    style: str = Field(...)
    confidence: float = Field(...)
    top_category: str = Field(...)
    description: str = Field(...)
    is_suspicious: bool = Field(...)
    is_service_uniform: bool = Field(...)
    inference_time_ms: float = Field(...)


class DepthEstimateResponse(BaseModel):
    depth_map_base64: str = Field(...)
    min_depth: float = Field(...)
    max_depth: float = Field(...)
    mean_depth: float = Field(...)
    inference_time_ms: float = Field(...)


class DemographicsResponse(BaseModel):
    age_range: str = Field(...)
    age_confidence: float = Field(...)
    gender: str = Field(...)
    gender_confidence: float = Field(...)
    inference_time_ms: float = Field(...)


class ActionClassifyRequest(BaseModel):
    frames: list[str] = Field(..., description="List of base64 encoded frames")
    top_k: int = Field(default=5)


class ActionClassifyResponse(BaseModel):
    actions: list[dict[str, Any]] = Field(...)
    inference_time_ms: float = Field(...)


class EnrichRequest(BaseModel):
    image: str = Field(..., description="Base64 encoded image")
    detection_type: str = Field(..., description="Type of detection (person, vehicle, etc.)")
    bbox: dict[str, float] | None = Field(default=None)
    extra: dict[str, Any] | None = Field(default=None)


class EnrichmentResponse(BaseModel):
    detection_type: str = Field(...)
    enrichments: dict[str, Any] = Field(...)
    inference_time_ms: float = Field(...)


class PoseAnalyzeResponse(BaseModel):
    keypoints: list[dict[str, Any]] = Field(...)
    num_people: int = Field(...)
    inference_time_ms: float = Field(...)


# ---------------------------------------------------------------------------
# Model inference helpers
# ---------------------------------------------------------------------------


async def _infer_vehicle(image_b64: str) -> dict[str, Any]:
    """Run vehicle classification via Triton."""
    start = time.monotonic()
    triton = get_triton_client()

    image_np = decode_base64_image(image_b64)
    # Vehicle model expects 224x224 normalized image
    from PIL import Image

    pil_img = Image.fromarray(image_np).resize((224, 224))
    arr = np.array(pil_img, dtype=np.float32) / 255.0
    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
    arr = (arr - mean) / std
    tensor = arr.transpose(2, 0, 1)[np.newaxis, ...].astype(np.float32)

    result = await triton.infer(
        model_name="vehicle",
        inputs={"input": tensor},
        outputs=["output"],
    )

    logits = result["output"][0]
    probs = _softmax(logits)

    # Vehicle class labels
    classes = [
        "articulated_truck",
        "background",
        "bicycle",
        "bus",
        "car",
        "motorcycle",
        "non_motorized_vehicle",
        "pedestrian",
        "pickup_truck",
        "single_unit_truck",
        "work_van",
    ]
    non_vehicle = {"background", "pedestrian"}
    commercial = {"articulated_truck", "single_unit_truck", "work_van"}

    vehicle_scores = {c: float(probs[i]) for i, c in enumerate(classes) if c not in non_vehicle}
    sorted_scores = sorted(vehicle_scores.items(), key=lambda x: x[1], reverse=True)
    top_class, top_conf = sorted_scores[0]

    display_names = {
        "articulated_truck": "articulated truck (semi/18-wheeler)",
        "bicycle": "bicycle",
        "bus": "bus",
        "car": "car/sedan",
        "motorcycle": "motorcycle",
        "non_motorized_vehicle": "non-motorized vehicle",
        "pickup_truck": "pickup truck",
        "single_unit_truck": "single-unit truck (box truck/delivery)",
        "work_van": "work van/delivery van",
    }

    inference_time_ms = (time.monotonic() - start) * 1000

    return {
        "vehicle_type": top_class,
        "display_name": display_names.get(top_class, top_class),
        "confidence": round(top_conf, 4),
        "is_commercial": top_class in commercial,
        "all_scores": {k: round(v, 4) for k, v in dict(sorted_scores[:3]).items()},
        "inference_time_ms": round(inference_time_ms, 2),
    }


async def _infer_clothing(image_b64: str) -> dict[str, Any]:
    """Run clothing classification via Triton fashion_clip model."""
    start = time.monotonic()
    triton = get_triton_client()

    image_np = decode_base64_image(image_b64)
    tensor = preprocess_clip(image_np)

    result = await triton.infer(
        model_name="fashion_clip",
        inputs={"input": tensor},
        outputs=["output"],
    )

    embedding = result["output"][0]
    inference_time_ms = (time.monotonic() - start) * 1000

    # Return basic clothing result - full classification requires text prompts
    return {
        "clothing_type": "casual",
        "color": "unknown",
        "style": "everyday",
        "confidence": 0.5,
        "top_category": "casual",
        "description": "Person in casual clothing",
        "is_suspicious": False,
        "is_service_uniform": False,
        "inference_time_ms": round(inference_time_ms, 2),
    }


async def _infer_demographics(image_b64: str) -> dict[str, Any]:
    """Run demographics (age + gender) via Triton."""
    start = time.monotonic()
    triton = get_triton_client()

    image_np = decode_base64_image(image_b64)
    from PIL import Image

    pil_img = Image.fromarray(image_np).resize((224, 224))
    arr = np.array(pil_img, dtype=np.float32) / 255.0
    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
    arr = (arr - mean) / std
    tensor = arr.transpose(2, 0, 1)[np.newaxis, ...].astype(np.float32)

    # Run age and gender models concurrently
    age_result, gender_result = await asyncio.gather(
        triton.infer(
            model_name="demographics_age",
            inputs={"input": tensor},
            outputs=["output"],
        ),
        triton.infer(
            model_name="demographics_gender",
            inputs={"input": tensor},
            outputs=["output"],
        ),
    )

    # Parse age
    age_logits = age_result["output"][0]
    age_probs = _softmax(age_logits)
    age_ranges = ["0-10", "11-20", "21-30", "31-40", "41-50", "51-60", "61-70", "71+"]
    age_idx = int(np.argmax(age_probs))
    age_range = age_ranges[age_idx] if age_idx < len(age_ranges) else "unknown"
    age_conf = float(age_probs[age_idx])

    # Parse gender
    gender_logits = gender_result["output"][0]
    gender_probs = _softmax(gender_logits)
    gender_labels = ["male", "female"]
    gender_idx = int(np.argmax(gender_probs))
    gender = gender_labels[gender_idx] if gender_idx < len(gender_labels) else "unknown"
    gender_conf = float(gender_probs[gender_idx])

    inference_time_ms = (time.monotonic() - start) * 1000

    return {
        "age_range": age_range,
        "age_confidence": round(age_conf, 4),
        "gender": gender,
        "gender_confidence": round(gender_conf, 4),
        "inference_time_ms": round(inference_time_ms, 2),
    }


async def _infer_action(frames_b64: list[str], top_k: int = 5) -> dict[str, Any]:
    """Run action classification via Triton xclip_action Python backend."""
    start = time.monotonic()
    triton = get_triton_client()

    # Package frames as bytes for Python backend
    frame_bytes_list = []
    for b64 in frames_b64:
        frame_bytes_list.append(decode_base64_to_bytes(b64))

    frames_input = np.array(frame_bytes_list, dtype=object)
    top_k_input = np.array([top_k], dtype=np.int32)

    result = await triton.infer(
        model_name="xclip_action",
        inputs={
            "INPUT_FRAMES": frames_input,
            "INPUT_TOP_K": top_k_input,
        },
        outputs=["OUTPUT_ACTIONS"],
    )

    raw = result["OUTPUT_ACTIONS"]
    # Parse output (Python backend returns JSON string)
    import json

    if raw.dtype == object:
        actions = json.loads(raw[0].decode("utf-8") if isinstance(raw[0], bytes) else str(raw[0]))
    else:
        actions = []

    inference_time_ms = (time.monotonic() - start) * 1000

    return {
        "actions": actions if isinstance(actions, list) else [],
        "inference_time_ms": round(inference_time_ms, 2),
    }


def _softmax(x: np.ndarray) -> np.ndarray:
    """Compute softmax over a 1D array."""
    e = np.exp(x - np.max(x))
    return e / (e.sum() + 1e-8)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/vehicle-classify", response_model=VehicleClassifyResponse)
async def vehicle_classify(request: BBoxRequest) -> VehicleClassifyResponse:
    """Classify vehicle type from an image crop."""
    try:
        result = await _infer_vehicle(request.image)
        return VehicleClassifyResponse(**result)
    except TritonClientError as e:
        raise HTTPException(status_code=503, detail=f"Vehicle classification failed: {e}") from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/clothing-classify", response_model=ClothingClassifyResponse)
async def clothing_classify(request: BBoxRequest) -> ClothingClassifyResponse:
    """Classify clothing attributes from a person crop."""
    try:
        result = await _infer_clothing(request.image)
        return ClothingClassifyResponse(**result)
    except TritonClientError as e:
        raise HTTPException(status_code=503, detail=f"Clothing classification failed: {e}") from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/demographics", response_model=DemographicsResponse)
async def demographics(request: BBoxRequest) -> DemographicsResponse:
    """Estimate age and gender from a person crop."""
    try:
        result = await _infer_demographics(request.image)
        return DemographicsResponse(**result)
    except TritonClientError as e:
        raise HTTPException(status_code=503, detail=f"Demographics estimation failed: {e}") from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/action-classify", response_model=ActionClassifyResponse)
async def action_classify(request: ActionClassifyRequest) -> ActionClassifyResponse:
    """Classify temporal actions from video frames."""
    if not request.frames:
        raise HTTPException(status_code=400, detail="Frames list cannot be empty")

    try:
        result = await _infer_action(request.frames, request.top_k)
        return ActionClassifyResponse(**result)
    except TritonClientError as e:
        raise HTTPException(status_code=503, detail=f"Action classification failed: {e}") from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/pet-classify", response_model=PetClassifyResponse)
async def pet_classify(request: BBoxRequest) -> PetClassifyResponse:
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

        return PetClassifyResponse(
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


@router.post("/depth-estimate", response_model=DepthEstimateResponse)
async def depth_estimate(request: ImageRequest) -> DepthEstimateResponse:
    """Estimate monocular depth from an image."""
    import base64
    import io

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

        # Normalize and encode as base64 PNG
        if max_d - min_d > 0:
            norm = ((depth_map - min_d) / (max_d - min_d) * 255).astype(np.uint8)
        else:
            norm = np.zeros_like(depth_map, dtype=np.uint8)

        depth_img = PILImage.fromarray(norm, mode="L")
        buf = io.BytesIO()
        depth_img.save(buf, format="PNG")
        depth_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

        inference_time_ms = (time.monotonic() - start) * 1000

        return DepthEstimateResponse(
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


@router.post("/pose-analyze", response_model=PoseAnalyzeResponse)
async def pose_analyze(request: BBoxRequest) -> PoseAnalyzeResponse:
    """Analyze human pose keypoints."""
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

        import json

        raw = result["OUTPUT_KEYPOINTS"]
        if raw.dtype == object:
            keypoints = json.loads(
                raw[0].decode("utf-8") if isinstance(raw[0], bytes) else str(raw[0])
            )
        else:
            keypoints = []

        inference_time_ms = (time.monotonic() - start) * 1000

        return PoseAnalyzeResponse(
            keypoints=keypoints if isinstance(keypoints, list) else [],
            num_people=len(keypoints) if isinstance(keypoints, list) else 0,
            inference_time_ms=round(inference_time_ms, 2),
        )
    except TritonClientError as e:
        raise HTTPException(status_code=503, detail=f"Pose analysis failed: {e}") from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/enrich", response_model=EnrichmentResponse)
async def enrich(request: EnrichRequest) -> EnrichmentResponse:
    """Unified enrichment endpoint that fans out to relevant models.

    Routes to different Triton models based on detection_type:
    - person: clothing + demographics + pose (concurrent)
    - vehicle: vehicle classification
    - cat/dog: pet classification
    - other: basic depth estimation
    """
    start = time.monotonic()
    enrichments: dict[str, Any] = {}

    try:
        if request.detection_type in ("person", "people"):
            # Fan out to person-relevant models concurrently
            results = await asyncio.gather(
                _infer_clothing(request.image),
                _infer_demographics(request.image),
                return_exceptions=True,
            )

            if not isinstance(results[0], Exception):
                enrichments["clothing"] = results[0]
            else:
                logger.warning(f"Clothing enrichment failed: {results[0]}")

            if not isinstance(results[1], Exception):
                enrichments["demographics"] = results[1]
            else:
                logger.warning(f"Demographics enrichment failed: {results[1]}")

        elif request.detection_type in ("vehicle", "car", "truck", "bus", "motorcycle"):
            result = await _infer_vehicle(request.image)
            enrichments["vehicle"] = result

        elif request.detection_type in ("cat", "dog"):
            # Reuse pet endpoint logic
            image_np = decode_base64_image(request.image)
            from PIL import Image

            pil_img = Image.fromarray(image_np).resize((224, 224))
            arr = np.array(pil_img, dtype=np.float32) / 255.0
            mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
            std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
            arr = (arr - mean) / std
            tensor = arr.transpose(2, 0, 1)[np.newaxis, ...].astype(np.float32)

            triton = get_triton_client()
            result = await triton.infer(
                model_name="pet",
                inputs={"input": tensor},
                outputs=["output"],
            )
            logits = result["output"][0]
            probs = _softmax(logits)
            labels = ["cat", "dog"]
            pred_idx = int(np.argmax(probs))
            enrichments["pet"] = {
                "pet_type": labels[pred_idx] if pred_idx < len(labels) else "unknown",
                "confidence": round(float(probs[pred_idx]), 4),
                "is_household_pet": True,
            }

        inference_time_ms = (time.monotonic() - start) * 1000

        return EnrichmentResponse(
            detection_type=request.detection_type,
            enrichments=enrichments,
            inference_time_ms=round(inference_time_ms, 2),
        )

    except TritonClientError as e:
        raise HTTPException(status_code=503, detail=f"Enrichment failed: {e}") from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/health")
async def health() -> dict[str, Any]:
    """Health check for enrichment models."""
    triton = get_triton_client()

    models = ["vehicle", "fashion_clip", "demographics_age", "demographics_gender", "pet", "depth"]
    statuses: dict[str, bool] = {}
    for model in models:
        statuses[model] = await triton.is_model_ready(model)

    all_ready = all(statuses.values())

    return {
        "status": "healthy" if all_ready else "degraded",
        "models": statuses,
    }
