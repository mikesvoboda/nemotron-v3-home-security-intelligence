"""Vision extraction service using Florence-2 for attribute extraction.

This module provides comprehensive attribute extraction from security camera feeds
using Florence-2, a vision-language model that supports:
- Vehicle attributes (color, type, commercial status, logos)
- Person attributes (clothing, carried items, actions)
- Scene analysis (unusual objects, tools, abandoned items)
- Environment context (time of day, lighting, weather)

The VisionExtractor calls the ai-florence HTTP service for Florence-2 inference,
which runs as a dedicated service at http://ai-florence:8092. This architecture
improves VRAM management by keeping Florence-2 in a separate container.

NEM-5478: Florence-2 YOLO Cross-Validation
This module implements cross-validation between YOLO detections and Florence-2
descriptions to prevent misclassification (e.g., bus -> police car hallucinations).
"""

from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from backend.core.logging import get_logger
from backend.core.metrics import (
    observe_enrichment_model_duration,
    record_enrichment_model_call,
    record_enrichment_model_error,
)
from backend.core.telemetry import add_span_event
from backend.services.bbox_validation import prepare_bbox_for_crop
from backend.services.florence_client import (
    BoundingBox as FlorenceBoundingBox,
)
from backend.services.florence_client import (
    FlorenceUnavailableError,
    SecurityObjectsResult,
    get_florence_client,
)

if TYPE_CHECKING:
    from PIL import Image

logger = get_logger(__name__)

# =============================================================================
# YOLO-Florence Semantic Equivalence Mapping (NEM-5478)
# =============================================================================
# Maps YOLO detection classes to semantically equivalent Florence descriptions.
# This allows Florence to provide more specific vehicle types while still being
# validated against YOLO's classification.

YOLO_TO_FLORENCE_EQUIVALENCE: dict[str, set[str]] = {
    "car": {"sedan", "coupe", "hatchback", "suv", "crossover", "car", "vehicle"},
    "truck": {"pickup", "truck", "dump truck", "semi-truck", "lorry"},
    "bus": {"bus", "minibus", "shuttle", "coach", "transit"},
    "motorcycle": {"motorcycle", "scooter", "bike", "moped", "motorbike"},
    "bicycle": {"bicycle", "bike", "cycle"},
}

# Confidence thresholds for cross-validation
YOLO_HIGH_CONFIDENCE_THRESHOLD = 0.70  # Above this, YOLO wins on conflict
YOLO_LOW_CONFIDENCE_THRESHOLD = 0.50  # Below this, Florence is trusted more

# Vehicle-related terms for detecting vehicle descriptions in Florence output
VEHICLE_TERMS = frozenset(
    {
        "car",
        "truck",
        "bus",
        "van",
        "suv",
        "sedan",
        "pickup",
        "vehicle",
        "automobile",
        "motorcycle",
        "scooter",
        "bike",
        "bicycle",
        "minivan",
    }
)

# Person-related terms for detecting person descriptions in Florence output
PERSON_TERMS = frozenset(
    {
        "person",
        "man",
        "woman",
        "child",
        "people",
        "individual",
        "pedestrian",
        "walking",
        "standing",
        "wearing",
        "carrying",
    }
)


# =============================================================================
# Cross-Validation Dataclasses (NEM-5478)
# =============================================================================


@dataclass(frozen=True, slots=True)
class ConflictResolutionResult:
    """Result of resolving a YOLO-Florence vehicle type conflict.

    Attributes:
        resolved_type: The final vehicle type to use
        source: Which source was trusted ("yolo", "florence", or "both")
        conflict_detected: Whether a semantic conflict was detected
        yolo_class: Original YOLO detection class
        yolo_confidence: YOLO detection confidence score
        florence_type: Florence-2 described vehicle type
        confidence_note: Optional note about the resolution decision
    """

    resolved_type: str
    source: str  # "yolo", "florence", "both"
    conflict_detected: bool
    yolo_class: str | None
    yolo_confidence: float | None
    florence_type: str | None
    confidence_note: str | None = None


@dataclass(frozen=True, slots=True)
class CrossValidationError:
    """Error detected during YOLO-Florence cross-validation.

    Attributes:
        is_critical: Whether this is a critical error (e.g., person-vehicle mismatch)
        message: Human-readable error message
        yolo_class: YOLO detection class
        yolo_confidence: YOLO detection confidence
        florence_description: Florence-2 description that caused the error
    """

    is_critical: bool
    message: str
    yolo_class: str | None
    yolo_confidence: float | None
    florence_description: str | None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "is_critical": self.is_critical,
            "message": self.message,
            "yolo_class": self.yolo_class,
            "yolo_confidence": self.yolo_confidence,
            "florence_description": self.florence_description,
        }


# =============================================================================
# Cross-Validation Helper Functions (NEM-5478)
# =============================================================================


def is_semantically_equivalent(yolo_class: str, florence_type: str) -> bool:
    """Check if Florence output is semantically equivalent to YOLO class.

    This function determines whether Florence-2's description is consistent
    with what YOLO detected. For example, if YOLO detects 'car' and Florence
    says 'sedan', they are semantically equivalent since a sedan is a type of car.

    Args:
        yolo_class: YOLO detection class (e.g., "car", "bus", "truck")
        florence_type: Florence-2 described type (e.g., "sedan", "police car")

    Returns:
        True if Florence's description is semantically equivalent to YOLO's class,
        False otherwise.

    Examples:
        >>> is_semantically_equivalent("car", "sedan")
        True
        >>> is_semantically_equivalent("bus", "police car")
        False
        >>> is_semantically_equivalent("truck", "pickup")
        True
    """
    if not yolo_class or not florence_type:
        return False

    yolo_lower = yolo_class.lower().strip()
    florence_lower = florence_type.lower().strip()

    # Exact match
    if yolo_lower == florence_lower:
        return True

    # Check equivalence mapping
    equivalents = YOLO_TO_FLORENCE_EQUIVALENCE.get(yolo_lower, set())

    # Direct match in equivalents
    if florence_lower in equivalents:
        return True

    # Check if any equivalent term appears in the Florence description
    # This handles cases like "white sedan" or "blue pickup truck"
    return any(equiv in florence_lower for equiv in equivalents)


def resolve_vehicle_type_conflict(
    yolo_class: str | None,
    yolo_confidence: float | None,
    florence_type: str | None,
) -> ConflictResolutionResult:
    """Resolve conflict between YOLO and Florence vehicle type.

    This function decides which source to trust when YOLO and Florence disagree
    on vehicle type. The decision is based on:
    1. YOLO confidence level
    2. Semantic equivalence between the two descriptions

    Args:
        yolo_class: YOLO detection class (e.g., "bus", "car")
        yolo_confidence: YOLO detection confidence (0.0-1.0)
        florence_type: Florence-2 described vehicle type

    Returns:
        ConflictResolutionResult with the resolved type and decision metadata.

    Examples:
        >>> result = resolve_vehicle_type_conflict("bus", 0.91, "police car")
        >>> result.resolved_type
        'bus'
        >>> result.conflict_detected
        True
    """
    # Handle missing inputs
    if not yolo_class and not florence_type:
        return ConflictResolutionResult(
            resolved_type="unknown",
            source="both",
            conflict_detected=False,
            yolo_class=yolo_class,
            yolo_confidence=yolo_confidence,
            florence_type=florence_type,
            confidence_note="No classification available from either source",
        )

    if not yolo_class:
        return ConflictResolutionResult(
            resolved_type=florence_type or "unknown",
            source="florence",
            conflict_detected=False,
            yolo_class=yolo_class,
            yolo_confidence=yolo_confidence,
            florence_type=florence_type,
            confidence_note="Only Florence classification available",
        )

    if not florence_type:
        return ConflictResolutionResult(
            resolved_type=yolo_class,
            source="yolo",
            conflict_detected=False,
            yolo_class=yolo_class,
            yolo_confidence=yolo_confidence,
            florence_type=florence_type,
            confidence_note="Only YOLO classification available",
        )

    # Check semantic equivalence
    semantically_equivalent = is_semantically_equivalent(yolo_class, florence_type)

    # Get confidence, default to medium if not provided
    confidence = yolo_confidence if yolo_confidence is not None else 0.75

    # If semantically equivalent, prefer Florence for more specific description
    if semantically_equivalent:
        return ConflictResolutionResult(
            resolved_type=florence_type,
            source="florence",
            conflict_detected=False,
            yolo_class=yolo_class,
            yolo_confidence=yolo_confidence,
            florence_type=florence_type,
            confidence_note=f"Semantic match: YOLO '{yolo_class}' matches Florence '{florence_type}'",
        )

    # Semantic mismatch - decide based on confidence
    if confidence >= YOLO_HIGH_CONFIDENCE_THRESHOLD:
        # High confidence YOLO - trust YOLO
        return ConflictResolutionResult(
            resolved_type=yolo_class,
            source="yolo",
            conflict_detected=True,
            yolo_class=yolo_class,
            yolo_confidence=yolo_confidence,
            florence_type=florence_type,
            confidence_note=f"High confidence YOLO ({confidence:.0%}) overrides Florence '{florence_type}'",
        )
    else:
        # Low confidence YOLO - trust Florence
        return ConflictResolutionResult(
            resolved_type=florence_type,
            source="florence",
            conflict_detected=False,
            yolo_class=yolo_class,
            yolo_confidence=yolo_confidence,
            florence_type=florence_type,
            confidence_note=f"Low YOLO confidence ({confidence:.0%}), using Florence '{florence_type}'",
        )


def generate_validation_note(  # noqa: PLR0911
    yolo_class: str | None,
    yolo_confidence: float | None,
    florence_type: str | None,
    resolved_type: str,
    conflict_detected: bool,
) -> str:
    """Generate validation note for Nemotron prompt.

    This function creates a human-readable note explaining how the vehicle type
    was determined through cross-validation.

    Args:
        yolo_class: YOLO detection class
        yolo_confidence: YOLO detection confidence
        florence_type: Florence-2 described type
        resolved_type: Final resolved type
        conflict_detected: Whether a conflict was detected

    Returns:
        Human-readable validation note string.
    """
    confidence_str = f"{yolo_confidence:.0%}" if yolo_confidence is not None else "unknown"

    if conflict_detected:
        # Check for critical person-vehicle mismatch
        yolo_lower = (yolo_class or "").lower()
        florence_lower = (florence_type or "").lower()
        is_person_vehicle_mismatch = (
            yolo_lower == "person" and any(v in florence_lower for v in VEHICLE_TERMS)
        ) or (yolo_lower in VEHICLE_TERMS and "person" in florence_lower)

        if is_person_vehicle_mismatch:
            return (
                f"Cross-validation mismatch error: YOLO detected '{yolo_class}' ({confidence_str} conf), "
                f"but Florence described '{florence_type}'. Resolved to '{resolved_type}'."
            )

        return (
            f"Cross-validation conflict: YOLO detected '{yolo_class}' ({confidence_str} conf), "
            f"Florence described '{florence_type}'. Resolved to '{resolved_type}'."
        )

    if yolo_class and florence_type:
        if is_semantically_equivalent(yolo_class, florence_type):
            return (
                f"Cross-validation confirmed: YOLO '{yolo_class}' ({confidence_str}) "
                f"matches Florence '{florence_type}'."
            )
        else:
            return (
                f"Cross-validation: YOLO '{yolo_class}' ({confidence_str}), "
                f"Florence '{florence_type}'. Using '{resolved_type}'."
            )

    if yolo_class:
        return f"YOLO detected '{yolo_class}' ({confidence_str})."

    if florence_type:
        return f"Florence detected '{florence_type}'."

    return "No cross-validation data available."


def build_vehicle_type_query(yolo_class: str) -> str:
    """Build VQA query that includes YOLO context.

    Including what YOLO detected in the query helps Florence-2 provide a more
    consistent and accurate response.

    Args:
        yolo_class: YOLO detection class

    Returns:
        VQA query string with YOLO context.
    """
    return f"YOLO detected this as: {yolo_class}. What specific type of vehicle is visible?"


def _extract_vehicle_terms(text: str) -> set[str]:
    """Extract vehicle-related terms from text."""
    text_lower = text.lower()
    found = set()
    for term in VEHICLE_TERMS:
        if term in text_lower:
            found.add(term)
    return found


def _extract_person_terms(text: str) -> set[str]:
    """Extract person-related terms from text."""
    text_lower = text.lower()
    found = set()
    for term in PERSON_TERMS:
        if term in text_lower:
            found.add(term)
    return found


def detect_cross_validation_error(
    yolo_class: str | None,
    yolo_confidence: float | None,
    florence_description: str | None,
) -> CrossValidationError | None:
    """Detect critical cross-validation errors.

    This function checks for serious mismatches between YOLO and Florence
    that indicate a fundamental classification error, such as YOLO detecting
    a person but Florence describing a vehicle.

    Args:
        yolo_class: YOLO detection class
        yolo_confidence: YOLO detection confidence
        florence_description: Florence-2 description text

    Returns:
        CrossValidationError if a critical error is detected, None otherwise.
    """
    if not yolo_class or not florence_description:
        return None

    yolo_lower = yolo_class.lower().strip()

    # Check for person-vehicle mismatch
    is_yolo_person = yolo_lower == "person"
    is_yolo_vehicle = yolo_lower in VEHICLE_TERMS or yolo_lower in YOLO_TO_FLORENCE_EQUIVALENCE

    # Extract what Florence describes
    florence_vehicle_terms = _extract_vehicle_terms(florence_description)
    florence_person_terms = _extract_person_terms(florence_description)

    # Person detected by YOLO, but Florence describes a vehicle
    if is_yolo_person and florence_vehicle_terms and not florence_person_terms:
        return CrossValidationError(
            is_critical=True,
            message=(
                f"Person-vehicle mismatch: YOLO detected 'person' ({yolo_confidence:.0%} conf) "
                f"but Florence described vehicle terms: {florence_vehicle_terms}"
            ),
            yolo_class=yolo_class,
            yolo_confidence=yolo_confidence,
            florence_description=florence_description,
        )

    # Vehicle detected by YOLO, but Florence describes a person
    if is_yolo_vehicle and florence_person_terms and not florence_vehicle_terms:
        return CrossValidationError(
            is_critical=True,
            message=(
                f"Vehicle-person mismatch: YOLO detected '{yolo_class}' ({yolo_confidence:.0%} conf) "
                f"but Florence described person terms: {florence_person_terms}"
            ),
            yolo_class=yolo_class,
            yolo_confidence=yolo_confidence,
            florence_description=florence_description,
        )

    return None


# Regex pattern to match Florence-2 location tokens like <loc_123>
# Replace with a space to preserve word boundaries
_LOC_TOKEN_PATTERN = re.compile(r"<loc_\d+>")

# Pattern to match VQA prefix and question up to the first loc token or end
# Handles: "VQA>What tools are visible?A ladder" -> removes "VQA>What tools are visible?"
# The question typically ends with ? followed by the actual answer
_VQA_PREFIX_PATTERN = re.compile(r"^.*?VQA>[^?]*\?", re.IGNORECASE)

# Patterns for validation of VQA output (NEM-3009)
# These patterns indicate garbage output that should be rejected
_GARBAGE_TOKEN_PATTERNS = [
    re.compile(r"<loc_\d+>"),  # Location tokens
    re.compile(r"<poly>", re.IGNORECASE),  # Polygon tokens
    re.compile(r"<pad>", re.IGNORECASE),  # Padding tokens
    re.compile(r"VQA>", re.IGNORECASE),  # VQA prefix artifact
]

# Minimum valid length for a meaningful VQA response
# Single letter outputs like "a" or "-" are considered garbage
_MIN_VALID_LENGTH = 2

# Short valid responses that are accepted despite being short
_VALID_SHORT_RESPONSES = frozenset(
    {"no", "yes", "red", "blue", "green", "white", "black", "gray", "grey", "suv", "van"}
)


def clean_vqa_output(text: str) -> str:
    """Clean Florence-2 VQA output by removing artifacts.

    Florence-2 VQA responses can contain artifacts that leak into downstream
    prompts, including:
    - VQA> prefix with the original question echoed
    - <loc_N> location tokens from the model's spatial encoding
    - Duplicated words like "visible visible" or "etc.) etc.)"

    Args:
        text: Raw VQA output text from Florence-2

    Returns:
        Cleaned text with artifacts removed. Returns empty string if the
        cleaned result would be empty or just whitespace.

    Examples:
        >>> clean_vqa_output("VQA>Are there any unusual objects<loc_1><loc_998>")
        ''
        >>> clean_vqa_output("A ladder against the wall<loc_100><loc_200>")
        'A ladder against the wall'
        >>> clean_vqa_output("tools visible visible (ladder)")
        'tools visible (ladder)'
    """
    if not text:
        return ""

    result = text

    # Remove VQA> prefix and the question (up to and including the ?)
    # This handles cases like "VQA>What tools are visible?A ladder"
    result = _VQA_PREFIX_PATTERN.sub("", result)

    # Also handle case where VQA prefix exists but no question mark follows
    # (the question may have been truncated or not include ?)
    # Remove "VQA>" and any following text that looks like a question
    if "VQA>" in result:
        # Find VQA> and remove everything from start to the first < (loc token)
        vqa_idx = result.find("VQA>")
        if vqa_idx != -1:
            # Find the first < after VQA>, or empty if no loc tokens
            loc_start = result.find("<", vqa_idx)
            result = result[loc_start:] if loc_start != -1 else ""

    # Replace all <loc_N> tokens with spaces to preserve word boundaries
    result = _LOC_TOKEN_PATTERN.sub(" ", result)

    # Remove duplicated consecutive words (case-insensitive)
    # Handles "visible visible", "etc.) etc.)", "the the", etc.
    # Use a function to preserve original case of first occurrence
    def remove_consecutive_duplicates(s: str) -> str:
        words = s.split()
        if len(words) < 2:
            return s

        cleaned_words = [words[0]]
        for i in range(1, len(words)):
            # Compare lowercase versions to catch "Visible visible"
            if words[i].lower() != words[i - 1].lower():
                cleaned_words.append(words[i])

        return " ".join(cleaned_words)

    result = remove_consecutive_duplicates(result)

    # Strip extra whitespace (normalizes multiple spaces to single space)
    result = " ".join(result.split())

    return result.strip()


def is_valid_vqa_output(text: str) -> bool:
    """Validate Florence-2 VQA output for garbage token patterns.

    Florence-2 VQA can return garbage outputs containing location tokens,
    prompt artifacts, or other invalid patterns instead of actual text answers.
    This function detects such garbage outputs.

    NEM-3009: VQA outputs like "VQA>person wearing<loc_95><loc_86><loc_901><loc_918>"
    should be rejected so the system can fall back to scene captioning.

    Args:
        text: VQA output text to validate

    Returns:
        True if the output appears to be valid text, False if it contains
        garbage patterns that indicate a failed VQA response.

    Examples:
        >>> is_valid_vqa_output("dark hoodie and jeans")
        True
        >>> is_valid_vqa_output("<loc_95><loc_86><loc_901><loc_918>")
        False
        >>> is_valid_vqa_output("VQA>person wearing<loc_95>")
        False
    """
    if not text or not text.strip():
        return False

    # Check for garbage token patterns
    for pattern in _GARBAGE_TOKEN_PATTERNS:
        if pattern.search(text):
            return False

    # Check minimum length (unless it's a known valid short response)
    stripped = text.strip().lower()
    return not (len(stripped) < _MIN_VALID_LENGTH and stripped not in _VALID_SHORT_RESPONSES)


def validate_and_clean_vqa_output(text: str) -> str | None:
    """Clean and validate Florence-2 VQA output, returning None if invalid.

    This function combines cleaning (removing artifacts) with validation
    (detecting garbage output). It first validates the raw text for garbage
    patterns - if any are found, the output is rejected entirely. Only clean
    outputs are then processed for artifact removal.

    NEM-3304: When VQA returns output containing <loc_> tokens like
    "sedan<loc_1><loc_2>" or "walking<loc_100>", the entire output should
    be rejected and return None. We do not clean and accept such outputs
    because the presence of location tokens indicates a failed VQA response.

    Args:
        text: Raw VQA output text from Florence-2

    Returns:
        Cleaned text if valid, or None if the output contains garbage tokens.
        Returning None allows callers to implement fallback behavior.

    Examples:
        >>> validate_and_clean_vqa_output("dark hoodie and jeans")
        'dark hoodie and jeans'
        >>> validate_and_clean_vqa_output("sedan<loc_1><loc_2>")
        None
        >>> validate_and_clean_vqa_output("walking<loc_100>")
        None
        >>> validate_and_clean_vqa_output("<loc_95><loc_86><loc_901><loc_918>")
        None
        >>> validate_and_clean_vqa_output("VQA>person wearing<loc_95>")
        None
    """
    if not text:
        return None

    # CRITICAL (NEM-3304): Validate BEFORE cleaning
    # If the original output contains garbage tokens (especially <loc_>),
    # reject it entirely. Do not clean and accept.
    for pattern in _GARBAGE_TOKEN_PATTERNS:
        if pattern.search(text):
            return None

    # Now that we've validated the raw text doesn't contain garbage tokens,
    # clean it to remove other artifacts (whitespace, duplicates, etc.)
    cleaned = clean_vqa_output(text)

    # If cleaning resulted in empty string, it's invalid
    if not cleaned:
        return None

    # Check minimum length
    if len(cleaned) < _MIN_VALID_LENGTH and cleaned.lower() not in _VALID_SHORT_RESPONSES:
        return None

    return cleaned


# Florence-2 task prompts
CAPTION_TASK = "<CAPTION>"
DETAILED_CAPTION_TASK = "<DETAILED_CAPTION>"
MORE_DETAILED_CAPTION_TASK = "<MORE_DETAILED_CAPTION>"
VQA_TASK = "<VQA>"

# =============================================================================
# Detail Level Mapping (NEM-5507/5508/5509)
# =============================================================================
# Maps detail_level parameter to Florence-2 caption tasks.
# - "basic": <CAPTION> - Brief 10-20 word caption
# - "detailed": <DETAILED_CAPTION> - Richer 50-100 word description (default)
# - "more_detailed": <MORE_DETAILED_CAPTION> - Extensive description

DETAIL_LEVEL_TO_TASK: dict[str, str] = {
    "basic": CAPTION_TASK,
    "detailed": DETAILED_CAPTION_TASK,
    "more_detailed": MORE_DETAILED_CAPTION_TASK,
}


@dataclass(frozen=True, slots=True)
class VehicleAttributes:
    """Extracted attributes for a detected vehicle.

    Attributes:
        color: Vehicle color (e.g., "white", "red", "black")
        vehicle_type: Type of vehicle (e.g., "sedan", "SUV", "pickup", "van")
        is_commercial: Whether this appears to be a commercial vehicle
        commercial_text: Visible company name/logo text if commercial
        caption: Full description of the vehicle
        validation_note: Note about YOLO-Florence cross-validation (NEM-5478)
        yolo_class: Original YOLO detection class for reference
        yolo_confidence: Original YOLO detection confidence
    """

    color: str | None
    vehicle_type: str | None
    is_commercial: bool
    commercial_text: str | None
    caption: str
    # Cross-validation fields (NEM-5478)
    validation_note: str | None = None
    yolo_class: str | None = None
    yolo_confidence: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "color": self.color,
            "vehicle_type": self.vehicle_type,
            "is_commercial": self.is_commercial,
            "commercial_text": self.commercial_text,
            "caption": self.caption,
            "validation_note": self.validation_note,
            "yolo_class": self.yolo_class,
            "yolo_confidence": self.yolo_confidence,
        }


@dataclass(frozen=True, slots=True)
class PersonAttributes:
    """Extracted attributes for a detected person.

    Attributes:
        clothing: Description of clothing (e.g., "blue jacket, dark pants")
        carrying: What the person is carrying (e.g., "backpack", "package", "nothing")
        is_service_worker: Whether this appears to be a delivery/service worker
        action: Current action (e.g., "walking", "standing", "crouching")
        caption: Full description of the person
    """

    clothing: str | None
    carrying: str | None
    is_service_worker: bool
    action: str | None
    caption: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "clothing": self.clothing,
            "carrying": self.carrying,
            "is_service_worker": self.is_service_worker,
            "action": self.action,
            "caption": self.caption,
        }


@dataclass(slots=True)
class SceneAnalysis:
    """Analysis of the scene for unusual elements.

    Attributes:
        unusual_objects: List of unusual objects detected
        tools_detected: List of tools visible (ladder, crowbar, etc.)
        abandoned_items: List of abandoned bags/packages
        scene_description: General description of the scene
    """

    unusual_objects: list[str] = field(default_factory=list)
    tools_detected: list[str] = field(default_factory=list)
    abandoned_items: list[str] = field(default_factory=list)
    scene_description: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "unusual_objects": self.unusual_objects,
            "tools_detected": self.tools_detected,
            "abandoned_items": self.abandoned_items,
            "scene_description": self.scene_description,
        }


@dataclass(slots=True)
class FlorenceEnhancedScene:
    """Enhanced scene context from Florence-2 advanced capabilities.

    Aggregates results from security objects detection, dense captioning,
    OCR with regions, phrase grounding, and security VQA queries.
    These feed into the Nemotron prompt via format_florence_scene_context().

    Attributes:
        security_objects: Security-relevant objects detected via open vocabulary
        dense_captions: Per-region descriptions with bounding boxes
        text_regions: OCR text with spatial bounding box regions
        phrase_grounding: Results of phrase grounding for security-relevant phrases
        region_descriptions: Descriptions for YOLO detection regions
        security_vqa: Security-focused VQA answers keyed by detection_id
    """

    security_objects: SecurityObjectsResult | None = None
    dense_captions: list[dict[str, Any]] = field(default_factory=list)
    text_regions: list[dict[str, Any]] = field(default_factory=list)
    phrase_grounding: list[dict[str, Any]] = field(default_factory=list)
    region_descriptions: dict[str, str] = field(default_factory=dict)
    security_vqa: dict[str, dict[str, str]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        security_objs = None
        if self.security_objects:
            security_objs = {
                "labels": [d.label for d in self.security_objects.detections],
                "detections": [
                    {
                        "label": d.label,
                        "bbox": d.bbox,
                        "confidence": d.confidence,
                    }
                    for d in self.security_objects.detections
                ],
                "objects_queried": self.security_objects.objects_queried,
            }
        return {
            "security_objects": security_objs,
            "dense_captions": self.dense_captions,
            "text_regions": {
                "labels": [r.get("text", "") for r in self.text_regions],
                "regions": self.text_regions,
            }
            if self.text_regions
            else None,
            "phrase_grounding": self.phrase_grounding,
            "region_descriptions": self.region_descriptions,
            "security_vqa": self.security_vqa,
        }


@dataclass(slots=True)
class BatchExtractionResult:
    """Result of batch attribute extraction.

    Attributes:
        vehicle_attributes: Dict mapping detection_id to VehicleAttributes
        person_attributes: Dict mapping detection_id to PersonAttributes
        scene_analysis: Scene analysis for the full frame
        environment_context: Environment context for the full frame
        florence_enhanced: Enhanced Florence-2 scene context (security objects,
            dense captions, OCR regions, phrase grounding, region descriptions,
            security VQA)
    """

    vehicle_attributes: dict[str, VehicleAttributes] = field(default_factory=dict)
    person_attributes: dict[str, PersonAttributes] = field(default_factory=dict)
    scene_analysis: SceneAnalysis | None = None
    environment_context: EnvironmentContext | None = None
    florence_enhanced: FlorenceEnhancedScene | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "vehicle_attributes": {
                det_id: attrs.to_dict() for det_id, attrs in self.vehicle_attributes.items()
            },
            "person_attributes": {
                det_id: attrs.to_dict() for det_id, attrs in self.person_attributes.items()
            },
            "scene_analysis": self.scene_analysis.to_dict() if self.scene_analysis else None,
            "environment_context": (
                self.environment_context.to_dict() if self.environment_context else None
            ),
            "florence_enhanced": (
                self.florence_enhanced.to_dict() if self.florence_enhanced else None
            ),
        }


# Vehicle classes from COCO that should trigger vehicle attribute extraction
VEHICLE_CLASSES = frozenset(
    {
        "car",
        "truck",
        "bus",
        "motorcycle",
        "bicycle",
        "vehicle",
    }
)

# Person class
PERSON_CLASS = "person"


@dataclass(frozen=True, slots=True)
class EnvironmentContext:
    """Environmental context from the scene.

    Attributes:
        time_of_day: Estimated time of day ("day", "dusk", "night")
        artificial_light: Whether artificial light source is visible
        weather: Weather conditions if visible
    """

    time_of_day: str
    artificial_light: bool
    weather: str | None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "time_of_day": self.time_of_day,
            "artificial_light": self.artificial_light,
            "weather": self.weather,
        }


# Query templates for Florence-2
VEHICLE_QUERIES = {
    "color": "What color is this vehicle?",
    "type": "What type of vehicle is this? (sedan, SUV, pickup, van, truck, motorcycle)",
    "commercial": "Is this a commercial vehicle? Answer yes or no.",
    "commercial_text": "What company logo or text is visible on this vehicle?",
}

PERSON_QUERIES = {
    "clothing": "What is this person wearing?",
    "carrying": "Is this person carrying anything? If yes, what?",
    "service_worker": "Does this person appear to be a delivery worker or service worker? Answer yes or no.",
    "action": "What is this person doing?",
}

SCENE_QUERIES = {
    "unusual": "Are there any unusual objects in this scene?",
    "tools": "Are there any tools visible? (ladder, crowbar, bolt cutters, etc.)",
    "abandoned": "Are there any abandoned bags or packages?",
}

ENVIRONMENT_QUERIES = {
    "time_of_day": "What time of day does this appear to be based on lighting? (day, dusk, night)",
    "artificial_light": "Is there a flashlight or artificial light source visible? Answer yes or no.",
    "weather": "What are the weather conditions?",
}

# Security-focused VQA queries for threat assessment
# These questions help identify suspicious behavior or potential threats
SECURITY_VQA_QUERIES = {
    "looking_at_camera": "Is this person looking at the camera?",
    "weapons_or_tools": "Are there any weapons or tools visible?",
    "face_covering": "Is this person wearing a mask or face covering?",
    "bags_or_packages": "Are there any bags or packages being carried?",
    "gloves": "Is this person wearing gloves?",
    "interaction_with_property": "Is this person interacting with doors, windows, or locks?",
    "flashlight": "Is this person carrying or using a flashlight?",
    "crouching_or_hiding": "Is this person crouching, hiding, or trying to stay out of view?",
}


class VisionExtractor:
    """Service for extracting visual attributes using Florence-2.

    This service calls the ai-florence HTTP service for Florence-2 inference
    and provides methods for extracting vehicle attributes, person attributes,
    and scene analysis from cropped detection images.

    The ai-florence service runs Florence-2 as a dedicated container, which
    improves VRAM management by keeping the model separate from the backend.

    Usage:
        extractor = VisionExtractor()

        # Extract vehicle attributes
        vehicle = await extractor.extract_vehicle_attributes(
            full_image, bbox=(100, 100, 300, 300)
        )

        # Extract person attributes
        person = await extractor.extract_person_attributes(
            full_image, bbox=(50, 50, 150, 400)
        )

        # Analyze scene
        scene = await extractor.extract_scene_analysis(full_image)
    """

    def __init__(self) -> None:
        """Initialize the VisionExtractor."""
        self._florence_client = get_florence_client()
        logger.info("VisionExtractor initialized with Florence HTTP client")

    async def _query_florence(
        self,
        image: Image.Image,
        task: str,
        text_input: str = "",
    ) -> str:
        """Run a query on Florence-2 via the HTTP service.

        Args:
            image: PIL Image to analyze
            task: Florence-2 task prompt (e.g., "<CAPTION>", "<VQA>")
            text_input: Additional text input for VQA tasks

        Returns:
            Model response as string, or empty string on error
        """
        # Construct the prompt
        prompt = f"{task}{text_input}" if task == VQA_TASK and text_input else task

        try:
            result = await self._florence_client.extract(image, prompt)
            return result
        except FlorenceUnavailableError as e:
            logger.warning(f"Florence service unavailable: {e}")
            return ""

    def _crop_image(self, image: Image.Image, bbox: tuple[int, int, int, int]) -> Image.Image:
        """Crop image to bounding box with padding.

        Handles edge cases such as:
        - Inverted coordinates (x2 < x1 or y2 < y1)
        - Out-of-bounds coordinates
        - Zero-dimension boxes

        Args:
            image: Full PIL Image
            bbox: Bounding box as (x1, y1, x2, y2)

        Returns:
            Cropped PIL Image with 10% padding, or original image if bbox is invalid
        """
        img_width, img_height = image.size

        # Calculate 10% padding based on box dimensions
        # Handle inverted coords by using abs()
        x1, y1, x2, y2 = bbox
        width = abs(x2 - x1)
        height = abs(y2 - y1)
        pad_x = int(width * 0.1) if width > 0 else 0
        pad_y = int(height * 0.1) if height > 0 else 0
        padding = max(pad_x, pad_y)

        # Use safe crop preparation that handles all edge cases
        safe_bbox = prepare_bbox_for_crop(
            bbox,
            image_width=img_width,
            image_height=img_height,
            padding=padding,
            min_size=1,
        )

        if safe_bbox is None:
            logger.warning(
                f"Invalid bounding box {bbox} for image size {img_width}x{img_height}. "
                f"Using full image instead."
            )
            return image

        return image.crop(safe_bbox)

    def _parse_yes_no(self, response: str) -> bool:
        """Parse a yes/no response from Florence-2.

        Args:
            response: Model response text

        Returns:
            True if response indicates yes, False otherwise
        """
        response_lower = response.lower().strip()
        return response_lower.startswith("yes") or "yes" in response_lower[:20]

    def _parse_none_response(self, response: str) -> str | None:
        """Parse response that might indicate nothing/none.

        Args:
            response: Model response text

        Returns:
            Response text or None if indicating nothing
        """
        response_lower = response.lower().strip()
        nothing_indicators = [
            "nothing",
            "none",
            "no ",
            "not carrying",
            "empty",
            "n/a",
            "not visible",
            "cannot see",
            "can't see",
        ]
        for indicator in nothing_indicators:
            if response_lower.startswith(indicator):
                return None
        return response.strip() if response.strip() else None

    async def extract_vehicle_attributes(
        self,
        image: Image.Image,
        bbox: tuple[int, int, int, int] | None = None,
    ) -> VehicleAttributes:
        """Extract attributes from a detected vehicle.

        Args:
            image: Full frame or cropped vehicle image
            bbox: Optional bounding box to crop (x1, y1, x2, y2)

        Returns:
            VehicleAttributes with extracted information

        Note:
            NEM-3009: VQA responses are validated and garbage outputs (containing
            location tokens, VQA> prefix, etc.) are rejected. Invalid outputs
            result in None for that attribute, with the caption providing fallback.
        """
        if bbox is not None:
            image = self._crop_image(image, bbox)

        # Get caption first (used as fallback context when VQA fails)
        caption = await self._query_florence(image, CAPTION_TASK)

        # Query for specific attributes and validate each response (NEM-3009)
        color_raw = await self._query_florence(image, VQA_TASK, VEHICLE_QUERIES["color"])
        vehicle_type_raw = await self._query_florence(image, VQA_TASK, VEHICLE_QUERIES["type"])
        commercial_response = await self._query_florence(
            image, VQA_TASK, VEHICLE_QUERIES["commercial"]
        )

        # Validate VQA responses to reject garbage outputs
        color = validate_and_clean_vqa_output(color_raw)
        vehicle_type = validate_and_clean_vqa_output(vehicle_type_raw)

        is_commercial = self._parse_yes_no(commercial_response)

        commercial_text = None
        if is_commercial:
            commercial_text_raw = await self._query_florence(
                image, VQA_TASK, VEHICLE_QUERIES["commercial_text"]
            )
            commercial_text_clean = validate_and_clean_vqa_output(commercial_text_raw)
            commercial_text = (
                self._parse_none_response(commercial_text_clean) if commercial_text_clean else None
            )

        return VehicleAttributes(
            color=color,
            vehicle_type=vehicle_type,
            is_commercial=is_commercial,
            commercial_text=commercial_text,
            caption=caption,
        )

    async def extract_person_attributes(
        self,
        image: Image.Image,
        bbox: tuple[int, int, int, int] | None = None,
    ) -> PersonAttributes:
        """Extract attributes from a detected person.

        Args:
            image: Full frame or cropped person image
            bbox: Optional bounding box to crop (x1, y1, x2, y2)

        Returns:
            PersonAttributes with extracted information

        Note:
            NEM-3009: VQA responses are validated and garbage outputs (containing
            location tokens, VQA> prefix, etc.) are rejected. Invalid outputs
            result in None for that attribute, with the caption providing fallback.
        """
        if bbox is not None:
            image = self._crop_image(image, bbox)

        # Get caption first (used as fallback context when VQA fails)
        caption = await self._query_florence(image, CAPTION_TASK)

        # Query for specific attributes and validate each response (NEM-3009)
        clothing_raw = await self._query_florence(image, VQA_TASK, PERSON_QUERIES["clothing"])
        carrying_raw = await self._query_florence(image, VQA_TASK, PERSON_QUERIES["carrying"])
        service_response = await self._query_florence(
            image, VQA_TASK, PERSON_QUERIES["service_worker"]
        )
        action_raw = await self._query_florence(image, VQA_TASK, PERSON_QUERIES["action"])

        # Validate VQA responses to reject garbage outputs
        clothing = validate_and_clean_vqa_output(clothing_raw)
        carrying_clean = validate_and_clean_vqa_output(carrying_raw)
        action = validate_and_clean_vqa_output(action_raw)

        return PersonAttributes(
            clothing=clothing,
            carrying=self._parse_none_response(carrying_clean) if carrying_clean else None,
            is_service_worker=self._parse_yes_no(service_response),
            action=action,
            caption=caption,
        )

    async def extract_with_vqa(
        self,
        image: Image.Image,
        questions: list[str],
        bbox: tuple[int, int, int, int] | None = None,
    ) -> dict[str, str]:
        """Ask custom questions about an image using Florence-2 VQA.

        This method allows querying the image with arbitrary security-focused
        questions, returning the model's responses for each question.

        Args:
            image: PIL Image to analyze (full frame or cropped)
            questions: List of questions to ask about the image
            bbox: Optional bounding box to crop (x1, y1, x2, y2)

        Returns:
            Dictionary mapping each question to its answer.
            Empty answers are filtered out.

        Example:
            >>> questions = [
            ...     "Is this person looking at the camera?",
            ...     "Are there any weapons visible?",
            ... ]
            >>> results = await extractor.extract_with_vqa(image, questions)
            >>> # {'Is this person looking at the camera?': 'Yes, directly', ...}
        """
        if bbox is not None:
            image = self._crop_image(image, bbox)

        results: dict[str, str] = {}
        for question in questions:
            answer = await self._query_florence(image, VQA_TASK, question)
            # Only include non-empty answers
            if answer and answer.strip():
                results[question] = answer.strip()

        logger.debug(
            f"VQA extraction completed: {len(results)}/{len(questions)} questions answered"
        )
        return results

    async def extract_security_vqa(
        self,
        image: Image.Image,
        bbox: tuple[int, int, int, int] | None = None,
    ) -> dict[str, str]:
        """Extract security-specific VQA answers using predefined questions.

        This is a convenience method that uses the default security-focused
        questions defined in SECURITY_VQA_QUERIES for threat assessment.

        Args:
            image: PIL Image to analyze
            bbox: Optional bounding box to crop (x1, y1, x2, y2)

        Returns:
            Dictionary mapping security questions to answers
        """
        return await self.extract_with_vqa(image, list(SECURITY_VQA_QUERIES.values()), bbox)

    async def extract_scene_caption(
        self,
        image: Image.Image,
    ) -> str:
        """Extract a detailed scene caption using Florence-2.

        This method uses DETAILED_CAPTION_TASK to generate a richer, more
        comprehensive description of the scene compared to the standard
        CAPTION_TASK. Useful for providing more context to the LLM for
        risk assessment.

        Args:
            image: Full frame image

        Returns:
            Detailed scene description string
        """
        caption = await self._query_florence(image, DETAILED_CAPTION_TASK)
        return caption.strip() if caption else ""

    async def get_scene_caption(
        self,
        image: Image.Image,
        detail_level: str = "detailed",
    ) -> str:
        """Extract scene caption with configurable detail level.

        NEM-5507/5508/5509: Florence Caption Upgrade to DETAILED_CAPTION.

        This method allows callers to specify the detail level for scene
        captioning, mapping to different Florence-2 caption tasks:
        - "basic": <CAPTION> - Brief 10-20 word caption
        - "detailed": <DETAILED_CAPTION> - Richer 50-100 word description (default)
        - "more_detailed": <MORE_DETAILED_CAPTION> - Extensive description

        Args:
            image: Full frame image
            detail_level: Level of detail for caption.
                         One of: "basic", "detailed", "more_detailed"
                         Defaults to "detailed".

        Returns:
            Scene description string at the specified detail level

        Examples:
            >>> # Default detailed caption
            >>> caption = await extractor.get_scene_caption(image)
            >>> # Basic short caption
            >>> caption = await extractor.get_scene_caption(image, detail_level="basic")
            >>> # Most detailed caption
            >>> caption = await extractor.get_scene_caption(image, detail_level="more_detailed")
        """
        # Map detail_level to Florence-2 task, defaulting to detailed
        task = DETAIL_LEVEL_TO_TASK.get(detail_level, DETAILED_CAPTION_TASK)
        caption = await self._query_florence(image, task)
        return caption.strip() if caption else ""

    async def extract_scene_analysis(
        self,
        image: Image.Image,
    ) -> SceneAnalysis:
        """Analyze the full scene for unusual elements.

        Args:
            image: Full frame image

        Returns:
            SceneAnalysis with detected unusual elements
        """
        # Get scene description
        description = await self._query_florence(image, CAPTION_TASK)

        # Query for unusual elements
        unusual_response = await self._query_florence(image, VQA_TASK, SCENE_QUERIES["unusual"])
        tools_response = await self._query_florence(image, VQA_TASK, SCENE_QUERIES["tools"])
        abandoned_response = await self._query_florence(image, VQA_TASK, SCENE_QUERIES["abandoned"])

        # Clean VQA responses to remove Florence-2 artifacts
        unusual_cleaned = clean_vqa_output(unusual_response)
        tools_cleaned = clean_vqa_output(tools_response)
        abandoned_cleaned = clean_vqa_output(abandoned_response)

        # Parse responses into lists
        unusual_objects: list[str] = []
        if unusual_cleaned and not self._is_negative_response(unusual_cleaned):
            unusual_objects = [unusual_cleaned]

        tools_detected: list[str] = []
        if tools_cleaned and not self._is_negative_response(tools_cleaned):
            # Parse comma-separated tools
            tools_detected = [t.strip() for t in tools_cleaned.split(",") if t.strip()]

        abandoned_items: list[str] = []
        if abandoned_cleaned and not self._is_negative_response(abandoned_cleaned):
            abandoned_items = [abandoned_cleaned]

        return SceneAnalysis(
            unusual_objects=unusual_objects,
            tools_detected=tools_detected,
            abandoned_items=abandoned_items,
            scene_description=description,
        )

    async def extract_environment_context(
        self,
        image: Image.Image,
    ) -> EnvironmentContext:
        """Extract environmental context from the scene.

        Args:
            image: Full frame image

        Returns:
            EnvironmentContext with time, lighting, and weather info
        """
        # Run all environment VQA queries concurrently
        time_response, light_response, weather_response = await asyncio.gather(
            self._query_florence(image, VQA_TASK, ENVIRONMENT_QUERIES["time_of_day"]),
            self._query_florence(image, VQA_TASK, ENVIRONMENT_QUERIES["artificial_light"]),
            self._query_florence(image, VQA_TASK, ENVIRONMENT_QUERIES["weather"]),
        )

        # Parse time of day
        time_lower = time_response.lower() if time_response else ""
        if "night" in time_lower:
            time_of_day = "night"
        elif "dusk" in time_lower or "dawn" in time_lower or "evening" in time_lower:
            time_of_day = "dusk"
        else:
            time_of_day = "day"

        return EnvironmentContext(
            time_of_day=time_of_day,
            artificial_light=self._parse_yes_no(light_response),
            weather=self._parse_none_response(weather_response),
        )

    def _is_negative_response(self, response: str) -> bool:
        """Check if response indicates nothing/no/none.

        Args:
            response: Model response text

        Returns:
            True if response is negative
        """
        response_lower = response.lower().strip()
        negative_indicators = [
            "no ",
            "no,",
            "no.",
            "none",
            "nothing",
            "not ",
            "cannot",
            "can't",
            "don't see",
            "do not see",
            "isn't",
            "aren't",
        ]
        return any(response_lower.startswith(indicator) for indicator in negative_indicators)

    async def extract_batch_attributes(
        self,
        image: Image.Image,
        detections: list[dict[str, Any]],
    ) -> BatchExtractionResult:
        """Extract attributes from all detections in a batch.

        This method processes all detections via the ai-florence HTTP service,
        which keeps the Florence-2 model loaded and ready for inference.

        Wires up all Florence-2 capabilities:
        1. Security objects detection (open vocabulary)
        2. Dense captioning (per-region descriptions)
        3. Region description for YOLO detections
        4. OCR with region localization
        5. Phrase grounding for threat validation
        6. Security VQA queries for person detections

        Args:
            image: Full frame image
            detections: List of detection dictionaries with:
                - class_name: Detection class (e.g., "person", "car")
                - bbox: Bounding box as [x1, y1, x2, y2]
                - detection_id: Optional unique ID for the detection

        Returns:
            BatchExtractionResult with all extracted attributes
        """
        result = BatchExtractionResult()

        # Separate detections by type
        vehicle_dets = []
        person_dets = []

        for det in detections:
            class_name = det.get("class_name", "").lower()
            if class_name in VEHICLE_CLASSES:
                vehicle_dets.append(det)
            elif class_name == PERSON_CLASS:
                person_dets.append(det)

        # Extract vehicle attributes with YOLO cross-validation (NEM-5478)
        for det in vehicle_dets:
            bbox = det.get("bbox")
            if bbox:
                bbox = tuple(bbox) if isinstance(bbox, list) else bbox
                cropped = self._crop_image(image, bbox)
            else:
                cropped = image

            # Extract YOLO context for cross-validation
            yolo_class = det.get("class_name", "").lower()
            yolo_confidence = det.get("confidence")

            vehicle_attrs = await self._extract_vehicle_internal(
                cropped,
                yolo_class=yolo_class,
                yolo_confidence=yolo_confidence,
            )
            det_id = det.get("detection_id", str(len(result.vehicle_attributes)))
            result.vehicle_attributes[det_id] = vehicle_attrs

        # Extract person attributes
        for det in person_dets:
            bbox = det.get("bbox")
            if bbox:
                bbox = tuple(bbox) if isinstance(bbox, list) else bbox
                cropped = self._crop_image(image, bbox)
            else:
                cropped = image

            person_attrs = await self._extract_person_internal(cropped)
            det_id = det.get("detection_id", str(len(result.person_attributes)))
            result.person_attributes[det_id] = person_attrs

        # Extract scene analysis (full frame)
        result.scene_analysis = await self._extract_scene_internal(image)

        # Extract environment context (full frame)
        result.environment_context = await self._extract_environment_internal(image)

        # =====================================================================
        # Enhanced Florence-2 Capabilities (parallel scene-level extraction)
        # =====================================================================
        result.florence_enhanced = await self._extract_florence_enhanced(
            image, detections, person_dets
        )

        logger.info(
            f"Extracted attributes: {len(result.vehicle_attributes)} vehicles, "
            f"{len(result.person_attributes)} persons, "
            f"enhanced={result.florence_enhanced is not None}"
        )
        return result

    async def _extract_florence_enhanced(
        self,
        image: Image.Image,
        all_detections: list[dict[str, Any]],
        person_dets: list[dict[str, Any]],
    ) -> FlorenceEnhancedScene | None:
        """Extract enhanced Florence-2 scene context using all available capabilities.

        Runs the following Florence-2 tasks in parallel where possible:
        1. Security objects detection (open vocabulary)
        2. Dense captioning (per-region descriptions)
        3. OCR with region localization
        4. Phrase grounding for security-relevant phrases
        Then sequentially:
        5. Region descriptions for each YOLO detection
        6. Security VQA for person detections

        Args:
            image: Full frame image
            all_detections: All YOLO detections
            person_dets: Person detections for security VQA

        Returns:
            FlorenceEnhancedScene with all enhanced data, or None on total failure
        """
        record_enrichment_model_call("florence-enhanced")
        overall_start = time.perf_counter()
        enhanced = FlorenceEnhancedScene()
        client = self._florence_client

        add_span_event(
            "florence_enhanced.start",
            {"detection.count": len(all_detections), "person.count": len(person_dets)},
        )

        # Security-relevant phrases for phrase grounding
        security_phrases = [
            "person with tool",
            "person near door",
            "suspicious package",
            "person wearing mask",
            "person with weapon",
            "person carrying bag",
        ]

        # Phase 1: Parallel scene-level tasks
        # These are independent and can run concurrently
        async def _detect_security_objects() -> SecurityObjectsResult | None:
            try:
                return await client.detect_security_objects(image)
            except FlorenceUnavailableError:
                logger.warning("Florence security objects detection unavailable")
                return None
            except Exception as e:
                record_enrichment_model_error("florence-security-objects")
                logger.warning(
                    f"Florence security objects detection failed: {e}",
                    extra={"service": "florence-security-objects", "error_type": type(e).__name__},
                )
                return None

        async def _dense_caption() -> list[dict[str, Any]]:
            try:
                regions = await client.dense_caption(image)
                return [{"caption": r.caption, "bbox": r.bbox} for r in regions]
            except FlorenceUnavailableError:
                logger.warning("Florence dense captioning unavailable")
                return []
            except Exception as e:
                record_enrichment_model_error("florence-dense-caption")
                logger.warning(
                    f"Florence dense captioning failed: {e}",
                    extra={"service": "florence-dense-caption", "error_type": type(e).__name__},
                )
                return []

        async def _ocr_with_regions() -> list[dict[str, Any]]:
            try:
                regions = await client.ocr_with_regions(image)
                return [{"text": r.text, "bbox": r.bbox} for r in regions]
            except FlorenceUnavailableError:
                logger.warning("Florence OCR with regions unavailable")
                return []
            except Exception as e:
                record_enrichment_model_error("florence-ocr-regions")
                logger.warning(
                    f"Florence OCR with regions failed: {e}",
                    extra={"service": "florence-ocr-regions", "error_type": type(e).__name__},
                )
                return []

        async def _phrase_grounding() -> list[dict[str, Any]]:
            try:
                grounded = await client.phrase_grounding(image, security_phrases)
                return [
                    {
                        "phrase": g.phrase,
                        "bboxes": g.bboxes,
                        "confidence_scores": g.confidence_scores,
                        "matched": len(g.bboxes) > 0,
                    }
                    for g in grounded
                ]
            except FlorenceUnavailableError:
                logger.warning("Florence phrase grounding unavailable")
                return []
            except Exception as e:
                record_enrichment_model_error("florence-phrase-grounding")
                logger.warning(
                    f"Florence phrase grounding failed: {e}",
                    extra={"service": "florence-phrase-grounding", "error_type": type(e).__name__},
                )
                return []

        # Run all four scene-level tasks in parallel
        (
            security_objects_result,
            dense_captions_result,
            ocr_regions_result,
            phrase_grounding_result,
        ) = await asyncio.gather(
            _detect_security_objects(),
            _dense_caption(),
            _ocr_with_regions(),
            _phrase_grounding(),
        )

        enhanced.security_objects = security_objects_result
        enhanced.dense_captions = dense_captions_result
        enhanced.text_regions = ocr_regions_result
        enhanced.phrase_grounding = phrase_grounding_result

        # Phase 2: Region descriptions for YOLO detections (sequential per detection)
        # Send each detection's bounding box to Florence-2 for a detailed description
        region_boxes = []
        region_det_ids: list[str] = []
        for det in all_detections:
            bbox = det.get("bbox")
            if bbox and len(bbox) == 4:
                x1, y1, x2, y2 = bbox
                # Validate bbox has positive area
                if x2 > x1 and y2 > y1:
                    region_boxes.append(FlorenceBoundingBox(x1=x1, y1=y1, x2=x2, y2=y2))
                    det_id = det.get("detection_id", str(len(region_det_ids)))
                    region_det_ids.append(det_id)

        if region_boxes:
            try:
                descriptions = await client.describe_regions(image, region_boxes)
                for i, desc in enumerate(descriptions):
                    if i < len(region_det_ids) and desc.caption:
                        enhanced.region_descriptions[region_det_ids[i]] = desc.caption
            except FlorenceUnavailableError:
                logger.warning("Florence region description unavailable")
            except Exception as e:
                record_enrichment_model_error("florence-region-description")
                logger.warning(
                    f"Florence region description failed: {e}",
                    extra={
                        "service": "florence-region-description",
                        "error_type": type(e).__name__,
                    },
                )

        # Phase 3: Security VQA for person detections
        for det in person_dets:
            det_id = det.get("detection_id", "")
            if not det_id:
                continue

            bbox = det.get("bbox")
            bbox_tuple = None
            if bbox:
                bbox_tuple = tuple(bbox) if isinstance(bbox, list) else bbox

            try:
                vqa_answers = await self.extract_security_vqa(image, bbox=bbox_tuple)
                if vqa_answers:
                    enhanced.security_vqa[det_id] = vqa_answers
            except Exception as e:
                record_enrichment_model_error("florence-security-vqa")
                logger.warning(
                    f"Security VQA failed for detection {det_id}: {e}",
                    extra={
                        "service": "florence-security-vqa",
                        "detection_id": det_id,
                        "error_type": type(e).__name__,
                    },
                )

        # Check if we got any enhanced data at all
        has_data = (
            enhanced.security_objects is not None
            or enhanced.dense_captions
            or enhanced.text_regions
            or enhanced.phrase_grounding
            or enhanced.region_descriptions
            or enhanced.security_vqa
        )

        overall_duration = time.perf_counter() - overall_start
        observe_enrichment_model_duration("florence-enhanced", overall_duration)

        if not has_data:
            record_enrichment_model_error("florence-enhanced")
            logger.debug(
                "No Florence enhanced data available",
                extra={"service": "florence-enhanced", "duration_ms": int(overall_duration * 1000)},
            )
            return None

        security_obj_count = (
            len(enhanced.security_objects.detections) if enhanced.security_objects else 0
        )
        phrase_match_count = sum(1 for p in enhanced.phrase_grounding if p.get("matched"))

        add_span_event(
            "florence_enhanced.complete",
            {
                "security_objects.count": security_obj_count,
                "dense_captions.count": len(enhanced.dense_captions),
                "text_regions.count": len(enhanced.text_regions),
                "phrase_grounding.matched": phrase_match_count,
                "region_descriptions.count": len(enhanced.region_descriptions),
                "security_vqa.count": len(enhanced.security_vqa),
                "duration_ms": int(overall_duration * 1000),
            },
        )

        logger.info(
            f"Florence enhanced: "
            f"security_objects={security_obj_count}, "
            f"dense_captions={len(enhanced.dense_captions)}, "
            f"text_regions={len(enhanced.text_regions)}, "
            f"phrase_grounding={phrase_match_count}, "
            f"region_descriptions={len(enhanced.region_descriptions)}, "
            f"security_vqa={len(enhanced.security_vqa)}",
            extra={"service": "florence-enhanced", "duration_ms": int(overall_duration * 1000)},
        )
        return enhanced

    async def _extract_vehicle_internal(
        self,
        image: Image.Image,
        yolo_class: str | None = None,
        yolo_confidence: float | None = None,
    ) -> VehicleAttributes:
        """Extract vehicle attributes via HTTP service with YOLO cross-validation.

        Args:
            image: Cropped vehicle image
            yolo_class: YOLO detection class for cross-validation (NEM-5478)
            yolo_confidence: YOLO detection confidence for cross-validation

        Returns:
            VehicleAttributes with extracted information and validation metadata

        Note:
            NEM-3304: VQA responses are validated to reject garbage outputs
            containing <loc_> tokens or VQA> prefix artifacts.

            NEM-5478: Florence vehicle type is cross-validated against YOLO
            detection to prevent misclassification (e.g., bus -> police car).
        """
        # Run all vehicle VQA queries concurrently
        caption, color_raw, vehicle_type_raw, commercial_response = await asyncio.gather(
            self._query_florence(image, CAPTION_TASK),
            self._query_florence(image, VQA_TASK, VEHICLE_QUERIES["color"]),
            self._query_florence(image, VQA_TASK, VEHICLE_QUERIES["type"]),
            self._query_florence(image, VQA_TASK, VEHICLE_QUERIES["commercial"]),
        )

        # Validate VQA responses to reject garbage outputs (NEM-3304)
        color = validate_and_clean_vqa_output(color_raw)
        florence_vehicle_type = validate_and_clean_vqa_output(vehicle_type_raw)

        is_commercial = self._parse_yes_no(commercial_response)

        commercial_text = None
        if is_commercial:
            commercial_text_raw = await self._query_florence(
                image, VQA_TASK, VEHICLE_QUERIES["commercial_text"]
            )
            commercial_text_clean = validate_and_clean_vqa_output(commercial_text_raw)
            commercial_text = (
                self._parse_none_response(commercial_text_clean) if commercial_text_clean else None
            )

        # Cross-validate Florence vehicle type against YOLO detection (NEM-5478)
        validation_note: str | None = None
        resolved_vehicle_type = florence_vehicle_type

        if yolo_class:
            # Perform cross-validation
            resolution = resolve_vehicle_type_conflict(
                yolo_class=yolo_class,
                yolo_confidence=yolo_confidence,
                florence_type=florence_vehicle_type,
            )
            resolved_vehicle_type = resolution.resolved_type
            validation_note = generate_validation_note(
                yolo_class=yolo_class,
                yolo_confidence=yolo_confidence,
                florence_type=florence_vehicle_type,
                resolved_type=resolved_vehicle_type,
                conflict_detected=resolution.conflict_detected,
            )

            if resolution.conflict_detected:
                logger.warning(
                    f"YOLO-Florence conflict detected: YOLO={yolo_class} ({yolo_confidence}), "
                    f"Florence={florence_vehicle_type}, resolved to {resolved_vehicle_type}"
                )

        return VehicleAttributes(
            color=color,
            vehicle_type=resolved_vehicle_type,
            is_commercial=is_commercial,
            commercial_text=commercial_text,
            caption=caption,
            validation_note=validation_note,
            yolo_class=yolo_class,
            yolo_confidence=yolo_confidence,
        )

    async def _extract_person_internal(
        self,
        image: Image.Image,
    ) -> PersonAttributes:
        """Extract person attributes via HTTP service.

        Args:
            image: Cropped person image

        Returns:
            PersonAttributes with extracted information

        Note:
            NEM-3304: VQA responses are validated to reject garbage outputs
            like "VQA>person wearing<loc_95><loc_86><loc_901><loc_918>".
        """
        # Run all person VQA queries concurrently
        caption, clothing_raw, carrying_raw, service_response, action_raw = await asyncio.gather(
            self._query_florence(image, CAPTION_TASK),
            self._query_florence(image, VQA_TASK, PERSON_QUERIES["clothing"]),
            self._query_florence(image, VQA_TASK, PERSON_QUERIES["carrying"]),
            self._query_florence(image, VQA_TASK, PERSON_QUERIES["service_worker"]),
            self._query_florence(image, VQA_TASK, PERSON_QUERIES["action"]),
        )

        # Validate VQA responses to reject garbage outputs (NEM-3304)
        clothing = validate_and_clean_vqa_output(clothing_raw)
        carrying_clean = validate_and_clean_vqa_output(carrying_raw)
        action = validate_and_clean_vqa_output(action_raw)

        return PersonAttributes(
            clothing=clothing,
            carrying=self._parse_none_response(carrying_clean) if carrying_clean else None,
            is_service_worker=self._parse_yes_no(service_response),
            action=action,
            caption=caption,
        )

    async def _extract_scene_internal(
        self,
        image: Image.Image,
    ) -> SceneAnalysis:
        """Extract scene analysis via HTTP service.

        Args:
            image: Full frame image

        Returns:
            SceneAnalysis with detected unusual elements
        """
        # Run all scene VQA queries concurrently
        description, unusual_response, tools_response, abandoned_response = await asyncio.gather(
            self._query_florence(image, CAPTION_TASK),
            self._query_florence(image, VQA_TASK, SCENE_QUERIES["unusual"]),
            self._query_florence(image, VQA_TASK, SCENE_QUERIES["tools"]),
            self._query_florence(image, VQA_TASK, SCENE_QUERIES["abandoned"]),
        )

        # Clean VQA responses to remove Florence-2 artifacts
        unusual_cleaned = clean_vqa_output(unusual_response)
        tools_cleaned = clean_vqa_output(tools_response)
        abandoned_cleaned = clean_vqa_output(abandoned_response)

        unusual_objects: list[str] = []
        if unusual_cleaned and not self._is_negative_response(unusual_cleaned):
            unusual_objects = [unusual_cleaned]

        tools_detected: list[str] = []
        if tools_cleaned and not self._is_negative_response(tools_cleaned):
            tools_detected = [t.strip() for t in tools_cleaned.split(",") if t.strip()]

        abandoned_items: list[str] = []
        if abandoned_cleaned and not self._is_negative_response(abandoned_cleaned):
            abandoned_items = [abandoned_cleaned]

        return SceneAnalysis(
            unusual_objects=unusual_objects,
            tools_detected=tools_detected,
            abandoned_items=abandoned_items,
            scene_description=description,
        )

    async def _extract_environment_internal(
        self,
        image: Image.Image,
    ) -> EnvironmentContext:
        """Extract environment context via HTTP service.

        Args:
            image: Full frame image

        Returns:
            EnvironmentContext with time, lighting, and weather info
        """
        time_response = await self._query_florence(
            image, VQA_TASK, ENVIRONMENT_QUERIES["time_of_day"]
        )
        light_response = await self._query_florence(
            image, VQA_TASK, ENVIRONMENT_QUERIES["artificial_light"]
        )
        weather_response = await self._query_florence(
            image, VQA_TASK, ENVIRONMENT_QUERIES["weather"]
        )

        time_lower = time_response.lower() if time_response else ""
        if "night" in time_lower:
            time_of_day = "night"
        elif "dusk" in time_lower or "dawn" in time_lower or "evening" in time_lower:
            time_of_day = "dusk"
        else:
            time_of_day = "day"

        return EnvironmentContext(
            time_of_day=time_of_day,
            artificial_light=self._parse_yes_no(light_response),
            weather=self._parse_none_response(weather_response),
        )


# Global service instance
_vision_extractor: VisionExtractor | None = None


def get_vision_extractor() -> VisionExtractor:
    """Get or create the global VisionExtractor instance.

    Returns:
        Global VisionExtractor instance
    """
    global _vision_extractor  # noqa: PLW0603
    if _vision_extractor is None:
        _vision_extractor = VisionExtractor()
    return _vision_extractor


def reset_vision_extractor() -> None:
    """Reset the global VisionExtractor instance (for testing)."""
    global _vision_extractor  # noqa: PLW0603
    _vision_extractor = None


# ============================================================================
# Prompt Formatting Functions
# ============================================================================


def format_vehicle_attributes(
    attrs: VehicleAttributes,
    detection_id: str | None = None,
) -> str:
    """Format vehicle attributes for prompt inclusion.

    Args:
        attrs: VehicleAttributes to format
        detection_id: Optional detection ID prefix

    Returns:
        Formatted string for prompt
    """
    lines = []
    prefix = f"[{detection_id}] " if detection_id else ""

    # Start with caption
    lines.append(f"{prefix}Vehicle: {attrs.caption}")

    # Add specific attributes
    details = []
    if attrs.color:
        details.append(f"Color: {attrs.color}")
    if attrs.vehicle_type:
        details.append(f"Type: {attrs.vehicle_type}")
    if attrs.is_commercial:
        commercial_desc = "Commercial vehicle"
        if attrs.commercial_text:
            commercial_desc += f" ({attrs.commercial_text})"
        details.append(commercial_desc)

    if details:
        lines.append(f"  {', '.join(details)}")

    return "\n".join(lines)


def format_person_attributes(
    attrs: PersonAttributes,
    detection_id: str | None = None,
) -> str:
    """Format person attributes for prompt inclusion.

    Args:
        attrs: PersonAttributes to format
        detection_id: Optional detection ID prefix

    Returns:
        Formatted string for prompt
    """
    lines = []
    prefix = f"[{detection_id}] " if detection_id else ""

    # Start with caption
    lines.append(f"{prefix}Person: {attrs.caption}")

    # Add specific attributes
    details = []
    if attrs.clothing:
        details.append(f"Wearing: {attrs.clothing}")
    if attrs.carrying:
        details.append(f"Carrying: {attrs.carrying}")
    if attrs.action:
        details.append(f"Action: {attrs.action}")
    if attrs.is_service_worker:
        details.append("Appears to be service/delivery worker")

    if details:
        lines.append(f"  {', '.join(details)}")

    return "\n".join(lines)


def format_scene_analysis(scene: SceneAnalysis) -> str:
    """Format scene analysis for prompt inclusion.

    Args:
        scene: SceneAnalysis to format

    Returns:
        Formatted string for prompt
    """
    lines = []

    if scene.scene_description:
        lines.append(f"Scene: {scene.scene_description}")

    if scene.unusual_objects:
        lines.append(f"Unusual objects: {', '.join(scene.unusual_objects)}")

    if scene.tools_detected:
        lines.append(f"Tools detected: {', '.join(scene.tools_detected)}")

    if scene.abandoned_items:
        lines.append(f"Abandoned items: {', '.join(scene.abandoned_items)}")

    if not lines:
        return "No notable scene elements detected."

    return "\n".join(lines)


def format_environment_context(env: EnvironmentContext) -> str:
    """Format environment context for prompt inclusion.

    Args:
        env: EnvironmentContext to format

    Returns:
        Formatted string for prompt
    """
    parts = [f"Time of day: {env.time_of_day}"]

    if env.artificial_light:
        parts.append("Artificial light source detected")

    if env.weather:
        parts.append(f"Weather: {env.weather}")

    return ", ".join(parts)


def format_batch_extraction_result(
    result: BatchExtractionResult,
    include_scene: bool = True,
    include_environment: bool = True,
) -> str:
    """Format a complete batch extraction result for prompt inclusion.

    Args:
        result: BatchExtractionResult to format
        include_scene: Whether to include scene analysis
        include_environment: Whether to include environment context

    Returns:
        Formatted string for prompt
    """
    from backend.services.prompts import format_florence_scene_context

    sections = []

    # Format vehicle attributes
    if result.vehicle_attributes:
        vehicle_lines = ["## Vehicles"]
        for det_id, vehicle_attrs in result.vehicle_attributes.items():
            vehicle_lines.append(format_vehicle_attributes(vehicle_attrs, det_id))
        sections.append("\n".join(vehicle_lines))

    # Format person attributes
    if result.person_attributes:
        person_lines = ["## Persons"]
        for det_id, person_attrs in result.person_attributes.items():
            person_lines.append(format_person_attributes(person_attrs, det_id))
        sections.append("\n".join(person_lines))

    # Format scene analysis
    if include_scene and result.scene_analysis:
        scene_section = "## Scene Analysis\n" + format_scene_analysis(result.scene_analysis)
        sections.append(scene_section)

    # Format environment context
    if include_environment and result.environment_context:
        env_section = "## Environment\n" + format_environment_context(result.environment_context)
        sections.append(env_section)

    # Format Florence-2 enhanced scene context
    if result.florence_enhanced:
        enhanced_dict = result.florence_enhanced.to_dict()
        enhanced_str = format_florence_scene_context(enhanced_dict)
        if enhanced_str:
            sections.append(enhanced_str)

    if not sections:
        return "No vision extraction data available."

    return "\n\n".join(sections)


def format_detections_with_attributes(
    detections: list[dict[str, Any]],
    result: BatchExtractionResult,
) -> str:
    """Format detections list with vision extraction attributes inline.

    This creates a combined view of detections with their extracted attributes
    for use in the Nemotron prompt's detection section.

    Args:
        detections: List of detection dicts with class_name, confidence, bbox, detection_id
        result: BatchExtractionResult with extracted attributes

    Returns:
        Formatted string with detections and their attributes
    """
    lines = []

    for det in detections:
        det_id = det.get("detection_id", "")
        class_name = det.get("class_name", "unknown")
        confidence = det.get("confidence", 0.0)
        bbox = det.get("bbox", [])

        # Base detection info
        bbox_str = f"[{', '.join(str(int(b)) for b in bbox)}]" if bbox else "[]"
        base_line = f"- {class_name} ({confidence:.0%}) at {bbox_str}"

        # Add attributes if available
        if det_id in result.vehicle_attributes:
            vehicle_attrs = result.vehicle_attributes[det_id]
            attr_parts = []
            if vehicle_attrs.color:
                attr_parts.append(vehicle_attrs.color)
            if vehicle_attrs.vehicle_type:
                attr_parts.append(vehicle_attrs.vehicle_type)
            if vehicle_attrs.is_commercial:
                commercial = "commercial"
                if vehicle_attrs.commercial_text:
                    commercial = f"commercial: {vehicle_attrs.commercial_text}"
                attr_parts.append(commercial)
            if attr_parts:
                base_line += f" [{', '.join(attr_parts)}]"

        elif det_id in result.person_attributes:
            person_attrs = result.person_attributes[det_id]
            attr_parts = []
            if person_attrs.clothing:
                attr_parts.append(person_attrs.clothing)
            if person_attrs.carrying:
                attr_parts.append(f"carrying {person_attrs.carrying}")
            if person_attrs.action:
                attr_parts.append(person_attrs.action)
            if person_attrs.is_service_worker:
                attr_parts.append("service worker")
            if attr_parts:
                base_line += f" [{', '.join(attr_parts)}]"

        lines.append(base_line)

    if not lines:
        return "No detections."

    return "\n".join(lines)
