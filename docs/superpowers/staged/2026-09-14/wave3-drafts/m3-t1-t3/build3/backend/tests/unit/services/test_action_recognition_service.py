"""Unit tests for ActionRecognitionService Prometheus metrics (NEM-4144).

This module provides comprehensive tests for:
- hsi_action_detections_total Counter (action_type, camera_id labels)
- hsi_action_confidence Histogram (action_type label)
- hsi_action_corrections_total Counter (action_type, correction_type labels)
- Helper functions: record_action_detection, record_action_correction

Tests follow TDD approach and verify:
- Metric increments and observations
- Label value extraction (action categories)
- Camera ID sanitization
- Different action categories from ACTION_PROMPTS_V2
"""

import pytest

from backend.services.action_recognition_service import (
    hsi_action_confidence,
    hsi_action_corrections_total,
    hsi_action_detections_total,
    record_action_correction,
    record_action_detection,
)
from backend.services.xclip_loader import ACTION_PROMPTS_V2

# Mark all tests in this file as unit tests
pytestmark = pytest.mark.unit


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def clear_action_metrics():
    """Clear action metrics before and after each test.

    This ensures tests don't interfere with each other.
    """
    # Clear metrics before test
    hsi_action_detections_total.clear()
    hsi_action_confidence.clear()
    hsi_action_corrections_total.clear()
    yield
    # Clear metrics after test
    hsi_action_detections_total.clear()
    hsi_action_confidence.clear()
    hsi_action_corrections_total.clear()


# =============================================================================
# Counter Metric Tests - hsi_action_detections_total
# =============================================================================


class TestActionDetectionsCounter:
    """Tests for hsi_action_detections_total Counter metric."""

    def test_counter_exists(self):
        """Test that the counter metric is registered."""
        assert hsi_action_detections_total is not None

    def test_counter_has_correct_name(self):
        """Test that counter has the standard hsi_ prefix name.

        Note: Counter internal _name doesn't include '_total' suffix;
        the suffix is added during metric export.
        """
        assert hsi_action_detections_total._name == "hsi_action_detections"

    def test_counter_has_correct_labels(self):
        """Test that counter has required labels."""
        expected_labels = ["action_type", "camera_id"]
        assert set(hsi_action_detections_total._labelnames) == set(expected_labels)

    def test_counter_increments_for_high_risk_action(self, clear_action_metrics):
        """Test counter increments for high_risk category actions."""
        # Get a high_risk action from ACTION_PROMPTS_V2
        high_risk_action = ACTION_PROMPTS_V2["high_risk"]["prompts"][0]
        camera_id = "front_door"

        # Record the detection
        record_action_detection(high_risk_action, camera_id, confidence=0.85)

        # Verify counter was incremented
        metric_value = hsi_action_detections_total.labels(
            action_type="high_risk",
            camera_id="front_door",
        )._value.get()
        assert metric_value == 1.0

    def test_counter_increments_for_suspicious_action(self, clear_action_metrics):
        """Test counter increments for suspicious category actions."""
        suspicious_action = ACTION_PROMPTS_V2["suspicious"]["prompts"][0]
        camera_id = "backyard"

        record_action_detection(suspicious_action, camera_id, confidence=0.75)

        metric_value = hsi_action_detections_total.labels(
            action_type="suspicious",
            camera_id="backyard",
        )._value.get()
        assert metric_value == 1.0

    def test_counter_increments_for_normal_action(self, clear_action_metrics):
        """Test counter increments for normal category actions."""
        normal_action = ACTION_PROMPTS_V2["normal"]["prompts"][0]
        camera_id = "garage"

        record_action_detection(normal_action, camera_id, confidence=0.90)

        metric_value = hsi_action_detections_total.labels(
            action_type="normal",
            camera_id="garage",
        )._value.get()
        assert metric_value == 1.0

    def test_counter_increments_for_approaching_action(self, clear_action_metrics):
        """Test counter increments for approaching category actions."""
        approaching_action = ACTION_PROMPTS_V2["approaching"]["prompts"][0]
        camera_id = "driveway"

        record_action_detection(approaching_action, camera_id, confidence=0.80)

        metric_value = hsi_action_detections_total.labels(
            action_type="approaching",
            camera_id="driveway",
        )._value.get()
        assert metric_value == 1.0

    def test_counter_increments_for_stationary_action(self, clear_action_metrics):
        """Test counter increments for stationary category actions."""
        stationary_action = ACTION_PROMPTS_V2["stationary"]["prompts"][0]
        camera_id = "porch"

        record_action_detection(stationary_action, camera_id, confidence=0.88)

        metric_value = hsi_action_detections_total.labels(
            action_type="stationary",
            camera_id="porch",
        )._value.get()
        assert metric_value == 1.0

    def test_counter_increments_for_fleeing_action(self, clear_action_metrics):
        """Test counter increments for fleeing category actions."""
        fleeing_action = ACTION_PROMPTS_V2["fleeing"]["prompts"][0]
        camera_id = "side_gate"

        record_action_detection(fleeing_action, camera_id, confidence=0.92)

        metric_value = hsi_action_detections_total.labels(
            action_type="fleeing",
            camera_id="side_gate",
        )._value.get()
        assert metric_value == 1.0

    def test_counter_handles_unknown_action(self, clear_action_metrics):
        """Test counter uses 'unknown' for unrecognized actions."""
        unknown_action = "completely unknown action not in prompts"
        camera_id = "test_cam"

        record_action_detection(unknown_action, camera_id, confidence=0.60)

        metric_value = hsi_action_detections_total.labels(
            action_type="unknown",
            camera_id="test_cam",
        )._value.get()
        assert metric_value == 1.0

    def test_counter_sanitizes_long_camera_id(self, clear_action_metrics):
        """Test counter truncates camera IDs longer than 50 characters."""
        high_risk_action = ACTION_PROMPTS_V2["high_risk"]["prompts"][0]
        long_camera_id = "a" * 100  # 100 character camera ID

        record_action_detection(high_risk_action, long_camera_id, confidence=0.85)

        # Camera ID should be truncated to 50 characters
        truncated_id = "a" * 50
        metric_value = hsi_action_detections_total.labels(
            action_type="high_risk",
            camera_id=truncated_id,
        )._value.get()
        assert metric_value == 1.0

    def test_counter_sanitizes_special_characters_in_camera_id(self, clear_action_metrics):
        """Test counter replaces / and \\ with _ in camera IDs."""
        high_risk_action = ACTION_PROMPTS_V2["high_risk"]["prompts"][0]
        camera_id_with_slashes = "building/floor1\\cam3"

        record_action_detection(high_risk_action, camera_id_with_slashes, confidence=0.85)

        sanitized_id = "building_floor1_cam3"
        metric_value = hsi_action_detections_total.labels(
            action_type="high_risk",
            camera_id=sanitized_id,
        )._value.get()
        assert metric_value == 1.0

    def test_counter_accumulates_multiple_detections(self, clear_action_metrics):
        """Test counter accumulates multiple detections for same labels."""
        high_risk_action = ACTION_PROMPTS_V2["high_risk"]["prompts"][0]
        camera_id = "entrance"

        # Record multiple detections
        for _ in range(5):
            record_action_detection(high_risk_action, camera_id, confidence=0.80)

        metric_value = hsi_action_detections_total.labels(
            action_type="high_risk",
            camera_id="entrance",
        )._value.get()
        assert metric_value == 5.0


# =============================================================================
# Histogram Metric Tests - hsi_action_confidence
# =============================================================================


class TestActionConfidenceHistogram:
    """Tests for hsi_action_confidence Histogram metric."""

    def test_histogram_exists(self):
        """Test that the histogram metric is registered."""
        assert hsi_action_confidence is not None

    def test_histogram_has_correct_name(self):
        """Test that histogram has the standard hsi_ prefix name."""
        assert hsi_action_confidence._name == "hsi_action_confidence"

    def test_histogram_has_correct_labels(self):
        """Test that histogram has required labels."""
        expected_labels = ["action_type"]
        assert set(hsi_action_confidence._labelnames) == set(expected_labels)

    def test_histogram_has_correct_buckets(self):
        """Test that histogram has the expected confidence buckets."""
        # Check the upper bounds match our specification
        expected_buckets = [0.5, 0.6, 0.7, 0.8, 0.9, 0.95]
        actual_buckets = list(hsi_action_confidence._upper_bounds)
        # Remove +Inf bucket from comparison
        actual_buckets_without_inf = [b for b in actual_buckets if b != float("inf")]
        assert actual_buckets_without_inf == expected_buckets

    def test_histogram_records_confidence_for_high_risk(self, clear_action_metrics):
        """Test histogram records confidence score for high_risk actions."""
        high_risk_action = ACTION_PROMPTS_V2["high_risk"]["prompts"][0]

        record_action_detection(high_risk_action, "cam1", confidence=0.85)

        # Get the histogram's count - it should have 1 observation
        histogram = hsi_action_confidence.labels(action_type="high_risk")
        # The sum should be 0.85 for one observation
        assert histogram._sum.get() == 0.85

    def test_histogram_records_multiple_confidences(self, clear_action_metrics):
        """Test histogram accumulates multiple confidence observations."""
        high_risk_action = ACTION_PROMPTS_V2["high_risk"]["prompts"][0]
        confidences = [0.75, 0.85, 0.92]

        for conf in confidences:
            record_action_detection(high_risk_action, "cam1", confidence=conf)

        histogram = hsi_action_confidence.labels(action_type="high_risk")
        # Sum should be total of all confidences
        assert histogram._sum.get() == pytest.approx(sum(confidences), rel=1e-6)

    def test_histogram_records_for_different_action_types(self, clear_action_metrics):
        """Test histogram tracks different action types separately."""
        high_risk_action = ACTION_PROMPTS_V2["high_risk"]["prompts"][0]
        normal_action = ACTION_PROMPTS_V2["normal"]["prompts"][0]

        record_action_detection(high_risk_action, "cam1", confidence=0.90)
        record_action_detection(normal_action, "cam1", confidence=0.80)

        # Each action type should have its own observation
        high_risk_histogram = hsi_action_confidence.labels(action_type="high_risk")
        normal_histogram = hsi_action_confidence.labels(action_type="normal")

        assert high_risk_histogram._sum.get() == pytest.approx(0.90, rel=1e-6)
        assert normal_histogram._sum.get() == pytest.approx(0.80, rel=1e-6)


# =============================================================================
# Counter Metric Tests - hsi_action_corrections_total
# =============================================================================


class TestActionCorrectionsCounter:
    """Tests for hsi_action_corrections_total Counter metric."""

    def test_counter_exists(self):
        """Test that the counter metric is registered."""
        assert hsi_action_corrections_total is not None

    def test_counter_has_correct_name(self):
        """Test that counter has the standard hsi_ prefix name.

        Note: Counter internal _name doesn't include '_total' suffix;
        the suffix is added during metric export.
        """
        assert hsi_action_corrections_total._name == "hsi_action_corrections"

    def test_counter_has_correct_labels(self):
        """Test that counter has required labels."""
        expected_labels = ["action_type", "correction_type"]
        assert set(hsi_action_corrections_total._labelnames) == set(expected_labels)

    def test_counter_records_false_positive_correction(self, clear_action_metrics):
        """Test counter records false_positive corrections."""
        high_risk_action = ACTION_PROMPTS_V2["high_risk"]["prompts"][0]

        record_action_correction(high_risk_action, "false_positive")

        metric_value = hsi_action_corrections_total.labels(
            action_type="high_risk",
            correction_type="false_positive",
        )._value.get()
        assert metric_value == 1.0

    def test_counter_records_false_negative_correction(self, clear_action_metrics):
        """Test counter records false_negative corrections."""
        suspicious_action = ACTION_PROMPTS_V2["suspicious"]["prompts"][0]

        record_action_correction(suspicious_action, "false_negative")

        metric_value = hsi_action_corrections_total.labels(
            action_type="suspicious",
            correction_type="false_negative",
        )._value.get()
        assert metric_value == 1.0

    def test_counter_records_misclassification_correction(self, clear_action_metrics):
        """Test counter records misclassification corrections."""
        normal_action = ACTION_PROMPTS_V2["normal"]["prompts"][0]

        record_action_correction(normal_action, "misclassification")

        metric_value = hsi_action_corrections_total.labels(
            action_type="normal",
            correction_type="misclassification",
        )._value.get()
        assert metric_value == 1.0

    def test_counter_handles_unknown_action(self, clear_action_metrics):
        """Test counter uses 'unknown' for unrecognized actions in corrections."""
        unknown_action = "unknown action not in prompts"

        record_action_correction(unknown_action, "false_positive")

        metric_value = hsi_action_corrections_total.labels(
            action_type="unknown",
            correction_type="false_positive",
        )._value.get()
        assert metric_value == 1.0

    def test_counter_accumulates_corrections(self, clear_action_metrics):
        """Test counter accumulates multiple corrections."""
        high_risk_action = ACTION_PROMPTS_V2["high_risk"]["prompts"][0]

        for _ in range(3):
            record_action_correction(high_risk_action, "false_positive")

        metric_value = hsi_action_corrections_total.labels(
            action_type="high_risk",
            correction_type="false_positive",
        )._value.get()
        assert metric_value == 3.0


# =============================================================================
# Integration Tests - record_action_detection function
# =============================================================================


class TestRecordActionDetection:
    """Tests for the record_action_detection helper function."""

    def test_records_both_counter_and_histogram(self, clear_action_metrics):
        """Test that record_action_detection updates both metrics."""
        high_risk_action = ACTION_PROMPTS_V2["high_risk"]["prompts"][0]

        record_action_detection(high_risk_action, "test_cam", confidence=0.85)

        # Check counter was incremented
        counter_value = hsi_action_detections_total.labels(
            action_type="high_risk",
            camera_id="test_cam",
        )._value.get()
        assert counter_value == 1.0

        # Check histogram was updated
        histogram = hsi_action_confidence.labels(action_type="high_risk")
        assert histogram._sum.get() == pytest.approx(0.85, rel=1e-6)

    def test_handles_edge_case_confidence_values(self, clear_action_metrics):
        """Test handling of edge case confidence values."""
        normal_action = ACTION_PROMPTS_V2["normal"]["prompts"][0]

        # Test boundary confidence values
        for conf in [0.5, 0.95, 1.0]:
            record_action_detection(normal_action, "cam", confidence=conf)

        histogram = hsi_action_confidence.labels(action_type="normal")
        expected_sum = 0.5 + 0.95 + 1.0
        assert histogram._sum.get() == pytest.approx(expected_sum, rel=1e-6)


# =============================================================================
# Integration Tests - record_action_correction function
# =============================================================================


class TestRecordActionCorrection:
    """Tests for the record_action_correction helper function."""

    def test_all_correction_types(self, clear_action_metrics):
        """Test all supported correction types."""
        high_risk_action = ACTION_PROMPTS_V2["high_risk"]["prompts"][0]
        correction_types = ["false_positive", "false_negative", "misclassification"]

        for correction_type in correction_types:
            record_action_correction(high_risk_action, correction_type)

        for correction_type in correction_types:
            metric_value = hsi_action_corrections_total.labels(
                action_type="high_risk",
                correction_type=correction_type,
            )._value.get()
            assert metric_value == 1.0

    def test_correction_across_action_types(self, clear_action_metrics):
        """Test corrections for different action types."""
        action_types = ["high_risk", "suspicious", "normal", "approaching", "fleeing"]

        for action_type in action_types:
            action = ACTION_PROMPTS_V2[action_type]["prompts"][0]
            record_action_correction(action, "false_positive")

        for action_type in action_types:
            metric_value = hsi_action_corrections_total.labels(
                action_type=action_type,
                correction_type="false_positive",
            )._value.get()
            assert metric_value == 1.0
