"""Unit tests for the MaterializedViewService.

Tests cover:
- Refreshing materialized views
- Querying aggregated data
- Error handling
"""

from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.materialized_views import MaterializedViewService


@pytest.fixture
def mock_session() -> AsyncMock:
    """Create a mock async session."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session


@pytest.fixture
def service(mock_session: AsyncMock) -> MaterializedViewService:
    """Create a MaterializedViewService with mocked session."""
    return MaterializedViewService(mock_session)


class TestMaterializedViewService:
    """Tests for MaterializedViewService."""

    def test_managed_views_list(self, service: MaterializedViewService) -> None:
        """Test that MANAGED_VIEWS contains expected views."""
        expected_views = [
            "mv_daily_detection_counts",
            "mv_hourly_event_stats",
            "mv_detection_type_distribution",
            "mv_entity_tracking_summary",
            "mv_risk_score_aggregations",
            "mv_enrichment_summary",
        ]
        assert expected_views == service.MANAGED_VIEWS

    @pytest.mark.asyncio
    async def test_refresh_all_views_concurrent(
        self, service: MaterializedViewService, mock_session: AsyncMock
    ) -> None:
        """Test refreshing all views concurrently."""
        mock_session.execute.return_value = MagicMock()

        results = await service.refresh_all_views(concurrently=True)

        # Should call the refresh function once
        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()

        # All views should report success
        for view in service.MANAGED_VIEWS:
            assert results[view] is True

    @pytest.mark.asyncio
    async def test_refresh_all_views_non_concurrent(
        self, service: MaterializedViewService, mock_session: AsyncMock
    ) -> None:
        """Test refreshing all views non-concurrently."""
        mock_session.execute.return_value = MagicMock()

        results = await service.refresh_all_views(concurrently=False)

        # Should call execute for each view
        assert mock_session.execute.call_count == len(service.MANAGED_VIEWS)
        assert mock_session.commit.call_count == len(service.MANAGED_VIEWS)

        # All views should report success
        for view in service.MANAGED_VIEWS:
            assert results[view] is True

    @pytest.mark.asyncio
    async def test_refresh_all_views_failure(
        self, service: MaterializedViewService, mock_session: AsyncMock
    ) -> None:
        """Test handling refresh failure."""
        mock_session.execute.side_effect = Exception("Database error")

        results = await service.refresh_all_views(concurrently=True)

        mock_session.rollback.assert_called_once()

        # All views should report failure
        for view in service.MANAGED_VIEWS:
            assert results[view] is False

    @pytest.mark.asyncio
    async def test_refresh_single_view(
        self, service: MaterializedViewService, mock_session: AsyncMock
    ) -> None:
        """Test refreshing a single view."""
        mock_session.execute.return_value = MagicMock()

        result = await service.refresh_view("mv_daily_detection_counts")

        assert result is True
        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_refresh_unknown_view(
        self, service: MaterializedViewService, mock_session: AsyncMock
    ) -> None:
        """Test refreshing an unknown view returns False."""
        result = await service.refresh_view("unknown_view")

        assert result is False
        mock_session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_daily_detection_counts(
        self, service: MaterializedViewService, mock_session: AsyncMock
    ) -> None:
        """Test querying daily detection counts."""
        # Mock result
        mock_row = MagicMock()
        mock_row.detection_date = date(2026, 1, 23)
        mock_row.camera_id = "front_door"
        mock_row.object_type = "person"
        mock_row.detection_count = 42
        mock_row.avg_confidence = 0.85
        mock_row.first_detection = datetime(2026, 1, 23, 8, 0, tzinfo=UTC)
        mock_row.last_detection = datetime(2026, 1, 23, 18, 0, tzinfo=UTC)

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row]
        mock_session.execute.return_value = mock_result

        results = await service.get_daily_detection_counts(
            start_date=date(2026, 1, 20),
            end_date=date(2026, 1, 23),
            camera_id="front_door",
        )

        assert len(results) == 1
        assert results[0]["detection_date"] == date(2026, 1, 23)
        assert results[0]["camera_id"] == "front_door"
        assert results[0]["object_type"] == "person"
        assert results[0]["detection_count"] == 42
        assert results[0]["avg_confidence"] == 0.85

    @pytest.mark.asyncio
    async def test_get_hourly_event_stats(
        self, service: MaterializedViewService, mock_session: AsyncMock
    ) -> None:
        """Test querying hourly event stats."""
        mock_row = MagicMock()
        mock_row.event_date = date(2026, 1, 23)
        mock_row.event_hour = 14
        mock_row.camera_id = "back_yard"
        mock_row.risk_level = "medium"
        mock_row.event_count = 5
        mock_row.avg_risk_score = 45.5
        mock_row.reviewed_count = 3
        mock_row.fast_path_count = 2

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row]
        mock_session.execute.return_value = mock_result

        results = await service.get_hourly_event_stats(
            start_date=date(2026, 1, 23),
            risk_level="medium",
        )

        assert len(results) == 1
        assert results[0]["event_date"] == date(2026, 1, 23)
        assert results[0]["event_hour"] == 14
        assert results[0]["risk_level"] == "medium"
        assert results[0]["event_count"] == 5
        assert results[0]["avg_risk_score"] == 45.5

    @pytest.mark.asyncio
    async def test_get_risk_score_aggregations(
        self, service: MaterializedViewService, mock_session: AsyncMock
    ) -> None:
        """Test querying risk score aggregations."""
        mock_row = MagicMock()
        mock_row.camera_id = "garage"
        mock_row.event_date = date(2026, 1, 23)
        mock_row.total_events = 20
        mock_row.low_risk_count = 10
        mock_row.medium_risk_count = 6
        mock_row.high_risk_count = 3
        mock_row.critical_risk_count = 1
        mock_row.avg_risk_score = 35.0
        mock_row.median_risk_score = 30.0
        mock_row.p95_risk_score = 75.0
        mock_row.max_risk_score = 90

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row]
        mock_session.execute.return_value = mock_result

        results = await service.get_risk_score_aggregations(
            camera_id="garage",
        )

        assert len(results) == 1
        assert results[0]["camera_id"] == "garage"
        assert results[0]["total_events"] == 20
        assert results[0]["low_risk_count"] == 10
        assert results[0]["critical_risk_count"] == 1
        assert results[0]["p95_risk_score"] == 75.0

    @pytest.mark.asyncio
    async def test_get_detection_type_distribution(
        self, service: MaterializedViewService, mock_session: AsyncMock
    ) -> None:
        """Test querying detection type distribution."""
        mock_row = MagicMock()
        mock_row.camera_id = "front_door"
        mock_row.object_type = "person"
        mock_row.total_count = 500
        mock_row.last_24h_count = 20
        mock_row.last_7d_count = 150
        mock_row.last_30d_count = 450
        mock_row.avg_confidence = 0.92
        mock_row.first_seen = datetime(2026, 1, 1, tzinfo=UTC)
        mock_row.last_seen = datetime(2026, 1, 23, tzinfo=UTC)

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row]
        mock_session.execute.return_value = mock_result

        results = await service.get_detection_type_distribution()

        assert len(results) == 1
        assert results[0]["camera_id"] == "front_door"
        assert results[0]["object_type"] == "person"
        assert results[0]["total_count"] == 500
        assert results[0]["last_24h_count"] == 20

    @pytest.mark.asyncio
    async def test_get_entity_tracking_summary(
        self, service: MaterializedViewService, mock_session: AsyncMock
    ) -> None:
        """Test querying entity tracking summary."""
        mock_row = MagicMock()
        mock_row.entity_type = "person"
        mock_row.trust_status = "unknown"
        mock_row.entity_count = 15
        mock_row.total_detections = 150
        mock_row.avg_detections_per_entity = 10.0
        mock_row.earliest_first_seen = datetime(2026, 1, 1, tzinfo=UTC)
        mock_row.latest_last_seen = datetime(2026, 1, 23, tzinfo=UTC)
        mock_row.active_last_24h = 5
        mock_row.active_last_7d = 12

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row]
        mock_session.execute.return_value = mock_result

        results = await service.get_entity_tracking_summary()

        assert len(results) == 1
        assert results[0]["entity_type"] == "person"
        assert results[0]["trust_status"] == "unknown"
        assert results[0]["entity_count"] == 15
        assert results[0]["active_last_24h"] == 5

    @pytest.mark.asyncio
    async def test_get_enrichment_summary(
        self, service: MaterializedViewService, mock_session: AsyncMock
    ) -> None:
        """Test querying enrichment summary."""
        mock_row = MagicMock()
        mock_row.camera_id = "front_door"
        mock_row.total_detections = 1000
        mock_row.with_enrichment = 950
        mock_row.with_license_plates = 50
        mock_row.total_license_plates = 55
        mock_row.with_faces = 200
        mock_row.total_faces = 250
        mock_row.violent_detections = 2
        mock_row.with_vehicle_classification = 100
        mock_row.with_pet_classification = 30
        mock_row.avg_image_quality = 75.5
        mock_row.avg_processing_time_ms = 125.3

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row]
        mock_session.execute.return_value = mock_result

        results = await service.get_enrichment_summary()

        assert len(results) == 1
        assert results[0]["camera_id"] == "front_door"
        assert results[0]["total_detections"] == 1000
        assert results[0]["with_license_plates"] == 50
        assert results[0]["violent_detections"] == 2

    @pytest.mark.asyncio
    async def test_check_view_exists_true(
        self, service: MaterializedViewService, mock_session: AsyncMock
    ) -> None:
        """Test checking if view exists when it does."""
        mock_result = MagicMock()
        mock_result.fetchone.return_value = (True,)
        mock_session.execute.return_value = mock_result

        exists = await service.check_view_exists("mv_daily_detection_counts")

        assert exists is True

    @pytest.mark.asyncio
    async def test_check_view_exists_false(
        self, service: MaterializedViewService, mock_session: AsyncMock
    ) -> None:
        """Test checking if view exists when it doesn't."""
        mock_result = MagicMock()
        mock_result.fetchone.return_value = (False,)
        mock_session.execute.return_value = mock_result

        exists = await service.check_view_exists("nonexistent_view")

        assert exists is False

    @pytest.mark.asyncio
    async def test_get_view_stats(
        self, service: MaterializedViewService, mock_session: AsyncMock
    ) -> None:
        """Test getting statistics for all views."""
        # Mock exists check
        exists_result = MagicMock()
        exists_result.fetchone.return_value = (True,)

        # Mock count query
        count_result = MagicMock()
        count_result.scalar.return_value = 100

        # Mock size query
        size_result = MagicMock()
        size_result.scalar.return_value = 8192

        # Configure execute to return different results based on call order
        mock_session.execute.side_effect = [
            exists_result,
            count_result,
            size_result,
        ] * len(service.MANAGED_VIEWS)

        stats = await service.get_view_stats()

        assert len(stats) == len(service.MANAGED_VIEWS)
        for stat in stats:
            assert stat["exists"] is True
            assert stat["row_count"] == 100
            assert stat["size_bytes"] == 8192

    @pytest.mark.asyncio
    async def test_handles_null_values(
        self, service: MaterializedViewService, mock_session: AsyncMock
    ) -> None:
        """Test that service handles null values gracefully."""
        mock_row = MagicMock()
        mock_row.detection_date = date(2026, 1, 23)
        mock_row.camera_id = "front_door"
        mock_row.object_type = None  # Null object type
        mock_row.detection_count = 10
        mock_row.avg_confidence = None  # Null confidence
        mock_row.first_detection = None
        mock_row.last_detection = None

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row]
        mock_session.execute.return_value = mock_result

        results = await service.get_daily_detection_counts()

        assert len(results) == 1
        assert results[0]["object_type"] is None
        assert results[0]["avg_confidence"] is None

    @pytest.mark.asyncio
    async def test_refresh_all_views_non_concurrent_partial_failure(
        self, service: MaterializedViewService, mock_session: AsyncMock
    ) -> None:
        """Test non-concurrent refresh with partial failures."""
        # First view succeeds, second fails, third succeeds
        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 2:
                raise Exception("View refresh failed")
            return MagicMock()

        mock_session.execute.side_effect = side_effect

        results = await service.refresh_all_views(concurrently=False)

        # Should have tried all views
        assert mock_session.execute.call_count == len(service.MANAGED_VIEWS)
        # Second view should have failed
        assert results[service.MANAGED_VIEWS[1]] is False
        # First and third views should have succeeded
        assert results[service.MANAGED_VIEWS[0]] is True
        assert results[service.MANAGED_VIEWS[2]] is True

    @pytest.mark.asyncio
    async def test_refresh_view_failure(
        self, service: MaterializedViewService, mock_session: AsyncMock
    ) -> None:
        """Test refresh_view with database error."""
        mock_session.execute.side_effect = Exception("Database connection lost")

        result = await service.refresh_view("mv_daily_detection_counts")

        assert result is False
        mock_session.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_hourly_event_stats_with_all_filters(
        self, service: MaterializedViewService, mock_session: AsyncMock
    ) -> None:
        """Test querying hourly event stats with all optional filters applied."""
        mock_row = MagicMock()
        mock_row.event_date = date(2026, 1, 23)
        mock_row.event_hour = 14
        mock_row.camera_id = "back_yard"
        mock_row.risk_level = "high"
        mock_row.event_count = 8
        mock_row.avg_risk_score = 72.5
        mock_row.reviewed_count = 4
        mock_row.fast_path_count = 1

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row]
        mock_session.execute.return_value = mock_result

        results = await service.get_hourly_event_stats(
            start_date=date(2026, 1, 20),
            end_date=date(2026, 1, 25),
            camera_id="back_yard",
            risk_level="high",
        )

        assert len(results) == 1
        assert results[0]["camera_id"] == "back_yard"
        assert results[0]["risk_level"] == "high"
        # Verify the query was called with all parameters
        call_args = mock_session.execute.call_args
        assert call_args[0][1]["start_date"] == date(2026, 1, 20)
        assert call_args[0][1]["end_date"] == date(2026, 1, 25)
        assert call_args[0][1]["camera_id"] == "back_yard"
        assert call_args[0][1]["risk_level"] == "high"

    @pytest.mark.asyncio
    async def test_get_risk_score_aggregations_with_all_filters(
        self, service: MaterializedViewService, mock_session: AsyncMock
    ) -> None:
        """Test querying risk score aggregations with all optional filters applied."""
        mock_row = MagicMock()
        mock_row.camera_id = "garage"
        mock_row.event_date = date(2026, 1, 23)
        mock_row.total_events = 20
        mock_row.low_risk_count = 10
        mock_row.medium_risk_count = 6
        mock_row.high_risk_count = 3
        mock_row.critical_risk_count = 1
        mock_row.avg_risk_score = 35.0
        mock_row.median_risk_score = 30.0
        mock_row.p95_risk_score = 75.0
        mock_row.max_risk_score = 90

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row]
        mock_session.execute.return_value = mock_result

        results = await service.get_risk_score_aggregations(
            start_date=date(2026, 1, 20),
            end_date=date(2026, 1, 25),
            camera_id="garage",
        )

        assert len(results) == 1
        assert results[0]["camera_id"] == "garage"
        # Verify the query was called with all parameters
        call_args = mock_session.execute.call_args
        assert call_args[0][1]["start_date"] == date(2026, 1, 20)
        assert call_args[0][1]["end_date"] == date(2026, 1, 25)
        assert call_args[0][1]["camera_id"] == "garage"

    @pytest.mark.asyncio
    async def test_get_detection_type_distribution_with_camera_filter(
        self, service: MaterializedViewService, mock_session: AsyncMock
    ) -> None:
        """Test querying detection type distribution with camera_id filter."""
        mock_row = MagicMock()
        mock_row.camera_id = "front_door"
        mock_row.object_type = "vehicle"
        mock_row.total_count = 200
        mock_row.last_24h_count = 15
        mock_row.last_7d_count = 80
        mock_row.last_30d_count = 180
        mock_row.avg_confidence = 0.88
        mock_row.first_seen = datetime(2026, 1, 1, tzinfo=UTC)
        mock_row.last_seen = datetime(2026, 1, 23, tzinfo=UTC)

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row]
        mock_session.execute.return_value = mock_result

        results = await service.get_detection_type_distribution(camera_id="front_door")

        assert len(results) == 1
        assert results[0]["camera_id"] == "front_door"
        assert results[0]["object_type"] == "vehicle"
        # Verify the query was called with camera_id parameter
        call_args = mock_session.execute.call_args
        assert call_args[0][1]["camera_id"] == "front_door"

    @pytest.mark.asyncio
    async def test_get_enrichment_summary_with_camera_filter(
        self, service: MaterializedViewService, mock_session: AsyncMock
    ) -> None:
        """Test querying enrichment summary with camera_id filter."""
        mock_row = MagicMock()
        mock_row.camera_id = "back_yard"
        mock_row.total_detections = 500
        mock_row.with_enrichment = 475
        mock_row.with_license_plates = 25
        mock_row.total_license_plates = 28
        mock_row.with_faces = 100
        mock_row.total_faces = 125
        mock_row.violent_detections = 1
        mock_row.with_vehicle_classification = 50
        mock_row.with_pet_classification = 15
        mock_row.avg_image_quality = 68.5
        mock_row.avg_processing_time_ms = 145.2

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row]
        mock_session.execute.return_value = mock_result

        results = await service.get_enrichment_summary(camera_id="back_yard")

        assert len(results) == 1
        assert results[0]["camera_id"] == "back_yard"
        assert results[0]["total_detections"] == 500
        # Verify the query was called with camera_id parameter
        call_args = mock_session.execute.call_args
        assert call_args[0][1]["camera_id"] == "back_yard"

    @pytest.mark.asyncio
    async def test_get_view_stats_view_not_exists(
        self, service: MaterializedViewService, mock_session: AsyncMock
    ) -> None:
        """Test get_view_stats when a view doesn't exist."""
        # Mock first view doesn't exist, second view exists
        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:  # First check_view_exists call
                mock_result = MagicMock()
                mock_result.fetchone.return_value = (False,)
                return mock_result
            elif call_count[0] == 2:  # Second check_view_exists call
                mock_result = MagicMock()
                mock_result.fetchone.return_value = (True,)
                return mock_result
            elif call_count[0] == 3:  # Count query for second view
                mock_result = MagicMock()
                mock_result.scalar.return_value = 50
                return mock_result
            elif call_count[0] == 4:  # Size query for second view
                mock_result = MagicMock()
                mock_result.scalar.return_value = 4096
                return mock_result
            # Reset for next view
            if call_count[0] == 4:
                call_count[0] = 0
            return MagicMock()

        mock_session.execute.side_effect = side_effect

        stats = await service.get_view_stats()

        # First view should report doesn't exist
        assert stats[0]["view_name"] == service.MANAGED_VIEWS[0]
        assert stats[0]["exists"] is False
        assert stats[0]["row_count"] == 0
        assert stats[0]["size_bytes"] == 0

    @pytest.mark.asyncio
    async def test_get_view_stats_error_handling(
        self, service: MaterializedViewService, mock_session: AsyncMock
    ) -> None:
        """Test get_view_stats error handling when queries fail."""
        # First view check raises exception
        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:  # First check_view_exists call raises error
                raise Exception("Database error")
            # Subsequent calls succeed
            mock_result = MagicMock()
            mock_result.fetchone.return_value = (True,)
            mock_result.scalar.return_value = 100
            return mock_result

        mock_session.execute.side_effect = side_effect

        stats = await service.get_view_stats()

        # First view should report error
        assert stats[0]["view_name"] == service.MANAGED_VIEWS[0]
        assert stats[0]["exists"] is False
        assert stats[0]["row_count"] == 0
        assert stats[0]["size_bytes"] == 0
        assert "error" in stats[0]
        assert stats[0]["error"] == "Database error"

    @pytest.mark.asyncio
    async def test_check_view_exists_none_result(
        self, service: MaterializedViewService, mock_session: AsyncMock
    ) -> None:
        """Test check_view_exists when result is None."""
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_session.execute.return_value = mock_result

        exists = await service.check_view_exists("some_view")

        assert exists is False

    @pytest.mark.asyncio
    async def test_refresh_view_concurrently_true(
        self, service: MaterializedViewService, mock_session: AsyncMock
    ) -> None:
        """Test refresh_view with concurrently=True."""
        mock_session.execute.return_value = MagicMock()

        result = await service.refresh_view("mv_daily_detection_counts", concurrently=True)

        assert result is True
        # Verify CONCURRENTLY clause was used
        call_args = mock_session.execute.call_args
        query_text = str(call_args[0][0])
        assert "CONCURRENTLY" in query_text

    @pytest.mark.asyncio
    async def test_refresh_view_concurrently_false(
        self, service: MaterializedViewService, mock_session: AsyncMock
    ) -> None:
        """Test refresh_view with concurrently=False."""
        mock_session.execute.return_value = MagicMock()

        result = await service.refresh_view("mv_daily_detection_counts", concurrently=False)

        assert result is True
        # Verify CONCURRENTLY clause was NOT used
        call_args = mock_session.execute.call_args
        query_text = str(call_args[0][0])
        assert "CONCURRENTLY" not in query_text
