"""Scene OCR Service for comprehensive text extraction from security frames.

This module provides SceneOCRService that orchestrates PaddleOCR text extraction
from both full frames and detection crops, enabling identification of:
- Service workers (uniform text: "FedEx", "Amazon", "Joe's Plumbing")
- Delivery vehicles (company names, fleet IDs)
- Package labels (shipping labels)
- Scene context (street signs, house numbers, business names)

The service runs OCR on:
1. Full frame (Phase 1, parallel with other enrichment models)
2. Detection crops (Phase 2, after YOLO26 detections are available)

Results are deduplicated and associated with detections for Nemotron context.

Architecture:
- Full frame OCR captures distant text (signs, house numbers)
- Crop OCR captures object-specific text at higher resolution
- ServiceProviderMatcher identifies known service providers
- Deduplication removes duplicate detections from overlapping regions

Reference: docs/plans/2026-02-04-scene-ocr-design.md
"""

from __future__ import annotations

import asyncio
import base64
import io
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import httpx
from PIL import Image

from backend.core.config import get_settings
from backend.core.logging import get_logger
from backend.core.metrics import (
    observe_scene_ocr_confidence,
    observe_scene_ocr_processing,
    record_scene_ocr_provider_match,
    record_scene_ocr_request,
    record_scene_ocr_texts_detected,
)
from backend.services.service_provider_matcher import (
    ServiceMatch,
    get_service_provider_matcher,
)

if TYPE_CHECKING:
    from backend.services.enrichment_pipeline import DetectionInput

logger = get_logger(__name__)

# Confidence thresholds for OCR results
CONFIDENCE_HIGH = 0.80  # Include in context, high weight
CONFIDENCE_LOW = 0.50  # Include with "uncertain" flag
CONFIDENCE_EXCLUDE = 0.50  # Below this, exclude (likely noise)

# IoU threshold for deduplication (same text detected in overlapping regions)
IOU_DEDUP_THRESHOLD = 0.70

# Bbox overlap threshold for associating frame OCR with detections
DETECTION_OVERLAP_THRESHOLD = 0.50

# HTTP client timeout for ai-enrichment service
OCR_TIMEOUT_SECONDS = 30.0

# Default ai-enrichment service URL
DEFAULT_ENRICHMENT_URL = "http://ai-enrichment:8094"


@dataclass(slots=True)
class RawOCRResult:
    """Raw OCR result from PaddleOCR.

    Attributes:
        text: Extracted text value
        confidence: OCR confidence score (0-1)
        bbox: Bounding box as (x1, y1, x2, y2) in frame coordinates
        source: Source of OCR result ("frame" or "crop")
        detection_id: Associated detection ID (for crop OCR)
    """

    text: str
    confidence: float
    bbox: tuple[int, int, int, int]
    source: str = "frame"
    detection_id: str | None = None


@dataclass(slots=True)
class SceneTextResult:
    """Text detected in scene (not associated with a specific detection).

    Attributes:
        value: The extracted text
        confidence: OCR confidence score (0-1)
        bbox: Bounding box as (x1, y1, x2, y2)
        text_type: Classification of text type (e.g., "house_number", "sign", "street_sign")
        is_uncertain: Whether confidence is in the uncertain range (0.50-0.79)
    """

    value: str
    confidence: float
    bbox: tuple[int, int, int, int]
    text_type: str | None = None
    is_uncertain: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result: dict[str, Any] = {
            "value": self.value,
            "confidence": self.confidence,
            "bbox": list(self.bbox),
        }
        if self.text_type:
            result["type"] = self.text_type
        if self.is_uncertain:
            result["uncertain"] = True
        return result


@dataclass(slots=True)
class DetectionOCRResult:
    """OCR results associated with a specific detection.

    Attributes:
        detection_id: ID of the associated detection
        texts: List of text results with value, confidence, and region
        service_match: Service provider match result (if any)
    """

    detection_id: str
    texts: list[dict[str, Any]] = field(default_factory=list)
    service_match: ServiceMatch | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result: dict[str, Any] = {
            "detection_id": self.detection_id,
            "texts": self.texts,
        }
        if self.service_match:
            result["service_match"] = self.service_match.to_dict()
        return result


@dataclass(slots=True)
class SceneOCRResult:
    """Complete OCR results for a frame.

    Attributes:
        scene_texts: Text detected in the scene (not associated with detections)
        detection_ocr: OCR results mapped to detection IDs
        processing_time_ms: Total processing time in milliseconds
    """

    scene_texts: list[SceneTextResult] = field(default_factory=list)
    detection_ocr: dict[str, DetectionOCRResult] = field(default_factory=dict)
    processing_time_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "scene_texts": [t.to_dict() for t in self.scene_texts],
            "detection_ocr": {k: v.to_dict() for k, v in self.detection_ocr.items()},
            "processing_time_ms": self.processing_time_ms,
        }

    @property
    def has_scene_texts(self) -> bool:
        """Check if any scene text was detected."""
        return len(self.scene_texts) > 0

    @property
    def has_detection_ocr(self) -> bool:
        """Check if any detection-associated OCR results exist."""
        return len(self.detection_ocr) > 0

    @property
    def has_service_matches(self) -> bool:
        """Check if any service provider matches were found."""
        return any(d.service_match is not None for d in self.detection_ocr.values())


def _calculate_iou(bbox1: tuple[int, int, int, int], bbox2: tuple[int, int, int, int]) -> float:
    """Calculate Intersection over Union (IoU) for two bounding boxes.

    Args:
        bbox1: First bounding box as (x1, y1, x2, y2)
        bbox2: Second bounding box as (x1, y1, x2, y2)

    Returns:
        IoU value between 0.0 and 1.0
    """
    x1_1, y1_1, x2_1, y2_1 = bbox1
    x1_2, y1_2, x2_2, y2_2 = bbox2

    # Calculate intersection
    x1_i = max(x1_1, x1_2)
    y1_i = max(y1_1, y1_2)
    x2_i = min(x2_1, x2_2)
    y2_i = min(y2_1, y2_2)

    if x2_i <= x1_i or y2_i <= y1_i:
        return 0.0

    intersection = (x2_i - x1_i) * (y2_i - y1_i)

    # Calculate union
    area1 = (x2_1 - x1_1) * (y2_1 - y1_1)
    area2 = (x2_2 - x1_2) * (y2_2 - y1_2)
    union = area1 + area2 - intersection

    if union <= 0:
        return 0.0

    return intersection / union


def _calculate_overlap_ratio(
    ocr_bbox: tuple[int, int, int, int], det_bbox: tuple[int, int, int, int]
) -> float:
    """Calculate overlap ratio of OCR bbox with detection bbox.

    The overlap ratio is the intersection area divided by the OCR bbox area.
    This measures how much of the OCR text is inside the detection.

    Args:
        ocr_bbox: OCR text bounding box as (x1, y1, x2, y2)
        det_bbox: Detection bounding box as (x1, y1, x2, y2)

    Returns:
        Overlap ratio between 0.0 and 1.0
    """
    x1_o, y1_o, x2_o, y2_o = ocr_bbox
    x1_d, y1_d, x2_d, y2_d = det_bbox

    # Calculate intersection
    x1_i = max(x1_o, x1_d)
    y1_i = max(y1_o, y1_d)
    x2_i = min(x2_o, x2_d)
    y2_i = min(y2_o, y2_d)

    if x2_i <= x1_i or y2_i <= y1_i:
        return 0.0

    intersection = (x2_i - x1_i) * (y2_i - y1_i)

    # OCR bbox area
    ocr_area = (x2_o - x1_o) * (y2_o - y1_o)
    if ocr_area <= 0:
        return 0.0

    return intersection / ocr_area


def _classify_text_type(text: str) -> str | None:
    """Classify the type of scene text based on content.

    Args:
        text: The text to classify

    Returns:
        Text type classification or None if unknown
    """
    text_upper = text.upper().strip()

    # House numbers (1-5 digits, possibly with letters)
    if text_upper.isdigit() and len(text_upper) <= 5:
        return "house_number"

    # Common street suffixes
    street_suffixes = {
        "ST",
        "STREET",
        "AVE",
        "AVENUE",
        "RD",
        "ROAD",
        "DR",
        "DRIVE",
        "LN",
        "LANE",
        "CT",
        "COURT",
        "PL",
        "PLACE",
        "BLVD",
        "BOULEVARD",
        "WAY",
        "CIR",
        "CIRCLE",
    }
    words = text_upper.split()
    if any(word in street_suffixes for word in words):
        return "street_sign"

    # Common sign text
    common_signs = {
        "STOP",
        "YIELD",
        "NO PARKING",
        "ONE WAY",
        "DO NOT ENTER",
        "EXIT",
        "ENTRANCE",
        "PRIVATE",
        "NO TRESPASSING",
        "CAUTION",
        "WARNING",
        "SLOW",
        "SPEED LIMIT",
        "LOADING",
        "RESERVED",
    }
    if text_upper in common_signs or any(sign in text_upper for sign in common_signs):
        return "sign"

    return None


def _image_to_base64(image: Image.Image) -> str:
    """Convert PIL Image to base64-encoded PNG string.

    Args:
        image: PIL Image to convert

    Returns:
        Base64-encoded PNG string
    """
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return base64.b64encode(buffer.read()).decode("utf-8")


class SceneOCRService:
    """Comprehensive scene OCR service for security frame analysis.

    This service orchestrates PaddleOCR text extraction from security camera frames,
    running OCR on both full frames and detection crops for comprehensive text
    detection.

    Features:
    - Full-frame OCR for scene context (signs, house numbers)
    - Crop OCR for detection-specific text (uniforms, vehicle markings)
    - Deduplication of overlapping OCR results
    - Association of text with YOLO26 detections
    - Service provider matching for known companies

    Attributes:
        enrichment_url: URL of the ai-enrichment service
        timeout: HTTP request timeout in seconds
        enabled: Whether scene OCR is enabled
        service_matcher: Service provider matcher instance

    Example:
        >>> service = SceneOCRService()
        >>> result = await service.process_frame(image, detections)
        >>> for text in result.scene_texts:
        ...     print(f"{text.value}: {text.confidence:.2f}")
    """

    def __init__(
        self,
        enrichment_url: str | None = None,
        timeout: float = OCR_TIMEOUT_SECONDS,
        enabled: bool = True,
    ) -> None:
        """Initialize the SceneOCRService.

        Args:
            enrichment_url: URL of the ai-enrichment service (default from settings)
            timeout: HTTP request timeout in seconds
            enabled: Whether scene OCR is enabled (for feature flags)
        """
        settings = get_settings()
        self.enrichment_url = enrichment_url or getattr(
            settings, "enrichment_url", DEFAULT_ENRICHMENT_URL
        )
        self.timeout = timeout
        self.enabled = enabled
        self.service_matcher = get_service_provider_matcher()

        # HTTP client is created lazily for async context
        self._client: httpx.AsyncClient | None = None

        logger.info(f"SceneOCRService initialized (url={self.enrichment_url}, enabled={enabled})")

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client.

        Returns:
            Async HTTP client instance
        """
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def process_frame(
        self,
        image: Image.Image,
        detections: list[DetectionInput],
    ) -> SceneOCRResult:
        """Run full-frame and crop OCR, deduplicate, and match providers.

        This is the main entry point for scene OCR processing. It:
        1. Runs full-frame OCR in parallel
        2. Runs crop OCR on person, vehicle, and package detections
        3. Deduplicates overlapping results
        4. Associates text with detections
        5. Matches service providers

        Args:
            image: PIL Image of the frame
            detections: List of YOLO26 detections with bounding boxes

        Returns:
            SceneOCRResult with scene texts and detection-associated OCR
        """
        if not self.enabled:
            return SceneOCRResult()

        start_time = time.perf_counter()

        try:
            # Run full-frame and crop OCR in parallel
            frame_task = self._run_full_frame_ocr(image)
            crop_task = self._run_crop_ocr(image, detections)

            frame_results, crop_results = await asyncio.gather(
                frame_task,
                crop_task,
                return_exceptions=True,
            )

            # Handle exceptions from gather
            if isinstance(frame_results, BaseException):
                logger.warning(f"Full-frame OCR failed: {frame_results}")
                frame_results_clean: list[RawOCRResult] = []
            else:
                frame_results_clean = frame_results
            if isinstance(crop_results, BaseException):
                logger.warning(f"Crop OCR failed: {crop_results}")
                crop_results_clean: dict[str, list[RawOCRResult]] = {}
            else:
                crop_results_clean = crop_results

            # Deduplicate and associate
            result = self._deduplicate(frame_results_clean, crop_results_clean, detections)

            # Match service providers for detection OCR
            for _det_id, det_ocr in result.detection_ocr.items():
                all_texts = [t["value"] for t in det_ocr.texts if t.get("value")]
                matches = self.service_matcher.match_all(all_texts)
                if matches:
                    # Use the highest confidence match
                    det_ocr.service_match = max(matches, key=lambda m: m.confidence)
                    # Record provider match metric
                    record_scene_ocr_provider_match(det_ocr.service_match.category)

            # Also check scene texts for service providers
            for scene_text in result.scene_texts:
                match = self.service_matcher.match(scene_text.value)
                if match:
                    # If scene text matches a service provider, it might belong to
                    # a detection we missed - log for debugging
                    logger.debug(
                        f"Service provider '{match.provider}' detected in scene text "
                        f"(not associated with detection)"
                    )
                    # Record provider match metric for scene text
                    record_scene_ocr_provider_match(match.category)

            result.processing_time_ms = (time.perf_counter() - start_time) * 1000

            # Record total processing time metric (combined full_frame + crop)
            observe_scene_ocr_processing("total", result.processing_time_ms / 1000.0)

            # Record detected text counts
            total_texts = len(result.scene_texts)
            for det_ocr in result.detection_ocr.values():
                total_texts += len(det_ocr.texts)
            if total_texts > 0:
                record_scene_ocr_texts_detected(total_texts)
            logger.debug(
                f"Scene OCR completed in {result.processing_time_ms:.1f}ms: "
                f"{len(result.scene_texts)} scene texts, "
                f"{len(result.detection_ocr)} detection OCRs"
            )

            return result

        except Exception as e:
            logger.exception(f"Scene OCR processing failed: {e}")
            return SceneOCRResult(processing_time_ms=(time.perf_counter() - start_time) * 1000)

    async def _run_full_frame_ocr(self, image: Image.Image) -> list[RawOCRResult]:
        """Run PaddleOCR on the full frame.

        Args:
            image: PIL Image of the frame

        Returns:
            List of RawOCRResult from full-frame OCR
        """
        # Record request metric
        record_scene_ocr_request("full_frame")
        start_time = time.perf_counter()

        try:
            client = await self._get_client()
            image_base64 = _image_to_base64(image)

            response = await client.post(
                f"{self.enrichment_url}/scene-ocr",
                json={
                    "image": image_base64,
                    "mode": "full_frame",
                },
            )

            if response.status_code != 200:
                logger.warning(f"Full-frame OCR request failed: HTTP {response.status_code}")
                return []

            data = response.json()
            results: list[RawOCRResult] = []

            for item in data.get("texts", []):
                confidence = item.get("confidence", 0)
                if confidence < CONFIDENCE_EXCLUDE:
                    continue

                # Record confidence metric for each detected text
                observe_scene_ocr_confidence(confidence)

                bbox = item.get("bbox", [0, 0, 0, 0])
                results.append(
                    RawOCRResult(
                        text=item.get("text", ""),
                        confidence=confidence,
                        bbox=(int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])),
                        source="frame",
                    )
                )

            # Record processing time for full frame OCR
            duration = time.perf_counter() - start_time
            observe_scene_ocr_processing("full_frame", duration)

            return results

        except httpx.TimeoutException:
            logger.warning("Full-frame OCR request timed out")
            return []
        except httpx.ConnectError:
            logger.warning("Failed to connect to ai-enrichment service for OCR")
            return []
        except Exception as e:
            logger.exception(f"Full-frame OCR failed: {e}")
            return []

    async def _run_crop_ocr(
        self,
        image: Image.Image,
        detections: list[DetectionInput],
    ) -> dict[str, list[RawOCRResult]]:
        """Run PaddleOCR on detection crops.

        Only processes person, vehicle, and package detections as these
        are likely to have readable text (uniforms, vehicle markings, labels).

        Args:
            image: PIL Image of the frame
            detections: List of YOLO26 detections

        Returns:
            Dictionary mapping detection IDs to OCR results
        """
        # Filter to relevant detection classes
        ocr_classes = {"person", "car", "truck", "bus", "motorcycle", "bicycle", "package"}
        relevant_detections = [d for d in detections if d.class_name.lower() in ocr_classes]

        if not relevant_detections:
            return {}

        results: dict[str, list[RawOCRResult]] = {}

        # Process crops in parallel with semaphore to limit concurrency
        semaphore = asyncio.Semaphore(4)  # Max 4 concurrent OCR requests

        async def process_crop(detection: DetectionInput) -> tuple[str, list[RawOCRResult]]:
            async with semaphore:
                det_id = str(detection.id) if detection.id else f"det_{id(detection)}"
                # Record request metric for each crop
                record_scene_ocr_request("crop")
                crop_start_time = time.perf_counter()

                try:
                    # Extract crop from image
                    bbox = detection.bbox.to_int_tuple()
                    # Ensure bbox is within image bounds
                    x1 = max(0, bbox[0])
                    y1 = max(0, bbox[1])
                    x2 = min(image.width, bbox[2])
                    y2 = min(image.height, bbox[3])

                    if x2 <= x1 or y2 <= y1:
                        return det_id, []

                    crop = image.crop((x1, y1, x2, y2))
                    crop_base64 = _image_to_base64(crop)

                    client = await self._get_client()
                    response = await client.post(
                        f"{self.enrichment_url}/scene-ocr",
                        json={
                            "image": crop_base64,
                            "mode": "crop",
                        },
                    )

                    if response.status_code != 200:
                        return det_id, []

                    data = response.json()
                    crop_results: list[RawOCRResult] = []

                    for item in data.get("texts", []):
                        confidence = item.get("confidence", 0)
                        if confidence < CONFIDENCE_EXCLUDE:
                            continue

                        # Record confidence metric for each detected text
                        observe_scene_ocr_confidence(confidence)

                        # Convert crop coordinates to frame coordinates
                        item_bbox = item.get("bbox", [0, 0, 0, 0])
                        frame_bbox = (
                            int(item_bbox[0] + x1),
                            int(item_bbox[1] + y1),
                            int(item_bbox[2] + x1),
                            int(item_bbox[3] + y1),
                        )

                        crop_results.append(
                            RawOCRResult(
                                text=item.get("text", ""),
                                confidence=confidence,
                                bbox=frame_bbox,
                                source="crop",
                                detection_id=det_id,
                            )
                        )

                    # Record processing time for this crop
                    crop_duration = time.perf_counter() - crop_start_time
                    observe_scene_ocr_processing("crop", crop_duration)

                    return det_id, crop_results

                except Exception as e:
                    logger.warning(f"Crop OCR failed for detection {det_id}: {e}")
                    return det_id, []

        # Run all crop OCR tasks in parallel
        tasks = [process_crop(d) for d in relevant_detections]
        crop_results = await asyncio.gather(*tasks)

        # Collect results
        for det_id, ocr_results in crop_results:
            if ocr_results:
                results[det_id] = ocr_results

        return results

    def _deduplicate(
        self,
        frame_results: list[RawOCRResult],
        crop_results: dict[str, list[RawOCRResult]],
        detections: list[DetectionInput],
    ) -> SceneOCRResult:
        """Deduplicate and associate text with detections.

        Deduplication rules:
        1. Spatial overlap (IoU > 70%): Keep higher confidence result
        2. Similar confidence (within 0.05): Prefer crop over frame (higher resolution)
        3. Text association:
           - Crop OCR text -> directly associated with detection
           - Frame OCR text with bbox overlap > 50% -> associate with detection
           - Frame OCR text with no detection overlap -> classify as scene_text

        Args:
            frame_results: OCR results from full-frame processing
            crop_results: OCR results from crop processing by detection ID
            detections: Original YOLO26 detections

        Returns:
            SceneOCRResult with deduplicated and associated results
        """
        scene_texts: list[SceneTextResult] = []
        detection_ocr: dict[str, DetectionOCRResult] = {}

        # Build detection bboxes lookup
        detection_bboxes: dict[str, tuple[int, int, int, int]] = {}
        for det in detections:
            det_id = str(det.id) if det.id else f"det_{id(det)}"
            detection_bboxes[det_id] = det.bbox.to_int_tuple()

        # Initialize detection OCR results from crop results
        for det_id, crop_ocr_list in crop_results.items():
            texts: list[dict[str, Any]] = []
            for ocr in crop_ocr_list:
                texts.append(
                    {
                        "value": ocr.text,
                        "confidence": ocr.confidence,
                        "region": self._determine_region(
                            ocr.bbox, detection_bboxes.get(det_id, (0, 0, 0, 0))
                        ),
                    }
                )
            detection_ocr[det_id] = DetectionOCRResult(
                detection_id=det_id,
                texts=texts,
            )

        # Process frame results
        for frame_ocr in frame_results:
            # Check for duplicates against crop results (IoU > 70%)
            is_duplicate = False
            for _det_id, crop_ocr_list in crop_results.items():
                for crop_ocr in crop_ocr_list:
                    iou = _calculate_iou(frame_ocr.bbox, crop_ocr.bbox)
                    if iou >= IOU_DEDUP_THRESHOLD:
                        # Duplicate found - keep the one with higher confidence
                        # or prefer crop if confidence is similar
                        if abs(frame_ocr.confidence - crop_ocr.confidence) < 0.05:
                            # Similar confidence - prefer crop (higher resolution)
                            is_duplicate = True
                            break
                        elif frame_ocr.confidence <= crop_ocr.confidence:
                            # Crop has higher confidence - skip frame result
                            is_duplicate = True
                            break
                        # else: frame has higher confidence - will be added
                if is_duplicate:
                    break

            if is_duplicate:
                continue

            # Try to associate with a detection
            best_det_id = None
            best_overlap = DETECTION_OVERLAP_THRESHOLD

            for det_id, det_bbox in detection_bboxes.items():
                overlap = _calculate_overlap_ratio(frame_ocr.bbox, det_bbox)
                if overlap > best_overlap:
                    best_overlap = overlap
                    best_det_id = det_id

            if best_det_id:
                # Associate with detection
                if best_det_id not in detection_ocr:
                    detection_ocr[best_det_id] = DetectionOCRResult(detection_id=best_det_id)

                detection_ocr[best_det_id].texts.append(
                    {
                        "value": frame_ocr.text,
                        "confidence": frame_ocr.confidence,
                        "region": self._determine_region(
                            frame_ocr.bbox, detection_bboxes.get(best_det_id, (0, 0, 0, 0))
                        ),
                    }
                )
            else:
                # Scene text (not associated with any detection)
                is_uncertain = CONFIDENCE_LOW <= frame_ocr.confidence < CONFIDENCE_HIGH
                scene_texts.append(
                    SceneTextResult(
                        value=frame_ocr.text,
                        confidence=frame_ocr.confidence,
                        bbox=frame_ocr.bbox,
                        text_type=_classify_text_type(frame_ocr.text),
                        is_uncertain=is_uncertain,
                    )
                )

        return SceneOCRResult(
            scene_texts=scene_texts,
            detection_ocr=detection_ocr,
        )

    def _determine_region(
        self,
        text_bbox: tuple[int, int, int, int],
        det_bbox: tuple[int, int, int, int],
    ) -> str:
        """Determine the region of text within a detection.

        Args:
            text_bbox: Text bounding box (x1, y1, x2, y2)
            det_bbox: Detection bounding box (x1, y1, x2, y2)

        Returns:
            Region name ("top", "chest", "bottom", "left", "right", "center", "unknown")
        """
        if det_bbox[2] <= det_bbox[0] or det_bbox[3] <= det_bbox[1]:
            return "unknown"

        # Calculate text center relative to detection
        text_center_y = (text_bbox[1] + text_bbox[3]) / 2
        text_center_x = (text_bbox[0] + text_bbox[2]) / 2

        det_height = det_bbox[3] - det_bbox[1]
        det_width = det_bbox[2] - det_bbox[0]

        rel_y = (text_center_y - det_bbox[1]) / det_height
        rel_x = (text_center_x - det_bbox[0]) / det_width

        # Determine vertical position
        v_region = "top" if rel_y < 0.33 else ("bottom" if rel_y > 0.66 else "middle")

        # Determine horizontal position
        h_region = "left" if rel_x < 0.33 else ("right" if rel_x > 0.66 else "center")

        # Map to final region name
        # For person detections: top = head area, middle = chest, bottom = legs
        # For vehicles: side = door area, front/back = license plate area
        region_map = {
            ("middle", "center"): "chest",  # For person uniforms
            ("top", "center"): "top",
            ("top", "left"): "top",
            ("top", "right"): "top",
            ("bottom", "center"): "bottom",
            ("bottom", "left"): "bottom",
            ("bottom", "right"): "bottom",
            ("middle", "left"): "left",
            ("middle", "right"): "right",
        }

        return region_map.get((v_region, h_region), "center")


# Module-level singleton
_scene_ocr_service: SceneOCRService | None = None


def get_scene_ocr_service() -> SceneOCRService:
    """Get or create the singleton SceneOCRService instance.

    Returns:
        SceneOCRService instance
    """
    global _scene_ocr_service  # noqa: PLW0603
    if _scene_ocr_service is None:
        _scene_ocr_service = SceneOCRService()
    return _scene_ocr_service


def reset_scene_ocr_service() -> None:
    """Reset the singleton instance (for testing)."""
    global _scene_ocr_service  # noqa: PLW0603
    _scene_ocr_service = None
