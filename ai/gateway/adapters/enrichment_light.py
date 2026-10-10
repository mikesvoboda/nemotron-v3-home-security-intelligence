"""Enrichment light adapter for the AI Gateway.

Serves the two resident specialists of the shipped Triton set (R8 S3, owner
rulings 3+4+5):

    /threat-detect   -> Triton ``threat`` model (TensorRT)
    /person-reid     -> Triton ``reid`` model (ONNX Runtime)

R8 S3 retired /pose-analyze, /pet-classify and /depth-estimate with their
models (pose/pet/depth are pruned from the Triton repository, and
GATEWAY_MODEL_SET hard-raises so no deployment can boot them). The backend's
EnrichmentClient sent JSON payloads with base64 images to the retired
enrichment-light service (port 8096) and expects JSON responses matching the
current format; the two routes here keep that wire shape byte-for-byte.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path
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


class BBoxRequest(BaseModel):
    """Request with a base64 image and optional bounding box.

    Accepts ``image`` or ``image_base64`` as the field name. The ``bbox``
    field accepts either a dict (``{x, y, width, height}``) or a list
    (``[x1, y1, x2, y2]``) for backward compatibility with the backend client.
    Extra fields (e.g. ``min_confidence``) are silently ignored.
    """

    model_config = {"extra": "ignore", "populate_by_name": True}

    image: str = Field(..., description="Base64 encoded image", alias="image_base64")
    bbox: dict[str, float] | list[float] | None = Field(default=None)


class ThreatResponse(BaseModel):
    threats_detected: list[dict[str, Any]] = Field(default_factory=list)
    is_threat: bool = Field(...)
    max_confidence: float = Field(default=0.0)
    inference_time_ms: float = Field(...)


class ReIDResponse(BaseModel):
    embedding: list[float] = Field(...)
    embedding_dimension: int = Field(...)
    inference_time_ms: float = Field(...)
    # B2.2: which weights computed the vector, from the export's provenance
    # record. None when the record is missing or unusable: the backend then
    # stamps its sentinel, which the matcher refuses, instead of guessing.
    model_id: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


@router.post("/threat-detect", response_model=ThreatResponse)
async def threat_detect(request: BBoxRequest) -> ThreatResponse:
    """Detect weapons or threats in an image.

    Uses the YOLO weapon detection TensorRT model via Triton.
    Returns fields matching the backend's EnrichmentClient expected format:
    threats_detected, is_threat, max_confidence.
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

        is_threat = len(detections) > 0
        max_confidence = max((d.get("confidence", 0.0) for d in detections), default=0.0)

        return ThreatResponse(
            threats_detected=detections,
            is_threat=is_threat,
            max_confidence=round(max_confidence, 4),
            inference_time_ms=round(inference_time_ms, 2),
        )
    except TritonClientError as e:
        raise HTTPException(status_code=503, detail=f"Threat detection failed: {e}") from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")


def reid_model_id() -> str | None:
    """The ``reid`` model's ID, read from the provenance record the export wrote.

    Same grammar as the backend's ``osnet_model_id()``
    (``<zoo name>@<weights file stem>@<sha256[:12]>``), so the same weights give
    the same ID on both paths. Read per call: the file is tiny, and a re-export
    behind a running gateway is then reported as what it is.
    """
    repo = Path(os.getenv("TRITON_MODEL_REPOSITORY", "/models/repository"))
    try:
        record = json.loads((repo / "reid" / "1" / "provenance.json").read_text())
        zoo = str(record["zoo_name"])
        stem = Path(str(record["source_file"])).stem
        sha = str(record["source_sha256"]).lower()
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if not zoo or not stem or not _SHA256_HEX.match(sha):
        return None
    return f"{zoo}@{stem}@{sha[:12]}"


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

        # OSNet expects 256x128 input. Bilinear, as torchvision's Resize uses on
        # PIL images in the backend path: PIL's default filter (bicubic) moves
        # pixels by up to 0.7 after normalisation and breaks B2.2's parity gate.
        pil_img = Image.fromarray(image_np).resize((128, 256), Image.Resampling.BILINEAR)
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
            model_id=reid_model_id(),
        )
    except TritonClientError as e:
        raise HTTPException(status_code=503, detail=f"Person ReID failed: {e}") from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/health")
async def health() -> dict[str, Any]:
    """Health check for enrichment-light models.

    R8 S3: this adapter's models are exactly the residency set's non-yolo26
    members. A pruned model (pose/pet/depth) listed here would make this
    payload report ``degraded`` on every healthy boot -- the health row probes
    the set, not a memory of it.
    """
    triton = get_triton_client()

    models = ["threat", "reid"]
    statuses: dict[str, bool] = {}
    for model in models:
        statuses[model] = await triton.is_model_ready(model)

    all_ready = all(statuses.values())

    return {
        "status": "healthy" if all_ready else "degraded",
        "models": statuses,
    }
