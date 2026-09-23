"""Pure-leaf detection-quality contract (WP6.3, NEM-5502/5503/5504).

Stdlib + typing ONLY — zero sibling imports, zero torch. backend/services/
prompts.py imports ConfidenceQuality / EnhancedDetection / enhance_detections
from here instead of ai.yolo26.model: the model module is a GPU service
(torch, fastapi, metrics, ultralytics) that cannot import inside the backend
process, so format_detections_with_quality() had been raising
ModuleNotFoundError on every production call — invisible to a suite that
only asserted its signature.

HISTORY (A7.3 / WP6-A): model.py used to carry inline copies of these
symbols because ai/yolo26/Dockerfile's explicit per-file COPY list left
contract.py out of the image — importing it there would have broken
startup. The Dockerfile later COPYed this file flat next to model.py and
model.py does `from contract import ...`, so backend and container shared
ONE definition. The duplicate is deleted (ratcheted absent by
ai/yolo26/tests/test_model.py::TestContractSeam, repo-side; the retired
ai-yolo26-image-smoke CI job proved `import model` inside the built
image). The standalone GPU image was retired 2026-09-23 (build recipe at
archive/ai-yolo26-image/Dockerfile) — this module now serves backend and
the kept-locally model modules only.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class ConfidenceQuality(str, Enum):
    """Quality tier for detection confidence scores.

    Provides semantic meaning to raw confidence values, helping the LLM
    understand the reliability of each detection.

    Tiers:
        EXCELLENT: >= 0.90 - Very high confidence, highly reliable
        GOOD: >= 0.75 - Solid detection, trustworthy
        MODERATE: >= 0.60 - Acceptable but verify with context
        MARGINAL: < 0.60 - Low confidence, treat with caution
    """

    EXCELLENT = "excellent"
    GOOD = "good"
    MODERATE = "moderate"
    MARGINAL = "marginal"


def compute_confidence_quality(confidence: float) -> ConfidenceQuality:
    """Compute the quality tier for a detection confidence score.

    Args:
        confidence: Detection confidence score between 0 and 1.

    Returns:
        ConfidenceQuality enum value indicating the quality tier.

    Examples:
        >>> compute_confidence_quality(0.95)
        <ConfidenceQuality.EXCELLENT: 'excellent'>
        >>> compute_confidence_quality(0.82)
        <ConfidenceQuality.GOOD: 'good'>
        >>> compute_confidence_quality(0.65)
        <ConfidenceQuality.MODERATE: 'moderate'>
        >>> compute_confidence_quality(0.45)
        <ConfidenceQuality.MARGINAL: 'marginal'>
    """
    if confidence >= 0.90:
        return ConfidenceQuality.EXCELLENT
    elif confidence >= 0.75:
        return ConfidenceQuality.GOOD
    elif confidence >= 0.60:
        return ConfidenceQuality.MODERATE
    else:
        return ConfidenceQuality.MARGINAL


def get_confidence_explanation(quality: ConfidenceQuality, confidence: float) -> str:
    """Generate a human-readable explanation of the confidence quality.

    Args:
        quality: The computed ConfidenceQuality tier.
        confidence: The raw confidence score.

    Returns:
        String explanation suitable for LLM prompt context.
    """
    explanations = {
        ConfidenceQuality.EXCELLENT: f"Very high confidence ({confidence:.0%}) - highly reliable detection",
        ConfidenceQuality.GOOD: f"Good confidence ({confidence:.0%}) - solid detection",
        ConfidenceQuality.MODERATE: f"Moderate confidence ({confidence:.0%}) - verify with visual context",
        ConfidenceQuality.MARGINAL: f"MARGINAL confidence ({confidence:.0%}) - treat with caution, may be false positive",
    }
    return explanations[quality]


@dataclass
class SpatialContext:
    """Spatial context for a detection within the frame.

    Provides information about where the detection is located in the frame
    and its relative size, which can indicate detection reliability.

    Attributes:
        relative_position: Position in frame as 9-grid (e.g., "top-left", "center")
        size_relative_to_frame: Detection area as fraction of frame area (0-1)
        is_at_boundary: True if detection bbox touches frame edge
        position_description: Human-readable position description
    """

    relative_position: str
    size_relative_to_frame: float
    is_at_boundary: bool
    position_description: str


def compute_spatial_context(
    bbox_x: int,
    bbox_y: int,
    bbox_width: int,
    bbox_height: int,
    frame_width: int,
    frame_height: int,
    boundary_threshold: int = 5,
) -> SpatialContext:
    """Compute spatial context for a detection bounding box.

    Analyzes where the detection is located within the frame and its
    relative size, providing context for detection reliability.

    Args:
        bbox_x: Top-left x coordinate of bounding box.
        bbox_y: Top-left y coordinate of bounding box.
        bbox_width: Width of bounding box.
        bbox_height: Height of bounding box.
        frame_width: Width of the frame/image.
        frame_height: Height of the frame/image.
        boundary_threshold: Pixels from edge to consider "at boundary".

    Returns:
        SpatialContext with position and size information.

    Examples:
        >>> ctx = compute_spatial_context(10, 10, 100, 200, 1920, 1080)
        >>> ctx.relative_position
        'top-left'
        >>> ctx.is_at_boundary
        False
    """
    # Calculate center of bounding box
    center_x = bbox_x + bbox_width / 2
    center_y = bbox_y + bbox_height / 2

    # Determine position in 9-grid
    x_third = frame_width / 3
    y_third = frame_height / 3

    if center_x < x_third:
        h_pos = "left"
    elif center_x < 2 * x_third:
        h_pos = "center"
    else:
        h_pos = "right"

    if center_y < y_third:
        v_pos = "top"
    elif center_y < 2 * y_third:
        v_pos = "middle"
    else:
        v_pos = "bottom"

    # Combine position
    if h_pos == "center" and v_pos == "middle":
        relative_position = "center"
    elif h_pos == "center":
        relative_position = v_pos
    elif v_pos == "middle":
        relative_position = h_pos
    else:
        relative_position = f"{v_pos}-{h_pos}"

    # Calculate size relative to frame
    bbox_area = bbox_width * bbox_height
    frame_area = frame_width * frame_height
    size_relative = bbox_area / frame_area if frame_area > 0 else 0.0

    # Check if at boundary
    is_at_boundary = (
        bbox_x <= boundary_threshold
        or bbox_y <= boundary_threshold
        or (bbox_x + bbox_width) >= (frame_width - boundary_threshold)
        or (bbox_y + bbox_height) >= (frame_height - boundary_threshold)
    )

    # Generate position description
    size_desc = "large" if size_relative >= 0.10 else "medium" if size_relative >= 0.02 else "small"
    boundary_note = " (at frame edge)" if is_at_boundary else ""
    position_description = f"{size_desc} object in {relative_position} of frame{boundary_note}"

    return SpatialContext(
        relative_position=relative_position,
        size_relative_to_frame=size_relative,
        is_at_boundary=is_at_boundary,
        position_description=position_description,
    )


@dataclass
class EnhancedDetection:
    """Enhanced detection with quality indicators and spatial context.

    Combines raw detection data with computed quality metrics to provide
    richer context for LLM-based risk assessment.

    Attributes:
        class_name: Detected object class (e.g., "person", "car").
        confidence: Raw confidence score (0-1).
        bbox: Bounding box as dict with x, y, width, height.
        confidence_quality: Computed quality tier.
        confidence_explanation: Human-readable confidence explanation.
        relative_position: Position in frame (9-grid).
        size_relative_to_frame: Detection size as fraction of frame.
        is_at_boundary: True if detection touches frame edge.
        spatial_description: Human-readable spatial description.
    """

    class_name: str
    confidence: float
    bbox: dict[str, int]
    confidence_quality: ConfidenceQuality
    confidence_explanation: str
    relative_position: str
    size_relative_to_frame: float
    is_at_boundary: bool
    spatial_description: str

    @classmethod
    def from_detection(
        cls,
        class_name: str,
        confidence: float,
        bbox: dict[str, int],
        frame_width: int,
        frame_height: int,
    ) -> EnhancedDetection:
        """Create an EnhancedDetection from raw detection data.

        Args:
            class_name: Detected object class.
            confidence: Detection confidence score (0-1).
            bbox: Bounding box dict with x, y, width, height keys.
            frame_width: Width of the frame/image.
            frame_height: Height of the frame/image.

        Returns:
            EnhancedDetection with computed quality indicators.
        """
        quality = compute_confidence_quality(confidence)
        explanation = get_confidence_explanation(quality, confidence)

        spatial = compute_spatial_context(
            bbox_x=bbox.get("x", 0),
            bbox_y=bbox.get("y", 0),
            bbox_width=bbox.get("width", 0),
            bbox_height=bbox.get("height", 0),
            frame_width=frame_width,
            frame_height=frame_height,
        )

        return cls(
            class_name=class_name,
            confidence=confidence,
            bbox=bbox,
            confidence_quality=quality,
            confidence_explanation=explanation,
            relative_position=spatial.relative_position,
            size_relative_to_frame=spatial.size_relative_to_frame,
            is_at_boundary=spatial.is_at_boundary,
            spatial_description=spatial.position_description,
        )

    def to_prompt_context(self) -> str:
        """Format detection for LLM prompt context.

        Returns:
            Multi-line string with detection details and quality indicators.
        """
        lines = [
            f"- {self.class_name.upper()}: {self.confidence_explanation}",
            f"  Position: {self.spatial_description}",
        ]

        # Add warning for marginal detections
        if self.confidence_quality == ConfidenceQuality.MARGINAL:
            lines.append("  WARNING: Low confidence detection - verify before acting")

        # Add warning for boundary detections
        if self.is_at_boundary:
            lines.append("  NOTE: Object at frame boundary - may be partially visible")

        return "\n".join(lines)


def enhance_detections(
    detections: list[dict[str, Any]],
    frame_width: int,
    frame_height: int,
) -> list[EnhancedDetection]:
    """Enhance a list of raw detections with quality indicators.

    Args:
        detections: List of detection dicts with class, confidence, bbox.
        frame_width: Width of the frame/image.
        frame_height: Height of the frame/image.

    Returns:
        List of EnhancedDetection objects with computed quality metrics.
    """
    enhanced = []
    for det in detections:
        class_name = det.get("class", det.get("class_name", "unknown"))
        confidence = det.get("confidence", 0.0)
        bbox = det.get("bbox", {"x": 0, "y": 0, "width": 0, "height": 0})

        # Handle bbox as dict or as BoundingBox model
        if hasattr(bbox, "model_dump"):
            bbox = bbox.model_dump()
        elif not isinstance(bbox, dict):
            bbox = {"x": 0, "y": 0, "width": 0, "height": 0}

        enhanced.append(
            EnhancedDetection.from_detection(
                class_name=class_name,
                confidence=confidence,
                bbox=bbox,
                frame_width=frame_width,
                frame_height=frame_height,
            )
        )

    return enhanced
