"""Unit tests for YOLO26 Prometheus metrics module.

Tests verify that all required metrics are properly defined and instrumented:
- yolo26_inference_duration_seconds (histogram)
- yolo26_requests_total (counter)
- yolo26_detections_total (counter by class)
- yolo26_vram_bytes (gauge)
- yolo26_errors_total (counter)
- yolo26_batch_size (histogram)
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Add the ai/yolo26 directory to sys.path to enable imports
_yolo26_dir = Path(__file__).parent.parent
if str(_yolo26_dir) not in sys.path:
    sys.path.insert(0, str(_yolo26_dir))


class TestMetricsDefinition:
    """Tests for verifying metric definitions exist with correct types."""

    def test_inference_duration_seconds_histogram_exists(self):
        """Test that yolo26_inference_duration_seconds histogram is defined."""
        from metrics import INFERENCE_DURATION_SECONDS

        assert INFERENCE_DURATION_SECONDS is not None
        # Verify it's a histogram by checking for observe method
        assert hasattr(INFERENCE_DURATION_SECONDS, "observe")
        # Check metric name
        assert INFERENCE_DURATION_SECONDS._name == "yolo26_inference_duration_seconds"

    def test_inference_duration_has_endpoint_label(self):
        """Test that inference duration histogram has endpoint label."""
        from metrics import INFERENCE_DURATION_SECONDS

        assert "endpoint" in INFERENCE_DURATION_SECONDS._labelnames

    def test_inference_duration_buckets_tuned_for_inference(self):
        """Test that buckets are tuned for typical inference times (10-100ms)."""
        from metrics import INFERENCE_DURATION_SECONDS

        # Buckets should cover the 10-100ms range well
        # Verify lower buckets exist for fast inference
        assert 0.01 in INFERENCE_DURATION_SECONDS._kwargs.get(
            "buckets", INFERENCE_DURATION_SECONDS._upper_bounds
        ) or any(b <= 0.02 for b in INFERENCE_DURATION_SECONDS._upper_bounds)

    def test_requests_total_counter_exists(self):
        """Test that yolo26_requests_total counter is defined."""
        from metrics import REQUESTS_TOTAL

        assert REQUESTS_TOTAL is not None
        # Verify it's a counter by checking for inc method
        assert hasattr(REQUESTS_TOTAL, "inc")
        # prometheus_client strips _total suffix internally, adds it back during export
        assert REQUESTS_TOTAL._name == "yolo26_requests"

    def test_requests_total_has_required_labels(self):
        """Test that requests counter has endpoint and status labels."""
        from metrics import REQUESTS_TOTAL

        assert "endpoint" in REQUESTS_TOTAL._labelnames
        assert "status" in REQUESTS_TOTAL._labelnames

    def test_detections_total_counter_exists(self):
        """Test that yolo26_detections_total counter is defined."""
        from metrics import DETECTIONS_TOTAL

        assert DETECTIONS_TOTAL is not None
        assert hasattr(DETECTIONS_TOTAL, "inc")
        # prometheus_client strips _total suffix internally, adds it back during export
        assert DETECTIONS_TOTAL._name == "yolo26_detections"

    def test_detections_total_has_class_label(self):
        """Test that detections counter has class_name label for per-class tracking."""
        from metrics import DETECTIONS_TOTAL

        assert "class_name" in DETECTIONS_TOTAL._labelnames

    def test_vram_bytes_gauge_exists(self):
        """Test that yolo26_vram_bytes gauge is defined."""
        from metrics import VRAM_BYTES

        assert VRAM_BYTES is not None
        assert hasattr(VRAM_BYTES, "set")
        assert VRAM_BYTES._name == "yolo26_vram_bytes"

    def test_errors_total_counter_exists(self):
        """Test that yolo26_errors_total counter is defined."""
        from metrics import ERRORS_TOTAL

        assert ERRORS_TOTAL is not None
        assert hasattr(ERRORS_TOTAL, "inc")
        # prometheus_client strips _total suffix internally, adds it back during export
        assert ERRORS_TOTAL._name == "yolo26_errors"

    def test_errors_total_has_error_type_label(self):
        """Test that errors counter has error_type label."""
        from metrics import ERRORS_TOTAL

        assert "error_type" in ERRORS_TOTAL._labelnames

    def test_batch_size_histogram_exists(self):
        """Test that yolo26_batch_size histogram is defined."""
        from metrics import BATCH_SIZE

        assert BATCH_SIZE is not None
        assert hasattr(BATCH_SIZE, "observe")
        assert BATCH_SIZE._name == "yolo26_batch_size"

    def test_batch_size_buckets_appropriate(self):
        """Test that batch size buckets cover typical batch sizes (1-32)."""
        from metrics import BATCH_SIZE

        # Should have buckets for small batch sizes
        buckets = BATCH_SIZE._upper_bounds
        assert any(b <= 4 for b in buckets)  # Small batches
        assert any(b >= 16 for b in buckets)  # Larger batches


class TestMetricsRecording:
    """Tests for recording metrics values."""

    def test_record_inference_duration(self):
        """Test recording inference duration."""
        from metrics import record_inference

        # Record a sample inference - should not raise
        record_inference(endpoint="detect", duration_seconds=0.045, success=True)

    def test_record_detection(self):
        """Test recording detection by class."""
        from metrics import DETECTIONS_TOTAL, record_detection

        initial_value = DETECTIONS_TOTAL.labels(class_name="person")._value.get()
        record_detection(class_name="person")
        new_value = DETECTIONS_TOTAL.labels(class_name="person")._value.get()

        assert new_value == initial_value + 1

    def test_record_multiple_detections(self):
        """Test recording multiple detections at once."""
        from metrics import DETECTIONS_TOTAL, record_detections

        # Record detections for multiple objects
        detections = [
            {"class": "person", "confidence": 0.95},
            {"class": "car", "confidence": 0.88},
            {"class": "person", "confidence": 0.72},
        ]

        initial_person = DETECTIONS_TOTAL.labels(class_name="person")._value.get()
        initial_car = DETECTIONS_TOTAL.labels(class_name="car")._value.get()

        record_detections(detections)

        # Should have recorded 2 persons and 1 car
        assert DETECTIONS_TOTAL.labels(class_name="person")._value.get() == initial_person + 2
        assert DETECTIONS_TOTAL.labels(class_name="car")._value.get() == initial_car + 1

    def test_record_error(self):
        """Test recording an error."""
        from metrics import ERRORS_TOTAL, record_error

        initial_value = ERRORS_TOTAL.labels(error_type="invalid_image")._value.get()
        record_error(error_type="invalid_image")
        new_value = ERRORS_TOTAL.labels(error_type="invalid_image")._value.get()

        assert new_value == initial_value + 1

    def test_record_batch_size(self):
        """Test recording batch size."""
        from metrics import record_batch_size

        # Should not raise
        record_batch_size(batch_size=4)

    def test_update_vram_bytes(self):
        """Test updating VRAM usage."""
        from metrics import VRAM_BYTES, update_vram_bytes

        update_vram_bytes(vram_bytes=2147483648)  # 2GB in bytes
        assert VRAM_BYTES._value.get() == 2147483648


class TestMetricsHelperFunctions:
    """Tests for helper functions that simplify metrics recording."""

    def test_record_inference_increments_request_counter(self):
        """Test that record_inference also increments request counter."""
        from metrics import REQUESTS_TOTAL, record_inference

        initial_success = REQUESTS_TOTAL.labels(endpoint="detect", status="success")._value.get()
        initial_error = REQUESTS_TOTAL.labels(endpoint="detect", status="error")._value.get()

        record_inference(endpoint="detect", duration_seconds=0.05, success=True)
        record_inference(endpoint="detect", duration_seconds=0.05, success=False)

        assert (
            REQUESTS_TOTAL.labels(endpoint="detect", status="success")._value.get()
            == initial_success + 1
        )
        assert (
            REQUESTS_TOTAL.labels(endpoint="detect", status="error")._value.get()
            == initial_error + 1
        )

    def test_get_vram_usage_bytes_returns_bytes(self):
        """Test that get_vram_usage_bytes returns usage in bytes."""
        from metrics import get_vram_usage_bytes

        with (
            patch("metrics.torch.cuda.is_available", return_value=True),
            patch("metrics.torch.cuda.memory_allocated", return_value=2147483648),
        ):
            vram = get_vram_usage_bytes()
            assert vram == 2147483648

    def test_get_vram_usage_bytes_returns_none_when_cuda_unavailable(self):
        """Test that get_vram_usage_bytes returns None when CUDA is unavailable."""
        from metrics import get_vram_usage_bytes

        with patch("metrics.torch.cuda.is_available", return_value=False):
            vram = get_vram_usage_bytes()
            assert vram is None


class TestMetricsExport:
    """Tests for metrics export functionality."""

    def test_metrics_can_be_exported(self):
        """Test that metrics can be exported in Prometheus format."""
        import metrics  # noqa: F401
        from prometheus_client import generate_latest

        # Generate metrics output
        output = generate_latest().decode("utf-8")

        # Verify all required metrics appear in output
        assert "yolo26_inference_duration_seconds" in output
        assert "yolo26_requests_total" in output
        assert "yolo26_detections_total" in output
        assert "yolo26_vram_bytes" in output
        assert "yolo26_errors_total" in output
        assert "yolo26_batch_size" in output


class TestBackwardsCompatibility:
    """Tests to ensure backwards compatibility with existing metrics."""

    def test_legacy_metrics_still_available(self):
        """Test that legacy metric names are still available for backwards compatibility."""
        from metrics import (
            GPU_MEMORY_USED_GB,
            GPU_POWER_WATTS,
            GPU_TEMPERATURE,
            GPU_UTILIZATION,
            INFERENCE_LATENCY_SECONDS,
            INFERENCE_REQUESTS_TOTAL,
            MODEL_LOADED,
        )

        # All legacy metrics should still be importable
        assert INFERENCE_REQUESTS_TOTAL is not None
        assert INFERENCE_LATENCY_SECONDS is not None
        assert MODEL_LOADED is not None
        assert GPU_UTILIZATION is not None
        assert GPU_MEMORY_USED_GB is not None
        assert GPU_TEMPERATURE is not None
        assert GPU_POWER_WATTS is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
