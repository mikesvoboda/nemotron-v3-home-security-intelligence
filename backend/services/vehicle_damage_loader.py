"""Vehicle damage detection model loader and inference.

This module provides async loading and detection for the YOLOv11 vehicle damage
segmentation model (harpreetsahota/car-dd-segmentation-yolov11 from HuggingFace).

The model detects and segments 6 types of vehicle damage:
- cracks: Surface cracks in paint/body
- dents: Impact dents on body panels
- glass_shatter: Broken/shattered glass
- lamp_broken: Damaged headlights/taillights
- scratches: Surface scratches on paint
- tire_flat: Flat or damaged tires

Security Value:
- glass_shatter + lamp_broken at 3 AM = highly suspicious (potential break-in/vandalism)
- Fresh damage on vehicles parked in driveway = possible hit-and-run or vandalism
- Damaged vehicles arriving = potential stolen/involved in incident

VRAM Usage: ~2GB (yolo11x-seg architecture)
License: AGPL-3.0
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from backend.core.logging import get_logger

if TYPE_CHECKING:
    from PIL import Image

logger = get_logger(__name__)

# Damage classes detected by the model
DAMAGE_CLASSES: list[str] = [
    "crack",
    "dent",
    "glass_shatter",
    "lamp_broken",
    "scratch",
    "tire_flat",
]

# High-security damage types that may indicate vandalism/break-in
HIGH_SECURITY_DAMAGE: frozenset[str] = frozenset(
    {
        "glass_shatter",
        "lamp_broken",
    }
)

# All damage types for reference
ALL_DAMAGE_TYPES: frozenset[str] = frozenset(DAMAGE_CLASSES)


@dataclass(slots=True)
class DamageDetection:
    """Single damage detection result.

    Attributes:
        damage_type: Type of damage detected (from DAMAGE_CLASSES)
        confidence: Detection confidence score (0-1)
        bbox: Bounding box as (x1, y1, x2, y2)
        has_mask: Whether segmentation mask is available
        mask_area: Area of segmentation mask in pixels (if available)
    """

    damage_type: str
    confidence: float
    bbox: tuple[float, float, float, float]
    has_mask: bool = False
    mask_area: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "damage_type": self.damage_type,
            "confidence": self.confidence,
            "bbox": {
                "x1": self.bbox[0],
                "y1": self.bbox[1],
                "x2": self.bbox[2],
                "y2": self.bbox[3],
            },
            "has_mask": self.has_mask,
            "mask_area": self.mask_area,
        }


@dataclass(slots=True)
class VehicleDamageResult:
    """Result from vehicle damage detection.

    Attributes:
        detections: List of detected damage instances
        damage_types: Set of unique damage types detected
        has_high_security_damage: Whether high-security damage types were found
        total_damage_count: Total number of damage instances detected
    """

    detections: list[DamageDetection] = field(default_factory=list)

    @property
    def damage_types(self) -> set[str]:
        """Get set of unique damage types detected."""
        return {d.damage_type for d in self.detections}

    @property
    def has_high_security_damage(self) -> bool:
        """Check if high-security damage types were detected."""
        return bool(self.damage_types & HIGH_SECURITY_DAMAGE)

    @property
    def total_damage_count(self) -> int:
        """Get total number of damage instances."""
        return len(self.detections)

    @property
    def has_damage(self) -> bool:
        """Check if any damage was detected."""
        return len(self.detections) > 0

    @property
    def highest_confidence(self) -> float:
        """Get highest confidence score among detections."""
        if not self.detections:
            return 0.0
        return max(d.confidence for d in self.detections)

    def get_detections_by_type(self, damage_type: str) -> list[DamageDetection]:
        """Get all detections of a specific damage type.

        Args:
            damage_type: Damage type to filter by

        Returns:
            List of detections matching the damage type
        """
        return [d for d in self.detections if d.damage_type == damage_type]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "detections": [d.to_dict() for d in self.detections],
            "damage_types": list(self.damage_types),
            "has_high_security_damage": self.has_high_security_damage,
            "total_damage_count": self.total_damage_count,
            "highest_confidence": self.highest_confidence,
        }

    def to_context_string(self) -> str:
        """Generate context string for LLM prompt.

        Returns:
            Formatted string describing damage detection results
        """
        if not self.has_damage:
            return "No vehicle damage detected."

        lines = [f"Vehicle Damage Detected ({self.total_damage_count} instances):"]

        # Group by damage type
        for dtype in sorted(self.damage_types):
            type_detections = self.get_detections_by_type(dtype)
            avg_conf = sum(d.confidence for d in type_detections) / len(type_detections)
            lines.append(
                f"  - {dtype}: {len(type_detections)} instance(s) (avg conf: {avg_conf:.0%})"
            )

        if self.has_high_security_damage:
            lines.append("  **HIGH SECURITY ALERT**: Suspicious damage types detected")

        return "\n".join(lines)


def _has_meta_tensors(model: Any) -> bool:
    """Check if a model contains meta tensors (lazy-loaded weights).

    Meta tensors are placeholders without actual data, used for lazy weight loading.
    Calling .to(device) on such tensors raises NotImplementedError.

    Args:
        model: PyTorch model to check

    Returns:
        True if any parameter is on the meta device
    """
    try:
        return any(param.device.type == "meta" for param in model.parameters())
    except Exception:
        return False


def _materialize_meta_tensors(model: Any, device: str) -> Any:
    """Materialize meta tensors by using to_empty() + load_state_dict.

    When models are saved with meta tensors (lazy initialization), calling
    model.to(device) raises:
        NotImplementedError: Cannot copy out of meta tensor; no data!

    The fix is to use to_empty() to create empty tensors on the target device,
    then reload the state_dict with assign=True to populate them.

    Args:
        model: Model with potential meta tensors
        device: Target device ("cuda" or "cpu")

    Returns:
        Model with materialized tensors on the target device
    """
    import torch

    logger.info(f"Materializing meta tensors to device: {device}")

    # Get the current state dict before to_empty()
    # We need the actual weights from the checkpoint
    state_dict = model.state_dict()

    # Move model structure to device without copying tensor data
    model = model.to_empty(device=torch.device(device))

    # Reload the state dict with assign=True to populate the empty tensors
    # assign=True replaces parameter tensors in-place rather than copying
    model.load_state_dict(state_dict, assign=True)

    logger.info("Meta tensors materialized successfully")
    return model


async def load_vehicle_damage_model(model_path: str) -> Any:
    """Load the YOLOv11 vehicle damage segmentation model.

    This function loads the YOLO model for vehicle damage detection
    and segmentation. Handles models saved with meta tensors (lazy loading)
    by properly materializing them before use.

    Args:
        model_path: Path to model directory containing best.pt
                   (e.g., "/export/ai_models/model-zoo/vehicle-damage-detection")

    Returns:
        Loaded YOLO model instance

    Raises:
        ImportError: If ultralytics is not installed
        RuntimeError: If model loading fails
    """
    try:
        import torch
        from ultralytics import YOLO

        logger.info(f"Loading vehicle damage detection model from {model_path}")

        loop = asyncio.get_event_loop()

        def _load() -> Any:
            # Construct path to weights file
            weights_path = f"{model_path}/best.pt"

            # Determine target device
            device = "cuda" if torch.cuda.is_available() else "cpu"

            # Load the YOLO model
            model = YOLO(weights_path)

            # Check if model has meta tensors and handle them properly
            # This can happen when models are saved with lazy weight initialization
            if hasattr(model, "model") and _has_meta_tensors(model.model):
                logger.warning(
                    "Model contains meta tensors (lazy-loaded weights). "
                    "Materializing tensors to avoid 'Cannot copy out of meta tensor' error."
                )
                try:
                    model.model = _materialize_meta_tensors(model.model, device)
                except Exception as e:
                    # If materialization fails, try alternative approach:
                    # Force a warmup inference which may trigger proper initialization
                    logger.warning(
                        f"Meta tensor materialization failed: {e}. Trying warmup inference."
                    )
                    try:
                        import numpy as np
                        from PIL import Image as PILImage

                        # Create a small dummy image for warmup
                        dummy_img = PILImage.fromarray(np.zeros((64, 64, 3), dtype=np.uint8))
                        model.predict(source=dummy_img, device=device, verbose=False)
                        logger.info("Model initialized via warmup inference")
                    except Exception as warmup_error:
                        logger.error(f"Warmup inference also failed: {warmup_error}")
                        raise

            logger.info(f"Vehicle damage model loaded: {len(model.names)} classes")
            logger.debug(f"Model classes: {model.names}")

            return model

        model = await loop.run_in_executor(None, _load)

        logger.info(f"Successfully loaded vehicle damage detection model from {model_path}")
        return model

    except ImportError as e:
        logger.warning("ultralytics package not installed. Install with: pip install ultralytics")
        raise ImportError(
            "ultralytics package required for vehicle damage detection. "
            "Install with: pip install ultralytics"
        ) from e

    except Exception as e:
        logger.error(
            "Failed to load vehicle damage detection model",
            exc_info=True,
            extra={"model_path": model_path},
        )
        raise RuntimeError(f"Failed to load vehicle damage detection model: {e}") from e


async def detect_vehicle_damage(
    model: Any,
    image: Image.Image,
    confidence_threshold: float = 0.25,
    iou_threshold: float = 0.45,
) -> VehicleDamageResult:
    """Detect vehicle damage in an image (typically a vehicle crop).

    This function runs the damage detection model on an image and returns
    structured results including damage types, confidence scores, and
    bounding boxes.

    Args:
        model: Loaded YOLO vehicle damage model
        image: PIL Image to analyze (should be a vehicle crop for best results)
        confidence_threshold: Minimum confidence for detections (default: 0.25)
        iou_threshold: IoU threshold for NMS (default: 0.45)

    Returns:
        VehicleDamageResult with all detected damage

    Raises:
        RuntimeError: If detection fails
    """
    try:
        loop = asyncio.get_event_loop()

        def _detect() -> VehicleDamageResult:
            # Determine target device
            try:
                import torch

                device = "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                device = "cpu"

            # Run inference with explicit device parameter to avoid meta tensor issues
            # The device parameter ensures proper tensor initialization and avoids
            # "Cannot copy out of meta tensor" errors when using .to(device)
            results = model.predict(
                source=image,
                conf=confidence_threshold,
                iou=iou_threshold,
                device=device,
                verbose=False,
            )

            detections: list[DamageDetection] = []

            for result in results:
                if result.boxes is None:
                    continue

                boxes = result.boxes

                for i in range(len(boxes)):
                    # Get bounding box coordinates
                    xyxy = boxes.xyxy[i].cpu().numpy()
                    conf = float(boxes.conf[i].cpu().numpy())
                    cls_id = int(boxes.cls[i].cpu().numpy())

                    # Get class name from model
                    raw_class_name = result.names.get(cls_id, f"unknown_{cls_id}")

                    # Normalize class name (handle spaces, case)
                    class_name = _normalize_damage_class(raw_class_name)

                    # Check for segmentation mask
                    has_mask = False
                    mask_area = 0

                    if result.masks is not None and i < len(result.masks):
                        has_mask = True
                        mask = result.masks.data[i].cpu().numpy()
                        mask_area = int(mask.sum())

                    detections.append(
                        DamageDetection(
                            damage_type=class_name,
                            confidence=conf,
                            bbox=(float(xyxy[0]), float(xyxy[1]), float(xyxy[2]), float(xyxy[3])),
                            has_mask=has_mask,
                            mask_area=mask_area,
                        )
                    )

            return VehicleDamageResult(detections=detections)

        result = await loop.run_in_executor(None, _detect)

        if result.has_damage:
            logger.info(
                f"Vehicle damage detected: {result.total_damage_count} instances, "
                f"types: {result.damage_types}, "
                f"high_security: {result.has_high_security_damage}"
            )
        else:
            logger.debug("No vehicle damage detected")

        return result

    except Exception as e:
        logger.error("Vehicle damage detection failed", exc_info=True)
        raise RuntimeError(f"Vehicle damage detection failed: {e}") from e


def _normalize_damage_class(raw_name: str) -> str:
    """Normalize damage class names to consistent format.

    The model may return class names with spaces or different cases.
    This normalizes them to snake_case.

    Args:
        raw_name: Raw class name from model

    Returns:
        Normalized class name (e.g., "glass_shatter")
    """
    # Convert to lowercase and replace spaces with underscores
    normalized = raw_name.lower().strip().replace(" ", "_")

    # Map known variations
    class_mapping = {
        "glass_shatter": "glass_shatter",
        "glass shatter": "glass_shatter",
        "glassshatter": "glass_shatter",
        "lamp_broken": "lamp_broken",
        "lamp broken": "lamp_broken",
        "lampbroken": "lamp_broken",
        "tire_flat": "tire_flat",
        "tire flat": "tire_flat",
        "tireflat": "tire_flat",
        "crack": "crack",
        "cracks": "crack",
        "dent": "dent",
        "dents": "dent",
        "scratch": "scratch",
        "scratches": "scratch",
    }

    return class_mapping.get(normalized, normalized)


def format_damage_context(result: VehicleDamageResult, time_of_day: str | None = None) -> str:
    """Format damage detection result for LLM context.

    Includes additional security context based on time of day and
    damage types detected.

    Args:
        result: VehicleDamageResult to format
        time_of_day: Optional time context ("night", "early_morning", etc.)

    Returns:
        Formatted context string for LLM prompt
    """
    if not result.has_damage:
        return "No vehicle damage detected."

    lines = ["## Vehicle Damage Analysis"]
    lines.append(f"Total damage instances: {result.total_damage_count}")
    lines.append(f"Damage types: {', '.join(sorted(result.damage_types))}")

    if result.has_high_security_damage:
        lines.append("")
        lines.append("**SECURITY ALERT**: High-priority damage detected:")

        # Provide specific context for high-security damage
        if "glass_shatter" in result.damage_types:
            glass_dets = result.get_detections_by_type("glass_shatter")
            max_conf = max(d.confidence for d in glass_dets)
            lines.append(
                f"  - Glass shatter: {len(glass_dets)} instance(s), max conf: {max_conf:.0%}"
            )
            lines.append("    Possible: break-in attempt, vandalism, or collision")

        if "lamp_broken" in result.damage_types:
            lamp_dets = result.get_detections_by_type("lamp_broken")
            max_conf = max(d.confidence for d in lamp_dets)
            lines.append(f"  - Broken lamp: {len(lamp_dets)} instance(s), max conf: {max_conf:.0%}")
            lines.append("    Possible: vandalism, hit-and-run, or deliberate damage")

        # Time-based security escalation
        if time_of_day in ("night", "early_morning", "late_night"):
            lines.append("")
            lines.append(f"**TIME CONTEXT**: Damage detected during {time_of_day}")
            lines.append("  Elevated risk: suspicious activity more likely during these hours")

    # Add detail for each damage type
    lines.append("")
    lines.append("Damage breakdown:")
    for dtype in sorted(result.damage_types):
        dets = result.get_detections_by_type(dtype)
        avg_conf = sum(d.confidence for d in dets) / len(dets)
        lines.append(f"  - {dtype}: {len(dets)} instance(s), avg confidence: {avg_conf:.0%}")

    return "\n".join(lines)


def is_suspicious_damage_pattern(
    result: VehicleDamageResult,
    hour_of_day: int | None = None,
) -> tuple[bool, str]:
    """Determine if damage pattern is suspicious for security purposes.

    Args:
        result: VehicleDamageResult to analyze
        hour_of_day: Hour of day (0-23) when damage was detected

    Returns:
        Tuple of (is_suspicious, reason)
    """
    if not result.has_damage:
        return False, "No damage detected"

    reasons = []

    # High-security damage types are always suspicious
    if result.has_high_security_damage:
        if "glass_shatter" in result.damage_types:
            reasons.append("glass shatter detected (possible break-in)")
        if "lamp_broken" in result.damage_types:
            reasons.append("broken lamp detected (possible vandalism)")

    # Night time + any damage = suspicious
    if hour_of_day is not None:
        is_night = hour_of_day < 6 or hour_of_day >= 22
        if is_night and result.has_damage:
            reasons.append(f"damage detected at night (hour: {hour_of_day})")

    # Multiple damage types = likely incident
    if len(result.damage_types) >= 2:
        reasons.append(f"multiple damage types ({len(result.damage_types)}) suggest incident")

    # High confidence glass shatter + lamp broken = break-in pattern
    if "glass_shatter" in result.damage_types and "lamp_broken" in result.damage_types:
        reasons.append("glass + lamp damage pattern consistent with break-in attempt")

    if reasons:
        return True, "; ".join(reasons)

    return False, "Damage detected but no suspicious patterns"
