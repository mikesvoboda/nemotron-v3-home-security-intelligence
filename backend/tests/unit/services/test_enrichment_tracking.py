"""Unit tests for enrichment status reporting (NEM-1672, reduced by R8 S2).

What this file asserted about enrichment TRACKING was three subjects, and R8
S2 deleted only one of them:

- ENDED: EnrichmentStatus / EnrichmentTrackingResult / EnrichmentResult —
  the enrichment_pipeline value objects (enum values, success-rate maths,
  compute_status, to_dict, the mutable-default edge cases). The tier is gone,
  so those classes are gone, and their suites went with the module.
- STILL SHIPPED, still pinned here: the Prometheus enrichment metrics in
  backend/core/metrics.py and the EnrichmentStatusEnum /
  EnrichmentStatusResponse API schema in backend/api/schemas/events.py. Both
  are live surfaces (the event API still answers an enrichment_status field),
  so their tests stay.
"""

from __future__ import annotations

# =============================================================================
# Metrics Recording Tests
# =============================================================================


class TestEnrichmentMetrics:
    """Tests for enrichment metrics recording."""

    def test_metric_functions_exist(self) -> None:
        """Test that metric functions are importable."""
        from backend.core.metrics import (
            record_enrichment_batch_status,
            record_enrichment_failure,
            record_enrichment_partial_batch,
            set_enrichment_success_rate,
        )

        # Ensure functions exist and are callable
        assert callable(record_enrichment_batch_status)
        assert callable(record_enrichment_failure)
        assert callable(record_enrichment_partial_batch)
        assert callable(set_enrichment_success_rate)

    def test_metric_counters_exist(self) -> None:
        """Test that metric counters are defined."""
        from backend.core.metrics import (
            ENRICHMENT_BATCH_STATUS_TOTAL,
            ENRICHMENT_FAILURES_TOTAL,
            ENRICHMENT_PARTIAL_BATCHES_TOTAL,
            ENRICHMENT_SUCCESS_RATE,
        )

        # Ensure metrics are defined
        assert ENRICHMENT_BATCH_STATUS_TOTAL is not None
        assert ENRICHMENT_FAILURES_TOTAL is not None
        assert ENRICHMENT_PARTIAL_BATCHES_TOTAL is not None
        assert ENRICHMENT_SUCCESS_RATE is not None

    def test_record_enrichment_batch_status(self) -> None:
        """Test recording batch status metric."""
        from backend.core.metrics import (
            ENRICHMENT_BATCH_STATUS_TOTAL,
            record_enrichment_batch_status,
        )

        # Record different statuses
        record_enrichment_batch_status("full")
        record_enrichment_batch_status("partial")
        record_enrichment_batch_status("failed")
        record_enrichment_batch_status("skipped")

        # Verify counters were incremented (they should be > 0)
        # Note: We can't test exact values because tests run in parallel
        # and counters are cumulative across tests
        assert ENRICHMENT_BATCH_STATUS_TOTAL._metrics is not None

    def test_record_enrichment_failure(self) -> None:
        """Test recording enrichment failure metric."""
        from backend.core.metrics import (
            ENRICHMENT_FAILURES_TOTAL,
            record_enrichment_failure,
        )

        # Record failures for different models
        record_enrichment_failure("violence")
        record_enrichment_failure("weather")
        record_enrichment_failure("clothing")

        # Verify counter exists
        assert ENRICHMENT_FAILURES_TOTAL._metrics is not None

    def test_set_enrichment_success_rate(self) -> None:
        """Test setting enrichment success rate gauge."""
        from backend.core.metrics import (
            ENRICHMENT_SUCCESS_RATE,
            set_enrichment_success_rate,
        )

        # Set success rates for different models
        set_enrichment_success_rate("violence", 1.0)
        set_enrichment_success_rate("weather", 0.5)
        set_enrichment_success_rate("clothing", 0.0)

        # Verify gauge exists
        assert ENRICHMENT_SUCCESS_RATE._metrics is not None

    def test_record_enrichment_partial_batch(self) -> None:
        """Test recording partial batch metric."""
        from backend.core.metrics import (
            ENRICHMENT_PARTIAL_BATCHES_TOTAL,
            record_enrichment_partial_batch,
        )

        # Record partial batch
        record_enrichment_partial_batch()

        # Verify counter exists
        assert ENRICHMENT_PARTIAL_BATCHES_TOTAL._value._value >= 0


class TestEnrichmentMetricsService:
    """Tests for MetricsService enrichment methods."""

    def test_metrics_service_has_enrichment_methods(self) -> None:
        """Test that MetricsService has all enrichment methods."""
        from backend.core.metrics import get_metrics_service

        service = get_metrics_service()

        # Check all methods exist
        assert hasattr(service, "record_enrichment_model_call")
        assert hasattr(service, "set_enrichment_success_rate")
        assert hasattr(service, "record_enrichment_partial_batch")
        assert hasattr(service, "record_enrichment_failure")
        assert hasattr(service, "record_enrichment_batch_status")

    def test_metrics_service_methods_callable(self) -> None:
        """Test that MetricsService enrichment methods are callable."""
        from backend.core.metrics import get_metrics_service

        service = get_metrics_service()

        # Call methods - they should not raise
        service.record_enrichment_model_call("test_model")
        service.set_enrichment_success_rate("test_model", 0.75)
        service.record_enrichment_partial_batch()
        service.record_enrichment_failure("test_model")
        service.record_enrichment_batch_status("partial")


# =============================================================================
# API Schema Tests
# =============================================================================


class TestEnrichmentStatusSchema:
    """Tests for API schema EnrichmentStatusResponse."""

    def test_schema_can_be_imported(self) -> None:
        """Test that schema classes are importable."""
        from backend.api.schemas.events import (
            EnrichmentStatusEnum,
            EnrichmentStatusResponse,
        )

        assert EnrichmentStatusEnum is not None
        assert EnrichmentStatusResponse is not None

    def test_enrichment_status_enum_values(self) -> None:
        """Test EnrichmentStatusEnum has correct values."""
        from backend.api.schemas.events import EnrichmentStatusEnum

        assert EnrichmentStatusEnum.FULL.value == "full"
        assert EnrichmentStatusEnum.PARTIAL.value == "partial"
        assert EnrichmentStatusEnum.FAILED.value == "failed"
        assert EnrichmentStatusEnum.SKIPPED.value == "skipped"

    def test_enrichment_status_response_creation(self) -> None:
        """Test creating EnrichmentStatusResponse."""
        from backend.api.schemas.events import (
            EnrichmentStatusEnum,
            EnrichmentStatusResponse,
        )

        response = EnrichmentStatusResponse(
            status=EnrichmentStatusEnum.PARTIAL,
            successful_models=["violence", "weather"],
            failed_models=["clothing"],
            errors={"clothing": "Model not loaded"},
            success_rate=0.67,
        )

        assert response.status == EnrichmentStatusEnum.PARTIAL
        assert response.successful_models == ["violence", "weather"]
        assert response.failed_models == ["clothing"]
        assert response.errors == {"clothing": "Model not loaded"}
        assert response.success_rate == 0.67

    def test_enrichment_status_response_defaults(self) -> None:
        """Test EnrichmentStatusResponse with minimal fields."""
        from backend.api.schemas.events import (
            EnrichmentStatusEnum,
            EnrichmentStatusResponse,
        )

        response = EnrichmentStatusResponse(
            status=EnrichmentStatusEnum.SKIPPED,
            success_rate=1.0,
        )

        assert response.status == EnrichmentStatusEnum.SKIPPED
        assert response.successful_models == []
        assert response.failed_models == []
        assert response.errors == {}
        assert response.success_rate == 1.0

    def test_event_response_has_enrichment_status_field(self) -> None:
        """Test EventResponse includes enrichment_status field."""
        from backend.api.schemas.events import EventResponse

        # Check the field exists in the model fields
        assert "enrichment_status" in EventResponse.model_fields

        # Check the field is optional (can be None)
        field = EventResponse.model_fields["enrichment_status"]
        assert field.default is None
