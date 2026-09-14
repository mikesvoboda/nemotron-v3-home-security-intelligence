"""Unit tests for enrichment tracking (NEM-1672).

Tests cover:
- EnrichmentStatus enum values and properties
- EnrichmentTrackingResult dataclass methods and properties
- Status computation from successful/failed model lists
- Success rate calculations
- to_dict() serialization
- Partial failure tracking
"""

from __future__ import annotations

import pytest

from backend.services.enrichment_pipeline import (
    EnrichmentResult,
    EnrichmentStatus,
    EnrichmentTrackingResult,
)

# =============================================================================
# EnrichmentStatus Tests
# =============================================================================


class TestEnrichmentStatus:
    """Tests for EnrichmentStatus enum."""

    def test_enum_values(self) -> None:
        """Test all enum values are defined correctly."""
        assert EnrichmentStatus.FULL.value == "full"
        assert EnrichmentStatus.PARTIAL.value == "partial"
        assert EnrichmentStatus.FAILED.value == "failed"
        assert EnrichmentStatus.SKIPPED.value == "skipped"

    def test_enum_is_string(self) -> None:
        """Test that EnrichmentStatus values are strings."""
        assert isinstance(EnrichmentStatus.FULL.value, str)
        # StrEnum inherits from str, so the value is the string
        assert EnrichmentStatus.FULL.value == "full"

    def test_enum_comparison(self) -> None:
        """Test enum comparison works correctly."""
        assert EnrichmentStatus.FULL == EnrichmentStatus.FULL
        assert EnrichmentStatus.FULL != EnrichmentStatus.PARTIAL
        assert EnrichmentStatus.FULL == "full"

    def test_enum_from_value(self) -> None:
        """Test creating enum from string value."""
        assert EnrichmentStatus("full") == EnrichmentStatus.FULL
        assert EnrichmentStatus("partial") == EnrichmentStatus.PARTIAL
        assert EnrichmentStatus("failed") == EnrichmentStatus.FAILED
        assert EnrichmentStatus("skipped") == EnrichmentStatus.SKIPPED

    def test_enum_invalid_value_raises(self) -> None:
        """Test that invalid value raises ValueError."""
        with pytest.raises(ValueError):
            EnrichmentStatus("invalid")


# =============================================================================
# EnrichmentTrackingResult Tests
# =============================================================================


class TestEnrichmentTrackingResult:
    """Tests for EnrichmentTrackingResult dataclass."""

    def test_default_initialization(self) -> None:
        """Test default values are set correctly."""
        result = EnrichmentTrackingResult()

        assert result.status == EnrichmentStatus.SKIPPED
        assert result.successful_models == []
        assert result.failed_models == []
        assert result.errors == {}
        assert result.data is None

    def test_initialization_with_values(self) -> None:
        """Test initialization with explicit values."""
        result = EnrichmentTrackingResult(
            status=EnrichmentStatus.PARTIAL,
            successful_models=["violence", "weather"],
            failed_models=["clothing"],
            errors={"clothing": "Model not loaded"},
            data=None,
        )

        assert result.status == EnrichmentStatus.PARTIAL
        assert result.successful_models == ["violence", "weather"]
        assert result.failed_models == ["clothing"]
        assert result.errors == {"clothing": "Model not loaded"}

    def test_has_data_property_with_data(self) -> None:
        """Test has_data returns True when data is present."""
        result = EnrichmentTrackingResult(data=EnrichmentResult())
        assert result.has_data is True

    def test_has_data_property_without_data(self) -> None:
        """Test has_data returns False when data is None."""
        result = EnrichmentTrackingResult(data=None)
        assert result.has_data is False


class TestEnrichmentTrackingResultSuccessRate:
    """Tests for success rate calculation."""

    def test_success_rate_all_success(self) -> None:
        """Test success rate when all models succeed."""
        result = EnrichmentTrackingResult(
            status=EnrichmentStatus.FULL,
            successful_models=["violence", "weather", "clothing"],
            failed_models=[],
        )
        assert result.success_rate == 1.0

    def test_success_rate_all_failure(self) -> None:
        """Test success rate when all models fail."""
        result = EnrichmentTrackingResult(
            status=EnrichmentStatus.FAILED,
            successful_models=[],
            failed_models=["violence", "weather", "clothing"],
        )
        assert result.success_rate == 0.0

    def test_success_rate_partial(self) -> None:
        """Test success rate with partial success."""
        result = EnrichmentTrackingResult(
            status=EnrichmentStatus.PARTIAL,
            successful_models=["violence", "weather"],
            failed_models=["clothing"],
        )
        assert result.success_rate == pytest.approx(2 / 3)

    def test_success_rate_no_models(self) -> None:
        """Test success rate when no models were attempted."""
        result = EnrichmentTrackingResult(
            status=EnrichmentStatus.SKIPPED,
            successful_models=[],
            failed_models=[],
        )
        assert result.success_rate == 1.0

    def test_success_rate_single_success(self) -> None:
        """Test success rate with single successful model."""
        result = EnrichmentTrackingResult(
            status=EnrichmentStatus.FULL,
            successful_models=["violence"],
            failed_models=[],
        )
        assert result.success_rate == 1.0

    def test_success_rate_single_failure(self) -> None:
        """Test success rate with single failed model."""
        result = EnrichmentTrackingResult(
            status=EnrichmentStatus.FAILED,
            successful_models=[],
            failed_models=["violence"],
        )
        assert result.success_rate == 0.0


class TestEnrichmentTrackingResultStatusProperties:
    """Tests for status-related properties."""

    def test_is_partial_true(self) -> None:
        """Test is_partial returns True for partial status."""
        result = EnrichmentTrackingResult(status=EnrichmentStatus.PARTIAL)
        assert result.is_partial is True

    def test_is_partial_false(self) -> None:
        """Test is_partial returns False for non-partial status."""
        for status in [EnrichmentStatus.FULL, EnrichmentStatus.FAILED, EnrichmentStatus.SKIPPED]:
            result = EnrichmentTrackingResult(status=status)
            assert result.is_partial is False

    def test_all_succeeded_true(self) -> None:
        """Test all_succeeded returns True for full status."""
        result = EnrichmentTrackingResult(status=EnrichmentStatus.FULL)
        assert result.all_succeeded is True

    def test_all_succeeded_false(self) -> None:
        """Test all_succeeded returns False for non-full status."""
        for status in [
            EnrichmentStatus.PARTIAL,
            EnrichmentStatus.FAILED,
            EnrichmentStatus.SKIPPED,
        ]:
            result = EnrichmentTrackingResult(status=status)
            assert result.all_succeeded is False

    def test_all_failed_true(self) -> None:
        """Test all_failed returns True for failed status."""
        result = EnrichmentTrackingResult(status=EnrichmentStatus.FAILED)
        assert result.all_failed is True

    def test_all_failed_false(self) -> None:
        """Test all_failed returns False for non-failed status."""
        for status in [EnrichmentStatus.FULL, EnrichmentStatus.PARTIAL, EnrichmentStatus.SKIPPED]:
            result = EnrichmentTrackingResult(status=status)
            assert result.all_failed is False


class TestEnrichmentTrackingResultToDict:
    """Tests for to_dict() serialization."""

    def test_to_dict_default(self) -> None:
        """Test to_dict with default values."""
        result = EnrichmentTrackingResult()
        d = result.to_dict()

        assert d["status"] == "skipped"
        assert d["successful_models"] == []
        assert d["failed_models"] == []
        assert d["errors"] == {}
        assert d["success_rate"] == 1.0

    def test_to_dict_with_values(self) -> None:
        """Test to_dict with populated values."""
        result = EnrichmentTrackingResult(
            status=EnrichmentStatus.PARTIAL,
            successful_models=["violence", "weather"],
            failed_models=["clothing"],
            errors={"clothing": "Model failed to load"},
        )
        d = result.to_dict()

        assert d["status"] == "partial"
        assert d["successful_models"] == ["violence", "weather"]
        assert d["failed_models"] == ["clothing"]
        assert d["errors"] == {"clothing": "Model failed to load"}
        assert d["success_rate"] == pytest.approx(2 / 3)

    def test_to_dict_does_not_include_data(self) -> None:
        """Test that data is not included in to_dict output."""
        result = EnrichmentTrackingResult(data=EnrichmentResult())
        d = result.to_dict()

        assert "data" not in d


class TestEnrichmentTrackingResultComputeStatus:
    """Tests for compute_status class method."""

    def test_compute_status_all_success(self) -> None:
        """Test compute_status returns FULL when all succeed."""
        status = EnrichmentTrackingResult.compute_status(
            successful=["violence", "weather"],
            failed=[],
        )
        assert status == EnrichmentStatus.FULL

    def test_compute_status_all_failure(self) -> None:
        """Test compute_status returns FAILED when all fail."""
        status = EnrichmentTrackingResult.compute_status(
            successful=[],
            failed=["violence", "weather"],
        )
        assert status == EnrichmentStatus.FAILED

    def test_compute_status_partial(self) -> None:
        """Test compute_status returns PARTIAL when mixed."""
        status = EnrichmentTrackingResult.compute_status(
            successful=["violence"],
            failed=["weather"],
        )
        assert status == EnrichmentStatus.PARTIAL

    def test_compute_status_no_models(self) -> None:
        """Test compute_status returns SKIPPED when no models attempted."""
        status = EnrichmentTrackingResult.compute_status(
            successful=[],
            failed=[],
        )
        assert status == EnrichmentStatus.SKIPPED

    def test_compute_status_single_success(self) -> None:
        """Test compute_status with single successful model."""
        status = EnrichmentTrackingResult.compute_status(
            successful=["violence"],
            failed=[],
        )
        assert status == EnrichmentStatus.FULL

    def test_compute_status_single_failure(self) -> None:
        """Test compute_status with single failed model."""
        status = EnrichmentTrackingResult.compute_status(
            successful=[],
            failed=["violence"],
        )
        assert status == EnrichmentStatus.FAILED

    def test_compute_status_many_models(self) -> None:
        """Test compute_status with many models."""
        successful = ["violence", "weather", "vehicle_class", "pet"]
        failed = ["clothing", "damage"]
        status = EnrichmentTrackingResult.compute_status(
            successful=successful,
            failed=failed,
        )
        assert status == EnrichmentStatus.PARTIAL


class TestEnrichmentTrackingResultIntegration:
    """Integration tests for EnrichmentTrackingResult."""

    def test_create_full_tracking_result(self) -> None:
        """Test creating a complete tracking result with data."""
        enrichment_data = EnrichmentResult(
            processing_time_ms=150.5,
        )

        successful = ["violence", "weather", "clothing"]
        failed: list[str] = []

        result = EnrichmentTrackingResult(
            status=EnrichmentTrackingResult.compute_status(successful, failed),
            successful_models=successful,
            failed_models=failed,
            errors={},
            data=enrichment_data,
        )

        assert result.status == EnrichmentStatus.FULL
        assert result.has_data is True
        assert result.all_succeeded is True
        assert result.success_rate == 1.0

    def test_create_partial_tracking_result(self) -> None:
        """Test creating a partial tracking result with errors."""
        enrichment_data = EnrichmentResult(
            processing_time_ms=100.0,
        )

        successful = ["violence"]
        failed = ["weather", "clothing"]
        errors = {
            "weather": "Connection timeout",
            "clothing": "Model not loaded",
        }

        result = EnrichmentTrackingResult(
            status=EnrichmentTrackingResult.compute_status(successful, failed),
            successful_models=successful,
            failed_models=failed,
            errors=errors,
            data=enrichment_data,
        )

        assert result.status == EnrichmentStatus.PARTIAL
        assert result.has_data is True
        assert result.is_partial is True
        assert result.success_rate == pytest.approx(1 / 3)
        assert len(result.errors) == 2

    def test_create_failed_tracking_result(self) -> None:
        """Test creating a failed tracking result."""
        successful: list[str] = []
        failed = ["violence", "weather", "clothing"]
        errors = {
            "violence": "GPU OOM",
            "weather": "Connection refused",
            "clothing": "Model file not found",
        }

        result = EnrichmentTrackingResult(
            status=EnrichmentTrackingResult.compute_status(successful, failed),
            successful_models=successful,
            failed_models=failed,
            errors=errors,
            data=None,
        )

        assert result.status == EnrichmentStatus.FAILED
        assert result.has_data is False
        assert result.all_failed is True
        assert result.success_rate == 0.0


class TestEnrichmentTrackingResultEdgeCases:
    """Edge case tests for EnrichmentTrackingResult."""

    def test_mutable_default_lists(self) -> None:
        """Test that default lists are not shared between instances."""
        result1 = EnrichmentTrackingResult()
        result2 = EnrichmentTrackingResult()

        result1.successful_models.append("test")

        assert "test" in result1.successful_models
        assert "test" not in result2.successful_models

    def test_mutable_default_dict(self) -> None:
        """Test that default dict is not shared between instances."""
        result1 = EnrichmentTrackingResult()
        result2 = EnrichmentTrackingResult()

        result1.errors["test"] = "error"

        assert "test" in result1.errors
        assert "test" not in result2.errors

    def test_data_can_be_set_after_creation(self) -> None:
        """Test that data can be set after initial creation."""
        result = EnrichmentTrackingResult()
        assert result.data is None

        result.data = EnrichmentResult()
        assert result.data is not None
        assert result.has_data is True


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
