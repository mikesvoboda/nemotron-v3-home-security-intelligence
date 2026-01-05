"""Reusable Hypothesis strategies for property-based testing.

This module provides composable Hypothesis strategies for generating domain objects
used across the home security intelligence system. These strategies are designed
to generate valid data that respects model constraints while still exploring
edge cases.

Key strategies:
- Detection objects: bbox, confidence, label, media_type
- Event objects: risk_score, timestamps, batch_id
- Camera objects: id, name, status, folder_path
- Batch-related: detection lists, camera batches
- Severity: risk scores, threshold configurations

Usage:
    from backend.tests.strategies import (
        detections,
        events,
        valid_risk_scores,
        detection_lists,
    )

    @given(detection=detections())
    def test_detection_property(detection):
        assert detection.confidence <= 1.0
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from hypothesis import strategies as st

# =============================================================================
# Core Value Strategies
# =============================================================================

# Risk scores (0-100 inclusive, as specified in the system)
valid_risk_scores = st.integers(min_value=0, max_value=100)

# Invalid risk scores (outside 0-100 range)
invalid_risk_scores = st.one_of(
    st.integers(max_value=-1),
    st.integers(min_value=101),
)

# Confidence scores (0.0-1.0 range for detection confidence)
valid_confidence = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)

# Invalid confidence scores (outside 0.0-1.0)
invalid_confidence = st.one_of(
    st.floats(max_value=-0.001, allow_nan=False, allow_infinity=False),
    st.floats(min_value=1.001, allow_nan=False, allow_infinity=False),
)

# Positive integers for bbox dimensions
positive_bbox_values = st.integers(min_value=0, max_value=4096)

# Object types commonly detected by RT-DETR
common_object_types = st.sampled_from(
    ["person", "car", "truck", "bicycle", "motorcycle", "dog", "cat", "bird", "package", "unknown"]
)

# All valid object types (including less common ones)
all_object_types = st.text(
    min_size=1,
    max_size=50,
    alphabet=st.characters(
        whitelist_categories=("Lu", "Ll", "Nd"),
        whitelist_characters="_-",
    ),
).filter(lambda x: len(x.strip()) > 0)

# Camera IDs (normalized identifiers)
camera_ids = st.from_regex(r"[a-z0-9_]{1,50}", fullmatch=True).filter(
    lambda x: not x.startswith("_") and not x.endswith("_") and "__" not in x
)

# Camera names (human-readable)
camera_names = st.text(
    min_size=1,
    max_size=255,
    alphabet=st.characters(
        whitelist_categories=("Lu", "Ll", "Nd", "Zs"),
        whitelist_characters="-_",
    ),
).filter(lambda x: len(x.strip()) > 0)

# Valid folder paths (no path traversal)
valid_folder_paths = st.from_regex(
    r"/[a-zA-Z0-9_\-/]{1,100}",
    fullmatch=True,
).filter(lambda x: ".." not in x and len(x) <= 500)

# File paths for images
image_file_paths = st.from_regex(
    r"/[a-zA-Z0-9_/\-]+\.(jpg|jpeg|png|bmp)",
    fullmatch=True,
).filter(lambda x: len(x) <= 500)

# Batch IDs (UUID hex format)
batch_ids = st.from_regex(r"[a-f0-9]{32}", fullmatch=True)

# Detection IDs (positive integers)
detection_ids = st.integers(min_value=1, max_value=1_000_000)

# Timestamps in reasonable range
timestamps = st.datetimes(
    min_value=datetime(2020, 1, 1),
    max_value=datetime(2030, 12, 31),
)

# UTC timestamps
utc_timestamps = timestamps.map(lambda dt: dt.replace(tzinfo=UTC))


# =============================================================================
# Composite Strategies
# =============================================================================


@st.composite
def valid_bbox(draw: st.DrawFn) -> tuple[int, int, int, int]:
    """Generate valid bounding box as (x, y, width, height).

    Ensures:
    - All values are non-negative
    - Width and height are at least 1 (non-empty bbox)
    - Total coordinates fit within reasonable image bounds
    """
    x = draw(st.integers(min_value=0, max_value=1920))
    y = draw(st.integers(min_value=0, max_value=1080))
    max_width = min(500, 1920 - x)
    max_height = min(500, 1080 - y)
    width = draw(st.integers(min_value=1, max_value=max(1, max_width)))
    height = draw(st.integers(min_value=1, max_value=max(1, max_height)))
    return (x, y, width, height)


@st.composite
def ordered_timestamps(draw: st.DrawFn) -> tuple[datetime, datetime]:
    """Generate two UTC timestamps where started_at <= ended_at."""
    started_at = draw(timestamps)
    delta = draw(st.timedeltas(min_value=timedelta(seconds=0), max_value=timedelta(hours=24)))
    ended_at = started_at + delta
    return (started_at.replace(tzinfo=UTC), ended_at.replace(tzinfo=UTC))


@st.composite
def severity_thresholds(draw: st.DrawFn) -> tuple[int, int, int]:
    """Generate valid severity threshold configuration (low_max, medium_max, high_max).

    Ensures: 0 <= low_max < medium_max < high_max <= 100
    """
    # Generate three distinct values in ascending order
    low_max = draw(st.integers(min_value=0, max_value=50))
    medium_max = draw(st.integers(min_value=low_max + 1, max_value=80))
    high_max = draw(st.integers(min_value=medium_max + 1, max_value=100))
    return (low_max, medium_max, high_max)


@st.composite
def detection_data(draw: st.DrawFn) -> dict:
    """Generate valid detection data dictionary.

    This generates the data that would be used to create a Detection model,
    respecting all field constraints.
    """
    bbox = draw(valid_bbox())

    return {
        "camera_id": draw(camera_ids),
        "file_path": draw(image_file_paths),
        "object_type": draw(common_object_types),
        "confidence": draw(valid_confidence),
        "bbox_x": bbox[0],
        "bbox_y": bbox[1],
        "bbox_width": bbox[2],
        "bbox_height": bbox[3],
        "media_type": draw(st.sampled_from(["image", "video"])),
    }


@st.composite
def detection_lists(draw: st.DrawFn, min_size: int = 0, max_size: int = 20) -> list[dict]:
    """Generate a list of detection data dictionaries.

    Useful for testing batch processing and aggregation.
    """
    size = draw(st.integers(min_value=min_size, max_value=max_size))
    return [draw(detection_data()) for _ in range(size)]


@st.composite
def event_data(draw: st.DrawFn) -> dict:
    """Generate valid event data dictionary.

    This generates the data that would be used to create an Event model,
    respecting all field constraints.
    """
    started_at, ended_at = draw(ordered_timestamps())

    return {
        "batch_id": draw(batch_ids),
        "camera_id": draw(camera_ids),
        "started_at": started_at,
        "ended_at": ended_at,
        "risk_score": draw(valid_risk_scores),
        "risk_level": draw(st.sampled_from(["low", "medium", "high", "critical"])),
        "reviewed": draw(st.booleans()),
        "is_fast_path": draw(st.booleans()),
    }


@st.composite
def camera_batch(draw: st.DrawFn) -> dict:
    """Generate a camera batch for batch aggregator testing.

    Returns dict with:
    - camera_id: str
    - detection_ids: list[int]
    - batch_id: str
    """
    return {
        "camera_id": draw(camera_ids),
        "detection_ids": draw(st.lists(detection_ids, min_size=1, max_size=50)),
        "batch_id": draw(batch_ids),
    }


@st.composite
def overlapping_detections(draw: st.DrawFn) -> list[dict]:
    """Generate detections that may have overlapping bboxes.

    Useful for testing deduplication logic.
    """
    # Start with a base position
    base_x = draw(st.integers(min_value=0, max_value=1500))
    base_y = draw(st.integers(min_value=0, max_value=800))
    base_width = draw(st.integers(min_value=50, max_value=200))
    base_height = draw(st.integers(min_value=50, max_value=200))

    n_detections = draw(st.integers(min_value=2, max_value=5))
    detections = []

    for _ in range(n_detections):
        # Generate slight offsets from base
        offset_x = draw(st.integers(min_value=-50, max_value=50))
        offset_y = draw(st.integers(min_value=-50, max_value=50))

        x = max(0, base_x + offset_x)
        y = max(0, base_y + offset_y)

        detections.append(
            {
                "camera_id": draw(camera_ids),
                "file_path": draw(image_file_paths),
                "object_type": draw(common_object_types),
                "confidence": draw(valid_confidence),
                "bbox_x": x,
                "bbox_y": y,
                "bbox_width": base_width,
                "bbox_height": base_height,
            }
        )

    return detections


@st.composite
def detection_with_confidence(
    draw: st.DrawFn,
    min_confidence: float = 0.0,
    max_confidence: float = 1.0,
) -> dict:
    """Generate detection with confidence in specified range.

    Useful for testing confidence-based filtering.
    """
    confidence = draw(
        st.floats(
            min_value=min_confidence,
            max_value=max_confidence,
            allow_nan=False,
            allow_infinity=False,
        )
    )
    bbox = draw(valid_bbox())

    return {
        "camera_id": draw(camera_ids),
        "file_path": draw(image_file_paths),
        "object_type": draw(common_object_types),
        "confidence": confidence,
        "bbox_x": bbox[0],
        "bbox_y": bbox[1],
        "bbox_width": bbox[2],
        "bbox_height": bbox[3],
    }


@st.composite
def high_confidence_detections(draw: st.DrawFn, n: int = 5) -> list[dict]:
    """Generate list of high confidence detections (>= 0.8)."""
    return [draw(detection_with_confidence(min_confidence=0.8)) for _ in range(n)]


@st.composite
def mixed_confidence_detections(draw: st.DrawFn) -> list[dict]:
    """Generate list with mixed confidence levels.

    Useful for testing that highest confidence is kept during deduplication.
    """
    confidences = [0.3, 0.5, 0.7, 0.9, 0.95]
    draw(st.randoms()).shuffle(confidences)

    detections = []
    for conf in confidences:
        det = draw(detection_with_confidence(min_confidence=conf, max_confidence=conf + 0.01))
        det["confidence"] = conf  # Force exact confidence for testing
        detections.append(det)

    return detections


# =============================================================================
# Alert Engine Strategies
# =============================================================================


@st.composite
def alert_rule_conditions(draw: st.DrawFn) -> dict:
    """Generate valid alert rule condition data.

    Returns a dictionary of conditions that can be used for rule evaluation.
    """
    conditions = {}

    # Optionally include risk threshold
    if draw(st.booleans()):
        conditions["risk_threshold"] = draw(valid_risk_scores)

    # Optionally include object types filter
    if draw(st.booleans()):
        n_types = draw(st.integers(min_value=1, max_value=3))
        conditions["object_types"] = [draw(common_object_types) for _ in range(n_types)]

    # Optionally include camera filter
    if draw(st.booleans()):
        n_cameras = draw(st.integers(min_value=1, max_value=3))
        conditions["camera_ids"] = [draw(camera_ids) for _ in range(n_cameras)]

    # Optionally include confidence threshold
    if draw(st.booleans()):
        conditions["min_confidence"] = draw(
            st.floats(
                min_value=0.1,
                max_value=0.99,
                allow_nan=False,
                allow_infinity=False,
            )
        )

    return conditions


@st.composite
def matching_event_and_detection(draw: st.DrawFn) -> tuple[dict, dict]:
    """Generate an event and detection that should match each other.

    Useful for testing alert rule evaluation.
    """
    camera_id = draw(camera_ids)
    object_type = draw(common_object_types)
    confidence = draw(st.floats(min_value=0.7, max_value=1.0, allow_nan=False))
    risk_score = draw(valid_risk_scores)

    event = {
        "batch_id": draw(batch_ids),
        "camera_id": camera_id,
        "started_at": draw(utc_timestamps),
        "risk_score": risk_score,
    }

    bbox = draw(valid_bbox())
    detection = {
        "camera_id": camera_id,
        "file_path": draw(image_file_paths),
        "object_type": object_type,
        "confidence": confidence,
        "bbox_x": bbox[0],
        "bbox_y": bbox[1],
        "bbox_width": bbox[2],
        "bbox_height": bbox[3],
    }

    return (event, detection)
