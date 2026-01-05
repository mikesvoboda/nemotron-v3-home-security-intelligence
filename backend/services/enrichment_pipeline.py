"""Enrichment Pipeline for detection context enhancement.

This module provides the EnrichmentPipeline service that enriches detections
with additional context by running on-demand AI models:

1. License Plate Detection: Runs YOLO11 on vehicle detections
2. License Plate OCR: Runs PaddleOCR on detected plates
3. Face Detection: Runs YOLO11 on person detections
4. Image Quality Assessment: BRISQUE for blur/noise/tampering detection

The pipeline can use either:
- Local models via ModelManager (default, for single-process deployments)
- Remote HTTP service at ai-enrichment:8094 (for containerized deployments)

Set use_enrichment_service=True to use the HTTP service for vehicle, pet,
and clothing classification instead of loading models locally.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC
from pathlib import Path
from typing import Any

from PIL import Image

from backend.core.logging import get_logger
from backend.core.metrics import record_enrichment_model_call

# Import enrichment client for remote HTTP service
from backend.services.enrichment_client import (
    EnrichmentClient,
    EnrichmentUnavailableError,
    get_enrichment_client,
)
from backend.services.fashion_clip_loader import (
    ClothingClassification,
    classify_clothing,
    format_clothing_context,
)
from backend.services.image_quality_loader import (
    ImageQualityResult,
    assess_image_quality,
    detect_quality_change,
    interpret_blur_with_motion,
)
from backend.services.model_zoo import (
    ANIMAL_CLASSES,
    PERSON_CLASS,
    VEHICLE_CLASSES,
    ModelManager,
    get_model_manager,
)
from backend.services.pet_classifier_loader import (
    PetClassificationResult,
    classify_pet,
    format_pet_for_nemotron,
    is_likely_pet_false_positive,
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
from backend.services.vehicle_classifier_loader import (
    VehicleClassificationResult,
    classify_vehicle,
    format_vehicle_classification_context,
)
from backend.services.vehicle_damage_loader import (
    VehicleDamageResult,
    detect_vehicle_damage,
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
    classify_weather,
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
    vehicle_classifications: dict[str, VehicleClassificationResult] = field(default_factory=dict)
    vehicle_damage: dict[str, VehicleDamageResult] = field(default_factory=dict)
    pet_classifications: dict[str, PetClassificationResult] = field(default_factory=dict)
    image_quality: ImageQualityResult | None = None
    quality_change_detected: bool = False
    quality_change_description: str = ""
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

    @property
    def has_vehicle_classifications(self) -> bool:
        """Check if any vehicle classifications are available."""
        return bool(self.vehicle_classifications)

    @property
    def has_commercial_vehicles(self) -> bool:
        """Check if any commercial/delivery vehicles were detected."""
        return any(v.is_commercial for v in self.vehicle_classifications.values())

    @property
    def has_vehicle_damage(self) -> bool:
        """Check if any vehicle damage was detected."""
        return any(d.has_damage for d in self.vehicle_damage.values())

    @property
    def has_high_security_damage(self) -> bool:
        """Check if any high-security vehicle damage was detected (glass shatter, lamp broken)."""
        return any(d.has_high_security_damage for d in self.vehicle_damage.values())

    @property
    def has_image_quality(self) -> bool:
        """Check if image quality assessment is available."""
        return self.image_quality is not None

    @property
    def has_quality_issues(self) -> bool:
        """Check if any image quality issues were detected."""
        return self.image_quality is not None and not self.image_quality.is_good_quality

    @property
    def has_motion_blur(self) -> bool:
        """Check if motion blur was detected (possible fast movement)."""
        return self.image_quality is not None and self.image_quality.is_blurry

    @property
    def has_pet_classifications(self) -> bool:
        """Check if any pet classifications are available."""
        return bool(self.pet_classifications)

    @property
    def has_confirmed_pets(self) -> bool:
        """Check if any high-confidence household pets were detected."""
        return any(is_likely_pet_false_positive(p) for p in self.pet_classifications.values())

    @property
    def pet_only_event(self) -> bool:
        """Check if this is a pet-only event (can skip Nemotron analysis)."""
        return (
            self.has_confirmed_pets
            and not self.has_faces
            and not self.has_license_plates
            and not self.has_violence
            and not self.has_clothing_classifications
        )

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

        # Vehicle Damage Detection
        if self.vehicle_damage:
            damaged_vehicles = {k: v for k, v in self.vehicle_damage.items() if v.has_damage}
            if damaged_vehicles:
                lines.append(f"## Vehicle Damage ({len(damaged_vehicles)} vehicles with damage)")
                for det_id, damage_result in damaged_vehicles.items():
                    lines.append(f"  Vehicle {det_id}:")
                    lines.append(f"    {damage_result.to_context_string()}")
                    if damage_result.has_high_security_damage:
                        lines.append("    **SECURITY ALERT**: High-priority damage detected")

        # Vehicle Classifications (ResNet-50)
        if self.vehicle_classifications:
            lines.append(
                f"## Vehicle Classifications ({len(self.vehicle_classifications)} vehicles)"
            )
            for det_id, vehicle_class in self.vehicle_classifications.items():
                lines.append(f"  Vehicle {det_id}:")
                lines.append(f"    {format_vehicle_classification_context(vehicle_class)}")

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

        # Pet Classifications (for false positive context)
        if self.pet_classifications:
            lines.append(f"## Pet Classifications ({len(self.pet_classifications)} animals)")
            for det_id, pet_result in self.pet_classifications.items():
                lines.append(f"  - Animal {det_id}: {format_pet_for_nemotron(pet_result)}")
            if self.pet_only_event:
                lines.append("  **NOTE**: Pet-only event - low security risk")

        # Image Quality Assessment
        if self.image_quality:
            lines.append("## Image Quality Assessment")
            lines.append(f"  {self.image_quality.format_context()}")
            if self.quality_change_detected:
                lines.append(f"  **ALERT**: {self.quality_change_description}")

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
            "vehicle_damage": {
                det_id: result.to_dict() for det_id, result in self.vehicle_damage.items()
            },
            "vehicle_classifications": {
                det_id: result.to_dict() for det_id, result in self.vehicle_classifications.items()
            },
            "image_quality": (self.image_quality.to_dict() if self.image_quality else None),
            "quality_change_detected": self.quality_change_detected,
            "quality_change_description": self.quality_change_description,
            "errors": self.errors,
            "processing_time_ms": self.processing_time_ms,
        }

    def to_prompt_context(self, time_of_day: str | None = None) -> dict[str, str]:
        """Generate all prompt context sections for MODEL_ZOO_ENHANCED template.

        Returns a dictionary of formatted context strings for each enrichment
        category, suitable for direct insertion into the prompt template.

        Args:
            time_of_day: Optional time context for risk assessment

        Returns:
            Dictionary mapping prompt field names to formatted context strings
        """
        from backend.services.prompts import (
            format_action_recognition_context,
            format_clothing_analysis_context,
            format_depth_context,
            format_image_quality_context,
            format_pet_classification_context,
            format_pose_analysis_context,
            format_vehicle_classification_context,
            format_vehicle_damage_context,
            format_violence_context,
            format_weather_context,
        )

        return {
            # Violence analysis
            "violence_context": format_violence_context(self.violence_detection),
            # Weather context
            "weather_context": format_weather_context(self.weather_classification),
            # Image quality
            "image_quality_context": format_image_quality_context(
                self.image_quality,
                self.quality_change_detected,
                self.quality_change_description,
            ),
            # Clothing analysis
            "clothing_analysis_context": format_clothing_analysis_context(
                self.clothing_classifications,
                self.clothing_segmentation,
            ),
            # Vehicle classification
            "vehicle_classification_context": format_vehicle_classification_context(
                self.vehicle_classifications
            ),
            # Vehicle damage
            "vehicle_damage_context": format_vehicle_damage_context(
                self.vehicle_damage,
                time_of_day=time_of_day,
            ),
            # Pet classification
            "pet_classification_context": format_pet_classification_context(
                self.pet_classifications
            ),
            # Pose analysis (placeholder for future ViTPose integration)
            "pose_analysis": format_pose_analysis_context(None),
            # Action recognition (placeholder for future X-CLIP integration)
            "action_recognition": format_action_recognition_context(None),
            # Depth context (placeholder for future Depth Anything V2 integration)
            "depth_context": format_depth_context(None),
        }

    def get_risk_modifiers(self) -> dict[str, float]:
        """Calculate risk score modifiers based on enrichment results.

        Returns a dictionary of named risk modifiers that can be used to
        adjust the base risk score from Nemotron.

        Positive values increase risk, negative values decrease risk.

        Returns:
            Dictionary mapping modifier names to float values (-1.0 to 1.0)
        """
        modifiers: dict[str, float] = {}

        # Violence detection - major risk increase
        if self.has_violence:
            assert self.violence_detection is not None
            modifiers["violence"] = 0.5 + (0.5 * self.violence_detection.confidence)

        # Pet-only event - significant risk decrease
        if self.pet_only_event:
            modifiers["pet_only"] = -0.7

        # High-confidence pets without other threats - moderate risk decrease
        elif self.has_confirmed_pets and not self.has_violence:
            modifiers["confirmed_pet"] = -0.3

        # Suspicious clothing - moderate risk increase
        if self.has_suspicious_clothing:
            modifiers["suspicious_attire"] = 0.3

        # Service uniform - moderate risk decrease (legitimate presence)
        service_uniforms = [
            c for c in self.clothing_classifications.values() if c.is_service_uniform
        ]
        if service_uniforms:
            modifiers["service_uniform"] = -0.2

        # High-security vehicle damage - major risk increase
        if self.has_high_security_damage:
            modifiers["vehicle_damage_high"] = 0.4
        elif self.has_vehicle_damage:
            modifiers["vehicle_damage"] = 0.15

        # Commercial vehicles during day - slight risk decrease
        if self.has_commercial_vehicles:
            modifiers["commercial_vehicle"] = -0.1

        # Image quality issues - slight uncertainty increase
        if self.has_quality_issues:
            modifiers["quality_issues"] = 0.1
        if self.quality_change_detected:
            modifiers["quality_change"] = 0.2

        return modifiers

    def get_summary_flags(self) -> list[dict[str, str]]:
        """Generate summary flags for the risk assessment output.

        Creates a list of flag dictionaries suitable for inclusion in
        the Nemotron JSON output format.

        Returns:
            List of flag dictionaries with type, description, and severity
        """
        flags: list[dict[str, str]] = []

        # Violence flag
        if self.has_violence:
            assert self.violence_detection is not None
            flags.append(
                {
                    "type": "violence",
                    "description": f"Violence detected ({self.violence_detection.confidence:.0%} confidence)",
                    "severity": "critical",
                }
            )

        # Suspicious attire flags
        for det_id, clothing in self.clothing_classifications.items():
            if clothing.is_suspicious:
                flags.append(
                    {
                        "type": "suspicious_attire",
                        "description": f"Person {det_id}: {clothing.top_category}",
                        "severity": "alert",
                    }
                )

        # Face covering flags from SegFormer
        for det_id, seg in self.clothing_segmentation.items():
            if seg.has_face_covered:
                flags.append(
                    {
                        "type": "face_covered",
                        "description": f"Person {det_id}: Face obscured by hat/sunglasses/scarf",
                        "severity": "alert",
                    }
                )

        # Vehicle damage flags
        for det_id, damage in self.vehicle_damage.items():
            if damage.has_high_security_damage:
                flags.append(
                    {
                        "type": "vehicle_damage",
                        "description": f"Vehicle {det_id}: {', '.join(damage.damage_types)}",
                        "severity": "critical" if damage.has_high_security_damage else "warning",
                    }
                )

        # Quality change flag
        if self.quality_change_detected:
            flags.append(
                {
                    "type": "quality_issue",
                    "description": self.quality_change_description,
                    "severity": "alert",
                }
            )

        return flags

    def get_enrichment_for_detection(self, detection_id: int) -> dict[str, Any] | None:
        """Get enrichment data for a specific detection.

        Aggregates all enrichment results that apply to the given detection ID.
        Returns None if no enrichment data is available for this detection.

        Args:
            detection_id: The detection ID to get enrichment for

        Returns:
            Dictionary with detection-specific enrichment data, or None if no data
        """
        enrichment: dict[str, Any] = {}
        det_id_str = str(detection_id)

        # Vehicle classification
        if det_id_str in self.vehicle_classifications:
            vc = self.vehicle_classifications[det_id_str]
            enrichment["vehicle"] = {
                "type": vc.vehicle_type,
                "color": None,  # Color extraction not implemented in current classifier
                "damage": [],  # Will be filled from vehicle_damage if present
                "confidence": vc.confidence,
            }

        # Vehicle damage
        if det_id_str in self.vehicle_damage:
            vd = self.vehicle_damage[det_id_str]
            if "vehicle" not in enrichment:
                enrichment["vehicle"] = {
                    "type": None,
                    "color": None,
                    "damage": [],
                    "confidence": None,
                }
            enrichment["vehicle"]["damage"] = [
                {"type": d.damage_type, "confidence": d.confidence} for d in vd.detections
            ]

        # Pet classification
        if det_id_str in self.pet_classifications:
            pc = self.pet_classifications[det_id_str]
            enrichment["pet"] = {
                "type": pc.animal_type,
                "breed": None,  # Breed extraction not implemented in current classifier
                "confidence": pc.confidence,
            }

        # Person: clothing classification and segmentation
        if det_id_str in self.clothing_classifications:
            cc = self.clothing_classifications[det_id_str]
            enrichment["person"] = {
                "clothing": cc.top_category,
                "action": None,  # Future: from action recognition
                "carrying": None,  # Future: from pose estimation
                "confidence": cc.confidence,
            }

        # Person: clothing segmentation (adds additional attributes)
        if det_id_str in self.clothing_segmentation:
            cs = self.clothing_segmentation[det_id_str]
            if "person" not in enrichment:
                enrichment["person"] = {
                    "clothing": None,
                    "action": None,
                    "carrying": None,
                    "confidence": None,
                }
            enrichment["person"]["face_covered"] = cs.has_face_covered

        # License plates associated with this detection
        detection_plates = [
            lp for lp in self.license_plates if lp.source_detection_id == detection_id
        ]
        if detection_plates:
            # Take the highest confidence plate
            best_plate = max(detection_plates, key=lambda p: p.ocr_confidence or 0.0)
            enrichment["license_plate"] = {
                "text": best_plate.text,
                "confidence": best_plate.ocr_confidence or best_plate.confidence,
            }

        # Faces associated with this detection
        detection_faces = [f for f in self.faces if f.source_detection_id == detection_id]
        if detection_faces:
            enrichment["face_detected"] = True
            enrichment["face_count"] = len(detection_faces)

        # Shared/global enrichment data (applies to all detections in the batch)
        if self.weather_classification:
            enrichment["weather"] = {
                "condition": self.weather_classification.condition,
                "confidence": self.weather_classification.confidence,
            }

        if self.image_quality:
            enrichment["image_quality"] = {
                "score": self.image_quality.quality_score,
                "issues": list(self.image_quality.quality_issues)
                if self.image_quality.quality_issues
                else [],
            }

        # Return None if no enrichment data was collected
        return enrichment if enrichment else None


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
        weather_classification_enabled: bool = True,
        clothing_classification_enabled: bool = True,
        clothing_segmentation_enabled: bool = True,
        vehicle_damage_detection_enabled: bool = True,
        vehicle_classification_enabled: bool = True,
        image_quality_enabled: bool | None = None,
        pet_classification_enabled: bool = True,
        redis_client: Any | None = None,
        use_enrichment_service: bool = False,
        enrichment_client: EnrichmentClient | None = None,
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
            weather_classification_enabled: Enable SigLIP weather classification (runs on full frame)
            clothing_classification_enabled: Enable FashionCLIP clothing classification
            clothing_segmentation_enabled: Enable SegFormer clothing segmentation
            vehicle_damage_detection_enabled: Enable YOLOv11 vehicle damage detection
            vehicle_classification_enabled: Enable ResNet-50 vehicle type classification
            image_quality_enabled: Enable BRISQUE image quality assessment (CPU-based).
                                   Default None uses settings.image_quality_enabled (False by default
                                   due to pyiqa/NumPy 2.0 incompatibility).
            pet_classification_enabled: Enable pet classification for false positive reduction
            redis_client: Redis client for re-id storage (optional)
            use_enrichment_service: Use HTTP service at ai-enrichment:8094 instead of local models
                                    for vehicle, pet, and clothing classification
            enrichment_client: Optional EnrichmentClient instance (uses global if not provided)
        """
        # Import settings to get image_quality_enabled default
        from backend.core.config import get_settings

        self.model_manager = model_manager or get_model_manager()
        self.min_confidence = min_confidence
        self.license_plate_enabled = license_plate_enabled
        self.face_detection_enabled = face_detection_enabled
        self.ocr_enabled = ocr_enabled
        self.vision_extraction_enabled = vision_extraction_enabled
        self.reid_enabled = reid_enabled
        self.scene_change_enabled = scene_change_enabled
        self.violence_detection_enabled = violence_detection_enabled
        self.weather_classification_enabled = weather_classification_enabled
        self.clothing_classification_enabled = clothing_classification_enabled
        self.clothing_segmentation_enabled = clothing_segmentation_enabled
        self.vehicle_damage_detection_enabled = vehicle_damage_detection_enabled
        self.vehicle_classification_enabled = vehicle_classification_enabled
        # Use config default if not explicitly set (disabled due to pyiqa/NumPy 2.0 incompatibility)
        if image_quality_enabled is None:
            settings = get_settings()
            self.image_quality_enabled = settings.image_quality_enabled
        else:
            self.image_quality_enabled = image_quality_enabled
        self.pet_classification_enabled = pet_classification_enabled
        self._previous_quality_results: dict[str, ImageQualityResult] = {}
        self.redis_client = redis_client

        # Enrichment service settings
        self.use_enrichment_service = use_enrichment_service
        self._enrichment_client = enrichment_client

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
            f"scene_change={scene_change_enabled}, "
            f"use_enrichment_service={use_enrichment_service}"
        )

    def _get_enrichment_client(self) -> EnrichmentClient:
        """Get the enrichment client, creating if needed.

        Returns:
            EnrichmentClient instance
        """
        if self._enrichment_client is None:
            self._enrichment_client = get_enrichment_client()
        return self._enrichment_client

    async def _classify_vehicle_via_service(
        self,
        vehicles: list[DetectionInput],
        image: Image.Image,
    ) -> dict[str, VehicleClassificationResult]:
        """Classify vehicles using the remote enrichment HTTP service.

        Args:
            vehicles: List of vehicle detections to classify
            image: Full frame image to crop vehicles from

        Returns:
            Dictionary mapping detection IDs to VehicleClassificationResult
        """
        results: dict[str, VehicleClassificationResult] = {}

        if not vehicles:
            return results

        client = self._get_enrichment_client()

        for i, vehicle in enumerate(vehicles):
            det_id = str(vehicle.id) if vehicle.id else str(i)

            try:
                # Crop vehicle from full frame
                vehicle_crop = await self._crop_to_bbox(image, vehicle.bbox)
                if vehicle_crop is None:
                    continue

                # Call remote service
                bbox_tuple = vehicle.bbox.to_tuple() if vehicle.bbox else None
                remote_result = await client.classify_vehicle(vehicle_crop, bbox_tuple)

                if remote_result:
                    # Convert remote result to local VehicleClassificationResult

                    results[det_id] = VehicleClassificationResult(
                        vehicle_type=remote_result.vehicle_type,
                        confidence=remote_result.confidence,
                        display_name=remote_result.display_name,
                        is_commercial=remote_result.is_commercial,
                        all_scores=remote_result.all_scores,
                    )

                    logger.debug(
                        f"Vehicle {det_id} type (via service): {remote_result.vehicle_type} "
                        f"({remote_result.confidence:.0%})"
                    )

            except EnrichmentUnavailableError as e:
                logger.warning(f"Enrichment service unavailable for vehicle {det_id}: {e}")
            except Exception as e:
                logger.warning(f"Vehicle classification via service failed for {det_id}: {e}")

        return results

    async def _classify_pets_via_service(
        self,
        animals: list[DetectionInput],
        image: Image.Image,
    ) -> dict[str, PetClassificationResult]:
        """Classify pets using the remote enrichment HTTP service.

        Args:
            animals: List of animal detections to classify
            image: Full frame image to crop animals from

        Returns:
            Dictionary mapping detection IDs to PetClassificationResult
        """
        results: dict[str, PetClassificationResult] = {}

        if not animals:
            return results

        client = self._get_enrichment_client()

        for i, animal in enumerate(animals):
            det_id = str(animal.id) if animal.id else str(i)

            try:
                # Crop animal from full frame
                animal_crop = await self._crop_to_bbox(image, animal.bbox)
                if animal_crop is None:
                    continue

                # Call remote service
                bbox_tuple = animal.bbox.to_tuple() if animal.bbox else None
                remote_result = await client.classify_pet(animal_crop, bbox_tuple)

                if remote_result:
                    # Convert remote result to local PetClassificationResult
                    results[det_id] = PetClassificationResult(
                        animal_type=remote_result.pet_type,
                        confidence=remote_result.confidence,
                        cat_score=0.0,  # Remote service doesn't return raw scores
                        dog_score=0.0,
                        is_household_pet=remote_result.is_household_pet,
                    )

                    logger.debug(
                        f"Animal {det_id} classified (via service) as {remote_result.pet_type} "
                        f"({remote_result.confidence:.0%} confidence)"
                    )

            except EnrichmentUnavailableError as e:
                logger.warning(f"Enrichment service unavailable for animal {det_id}: {e}")
            except Exception as e:
                logger.warning(f"Pet classification via service failed for {det_id}: {e}")

        return results

    async def _classify_clothing_via_service(
        self,
        persons: list[DetectionInput],
        image: Image.Image,
    ) -> dict[str, ClothingClassification]:
        """Classify clothing using the remote enrichment HTTP service.

        Args:
            persons: List of person detections to classify
            image: Full frame image to crop persons from

        Returns:
            Dictionary mapping detection IDs to ClothingClassification
        """
        results: dict[str, ClothingClassification] = {}

        if not persons:
            return results

        client = self._get_enrichment_client()

        for i, person in enumerate(persons):
            det_id = str(person.id) if person.id else str(i)

            try:
                # Crop person from full frame
                person_crop = await self._crop_to_bbox(image, person.bbox)
                if person_crop is None:
                    continue

                # Call remote service
                bbox_tuple = person.bbox.to_tuple() if person.bbox else None
                remote_result = await client.classify_clothing(person_crop, bbox_tuple)

                if remote_result:
                    # Convert remote result to local ClothingClassification
                    results[det_id] = ClothingClassification(
                        top_category=remote_result.top_category,
                        confidence=remote_result.confidence,
                        all_scores={},  # Remote service only returns top category
                        is_suspicious=remote_result.is_suspicious,
                        is_service_uniform=remote_result.is_service_uniform,
                        raw_description=remote_result.description,
                    )

                    logger.debug(
                        f"Person {det_id} clothing (via service): {remote_result.description} "
                        f"({remote_result.confidence:.0%})"
                    )

            except EnrichmentUnavailableError as e:
                logger.warning(f"Enrichment service unavailable for person {det_id}: {e}")
            except Exception as e:
                logger.warning(f"Clothing classification via service failed for {det_id}: {e}")

        return results

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

        # Run weather classification on full frame (environmental context)
        if self.weather_classification_enabled and pil_image:
            try:
                result.weather_classification = await self._classify_weather(pil_image)
            except Exception as e:
                error_msg = f"Weather classification failed: {e}"
                logger.error(error_msg)
                result.errors.append(error_msg)

        # Run clothing classification on person crops
        if self.clothing_classification_enabled and pil_image:
            persons = [d for d in high_conf_detections if d.class_name == PERSON_CLASS]
            if persons:
                try:
                    if self.use_enrichment_service:
                        result.clothing_classifications = await self._classify_clothing_via_service(
                            persons, pil_image
                        )
                    else:
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

        # Run vehicle damage detection on vehicle crops
        if self.vehicle_damage_detection_enabled and pil_image:
            vehicles = [d for d in high_conf_detections if d.class_name in VEHICLE_CLASSES]
            if vehicles:
                try:
                    result.vehicle_damage = await self._detect_vehicle_damage(vehicles, pil_image)
                except Exception as e:
                    error_msg = f"Vehicle damage detection failed: {e}"
                    logger.error(error_msg)
                    result.errors.append(error_msg)

        # Run vehicle segment classification on vehicle crops
        if self.vehicle_classification_enabled and pil_image:
            vehicles = [d for d in high_conf_detections if d.class_name in VEHICLE_CLASSES]
            if vehicles:
                try:
                    if self.use_enrichment_service:
                        result.vehicle_classifications = await self._classify_vehicle_via_service(
                            vehicles, pil_image
                        )
                    else:
                        result.vehicle_classifications = await self._classify_vehicle_types(
                            vehicles, pil_image
                        )
                except Exception as e:
                    error_msg = f"Vehicle classification failed: {e}"
                    logger.error(error_msg)
                    result.errors.append(error_msg)

        # Run BRISQUE image quality assessment (CPU-based, no VRAM)
        if self.image_quality_enabled and pil_image:
            try:
                quality_result = await self._assess_image_quality(pil_image, camera_id)
                result.image_quality = quality_result

                # Check for sudden quality changes (possible tampering)
                if camera_id:
                    previous = self._previous_quality_results.get(camera_id)
                    change_detected, description = detect_quality_change(quality_result, previous)
                    result.quality_change_detected = change_detected
                    result.quality_change_description = description
                    if change_detected:
                        logger.warning(f"Camera {camera_id}: {description}")

                    # Update tracking
                    self._previous_quality_results[camera_id] = quality_result

                # Log if blur detected with person (possible running)
                persons = [d for d in high_conf_detections if d.class_name == PERSON_CLASS]
                if quality_result.is_blurry and persons:
                    blur_context = interpret_blur_with_motion(quality_result, has_person=True)
                    logger.info(f"Motion context: {blur_context}")

            except Exception as e:
                # Model disabled is expected behavior when pyiqa is incompatible
                if "disabled" in str(e).lower():
                    logger.debug(f"Image quality assessment skipped (model disabled): {e}")
                else:
                    error_msg = f"Image quality assessment failed: {e}"
                    logger.error(error_msg)
                    result.errors.append(error_msg)

        # Run pet classification on dog/cat detections for false positive reduction
        if self.pet_classification_enabled and pil_image:
            animals = [d for d in high_conf_detections if d.class_name in ANIMAL_CLASSES]
            if animals:
                try:
                    if self.use_enrichment_service:
                        result.pet_classifications = await self._classify_pets_via_service(
                            animals, pil_image
                        )
                    else:
                        result.pet_classifications = await self._classify_pets(animals, pil_image)
                    if result.pet_only_event:
                        logger.info("Pet-only event detected - can skip Nemotron risk analysis")
                except Exception as e:
                    error_msg = f"Pet classification failed: {e}"
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
            f"clothing_seg={len(result.clothing_segmentation)}, "
            f"vehicle_damage={len(result.vehicle_damage)}, "
            f"vehicle_class={len(result.vehicle_classifications)}, "
            f"pets={len(result.pet_classifications)}, "
            f"quality={'yes' if result.image_quality else 'no'} "
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

        # CLIP model is now accessed via HTTP service (ai-clip)
        # The context manager is kept for compatibility but model is unused
        async with self.model_manager.load("clip-vit-l"):
            for i, det in enumerate(detections):
                det_id = str(det.id) if det.id else str(i)
                entity_type = "person" if det.class_name == PERSON_CLASS else "vehicle"

                if det.class_name not in VEHICLE_CLASSES and det.class_name != PERSON_CLASS:
                    continue

                try:
                    # Generate embedding using ai-clip HTTP service
                    bbox = det.bbox.to_int_tuple() if det.bbox else None
                    embedding = await self._reid_service.generate_embedding(image, bbox=bbox)

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
                record_enrichment_model_call("violence")
                result = await classify_violence(model_data, image)
                # Record semantic metric for enrichment model call
                record_enrichment_model_call("violence-detection")
                if result.is_violent:
                    logger.warning(f"Violence detected with {result.confidence:.0%} confidence")
                return result

        except KeyError as e:
            logger.warning("violence-detection model not available in MODEL_ZOO")
            raise RuntimeError("violence-detection model not configured") from e
        except Exception as e:
            logger.error(f"Violence detection error: {e}")
            raise

    async def _classify_weather(self, image: Image.Image) -> WeatherResult:
        """Run weather classification on a full frame image.

        This method loads the weather classification model, runs inference,
        and returns the classification result. Weather context helps Nemotron
        calibrate risk assessments based on visibility and environmental conditions.

        Args:
            image: PIL Image (full frame) to classify

        Returns:
            WeatherResult with condition and confidence

        Raises:
            RuntimeError: If weather classification fails
        """
        try:
            async with self.model_manager.load("weather-classification") as model_data:
                record_enrichment_model_call("weather")
                result = await classify_weather(model_data, image)
                # Record semantic metric for enrichment model call
                record_enrichment_model_call("weather-classification")
                logger.info(
                    f"Weather classified as {result.simple_condition} "
                    f"({result.confidence:.0%} confidence)"
                )
                return result

        except KeyError as e:
            logger.warning("weather-classification model not available in MODEL_ZOO")
            raise RuntimeError("weather-classification model not configured") from e
        except Exception as e:
            logger.error(f"Weather classification error: {e}")
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
                record_enrichment_model_call("clothing")
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

                        # Record semantic metric for enrichment model call
                        record_enrichment_model_call("fashion-clip")

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

                        # Record semantic metric for enrichment model call
                        record_enrichment_model_call("segformer-b2-clothes")

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

    async def _classify_vehicle_types(
        self,
        vehicles: list[DetectionInput],
        image: Image.Image,
    ) -> dict[str, VehicleClassificationResult]:
        """Classify vehicle types for each vehicle detection using ResNet-50.

        Runs the vehicle segment classification model on vehicle crops to identify
        specific vehicle types (car, pickup_truck, work_van, etc.).

        Args:
            vehicles: List of vehicle detections to classify
            image: Full frame image to crop vehicles from

        Returns:
            Dictionary mapping detection IDs to VehicleClassificationResult
        """
        results: dict[str, VehicleClassificationResult] = {}

        if not vehicles:
            return results

        try:
            async with self.model_manager.load("vehicle-segment-classification") as model_data:
                record_enrichment_model_call("vehicle")
                for i, vehicle in enumerate(vehicles):
                    det_id = str(vehicle.id) if vehicle.id else str(i)

                    try:
                        # Crop vehicle from full frame
                        vehicle_crop = await self._crop_to_bbox(image, vehicle.bbox)
                        if vehicle_crop is None:
                            continue

                        # Classify vehicle type
                        classification = await classify_vehicle(model_data, vehicle_crop)
                        results[det_id] = classification

                        # Record semantic metric for enrichment model call
                        record_enrichment_model_call("vehicle-segment-classification")

                        logger.debug(
                            f"Vehicle {det_id} type: {classification.vehicle_type} "
                            f"({classification.confidence:.0%})"
                        )

                    except Exception as e:
                        logger.warning(f"Vehicle classification failed for vehicle {det_id}: {e}")
                        continue

        except KeyError:
            logger.warning("vehicle-segment-classification model not available in MODEL_ZOO")
        except Exception as e:
            logger.error(f"Vehicle classification error: {e}")

        return results

    async def _detect_vehicle_damage(
        self,
        vehicles: list[DetectionInput],
        image: Image.Image,
    ) -> dict[str, VehicleDamageResult]:
        """Detect damage on vehicle detections using YOLOv11-seg.

        Runs the vehicle damage detection model on vehicle crops to identify:
        - cracks: Surface cracks in paint/body
        - dents: Impact dents on body panels
        - glass_shatter: Broken/shattered glass (HIGH SECURITY)
        - lamp_broken: Damaged headlights/taillights (HIGH SECURITY)
        - scratches: Surface scratches on paint
        - tire_flat: Flat or damaged tires

        Security Value:
        - glass_shatter + lamp_broken at night = suspicious (break-in/vandalism)
        - Fresh damage on parked vehicles = possible hit-and-run or vandalism

        Args:
            vehicles: List of vehicle detections to analyze
            image: Full frame image to crop vehicles from

        Returns:
            Dictionary mapping detection IDs to VehicleDamageResult
        """
        results: dict[str, VehicleDamageResult] = {}

        if not vehicles:
            return results

        try:
            async with self.model_manager.load("vehicle-damage-detection") as model:
                for i, vehicle in enumerate(vehicles):
                    det_id = str(vehicle.id) if vehicle.id else str(i)

                    try:
                        # Crop vehicle from full frame
                        vehicle_crop = await self._crop_to_bbox(image, vehicle.bbox)
                        if vehicle_crop is None:
                            continue

                        # Detect damage
                        damage_result = await detect_vehicle_damage(model, vehicle_crop)
                        results[det_id] = damage_result

                        # Record semantic metric for enrichment model call
                        record_enrichment_model_call("vehicle-damage-detection")

                        if damage_result.has_damage:
                            logger.info(
                                f"Vehicle {det_id} damage detected: "
                                f"types={damage_result.damage_types}, "
                                f"count={damage_result.total_damage_count}, "
                                f"high_security={damage_result.has_high_security_damage}"
                            )

                    except Exception as e:
                        logger.warning(f"Vehicle damage detection failed for vehicle {det_id}: {e}")
                        continue

        except KeyError:
            logger.warning("vehicle-damage-detection model not available in MODEL_ZOO")
        except Exception as e:
            logger.error(f"Vehicle damage detection error: {e}")

        return results

    async def _assess_image_quality(
        self,
        image: Image.Image,
        camera_id: str | None = None,
    ) -> ImageQualityResult:
        """Assess image quality using BRISQUE metric.

        BRISQUE (Blind/Referenceless Image Spatial Quality Evaluator) is a
        no-reference image quality metric that detects blur, noise, and
        other quality degradations.

        Security use cases:
        - Sudden quality drop = possible camera obstruction/tampering
        - High blur + person = fast movement (running)
        - Consistent low quality = camera maintenance needed

        Args:
            image: PIL Image to assess
            camera_id: Camera ID for tracking quality over time

        Returns:
            ImageQualityResult with quality assessment

        Raises:
            RuntimeError: If quality assessment fails
        """
        try:
            async with self.model_manager.load("brisque-quality") as model_data:
                record_enrichment_model_call("brisque")
                result = await assess_image_quality(model_data, image)

                # Record semantic metric for enrichment model call
                record_enrichment_model_call("brisque-quality")

                if result.is_low_quality:
                    camera_str = f" (camera: {camera_id})" if camera_id else ""
                    logger.debug(
                        f"Low quality image detected{camera_str}: "
                        f"score={result.quality_score:.0f}, "
                        f"issues={result.quality_issues}"
                    )

                return result

        except KeyError as e:
            logger.warning("brisque-quality model not available in MODEL_ZOO")
            raise RuntimeError("brisque-quality model not configured") from e
        except RuntimeError as e:
            # Model disabled is expected behavior, log at debug level
            if "disabled" in str(e).lower():
                logger.debug(f"Image quality assessment skipped: {e}")
            else:
                logger.error(f"Image quality assessment error: {e}")
            raise
        except Exception as e:
            logger.error(f"Image quality assessment error: {e}")
            raise

    async def _classify_pets(
        self,
        animals: list[DetectionInput],
        image: Image.Image,
    ) -> dict[str, PetClassificationResult]:
        """Classify pets (dog/cat) for false positive reduction.

        Runs the ResNet-18 pet classifier on animal crop detections to
        distinguish between cats and dogs. High-confidence pet detections
        can be used to skip Nemotron risk analysis for false positive reduction.

        Args:
            animals: List of animal detections (cat/dog classes from RT-DETRv2)
            image: Full frame image to crop animals from

        Returns:
            Dictionary mapping detection IDs to PetClassificationResult
        """
        results: dict[str, PetClassificationResult] = {}

        if not animals:
            return results

        try:
            async with self.model_manager.load("pet-classifier") as model_data:
                record_enrichment_model_call("pet")
                for i, animal in enumerate(animals):
                    det_id = str(animal.id) if animal.id else str(i)

                    try:
                        # Crop animal from full frame
                        animal_crop = await self._crop_to_bbox(image, animal.bbox)
                        if animal_crop is None:
                            continue

                        # Classify pet
                        pet_result = await classify_pet(model_data, animal_crop)
                        results[det_id] = pet_result

                        # Record semantic metric for enrichment model call
                        record_enrichment_model_call("pet-classifier")

                        logger.debug(
                            f"Animal {det_id} classified as {pet_result.animal_type} "
                            f"({pet_result.confidence:.0%} confidence), "
                            f"is_household_pet={pet_result.is_household_pet}"
                        )

                    except Exception as e:
                        logger.warning(f"Pet classification failed for animal {det_id}: {e}")
                        continue

        except KeyError:
            logger.warning("pet-classifier model not available in MODEL_ZOO")
        except Exception as e:
            logger.error(f"Pet classification error: {e}")

        return results


# Global EnrichmentPipeline instance
_enrichment_pipeline: EnrichmentPipeline | None = None


def get_enrichment_pipeline() -> EnrichmentPipeline:
    """Get or create the global EnrichmentPipeline instance.

    The pipeline is initialized with the global Redis client (if available)
    to enable Re-ID functionality for entity tracking.

    Returns:
        Global EnrichmentPipeline instance
    """
    global _enrichment_pipeline  # noqa: PLW0603
    if _enrichment_pipeline is None:
        from backend.core.redis import get_redis_client_sync

        redis_client = get_redis_client_sync()
        _enrichment_pipeline = EnrichmentPipeline(redis_client=redis_client)
    return _enrichment_pipeline


def reset_enrichment_pipeline() -> None:
    """Reset the global EnrichmentPipeline instance (for testing)."""
    global _enrichment_pipeline  # noqa: PLW0603
    _enrichment_pipeline = None
