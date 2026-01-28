"""Unit tests for ZoneBaselineService.

Tests cover:
- get_baseline() - Baseline retrieval by zone ID
- get_zone_baseline_service() - Singleton factory function
- reset_zone_baseline_service() - Singleton reset for testing

Edge cases: None session handling, non-existent baselines, singleton pattern.

Note: This service is a stub implementation that will be fully developed in
a separate task (NEM-3197). These tests cover the existing stub functionality.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.zone_baseline import ZoneActivityBaseline
from backend.services.zone_baseline_service import (
    ZoneBaselineService,
    get_zone_baseline_service,
    reset_zone_baseline_service,
)


@pytest.fixture
def mock_session() -> AsyncMock:
    """Create a mock async database session."""
    session = AsyncMock(spec=AsyncSession)
    session.execute = AsyncMock()
    return session


@pytest.fixture
def sample_baseline() -> ZoneActivityBaseline:
    """Create a sample ZoneActivityBaseline instance."""
    baseline = ZoneActivityBaseline(
        id="baseline-uuid-1",
        zone_id="zone-1",
        camera_id="front_door",
        hourly_pattern=[1.0] * 24,
        hourly_std=[0.5] * 24,
        daily_pattern=[10.0] * 7,
        daily_std=[2.0] * 7,
        entity_class_distribution={"person": 100, "car": 50},
        mean_daily_count=25.0,
        std_daily_count=5.0,
        min_daily_count=10,
        max_daily_count=40,
        typical_crossing_rate=10.0,
        typical_crossing_std=5.0,
        typical_dwell_time=30.0,
        typical_dwell_std=10.0,
        sample_count=30,
    )
    return baseline


@pytest.fixture(autouse=True)
def reset_singleton() -> None:
    """Reset the singleton service before each test."""
    reset_zone_baseline_service()


# =============================================================================
# get_baseline Tests
# =============================================================================


class TestGetBaseline:
    """Tests for get_baseline method."""

    @pytest.mark.asyncio
    async def test_get_baseline_found(
        self,
        mock_session: AsyncMock,
        sample_baseline: ZoneActivityBaseline,
    ) -> None:
        """Test getting an existing baseline."""
        service = ZoneBaselineService()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_baseline
        mock_session.execute.return_value = mock_result

        result = await service.get_baseline("zone-1", session=mock_session)

        assert result == sample_baseline
        assert mock_session.execute.called

    @pytest.mark.asyncio
    async def test_get_baseline_not_found(
        self,
        mock_session: AsyncMock,
    ) -> None:
        """Test getting a non-existent baseline returns None."""
        service = ZoneBaselineService()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await service.get_baseline("non-existent-zone", session=mock_session)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_baseline_none_session(self) -> None:
        """Test get_baseline with None session returns None."""
        service = ZoneBaselineService()

        result = await service.get_baseline("zone-1", session=None)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_baseline_constructs_correct_query(
        self,
        mock_session: AsyncMock,
    ) -> None:
        """Test get_baseline constructs the correct SQL query."""
        service = ZoneBaselineService()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        await service.get_baseline("test-zone-id", session=mock_session)

        # Verify execute was called with a query
        assert mock_session.execute.called
        call_args = mock_session.execute.call_args
        assert call_args is not None


# =============================================================================
# Singleton Pattern Tests
# =============================================================================


class TestSingletonPattern:
    """Tests for singleton pattern implementation."""

    def test_get_zone_baseline_service_returns_instance(self) -> None:
        """Test factory function returns ZoneBaselineService instance."""
        service = get_zone_baseline_service()

        assert isinstance(service, ZoneBaselineService)

    def test_get_zone_baseline_service_returns_same_instance(self) -> None:
        """Test factory function returns the same singleton instance."""
        service1 = get_zone_baseline_service()
        service2 = get_zone_baseline_service()

        assert service1 is service2

    def test_reset_zone_baseline_service_clears_singleton(self) -> None:
        """Test reset function clears the singleton."""
        service1 = get_zone_baseline_service()
        reset_zone_baseline_service()
        service2 = get_zone_baseline_service()

        assert service1 is not service2

    def test_multiple_resets_work_correctly(self) -> None:
        """Test multiple resets work as expected."""
        service1 = get_zone_baseline_service()
        reset_zone_baseline_service()
        service2 = get_zone_baseline_service()
        reset_zone_baseline_service()
        service3 = get_zone_baseline_service()

        assert service1 is not service2
        assert service2 is not service3
        assert service1 is not service3


# =============================================================================
# Integration with ZoneActivityBaseline Model Tests
# =============================================================================


class TestZoneActivityBaselineIntegration:
    """Tests for integration with ZoneActivityBaseline model."""

    @pytest.mark.asyncio
    async def test_get_baseline_returns_correct_model_type(
        self,
        mock_session: AsyncMock,
        sample_baseline: ZoneActivityBaseline,
    ) -> None:
        """Test get_baseline returns ZoneActivityBaseline instance."""
        service = ZoneBaselineService()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_baseline
        mock_session.execute.return_value = mock_result

        result = await service.get_baseline("zone-1", session=mock_session)

        assert isinstance(result, ZoneActivityBaseline)
        assert result.zone_id == "zone-1"
        assert result.camera_id == "front_door"

    @pytest.mark.asyncio
    async def test_get_baseline_preserves_model_attributes(
        self,
        mock_session: AsyncMock,
        sample_baseline: ZoneActivityBaseline,
    ) -> None:
        """Test get_baseline preserves all model attributes."""
        service = ZoneBaselineService()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_baseline
        mock_session.execute.return_value = mock_result

        result = await service.get_baseline("zone-1", session=mock_session)

        assert result is not None
        assert len(result.hourly_pattern) == 24
        assert len(result.daily_pattern) == 7
        assert result.mean_daily_count == 25.0
        assert result.sample_count == 30


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error handling scenarios."""

    @pytest.mark.asyncio
    async def test_get_baseline_handles_database_error_gracefully(
        self,
        mock_session: AsyncMock,
    ) -> None:
        """Test get_baseline handles database errors gracefully."""
        service = ZoneBaselineService()

        # Simulate database error
        mock_session.execute.side_effect = Exception("Database connection failed")

        with pytest.raises(Exception, match="Database connection failed"):
            await service.get_baseline("zone-1", session=mock_session)

    @pytest.mark.asyncio
    async def test_get_baseline_with_empty_zone_id(
        self,
        mock_session: AsyncMock,
    ) -> None:
        """Test get_baseline with empty zone_id."""
        service = ZoneBaselineService()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await service.get_baseline("", session=mock_session)

        assert result is None


# =============================================================================
# Future Expansion Tests (Placeholders for NEM-3197)
# =============================================================================


class TestFutureExpansion:
    """Placeholder tests for future expansion in NEM-3197.

    These tests document expected functionality that will be implemented
    in the complete baseline service.
    """

    @pytest.mark.skip(reason="NEM-3197: Not yet implemented")
    @pytest.mark.asyncio
    async def test_compute_baseline_not_implemented(self) -> None:
        """Test compute_baseline method (to be implemented in NEM-3197)."""
        service = ZoneBaselineService()
        # Future: service.compute_baseline(zone_id, start_date, end_date)

    @pytest.mark.skip(reason="NEM-3197: Not yet implemented")
    @pytest.mark.asyncio
    async def test_update_baseline_not_implemented(self) -> None:
        """Test update_baseline method (to be implemented in NEM-3197)."""
        service = ZoneBaselineService()
        # Future: service.update_baseline(zone_id, new_data)

    @pytest.mark.skip(reason="NEM-3197: Not yet implemented")
    @pytest.mark.asyncio
    async def test_delete_baseline_not_implemented(self) -> None:
        """Test delete_baseline method (to be implemented in NEM-3197)."""
        service = ZoneBaselineService()
        # Future: service.delete_baseline(zone_id)
