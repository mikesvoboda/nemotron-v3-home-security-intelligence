"""Enrichment Pipeline for detection context enhancement.

This module provides the EnrichmentPipeline service that enriches detections
with additional context by running on-demand AI models:

1. License Plate Detection: Runs YOLO11 on vehicle detections
2. License Plate OCR: Runs PaddleOCR on detected plates
3. Face Detection: Runs YOLO11 on person detections

The pipeline uses the ModelManager to efficiently load/unload models,
minimizing VRAM usage while providing rich context for the Nemotron LLM
risk analysis.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC
from pathlib import Path
from typing import Any

from PIL import Image

from backend.core.logging import get_logger
from backend.services.fashion_clip_loader import (
    ClothingClassification,
    classify_clothing,
    format_clothing_context,
)
from backend.services.model_zoo import (
    PERSON_CLASS,
    VEHICLE_CLASSES,
    ModelManager,
    get_model_manager,
)
from backend.services.reid_service import (
    EntityEmbedding,
    EntityMatch,
    get_reid_service,
)
from backend.services.scene_change_detector import (
    SceneChangeResult,
    get_scene_change_detector,
)
from backend.services.segformer_loader import (
    ClothingSegmentationResult,
)
from backend.services.violence_loader import (
    ViolenceDetectionResult,
    classify_violence,
)
from backend.services.vision_extractor import (
    BatchExtractionResult,
    get_vision_extractor,
)
from backend.services.weather_loader import (
    WeatherResult,
)

logger = get_logger(__name__)


@dataclass
class BoundingBox:
    """Bounding box coordinates.

    Attributes:
        x1: Left coordinate
        y1: Top coordinate
        x2: Right coordinate
        y2: Bottom coordinate
        confidence: Detection confidence score (0-1)
    """

    x1: float
    y1: float
    x2: float
    y2: float
    confidence: float = 0.0

    def to_tuple(self) -> tuple[float, float, float, float]:
        """Convert to (x1, y1, x2, y2) tuple."""
        return (self.x1, self.y1, self.x2, self.y2)

    def to_int_tuple(self) -> tuple[int, int, int, int]:
        """Convert to integer (x1, y1, x2, y2) tuple for cropping."""
        return (int(self.x1), int(self.y1), int(self.x2), int(self.y2))

    @property
    def width(self) -> float:
        """Get bounding box width."""
        return self.x2 - self.x1

    @property
    def height(self) -> float:
        """Get bounding box height."""
        return self.y2 - self.y1

    @property
    def center(self) -> tuple[float, float]:
        """Get center point (x, y)."""
        return ((self.x1 + self.x2) / 2, (self.y1 + self.y2) / 2)


@dataclass
class LicensePlateResult:
    """Result from license plate detection and OCR.

    Attributes:
        bbox: Bounding box of the detected plate
        text: OCR text from the plate (may be empty)
        confidence: Detection confidence
        ocr_confidence: OCR confidence (0-1, may be 0 if OCR failed)
        source_detection_id: ID of the vehicle detection this came from
    """

    bbox: BoundingBox
    text: str = ""
    confidence: float = 0.0
    ocr_confidence: float = 0.0
    source_detection_id: int | None = None


@dataclass
class FaceResult:
    """Result from face detection.

    Attributes:
        bbox: Bounding box of the detected face
        confidence: Detection confidence
        source_detection_id: ID of the person detection this came from
    """

    bbox: BoundingBox
    confidence: float = 0.0
    source_detection_id: int | None = None


@dataclass
class EnrichmentResult:
    """Result from the enrichment pipeline.

    Contains all additional context extracted from detections
    for use in the Nemotron LLM prompt.

    Attributes:
        license_plates: Detected license plates with OCR text
        faces: Detected faces
        vision_extraction: Florence-2 attribute extraction results
        person_reid_matches: Re-identification matches for persons
        vehicle_reid_matches: Re-identification matches for vehicles
        scene_change: Scene change detection result
        errors: List of error messages during processing
        processing_time_ms: Total processing time in milliseconds
    """

    license_plates: list[LicensePlateResult] = field(default_factory=list)
    faces: list[FaceResult] = field(default_factory=list)
    vision_extraction: BatchExtractionResult | None = None
    person_reid_matches: dict[str, list[EntityMatch]] = field(default_factory=dict)
    vehicle_reid_matches: dict[str, list[EntityMatch]] = field(default_factory=dict)
    scene_change: SceneChangeResult | None = None
    violence_detection: ViolenceDetectionResult | None = None
    weather_classification: WeatherResult | None = None
    clothing_classifications: dict[str, ClothingClassification] = field(default_factory=dict)
    clothing_segmentation: dict[str, ClothingSegmentationResult] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    processing_time_ms: float = 0.0

    @property
    def has_license_plates(self) -> bool:
        """Check if any license plates were detected."""
        return len(self.license_plates) > 0

    @property
    def has_clothing_segmentation(self) -> bool:
        """Check if any clothing segmentation results are available."""
        return bool(self.clothing_segmentation)

    @property
    def has_readable_plates(self) -> bool:
        """Check if any plates have readable text."""
        return any(plate.text for plate in self.license_plates)

    @property
    def has_faces(self) -> bool:
        """Check if any faces were detected."""
        return len(self.faces) > 0

    @property
    def plate_texts(self) -> list[str]:
        """Get list of all plate texts (non-empty only)."""
        return [plate.text for plate in self.license_plates if plate.text]

    @property
    def has_vision_extraction(self) -> bool:
        """Check if vision extraction results are available."""
        return self.vision_extraction is not None

    @property
    def has_reid_matches(self) -> bool:
        """Check if any re-identification matches were found."""
        return bool(self.person_reid_matches) or bool(self.vehicle_reid_matches)

    @property
    def has_scene_change(self) -> bool:
        """Check if scene change was detected."""
        return self.scene_change is not None and self.scene_change.change_detected

    @property
    def has_violence(self) -> bool:
        """Check if violence was detected."""
        return self.violence_detection is not None and self.violence_detection.is_violent

    @property
    def has_clothing_classifications(self) -> bool:
        """Check if any clothing classifications are available."""
        return bool(self.clothing_classifications)

    @property
    def has_suspicious_clothing(self) -> bool:
        """Check if any suspicious clothing was detected."""
        return any(c.is_suspicious for c in self.clothing_classifications.values())

    def to_context_string(self) -> str:  # noqa: PLR0912
        """Generate context string for LLM prompt.

        Returns:
            Formatted string describing enrichment results
        """
        from backend.services.reid_service import format_full_reid_context
        from backend.services.vision_extractor import (
            format_batch_extraction_result,
        )

        lines = []

        # Vision extraction (Florence-2)
        if self.vision_extraction:
            vision_str = format_batch_extraction_result(self.vision_extraction)
            if vision_str and not vision_str.startswith("No vision"):
                lines.append("## Vision Analysis")
                lines.append(vision_str)

        # Re-identification
        if self.person_reid_matches or self.vehicle_reid_matches:
            reid_str = format_full_reid_context(self.person_reid_matches, self.vehicle_reid_matches)
            if reid_str and not reid_str.startswith("No entities"):
                lines.append("## Re-Identification")
                lines.append(reid_str)

        # Scene change
        if self.scene_change and self.scene_change.change_detected:
            lines.append("## Scene Change")
            lines.append(
                f"Scene change detected (similarity: {self.scene_change.similarity_score:.2f})"
            )

        # Violence detection
        if self.violence_detection:
            lines.append("## Violence Detection")
            if self.violence_detection.is_violent:
                lines.append(
                    f"**VIOLENCE DETECTED** (confidence: {self.violence_detection.confidence:.0%})"
                )
            else:
                lines.append(
                    f"No violence detected (confidence: {self.violence_detection.confidence:.0%})"
                )

        # Clothing Classifications (FashionCLIP)
        if self.clothing_classifications:
            lines.append(
                f"## Clothing Classifications ({len(self.clothing_classifications)} persons)"
            )
            for det_id, classification in self.clothing_classifications.items():
                lines.append(f"  Person {det_id}:")
                lines.append(f"    {format_clothing_context(classification)}")

        # License plates
        if self.license_plates:
            lines.append(f"## License Plates ({len(self.license_plates)} detected)")
            for i, plate in enumerate(self.license_plates, 1):
                if plate.text:
                    lines.append(
                        f"  - Plate {i}: {plate.text} (OCR confidence: {plate.ocr_confidence:.0%})"
                    )
                else:
                    lines.append(f"  - Plate {i}: [unreadable]")

        # Faces
        if self.faces:
            lines.append(f"## Faces ({len(self.faces)} detected)")
            for i, face in enumerate(self.faces, 1):
                lines.append(f"  - Face {i}: confidence {face.confidence:.0%}")

        if not lines:
            return "No additional context extracted."

        return "\n\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        Returns:
            Dictionary representation of enrichment results
        """
        return {
            "license_plates": [
                {
                    "bbox": plate.bbox.to_tuple(),
                    "text": plate.text,
                    "confidence": plate.confidence,
                    "ocr_confidence": plate.ocr_confidence,
                    "source_detection_id": plate.source_detection_id,
                }
                for plate in self.license_plates
            ],
            "faces": [
                {
                    "bbox": face.bbox.to_tuple(),
                    "confidence": face.confidence,
                    "source_detection_id": face.source_detection_id,
                }
                for face in self.faces
            ],
            "violence_detection": (
                self.violence_detection.to_dict() if self.violence_detection else None
            ),
            "errors": self.errors,
            "processing_time_ms": self.processing_time_ms,
        }


@dataclass
class DetectionInput:
    """Input detection for enrichment pipeline.

    Simplified detection representation for the enrichment pipeline.
    Maps from the Detection model or API schemas.

    Attributes:
        id: Detection ID (optional)
        class_name: Object class (e.g., "car", "person")
        confidence: Detection confidence
        bbox: Bounding box coordinates
    """

    class_name: str
    confidence: float
    bbox: BoundingBox
    id: int | None = None


class EnrichmentPipeline:
    """Pipeline for enriching detections with additional context.

    The EnrichmentPipeline orchestrates on-demand model loading to extract
    additional context from detections:

    1. Vehicle detections -> License plate detection -> OCR
    2. Person detections -> Face detection

    Models are loaded lazily via the ModelManager and unloaded after use
    to maximize VRAM availability for Nemotron and RT-DETRv2.

    Usage:
        pipeline = EnrichmentPipeline()

        result = await pipeline.enrich_batch(detections, images)
        context = result.to_context_string()

    Attributes:
        model_manager: ModelManager instance for model loading
        min_confidence: Minimum detection confidence for enrichment
        license_plate_enabled: Whether to run license plate detection
        face_detection_enabled: Whether to run face detection
        ocr_enabled: Whether to run OCR on detected plates
    """

    def __init__(
        self,
        model_manager: ModelManager | None = None,
        min_confidence: float = 0.5,
        license_plate_enabled: bool = True,
        face_detection_enabled: bool = True,
        ocr_enabled: bool = True,
        vision_extraction_enabled: bool = True,
        reid_enabled: bool = True,
        scene_change_enabled: bool = True,
        violence_detection_enabled: bool = True,
        clothing_classification_enabled: bool = True,
        clothing_segmentation_enabled: bool = True,
        redis_client: Any | None = None,
    ) -> None:
        """Initialize the EnrichmentPipeline.

        Args:
            model_manager: ModelManager instance (uses global if not provided)
            min_confidence: Minimum confidence for detections to enrich
            license_plate_enabled: Enable license plate detection
            face_detection_enabled: Enable face detection
            ocr_enabled: Enable OCR on detected plates
            vision_extraction_enabled: Enable Florence-2 vision extraction
            reid_enabled: Enable CLIP re-identification
            scene_change_enabled: Enable scene change detection
            violence_detection_enabled: Enable violence detection (runs when 2+ persons)
            clothing_classification_enabled: Enable FashionCLIP clothing classification
            clothing_segmentation_enabled: Enable SegFormer clothing segmentation
            redis_client: Redis client for re-id storage (optional)
        """
        self.model_manager = model_manager or get_model_manager()
        self.min_confidence = min_confidence
        self.license_plate_enabled = license_plate_enabled
        self.face_detection_enabled = face_detection_enabled
        self.ocr_enabled = ocr_enabled
        self.vision_extraction_enabled = vision_extraction_enabled
        self.reid_enabled = reid_enabled
        self.scene_change_enabled = scene_change_enabled
        self.violence_detection_enabled = violence_detection_enabled
        self.clothing_classification_enabled = clothing_classification_enabled
        self.clothing_segmentation_enabled = clothing_segmentation_enabled
        self.redis_client = redis_client

        # Initialize services
        self._vision_extractor = get_vision_extractor()
        self._reid_service = get_reid_service()
        self._scene_detector = get_scene_change_detector()

        logger.info(
            f"EnrichmentPipeline initialized: "
            f"license_plate={license_plate_enabled}, "
            f"face_detection={face_detection_enabled}, "
            f"ocr={ocr_enabled}, "
            f"vision_extraction={vision_extraction_enabled}, "
            f"reid={reid_enabled}, "
            f"scene_change={scene_change_enabled}"
        )

    async def enrich_batch(  # noqa: PLR0912
        self,
        detections: list[DetectionInput],
        images: dict[int | None, Image.Image | Path | str],
        camera_id: str | None = None,
    ) -> EnrichmentResult:
        """Enrich a batch of detections with additional context.

        Processes detections through the enrichment pipeline:
        1. Filter vehicles -> run license plate detection -> run OCR
        2. Filter persons -> run face detection
        3. Run Florence-2 vision extraction for attributes
        4. Run CLIP re-identification
        5. Run scene change detection

        Args:
            detections: List of detections to enrich
            images: Dictionary mapping detection IDs to images (PIL Image, Path, or str)
                   Use None key for a single shared image
            camera_id: Camera ID for scene change detection and re-id

        Returns:
            EnrichmentResult with all extracted context
        """
        import time

        start_time = time.monotonic()
        result = EnrichmentResult()

        if not detections:
            return result

        # Get the shared image for full-frame analysis
        shared_image = images.get(None)
        if shared_image:
            pil_image = await self._load_image(shared_image)
        else:
            pil_image = None

        # Filter detections by confidence
        high_conf_detections = [d for d in detections if d.confidence >= self.min_confidence]

        if not high_conf_detections:
            return result

        # Process vehicles for license plates
        if self.license_plate_enabled:
            vehicles = [d for d in high_conf_detections if d.class_name in VEHICLE_CLASSES]
            if vehicles:
                try:
                    plates = await self._detect_license_plates(vehicles, images)
                    result.license_plates.extend(plates)

                    # Run OCR on detected plates
                    if self.ocr_enabled and plates:
                        await self._read_plates(result.license_plates, images)

                except Exception as e:
                    error_msg = f"License plate detection failed: {e}"
                    logger.error(error_msg)
                    result.errors.append(error_msg)

        # Process persons for faces
        if self.face_detection_enabled:
            persons = [d for d in high_conf_detections if d.class_name == PERSON_CLASS]
            if persons:
                try:
                    faces = await self._detect_faces(persons, images)
                    result.faces.extend(faces)
                except Exception as e:
                    error_msg = f"Face detection failed: {e}"
                    logger.error(error_msg)
                    result.errors.append(error_msg)

        # Run Florence-2 vision extraction
        if self.vision_extraction_enabled and pil_image:
            try:
                # Convert detections to dict format for VisionExtractor
                det_dicts = [
                    {
                        "class_name": d.class_name,
                        "confidence": d.confidence,
                        "bbox": d.bbox.to_tuple() if d.bbox else None,
                        "detection_id": str(d.id) if d.id else str(i),
                    }
                    for i, d in enumerate(high_conf_detections)
                ]
                result.vision_extraction = await self._vision_extractor.extract_batch_attributes(
                    pil_image, det_dicts
                )
            except Exception as e:
                error_msg = f"Vision extraction failed: {e}"
                logger.error(error_msg)
                result.errors.append(error_msg)

        # Run CLIP re-identification
        if self.reid_enabled and self.redis_client and pil_image:
            try:
                await self._run_reid(high_conf_detections, pil_image, camera_id, result)
            except Exception as e:
                error_msg = f"Re-identification failed: {e}"
                logger.error(error_msg)
                result.errors.append(error_msg)

        # Run scene change detection
        if self.scene_change_enabled and camera_id and pil_image:
            try:
                import numpy as np

                frame_array = np.array(pil_image)
                result.scene_change = self._scene_detector.detect_changes(camera_id, frame_array)
            except Exception as e:
                error_msg = f"Scene change detection failed: {e}"
                logger.error(error_msg)
                result.errors.append(error_msg)

        # Run violence detection when 2+ persons are detected (optimization)
        if self.violence_detection_enabled and pil_image:
            persons = [d for d in high_conf_detections if d.class_name == PERSON_CLASS]
            if len(persons) >= 2:
                try:
                    result.violence_detection = await self._detect_violence(pil_image)
                except Exception as e:
                    error_msg = f"Violence detection failed: {e}"
                    logger.error(error_msg)
                    result.errors.append(error_msg)

        # Run clothing classification on person crops
        if self.clothing_classification_enabled and pil_image:
            persons = [d for d in high_conf_detections if d.class_name == PERSON_CLASS]
            if persons:
                try:
                    result.clothing_classifications = await self._classify_person_clothing(
                        persons, pil_image
                    )
                except Exception as e:
                    error_msg = f"Clothing classification failed: {e}"
                    logger.error(error_msg)
                    result.errors.append(error_msg)

        # Run SegFormer clothing segmentation on person crops
        if self.clothing_segmentation_enabled and pil_image:
            persons = [d for d in high_conf_detections if d.class_name == PERSON_CLASS]
            if persons:
                try:
                    result.clothing_segmentation = await self._segment_person_clothing(
                        persons, pil_image
                    )
                except Exception as e:
                    error_msg = f"Clothing segmentation failed: {e}"
                    logger.error(error_msg)
                    result.errors.append(error_msg)

        result.processing_time_ms = (time.monotonic() - start_time) * 1000
        logger.info(
            f"Enrichment complete: {len(result.license_plates)} plates, "
            f"{len(result.faces)} faces, "
            f"vision={'yes' if result.vision_extraction else 'no'}, "
            f"reid={'yes' if result.has_reid_matches else 'no'}, "
            f"scene_change={'yes' if result.has_scene_change else 'no'}, "
            f"clothing_class={len(result.clothing_classifications)}, "
            f"clothing_seg={len(result.clothing_segmentation)} "
            f"in {result.processing_time_ms:.1f}ms"
        )

        return result

    async def _run_reid(
        self,
        detections: list[DetectionInput],
        image: Image.Image,
        camera_id: str | None,
        result: EnrichmentResult,
    ) -> None:
        """Run re-identification on detections.

        Args:
            detections: List of detections
            image: Full frame image
            camera_id: Camera ID
            result: EnrichmentResult to update
        """
        from datetime import datetime

        from redis.asyncio import Redis

        # Ensure redis_client is available (caller should check before calling)
        assert self.redis_client is not None, "redis_client required for re-id"
        redis: Redis = self.redis_client  # type: ignore[assignment]

        # Load CLIP model
        async with self.model_manager.load("clip-vit-l") as model:
            for i, det in enumerate(detections):
                det_id = str(det.id) if det.id else str(i)
                entity_type = "person" if det.class_name == PERSON_CLASS else "vehicle"

                if det.class_name not in VEHICLE_CLASSES and det.class_name != PERSON_CLASS:
                    continue

                try:
                    # Generate embedding
                    bbox = det.bbox.to_int_tuple() if det.bbox else None
                    embedding = await self._reid_service.generate_embedding(model, image, bbox)

                    # Find matches
                    matches = await self._reid_service.find_matching_entities(
                        redis,
                        embedding,
                        entity_type=entity_type,
                        exclude_detection_id=det_id,
                    )

                    if matches:
                        if entity_type == "person":
                            result.person_reid_matches[det_id] = matches
                        else:
                            result.vehicle_reid_matches[det_id] = matches

                    # Store this embedding for future matching
                    attrs = {}
                    if result.vision_extraction:
                        if det_id in result.vision_extraction.person_attributes:
                            p_attrs = result.vision_extraction.person_attributes[det_id]
                            attrs = {
                                "clothing": p_attrs.clothing,
                                "carrying": p_attrs.carrying,
                            }
                        elif det_id in result.vision_extraction.vehicle_attributes:
                            v_attrs = result.vision_extraction.vehicle_attributes[det_id]
                            attrs = {
                                "color": v_attrs.color,
                                "vehicle_type": v_attrs.vehicle_type,
                            }

                    entity_embedding = EntityEmbedding(
                        entity_type=entity_type,
                        embedding=embedding,
                        camera_id=camera_id or "unknown",
                        timestamp=datetime.now(UTC),
                        detection_id=det_id,
                        attributes=attrs,
                    )
                    await self._reid_service.store_embedding(redis, entity_embedding)

                except Exception as e:
                    logger.warning(f"Re-id failed for detection {det_id}: {e}")

    async def _detect_license_plates(
        self,
        vehicles: list[DetectionInput],
        images: dict[int | None, Image.Image | Path | str],
    ) -> list[LicensePlateResult]:
        """Detect license plates in vehicle detections.

        Args:
            vehicles: List of vehicle detections
            images: Dictionary mapping detection IDs to images

        Returns:
            List of detected license plates
        """
        results: list[LicensePlateResult] = []

        try:
            async with self.model_manager.load("yolo11-license-plate") as model:
                for vehicle in vehicles:
                    image = self._get_image_for_detection(vehicle, images)
                    if image is None:
                        continue

                    # Crop to vehicle bounding box for more accurate plate detection
                    cropped = await self._crop_to_bbox(image, vehicle.bbox)
                    if cropped is None:
                        continue

                    # Run plate detection
                    plates = await self._run_yolo_detection(model, cropped, vehicle.id)
                    results.extend(plates)

        except KeyError:
            logger.warning("yolo11-license-plate model not available")
        except RuntimeError as e:
            logger.error(f"License plate detection error: {e}")

        return results

    async def _read_plates(
        self,
        plates: list[LicensePlateResult],
        images: dict[int | None, Image.Image | Path | str],
    ) -> None:
        """Run OCR on detected license plates to extract text.

        Updates the plates in-place with OCR results.

        Args:
            plates: List of detected plates to OCR
            images: Dictionary mapping detection IDs to images
        """
        if not plates:
            return

        try:
            async with self.model_manager.load("paddleocr") as ocr:
                for plate in plates:
                    # Get the original image
                    image = images.get(plate.source_detection_id) or images.get(None)
                    if image is None:
                        continue

                    # Load image if path
                    pil_image = await self._load_image(image)
                    if pil_image is None:
                        continue

                    # Crop to plate bounding box
                    cropped = await self._crop_to_bbox(pil_image, plate.bbox)
                    if cropped is None:
                        continue

                    # Run OCR
                    text, confidence = await self._run_ocr(ocr, cropped)
                    plate.text = text
                    plate.ocr_confidence = confidence

        except KeyError:
            logger.warning("paddleocr model not available")
        except RuntimeError as e:
            logger.error(f"OCR error: {e}")

    async def _detect_faces(
        self,
        persons: list[DetectionInput],
        images: dict[int | None, Image.Image | Path | str],
    ) -> list[FaceResult]:
        """Detect faces in person detections.

        Args:
            persons: List of person detections
            images: Dictionary mapping detection IDs to images

        Returns:
            List of detected faces
        """
        results: list[FaceResult] = []

        try:
            async with self.model_manager.load("yolo11-face") as model:
                for person in persons:
                    image = self._get_image_for_detection(person, images)
                    if image is None:
                        continue

                    # Crop to person bounding box for more accurate face detection
                    cropped = await self._crop_to_bbox(image, person.bbox)
                    if cropped is None:
                        continue

                    # Run face detection
                    faces = await self._run_face_detection(model, cropped, person.id)
                    results.extend(faces)

        except KeyError:
            logger.warning("yolo11-face model not available")
        except RuntimeError as e:
            logger.error(f"Face detection error: {e}")

        return results

    def _get_image_for_detection(
        self,
        detection: DetectionInput,
        images: dict[int | None, Image.Image | Path | str],
    ) -> Image.Image | Path | str | None:
        """Get image for a specific detection.

        Args:
            detection: Detection to get image for
            images: Dictionary mapping detection IDs to images

        Returns:
            Image for the detection, or None if not found
        """
        # Try detection-specific image first
        if detection.id is not None and detection.id in images:
            return images[detection.id]

        # Fall back to shared image (None key)
        return images.get(None)

    async def _load_image(self, image: Image.Image | Path | str) -> Image.Image | None:
        """Load image from path or return if already PIL Image.

        Args:
            image: PIL Image, Path, or string path

        Returns:
            PIL Image or None if loading fails
        """
        if isinstance(image, Image.Image):
            return image

        try:
            path = Path(image) if isinstance(image, str) else image
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, lambda: Image.open(path))
        except Exception as e:
            logger.warning(f"Failed to load image: {e}")
            return None

    async def _crop_to_bbox(
        self, image: Image.Image | Path | str, bbox: BoundingBox
    ) -> Image.Image | None:
        """Crop image to bounding box.

        Args:
            image: Image to crop
            bbox: Bounding box coordinates

        Returns:
            Cropped PIL Image or None if cropping fails
        """
        pil_image = await self._load_image(image)
        if pil_image is None:
            return None

        try:
            # Ensure coordinates are within image bounds
            width, height = pil_image.size
            x1 = max(0, int(bbox.x1))
            y1 = max(0, int(bbox.y1))
            x2 = min(width, int(bbox.x2))
            y2 = min(height, int(bbox.y2))

            if x2 <= x1 or y2 <= y1:
                return None

            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, lambda: pil_image.crop((x1, y1, x2, y2)))
        except Exception as e:
            logger.warning(f"Failed to crop image: {e}")
            return None

    async def _run_yolo_detection(
        self, model: Any, image: Image.Image, source_detection_id: int | None
    ) -> list[LicensePlateResult]:
        """Run YOLO detection and convert results to LicensePlateResult.

        Args:
            model: Loaded YOLO model
            image: Image to run detection on
            source_detection_id: ID of the source vehicle detection

        Returns:
            List of detected license plates
        """
        results: list[LicensePlateResult] = []

        try:
            loop = asyncio.get_event_loop()
            detections = await loop.run_in_executor(
                None, lambda: model.predict(image, verbose=False)
            )

            if detections and len(detections) > 0:
                for det in detections[0].boxes:
                    bbox_data = det.xyxy[0].tolist()
                    conf = float(det.conf[0])

                    results.append(
                        LicensePlateResult(
                            bbox=BoundingBox(
                                x1=bbox_data[0],
                                y1=bbox_data[1],
                                x2=bbox_data[2],
                                y2=bbox_data[3],
                                confidence=conf,
                            ),
                            confidence=conf,
                            source_detection_id=source_detection_id,
                        )
                    )

        except Exception as e:
            logger.warning(f"YOLO detection failed: {e}")

        return results

    async def _run_face_detection(
        self, model: Any, image: Image.Image, source_detection_id: int | None
    ) -> list[FaceResult]:
        """Run face detection and convert results to FaceResult.

        Args:
            model: Loaded YOLO face model
            image: Image to run detection on
            source_detection_id: ID of the source person detection

        Returns:
            List of detected faces
        """
        results: list[FaceResult] = []

        try:
            loop = asyncio.get_event_loop()
            detections = await loop.run_in_executor(
                None, lambda: model.predict(image, verbose=False)
            )

            if detections and len(detections) > 0:
                for det in detections[0].boxes:
                    bbox_data = det.xyxy[0].tolist()
                    conf = float(det.conf[0])

                    results.append(
                        FaceResult(
                            bbox=BoundingBox(
                                x1=bbox_data[0],
                                y1=bbox_data[1],
                                x2=bbox_data[2],
                                y2=bbox_data[3],
                                confidence=conf,
                            ),
                            confidence=conf,
                            source_detection_id=source_detection_id,
                        )
                    )

        except Exception as e:
            logger.warning(f"Face detection failed: {e}")

        return results

    async def _run_ocr(self, ocr: Any, image: Image.Image) -> tuple[str, float]:
        """Run OCR on an image and extract text.

        Args:
            ocr: Loaded PaddleOCR instance
            image: Image to OCR

        Returns:
            Tuple of (text, confidence)
        """
        try:
            import numpy as np

            # Convert PIL to numpy for PaddleOCR
            loop = asyncio.get_event_loop()

            def run_ocr() -> tuple[str, float]:
                img_array = np.array(image)
                result = ocr.ocr(img_array, cls=True)

                if not result or not result[0]:
                    return "", 0.0

                # Extract text from all detected regions
                texts = []
                confidences = []

                for line in result[0]:
                    if line and len(line) >= 2:
                        text_info = line[1]
                        if isinstance(text_info, tuple) and len(text_info) >= 2:
                            texts.append(text_info[0])
                            confidences.append(text_info[1])

                if not texts:
                    return "", 0.0

                # Join texts and average confidences
                combined_text = " ".join(texts).strip()
                avg_confidence = sum(confidences) / len(confidences)

                return combined_text, avg_confidence

            return await loop.run_in_executor(None, run_ocr)

        except Exception as e:
            logger.warning(f"OCR failed: {e}")
            return "", 0.0

    async def _detect_violence(self, image: Image.Image) -> ViolenceDetectionResult:
        """Run violence detection on a full frame image.

        This method loads the violence detection model, runs inference,
        and returns the classification result.

        Args:
            image: PIL Image (full frame) to classify

        Returns:
            ViolenceDetectionResult with classification

        Raises:
            RuntimeError: If violence detection fails
        """
        try:
            async with self.model_manager.load("violence-detection") as model_data:
                result = await classify_violence(model_data, image)
                if result.is_violent:
                    logger.warning(f"Violence detected with {result.confidence:.0%} confidence")
                return result

        except KeyError as e:
            logger.warning("violence-detection model not available in MODEL_ZOO")
            raise RuntimeError("violence-detection model not configured") from e
        except Exception as e:
            logger.error(f"Violence detection error: {e}")
            raise

    async def _classify_person_clothing(
        self,
        persons: list[DetectionInput],
        image: Image.Image,
    ) -> dict[str, ClothingClassification]:
        """Classify clothing for each person detection using FashionCLIP.

        Args:
            persons: List of person detections to classify
            image: Full frame image to crop persons from

        Returns:
            Dictionary mapping detection IDs to ClothingClassification results
        """
        results: dict[str, ClothingClassification] = {}

        if not persons:
            return results

        try:
            async with self.model_manager.load("fashion-clip") as model_data:
                for i, person in enumerate(persons):
                    det_id = str(person.id) if person.id else str(i)

                    try:
                        # Crop person from full frame
                        person_crop = await self._crop_to_bbox(image, person.bbox)
                        if person_crop is None:
                            continue

                        # Classify clothing
                        classification = await classify_clothing(model_data, person_crop)
                        results[det_id] = classification

                        logger.debug(
                            f"Person {det_id} clothing: {classification.raw_description} "
                            f"({classification.confidence:.0%})"
                        )

                    except Exception as e:
                        logger.warning(f"Clothing classification failed for person {det_id}: {e}")
                        continue

        except KeyError:
            logger.warning("fashion-clip model not available in MODEL_ZOO")
        except Exception as e:
            logger.error(f"Clothing classification error: {e}")

        return results

    async def _segment_person_clothing(
        self,
        persons: list[DetectionInput],
        image: Image.Image,
    ) -> dict[str, ClothingSegmentationResult]:
        """Segment clothing for each person detection using SegFormer.

        Runs SegFormer B2 Clothes model on person crops to extract detailed
        clothing segmentation including hats, sunglasses, upper clothes, pants,
        dress, bags, shoes, and other apparel items.

        Args:
            persons: List of person detections to segment
            image: Full frame image to crop persons from

        Returns:
            Dictionary mapping detection IDs to ClothingSegmentationResult
        """
        from backend.services.segformer_loader import segment_clothing

        results: dict[str, ClothingSegmentationResult] = {}

        if not persons:
            return results

        try:
            async with self.model_manager.load("segformer-b2-clothes") as model_data:
                model, processor = model_data

                for i, person in enumerate(persons):
                    det_id = str(person.id) if person.id else str(i)

                    try:
                        # Crop person from full frame
                        person_crop = await self._crop_to_bbox(image, person.bbox)
                        if person_crop is None:
                            continue

                        # Segment clothing
                        segmentation = await segment_clothing(model, processor, person_crop)
                        results[det_id] = segmentation

                        logger.debug(
                            f"Person {det_id} clothing items: {segmentation.clothing_items}, "
                            f"face_covered={segmentation.has_face_covered}, "
                            f"has_bag={segmentation.has_bag}"
                        )

                    except Exception as e:
                        logger.warning(f"Clothing segmentation failed for person {det_id}: {e}")
                        continue

        except KeyError:
            logger.warning("segformer-b2-clothes model not available in MODEL_ZOO")
        except Exception as e:
            logger.error(f"Clothing segmentation error: {e}")

        return results


# Global EnrichmentPipeline instance
_enrichment_pipeline: EnrichmentPipeline | None = None


def get_enrichment_pipeline() -> EnrichmentPipeline:
    """Get or create the global EnrichmentPipeline instance.

    Returns:
        Global EnrichmentPipeline instance
    """
    global _enrichment_pipeline  # noqa: PLW0603
    if _enrichment_pipeline is None:
        _enrichment_pipeline = EnrichmentPipeline()
    return _enrichment_pipeline


def reset_enrichment_pipeline() -> None:
    """Reset the global EnrichmentPipeline instance (for testing)."""
    global _enrichment_pipeline  # noqa: PLW0603
    _enrichment_pipeline = None
