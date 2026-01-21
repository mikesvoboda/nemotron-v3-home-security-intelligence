"""Configuration and Pydantic models for NeMo Data Designer scenarios.

This module defines the schema for synthetic security scenarios used in
testing and prompt evaluation. The models align with the home security
system's detection pipeline and Nemotron risk analysis.

Models:
    Detection: Single object detection with bbox and confidence
    EnrichmentContext: Additional context from enrichment pipeline
    GroundTruth: Expected risk assessment and key reasoning points
    ScenarioBundle: Complete scenario combining all components
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

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
