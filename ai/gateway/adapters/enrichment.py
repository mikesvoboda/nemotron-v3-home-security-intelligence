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
import os
import threading
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
# Fashion CLIP text encoder for zero-shot clothing classification
# ---------------------------------------------------------------------------

FASHION_CLIP_EMBED_DIM = 768

FASHION_CLIP_HUB_PATH = os.environ.get("FASHION_CLIP_HUB_PATH", "hf-hub:Marqo/marqo-fashionSigLIP")

_CLOTHING_TYPE_PROMPTS = {
    "t-shirt": "a person wearing a t-shirt",
    "hoodie": "a person wearing a hoodie",
    "jacket": "a person wearing a jacket",
    "coat": "a person wearing a coat",
    "sweater": "a person wearing a sweater",
    "dress_shirt": "a person wearing a dress shirt",
    "polo": "a person wearing a polo shirt",
    "tank_top": "a person wearing a tank top",
    "dress": "a person wearing a dress",
    "suit": "a person wearing a suit",
    "vest": "a person wearing a vest",
    "overalls": "a person wearing overalls",
    "uniform": "a person wearing a uniform",
    "athletic_wear": "a person wearing athletic sportswear",
    "casual": "a person in casual everyday clothing",
}

_COLOR_PROMPTS = {
    "black": "person wearing black clothing",
    "white": "person wearing white clothing",
    "red": "person wearing red clothing",
    "blue": "person wearing blue clothing",
    "green": "person wearing green clothing",
    "yellow": "person wearing yellow clothing",
    "orange": "person wearing orange clothing",
    "brown": "person wearing brown clothing",
    "gray": "person wearing gray clothing",
    "navy": "person wearing navy blue clothing",
    "pink": "person wearing pink clothing",
    "purple": "person wearing purple clothing",
    "beige": "person wearing beige clothing",
    "camouflage": "person wearing camouflage pattern clothing",
}

_STYLE_PROMPTS = {
    "casual": "person in casual everyday outfit",
    "formal": "person in formal business attire",
    "athletic": "person in athletic sportswear outfit",
    "workwear": "person in work uniform or workwear",
    "streetwear": "person in streetwear urban fashion",
    "outdoor": "person in outdoor hiking gear",
    "sleepwear": "person in sleepwear or pajamas",
    "high_visibility": "person wearing high visibility safety vest",
}

_SUSPICIOUS_PROMPTS = {
    "ski_mask": "person wearing a ski mask balaclava covering face",
    "face_covered_hoodie": "person with face obscured by hoodie pulled up",
    "face_mask_bandana": "person with face covered by bandana or cloth mask",
    "all_black_outfit": "person dressed entirely in black dark clothing at night",
    "gloves_at_night": "person wearing gloves and dark clothing at night",
}

_SERVICE_UNIFORM_PROMPTS = {
    "delivery": "delivery driver in uniform with package",
    "postal": "postal worker mail carrier in uniform",
    "police": "police officer in uniform",
    "firefighter": "firefighter in uniform or gear",
    "medical": "medical worker in scrubs or uniform",
    "maintenance": "maintenance worker in work uniform",
    "security_guard": "security guard in uniform",
}

_clothing_text_lock = threading.Lock()
_clothing_text_cache: dict[str, tuple[list[str], np.ndarray]] | None = None
_clothing_text_failed = False

# In-process FashionSigLIP text encoder (lazy-loaded, CPU-only)
_fashion_text_model: Any = None
_fashion_text_tokenizer: Any = None


def _load_fashion_clip_text_encoder() -> bool:
    """Load the FashionSigLIP text encoder via open_clip (CPU-only).

    Follows the same pattern as the CLIP adapter (clip.py). Only the text
    encoding path is used; vision embeddings come from Triton.

    Returns True if the text encoder is available, False otherwise.
    """
    global _fashion_text_model, _fashion_text_tokenizer
    try:
        import open_clip
        import torch

        logger.info("Loading FashionSigLIP text encoder from %s (CPU)...", FASHION_CLIP_HUB_PATH)
        model, _ = open_clip.create_model_from_pretrained(FASHION_CLIP_HUB_PATH, device="cpu")
        model = model.eval()
        tokenizer = open_clip.get_tokenizer(FASHION_CLIP_HUB_PATH)

        # Verify embedding dimension matches Triton vision encoder
        test_tokens = tokenizer(["test"])
        with torch.no_grad():
            test_embed = model.encode_text(test_tokens)
        actual_dim = test_embed.shape[-1]
        if actual_dim != FASHION_CLIP_EMBED_DIM:
            logger.warning(
                "FashionSigLIP text encoder dim %d != expected %d; "
                "text-vision similarity will not work correctly",
                actual_dim,
                FASHION_CLIP_EMBED_DIM,
            )

        _fashion_text_model = model
        _fashion_text_tokenizer = tokenizer
        logger.info("FashionSigLIP text encoder loaded (dim=%d)", actual_dim)
        return True
    except Exception:
        logger.warning("Failed to load FashionSigLIP text encoder", exc_info=True)
        return False


def _encode_texts_fashion_clip(texts: list[str]) -> np.ndarray:
    """Encode text strings to L2-normalized embeddings using FashionSigLIP.

    Assumes _load_fashion_clip_text_encoder() has already returned True.

    Returns:
        Numpy array of shape (len(texts), FASHION_CLIP_EMBED_DIM) with
        L2-normalized embeddings.
    """
    import torch

    tokens = _fashion_text_tokenizer(texts)
    with torch.no_grad():
        text_features = _fashion_text_model.encode_text(tokens)
        text_features = text_features / (text_features.norm(dim=-1, keepdim=True) + 1e-8)
    return text_features.cpu().float().numpy()


def _ensure_clothing_text_embeddings() -> dict[str, tuple[list[str], np.ndarray]] | None:
    """Lazy-init and cache text embeddings for all clothing prompt categories.

    Returns a dict mapping category name to (labels_list, embeddings_array),
    or None if text encoding is unavailable.
    """
    global _clothing_text_cache, _clothing_text_failed

    if _clothing_text_cache is not None or _clothing_text_failed:
        return _clothing_text_cache

    with _clothing_text_lock:
        if _clothing_text_cache is not None or _clothing_text_failed:
            return _clothing_text_cache

        if not _load_fashion_clip_text_encoder():
            _clothing_text_failed = True
            logger.warning(
                "FashionSigLIP text encoder unavailable; "
                "clothing classification will return placeholder results"
            )
            return None

        try:
            cache: dict[str, tuple[list[str], np.ndarray]] = {}

            for category_name, prompts_dict in [
                ("clothing_type", _CLOTHING_TYPE_PROMPTS),
                ("color", _COLOR_PROMPTS),
                ("style", _STYLE_PROMPTS),
                ("suspicious", _SUSPICIOUS_PROMPTS),
                ("service_uniform", _SERVICE_UNIFORM_PROMPTS),
            ]:
                labels = list(prompts_dict.keys())
                texts = list(prompts_dict.values())
                embeddings = _encode_texts_fashion_clip(texts)
                cache[category_name] = (labels, embeddings)
                logger.info("Cached %d text embeddings for '%s'", len(labels), category_name)

            _clothing_text_cache = cache
            logger.info("FashionSigLIP text embeddings cached successfully")
            return _clothing_text_cache

        except Exception:
            _clothing_text_failed = True
            logger.warning("Failed to compute FashionSigLIP text embeddings", exc_info=True)
            return None


def _classify_with_text_embeddings(
    image_embedding: np.ndarray,
    text_cache: dict[str, tuple[list[str], np.ndarray]],
) -> dict[str, Any]:
    """Classify clothing attributes by comparing image embedding to text embeddings."""
    if image_embedding.ndim == 2:
        image_embedding = image_embedding[0]

    norm = np.linalg.norm(image_embedding)
    if norm > 1e-8:
        image_embedding = image_embedding / norm

    def _best_match(category: str) -> tuple[str, float]:
        labels, embeddings = text_cache[category]
        sims = embeddings @ image_embedding
        best_idx = int(np.argmax(sims))
        return labels[best_idx], float(sims[best_idx])

    clothing_type, clothing_conf = _best_match("clothing_type")
    color, _color_conf = _best_match("color")
    style, _style_conf = _best_match("style")

    suspicious_labels, suspicious_embeddings = text_cache["suspicious"]
    suspicious_sims = suspicious_embeddings @ image_embedding
    max_suspicious_idx = int(np.argmax(suspicious_sims))
    max_suspicious_sim = float(suspicious_sims[max_suspicious_idx])
    is_suspicious = max_suspicious_sim > 0.25

    uniform_labels, uniform_embeddings = text_cache["service_uniform"]
    uniform_sims = uniform_embeddings @ image_embedding
    max_uniform_idx = int(np.argmax(uniform_sims))
    max_uniform_sim = float(uniform_sims[max_uniform_idx])
    is_service_uniform = max_uniform_sim > 0.25

    confidence = clothing_conf

    description = f"Person wearing {color} {clothing_type.replace('_', ' ')}"
    if is_suspicious:
        description += f" (suspicious: {suspicious_labels[max_suspicious_idx].replace('_', ' ')})"
    if is_service_uniform:
        description += f" ({uniform_labels[max_uniform_idx].replace('_', ' ')} uniform)"

    return {
        "clothing_type": clothing_type,
        "color": color,
        "style": style,
        "confidence": round(confidence, 4),
        "top_category": clothing_type,
        "description": description,
        "is_suspicious": is_suspicious,
        "is_service_uniform": is_service_uniform,
    }


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
    """Run clothing classification via Triton fashion_clip model.

    Gets image embedding from Triton, then compares against pre-computed
    text embeddings for zero-shot classification of clothing type, color,
    style, suspicious attire, and service uniforms.
    """
    start = time.monotonic()
    triton = get_triton_client()

    image_np = decode_base64_image(image_b64)
    tensor = preprocess_clip(image_np)

    result = await triton.infer(
        model_name="fashion_clip",
        inputs={"pixel_values": tensor},
        outputs=["embedding"],
    )

    embedding = result["embedding"][0]
    inference_time_ms = (time.monotonic() - start) * 1000

    # Attempt zero-shot classification with cached text embeddings
    text_cache = _ensure_clothing_text_embeddings()
    if text_cache is not None:
        classification = _classify_with_text_embeddings(embedding, text_cache)
        classification["inference_time_ms"] = round(inference_time_ms, 2)
        return classification

    # Fallback: text encoder unavailable, return placeholder
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

    # Package frames as JSON array of base64 strings for Python backend
    import json as _json

    frames_json = _json.dumps(frames_b64)
    frames_input = np.array([frames_json.encode("utf-8")], dtype=object)

    result = await triton.infer(
        model_name="xclip_action",
        inputs={
            "frames": frames_input,
        },
        outputs=["action", "confidence", "all_scores"],
    )

    # Parse outputs from the Python backend
    all_scores_raw = result["all_scores"]
    if all_scores_raw.dtype == object:
        scores_str = (
            bytes(all_scores_raw.flat[0]).decode("utf-8")
            if isinstance(all_scores_raw.flat[0], bytes)
            else str(all_scores_raw.flat[0])
        )
        scores_data = _json.loads(scores_str)
    else:
        scores_data = {}

    inference_time_ms = (time.monotonic() - start) * 1000

    # Build actions list from all_scores for compatibility
    all_scores_dict = scores_data.get("all_scores", {})
    actions_list = [
        {"action": a, "confidence": round(s, 4)}
        for a, s in sorted(all_scores_dict.items(), key=lambda x: x[1], reverse=True)[:top_k]
    ]

    return {
        "actions": actions_list,
        "inference_time_ms": round(inference_time_ms, 2),
    }


def _softmax(x: np.ndarray) -> np.ndarray:
    """Compute softmax over a 1D array."""
    e = np.exp(x - np.max(x))
    return e / (e.sum() + 1e-8)


def _postprocess_pose(output: np.ndarray, conf_threshold: float = 0.25) -> list[dict[str, Any]]:
    """Post-process YOLOv8-pose output tensor to keypoint dicts.

    Args:
        output: Raw model output, shape (1, 56, 8400).
            56 = 4 box + 1 conf + 17*3 keypoints (x, y, visibility).
        conf_threshold: Minimum confidence to keep a detection.

    Returns:
        List of dicts, each with 'keypoints' (list of {x, y, confidence}).
    """
    preds = output[0]  # (56, 8400)
    if preds.shape[0] < preds.shape[1]:
        preds = preds.T  # (8400, 56)

    # Extract box confidence (index 4)
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
        kp_data = det[5:]  # 17*3 = 51 values
        keypoints = []
        for i in range(17):
            kx = float(kp_data[i * 3])
            ky = float(kp_data[i * 3 + 1])
            kc = float(kp_data[i * 3 + 2])
            keypoints.append(
                {
                    "name": COCO_KEYPOINT_NAMES[i],
                    "x": round(kx, 1),
                    "y": round(ky, 1),
                    "confidence": round(kc, 4),
                }
            )
        results.append({"keypoints": keypoints})

    return results


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
            outputs=["depth_map"],
        )

        depth_map = result["depth_map"][0]
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

        return PoseAnalyzeResponse(
            keypoints=keypoints,
            num_people=len(keypoints),
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
