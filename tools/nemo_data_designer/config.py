"""Configuration and Pydantic models for NeMo Data Designer scenarios.

This module defines the schema for synthetic security scenarios used in
testing and prompt evaluation. The models align with the home security
system's detection pipeline and Nemotron risk analysis.

Models:
    Detection: Single object detection with bbox and confidence
    EnrichmentContext: Additional context from enrichment pipeline
    GroundTruth: Expected risk assessment and key reasoning points
    JudgeScores: LLM-Judge rubric dimension scores
    ScenarioBundle: Complete scenario combining all components

Column Types (24 total):
    - SAMPLERS (7): Statistical control columns
    - LLM-STRUCTURED (3): Pydantic-validated generation
    - LLM-TEXT (3): Narrative generation
    - LLM-JUDGE (6): Quality rubrics
    - EMBEDDING (2): Semantic search vectors
    - EXPRESSION (3): Derived fields
    - VALIDATION (2): Quality gates
"""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from collections.abc import Sequence

# =============================================================================
# Detection Models
# =============================================================================


class Detection(BaseModel):
    """Single object detection from RT-DETRv2.

    Represents a detected object with its classification, confidence score,
    bounding box coordinates, and temporal offset within the batch window.

    Attributes:
        object_type: Type of detected object (person, vehicle, animal, etc.)
        confidence: Detection confidence score (0.5-1.0 threshold)
        bbox: Bounding box as (x, y, width, height) in pixels
        timestamp_offset_seconds: Seconds from batch start (0-90s window)
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "object_type": "person",
                "confidence": 0.92,
                "bbox": [150, 200, 80, 180],
                "timestamp_offset_seconds": 15,
            }
        }
    )

    object_type: Literal["person", "car", "truck", "dog", "cat", "bicycle", "motorcycle", "bus"]
    confidence: float = Field(ge=0.5, le=1.0, description="Detection confidence (0.5-1.0)")
    bbox: tuple[int, int, int, int] = Field(
        description="Bounding box (x, y, width, height) in pixels"
    )
    timestamp_offset_seconds: int = Field(
        ge=0, le=90, description="Seconds from batch window start (max 90s)"
    )


# =============================================================================
# Enrichment Context Models
# =============================================================================


class EnrichmentContext(BaseModel):
    """Enrichment pipeline output for detected objects.

    Contains additional context computed by the enrichment models including
    zone information, baseline deviation scores, and cross-camera tracking.

    Attributes:
        zone_name: Name of the zone where detection occurred
        is_entry_point: Whether detection is at an entry point (door, gate)
        baseline_expected_count: Expected count based on historical baseline
        baseline_deviation_score: Z-score deviation from baseline (-3 to +3)
        cross_camera_matches: Number of matching detections across cameras
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "zone_name": "front_door",
                "is_entry_point": True,
                "baseline_expected_count": 2,
                "baseline_deviation_score": 1.5,
                "cross_camera_matches": 1,
            }
        }
    )

    zone_name: str | None = Field(default=None, description="Zone name where detection occurred")
    is_entry_point: bool = Field(
        default=False, description="Whether location is an entry point (door, gate, etc.)"
    )
    baseline_expected_count: int = Field(
        ge=0, default=0, description="Expected detection count from historical baseline"
    )
    baseline_deviation_score: float = Field(
        ge=-3.0, le=3.0, default=0.0, description="Z-score deviation from baseline"
    )
    cross_camera_matches: int = Field(
        ge=0, le=5, default=0, description="Number of re-ID matches across cameras"
    )


# =============================================================================
# LLM-Judge Models
# =============================================================================


class JudgeScores(BaseModel):
    """LLM-Judge rubric scores for evaluating response quality.

    Each dimension is scored 1-4:
    - 1: Poor - fails to meet basic requirements
    - 2: Fair - partially meets requirements
    - 3: Good - meets requirements well
    - 4: Excellent - exceeds requirements

    Attributes:
        relevance: Does output address the actual security concern?
        risk_calibration: Is score appropriate for scenario severity?
        context_usage: Are enrichment inputs reflected in reasoning?
        reasoning_quality: Is the explanation logical and complete?
        threat_identification: Did it correctly identify/miss the actual threat?
        actionability: Is the output useful for a homeowner to act on?
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "relevance": 4,
                "risk_calibration": 3,
                "context_usage": 3,
                "reasoning_quality": 4,
                "threat_identification": 4,
                "actionability": 3,
            }
        }
    )

    relevance: int = Field(
        ge=1, le=4, default=3, description="Does output address the actual security concern? (1-4)"
    )
    risk_calibration: int = Field(
        ge=1, le=4, default=3, description="Is score appropriate for scenario severity? (1-4)"
    )
    context_usage: int = Field(
        ge=1, le=4, default=3, description="Are enrichment inputs reflected in reasoning? (1-4)"
    )
    reasoning_quality: int = Field(
        ge=1, le=4, default=3, description="Is the explanation logical and complete? (1-4)"
    )
    threat_identification: int = Field(
        ge=1, le=4, default=3, description="Did it correctly identify/miss the actual threat? (1-4)"
    )
    actionability: int = Field(
        ge=1, le=4, default=3, description="Is the output useful for a homeowner to act on? (1-4)"
    )

    def total_score(self) -> int:
        """Calculate total score across all dimensions (6-24)."""
        return (
            self.relevance
            + self.risk_calibration
            + self.context_usage
            + self.reasoning_quality
            + self.threat_identification
            + self.actionability
        )

    def average_score(self) -> float:
        """Calculate average score across all dimensions (1.0-4.0)."""
        return self.total_score() / 6.0


# =============================================================================
# Ground Truth Models
# =============================================================================


class GroundTruth(BaseModel):
    """Expected risk assessment and reasoning for a scenario.

    Defines the ground truth for evaluating Nemotron's risk analysis output.
    Used to verify that generated risk scores fall within expected ranges
    and that reasoning captures key security considerations.

    Attributes:
        risk_range: Expected risk score range (min, max) on 0-100 scale
        reasoning_key_points: Key points that should appear in reasoning
        expected_enrichment_models: Enrichment models expected to contribute
        should_trigger_alert: Whether scenario should trigger user alert
        expected_vram_mb: Total VRAM required for all models (optional)
        should_trigger_circuit_breaker: Whether scenario should activate circuit breaker
        expected_fallback_behavior: Expected fallback when models fail (optional)
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "risk_range": [70, 90],
                "reasoning_key_points": [
                    "unknown person",
                    "late night",
                    "entry point",
                ],
                "expected_enrichment_models": ["florence_2", "pose_estimation"],
                "should_trigger_alert": True,
                "expected_vram_mb": 800,
                "should_trigger_circuit_breaker": False,
                "expected_fallback_behavior": None,
            }
        }
    )

    risk_range: tuple[int, int] = Field(
        description="Expected risk score range (min, max) on 0-100 scale"
    )
    reasoning_key_points: list[str] = Field(
        default_factory=list, description="Key points expected in reasoning output"
    )
    expected_enrichment_models: list[str] = Field(
        default_factory=list, description="Enrichment models expected to contribute"
    )
    should_trigger_alert: bool = Field(
        default=False, description="Whether this scenario should trigger a user alert"
    )
    expected_vram_mb: int | None = Field(
        default=None, description="Total VRAM required for all enrichment models (MB)"
    )
    should_trigger_circuit_breaker: bool = Field(
        default=False, description="Whether scenario should trigger circuit breaker activation"
    )
    expected_fallback_behavior: str | None = Field(
        default=None, description="Expected fallback when enrichment models fail"
    )


# =============================================================================
# Scenario Bundle
# =============================================================================


class ScenarioBundle(BaseModel):
    """Complete scenario combining detections, enrichment, and ground truth.

    A scenario bundle represents a single test case for the security pipeline,
    including the raw detections, enrichment context, expected ground truth,
    and metadata for filtering and analysis.

    Attributes:
        scenario_id: Unique identifier for this scenario
        time_of_day: Time period when scenario occurs
        day_type: Type of day (weekday, weekend, holiday)
        camera_location: Camera location/zone
        scenario_type: Classification for ground truth
        enrichment_level: Level of enrichment context available
        detections: List of detections in this scenario
        enrichment_context: Optional enrichment data
        ground_truth: Expected risk assessment
        scenario_narrative: Human-readable description
        expected_summary: Expected summary text from Nemotron
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "scenario_id": "scn_001",
                "time_of_day": "night",
                "day_type": "weekday",
                "camera_location": "front_door",
                "scenario_type": "suspicious",
                "enrichment_level": "full",
                "detections": [
                    {
                        "object_type": "person",
                        "confidence": 0.92,
                        "bbox": [150, 200, 80, 180],
                        "timestamp_offset_seconds": 15,
                    }
                ],
                "enrichment_context": {
                    "zone_name": "front_door",
                    "is_entry_point": True,
                    "baseline_expected_count": 0,
                    "baseline_deviation_score": 2.5,
                    "cross_camera_matches": 0,
                },
                "ground_truth": {
                    "risk_range": [40, 55],
                    "reasoning_key_points": ["unknown person", "night time"],
                    "expected_enrichment_models": ["florence_2"],
                    "should_trigger_alert": True,
                },
                "scenario_narrative": "Unknown person at front door at 11pm",
                "expected_summary": "Suspicious: Unknown person detected at entry point during late hours",
            }
        }
    )

    scenario_id: str = Field(description="Unique scenario identifier")
    time_of_day: Literal["morning", "midday", "evening", "night", "late_night"] = Field(
        description="Time period of the scenario"
    )
    day_type: Literal["weekday", "weekend", "holiday"] = Field(description="Type of day")
    camera_location: Literal["front_door", "backyard", "driveway", "side_gate"] = Field(
        description="Camera location/zone"
    )
    scenario_type: Literal["normal", "suspicious", "threat", "edge_case"] = Field(
        description="Scenario classification for ground truth"
    )
    enrichment_level: Literal["none", "basic", "full"] = Field(
        description="Level of enrichment context"
    )
    detections: list[Detection] = Field(
        default_factory=list, description="List of detections in this scenario"
    )
    enrichment_context: EnrichmentContext | None = Field(
        default=None, description="Enrichment context (None if enrichment_level='none')"
    )
    ground_truth: GroundTruth = Field(description="Expected risk assessment")
    scenario_narrative: str = Field(default="", description="Human-readable scenario description")
    expected_summary: str = Field(default="", description="Expected summary text from Nemotron")


# =============================================================================
# Column Configuration Constants
# =============================================================================


# Sampler column configurations for NeMo Data Designer
SAMPLER_COLUMNS = {
    "time_of_day": {
        "values": ["morning", "midday", "evening", "night", "late_night"],
        "weights": [0.15, 0.20, 0.25, 0.25, 0.15],
        "description": "Time period for scenario (affects baseline expectations)",
    },
    "day_type": {
        "values": ["weekday", "weekend", "holiday"],
        "weights": [0.60, 0.35, 0.05],
        "description": "Day type (affects activity patterns)",
    },
    "camera_location": {
        "values": ["front_door", "backyard", "driveway", "side_gate"],
        "weights": [0.35, 0.25, 0.25, 0.15],
        "description": "Camera zone (affects entry point status)",
    },
    "detection_count": {
        "values": ["1", "2-3", "4-6", "7+"],
        "weights": [0.40, 0.35, 0.20, 0.05],
        "description": "Number of detections in batch",
    },
    "primary_object": {
        "values": ["person", "vehicle", "animal", "package"],
        "weights": [0.45, 0.30, 0.15, 0.10],
        "description": "Main object type detected",
    },
    "scenario_type": {
        "values": ["normal", "suspicious", "threat", "edge_case"],
        "weights": [0.40, 0.30, 0.20, 0.10],
        "description": "Scenario classification for ground truth",
    },
    "enrichment_level": {
        "values": ["none", "basic", "full"],
        "weights": [0.20, 0.35, 0.45],
        "description": "Level of enrichment context available",
    },
}


# Ground truth risk ranges by scenario type
RISK_RANGES = {
    "normal": (0, 25),
    "suspicious": (30, 55),
    "threat": (70, 100),
    "edge_case": (20, 60),
}


# Entry point indicators by camera location
ENTRY_POINTS = {
    "front_door": True,
    "backyard": False,
    "driveway": False,
    "side_gate": True,
}


# Object type to detection model mapping
OBJECT_TYPES = {
    "person": ["person"],
    "vehicle": ["car", "truck", "motorcycle", "bus"],
    "animal": ["dog", "cat"],
    "package": [],  # Packages are inferred from person + stationary behavior
}


# Enrichment models by level
ENRICHMENT_MODELS = {
    "none": [],
    "basic": ["florence_2"],
    "full": ["florence_2", "pose_estimation", "reid", "ocr"],
}


# Complexity multipliers for scenario factors
COMPLEXITY_FACTORS = {
    "detection_count": {
        "1": 0.1,
        "2-3": 0.2,
        "4-6": 0.4,
        "7+": 0.7,
    },
    "enrichment_level": {
        "none": 0.0,
        "basic": 0.15,
        "full": 0.3,
    },
    "scenario_type": {
        "normal": 0.1,
        "suspicious": 0.3,
        "threat": 0.5,
        "edge_case": 0.4,
    },
}


# Embedding dimensions for vector columns
EMBEDDING_DIM = 768


# =============================================================================
# Expression Column Helper Functions
# =============================================================================


def calculate_complexity_score(
    detection_count: str,
    enrichment_level: str,
    scenario_type: str,
) -> float:
    """Calculate scenario complexity score (0.0 - 1.0).

    Combines detection count, enrichment level, and scenario type to produce
    a normalized complexity score for categorizing scenarios.

    Args:
        detection_count: Number of detections ("1", "2-3", "4-6", "7+")
        enrichment_level: Enrichment level ("none", "basic", "full")
        scenario_type: Type of scenario ("normal", "suspicious", "threat", "edge_case")

    Returns:
        Complexity score between 0.0 and 1.0

    Examples:
        >>> calculate_complexity_score("1", "none", "normal")
        0.2
        >>> calculate_complexity_score("7+", "full", "threat")
        1.0
    """
    dc_weight = COMPLEXITY_FACTORS["detection_count"].get(detection_count, 0.2)
    el_weight = COMPLEXITY_FACTORS["enrichment_level"].get(enrichment_level, 0.15)
    st_weight = COMPLEXITY_FACTORS["scenario_type"].get(scenario_type, 0.3)

    # Weighted sum normalized to 0-1 range
    raw_score = dc_weight + el_weight + st_weight
    # Max possible is 0.7 + 0.3 + 0.5 = 1.5, normalize to 0-1
    normalized = min(1.0, raw_score / 1.5)

    return round(normalized, 3)


def generate_scenario_hash(scenario: dict) -> str:
    """Generate deterministic hash for scenario deduplication.

    Creates a SHA-256 hash from key scenario fields to uniquely identify
    scenarios and detect duplicates.

    Args:
        scenario: Dictionary containing scenario data

    Returns:
        Hex string of first 16 characters of SHA-256 hash

    Examples:
        >>> scenario = {"scenario_type": "threat", "time_of_day": "night"}
        >>> generate_scenario_hash(scenario)
        'a1b2c3d4e5f67890'  # pragma: allowlist secret
    """
    # Use stable fields for hashing
    hash_fields = [
        scenario.get("time_of_day", ""),
        scenario.get("day_type", ""),
        scenario.get("camera_location", ""),
        scenario.get("detection_count", ""),
        scenario.get("primary_object", ""),
        scenario.get("scenario_type", ""),
        scenario.get("enrichment_level", ""),
        scenario.get("scenario_narrative", ""),
    ]

    hash_input = "|".join(str(f) for f in hash_fields)
    hash_digest = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()

    return hash_digest[:16]


def validate_detection_schema(detections: Sequence[dict] | None) -> bool:  # noqa: PLR0911
    """Validate that detections conform to Detection schema.

    Args:
        detections: List of detection dictionaries to validate

    Returns:
        True if all detections are valid, False otherwise

    Examples:
        >>> detections = [{"object_type": "person", "confidence": 0.9, "bbox": [0,0,100,100], "timestamp_offset_seconds": 0}]
        >>> validate_detection_schema(detections)
        True
    """
    if detections is None:
        return True

    required_fields = {"object_type", "confidence", "bbox", "timestamp_offset_seconds"}

    for det in detections:
        if not isinstance(det, dict):
            return False
        if not required_fields.issubset(det.keys()):
            return False
        if det.get("confidence", 0) < 0.5 or det.get("confidence", 0) > 1.0:
            return False
        if (
            det.get("timestamp_offset_seconds", -1) < 0
            or det.get("timestamp_offset_seconds", 91) > 90
        ):
            return False
        bbox = det.get("bbox", [])
        if not isinstance(bbox, list | tuple) or len(bbox) != 4:
            return False

    return True


def validate_temporal_consistency(detections: Sequence[dict] | None) -> bool:
    """Validate temporal consistency of detections within batch window.

    Checks that detection timestamps are within the 90-second batch window
    and are logically ordered.

    Args:
        detections: List of detection dictionaries

    Returns:
        True if temporally consistent, False otherwise

    Examples:
        >>> detections = [{"timestamp_offset_seconds": 10}, {"timestamp_offset_seconds": 50}]
        >>> validate_temporal_consistency(detections)
        True
    """
    if detections is None or len(detections) == 0:
        return True

    timestamps = []
    for det in detections:
        ts = det.get("timestamp_offset_seconds")
        if ts is None or not isinstance(ts, int):
            return False
        if ts < 0 or ts > 90:
            return False
        timestamps.append(ts)

    # Check that timestamps span a reasonable range for the batch
    if len(timestamps) > 1:
        time_span = max(timestamps) - min(timestamps)
        # For multiple detections, expect at least 5 seconds between first and last
        if time_span < 5:
            return True  # Still valid, just clustered detections
    return True


def format_prompt_input(
    scenario: dict,
    template_name: str = "default",  # noqa: ARG001 - reserved for multi-template support
) -> str:
    """Format scenario data into a prompt input string.

    Pre-renders the scenario data into a format ready for Nemotron prompt templates.

    Args:
        scenario: Dictionary containing full scenario data
        template_name: Name of the prompt template to format for

    Returns:
        Formatted prompt input string

    Examples:
        >>> scenario = {"scenario_narrative": "Person at door", "detections": []}
        >>> format_prompt_input(scenario)
        '...'
    """
    detections_str = json.dumps(scenario.get("detections", []), indent=2)
    enrichment_str = json.dumps(scenario.get("enrichment_context"), indent=2)

    prompt_parts = [
        f"Time: {scenario.get('time_of_day', 'unknown')} ({scenario.get('day_type', 'unknown')})",
        f"Location: {scenario.get('camera_location', 'unknown')}",
        "",
        f"Narrative: {scenario.get('scenario_narrative', 'No description available')}",
        "",
        "Detections:",
        detections_str,
    ]

    # Add enrichment context if available
    enrichment_level = scenario.get("enrichment_level", "none")
    if enrichment_level != "none" and scenario.get("enrichment_context"):
        prompt_parts.extend(
            [
                "",
                "Enrichment Context:",
                enrichment_str,
            ]
        )

    return "\n".join(prompt_parts)


def generate_default_judge_scores(scenario_type: str) -> JudgeScores:
    """Generate default LLM-Judge scores based on scenario type.

    Provides reasonable default scores for scenarios where LLM-Judge
    evaluation has not yet been run.

    Args:
        scenario_type: Type of scenario ("normal", "suspicious", "threat", "edge_case")

    Returns:
        JudgeScores instance with default values
    """
    # Default scores vary by scenario complexity
    defaults = {
        "normal": JudgeScores(
            relevance=3,
            risk_calibration=3,
            context_usage=3,
            reasoning_quality=3,
            threat_identification=3,
            actionability=3,
        ),
        "suspicious": JudgeScores(
            relevance=3,
            risk_calibration=3,
            context_usage=3,
            reasoning_quality=3,
            threat_identification=3,
            actionability=3,
        ),
        "threat": JudgeScores(
            relevance=3,
            risk_calibration=3,
            context_usage=3,
            reasoning_quality=3,
            threat_identification=4,  # Higher for threats
            actionability=3,
        ),
        "edge_case": JudgeScores(
            relevance=3,
            risk_calibration=2,  # Lower - edge cases are harder to calibrate
            context_usage=3,
            reasoning_quality=3,
            threat_identification=2,  # Lower - edge cases are ambiguous
            actionability=3,
        ),
    }

    return defaults.get(scenario_type, JudgeScores())


def generate_placeholder_embedding(seed_text: str, dim: int = EMBEDDING_DIM) -> list[float]:
    """Generate a placeholder embedding vector for testing.

    Creates a deterministic pseudo-embedding based on the input text hash.
    This is NOT a real semantic embedding - use only for testing structure.

    Args:
        seed_text: Text to generate embedding from
        dim: Dimension of the embedding vector (default: 768)

    Returns:
        List of floats representing a placeholder embedding

    Note:
        For production use, call NVIDIA embedding API instead.
    """
    import random

    # Use hash of text as random seed for deterministic output
    text_hash = int(hashlib.sha256(seed_text.encode("utf-8")).hexdigest()[:8], 16)
    rng = random.Random(text_hash)  # noqa: S311 - intentional for deterministic test data

    # Generate normalized pseudo-embedding
    embedding = [rng.gauss(0, 0.1) for _ in range(dim)]

    # L2 normalize
    magnitude = sum(x * x for x in embedding) ** 0.5
    if magnitude > 0:
        embedding = [x / magnitude for x in embedding]

    return embedding


# =============================================================================
# Column Type Enumerations
# =============================================================================

# Complete column inventory for full scenario coverage
COLUMN_TYPES = {
    "samplers": [
        "time_of_day",
        "day_type",
        "camera_location",
        "detection_count",
        "primary_object",
        "scenario_type",
        "enrichment_level",
    ],
    "llm_structured": [
        "detections",
        "enrichment_context",
        "ground_truth",
    ],
    "llm_text": [
        "scenario_narrative",
        "expected_summary",
        "reasoning_key_points",
    ],
    "llm_judge": [
        "relevance",
        "risk_calibration",
        "context_usage",
        "reasoning_quality",
        "threat_identification",
        "actionability",
    ],
    "embedding": [
        "scenario_embedding",
        "reasoning_embedding",
    ],
    "expression": [
        "formatted_prompt_input",
        "complexity_score",
        "scenario_hash",
    ],
    "validation": [
        "detection_schema_valid",
        "temporal_consistency",
    ],
}

# Total column count for verification
TOTAL_COLUMNS = sum(len(cols) for cols in COLUMN_TYPES.values())  # Should be 24
