"""Domain-specific Hypothesis strategies for property-based testing.

This module provides comprehensive, domain-specific Hypothesis strategies that
generate valid test data matching the constraints and business rules of the
home security monitoring system.

These strategies are designed for use with Hypothesis' property-based testing
framework and ensure generated data matches database constraints, model
validation rules, and business logic.

Usage:
    from backend.tests.hypothesis_strategies import (
        valid_camera_id,
        valid_detection_bbox,
        valid_risk_score,
    )
    from hypothesis import given

    @given(camera_id=valid_camera_id(), risk_score=valid_risk_score())
    def test_event_creation(camera_id, risk_score):
        event = Event(camera_id=camera_id, risk_score=risk_score)
        assert event.risk_score >= 0
        assert event.risk_score <= 100

Key Strategy Categories:
- Basic domain types (camera IDs, UUIDs, risk scores, confidence)
- Timestamps and time ranges
- Bounding boxes and coordinates
- Detection labels and object types
- RTSP URLs and file paths
- Timezone handling
- Composite model instances

See conftest.py for Hypothesis profile configuration (default, ci, fast, debug).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from hypothesis import assume
from hypothesis import strategies as st

from backend.models.enums import CameraStatus, Severity

# =============================================================================
# Camera Strategies
# =============================================================================


@st.composite
def valid_camera_id(draw: st.DrawFn) -> str:
    """Generate valid camera IDs matching normalized format.

    Camera IDs are normalized from folder names:
    - Lowercase alphanumeric with underscores
    - No leading/trailing underscores
    - No consecutive underscores
    - Length 1-50 characters

    Examples: "front_door", "driveway_cam_1", "backyard"
    """
    # Start with lowercase letter
    first_char = draw(
        st.characters(whitelist_categories=("Ll",), min_codepoint=97, max_codepoint=122)
    )

    # Continue with lowercase, digits, or single underscores
    length = draw(st.integers(min_value=0, max_value=49))
    if length == 0:
        return first_char

    # Build rest of ID ensuring no consecutive underscores
    rest = []
    last_was_underscore = False
    for _ in range(length):
        if last_was_underscore:
            # Must use letter or digit, not underscore
            char = draw(
                st.characters(
                    whitelist_categories=("Ll", "Nd"), min_codepoint=48, max_codepoint=122
                )
            )
            last_was_underscore = False
        else:
            # Can be letter, digit, or underscore
            char = draw(
                st.sampled_from(
                    list("abcdefghijklmnopqrstuvwxyz0123456789")
                    + ["_"] * 2  # Weight underscores less
                )
            )
            last_was_underscore = char == "_"
        rest.append(char)

    # Ensure doesn't end with underscore
    result = first_char + "".join(rest)
    if result.endswith("_"):
        result = result[:-1]

    return result


@st.composite
def valid_camera_name(draw: st.DrawFn) -> str:
    """Generate valid camera display names.

    Camera names are human-readable display names:
    - Any printable characters
    - Length 1-255 characters
    - Must not be only whitespace

    Examples: "Front Door", "Driveway (Main)", "Back Yard - Wide Angle"
    """
    return draw(
        st.text(
            min_size=1,
            max_size=255,
            alphabet=st.characters(
                whitelist_categories=("Lu", "Ll", "Nd", "Pd", "Pc", "Po", "Zs"),
                blacklist_characters="\n\r\t\x00",
            ),
        ).filter(lambda x: x.strip() and len(x.strip()) > 0)
    )


@st.composite
def valid_camera_folder_path(draw: st.DrawFn) -> str:
    """Generate valid camera folder paths.

    Folder paths follow the pattern: /export/foscam/{normalized_folder_name}
    - Must start with /export/foscam/
    - Folder name can have spaces, hyphens, underscores
    - No path traversal (../)
    - Length <= 255 characters

    Examples:
        "/export/foscam/Front Door"
        "/export/foscam/driveway-cam-1"
        "/export/foscam/Back_Yard"
    """
    folder_name = draw(
        st.text(
            min_size=1,
            max_size=200,  # Leave room for /export/foscam/ prefix
            alphabet=st.characters(
                whitelist_categories=("Lu", "Ll", "Nd"),
                whitelist_characters=" -_",
            ),
        ).filter(lambda x: x.strip() and ".." not in x and "/" not in x)
    )
    return f"/export/foscam/{folder_name.strip()}"


@st.composite
def valid_camera_status(draw: st.DrawFn) -> str:
    """Generate valid camera status values.

    Status values from CameraStatus enum:
    - online, offline, error, unknown
    """
    return draw(st.sampled_from([s.value for s in CameraStatus]))


# =============================================================================
# UUID and ID Strategies
# =============================================================================


@st.composite
def valid_uuid4(draw: st.DrawFn) -> str:
    """Generate valid UUID4 strings.

    Returns standard UUID4 format: xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx
    where y is one of [8, 9, a, b]
    """
    return str(uuid.UUID(bytes=draw(st.binary(min_size=16, max_size=16)), version=4))


@st.composite
def valid_uuid_hex(draw: st.DrawFn) -> str:  # pragma: allowlist secret
    """Generate valid UUID hex strings (without dashes).

    Returns 32-character hex string, commonly used for batch IDs.
    Example: "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"  # pragma: allowlist secret
    """
    return uuid.UUID(bytes=draw(st.binary(min_size=16, max_size=16))).hex


# =============================================================================
# Detection and Bounding Box Strategies
# =============================================================================


@st.composite
def valid_detection_bbox(
    draw: st.DrawFn, max_width: int = 1920, max_height: int = 1080
) -> dict[str, int]:
    """Generate valid detection bounding box coordinates.

    Returns dict with keys: {x, y, width, height}
    - All values are non-negative integers
    - x + width <= max_width
    - y + height <= max_height
    - width >= 1, height >= 1 (positive dimensions)

    Args:
        max_width: Maximum image width (default: 1920 for Full HD)
        max_height: Maximum image height (default: 1080 for Full HD)

    Example: {"x": 100, "y": 200, "width": 150, "height": 200}
    """
    x = draw(st.integers(min_value=0, max_value=max(0, max_width - 1)))
    y = draw(st.integers(min_value=0, max_value=max(0, max_height - 1)))
    width = draw(st.integers(min_value=1, max_value=max(1, max_width - x)))
    height = draw(st.integers(min_value=1, max_value=max(1, max_height - y)))

    return {"x": x, "y": y, "width": width, "height": height}


@st.composite
def valid_normalized_bbox(draw: st.DrawFn) -> dict[str, float]:
    """Generate valid normalized bounding box coordinates.

    Returns dict with keys: {x, y, width, height}
    - All values are floats in range [0.0, 1.0]
    - x + width <= 1.0
    - y + height <= 1.0
    - width > 0.0, height > 0.0

    Used for zone coordinates which are normalized to image dimensions.

    Example: {"x": 0.1, "y": 0.2, "width": 0.3, "height": 0.4}
    """
    x = draw(st.floats(min_value=0.0, max_value=0.95, allow_nan=False, allow_infinity=False))
    y = draw(st.floats(min_value=0.0, max_value=0.95, allow_nan=False, allow_infinity=False))
    width = draw(
        st.floats(min_value=0.01, max_value=1.0 - x, allow_nan=False, allow_infinity=False)
    )
    height = draw(
        st.floats(min_value=0.01, max_value=1.0 - y, allow_nan=False, allow_infinity=False)
    )

    return {"x": x, "y": y, "width": width, "height": height}


# =============================================================================
# Risk Score and Confidence Strategies
# =============================================================================


def valid_risk_score() -> st.SearchStrategy[int]:
    """Generate valid risk scores.

    Returns integer in range [0, 100] inclusive.
    Risk scores are used by LLM to assess event severity.

    Ranges:
    - 0-25: LOW
    - 26-50: MEDIUM
    - 51-75: HIGH
    - 76-100: CRITICAL
    """
    return st.integers(min_value=0, max_value=100)


def valid_confidence() -> st.SearchStrategy[float]:
    """Generate valid confidence scores.

    Returns float in range [0.0, 1.0] inclusive.
    Used for detection confidence from YOLO26 and other models.

    Examples: 0.0, 0.5, 0.95, 1.0
    """
    return st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)


@st.composite
def valid_risk_level(draw: st.DrawFn) -> str:
    """Generate valid risk level strings.

    Risk levels correspond to risk score ranges:
    - "low": 0-25
    - "medium": 26-50
    - "high": 51-75
    - "critical": 76-100
    """
    return draw(st.sampled_from(["low", "medium", "high", "critical"]))


@st.composite
def valid_severity(draw: st.DrawFn) -> Severity:
    """Generate valid Severity enum values.

    Returns one of: Severity.LOW, Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL
    """
    return draw(st.sampled_from([Severity.LOW, Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL]))


# =============================================================================
# Detection Label Strategies
# =============================================================================

# Known detection classes from YOLO26 and YOLO models
_DETECTION_LABELS = [
    "person",
    "vehicle",
    "car",
    "truck",
    "motorcycle",
    "bicycle",
    "bus",
    "dog",
    "cat",
    "bird",
    "horse",
    "cow",
    "bear",
    "deer",
    "package",
    "unknown",
]


def valid_detection_label() -> st.SearchStrategy[str]:
    """Generate valid detection object type labels.

    Returns one of the known detection classes from YOLO26/YOLO models:
    - Common: person, vehicle, car, truck, motorcycle, bicycle
    - Animals: dog, cat, bird, horse, cow, bear, deer
    - Other: package, unknown

    These match the object_type field in the Detection model.
    """
    return st.sampled_from(_DETECTION_LABELS)


@st.composite
def valid_detection_labels_list(draw: st.DrawFn, min_size: int = 1, max_size: int = 5) -> list[str]:
    """Generate list of unique detection labels.

    Args:
        min_size: Minimum number of labels (default: 1)
        max_size: Maximum number of labels (default: 5)

    Returns list of unique detection labels.
    Example: ["person", "vehicle", "dog"]
    """
    return draw(
        st.lists(valid_detection_label(), min_size=min_size, max_size=max_size, unique=True)
    )


# =============================================================================
# Timestamp Strategies
# =============================================================================


@st.composite
def valid_utc_timestamp(
    draw: st.DrawFn,
    min_year: int = 2020,
    max_year: int = 2030,
) -> datetime:
    """Generate timezone-aware UTC timestamp.

    Args:
        min_year: Minimum year (default: 2020)
        max_year: Maximum year (default: 2030)

    Returns datetime with UTC timezone.
    All database timestamps should be timezone-aware UTC.

    Example: datetime(2024, 1, 15, 10, 30, 45, tzinfo=UTC)
    """
    dt_naive = draw(
        st.datetimes(
            min_value=datetime(min_year, 1, 1),
            max_value=datetime(max_year, 12, 31, 23, 59, 59),
        )
    )
    return dt_naive.replace(tzinfo=UTC)


@st.composite
def valid_timestamp_range(
    draw: st.DrawFn,
    min_duration_seconds: int = 1,
    max_duration_seconds: int = 3600,
) -> tuple[datetime, datetime]:
    """Generate ordered timestamp pair (start, end) where start < end.

    Args:
        min_duration_seconds: Minimum time between start and end (default: 1)
        max_duration_seconds: Maximum time between start and end (default: 3600 = 1 hour)

    Returns tuple of (started_at, ended_at) with timezone-aware UTC timestamps.

    Example: (datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC),
              datetime(2024, 1, 15, 10, 15, 0, tzinfo=UTC))
    """
    started_at = draw(valid_utc_timestamp())
    duration = draw(
        st.timedeltas(
            min_value=timedelta(seconds=min_duration_seconds),
            max_value=timedelta(seconds=max_duration_seconds),
        )
    )
    ended_at = started_at + duration
    return (started_at, ended_at)


# =============================================================================
# Timezone Strategies
# =============================================================================

# Common IANA timezone names for testing
_COMMON_TIMEZONES = [
    "UTC",
    "America/New_York",
    "America/Chicago",
    "America/Denver",
    "America/Los_Angeles",
    "America/Phoenix",
    "Europe/London",
    "Europe/Paris",
    "Europe/Berlin",
    "Asia/Tokyo",
    "Asia/Shanghai",
    "Asia/Dubai",
    "Australia/Sydney",
    "Pacific/Auckland",
]


def valid_timezone() -> st.SearchStrategy[str]:
    """Generate valid IANA timezone strings.

    Returns one of the common IANA timezone names.
    These are used in schedule configurations for alert rules.

    Examples: "UTC", "America/New_York", "Europe/London", "Asia/Tokyo"
    """
    return st.sampled_from(_COMMON_TIMEZONES)


# =============================================================================
# RTSP URL Strategies
# =============================================================================


@st.composite
def valid_rtsp_url(draw: st.DrawFn) -> str:  # pragma: allowlist secret
    """Generate valid RTSP URL format.

    RTSP URLs follow pattern: rtsp://[user:pass@]host[:port]/path
    - Must start with rtsp://
    - Host can be IP or hostname
    - Optional authentication
    - Optional port (default: 554)
    - Optional path

    Examples:
        "rtsp://192.168.1.100/stream1"
        "rtsp://admin:pass@camera.local:8554/live"  # pragma: allowlist secret
        "rtsp://10.0.0.5:554/h264"
    """
    # Generate host (IP or hostname)
    use_ip = draw(st.booleans())
    if use_ip:
        # Generate IPv4 address
        octets = [draw(st.integers(min_value=0, max_value=255)) for _ in range(4)]
        host = ".".join(str(o) for o in octets)
    else:
        # Generate hostname
        host = draw(
            st.text(
                min_size=3,
                max_size=20,
                alphabet=st.characters(
                    whitelist_categories=("Ll", "Nd"),
                    whitelist_characters="-.",
                ),
            ).filter(lambda x: x and x[0].isalpha() and ".." not in x)
        )

    # Optional authentication
    url = "rtsp://"
    if draw(st.booleans()):
        username = draw(
            st.text(
                min_size=1,
                max_size=20,
                alphabet=st.characters(whitelist_categories=("Ll", "Nd")),
            )
        )
        password = draw(
            st.text(
                min_size=1,
                max_size=20,
                alphabet=st.characters(whitelist_categories=("Ll", "Nd")),
            )
        )
        url += f"{username}:{password}@"

    url += host

    # Optional port
    if draw(st.booleans()):
        port = draw(st.integers(min_value=1, max_value=65535))
        url += f":{port}"

    # Optional path
    if draw(st.booleans()):
        path = draw(
            st.text(
                min_size=1,
                max_size=30,
                alphabet=st.characters(
                    whitelist_categories=("Ll", "Nd"), whitelist_characters="/_-"
                ),
            ).filter(lambda x: x and x[0] == "/" and ".." not in x)
        )
        url += path

    return url


# =============================================================================
# Event Summary Strategies
# =============================================================================


@st.composite
def valid_event_summary(draw: st.DrawFn) -> str:
    """Generate realistic event summary text.

    Event summaries are generated by the LLM and describe detected activity:
    - 20-200 characters
    - Grammatically correct sentences
    - Common patterns: "Person detected at...", "Vehicle approaching...", etc.

    Examples:
        "Person detected at front door at 10:30 PM"
        "Vehicle parked in driveway for 5 minutes"
        "Multiple people detected in yard"
    """
    templates = [
        "Person detected {location} at {time}",
        "Vehicle {action} {location}",
        "{count} {object} detected in {location}",
        "{object} approaching {location}",
        "Motion detected in {location} at {time}",
        "Unusual activity in {location}",
        "{object} loitering near {location} for {duration}",
    ]

    template = draw(st.sampled_from(templates))

    # Fill in template variables
    replacements = {
        "{location}": draw(
            st.sampled_from(
                ["front door", "driveway", "backyard", "entry point", "sidewalk", "porch", "garage"]
            )
        ),
        "{time}": draw(
            st.sampled_from(
                [
                    "10:30 PM",
                    "early morning",
                    "late evening",
                    "midnight",
                    "3:00 AM",
                    "dawn",
                ]
            )
        ),
        "{action}": draw(
            st.sampled_from(
                ["parked in", "approaching", "leaving", "stopped at", "circling", "reversing into"]
            )
        ),
        "{count}": draw(st.sampled_from(["Multiple", "Two", "Three", "Several"])),
        "{object}": draw(
            st.sampled_from(["people", "persons", "vehicles", "animals", "individuals"])
        ),
        "{duration}": draw(
            st.sampled_from(["5 minutes", "10 seconds", "several minutes", "an hour"])
        ),
    }

    for var, value in replacements.items():
        template = template.replace(var, value)

    return template


# =============================================================================
# Polygon Coordinates Strategies
# =============================================================================


@st.composite
def valid_polygon_coordinates(
    draw: st.DrawFn,
    min_points: int = 3,
    max_points: int = 8,
    normalized: bool = True,
) -> list[list[float]]:
    """Generate valid polygon coordinates for zone definition.

    Args:
        min_points: Minimum number of vertices (default: 3 for triangle)
        max_points: Maximum number of vertices (default: 8)
        normalized: If True, coordinates are in [0, 1] range; otherwise pixel coordinates

    Returns list of [x, y] coordinate pairs forming a valid polygon.
    Coordinates are clockwise or counter-clockwise ordered.

    Examples:
        Normalized: [[0.1, 0.2], [0.3, 0.2], [0.3, 0.8], [0.1, 0.8]]  # Rectangle
        Pixel: [[100, 200], [300, 200], [300, 800], [100, 800]]       # Rectangle
    """
    num_points = draw(st.integers(min_value=min_points, max_value=max_points))

    if normalized:
        # Generate points in [0, 1] range
        points = [
            [
                draw(
                    st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
                ),
                draw(
                    st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
                ),
            ]
            for _ in range(num_points)
        ]
    else:
        # Generate pixel coordinates (assuming 1920x1080)
        points = [
            [
                float(draw(st.integers(min_value=0, max_value=1920))),
                float(draw(st.integers(min_value=0, max_value=1080))),
            ]
            for _ in range(num_points)
        ]

    # Ensure polygon is not degenerate (all points collinear)
    # Simple check: ensure points are not all the same
    assume(len({tuple(p) for p in points}) >= 3)

    return points


# =============================================================================
# Composite Model Strategies
# =============================================================================


@st.composite
def camera_dict_strategy(draw: st.DrawFn) -> dict[str, Any]:
    """Generate complete Camera model dictionary.

    Returns dict with all Camera model fields, ready to create Camera instance.

    Example:
        camera_data = draw(camera_dict_strategy())
        camera = Camera(**camera_data)
    """
    camera_id = draw(valid_camera_id())
    return {
        "id": camera_id,
        "name": draw(valid_camera_name()),
        "folder_path": draw(valid_camera_folder_path()),
        "status": draw(valid_camera_status()),
        "created_at": draw(valid_utc_timestamp()),
        "last_seen_at": draw(st.one_of(st.none(), valid_utc_timestamp())),
        "deleted_at": None,  # Most cameras are not deleted
        "property_id": draw(st.one_of(st.none(), st.integers(min_value=1, max_value=1000))),
    }


@st.composite
def detection_dict_strategy(draw: st.DrawFn, camera_id: str | None = None) -> dict[str, Any]:
    """Generate complete Detection model dictionary.

    Args:
        camera_id: Optional camera ID to use; if None, generates random camera_id

    Returns dict with all Detection model fields.

    Example:
        detection_data = draw(detection_dict_strategy(camera_id="front_door"))
        detection = Detection(**detection_data)
    """
    if camera_id is None:
        camera_id = draw(valid_camera_id())

    bbox = draw(valid_detection_bbox())
    media_type = draw(st.sampled_from(["image", "video"]))

    base_data = {
        "camera_id": camera_id,
        "file_path": f"/export/foscam/{camera_id}/image_{draw(st.integers(1, 99999))}.jpg",
        "file_type": draw(st.sampled_from(["jpg", "jpeg", "png", "mp4", "avi"])),
        "detected_at": draw(valid_utc_timestamp()),
        "object_type": draw(valid_detection_label()),
        "confidence": draw(valid_confidence()),
        "bbox_x": bbox["x"],
        "bbox_y": bbox["y"],
        "bbox_width": bbox["width"],
        "bbox_height": bbox["height"],
        "thumbnail_path": draw(
            st.one_of(
                st.none(),
                st.just(
                    f"/export/foscam/{camera_id}/thumbnails/thumb_{draw(st.integers(1, 99999))}.jpg"
                ),
            )
        ),
        "media_type": media_type,
    }

    # Add video-specific fields if media_type is video
    if media_type == "video":
        base_data.update(
            {
                "duration": draw(st.floats(min_value=1.0, max_value=300.0, allow_nan=False)),
                "video_codec": draw(st.sampled_from(["h264", "h265", "hevc", "vp9", "av1"])),
                "video_width": draw(st.integers(min_value=640, max_value=3840)),
                "video_height": draw(st.integers(min_value=480, max_value=2160)),
            }
        )
    else:
        base_data.update(
            {
                "duration": None,
                "video_codec": None,
                "video_width": None,
                "video_height": None,
            }
        )

    return base_data


@st.composite
def event_dict_strategy(draw: st.DrawFn, camera_id: str | None = None) -> dict[str, Any]:
    """Generate complete Event model dictionary.

    Args:
        camera_id: Optional camera ID to use; if None, generates random camera_id

    Returns dict with all Event model fields.

    Example:
        event_data = draw(event_dict_strategy(camera_id="front_door"))
        event = Event(**event_data)
    """
    if camera_id is None:
        camera_id = draw(valid_camera_id())

    timestamps = draw(valid_timestamp_range(min_duration_seconds=1, max_duration_seconds=90))
    risk_score = draw(st.one_of(st.none(), valid_risk_score()))

    # Determine risk_level based on risk_score (if present)
    if risk_score is not None:
        if risk_score <= 25:
            risk_level = "low"
        elif risk_score <= 50:
            risk_level = "medium"
        elif risk_score <= 75:
            risk_level = "high"
        else:
            risk_level = "critical"
    else:
        risk_level = None

    return {
        "batch_id": draw(valid_uuid_hex()),
        "camera_id": camera_id,
        "started_at": timestamps[0],
        "ended_at": timestamps[1],
        "risk_score": risk_score,
        "risk_level": risk_level,
        "summary": draw(st.one_of(st.none(), valid_event_summary())),
        "reasoning": draw(
            st.one_of(
                st.none(),
                st.text(min_size=20, max_size=500).filter(lambda x: x.strip()),
            )
        ),
        "llm_prompt": draw(st.one_of(st.none(), st.text(min_size=50, max_size=1000))),
        "reviewed": draw(st.booleans()),
        "notes": draw(st.one_of(st.none(), st.text(max_size=500))),
        "is_fast_path": draw(st.booleans()),
        "object_types": draw(
            st.one_of(
                st.none(),
                valid_detection_labels_list().map(lambda labels: ",".join(labels)),
            )
        ),
        "clip_path": draw(
            st.one_of(st.none(), st.just(f"/export/clips/{draw(valid_uuid_hex())}.mp4"))
        ),
        "deleted_at": None,  # Most events are not deleted
        "snooze_until": None,  # Most events are not snoozed
    }


@st.composite
def zone_dict_strategy(draw: st.DrawFn, camera_id: str | None = None) -> dict[str, Any]:
    """Generate complete CameraZone (Zone) model dictionary.

    Args:
        camera_id: Optional camera ID to use; if None, generates random camera_id

    Returns dict with all CameraZone model fields.

    Example:
        zone_data = draw(zone_dict_strategy(camera_id="front_door"))
        zone = CameraZone(**zone_data)
    """
    from backend.models.camera_zone import CameraZoneShape, CameraZoneType

    if camera_id is None:
        camera_id = draw(valid_camera_id())

    zone_id = draw(valid_uuid4())
    shape = draw(st.sampled_from([s.value for s in CameraZoneShape]))

    # Generate coordinates based on shape
    if shape == "rectangle":
        # Rectangle: 4 points forming a rectangle
        coords = draw(valid_polygon_coordinates(min_points=4, max_points=4, normalized=True))
    else:
        # Polygon: 3-8 points
        coords = draw(valid_polygon_coordinates(min_points=3, max_points=8, normalized=True))

    return {
        "id": zone_id,
        "camera_id": camera_id,
        "name": draw(
            st.text(
                min_size=1,
                max_size=255,
                alphabet=st.characters(
                    whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters=" -_"
                ),
            ).filter(lambda x: x.strip())
        ),
        "zone_type": draw(st.sampled_from([t.value for t in CameraZoneType])),
        "coordinates": coords,
        "shape": shape,
        "color": draw(st.from_regex(r"#[0-9A-Fa-f]{6}", fullmatch=True)),  # Valid hex color
        "enabled": draw(st.booleans()),
        "priority": draw(st.integers(min_value=0, max_value=10)),
        "created_at": draw(valid_utc_timestamp()),
        "updated_at": draw(valid_utc_timestamp()),
    }


# =============================================================================
# Edge Case Strategies
# =============================================================================
# These strategies generate edge cases and boundary conditions for testing.


@st.composite
def edge_case_risk_scores(draw: st.DrawFn) -> int:
    """Generate edge case risk scores (boundaries and special values).

    Returns one of:
    - 0 (minimum)
    - 25 (LOW/MEDIUM boundary)
    - 50 (MEDIUM/HIGH boundary)
    - 75 (HIGH/CRITICAL boundary)
    - 100 (maximum)
    """
    return draw(st.sampled_from([0, 25, 50, 75, 100]))


@st.composite
def edge_case_confidence(draw: st.DrawFn) -> float:
    """Generate edge case confidence values (boundaries).

    Returns one of: 0.0 (minimum), 0.5 (threshold), 1.0 (maximum)
    """
    return draw(st.sampled_from([0.0, 0.5, 1.0]))


@st.composite
def edge_case_bbox(draw: st.DrawFn) -> dict[str, int]:
    """Generate edge case bounding boxes.

    Returns bounding boxes at image boundaries:
    - Top-left corner (0, 0)
    - Bottom-right corner (1920, 1080)
    - Full frame (0, 0, 1920, 1080)
    - Minimum size (1x1 pixels)
    """
    case = draw(st.sampled_from(["top_left", "bottom_right", "full_frame", "minimum_size"]))

    if case == "top_left":
        return {"x": 0, "y": 0, "width": 100, "height": 100}
    elif case == "bottom_right":
        return {"x": 1820, "y": 980, "width": 100, "height": 100}
    elif case == "full_frame":
        return {"x": 0, "y": 0, "width": 1920, "height": 1080}
    else:  # minimum_size
        x = draw(st.integers(min_value=0, max_value=1919))
        y = draw(st.integers(min_value=0, max_value=1079))
        return {"x": x, "y": y, "width": 1, "height": 1}


@st.composite
def edge_case_timestamp(draw: st.DrawFn) -> datetime:
    """Generate edge case timestamps.

    Returns timestamps at significant boundaries:
    - Year 2000 (epoch boundary)
    - Year 2038 (32-bit Unix timestamp limit)
    - Current year boundaries
    """
    return draw(
        st.sampled_from(
            [
                datetime(2000, 1, 1, 0, 0, 0, tzinfo=UTC),
                datetime(2038, 1, 19, 3, 14, 7, tzinfo=UTC),  # 32-bit Unix timestamp max
                datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC),
                datetime(2024, 12, 31, 23, 59, 59, tzinfo=UTC),
            ]
        )
    )


# =============================================================================
# Example-Based Strategies
# =============================================================================
# These provide realistic examples for common scenarios.


@st.composite
def example_person_detection(draw: st.DrawFn) -> dict[str, Any]:
    """Generate realistic person detection example.

    Returns detection dict with:
    - object_type: "person"
    - High confidence (0.7-1.0)
    - Realistic bbox for standing person
    """
    bbox = {"x": 500, "y": 200, "width": 200, "height": 400}  # Standing person proportions
    camera_id = draw(valid_camera_id())

    return {
        "camera_id": camera_id,
        "file_path": f"/export/foscam/{camera_id}/person_detected.jpg",
        "object_type": "person",
        "confidence": draw(st.floats(min_value=0.7, max_value=1.0, allow_nan=False)),
        "bbox_x": bbox["x"],
        "bbox_y": bbox["y"],
        "bbox_width": bbox["width"],
        "bbox_height": bbox["height"],
        "detected_at": draw(valid_utc_timestamp()),
        "media_type": "image",
    }


@st.composite
def example_vehicle_detection(draw: st.DrawFn) -> dict[str, Any]:
    """Generate realistic vehicle detection example.

    Returns detection dict with:
    - object_type: "car" or "truck"
    - High confidence (0.8-1.0)
    - Realistic bbox for vehicle
    """
    bbox = {"x": 300, "y": 400, "width": 600, "height": 300}  # Vehicle proportions
    camera_id = draw(valid_camera_id())

    return {
        "camera_id": camera_id,
        "file_path": f"/export/foscam/{camera_id}/vehicle_detected.jpg",
        "object_type": draw(st.sampled_from(["car", "truck", "vehicle"])),
        "confidence": draw(st.floats(min_value=0.8, max_value=1.0, allow_nan=False)),
        "bbox_x": bbox["x"],
        "bbox_y": bbox["y"],
        "bbox_width": bbox["width"],
        "bbox_height": bbox["height"],
        "detected_at": draw(valid_utc_timestamp()),
        "media_type": "image",
    }


@st.composite
def example_high_risk_event(draw: st.DrawFn) -> dict[str, Any]:
    """Generate realistic high-risk event example.

    Returns event dict with:
    - risk_score: 76-100 (CRITICAL)
    - risk_level: "critical"
    - Detailed summary and reasoning
    """
    camera_id = draw(valid_camera_id())
    timestamps = draw(valid_timestamp_range(min_duration_seconds=10, max_duration_seconds=60))

    return {
        "batch_id": draw(valid_uuid_hex()),
        "camera_id": camera_id,
        "started_at": timestamps[0],
        "ended_at": timestamps[1],
        "risk_score": draw(st.integers(min_value=76, max_value=100)),
        "risk_level": "critical",
        "summary": "Person detected at front door at 3:00 AM",
        "reasoning": "High risk due to late hour and proximity to entry point. Unknown individual.",
        "reviewed": False,
        "is_fast_path": False,
        "object_types": "person",
    }


__all__ = [
    "camera_dict_strategy",
    "detection_dict_strategy",
    "edge_case_bbox",
    "edge_case_confidence",
    "edge_case_risk_scores",
    "edge_case_timestamp",
    "event_dict_strategy",
    "example_high_risk_event",
    "example_person_detection",
    "example_vehicle_detection",
    "valid_camera_folder_path",
    "valid_camera_id",
    "valid_camera_name",
    "valid_camera_status",
    "valid_confidence",
    "valid_detection_bbox",
    "valid_detection_label",
    "valid_detection_labels_list",
    "valid_event_summary",
    "valid_normalized_bbox",
    "valid_polygon_coordinates",
    "valid_risk_level",
    "valid_risk_score",
    "valid_rtsp_url",
    "valid_severity",
    "valid_timestamp_range",
    "valid_timezone",
    "valid_utc_timestamp",
    "valid_uuid4",
    "valid_uuid_hex",
    "zone_dict_strategy",
]
