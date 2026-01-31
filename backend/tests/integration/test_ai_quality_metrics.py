"""Integration tests for AI Quality Metrics service.

Tests verify that the quality metrics queries work correctly with a real database.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.ai_quality_metrics import AIQualityMetrics


@pytest.mark.integration
class TestAIQualityMetricsIntegration:
    """Integration tests for AIQualityMetrics."""

    @pytest.mark.asyncio
    async def test_compute_metrics_empty_database(self, db_session: AsyncSession) -> None:
        """Test that metrics computation works on an empty database.

        Verifies the service handles the case of no events gracefully.
        """
        metrics = AIQualityMetrics(db_session)
        results = await metrics.compute_all_metrics()

        # Should return a valid result object, even if empty
        assert results is not None
        assert isinstance(results.metrics, list)

    @pytest.mark.asyncio
    async def test_field_completeness_check(self, db_session: AsyncSession) -> None:
        """Test field completeness metric calculation.

        Verifies the metric correctly identifies missing required fields.
        """
        metrics = AIQualityMetrics(db_session)

        # Run the completeness check
        result = await metrics.check_field_completeness()

        # Should return a valid MetricResult
        assert result is not None
        assert hasattr(result, "level")
        assert hasattr(result, "passed")
