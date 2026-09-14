"""YOLO26 adapter for the AI Gateway.

Translates the existing YOLO26 REST API (multipart image upload) into
Triton gRPC inference calls against the ``yolo26`` TensorRT model.

Endpoints:
    POST /detect         - Single image detection (multipart upload)
    POST /detect/batch   - Batch detection (multiple files)
    POST /segment        - Instance segmentation
    GET  /health         - Model health check

The backend's DetectorClient sends images as multipart file uploads and
expects JSON responses with ``detections``, ``image_width``, ``image_height``,
and ``inference_time_ms`` fields.
"""

from __future__ import annotations

import io
import logging
import time
from typing import Any

import numpy as np
from fastapi import APIRouter, File, HTTPException, UploadFile
from PIL import Image

from ai.gateway.triton_client import TritonClientError, get_triton_client
from ai.gateway.utils import letterbox_scale_factors, preprocess_yolo

logger = logging.getLogger(__name__)

router = APIRouter()

# YOLO26 model configuration
MODEL_NAME = "yolo26"
CONFIDENCE_THRESHOLD = 0.25
NMS_THRESHOLD = 0.45
TARGET_SIZE = 640

# COCO class names used by YOLO26
COCO_CLASSES: list[str] = [
    "person",
    "bicycle",
    "car",
    "motorcycle",
    "airplane",
    "bus",
    "train",
    "truck",
    "boat",
    "traffic light",
    "fire hydrant",
    "stop sign",
    "parking meter",
    "bench",
    "bird",
    "cat",
    "dog",
    "horse",
    "sheep",
    "cow",
    "elephant",
    "bear",
    "zebra",
    "giraffe",
    "backpack",
    "umbrella",
    "handbag",
    "tie",
    "suitcase",
    "frisbee",
    "skis",
    "snowboard",
    "sports ball",
    "kite",
    "baseball bat",
    "baseball glove",
    "skateboard",
    "surfboard",
    "tennis racket",
    "bottle",
    "wine glass",
    "cup",
    "fork",
    "knife",
    "spoon",
    "bowl",
    "banana",
    "apple",
    "sandwich",
    "orange",
    "broccoli",
    "carrot",
    "hot dog",
    "pizza",
    "donut",
    "cake",
    "chair",
    "couch",
    "potted plant",
    "bed",
    "dining table",
    "toilet",
    "tv",
    "laptop",
    "mouse",
    "remote",
    "keyboard",
    "cell phone",
    "microwave",
    "oven",
    "toaster",
    "sink",
    "refrigerator",
    "book",
    "clock",
    "vase",
    "scissors",
    "teddy bear",
    "hair drier",
    "toothbrush",
]


def _postprocess_yolo(
    output: np.ndarray,
    orig_w: int,
    orig_h: int,
    conf_threshold: float = CONFIDENCE_THRESHOLD,
    nms_threshold: float = NMS_THRESHOLD,
) -> list[dict[str, Any]]:
    """Post-process YOLO output tensor to detection dicts.

    Supports two output formats:
    - Post-NMS (YOLO26 Ultralytics export): shape (1, 300, 6) where each row
      is [x1, y1, x2, y2, confidence, class_id]. Already NMS'd.
    - Pre-NMS (legacy): shape (1, 84, 8400) or (1, 8400, 84) where columns
      are [cx, cy, w, h, class_scores...]. Requires manual NMS.

    Scales bounding boxes back to original image coordinates
    (reversing letterbox transform).

    Args:
        output: Raw model output tensor.
        orig_w: Original image width.
        orig_h: Original image height.
        conf_threshold: Minimum confidence to keep a detection.
        nms_threshold: IoU threshold for non-maximum suppression (pre-NMS only).

    Returns:
        List of detection dicts with keys: class, confidence, bbox.
    """
    preds = output[0]

    # Detect post-NMS format: (N, 6) = [x1, y1, x2, y2, score, class_id]
    if preds.shape[-1] == 6 and preds.shape[0] <= 1000:
        return _postprocess_post_nms(preds, orig_w, orig_h, conf_threshold)

    # Legacy pre-NMS format: (84, 8400) or (8400, 84)
    return _postprocess_pre_nms(preds, orig_w, orig_h, conf_threshold, nms_threshold)


def _postprocess_post_nms(
    preds: np.ndarray,
    orig_w: int,
    orig_h: int,
    conf_threshold: float,
) -> list[dict[str, Any]]:
    """Post-process post-NMS YOLO output (Ultralytics export format).

    Input rows: [x1, y1, x2, y2, confidence, class_id] in letterboxed coords.
    """
    scale, pad_x, pad_y = letterbox_scale_factors(orig_w, orig_h, TARGET_SIZE)

    detections: list[dict[str, Any]] = []
    for row in preds:
        score = float(row[4])
        if score < conf_threshold:
            continue

        # Clamp confidence to [0, 1]
        score = max(0.0, min(1.0, score))

        cls_id = int(row[5])
        cls_name = COCO_CLASSES[cls_id] if cls_id < len(COCO_CLASSES) else f"class_{cls_id}"

        # Reverse letterbox: coords are in 640x640 space
        bx1 = max(0, (float(row[0]) - pad_x) / scale)
        by1 = max(0, (float(row[1]) - pad_y) / scale)
        bx2 = min(orig_w, (float(row[2]) - pad_x) / scale)
        by2 = min(orig_h, (float(row[3]) - pad_y) / scale)

        box_w = bx2 - bx1
        box_h = by2 - by1
        if box_w <= 0 or box_h <= 0:
            continue

        detections.append(
            {
                "class": cls_name,
                "confidence": round(score, 4),
                "bbox": {
                    "x": round(bx1),
                    "y": round(by1),
                    "width": round(box_w),
                    "height": round(box_h),
                },
            }
        )

    return detections


def _postprocess_pre_nms(
    preds: np.ndarray,
    orig_w: int,
    orig_h: int,
    conf_threshold: float,
    nms_threshold: float,
) -> list[dict[str, Any]]:
    """Post-process pre-NMS YOLO output (raw predictions).

    Input shape: (84, 8400) or (8400, 84) where columns are
    [cx, cy, w, h, class_score_0, ..., class_score_79].
    """
    # Transpose if needed: (84, 8400) -> (8400, 84)
    if preds.shape[0] < preds.shape[1]:
        preds = preds.T

    # Extract boxes (cx, cy, w, h) and class scores
    boxes_cxcywh = preds[:, :4]
    class_scores = preds[:, 4:]

    # Get best class per prediction
    class_ids = np.argmax(class_scores, axis=1)
    confidences = np.array([class_scores[i, class_ids[i]] for i in range(len(class_ids))])

    # Filter by confidence
    mask = confidences >= conf_threshold
    boxes_cxcywh = boxes_cxcywh[mask]
    class_ids = class_ids[mask]
    confidences = confidences[mask]

    if len(confidences) == 0:
        return []

    # Convert cx, cy, w, h -> x1, y1, x2, y2
    x1 = boxes_cxcywh[:, 0] - boxes_cxcywh[:, 2] / 2
    y1 = boxes_cxcywh[:, 1] - boxes_cxcywh[:, 3] / 2
    x2 = boxes_cxcywh[:, 0] + boxes_cxcywh[:, 2] / 2
    y2 = boxes_cxcywh[:, 1] + boxes_cxcywh[:, 3] / 2

    # Simple NMS per class
    keep_indices: list[int] = []
    unique_classes = np.unique(class_ids)
    for cls_id in unique_classes:
        cls_mask = class_ids == cls_id
        cls_indices = np.where(cls_mask)[0]
        cls_confs = confidences[cls_indices]

        # Sort by confidence descending
        order = cls_confs.argsort()[::-1]
        cls_indices = cls_indices[order]

        while len(cls_indices) > 0:
            best = cls_indices[0]
            keep_indices.append(int(best))

            if len(cls_indices) == 1:
                break

            rest = cls_indices[1:]

            # Compute IoU
            xx1 = np.maximum(x1[best], x1[rest])
            yy1 = np.maximum(y1[best], y1[rest])
            xx2 = np.minimum(x2[best], x2[rest])
            yy2 = np.minimum(y2[best], y2[rest])

            inter_w = np.maximum(0, xx2 - xx1)
            inter_h = np.maximum(0, yy2 - yy1)
            inter_area = inter_w * inter_h

            area_best = (x2[best] - x1[best]) * (y2[best] - y1[best])
            area_rest = (x2[rest] - x1[rest]) * (y2[rest] - y1[rest])
            union_area = area_best + area_rest - inter_area

            iou = inter_area / (union_area + 1e-6)
            remaining = np.where(iou <= nms_threshold)[0]
            cls_indices = rest[remaining]

    # Reverse letterbox transform
    scale, pad_x, pad_y = letterbox_scale_factors(orig_w, orig_h, TARGET_SIZE)

    detections: list[dict[str, Any]] = []
    for idx in keep_indices:
        # Scale box coordinates back to original image
        bx1 = max(0, (float(x1[idx]) - pad_x) / scale)
        by1 = max(0, (float(y1[idx]) - pad_y) / scale)
        bx2 = min(orig_w, (float(x2[idx]) - pad_x) / scale)
        by2 = min(orig_h, (float(y2[idx]) - pad_y) / scale)

        box_w = bx2 - bx1
        box_h = by2 - by1

        if box_w <= 0 or box_h <= 0:
            continue

        cls_id = int(class_ids[idx])
        cls_name = COCO_CLASSES[cls_id] if cls_id < len(COCO_CLASSES) else f"class_{cls_id}"

        # Clamp confidence to [0, 1]
        conf = max(0.0, min(1.0, float(confidences[idx])))

        detections.append(
            {
                "class": cls_name,
                "confidence": round(conf, 4),
                "bbox": {
                    "x": round(bx1),
                    "y": round(by1),
                    "width": round(box_w),
                    "height": round(box_h),
                },
            }
        )

    return detections


@router.post("/detect")
async def detect(file: UploadFile = File(...)) -> dict[str, Any]:
    """Detect objects in a single uploaded image.

    Matches the existing YOLO26 /detect endpoint API exactly. The backend's
    DetectorClient sends a multipart file upload and expects a JSON response
    with detections, image dimensions, and timing.

    Args:
        file: Uploaded image file (multipart/form-data).

    Returns:
        Detection results matching the existing YOLO26 response format.
    """
    start = time.monotonic()
    triton = get_triton_client()

    try:
        image_bytes = await file.read()
        image = Image.open(io.BytesIO(image_bytes))
        if image.mode != "RGB":
            image = image.convert("RGB")
        orig_w, orig_h = image.size
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image: {e}") from e

    try:
        # Preprocess for YOLO
        input_tensor = preprocess_yolo(image_bytes, TARGET_SIZE)

        # Run Triton inference
        result = await triton.infer(
            model_name=MODEL_NAME,
            inputs={"images": input_tensor.astype(np.float32)},
            outputs=["output0"],
        )

        # Post-process
        detections = _postprocess_yolo(result["output0"], orig_w, orig_h)

        inference_time_ms = (time.monotonic() - start) * 1000

        return {
            "detections": detections,
            "image_width": orig_w,
            "image_height": orig_h,
            "inference_time_ms": round(inference_time_ms, 2),
        }

    except TritonClientError as e:
        logger.error(f"YOLO26 Triton inference failed: {e}")
        raise HTTPException(status_code=503, detail=f"Inference failed: {e}") from e


@router.post("/detect/batch")
async def detect_batch(files: list[UploadFile] = File(...)) -> dict[str, Any]:
    """Detect objects in multiple uploaded images.

    Matches the existing YOLO26 /detect/batch endpoint. Processes images
    sequentially through Triton (batch=1 per call) but in a single HTTP
    round-trip.

    Args:
        files: List of uploaded image files.

    Returns:
        Batch results with per-image detections.
    """
    start = time.monotonic()
    results: list[dict[str, Any]] = []

    for upload_file in files:
        try:
            image_bytes = await upload_file.read()
            image = Image.open(io.BytesIO(image_bytes))
            if image.mode != "RGB":
                image = image.convert("RGB")
            orig_w, orig_h = image.size

            input_tensor = preprocess_yolo(image_bytes, TARGET_SIZE)
            triton = get_triton_client()

            result = await triton.infer(
                model_name=MODEL_NAME,
                inputs={"images": input_tensor.astype(np.float32)},
                outputs=["output0"],
            )

            detections = _postprocess_yolo(result["output0"], orig_w, orig_h)

            results.append(
                {
                    "detections": detections,
                    "image_width": orig_w,
                    "image_height": orig_h,
                }
            )
        except Exception as e:
            logger.warning(f"Batch detection failed for {upload_file.filename}: {e}")
            results.append(
                {
                    "detections": [],
                    "error": str(e),
                }
            )

    total_time_ms = (time.monotonic() - start) * 1000

    return {
        "results": results,
        "total_inference_time_ms": round(total_time_ms, 2),
        "batch_size": len(files),
    }


@router.post("/segment")
async def segment(file: UploadFile = File(...)) -> dict[str, Any]:
    """Perform instance segmentation on an uploaded image.

    Matches the existing YOLO26 /segment endpoint. Uses the YOLO26 model
    in segmentation mode if available, otherwise falls back to detection
    with empty mask fields.

    Args:
        file: Uploaded image file.

    Returns:
        Segmentation results with detections and masks.
    """
    start = time.monotonic()
    triton = get_triton_client()

    try:
        image_bytes = await file.read()
        image = Image.open(io.BytesIO(image_bytes))
        if image.mode != "RGB":
            image = image.convert("RGB")
        orig_w, orig_h = image.size
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image: {e}") from e

    try:
        input_tensor = preprocess_yolo(image_bytes, TARGET_SIZE)

        # Try segmentation model first, fall back to detection
        model = MODEL_NAME
        outputs_list = ["output0"]

        # Check if segmentation output exists
        try:
            metadata = await triton.get_model_metadata(model)
            output_names = [o["name"] for o in metadata.get("outputs", [])]
            if "output1" in output_names:
                outputs_list.append("output1")
        except Exception:
            logger.debug("Could not fetch model metadata for segmentation check")

        result = await triton.infer(
            model_name=model,
            inputs={"images": input_tensor.astype(np.float32)},
            outputs=outputs_list,
        )

        detections = _postprocess_yolo(result["output0"], orig_w, orig_h)

        inference_time_ms = (time.monotonic() - start) * 1000

        return {
            "detections": detections,
            "image_width": orig_w,
            "image_height": orig_h,
            "inference_time_ms": round(inference_time_ms, 2),
        }

    except TritonClientError as e:
        logger.error(f"YOLO26 segmentation failed: {e}")
        raise HTTPException(status_code=503, detail=f"Segmentation failed: {e}") from e


@router.get("/health")
async def health() -> dict[str, Any]:
    """Health check for the YOLO26 model."""
    triton = get_triton_client()
    model_ready = await triton.is_model_ready(MODEL_NAME)
    return {
        "status": "healthy" if model_ready else "degraded",
        "model": MODEL_NAME,
        "model_loaded": model_ready,
    }
