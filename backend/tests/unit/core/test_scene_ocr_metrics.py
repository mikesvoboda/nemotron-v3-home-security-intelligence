"""Unit tests for Scene OCR Prometheus metrics.

Tests cover:
- Scene OCR metric definitions and registrations
- Metric value updates via helper functions
- MetricsService Scene OCR methods
- Proper labeling and bucket configurations
"""

from unittest.mock import patch

import pytest

from backend.core.metrics import (
    SCENE_OCR_CONFIDENCE,
    SCENE_OCR_CONFIDENCE_BUCKETS,
    SCENE_OCR_PROCESSING_BUCKETS,
    SCENE_OCR_PROCESSING_SECONDS,
    SCENE_OCR_REQUESTS_TOTAL,
    SCENE_OCR_SERVICE_PROVIDERS_MATCHED_TOTAL,
    SCENE_OCR_TEXTS_DETECTED_TOTAL,
    MetricsService,
    get_metrics_service,
    observe_scene_ocr_confidence,
    observe_scene_ocr_processing,
    record_scene_ocr_provider_match,
    record_scene_ocr_request,
    record_scene_ocr_texts_detected,
)


class TestSceneOCRMetricDefinitions:
    """Test Scene OCR metric definitions and registrations."""

    def test_scene_ocr_requests_counter_exists(self) -> None:
        """SCENE_OCR_REQUESTS_TOTAL counter should be defined with source label."""
        assert SCENE_OCR_REQUESTS_TOTAL is not None
        # Note: prometheus_client strips _total suffix from counter names internally
        assert SCENE_OCR_REQUESTS_TOTAL._name == "hsi_scene_ocr_requests"
        assert "source" in SCENE_OCR_REQUESTS_TOTAL._labelnames

    def test_scene_ocr_texts_detected_counter_exists(self) -> None:
        """SCENE_OCR_TEXTS_DETECTED_TOTAL counter should be defined."""
        assert SCENE_OCR_TEXTS_DETECTED_TOTAL is not None
        # Note: prometheus_client strips _total suffix from counter names internally
        assert SCENE_OCR_TEXTS_DETECTED_TOTAL._name == "hsi_scene_ocr_texts_detected"

    def test_scene_ocr_provider_match_counter_exists(self) -> None:
        """SCENE_OCR_SERVICE_PROVIDERS_MATCHED_TOTAL counter should be defined with category label."""
        assert SCENE_OCR_SERVICE_PROVIDERS_MATCHED_TOTAL is not None
        # Note: prometheus_client strips _total suffix from counter names internally
        assert (
            SCENE_OCR_SERVICE_PROVIDERS_MATCHED_TOTAL._name
            == "hsi_scene_ocr_service_providers_matched"
        )
        assert "category" in SCENE_OCR_SERVICE_PROVIDERS_MATCHED_TOTAL._labelnames

    def test_scene_ocr_processing_histogram_exists(self) -> None:
        """SCENE_OCR_PROCESSING_SECONDS histogram should be defined with source label."""
        assert SCENE_OCR_PROCESSING_SECONDS is not None
        assert SCENE_OCR_PROCESSING_SECONDS._name == "hsi_scene_ocr_processing_seconds"
        assert "source" in SCENE_OCR_PROCESSING_SECONDS._labelnames

    def test_scene_ocr_processing_buckets_coverage(self) -> None:
        """SCENE_OCR_PROCESSING_BUCKETS should cover expected latency ranges."""
        assert SCENE_OCR_PROCESSING_BUCKETS is not None
        # Verify buckets cover expected ranges (50ms to 5s)
        assert 0.05 in SCENE_OCR_PROCESSING_BUCKETS  # 50ms - fast single frame
        assert 0.5 in SCENE_OCR_PROCESSING_BUCKETS  # 500ms - multiple crops
        assert 5.0 in SCENE_OCR_PROCESSING_BUCKETS  # 5s - timeout threshold

    def test_scene_ocr_confidence_histogram_exists(self) -> None:
        """SCENE_OCR_CONFIDENCE histogram should be defined."""
        assert SCENE_OCR_CONFIDENCE is not None
        assert SCENE_OCR_CONFIDENCE._name == "hsi_scene_ocr_confidence"

    def test_scene_ocr_confidence_buckets_coverage(self) -> None:
        """SCENE_OCR_CONFIDENCE_BUCKETS should cover confidence score ranges."""
        assert SCENE_OCR_CONFIDENCE_BUCKETS is not None
        # Verify buckets match confidence thresholds in scene_ocr_service.py
        assert 0.5 in SCENE_OCR_CONFIDENCE_BUCKETS  # CONFIDENCE_LOW/EXCLUDE threshold
        assert 0.8 in SCENE_OCR_CONFIDENCE_BUCKETS  # CONFIDENCE_HIGH threshold
        assert 0.95 in SCENE_OCR_CONFIDENCE_BUCKETS  # High confidence


class TestSceneOCRHelperFunctions:
    """Test Scene OCR metric helper functions."""

    def test_record_scene_ocr_request_full_frame(self) -> None:
        """record_scene_ocr_request should increment counter for full_frame source."""
        # Get initial value
        initial = SCENE_OCR_REQUESTS_TOTAL.labels(source="full_frame")._value.get()

        # Record request
        record_scene_ocr_request("full_frame")

        # Verify increment
        new_value = SCENE_OCR_REQUESTS_TOTAL.labels(source="full_frame")._value.get()
        assert new_value == initial + 1

    def test_record_scene_ocr_request_crop(self) -> None:
        """record_scene_ocr_request should increment counter for crop source."""
        # Get initial value
        initial = SCENE_OCR_REQUESTS_TOTAL.labels(source="crop")._value.get()

        # Record request
        record_scene_ocr_request("crop")

        # Verify increment
        new_value = SCENE_OCR_REQUESTS_TOTAL.labels(source="crop")._value.get()
        assert new_value == initial + 1

    def test_record_scene_ocr_texts_detected(self) -> None:
        """record_scene_ocr_texts_detected should increment counter by specified count."""
        # Get initial value
        initial = SCENE_OCR_TEXTS_DETECTED_TOTAL._value.get()

        # Record texts
        record_scene_ocr_texts_detected(5)

        # Verify increment
        new_value = SCENE_OCR_TEXTS_DETECTED_TOTAL._value.get()
        assert new_value == initial + 5

    def test_record_scene_ocr_texts_detected_default(self) -> None:
        """record_scene_ocr_texts_detected should default to 1."""
        # Get initial value
        initial = SCENE_OCR_TEXTS_DETECTED_TOTAL._value.get()

        # Record with default
        record_scene_ocr_texts_detected()

        # Verify increment by 1
        new_value = SCENE_OCR_TEXTS_DETECTED_TOTAL._value.get()
        assert new_value == initial + 1

    def test_record_scene_ocr_provider_match(self) -> None:
        """record_scene_ocr_provider_match should increment counter with category label."""
        # Get initial value
        initial = SCENE_OCR_SERVICE_PROVIDERS_MATCHED_TOTAL.labels(category="DELIVERY")._value.get()

        # Record match
        record_scene_ocr_provider_match("DELIVERY")

        # Verify increment
        new_value = SCENE_OCR_SERVICE_PROVIDERS_MATCHED_TOTAL.labels(
            category="DELIVERY"
        )._value.get()
        assert new_value == initial + 1

    def test_record_scene_ocr_provider_match_different_categories(self) -> None:
        """record_scene_ocr_provider_match should track different categories separately."""
        # Get initial values
        delivery_initial = SCENE_OCR_SERVICE_PROVIDERS_MATCHED_TOTAL.labels(
            category="DELIVERY"
        )._value.get()
        utility_initial = SCENE_OCR_SERVICE_PROVIDERS_MATCHED_TOTAL.labels(
            category="UTILITY"
        )._value.get()

        # Record matches for different categories
        record_scene_ocr_provider_match("DELIVERY")
        record_scene_ocr_provider_match("UTILITY")
        record_scene_ocr_provider_match("DELIVERY")

        # Verify increments
        assert (
            SCENE_OCR_SERVICE_PROVIDERS_MATCHED_TOTAL.labels(category="DELIVERY")._value.get()
            == delivery_initial + 2
        )
        assert (
            SCENE_OCR_SERVICE_PROVIDERS_MATCHED_TOTAL.labels(category="UTILITY")._value.get()
            == utility_initial + 1
        )

    def test_observe_scene_ocr_processing(self) -> None:
        """observe_scene_ocr_processing should record duration to histogram."""
        # Record processing time
        observe_scene_ocr_processing("full_frame", 0.15)

        # Verify observation was recorded (histogram sum increases)
        # We can check that the histogram has samples
        assert SCENE_OCR_PROCESSING_SECONDS.labels(source="full_frame")._sum.get() > 0

    def test_observe_scene_ocr_confidence(self) -> None:
        """observe_scene_ocr_confidence should record confidence to histogram."""
        # Record confidence
        observe_scene_ocr_confidence(0.85)

        # Verify observation was recorded
        assert SCENE_OCR_CONFIDENCE._sum.get() > 0


class TestMetricsServiceSceneOCR:
    """Test MetricsService Scene OCR methods."""

    @pytest.fixture
    def metrics_service(self) -> MetricsService:
        """Get the metrics service instance."""
        return get_metrics_service()

    def test_record_scene_ocr_request(self, metrics_service: MetricsService) -> None:
        """MetricsService.record_scene_ocr_request should increment counter."""
        initial = SCENE_OCR_REQUESTS_TOTAL.labels(source="full_frame")._value.get()

        metrics_service.record_scene_ocr_request("full_frame")

        assert SCENE_OCR_REQUESTS_TOTAL.labels(source="full_frame")._value.get() == initial + 1

    def test_record_scene_ocr_texts_detected(self, metrics_service: MetricsService) -> None:
        """MetricsService.record_scene_ocr_texts_detected should increment counter."""
        initial = SCENE_OCR_TEXTS_DETECTED_TOTAL._value.get()

        metrics_service.record_scene_ocr_texts_detected(3)

        assert SCENE_OCR_TEXTS_DETECTED_TOTAL._value.get() == initial + 3

    def test_record_scene_ocr_provider_match(self, metrics_service: MetricsService) -> None:
        """MetricsService.record_scene_ocr_provider_match should increment counter."""
        initial = SCENE_OCR_SERVICE_PROVIDERS_MATCHED_TOTAL.labels(
            category="EMERGENCY"
        )._value.get()

        metrics_service.record_scene_ocr_provider_match("EMERGENCY")

        assert (
            SCENE_OCR_SERVICE_PROVIDERS_MATCHED_TOTAL.labels(category="EMERGENCY")._value.get()
            == initial + 1
        )

    def test_observe_scene_ocr_processing(self, metrics_service: MetricsService) -> None:
        """MetricsService.observe_scene_ocr_processing should record duration."""
        initial_sum = SCENE_OCR_PROCESSING_SECONDS.labels(source="crop")._sum.get()

        metrics_service.observe_scene_ocr_processing("crop", 0.25)

        # The sum should increase by approximately 0.25
        new_sum = SCENE_OCR_PROCESSING_SECONDS.labels(source="crop")._sum.get()
        assert new_sum >= initial_sum + 0.25

    def test_observe_scene_ocr_confidence(self, metrics_service: MetricsService) -> None:
        """MetricsService.observe_scene_ocr_confidence should record confidence."""
        initial_sum = SCENE_OCR_CONFIDENCE._sum.get()

        metrics_service.observe_scene_ocr_confidence(0.92)

        # The sum should increase by approximately 0.92
        new_sum = SCENE_OCR_CONFIDENCE._sum.get()
        assert new_sum >= initial_sum + 0.92


class TestSceneOCRMetricsIntegration:
    """Integration tests for Scene OCR metrics with service."""

    @pytest.fixture
    def mock_scene_ocr_service(self):
        """Create a mock scene OCR service to test metric recording."""
        with patch("backend.services.scene_ocr_service.httpx.AsyncClient") as mock_client:
            yield mock_client

    def test_metrics_recorded_for_valid_source_labels(self) -> None:
        """Verify metrics can be recorded for all expected source labels."""
        # Record metrics for all expected sources
        for source in ["full_frame", "crop", "total"]:
            record_scene_ocr_request(source)
            observe_scene_ocr_processing(source, 0.1)

        # Verify all labels work without errors
        assert SCENE_OCR_REQUESTS_TOTAL.labels(source="full_frame")._value.get() > 0
        assert SCENE_OCR_REQUESTS_TOTAL.labels(source="crop")._value.get() > 0
        assert SCENE_OCR_REQUESTS_TOTAL.labels(source="total")._value.get() > 0

    def test_metrics_recorded_for_provider_categories(self) -> None:
        """Verify metrics can be recorded for all expected provider categories."""
        categories = [
            "DELIVERY",
            "UTILITY",
            "MAINTENANCE",
            "EMERGENCY",
            "FOOD_DELIVERY",
            "RIDESHARE",
        ]

        for category in categories:
            record_scene_ocr_provider_match(category)

        # Verify all categories work without errors
        for category in categories:
            assert (
                SCENE_OCR_SERVICE_PROVIDERS_MATCHED_TOTAL.labels(category=category)._value.get() > 0
            )
