"""Reusable Hypothesis strategies for property-based testing.

This module provides domain-specific strategies for generating test data
used throughout the backend property-based tests. These strategies ensure
that generated data matches the constraints of our domain models.

Usage:
    from backend.tests.strategies import detection_strategy, event_strategy
    from hypothesis import given

    @given(detection=detection_strategy())
    def test_detection_property(detection):
        assert 0 <= detection["confidence"] <= 1

Key strategies:
- Camera strategies: camera_ids, camera_names
- Detection strategies: confidence scores, bbox, object types
- Event strategies: risk scores, timestamps, batch IDs
- Alert strategies: severity levels, dedup keys
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from hypothesis import strategies as st

from backend.models.enums import Severity

# =============================================================================
# Basic Type Strategies
# =============================================================================

# Valid confidence scores (0.0 to 1.0 inclusive)
confidence_scores = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)

# Invalid confidence scores (outside 0-1 range)
invalid_confidence_scores = st.one_of(
    st.floats(max_value=-0.001, allow_nan=False, allow_infinity=False),
    st.floats(min_value=1.001, allow_nan=False, allow_infinity=False),
)

# Valid risk scores (0-100 inclusive integer)
risk_scores = st.integers(min_value=0, max_value=100)

# Invalid risk scores (outside 0-100 range)
invalid_risk_scores = st.one_of(
    st.integers(max_value=-1),
    st.integers(min_value=101),
)

# Risk score floats (0.0 to 100.0)
risk_score_floats = st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)

# Positive integers for IDs, dimensions, etc.
positive_integers = st.integers(min_value=1, max_value=10000)
non_negative_integers = st.integers(min_value=0, max_value=10000)

# =============================================================================
# Camera Strategies
# =============================================================================

# Valid camera names (alphanumeric with underscores and hyphens)
camera_names = st.text(
    min_size=1,
    max_size=255,
    alphabet=st.characters(
        whitelist_categories=("Lu", "Ll", "Nd"),
        whitelist_characters="-_",
    ),
).filter(lambda x: len(x.strip()) > 0 and x[0].isalpha())

# Valid camera IDs (lowercase with underscores)
camera_ids = st.from_regex(r"[a-z][a-z0-9_]{0,49}", fullmatch=True)

# Camera folder paths (valid FTP paths without traversal)
camera_folder_paths = st.from_regex(
    r"/export/foscam/[a-z][a-z0-9_]{1,30}",
    fullmatch=True,
)

# =============================================================================
# Object Type Strategies
# =============================================================================

# Common object types detected by RT-DETR
object_types = st.sampled_from(
    [
        "person",
        "vehicle",
        "car",
        "truck",
        "motorcycle",
        "bicycle",
        "dog",
        "cat",
        "bird",
        "unknown",
    ]
)

# Object type lists (for detections and alert rules)
object_type_lists = st.lists(object_types, min_size=1, max_size=5, unique=True)

# =============================================================================
# Bounding Box Strategies
# =============================================================================


@st.composite
def bbox_strategy(draw: st.DrawFn) -> dict[str, int]:
    """Generate valid bounding box coordinates.

    Returns a dict with x, y, width, height where:
    - All values are non-negative
    - x + width <= reasonable frame width (1920)
    - y + height <= reasonable frame height (1080)
    """
    x = draw(st.integers(min_value=0, max_value=1800))
    y = draw(st.integers(min_value=0, max_value=900))
    width = draw(st.integers(min_value=1, max_value=min(500, 1920 - x)))
    height = draw(st.integers(min_value=1, max_value=min(500, 1080 - y)))
    return {"x": x, "y": y, "width": width, "height": height}


@st.composite
def bbox_tuple_strategy(draw: st.DrawFn) -> tuple[int, int, int, int]:
    """Generate valid bounding box as (x, y, width, height) tuple."""
    bbox = draw(bbox_strategy())
    return (bbox["x"], bbox["y"], bbox["width"], bbox["height"])


# =============================================================================
# Timestamp Strategies
# =============================================================================

# Timezone-aware UTC timestamps (for database compatibility)
utc_timestamps = st.datetimes(
    min_value=datetime(2020, 1, 1),
    max_value=datetime(2030, 12, 31),
).map(lambda dt: dt.replace(tzinfo=UTC))


@st.composite
def ordered_timestamp_pair(draw: st.DrawFn) -> tuple[datetime, datetime]:
    """Generate two timestamps where start <= end.

    Returns (started_at, ended_at) with timezone-aware UTC timestamps.
    """
    started_at_naive = draw(
        st.datetimes(
            min_value=datetime(2020, 1, 1),
            max_value=datetime(2030, 12, 31),
        )
    )
    delta = draw(st.timedeltas(min_value=timedelta(seconds=0), max_value=timedelta(hours=24)))
    ended_at_naive = started_at_naive + delta
    return (
        started_at_naive.replace(tzinfo=UTC),
        ended_at_naive.replace(tzinfo=UTC),
    )


# =============================================================================
# Detection Strategies
# =============================================================================


@st.composite
def detection_dict_strategy(draw: st.DrawFn) -> dict[str, Any]:
    """Generate a detection dictionary matching Detection model fields.

    Returns a dict that can be unpacked to create a Detection instance.
    """
    bbox = draw(bbox_strategy())
    return {
        "camera_id": draw(camera_ids),
        "file_path": f"/export/foscam/{draw(camera_ids)}/image_{draw(positive_integers)}.jpg",
        "object_type": draw(object_types),
        "confidence": draw(confidence_scores),
        "bbox_x": bbox["x"],
        "bbox_y": bbox["y"],
        "bbox_width": bbox["width"],
        "bbox_height": bbox["height"],
        "media_type": draw(st.sampled_from(["image", "video"])),
    }


@st.composite
def detection_list_strategy(
    draw: st.DrawFn,
    min_size: int = 1,
    max_size: int = 10,
    same_camera: bool = False,
) -> list[dict[str, Any]]:
    """Generate a list of detection dictionaries.

    Args:
        min_size: Minimum number of detections
        max_size: Maximum number of detections
        same_camera: If True, all detections have the same camera_id
    """
    size = draw(st.integers(min_value=min_size, max_value=max_size))
    camera_id = draw(camera_ids) if same_camera else None

    detections = []
    for i in range(size):
        det = draw(detection_dict_strategy())
        if same_camera and camera_id:
            det["camera_id"] = camera_id
            det["file_path"] = f"/export/foscam/{camera_id}/image_{i + 1}.jpg"
        detections.append(det)

    return detections


# =============================================================================
# Event Strategies
# =============================================================================

# Risk levels as determined by LLM
risk_levels = st.sampled_from(["low", "medium", "high", "critical"])

# Batch IDs (UUID hex strings)
batch_ids = st.uuids().map(lambda u: u.hex)


@st.composite
def event_dict_strategy(draw: st.DrawFn) -> dict[str, Any]:
    """Generate an event dictionary matching Event model fields.

    Returns a dict that can be unpacked to create an Event instance.
    """
    timestamps = draw(ordered_timestamp_pair())
    return {
        "batch_id": draw(batch_ids),
        "camera_id": draw(camera_ids),
        "started_at": timestamps[0],
        "ended_at": timestamps[1],
        "risk_score": draw(risk_scores),
        "risk_level": draw(risk_levels),
        "reviewed": draw(st.booleans()),
        "is_fast_path": draw(st.booleans()),
    }


# =============================================================================
# Alert Strategies
# =============================================================================

# Alert severity levels (as strings, for database compatibility)
severity_levels = st.sampled_from(["low", "medium", "high", "critical"])

# Severity enum values (for service tests)
severity_enums = st.sampled_from([Severity.LOW, Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL])

# Notification channels
notification_channels = st.sampled_from(["push", "email", "sms", "webhook"])
channel_lists = st.lists(notification_channels, min_size=0, max_size=4, unique=True)

# Cooldown seconds (positive integers, typically 60-3600)
cooldown_seconds = st.integers(min_value=60, max_value=3600)


@st.composite
def dedup_key_strategy(draw: st.DrawFn) -> str:
    """Generate a valid deduplication key.

    Format: {camera_id}:{object_type}:{zone} or simpler variants
    Only alphanumeric, underscores, hyphens, and colons allowed.
    """
    camera_id = draw(camera_ids)
    object_type = draw(object_types)
    # Optionally include zone
    if draw(st.booleans()):
        zone = draw(st.from_regex(r"[a-z_]{1,20}", fullmatch=True))
        return f"{camera_id}:{object_type}:{zone}"
    return f"{camera_id}:{object_type}"


@st.composite
def invalid_dedup_key_strategy(draw: st.DrawFn) -> str:
    """Generate invalid deduplication keys for negative testing.

    These contain characters that are not allowed (spaces, special chars, etc.)
    """
    invalid_char = draw(
        st.sampled_from(
            [
                " ",
                "!",
                "@",
                "#",
                "$",
                "%",
                "^",
                "&",
                "*",
                "(",
                ")",
                "<",
                ">",
                "?",
                "/",
                "\\",
                "|",
                "'",
                '"',
                ";",
                ".",
                "..",
            ]
        )
    )
    base = draw(st.text(min_size=1, max_size=10))
    position = draw(st.sampled_from(["prefix", "suffix", "middle"]))

    if position == "prefix":
        return f"{invalid_char}{base}"
    elif position == "suffix":
        return f"{base}{invalid_char}"
    else:
        return f"{base[: len(base) // 2]}{invalid_char}{base[len(base) // 2 :]}"


@st.composite
def alert_rule_dict_strategy(draw: st.DrawFn) -> dict[str, Any]:
    """Generate an alert rule dictionary for testing.

    Returns a dict with alert rule configuration fields.
    """
    return {
        "name": draw(st.text(min_size=1, max_size=100).filter(lambda x: x.strip())),
        "enabled": draw(st.booleans()),
        "severity": draw(severity_levels),
        "risk_threshold": draw(st.one_of(st.none(), risk_scores)),
        "camera_ids": draw(st.one_of(st.none(), st.lists(camera_ids, min_size=1, max_size=5))),
        "object_types": draw(st.one_of(st.none(), object_type_lists)),
        "min_confidence": draw(st.one_of(st.none(), confidence_scores)),
        "cooldown_seconds": draw(cooldown_seconds),
        "channels": draw(channel_lists),
    }


# =============================================================================
# Batch Aggregation Strategies
# =============================================================================


@st.composite
def batch_summary_strategy(draw: st.DrawFn) -> dict[str, Any]:
    """Generate a batch summary dictionary.

    Returns a dict matching the format returned by BatchAggregator.close_batch().
    """
    batch_id = draw(batch_ids)
    camera_id = draw(camera_ids)
    detection_count = draw(st.integers(min_value=1, max_value=50))
    detection_ids = list(range(1, detection_count + 1))

    return {
        "batch_id": batch_id,
        "camera_id": camera_id,
        "detection_count": detection_count,
        "detections": detection_ids,
        "started_at": draw(utc_timestamps).isoformat(),
        "duration_seconds": draw(st.floats(min_value=0.1, max_value=90.0)),
    }


@st.composite
def analysis_queue_item_strategy(draw: st.DrawFn) -> dict[str, Any]:
    """Generate an analysis queue item dictionary.

    Returns a dict matching the format pushed to Redis analysis_queue.
    """
    batch_id = draw(batch_ids)
    camera_id = draw(camera_ids)
    detection_count = draw(st.integers(min_value=1, max_value=50))
    detection_ids = list(range(1, detection_count + 1))

    return {
        "batch_id": batch_id,
        "camera_id": camera_id,
        "detection_ids": detection_ids,
        "timestamp": draw(utc_timestamps).isoformat(),
        "pipeline_start_time": draw(
            st.one_of(
                st.none(),
                utc_timestamps.map(lambda dt: dt.isoformat()),
            )
        ),
    }


# =============================================================================
# Severity Threshold Strategies
# =============================================================================


@st.composite
def severity_thresholds_strategy(draw: st.DrawFn) -> dict[str, int]:
    """Generate valid severity threshold configuration.

    Returns a dict with low_max, medium_max, high_max where:
    - 0 <= low_max < medium_max < high_max < 100
    - Reasonable spacing between thresholds
    - high_max < 100 to ensure CRITICAL range (high_max+1 to 100) is valid
    """
    # Generate three distinct values in [0, 99] and sort them
    # high_max must be < 100 so CRITICAL (high_max+1 to 100) has at least score 100
    low_max = draw(st.integers(min_value=0, max_value=40))
    medium_max = draw(st.integers(min_value=low_max + 1, max_value=70))
    high_max = draw(st.integers(min_value=medium_max + 1, max_value=99))

    return {
        "low_max": low_max,
        "medium_max": medium_max,
        "high_max": high_max,
    }


@st.composite
def invalid_severity_thresholds_strategy(draw: st.DrawFn) -> dict[str, int]:
    """Generate invalid severity threshold configurations for negative testing.

    Returns thresholds that violate ordering or range constraints.
    """
    violation = draw(
        st.sampled_from(
            [
                "negative_low",
                "low_equals_medium",
                "low_greater_medium",
                "medium_equals_high",
                "medium_greater_high",
                "high_over_100",
            ]
        )
    )

    if violation == "negative_low":
        return {"low_max": -1, "medium_max": 50, "high_max": 80}
    elif violation == "low_equals_medium":
        val = draw(st.integers(min_value=0, max_value=50))
        return {"low_max": val, "medium_max": val, "high_max": 80}
    elif violation == "low_greater_medium":
        return {"low_max": 60, "medium_max": 50, "high_max": 80}
    elif violation == "medium_equals_high":
        val = draw(st.integers(min_value=30, max_value=80))
        return {"low_max": 20, "medium_max": val, "high_max": val}
    elif violation == "medium_greater_high":
        return {"low_max": 20, "medium_max": 90, "high_max": 80}
    else:  # high_over_100
        return {"low_max": 20, "medium_max": 50, "high_max": 101}


# =============================================================================
# File Hash Strategies
# =============================================================================

# SHA256 hex strings (64 characters)
sha256_hashes = st.from_regex(r"[0-9a-f]{64}", fullmatch=True)

# File paths for deduplication
file_paths = st.builds(
    lambda camera, n: f"/export/foscam/{camera}/image_{n}.jpg",
    camera=camera_ids,
    n=positive_integers,
)


# =============================================================================
# Schedule Strategies (for Alert Rules)
# =============================================================================


@st.composite
def time_string_strategy(draw: st.DrawFn) -> str:
    """Generate a valid HH:MM time string."""
    hour = draw(st.integers(min_value=0, max_value=23))
    minute = draw(st.integers(min_value=0, max_value=59))
    return f"{hour:02d}:{minute:02d}"


@st.composite
def schedule_strategy(draw: st.DrawFn) -> dict[str, Any]:
    """Generate a valid schedule configuration for alert rules.

    Returns a dict with optional start_time, end_time, days, and timezone.
    """
    schedule: dict[str, Any] = {}

    if draw(st.booleans()):
        schedule["start_time"] = draw(time_string_strategy())
        schedule["end_time"] = draw(time_string_strategy())

    if draw(st.booleans()):
        days = draw(
            st.lists(
                st.sampled_from(
                    [
                        "monday",
                        "tuesday",
                        "wednesday",
                        "thursday",
                        "friday",
                        "saturday",
                        "sunday",
                    ]
                ),
                min_size=1,
                max_size=7,
                unique=True,
            )
        )
        schedule["days"] = days

    if draw(st.booleans()):
        schedule["timezone"] = draw(
            st.sampled_from(
                [
                    "UTC",
                    "US/Eastern",
                    "US/Pacific",
                    "Europe/London",
                ]
            )
        )

    return schedule
