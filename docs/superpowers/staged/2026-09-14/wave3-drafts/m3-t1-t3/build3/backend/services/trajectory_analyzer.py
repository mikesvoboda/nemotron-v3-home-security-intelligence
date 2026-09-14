"""Temporal trajectory analysis for enriching Nemotron LLM context.

This module provides the TrajectoryAnalyzer class that analyzes track trajectories
from YOLO26 to extract movement patterns and behavioral context. The analysis
results are fed to the Nemotron LLM as additional context for risk assessment.

Movement Pattern Classification:
    - stationary: < 5 pixels movement over 10+ seconds
    - approaching: Moving toward camera/entry point (decreasing distance to zone center)
    - departing: Moving away from camera/entry point
    - wandering: Non-directed movement, no consistent direction
    - circling: Returns to within 20% of starting position after movement

Integration:
    Wired into the enrichment pipeline Phase 2 via _run_parallel_enrichment().
    Results are stored in EnrichmentResult.trajectory_analysis and formatted
    by format_trajectory_context() in prompts.py for the Nemotron prompt.

See also:
    - backend/services/track_service.py: Trajectory point storage
    - backend/services/dwell_time_service.py: Existing dwell time logic
    - backend/services/enrichment_pipeline.py: Integration point
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from backend.core.logging import get_logger

logger = get_logger(__name__)

# Movement classification thresholds
STATIONARY_PIXEL_THRESHOLD = 5.0  # Max pixels moved to be "stationary"
STATIONARY_MIN_DURATION = 10.0  # Min seconds for stationary classification
CIRCLING_RETURN_THRESHOLD = 0.20  # Return to within 20% of total distance from start
APPROACH_CONSISTENCY_THRESHOLD = 0.6  # 60% of segments must show decreasing distance
DEPART_CONSISTENCY_THRESHOLD = 0.6  # 60% of segments must show increasing distance
MIN_MOVEMENT_FOR_PATTERN = 10.0  # Min pixels of total movement for non-stationary classification


@dataclass
class TrajectoryAnalysis:
    """Result of trajectory analysis for a single tracked object.

    Attributes:
        track_id: The track ID from YOLO26 tracker
        dwell_seconds: Time spent at current location / in view
        movement_pattern: Classified movement pattern
        speed_estimate: Average speed in pixels/second
        zone_transitions: List of zones entered/exited (e.g., ["entered Driveway", "exited Sidewalk"])
        is_approaching_entry: Whether the object is moving toward an entry point zone
        trajectory_summary: Human-readable summary for Nemotron context
    """

    track_id: int
    dwell_seconds: float = 0.0
    movement_pattern: str = "unknown"
    speed_estimate: float = 0.0
    zone_transitions: list[str] = field(default_factory=list)
    is_approaching_entry: bool = False
    trajectory_summary: str = ""


class TrajectoryAnalyzer:
    """Analyzer for object track trajectories.

    Processes trajectory point data from the track service to extract
    movement patterns, speed estimates, and zone transitions that
    provide behavioral context for Nemotron risk assessment.

    Example:
        analyzer = TrajectoryAnalyzer()
        analysis = analyzer.analyze_trajectory(
            track_id=42,
            track_points=[
                {"x": 100, "y": 200, "timestamp": "2026-01-26T12:00:00Z"},
                {"x": 110, "y": 210, "timestamp": "2026-01-26T12:00:05Z"},
            ],
            zones=[{"name": "Front Porch", "zone_type": "entry_point",
                    "coordinates": [[0.1, 0.2], [0.3, 0.2], [0.3, 0.8], [0.1, 0.8]]}],
        )
    """

    @staticmethod
    def analyze_trajectory(
        track_id: int,
        track_points: list[dict[str, Any]],
        zones: list[dict[str, Any]] | None = None,
        object_class: str = "unknown",
        video_width: int | None = None,
        video_height: int | None = None,
    ) -> TrajectoryAnalysis:
        """Analyze a trajectory to extract movement patterns and context.

        Args:
            track_id: Track ID from the tracker
            track_points: List of trajectory point dicts with x, y, timestamp keys.
                Coordinates are in pixels. Timestamps are ISO 8601 strings or datetimes.
            zones: Optional list of zone dicts with name, zone_type, and coordinates
                (normalized 0-1 range). Used for zone transition detection and
                entry point approach analysis.
            object_class: Object class (e.g., "person", "car") for summary context
            video_width: Video frame width in pixels (for normalizing coordinates
                when checking zone containment). If None, zone checks are skipped.
            video_height: Video frame height in pixels. If None, zone checks are skipped.

        Returns:
            TrajectoryAnalysis with movement pattern classification, speed estimate,
            zone transitions, and a human-readable summary.
        """
        result = TrajectoryAnalysis(track_id=track_id)

        if not track_points:
            result.movement_pattern = "unknown"
            result.trajectory_summary = (
                f"{object_class.capitalize()} #{track_id}: no trajectory data available."
            )
            return result

        if len(track_points) < 2:
            result.movement_pattern = "stationary"
            result.trajectory_summary = (
                f"{object_class.capitalize()} #{track_id}: single observation, stationary."
            )
            return result

        # Parse timestamps
        timestamps = _parse_timestamps(track_points)
        if not timestamps:
            result.movement_pattern = "unknown"
            result.trajectory_summary = (
                f"{object_class.capitalize()} #{track_id}: could not parse trajectory timestamps."
            )
            return result

        # Calculate basic metrics
        duration = (timestamps[-1] - timestamps[0]).total_seconds()
        result.dwell_seconds = max(duration, 0.0)

        total_distance = _calculate_total_distance(track_points)
        result.speed_estimate = round(total_distance / duration, 2) if duration > 0 else 0.0

        # Classify movement pattern
        result.movement_pattern = _classify_movement(
            track_points, total_distance, duration, zones, video_width, video_height
        )

        # Detect zone transitions
        if zones and video_width and video_height:
            result.zone_transitions = _detect_zone_transitions(
                track_points, zones, video_width, video_height
            )
            result.is_approaching_entry = _is_approaching_entry_point(
                track_points, zones, video_width, video_height
            )

        # Build human-readable summary
        result.trajectory_summary = _build_summary(
            track_id=track_id,
            object_class=object_class,
            analysis=result,
        )

        return result


def _parse_timestamps(track_points: list[dict[str, Any]]) -> list[datetime]:
    """Parse timestamps from trajectory points.

    Args:
        track_points: List of trajectory point dicts with timestamp key.

    Returns:
        List of parsed datetime objects. Empty list if parsing fails.
    """
    timestamps: list[datetime] = []
    for point in track_points:
        ts = point.get("timestamp")
        if ts is None:
            continue
        if isinstance(ts, datetime):
            timestamps.append(ts)
        elif isinstance(ts, str):
            try:
                timestamps.append(datetime.fromisoformat(ts))
            except (ValueError, TypeError):
                logger.debug(f"Failed to parse trajectory timestamp: {ts}")
                continue
    return timestamps


def _calculate_total_distance(track_points: list[dict[str, Any]]) -> float:
    """Calculate total Euclidean distance traveled across trajectory points.

    Args:
        track_points: List of trajectory point dicts with x, y keys.

    Returns:
        Total distance in pixels.
    """
    total = 0.0
    for i in range(1, len(track_points)):
        dx = track_points[i]["x"] - track_points[i - 1]["x"]
        dy = track_points[i]["y"] - track_points[i - 1]["y"]
        total += math.sqrt(dx * dx + dy * dy)
    return total


def _classify_movement(
    track_points: list[dict[str, Any]],
    total_distance: float,
    duration: float,
    zones: list[dict[str, Any]] | None,
    video_width: int | None,
    video_height: int | None,
) -> str:
    """Classify the movement pattern from trajectory data.

    Classification priority:
    1. Stationary: < 5 pixels movement over 10+ seconds
    2. Circling: Returns to within 20% of total distance from starting position
    3. Approaching: Consistently decreasing distance to an entry point zone center
    4. Departing: Consistently increasing distance to an entry point zone center
    5. Wandering: Default for non-directed movement

    Args:
        track_points: List of trajectory points
        total_distance: Pre-calculated total distance in pixels
        duration: Duration in seconds
        zones: Optional zone data for approach/depart detection
        video_width: Frame width for coordinate normalization
        video_height: Frame height for coordinate normalization

    Returns:
        Movement pattern string.
    """
    # Check stationary
    if total_distance < STATIONARY_PIXEL_THRESHOLD and duration >= STATIONARY_MIN_DURATION:
        return "stationary"

    # Need enough movement to classify non-stationary patterns
    if total_distance < MIN_MOVEMENT_FOR_PATTERN:
        if duration >= STATIONARY_MIN_DURATION:
            return "stationary"
        return "unknown"

    # Check circling: did the object return near its starting position?
    start_x, start_y = track_points[0]["x"], track_points[0]["y"]
    end_x, end_y = track_points[-1]["x"], track_points[-1]["y"]
    return_distance = math.sqrt((end_x - start_x) ** 2 + (end_y - start_y) ** 2)

    if total_distance > MIN_MOVEMENT_FOR_PATTERN and return_distance <= (
        total_distance * CIRCLING_RETURN_THRESHOLD
    ):
        return "circling"

    # Check approaching/departing relative to entry point zones
    if zones and video_width and video_height:
        entry_zones = [z for z in zones if z.get("zone_type") == "entry_point"]
        if entry_zones:
            direction = _check_approach_depart(track_points, entry_zones, video_width, video_height)
            if direction:
                return direction

    # Default: wandering (non-directed movement)
    return "wandering"


def _check_approach_depart(
    track_points: list[dict[str, Any]],
    entry_zones: list[dict[str, Any]],
    video_width: int,
    video_height: int,
) -> str | None:
    """Check if trajectory shows consistent approach or departure from entry zones.

    Calculates the distance from each trajectory point to the nearest entry zone
    center, then checks if the distances are consistently decreasing (approaching)
    or increasing (departing).

    Args:
        track_points: Trajectory points in pixel coordinates
        entry_zones: Entry point zone definitions
        video_width: Frame width for denormalizing zone coordinates
        video_height: Frame height for denormalizing zone coordinates

    Returns:
        "approaching" or "departing" if consistent, None otherwise.
    """
    if len(track_points) < 3:
        return None

    # Calculate zone centers in pixel coordinates
    zone_centers = []
    for zone in entry_zones:
        coords = zone.get("coordinates", [])
        if not coords:
            continue
        cx = sum(p[0] for p in coords) / len(coords) * video_width
        cy = sum(p[1] for p in coords) / len(coords) * video_height
        zone_centers.append((cx, cy))

    if not zone_centers:
        return None

    # Calculate distance from each trajectory point to nearest zone center
    distances = []
    for point in track_points:
        px, py = point["x"], point["y"]
        min_dist = min(math.sqrt((px - cx) ** 2 + (py - cy) ** 2) for cx, cy in zone_centers)
        distances.append(min_dist)

    # Check for consistent decrease (approaching) or increase (departing)
    decreasing = 0
    increasing = 0
    total_segments = len(distances) - 1

    for i in range(1, len(distances)):
        if distances[i] < distances[i - 1]:
            decreasing += 1
        elif distances[i] > distances[i - 1]:
            increasing += 1

    if total_segments > 0:
        if decreasing / total_segments >= APPROACH_CONSISTENCY_THRESHOLD:
            return "approaching"
        if increasing / total_segments >= DEPART_CONSISTENCY_THRESHOLD:
            return "departing"

    return None


def _point_in_polygon(
    px: float,
    py: float,
    polygon: list[list[float]],
) -> bool:
    """Check if a point is inside a polygon using ray casting algorithm.

    Args:
        px: Point x coordinate (normalized 0-1)
        py: Point y coordinate (normalized 0-1)
        polygon: List of [x, y] coordinate pairs (normalized 0-1)

    Returns:
        True if point is inside polygon.
    """
    n = len(polygon)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def _detect_zone_transitions(
    track_points: list[dict[str, Any]],
    zones: list[dict[str, Any]],
    video_width: int,
    video_height: int,
) -> list[str]:
    """Detect zone entry/exit transitions across the trajectory.

    Checks which zone each trajectory point falls in and records transitions.

    Args:
        track_points: Trajectory points in pixel coordinates
        zones: Zone definitions with name, zone_type, coordinates (normalized)
        video_width: Frame width for normalizing pixel coordinates
        video_height: Frame height for normalizing pixel coordinates

    Returns:
        List of transition strings, e.g., ["entered Driveway", "exited Sidewalk"]
    """
    if not zones or not track_points:
        return []

    transitions: list[str] = []
    # Track which zones each point is in
    prev_in_zones: set[str] = set()

    for i, point in enumerate(track_points):
        # Normalize pixel coordinates to 0-1 range for zone polygon check
        norm_x = point["x"] / video_width
        norm_y = point["y"] / video_height

        current_in_zones: set[str] = set()
        for zone in zones:
            coords = zone.get("coordinates", [])
            if not coords:
                continue
            if _point_in_polygon(norm_x, norm_y, coords):
                zone_name = zone.get("name", "Unknown")
                current_in_zones.add(zone_name)

        if i > 0:
            # Detect entries (zones in current but not in previous)
            entered = current_in_zones - prev_in_zones
            for zone_name in sorted(entered):
                transitions.append(f"entered {zone_name}")

            # Detect exits (zones in previous but not in current)
            exited = prev_in_zones - current_in_zones
            for zone_name in sorted(exited):
                transitions.append(f"exited {zone_name}")

        prev_in_zones = current_in_zones

    return transitions


def _is_approaching_entry_point(
    track_points: list[dict[str, Any]],
    zones: list[dict[str, Any]],
    video_width: int,
    video_height: int,
) -> bool:
    """Check if the trajectory is moving toward any entry point zone.

    Uses the last few trajectory points to determine if the object
    is getting closer to an entry point zone center.

    Args:
        track_points: Trajectory points in pixel coordinates
        zones: Zone definitions
        video_width: Frame width
        video_height: Frame height

    Returns:
        True if approaching an entry point.
    """
    entry_zones = [z for z in zones if z.get("zone_type") == "entry_point"]
    if not entry_zones or len(track_points) < 2:
        return False

    # Calculate zone centers in pixel coords
    zone_centers = []
    for zone in entry_zones:
        coords = zone.get("coordinates", [])
        if not coords:
            continue
        cx = sum(p[0] for p in coords) / len(coords) * video_width
        cy = sum(p[1] for p in coords) / len(coords) * video_height
        zone_centers.append((cx, cy))

    if not zone_centers:
        return False

    # Use the last few points (up to 5) to determine recent direction
    recent_points = track_points[-min(5, len(track_points)) :]
    if len(recent_points) < 2:
        return False

    # Calculate distance from first and last of recent points to nearest entry zone
    def min_dist_to_entries(px: float, py: float) -> float:
        return min(math.sqrt((px - cx) ** 2 + (py - cy) ** 2) for cx, cy in zone_centers)

    first_dist = min_dist_to_entries(recent_points[0]["x"], recent_points[0]["y"])
    last_dist = min_dist_to_entries(recent_points[-1]["x"], recent_points[-1]["y"])

    # Approaching if distance is decreasing
    return last_dist < first_dist


def _describe_speed(speed_px_per_sec: float) -> str:
    """Convert pixel-per-second speed to a human-readable description.

    These thresholds are approximate, assuming typical residential camera
    resolution (1920x1080) where a person occupies ~100-200 pixels height.

    Args:
        speed_px_per_sec: Speed in pixels per second.

    Returns:
        Human-readable speed description.
    """
    if speed_px_per_sec < 5:
        return "stationary"
    elif speed_px_per_sec < 30:
        return "slow (walking pace)"
    elif speed_px_per_sec < 80:
        return "moderate (brisk walk)"
    elif speed_px_per_sec < 150:
        return "fast (running)"
    else:
        return "very fast (vehicle speed)"


def _build_summary(
    track_id: int,
    object_class: str,
    analysis: TrajectoryAnalysis,
) -> str:
    """Build a human-readable trajectory summary for Nemotron context.

    Args:
        track_id: Track ID
        object_class: Object class (e.g., "person")
        analysis: The computed trajectory analysis

    Returns:
        Formatted summary string.

    Example:
        "Person #42: stationary at Front Porch (entry_point) for 45s.
         Speed: stationary. Approached from Sidewalk zone."
    """
    parts: list[str] = []

    # Object identification
    class_label = object_class.capitalize()

    # Movement pattern and duration
    pattern = analysis.movement_pattern
    dwell = analysis.dwell_seconds

    if dwell > 0:
        dwell_str = f"{dwell:.0f}s" if dwell < 3600 else f"{dwell / 60:.0f}min"
        parts.append(f"{class_label} #{track_id}: {pattern} for {dwell_str}")
    else:
        parts.append(f"{class_label} #{track_id}: {pattern}")

    # Speed
    speed_desc = _describe_speed(analysis.speed_estimate)
    parts.append(f"Speed: {speed_desc}")

    # Zone transitions
    if analysis.zone_transitions:
        parts.append(f"Zone activity: {', '.join(analysis.zone_transitions)}")

    # Entry point approach warning
    if analysis.is_approaching_entry:
        parts.append("WARNING: approaching entry point")

    return ". ".join(parts) + "."
