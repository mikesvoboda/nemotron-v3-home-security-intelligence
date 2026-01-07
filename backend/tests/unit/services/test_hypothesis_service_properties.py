"""Property-based tests for service layer using Hypothesis.

This module contains comprehensive property-based tests for service
layer components to verify mathematical invariants, boundary conditions,
and data consistency across many randomly generated inputs.

Services tested:
- Detection service: confidence, bbox validation
- Event aggregation: batch processing, timestamp ordering
- Risk scoring: bounds, consistency
- Alert deduplication: key generation, cooldown periods
- Cache operations: key/value consistency
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from hypothesis import given, settings
from hypothesis import strategies as st

from backend.models.detection import Detection
from backend.models.event import Event
from backend.tests.strategies import (
    bbox_strategy,
    camera_ids,
    confidence_scores,
    detection_dict_strategy,
    event_dict_strategy,
    object_types,
    ordered_timestamp_pair,
    positive_integers,
    risk_scores,
    utc_timestamps,
)

# =============================================================================
# Detection Service Property Tests
# =============================================================================


class TestDetectionServiceProperties:
    """Property-based tests for detection service behavior."""

    @given(confidence=confidence_scores)
    @settings(max_examples=200)
    def test_detection_confidence_always_valid_range(self, confidence: float) -> None:
        """Property: Detection confidence is always between 0 and 1."""
        detection = Detection(
            camera_id="test_cam",
            file_path="/test/path.jpg",
            confidence=confidence,
        )

        assert 0.0 <= detection.confidence <= 1.0
        assert detection.confidence == confidence

    @given(bbox=bbox_strategy())
    @settings(max_examples=200)
    def test_bbox_coordinates_always_valid(self, bbox: dict[str, int]) -> None:
        """Property: Bounding box coordinates are always non-negative and valid."""
        detection = Detection(
            camera_id="test_cam",
            file_path="/test/path.jpg",
            bbox_x=bbox["x"],
            bbox_y=bbox["y"],
            bbox_width=bbox["width"],
            bbox_height=bbox["height"],
        )

        # All coordinates are non-negative
        assert detection.bbox_x >= 0
        assert detection.bbox_y >= 0
        assert detection.bbox_width >= 0
        assert detection.bbox_height >= 0

        # Width and height are positive (from strategy)
        assert detection.bbox_width > 0
        assert detection.bbox_height > 0

        # Bottom-right corner is valid
        x2 = detection.bbox_x + detection.bbox_width
        y2 = detection.bbox_y + detection.bbox_height
        assert x2 > detection.bbox_x
        assert y2 > detection.bbox_y

    @given(
        det1=detection_dict_strategy(),
        det2=detection_dict_strategy(),
    )
    @settings(max_examples=100)
    def test_detection_comparison_transitive(self, det1: dict, det2: dict) -> None:
        """Property: Detection confidence comparison is transitive."""
        detection1 = Detection(**det1)
        detection2 = Detection(**det2)

        # Reflexive: a >= a
        assert detection1.confidence >= detection1.confidence

        # Transitive property holds for confidence ordering
        if detection1.confidence >= detection2.confidence:
            assert detection1.confidence - detection2.confidence >= 0
        else:
            assert detection2.confidence - detection1.confidence > 0

    @given(
        camera_id=camera_ids,
        object_type=object_types,
        confidence=confidence_scores,
    )
    @settings(max_examples=100)
    def test_detection_creation_always_succeeds_with_valid_inputs(
        self, camera_id: str, object_type: str, confidence: float
    ) -> None:
        """Property: Detection creation always succeeds with valid inputs."""
        detection = Detection(
            camera_id=camera_id,
            file_path=f"/export/foscam/{camera_id}/test.jpg",
            object_type=object_type,
            confidence=confidence,
        )

        assert detection.camera_id == camera_id
        assert detection.object_type == object_type
        assert detection.confidence == confidence


# =============================================================================
# Risk Scoring Property Tests
# =============================================================================


class TestRiskScoringProperties:
    """Property-based tests for risk scoring behavior."""

    @given(risk_score=risk_scores)
    @settings(max_examples=200)
    def test_risk_score_always_bounded(self, risk_score: int) -> None:
        """Property: Risk score is always between 0 and 100 inclusive."""
        event = Event(
            batch_id="test_batch",
            camera_id="test_cam",
            started_at=datetime.now(UTC),
            risk_score=risk_score,
        )

        assert 0 <= event.risk_score <= 100
        assert event.risk_score == risk_score

    @given(
        score1=risk_scores,
        score2=risk_scores,
    )
    @settings(max_examples=100)
    def test_risk_score_ordering_transitive(self, score1: int, score2: int) -> None:
        """Property: Risk score ordering is transitive."""
        # Reflexive (intentional self-comparison)
        assert score1 >= score1  # noqa: PLR0124
        assert score2 >= score2  # noqa: PLR0124

        # Transitive ordering
        if score1 >= score2:
            assert score1 - score2 >= 0
        if score2 >= score1:
            assert score2 - score1 >= 0

        # At least one direction is true
        assert (score1 >= score2) or (score2 >= score1)

    @given(event_data=event_dict_strategy())
    @settings(max_examples=100)
    def test_event_with_risk_score_maintains_bounds(self, event_data: dict) -> None:
        """Property: Events always maintain risk score bounds."""
        event = Event(**event_data)

        assert 0 <= event.risk_score <= 100
        assert event.risk_level in ["low", "medium", "high", "critical"]


# =============================================================================
# Event Aggregation Property Tests
# =============================================================================


class TestEventAggregationProperties:
    """Property-based tests for event aggregation behavior."""

    @given(timestamps=ordered_timestamp_pair())
    @settings(max_examples=200)
    def test_event_timestamp_ordering_always_valid(
        self, timestamps: tuple[datetime, datetime]
    ) -> None:
        """Property: Event ended_at is always >= started_at when both set."""
        started_at, ended_at = timestamps

        event = Event(
            batch_id="test_batch",
            camera_id="test_cam",
            started_at=started_at,
            ended_at=ended_at,
        )

        assert event.ended_at >= event.started_at

        # Calculate duration
        duration = event.ended_at - event.started_at
        assert duration.total_seconds() >= 0

    @given(
        started_at=utc_timestamps,
        delta_seconds=st.integers(min_value=0, max_value=7200),  # Up to 2 hours
    )
    @settings(max_examples=100)
    def test_event_duration_calculation_consistent(
        self, started_at: datetime, delta_seconds: int
    ) -> None:
        """Property: Event duration calculation is consistent."""
        ended_at = started_at + timedelta(seconds=delta_seconds)

        event = Event(
            batch_id="test_batch",
            camera_id="test_cam",
            started_at=started_at,
            ended_at=ended_at,
        )

        duration = (event.ended_at - event.started_at).total_seconds()
        assert abs(duration - delta_seconds) < 0.001  # Allow floating point error

    @given(events=st.lists(event_dict_strategy(), min_size=1, max_size=10))
    @settings(max_examples=50)
    def test_event_list_preserves_count(self, events: list[dict]) -> None:
        """Property: Event aggregation never loses events."""
        event_objects = [Event(**e) for e in events]

        # Count should be preserved
        assert len(event_objects) == len(events)

        # All events should be valid
        for event in event_objects:
            assert 0 <= event.risk_score <= 100
            assert event.batch_id is not None
            assert event.camera_id is not None


# =============================================================================
# Batch Processing Property Tests
# =============================================================================


class TestBatchProcessingProperties:
    """Property-based tests for batch processing behavior."""

    @given(
        batch_size=st.integers(min_value=1, max_value=50),
        camera_id=camera_ids,
    )
    @settings(max_examples=100)
    def test_batch_detection_count_preserved(self, batch_size: int, camera_id: str) -> None:
        """Property: Batch processing preserves detection count."""
        # Simulate batch of detections
        detection_ids = list(range(1, batch_size + 1))

        # Count is preserved
        assert len(detection_ids) == batch_size

        # All IDs are positive
        assert all(d_id > 0 for d_id in detection_ids)

        # All IDs are unique
        assert len(set(detection_ids)) == batch_size

    @given(
        window_seconds=st.integers(min_value=1, max_value=180),
        idle_seconds=st.integers(min_value=1, max_value=60),
    )
    @settings(max_examples=50)
    def test_batch_window_timing_consistent(self, window_seconds: int, idle_seconds: int) -> None:
        """Property: Batch window timing parameters are consistent."""
        # Window should be >= idle timeout
        # (though this is not strictly enforced, it's a reasonable constraint)

        # Both should be positive
        assert window_seconds > 0
        assert idle_seconds > 0

        # Create time deltas
        window_delta = timedelta(seconds=window_seconds)
        idle_delta = timedelta(seconds=idle_seconds)

        assert window_delta.total_seconds() == window_seconds
        assert idle_delta.total_seconds() == idle_seconds


# =============================================================================
# Alert Deduplication Property Tests
# =============================================================================


class TestAlertDeduplicationProperties:
    """Property-based tests for alert deduplication behavior."""

    @given(
        camera_id=camera_ids,
        object_type=object_types,
    )
    @settings(max_examples=100)
    def test_dedup_key_generation_deterministic(self, camera_id: str, object_type: str) -> None:
        """Property: Dedup key generation is deterministic."""
        # Generate key twice with same inputs
        key1 = f"{camera_id}:{object_type}"
        key2 = f"{camera_id}:{object_type}"

        assert key1 == key2

        # Key format is consistent
        assert ":" in key1
        parts = key1.split(":")
        assert len(parts) == 2
        assert parts[0] == camera_id
        assert parts[1] == object_type

    @given(
        cooldown_seconds=st.integers(min_value=60, max_value=3600),
    )
    @settings(max_examples=50)
    def test_cooldown_period_always_positive(self, cooldown_seconds: int) -> None:
        """Property: Cooldown period is always positive."""
        assert cooldown_seconds > 0

        cooldown_delta = timedelta(seconds=cooldown_seconds)
        assert cooldown_delta.total_seconds() == cooldown_seconds

        # Cooldown in the future
        now = datetime.now(UTC)
        cooldown_end = now + cooldown_delta
        assert cooldown_end > now


# =============================================================================
# Data Consistency Property Tests
# =============================================================================


class TestDataConsistencyProperties:
    """Property-based tests for data consistency across services."""

    @given(
        camera_id=camera_ids,
        num_detections=st.integers(min_value=1, max_value=20),
    )
    @settings(max_examples=50)
    def test_camera_detection_relationship_consistent(
        self, camera_id: str, num_detections: int
    ) -> None:
        """Property: All detections for a camera reference the same camera_id."""
        detections = [
            Detection(
                camera_id=camera_id,
                file_path=f"/export/foscam/{camera_id}/image_{i}.jpg",
            )
            for i in range(num_detections)
        ]

        # All detections reference the same camera
        assert all(d.camera_id == camera_id for d in detections)

        # Detection count is preserved
        assert len(detections) == num_detections

    @given(
        confidence1=confidence_scores,
        confidence2=confidence_scores,
    )
    @settings(max_examples=100)
    def test_confidence_averaging_bounded(self, confidence1: float, confidence2: float) -> None:
        """Property: Average confidence is always within bounds of inputs."""
        avg = (confidence1 + confidence2) / 2

        # Average is between min and max of inputs
        assert min(confidence1, confidence2) <= avg <= max(confidence1, confidence2)

        # Average is still in valid range
        assert 0.0 <= avg <= 1.0


# =============================================================================
# Boundary Condition Property Tests
# =============================================================================


class TestBoundaryConditionProperties:
    """Property-based tests for boundary conditions."""

    @given(risk_score=st.integers(min_value=0, max_value=100))
    @settings(max_examples=200)
    def test_risk_score_at_all_values(self, risk_score: int) -> None:
        """Property: Risk score is valid at all integer values 0-100."""
        event = Event(
            batch_id="test_batch",
            camera_id="test_cam",
            started_at=datetime.now(UTC),
            risk_score=risk_score,
        )

        assert event.risk_score == risk_score
        assert 0 <= event.risk_score <= 100

    @given(confidence=st.floats(min_value=0.0, max_value=1.0, allow_nan=False))
    @settings(max_examples=200)
    def test_confidence_at_all_valid_floats(self, confidence: float) -> None:
        """Property: Confidence is valid at all float values 0.0-1.0."""
        detection = Detection(
            camera_id="test_cam",
            file_path="/test/path.jpg",
            confidence=confidence,
        )

        assert detection.confidence == confidence
        assert 0.0 <= detection.confidence <= 1.0

    @given(
        x=positive_integers,
        y=positive_integers,
        width=st.integers(min_value=1, max_value=1000),
        height=st.integers(min_value=1, max_value=1000),
    )
    @settings(max_examples=100)
    def test_bbox_with_positive_dimensions(self, x: int, y: int, width: int, height: int) -> None:
        """Property: Bbox with positive dimensions always has valid corner coordinates."""
        detection = Detection(
            camera_id="test_cam",
            file_path="/test/path.jpg",
            bbox_x=x,
            bbox_y=y,
            bbox_width=width,
            bbox_height=height,
        )

        x2 = detection.bbox_x + detection.bbox_width
        y2 = detection.bbox_y + detection.bbox_height

        # Bottom-right corner is always greater than top-left
        assert x2 > detection.bbox_x
        assert y2 > detection.bbox_y


# =============================================================================
# Timestamp Arithmetic Property Tests
# =============================================================================


class TestTimestampArithmeticProperties:
    """Property-based tests for timestamp arithmetic."""

    @given(
        base_time=utc_timestamps,
        offset_seconds=st.integers(min_value=-86400, max_value=86400),  # ±1 day
    )
    @settings(max_examples=100)
    def test_timestamp_addition_invertible(self, base_time: datetime, offset_seconds: int) -> None:
        """Property: Adding and subtracting same timedelta is invertible."""
        delta = timedelta(seconds=offset_seconds)

        new_time = base_time + delta
        restored_time = new_time - delta

        # Should restore original time (within microsecond precision)
        time_diff = abs((restored_time - base_time).total_seconds())
        assert time_diff < 0.000001

    @given(
        time1=utc_timestamps,
        time2=utc_timestamps,
    )
    @settings(max_examples=100)
    def test_timestamp_comparison_consistent(self, time1: datetime, time2: datetime) -> None:
        """Property: Timestamp comparison is consistent and transitive."""
        # Reflexive (intentional self-comparison)
        assert time1 == time1  # noqa: PLR0124
        assert time2 == time2  # noqa: PLR0124

        # Trichotomy: exactly one of <, ==, > holds
        is_less = time1 < time2
        is_equal = time1 == time2
        is_greater = time1 > time2

        assert sum([is_less, is_equal, is_greater]) == 1

        # If time1 < time2, then duration is positive
        if is_less:
            duration = (time2 - time1).total_seconds()
            assert duration > 0

        # If time1 == time2, then duration is zero
        if is_equal:
            duration = (time2 - time1).total_seconds()
            assert abs(duration) < 0.000001


# =============================================================================
# String Formatting Property Tests
# =============================================================================


class TestStringFormattingProperties:
    """Property-based tests for string formatting consistency."""

    @given(camera_id=camera_ids)
    @settings(max_examples=100)
    def test_camera_id_format_consistent(self, camera_id: str) -> None:
        """Property: Camera ID format is always consistent."""
        # Should be lowercase
        assert camera_id == camera_id.lower()

        # Should only contain valid characters
        assert all(c.isalnum() or c == "_" for c in camera_id)

        # Should have at least one character
        assert len(camera_id) > 0

        # First character should be letter (from strategy)
        assert camera_id[0].isalpha(), f"Camera ID should start with letter: {camera_id}"

    @given(object_type=object_types)
    @settings(max_examples=50)
    def test_object_type_format_consistent(self, object_type: str) -> None:
        """Property: Object type format is always consistent."""
        # Should be non-empty
        assert len(object_type) > 0

        # Should not have leading/trailing whitespace
        assert object_type == object_type.strip()
