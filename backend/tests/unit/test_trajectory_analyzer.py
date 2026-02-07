"""Tests for backend.services.trajectory_analyzer (NEM-5532).

Tests movement pattern classification, zone transition detection,
speed estimation, and the format_trajectory_context prompt function.
"""

from __future__ import annotations

import pytest

from backend.services.prompts import format_trajectory_context
from backend.services.trajectory_analyzer import (
    TrajectoryAnalysis,
    TrajectoryAnalyzer,
    _build_summary,
    _calculate_total_distance,
    _classify_movement,
    _describe_speed,
    _detect_zone_transitions,
    _is_approaching_entry_point,
    _parse_timestamps,
    _point_in_polygon,
)

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _make_points(
    coords: list[tuple[float, float]],
    start_ts: str = "2026-01-26T12:00:00+00:00",
    interval_s: int = 5,
) -> list[dict]:
    """Build trajectory points with evenly-spaced timestamps."""
    from datetime import datetime, timedelta

    base = datetime.fromisoformat(start_ts)
    points = []
    for i, (x, y) in enumerate(coords):
        points.append(
            {
                "x": x,
                "y": y,
                "timestamp": (base + timedelta(seconds=i * interval_s)).isoformat(),
            }
        )
    return points


def _make_entry_zone(
    name: str = "Front Door",
    coords: list[list[float]] | None = None,
) -> dict:
    """Create an entry_point zone definition."""
    if coords is None:
        coords = [[0.4, 0.4], [0.6, 0.4], [0.6, 0.6], [0.4, 0.6]]
    return {
        "name": name,
        "zone_type": "entry_point",
        "coordinates": coords,
    }


def _make_zone(
    name: str = "Driveway",
    zone_type: str = "driveway",
    coords: list[list[float]] | None = None,
) -> dict:
    if coords is None:
        coords = [[0.0, 0.0], [0.3, 0.0], [0.3, 0.3], [0.0, 0.3]]
    return {
        "name": name,
        "zone_type": zone_type,
        "coordinates": coords,
    }


# ===========================================================================
# TrajectoryAnalysis dataclass tests
# ===========================================================================


class TestTrajectoryAnalysis:
    def test_defaults(self):
        a = TrajectoryAnalysis(track_id=1)
        assert a.track_id == 1
        assert a.dwell_seconds == 0.0
        assert a.movement_pattern == "unknown"
        assert a.speed_estimate == 0.0
        assert a.zone_transitions == []
        assert a.is_approaching_entry is False
        assert a.trajectory_summary == ""


# ===========================================================================
# _parse_timestamps
# ===========================================================================


class TestParseTimestamps:
    def test_iso_strings(self):
        points = _make_points([(0, 0), (1, 1)])
        ts = _parse_timestamps(points)
        assert len(ts) == 2

    def test_datetime_objects(self):
        from datetime import UTC, datetime

        now = datetime.now(UTC)
        points = [{"x": 0, "y": 0, "timestamp": now}]
        ts = _parse_timestamps(points)
        assert len(ts) == 1
        assert ts[0] == now

    def test_missing_timestamp(self):
        points = [{"x": 0, "y": 0}]
        ts = _parse_timestamps(points)
        assert len(ts) == 0

    def test_invalid_timestamp(self):
        points = [{"x": 0, "y": 0, "timestamp": "not-a-date"}]
        ts = _parse_timestamps(points)
        assert len(ts) == 0


# ===========================================================================
# _calculate_total_distance
# ===========================================================================


class TestCalculateTotalDistance:
    def test_straight_line(self):
        points = _make_points([(0, 0), (3, 4)])
        dist = _calculate_total_distance(points)
        assert dist == pytest.approx(5.0)

    def test_multi_segment(self):
        points = _make_points([(0, 0), (3, 4), (6, 8)])
        dist = _calculate_total_distance(points)
        assert dist == pytest.approx(10.0)

    def test_no_movement(self):
        points = _make_points([(5, 5), (5, 5), (5, 5)])
        dist = _calculate_total_distance(points)
        assert dist == 0.0


# ===========================================================================
# _point_in_polygon
# ===========================================================================


class TestPointInPolygon:
    def test_inside(self):
        polygon = [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]]
        assert _point_in_polygon(0.5, 0.5, polygon) is True

    def test_outside(self):
        polygon = [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]]
        assert _point_in_polygon(1.5, 0.5, polygon) is False

    def test_triangle(self):
        polygon = [[0.0, 0.0], [1.0, 0.0], [0.5, 1.0]]
        assert _point_in_polygon(0.5, 0.3, polygon) is True
        assert _point_in_polygon(0.9, 0.9, polygon) is False


# ===========================================================================
# Movement Pattern Classification
# ===========================================================================


class TestClassifyMovement:
    def test_stationary(self):
        """< 5 pixels movement over 10+ seconds => stationary."""
        # 3 points, barely moving, 15 seconds total
        points = _make_points([(100, 200), (101, 200), (102, 201)], interval_s=5)
        total_dist = _calculate_total_distance(points)
        # total_dist < 5 and duration = 10s
        pattern = _classify_movement(points, total_dist, 10.0, None, None, None)
        assert pattern == "stationary"

    def test_circling(self):
        """Returns near starting position after movement => circling."""
        # Move out and come back
        points = _make_points(
            [(100, 100), (200, 100), (200, 200), (100, 200), (105, 105)],
            interval_s=5,
        )
        total_dist = _calculate_total_distance(points)
        # Should be > MIN_MOVEMENT_FOR_PATTERN and end near start
        pattern = _classify_movement(points, total_dist, 20.0, None, None, None)
        assert pattern == "circling"

    def test_approaching_entry_point(self):
        """Moving consistently toward entry point zone => approaching."""
        entry_zone = _make_entry_zone(
            coords=[[0.45, 0.45], [0.55, 0.45], [0.55, 0.55], [0.45, 0.55]]
        )
        # Moving from (100, 100) toward (500, 500) which is zone center at (0.5, 0.5) * 1000
        points = _make_points(
            [(100, 100), (200, 200), (300, 300), (400, 400), (450, 450)],
            interval_s=3,
        )
        total_dist = _calculate_total_distance(points)
        pattern = _classify_movement(points, total_dist, 12.0, [entry_zone], 1000, 1000)
        assert pattern == "approaching"

    def test_departing_entry_point(self):
        """Moving consistently away from entry point zone => departing."""
        entry_zone = _make_entry_zone(
            coords=[[0.05, 0.05], [0.15, 0.05], [0.15, 0.15], [0.05, 0.15]]
        )
        # zone center at (100, 100), moving from (150, 150) away to (800, 800)
        points = _make_points(
            [(150, 150), (300, 300), (500, 500), (700, 700), (800, 800)],
            interval_s=3,
        )
        total_dist = _calculate_total_distance(points)
        pattern = _classify_movement(points, total_dist, 12.0, [entry_zone], 1000, 1000)
        assert pattern == "departing"

    def test_wandering(self):
        """Non-directed movement without consistent pattern => wandering."""
        # Zig-zag pattern, not returning to start, no entry zones
        points = _make_points(
            [(100, 100), (200, 50), (150, 200), (250, 150), (300, 250)],
            interval_s=3,
        )
        total_dist = _calculate_total_distance(points)
        pattern = _classify_movement(points, total_dist, 12.0, None, None, None)
        assert pattern == "wandering"

    def test_unknown_short_duration_low_movement(self):
        """Low movement over short time => unknown."""
        points = _make_points([(100, 100), (103, 102)], interval_s=2)
        total_dist = _calculate_total_distance(points)
        # total_dist ~= 3.6, duration = 2s
        pattern = _classify_movement(points, total_dist, 2.0, None, None, None)
        assert pattern == "unknown"


# ===========================================================================
# Zone Transitions
# ===========================================================================


class TestDetectZoneTransitions:
    def test_enter_zone(self):
        """Entering a zone should be detected."""
        zone = _make_zone("Driveway", coords=[[0.4, 0.4], [0.6, 0.4], [0.6, 0.6], [0.4, 0.6]])
        # First point outside, second point inside
        points = _make_points([(100, 100), (500, 500)], interval_s=5)
        transitions = _detect_zone_transitions(points, [zone], 1000, 1000)
        assert "entered Driveway" in transitions

    def test_exit_zone(self):
        """Exiting a zone should be detected."""
        zone = _make_zone("Driveway", coords=[[0.0, 0.0], [0.3, 0.0], [0.3, 0.3], [0.0, 0.3]])
        # First point inside (100,100) in zone (0-300, 0-300), second outside
        points = _make_points([(100, 100), (500, 500)], interval_s=5)
        transitions = _detect_zone_transitions(points, [zone], 1000, 1000)
        assert "exited Driveway" in transitions

    def test_no_zones(self):
        points = _make_points([(100, 100), (500, 500)])
        transitions = _detect_zone_transitions(points, [], 1000, 1000)
        assert transitions == []


# ===========================================================================
# _is_approaching_entry_point
# ===========================================================================


class TestIsApproachingEntryPoint:
    def test_approaching(self):
        entry_zone = _make_entry_zone(
            coords=[[0.45, 0.45], [0.55, 0.45], [0.55, 0.55], [0.45, 0.55]]
        )
        points = _make_points([(100, 100), (200, 200), (300, 300), (400, 400)], interval_s=3)
        assert _is_approaching_entry_point(points, [entry_zone], 1000, 1000) is True

    def test_not_approaching(self):
        entry_zone = _make_entry_zone(
            coords=[[0.05, 0.05], [0.15, 0.05], [0.15, 0.15], [0.05, 0.15]]
        )
        # Moving away from zone center at (100, 100)
        points = _make_points([(200, 200), (400, 400), (600, 600), (800, 800)], interval_s=3)
        assert _is_approaching_entry_point(points, [entry_zone], 1000, 1000) is False

    def test_no_entry_zones(self):
        zone = _make_zone("Yard", zone_type="yard")
        points = _make_points([(100, 100), (500, 500)], interval_s=5)
        assert _is_approaching_entry_point(points, [zone], 1000, 1000) is False


# ===========================================================================
# _describe_speed
# ===========================================================================


class TestDescribeSpeed:
    def test_stationary(self):
        assert _describe_speed(2) == "stationary"

    def test_walking(self):
        assert _describe_speed(15) == "slow (walking pace)"

    def test_brisk(self):
        assert _describe_speed(50) == "moderate (brisk walk)"

    def test_running(self):
        assert _describe_speed(100) == "fast (running)"

    def test_vehicle(self):
        assert _describe_speed(200) == "very fast (vehicle speed)"


# ===========================================================================
# TrajectoryAnalyzer.analyze_trajectory (integration tests)
# ===========================================================================


class TestAnalyzeTrajectory:
    def test_empty_points(self):
        result = TrajectoryAnalyzer.analyze_trajectory(track_id=1, track_points=[])
        assert result.movement_pattern == "unknown"
        assert result.track_id == 1
        assert "no trajectory data" in result.trajectory_summary.lower()

    def test_single_point(self):
        points = _make_points([(100, 200)])
        result = TrajectoryAnalyzer.analyze_trajectory(track_id=5, track_points=points)
        assert result.movement_pattern == "stationary"
        assert result.track_id == 5

    def test_stationary_person(self):
        """Person barely moving for 15 seconds."""
        points = _make_points(
            [(100, 200), (101, 200), (100, 201), (101, 201)],
            interval_s=5,
        )
        result = TrajectoryAnalyzer.analyze_trajectory(
            track_id=42, track_points=points, object_class="person"
        )
        assert result.movement_pattern == "stationary"
        assert result.dwell_seconds == pytest.approx(15.0)
        assert result.speed_estimate < 1.0
        assert "Person" in result.trajectory_summary

    def test_walking_person(self):
        """Person walking at a moderate pace."""
        points = _make_points(
            [(100, 100), (150, 120), (200, 140), (250, 160), (300, 180)],
            interval_s=3,
        )
        result = TrajectoryAnalyzer.analyze_trajectory(
            track_id=10, track_points=points, object_class="person"
        )
        # Should not be stationary
        assert result.movement_pattern in ("wandering", "approaching", "departing")
        assert result.speed_estimate > 5.0
        assert result.dwell_seconds > 0

    def test_with_zones(self):
        """Analysis with zone data should detect zone transitions."""
        zone = _make_zone("Driveway", coords=[[0.0, 0.0], [0.3, 0.0], [0.3, 0.3], [0.0, 0.3]])
        entry = _make_entry_zone(coords=[[0.8, 0.8], [1.0, 0.8], [1.0, 1.0], [0.8, 1.0]])

        # Start in driveway, move to entry point
        points = _make_points(
            [(100, 100), (300, 300), (500, 500), (700, 700), (900, 900)],
            interval_s=3,
        )
        result = TrajectoryAnalyzer.analyze_trajectory(
            track_id=7,
            track_points=points,
            zones=[zone, entry],
            object_class="person",
            video_width=1000,
            video_height=1000,
        )
        # Should detect zone transitions
        assert len(result.zone_transitions) > 0
        assert result.is_approaching_entry is True

    def test_graceful_with_no_video_dimensions(self):
        """Without video dimensions, zone analysis is skipped gracefully."""
        zone = _make_zone("Test")
        points = _make_points([(100, 100), (500, 500), (900, 900)], interval_s=5)
        result = TrajectoryAnalyzer.analyze_trajectory(
            track_id=1,
            track_points=points,
            zones=[zone],
            object_class="person",
            # No video_width/video_height
        )
        assert result.zone_transitions == []
        assert result.is_approaching_entry is False


# ===========================================================================
# format_trajectory_context (prompt formatting)
# ===========================================================================


class TestFormatTrajectoryContext:
    def test_none(self):
        result = format_trajectory_context(None)
        assert "not available" in result.lower() or "no track" in result.lower()

    def test_empty(self):
        result = format_trajectory_context({})
        assert "not available" in result.lower() or "no track" in result.lower()

    def test_single_analysis(self):
        analysis = TrajectoryAnalysis(
            track_id=42,
            dwell_seconds=45.0,
            movement_pattern="stationary",
            speed_estimate=2.1,
            zone_transitions=["entered Front Porch"],
            is_approaching_entry=False,
            trajectory_summary="Person #42: stationary for 45s. Speed: stationary. Zone activity: entered Front Porch.",
        )
        result = format_trajectory_context({42: analysis})
        assert "Person #42" in result
        assert "stationary" in result
        assert "Front Porch" in result

    def test_approaching_entry_warning(self):
        analysis = TrajectoryAnalysis(
            track_id=7,
            dwell_seconds=10.0,
            movement_pattern="approaching",
            speed_estimate=30.0,
            is_approaching_entry=True,
            trajectory_summary="Person #7: approaching for 10s. Speed: slow (walking pace).",
        )
        result = format_trajectory_context({7: analysis})
        assert "APPROACHING" in result
        assert "entry point" in result

    def test_multiple_analyses_sorted(self):
        a1 = TrajectoryAnalysis(
            track_id=10,
            trajectory_summary="Person #10: wandering for 20s.",
        )
        a2 = TrajectoryAnalysis(
            track_id=5,
            trajectory_summary="Car #5: departing for 8s.",
        )
        result = format_trajectory_context({10: a1, 5: a2})
        # Track 5 should appear before track 10 (sorted by track_id)
        idx_5 = result.index("Car #5")
        idx_10 = result.index("Person #10")
        assert idx_5 < idx_10


# ===========================================================================
# _build_summary
# ===========================================================================


class TestBuildSummary:
    def test_basic_summary(self):
        analysis = TrajectoryAnalysis(
            track_id=1,
            dwell_seconds=30.0,
            movement_pattern="stationary",
            speed_estimate=1.0,
        )
        summary = _build_summary(1, "person", analysis)
        assert "Person #1" in summary
        assert "stationary" in summary
        assert "30s" in summary

    def test_zone_transitions_in_summary(self):
        analysis = TrajectoryAnalysis(
            track_id=2,
            dwell_seconds=15.0,
            movement_pattern="wandering",
            speed_estimate=20.0,
            zone_transitions=["entered Driveway", "exited Sidewalk"],
        )
        summary = _build_summary(2, "person", analysis)
        assert "Driveway" in summary
        assert "Sidewalk" in summary

    def test_entry_warning_in_summary(self):
        analysis = TrajectoryAnalysis(
            track_id=3,
            dwell_seconds=5.0,
            movement_pattern="approaching",
            speed_estimate=50.0,
            is_approaching_entry=True,
        )
        summary = _build_summary(3, "person", analysis)
        assert "approaching entry point" in summary.lower()
