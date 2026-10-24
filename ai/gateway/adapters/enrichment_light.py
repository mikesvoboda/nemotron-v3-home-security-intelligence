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

import functools
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


class FaceDetectRequest(BaseModel):
    """Request for SCRFD face detection + 5-point landmarks ([r307a])."""

    model_config = {"extra": "ignore", "populate_by_name": True}

    image: str = Field(..., description="Base64 encoded image", alias="image_base64")
    threshold: float = Field(default=0.6, ge=0.0, le=1.0)
    nms_iou: float = Field(default=0.4, ge=0.0, le=1.0)


class FaceDetectionItem(BaseModel):
    """One SCRFD face detection in original image coordinates."""

    bbox: list[float] = Field(..., min_length=4, max_length=4)
    confidence: float = Field(...)
    landmarks: list[list[float]] = Field(..., min_length=5, max_length=5)


class FaceDetectResponse(BaseModel):
    """Response from SCRFD face detection ([r307a])."""

    faces: list[FaceDetectionItem] = Field(default_factory=list)
    inference_time_ms: float = Field(...)
    model_id: str | None = None


class FaceRecognizeResponse(BaseModel):
    """Response from ArcFace w600k_r50 face recognition ([r307a])."""

    embedding: list[float] = Field(...)
    embedding_dimension: int = Field(...)
    inference_time_ms: float = Field(...)
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
_SCRFD_FMC = 3
_SCRFD_STRIDES = (8, 16, 32)
_SCRFD_ANCHORS_PER_CELL = 2
_SCRFD_OUTPUT_NAMES = [
    "448",
    "471",
    "494",
    "451",
    "474",
    "497",
    "454",
    "477",
    "500",
]


def _provenance_model_id(triton_name: str) -> str | None:
    """Read `<zoo_name>@<source_file stem>@<sha256[:12]>` from `<triton_name>/1/provenance.json`."""
    repo = Path(os.getenv("TRITON_MODEL_REPOSITORY", "/models/repository"))
    try:
        record = json.loads((repo / triton_name / "1" / "provenance.json").read_text())
        zoo = str(record["zoo_name"])
        stem = Path(str(record["source_file"])).stem
        sha = str(record["source_sha256"]).lower()
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if not zoo or not stem or not _SHA256_HEX.match(sha):
        return None
    return f"{zoo}@{stem}@{sha[:12]}"


@functools.cache
def reid_model_id() -> str | None:
    """The ``reid`` model's ID, read from the provenance record the export wrote.

    Same grammar as the backend's ``osnet_model_id()``
    (``<zoo name>@<weights file stem>@<sha256[:12]>``), so the same weights give
    the same ID on both paths. Read once (``main``'s lifespan reads it at start)
    and kept: Triton runs ``--model-control-mode=none`` and serves the graph it
    loaded at start, so a record rewritten later by a re-export would describe
    weights this process is not serving.
    """
    return _provenance_model_id("reid")


@functools.cache
def scrfd_model_id() -> str | None:
    """The ``scrfd`` model's ID (`face-detector-scrfd@scrfd_10g_bnkps@<sha256[:12]>`)."""
    return _provenance_model_id("scrfd")


@functools.cache
def arcface_model_id() -> str | None:
    """The ``arcface`` model's ID (`face-recognizer@w600k_r50@<sha256[:12]>`)."""
    return _provenance_model_id("arcface")


def _scrfd_blob(
    image_np: np.ndarray, input_size: tuple[int, int] = (640, 640)
) -> tuple[np.ndarray, float]:
    """Letterbox + normalize `(canvas - 127.5) / 128.0` matching `face_recognizer_loader._scrfd_blob`."""
    from PIL import Image

    ih, iw = image_np.shape[0], image_np.shape[1]
    tw, th = input_size
    ratio = min(tw / iw, th / ih)
    nw, nh = max(1, int(iw * ratio)), max(1, int(ih * ratio))
    resized = np.asarray(
        Image.fromarray(image_np).resize((nw, nh), Image.Resampling.BILINEAR),
        dtype=np.float32,
    )
    canvas = np.zeros((th, tw, 3), dtype=np.float32)
    canvas[:nh, :nw, :] = resized
    blob = (canvas - 127.5) / 128.0
    blob = np.ascontiguousarray(blob.transpose(2, 0, 1)[None], dtype=np.float32)
    return blob, ratio


def _scrfd_nms(boxes: np.ndarray, scores: np.ndarray, iou_threshold: float = 0.4) -> list[int]:
    """Greedy score-ordered NMS matching `face_recognizer_loader._nms`."""
    order = np.argsort(-scores, kind="stable")
    keep: list[int] = []
    for idx in order:
        x1, y1, x2, y2 = boxes[idx]
        ok = True
        for k in keep:
            kx1, ky1, kx2, ky2 = boxes[k]
            ix1, iy1 = max(x1, kx1), max(y1, ky1)
            ix2, iy2 = min(x2, kx2), min(y2, ky2)
            iw_ih = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
            union = (x2 - x1) * (y2 - y1) + (kx2 - kx1) * (ky2 - ky1) - iw_ih
            if union > 0 and iw_ih / union > iou_threshold:
                ok = False
                break
        if ok:
            keep.append(int(idx))
    return keep


def _decode_scrfd_outputs(
    result: dict[str, np.ndarray],
    *,
    scale: float,
    input_size: tuple[int, int] = (640, 640),
    threshold: float = 0.6,
    nms_iou: float = 0.4,
) -> list[FaceDetectionItem]:
    """Decode SCRFD 9-output dict into boxes + 5 landmarks in original image coordinates."""
    w_in, h_in = input_size
    net_outs = [result[name] for name in _SCRFD_OUTPUT_NAMES]
    all_scores: list[np.ndarray] = []
    all_boxes: list[np.ndarray] = []
    all_kps: list[np.ndarray] = []
    for idx, stride in enumerate(_SCRFD_STRIDES):
        scores = np.asarray(net_outs[idx], dtype=np.float32).reshape(-1)
        dbox = np.asarray(net_outs[idx + _SCRFD_FMC], dtype=np.float32).reshape(-1, 4) * stride
        dkps = np.asarray(net_outs[idx + 2 * _SCRFD_FMC], dtype=np.float32).reshape(-1, 10) * stride
        h, w = h_in // stride, w_in // stride
        centers = (
            np.stack(list(np.mgrid[:h, :w][::-1]), axis=-1).astype(np.float32) * stride
        ).reshape(-1, 2)
        if _SCRFD_ANCHORS_PER_CELL > 1:
            centers = np.stack([centers] * _SCRFD_ANCHORS_PER_CELL, axis=1).reshape(-1, 2)
        centers = centers[: scores.shape[0]]
        pos = np.where(scores >= threshold)[0]
        if pos.size == 0:
            continue
        c = centers[pos]
        boxes = np.stack(
            [
                c[:, 0] - dbox[pos, 0],
                c[:, 1] - dbox[pos, 1],
                c[:, 0] + dbox[pos, 2],
                c[:, 1] + dbox[pos, 3],
            ],
            axis=1,
        )
        kps = (c[:, None, :] + dkps[pos].reshape(-1, 5, 2)).reshape(-1, 10)
        all_scores.append(scores[pos])
        all_boxes.append(boxes)
        all_kps.append(kps)

    if not all_scores:
        return []

    scores_cat = np.concatenate(all_scores)
    boxes_cat = np.concatenate(all_boxes) / scale
    kps_cat = np.concatenate(all_kps) / scale

    items: list[FaceDetectionItem] = []
    for i in _scrfd_nms(boxes_cat, scores_cat, nms_iou):
        x1, y1, x2, y2 = boxes_cat[i]
        landmarks = kps_cat[i].reshape(5, 2).tolist()
        items.append(
            FaceDetectionItem(
                bbox=[float(x1), float(y1), float(x2), float(y2)],
                confidence=float(scores_cat[i]),
                landmarks=[[float(pt[0]), float(pt[1])] for pt in landmarks],
            )
        )
    return items


@router.post("/face-detect", response_model=FaceDetectResponse)
async def face_detect(request: FaceDetectRequest) -> FaceDetectResponse:
    """Detect faces and 5-point landmarks via Triton `scrfd` TensorRT plan ([r307a])."""
    start = time.monotonic()
    triton = get_triton_client()

    try:
        image_np = decode_base64_image(request.image)
        blob, scale = _scrfd_blob(image_np, (640, 640))
        result = await triton.infer(
            model_name="scrfd",
            inputs={"input.1": blob},
            outputs=_SCRFD_OUTPUT_NAMES,
        )
        faces = _decode_scrfd_outputs(
            result,
            scale=scale,
            input_size=(640, 640),
            threshold=request.threshold,
            nms_iou=request.nms_iou,
        )
        inference_time_ms = (time.monotonic() - start) * 1000
        return FaceDetectResponse(
            faces=faces,
            inference_time_ms=round(inference_time_ms, 2),
            model_id=scrfd_model_id(),
        )
    except TritonClientError as e:
        raise HTTPException(status_code=503, detail=f"Face detection failed: {e}") from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/face-recognize", response_model=FaceRecognizeResponse)
async def face_recognize(request: BBoxRequest) -> FaceRecognizeResponse:
    """Embed an aligned 112x112 face crop via Triton `arcface` TensorRT plan ([r307a])."""
    start = time.monotonic()
    triton = get_triton_client()

    try:
        image_np = decode_base64_image(request.image)
        from PIL import Image

        pil_img = (
            Image.fromarray(image_np).convert("RGB").resize((112, 112), Image.Resampling.BILINEAR)
        )
        arr = np.asarray(pil_img, dtype=np.float32) / 127.5 - 1.0
        tensor = np.ascontiguousarray(arr.transpose(2, 0, 1)[np.newaxis, ...], dtype=np.float32)

        result = await triton.infer(
            model_name="arcface",
            inputs={"input.1": tensor},
            outputs=["683"],
        )

        vector = np.asarray(result["683"][0], dtype=np.float32).reshape(-1)
        if vector.shape[0] != 512:
            raise HTTPException(
                status_code=503,
                detail=f"Face recognition emitted {vector.shape[0]}-d, expected 512-d",
            )
        norm = float(np.linalg.norm(vector))
        if norm <= 0.0:
            raise HTTPException(status_code=503, detail="Face recognition emitted zero vector")
        embedding = [float(v) for v in (vector / norm)]

        inference_time_ms = (time.monotonic() - start) * 1000
        return FaceRecognizeResponse(
            embedding=embedding,
            embedding_dimension=len(embedding),
            inference_time_ms=round(inference_time_ms, 2),
            model_id=arcface_model_id(),
        )
    except TritonClientError as e:
        raise HTTPException(status_code=503, detail=f"Face recognition failed: {e}") from e
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
    from ai.gateway.residency import FULL_MODEL_SET

    triton = get_triton_client()

    models = [m for m in FULL_MODEL_SET if m != "yolo26"]
    statuses: dict[str, bool] = {}
    for model in models:
        statuses[model] = await triton.is_model_ready(model)

    all_ready = all(statuses.values())

    return {
        "status": "healthy" if all_ready else "degraded",
        "models": statuses,
    }
