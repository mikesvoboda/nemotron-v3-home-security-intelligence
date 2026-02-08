"""Florence-2 adapter for the AI Gateway.

Translates the existing Florence-2 REST API (JSON with base64 images) into
Triton gRPC inference calls against the ``florence2`` Python backend model.

Florence-2 uses Triton's Python backend because it requires ``trust_remote_code``
and has an autoregressive decoder that cannot be exported to TensorRT/ONNX.
The Python backend handles model inference; the gateway formats request/response.

Endpoints:
    POST /extract                 - Generic extraction with prompt
    POST /batch-extract           - Batch extraction
    POST /ocr                     - Text extraction
    POST /ocr-with-regions        - Text extraction with bounding boxes
    POST /detect                  - Object detection
    POST /dense-caption           - Dense region captioning
    POST /describe-region         - Region description (NEM-3911)
    POST /phrase-grounding        - Phrase grounding (NEM-3911)
    POST /detect_security_objects - Security-focused object detection
    POST /analyze-scene           - Comprehensive scene analysis
    GET  /health                  - Model health check

The backend's FlorenceClient sends JSON payloads with base64 images and
expects JSON responses matching the current ai-florence service format.
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
from ai.gateway.utils import decode_base64_to_bytes

logger = logging.getLogger(__name__)

router = APIRouter()

MODEL_NAME = "florence2"


# ---------------------------------------------------------------------------
# Request / Response schemas (match existing ai-florence API exactly)
# ---------------------------------------------------------------------------


class ExtractRequest(BaseModel):
    image: str = Field(..., description="Base64 encoded image")
    prompt: str = Field(default="<CAPTION>", description="Florence-2 prompt")


class ExtractResponse(BaseModel):
    result: str = Field(...)
    prompt_used: str = Field(...)
    inference_time_ms: float = Field(...)


class ImageRequest(BaseModel):
    image: str = Field(..., description="Base64 encoded image")


class OCRResponse(BaseModel):
    text: str = Field(...)
    inference_time_ms: float = Field(...)


class OCRRegion(BaseModel):
    text: str = Field(...)
    bbox: list[float] = Field(...)


class OCRWithRegionsResponse(BaseModel):
    regions: list[OCRRegion] = Field(...)
    inference_time_ms: float = Field(...)


class Detection(BaseModel):
    label: str = Field(...)
    bbox: list[float] = Field(...)
    score: float = Field(default=1.0)


class DetectResponse(BaseModel):
    detections: list[Detection] = Field(...)
    inference_time_ms: float = Field(...)


class CaptionedRegion(BaseModel):
    caption: str = Field(...)
    bbox: list[float] = Field(...)


class DenseCaptionResponse(BaseModel):
    regions: list[CaptionedRegion] = Field(...)
    inference_time_ms: float = Field(...)


class BoundingBox(BaseModel):
    x1: float = Field(...)
    y1: float = Field(...)
    x2: float = Field(...)
    y2: float = Field(...)


class RegionDescriptionRequest(BaseModel):
    image: str = Field(...)
    regions: list[BoundingBox] = Field(...)


class RegionDescriptionResponse(BaseModel):
    descriptions: list[CaptionedRegion] = Field(...)
    inference_time_ms: float = Field(...)


class PhraseGroundingRequest(BaseModel):
    image: str = Field(...)
    phrases: list[str] = Field(...)


class GroundedPhrase(BaseModel):
    phrase: str = Field(...)
    bboxes: list[list[float]] = Field(default_factory=list)
    confidence_scores: list[float] = Field(default_factory=list)


class PhraseGroundingResponse(BaseModel):
    grounded_phrases: list[GroundedPhrase] = Field(...)
    inference_time_ms: float = Field(...)


class SecurityObjectDetection(BaseModel):
    label: str = Field(...)
    bbox: list[float] = Field(...)
    confidence: float = Field(default=1.0)


class SecurityObjectsResponse(BaseModel):
    detections: list[SecurityObjectDetection] = Field(...)
    objects_queried: list[str] = Field(...)
    inference_time_ms: float = Field(...)


class BatchExtractItem(BaseModel):
    image: str = Field(...)
    prompt: str = Field(...)


class BatchExtractRequest(BaseModel):
    items: list[BatchExtractItem] = Field(...)


class BatchExtractResultItem(BaseModel):
    result: str = Field(...)
    prompt_used: str = Field(...)
    inference_time_ms: float = Field(...)
    error: str | None = None


class BatchExtractResponse(BaseModel):
    results: list[BatchExtractResultItem] = Field(...)
    total_inference_time_ms: float = Field(...)
    batch_size: int = Field(...)


class SceneAnalysisRequest(BaseModel):
    image: str = Field(...)


class SceneAnalysisResponse(BaseModel):
    caption: str = Field(...)
    regions: list[CaptionedRegion] = Field(default_factory=list)
    text_regions: list[OCRRegion] = Field(default_factory=list)
    inference_time_ms: float = Field(...)
    task_times_ms: dict[str, float] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _florence_infer(image_b64: str, prompt: str) -> tuple[str, float]:
    """Send image + prompt to Florence-2 Triton Python backend.

    The Python backend model expects:
    - image: TYPE_STRING [1] - base64-encoded image bytes
    - prompt: TYPE_STRING [1] - Florence-2 task prompt string

    And returns:
    - result: TYPE_STRING [1] - JSON string with task-specific result

    Args:
        image_b64: Base64-encoded image.
        prompt: Florence-2 task prompt.

    Returns:
        Tuple of (result_text, inference_time_ms).
    """
    start = time.monotonic()
    triton = get_triton_client()

    try:
        image_bytes = decode_base64_to_bytes(image_b64)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image: {e}") from e

    # Package inputs for Triton Python backend (tensor names match config.pbtxt)
    image_input = np.array([image_bytes], dtype=object)
    prompt_input = np.array([prompt.encode("utf-8")], dtype=object)

    try:
        result = await triton.infer(
            model_name=MODEL_NAME,
            inputs={
                "image": image_input,
                "prompt": prompt_input,
            },
            outputs=["result"],
        )
    except TritonClientError as e:
        raise HTTPException(status_code=503, detail=f"Florence inference failed: {e}") from e

    # Decode output
    raw_output = result["result"]
    if raw_output.dtype == object:
        text_result = (
            raw_output[0].decode("utf-8")
            if isinstance(raw_output[0], bytes)
            else str(raw_output[0])
        )
    else:
        text_result = str(raw_output[0])

    inference_time_ms = (time.monotonic() - start) * 1000
    return text_result, inference_time_ms


def _parse_json_output(text: str) -> Any:
    """Attempt to parse Florence-2 structured output as JSON.

    Florence Python backend may return JSON-serialized structured results.
    """
    import json

    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return text


# Security objects vocabulary (matches ai-florence)
SECURITY_OBJECTS = [
    "person",
    "face",
    "mask",
    "hoodie",
    "backpack",
    "package",
    "weapon",
    "knife",
    "gun",
    "crowbar",
    "tool",
    "vehicle",
    "car",
    "truck",
    "van",
    "motorcycle",
    "bicycle",
    "dog",
    "cat",
    "uniform",
    "badge",
    "clipboard",
]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/extract", response_model=ExtractResponse)
async def extract(request: ExtractRequest) -> ExtractResponse:
    """Extract information from an image using Florence-2."""
    result_text, inference_time_ms = await _florence_infer(request.image, request.prompt)

    return ExtractResponse(
        result=result_text,
        prompt_used=request.prompt,
        inference_time_ms=round(inference_time_ms, 2),
    )


@router.post("/batch-extract", response_model=BatchExtractResponse)
async def batch_extract(request: BatchExtractRequest) -> BatchExtractResponse:
    """Process multiple image+prompt pairs."""
    batch_start = time.monotonic()
    results: list[BatchExtractResultItem] = []

    for item in request.items:
        try:
            text, time_ms = await _florence_infer(item.image, item.prompt)
            results.append(
                BatchExtractResultItem(
                    result=text,
                    prompt_used=item.prompt,
                    inference_time_ms=round(time_ms, 2),
                )
            )
        except HTTPException as e:
            results.append(
                BatchExtractResultItem(
                    result="",
                    prompt_used=item.prompt,
                    inference_time_ms=0.0,
                    error=str(e.detail),
                )
            )
        except Exception as e:
            results.append(
                BatchExtractResultItem(
                    result="",
                    prompt_used=item.prompt,
                    inference_time_ms=0.0,
                    error=str(e),
                )
            )

    total_time_ms = (time.monotonic() - batch_start) * 1000

    return BatchExtractResponse(
        results=results,
        total_inference_time_ms=round(total_time_ms, 2),
        batch_size=len(results),
    )


@router.post("/ocr", response_model=OCRResponse)
async def ocr(request: ImageRequest) -> OCRResponse:
    """Extract text from an image using OCR."""
    text, inference_time_ms = await _florence_infer(request.image, "<OCR>")

    return OCRResponse(
        text=text,
        inference_time_ms=round(inference_time_ms, 2),
    )


@router.post("/ocr-with-regions", response_model=OCRWithRegionsResponse)
async def ocr_with_regions(request: ImageRequest) -> OCRWithRegionsResponse:
    """Extract text with bounding box regions."""
    text, inference_time_ms = await _florence_infer(request.image, "<OCR_WITH_REGION>")

    parsed = _parse_json_output(text)
    regions: list[OCRRegion] = []

    if isinstance(parsed, dict):
        quad_boxes = parsed.get("quad_boxes", [])
        labels = parsed.get("labels", [])
        for i, label in enumerate(labels):
            bbox = quad_boxes[i] if i < len(quad_boxes) else []
            if bbox and isinstance(bbox[0], list):
                bbox = [coord for point in bbox for coord in point]
            regions.append(OCRRegion(text=label, bbox=bbox))

    return OCRWithRegionsResponse(
        regions=regions,
        inference_time_ms=round(inference_time_ms, 2),
    )


@router.post("/detect", response_model=DetectResponse)
async def detect(request: ImageRequest) -> DetectResponse:
    """Detect objects with bounding boxes."""
    text, inference_time_ms = await _florence_infer(request.image, "<OD>")

    parsed = _parse_json_output(text)
    detections: list[Detection] = []

    if isinstance(parsed, dict):
        bboxes = parsed.get("bboxes", [])
        labels = parsed.get("labels", [])
        for i, label in enumerate(labels):
            bbox = bboxes[i] if i < len(bboxes) else []
            detections.append(Detection(label=label, bbox=bbox, score=1.0))

    return DetectResponse(
        detections=detections,
        inference_time_ms=round(inference_time_ms, 2),
    )


@router.post("/dense-caption", response_model=DenseCaptionResponse)
async def dense_caption(request: ImageRequest) -> DenseCaptionResponse:
    """Generate captions for all regions."""
    text, inference_time_ms = await _florence_infer(request.image, "<DENSE_REGION_CAPTION>")

    parsed = _parse_json_output(text)
    regions: list[CaptionedRegion] = []

    if isinstance(parsed, dict):
        bboxes = parsed.get("bboxes", [])
        labels = parsed.get("labels", [])
        for i, label in enumerate(labels):
            bbox = bboxes[i] if i < len(bboxes) else []
            regions.append(CaptionedRegion(caption=label, bbox=bbox))

    return DenseCaptionResponse(
        regions=regions,
        inference_time_ms=round(inference_time_ms, 2),
    )


@router.post("/describe-region", response_model=RegionDescriptionResponse)
async def describe_region(request: RegionDescriptionRequest) -> RegionDescriptionResponse:
    """Describe what's in specific bounding box regions."""
    start = time.monotonic()
    descriptions: list[CaptionedRegion] = []

    for region in request.regions:
        bbox = [region.x1, region.y1, region.x2, region.y2]
        # Florence-2 expects <REGION_TO_DESCRIPTION><loc_x1><loc_y1><loc_x2><loc_y2>
        # The Python backend handles coordinate normalization internally
        prompt = f"<REGION_TO_DESCRIPTION>{region.x1},{region.y1},{region.x2},{region.y2}"  # nosemgrep: python.django.security.injection.raw-html-format.raw-html-format

        text, _ = await _florence_infer(request.image, prompt)
        descriptions.append(CaptionedRegion(caption=text, bbox=bbox))

    total_time_ms = (time.monotonic() - start) * 1000

    return RegionDescriptionResponse(
        descriptions=descriptions,
        inference_time_ms=round(total_time_ms, 2),
    )


@router.post("/phrase-grounding", response_model=PhraseGroundingResponse)
async def phrase_grounding(request: PhraseGroundingRequest) -> PhraseGroundingResponse:
    """Find objects matching text descriptions."""
    start = time.monotonic()
    grounded_phrases: list[GroundedPhrase] = []

    for phrase in request.phrases:
        prompt = f"<CAPTION_TO_PHRASE_GROUNDING>{phrase}"  # nosemgrep: python.django.security.injection.raw-html-format.raw-html-format
        text, _ = await _florence_infer(request.image, prompt)

        parsed = _parse_json_output(text)
        bboxes: list[list[float]] = []
        confidence_scores: list[float] = []

        if isinstance(parsed, dict):
            result_bboxes = parsed.get("bboxes", [])
            for bbox in result_bboxes:
                if isinstance(bbox, list):
                    bboxes.append(bbox)
                    confidence_scores.append(1.0)

        grounded_phrases.append(
            GroundedPhrase(
                phrase=phrase,
                bboxes=bboxes,
                confidence_scores=confidence_scores,
            )
        )

    total_time_ms = (time.monotonic() - start) * 1000

    return PhraseGroundingResponse(
        grounded_phrases=grounded_phrases,
        inference_time_ms=round(total_time_ms, 2),
    )


@router.post("/detect_security_objects", response_model=SecurityObjectsResponse)
async def detect_security_objects(request: ImageRequest) -> SecurityObjectsResponse:
    """Detect security-relevant objects using open vocabulary detection."""
    objects_prompt = "Detect: " + ", ".join(SECURITY_OBJECTS)
    prompt = f"<OPEN_VOCABULARY_DETECTION>{objects_prompt}"

    text, inference_time_ms = await _florence_infer(request.image, prompt)

    parsed = _parse_json_output(text)
    detections: list[SecurityObjectDetection] = []

    if isinstance(parsed, dict):
        bboxes = parsed.get("bboxes", parsed.get("boxes", []))
        labels = parsed.get("bboxes_labels", parsed.get("labels", []))
        for i, label in enumerate(labels):
            bbox = bboxes[i] if i < len(bboxes) else []
            detections.append(
                SecurityObjectDetection(
                    label=label,
                    bbox=bbox,
                    confidence=1.0,
                )
            )

    return SecurityObjectsResponse(
        detections=detections,
        objects_queried=SECURITY_OBJECTS.copy(),
        inference_time_ms=round(inference_time_ms, 2),
    )


@router.post("/analyze-scene", response_model=SceneAnalysisResponse)
async def analyze_scene(request: SceneAnalysisRequest) -> SceneAnalysisResponse:
    """Comprehensive scene analysis using cascaded Florence-2 prompts."""
    start = time.monotonic()
    task_times: dict[str, float] = {}

    # Step 1: Detailed caption
    caption, caption_time = await _florence_infer(request.image, "<MORE_DETAILED_CAPTION>")
    task_times["caption"] = round(caption_time, 2)

    # Step 2 & 3: Dense regions and OCR in parallel
    async def run_dense() -> tuple[list[CaptionedRegion], float]:
        text, t = await _florence_infer(request.image, "<DENSE_REGION_CAPTION>")
        parsed = _parse_json_output(text)
        regions: list[CaptionedRegion] = []
        if isinstance(parsed, dict):
            bboxes = parsed.get("bboxes", [])
            labels = parsed.get("labels", [])
            for i, label in enumerate(labels):
                bbox = bboxes[i] if i < len(bboxes) else []
                regions.append(CaptionedRegion(caption=label, bbox=bbox))
        return regions, t

    async def run_ocr() -> tuple[list[OCRRegion], float]:
        text, t = await _florence_infer(request.image, "<OCR_WITH_REGION>")
        parsed = _parse_json_output(text)
        text_regions: list[OCRRegion] = []
        if isinstance(parsed, dict):
            quad_boxes = parsed.get("quad_boxes", [])
            labels = parsed.get("labels", [])
            for i, label in enumerate(labels):
                bbox = quad_boxes[i] if i < len(quad_boxes) else []
                if bbox and isinstance(bbox[0], list):
                    bbox = [coord for point in bbox for coord in point]
                text_regions.append(OCRRegion(text=label, bbox=bbox))
        return text_regions, t

    (regions, regions_time), (text_regions, ocr_time) = await asyncio.gather(run_dense(), run_ocr())

    task_times["dense_regions"] = round(regions_time, 2)
    task_times["ocr_with_regions"] = round(ocr_time, 2)

    total_time_ms = (time.monotonic() - start) * 1000

    return SceneAnalysisResponse(
        caption=caption,
        regions=regions,
        text_regions=text_regions,
        inference_time_ms=round(total_time_ms, 2),
        task_times_ms=task_times,
    )


@router.get("/health")
async def health() -> dict[str, Any]:
    """Health check for the Florence-2 model."""
    triton = get_triton_client()
    model_ready = await triton.is_model_ready(MODEL_NAME)
    return {
        "status": "healthy" if model_ready else "degraded",
        "model": "florence-2-large",
        "model_loaded": model_ready,
    }
