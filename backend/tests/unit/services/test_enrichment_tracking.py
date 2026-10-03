"""Unit tests for the enrichment status API schema.

Pinned here: EnrichmentStatusEnum / EnrichmentStatusResponse in
backend/api/schemas/events.py and the enrichment_status field on
EventResponse. The event API answers an enrichment_status field, so these
schemas are live surfaces.
"""

from __future__ import annotations

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
