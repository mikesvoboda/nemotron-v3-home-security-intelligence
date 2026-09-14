"""Unit tests for Materialized Views Admin API routes (NEM-4933).

Tests the materialized views admin endpoints for listing, status checking,
and refreshing materialized views.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.api.routes.materialized_views import (
    _format_bytes,
    get_materialized_view_status,
    list_materialized_views,
    list_view_names,
    refresh_materialized_views,
)
from backend.api.schemas.materialized_views import MaterializedViewRefreshRequest


class TestFormatBytes:
    """Tests for _format_bytes helper function."""

    def test_zero_bytes(self) -> None:
        """Test formatting zero bytes."""
        assert _format_bytes(0) == "0 B"

    def test_bytes(self) -> None:
        """Test formatting bytes under 1KB."""
        assert _format_bytes(512) == "512 B"

    def test_kilobytes(self) -> None:
        """Test formatting kilobytes."""
        assert _format_bytes(1024) == "1.0 KB"
        assert _format_bytes(1536) == "1.5 KB"

    def test_megabytes(self) -> None:
        """Test formatting megabytes."""
        assert _format_bytes(1024 * 1024) == "1.0 MB"
        assert _format_bytes(2 * 1024 * 1024) == "2.0 MB"

    def test_gigabytes(self) -> None:
        """Test formatting gigabytes."""
        assert _format_bytes(1024 * 1024 * 1024) == "1.0 GB"


class TestListMaterializedViews:
    """Tests for GET /api/admin/materialized-views endpoint."""

    @pytest.mark.asyncio
    async def test_list_views_success(self) -> None:
        """Test listing materialized views successfully."""
        mock_db = MagicMock()

        # Mock the service
        with patch("backend.api.routes.materialized_views.MaterializedViewService") as MockService:
            mock_service = MagicMock()
            MockService.return_value = mock_service

            # Mock get_view_stats
            mock_service.get_view_stats = AsyncMock(
                return_value=[
                    {
                        "view_name": "mv_daily_detection_counts",
                        "exists": True,
                        "row_count": 1500,
                        "size_bytes": 102400,
                    },
                    {
                        "view_name": "mv_hourly_event_stats",
                        "exists": True,
                        "row_count": 5000,
                        "size_bytes": 256000,
                    },
                ]
            )

            result = await list_materialized_views(db=mock_db)

        assert result.total_views == 2
        assert len(result.views) == 2
        assert result.total_size_bytes == 102400 + 256000
        assert result.total_size_human is not None

        # Check first view
        assert result.views[0].view_name == "mv_daily_detection_counts"
        assert result.views[0].exists is True
        assert result.views[0].row_count == 1500
        assert result.views[0].size_bytes == 102400
        assert result.views[0].size_human == "100.0 KB"

    @pytest.mark.asyncio
    async def test_list_views_with_missing_view(self) -> None:
        """Test listing views when some views don't exist."""
        mock_db = MagicMock()

        with patch("backend.api.routes.materialized_views.MaterializedViewService") as MockService:
            mock_service = MagicMock()
            MockService.return_value = mock_service

            mock_service.get_view_stats = AsyncMock(
                return_value=[
                    {
                        "view_name": "mv_daily_detection_counts",
                        "exists": True,
                        "row_count": 1500,
                        "size_bytes": 102400,
                    },
                    {
                        "view_name": "mv_hourly_event_stats",
                        "exists": False,
                        "row_count": 0,
                        "size_bytes": 0,
                    },
                ]
            )

            result = await list_materialized_views(db=mock_db)

        assert result.total_views == 2
        assert result.views[0].exists is True
        assert result.views[1].exists is False
        assert result.views[1].row_count == 0

    @pytest.mark.asyncio
    async def test_list_views_error(self) -> None:
        """Test listing views handles errors gracefully."""
        mock_db = MagicMock()

        with patch("backend.api.routes.materialized_views.MaterializedViewService") as MockService:
            mock_service = MagicMock()
            MockService.return_value = mock_service

            mock_service.get_view_stats = AsyncMock(side_effect=Exception("Database error"))

            with pytest.raises(Exception) as exc_info:
                await list_materialized_views(db=mock_db)

        assert exc_info.value.status_code == 500
        assert "Database error" in str(exc_info.value.detail)


class TestGetMaterializedViewStatus:
    """Tests for GET /api/admin/materialized-views/{view_name} endpoint."""

    @pytest.mark.asyncio
    async def test_get_status_success(self) -> None:
        """Test getting view status successfully."""
        mock_db = MagicMock()

        with patch("backend.api.routes.materialized_views.MaterializedViewService") as MockService:
            mock_service = MagicMock()
            MockService.return_value = mock_service

            # Set MANAGED_VIEWS on the class
            MockService.MANAGED_VIEWS = ["mv_daily_detection_counts"]
            mock_service.MANAGED_VIEWS = ["mv_daily_detection_counts"]

            mock_service.check_view_exists = AsyncMock(return_value=True)
            mock_service.get_view_stats = AsyncMock(
                return_value=[
                    {
                        "view_name": "mv_daily_detection_counts",
                        "exists": True,
                        "row_count": 1500,
                        "size_bytes": 102400,
                    }
                ]
            )

            result = await get_materialized_view_status(
                view_name="mv_daily_detection_counts",
                db=mock_db,
            )

        assert result.view_name == "mv_daily_detection_counts"
        assert result.exists is True
        assert result.row_count == 1500
        assert result.size_bytes == 102400
        assert result.is_populated is True

    @pytest.mark.asyncio
    async def test_get_status_not_in_managed_list(self) -> None:
        """Test getting status for view not in managed list returns 404."""
        mock_db = MagicMock()

        with patch("backend.api.routes.materialized_views.MaterializedViewService") as MockService:
            mock_service = MagicMock()
            MockService.return_value = mock_service

            mock_service.MANAGED_VIEWS = ["mv_daily_detection_counts"]

            with pytest.raises(Exception) as exc_info:
                await get_materialized_view_status(
                    view_name="unknown_view",
                    db=mock_db,
                )

        assert exc_info.value.status_code == 404
        assert "not in the managed views list" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_get_status_view_not_exists(self) -> None:
        """Test getting status for view that doesn't exist in database."""
        mock_db = MagicMock()

        with patch("backend.api.routes.materialized_views.MaterializedViewService") as MockService:
            mock_service = MagicMock()
            MockService.return_value = mock_service

            mock_service.MANAGED_VIEWS = ["mv_daily_detection_counts"]
            mock_service.check_view_exists = AsyncMock(return_value=False)

            result = await get_materialized_view_status(
                view_name="mv_daily_detection_counts",
                db=mock_db,
            )

        assert result.view_name == "mv_daily_detection_counts"
        assert result.exists is False
        assert result.row_count == 0
        assert result.is_populated is False


class TestRefreshMaterializedViews:
    """Tests for POST /api/admin/materialized-views/refresh endpoint."""

    @pytest.mark.asyncio
    async def test_refresh_single_view_success(self) -> None:
        """Test refreshing a single view successfully."""
        mock_db = MagicMock()

        with patch("backend.api.routes.materialized_views.MaterializedViewService") as MockService:
            mock_service = MagicMock()
            MockService.return_value = mock_service

            mock_service.MANAGED_VIEWS = ["mv_daily_detection_counts"]
            mock_service.refresh_view = AsyncMock(return_value=True)

            request = MaterializedViewRefreshRequest(
                view_name="mv_daily_detection_counts",
                concurrently=True,
            )

            result = await refresh_materialized_views(
                request=request,
                db=mock_db,
            )

        assert result.total_refreshed == 1
        assert result.success_count == 1
        assert result.failure_count == 0
        assert result.concurrently is True
        assert len(result.results) == 1
        assert result.results[0].view_name == "mv_daily_detection_counts"
        assert result.results[0].success is True

    @pytest.mark.asyncio
    async def test_refresh_all_views_success(self) -> None:
        """Test refreshing all views successfully."""
        mock_db = MagicMock()

        with patch("backend.api.routes.materialized_views.MaterializedViewService") as MockService:
            mock_service = MagicMock()
            MockService.return_value = mock_service

            mock_service.MANAGED_VIEWS = [
                "mv_daily_detection_counts",
                "mv_hourly_event_stats",
            ]
            mock_service.refresh_all_views = AsyncMock(
                return_value={
                    "mv_daily_detection_counts": True,
                    "mv_hourly_event_stats": True,
                }
            )

            request = MaterializedViewRefreshRequest(
                view_name=None,  # All views
                concurrently=True,
            )

            result = await refresh_materialized_views(
                request=request,
                db=mock_db,
            )

        assert result.total_refreshed == 2
        assert result.success_count == 2
        assert result.failure_count == 0
        assert len(result.results) == 2

    @pytest.mark.asyncio
    async def test_refresh_view_not_in_managed_list(self) -> None:
        """Test refreshing unknown view returns 404."""
        mock_db = MagicMock()

        with patch("backend.api.routes.materialized_views.MaterializedViewService") as MockService:
            mock_service = MagicMock()
            MockService.return_value = mock_service

            mock_service.MANAGED_VIEWS = ["mv_daily_detection_counts"]

            request = MaterializedViewRefreshRequest(
                view_name="unknown_view",
                concurrently=True,
            )

            with pytest.raises(Exception) as exc_info:
                await refresh_materialized_views(
                    request=request,
                    db=mock_db,
                )

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_refresh_partial_failure(self) -> None:
        """Test refreshing with some failures."""
        mock_db = MagicMock()

        with patch("backend.api.routes.materialized_views.MaterializedViewService") as MockService:
            mock_service = MagicMock()
            MockService.return_value = mock_service

            mock_service.MANAGED_VIEWS = [
                "mv_daily_detection_counts",
                "mv_hourly_event_stats",
            ]
            mock_service.refresh_all_views = AsyncMock(
                return_value={
                    "mv_daily_detection_counts": True,
                    "mv_hourly_event_stats": False,  # Failed
                }
            )

            request = MaterializedViewRefreshRequest(concurrently=False)

            result = await refresh_materialized_views(
                request=request,
                db=mock_db,
            )

        assert result.total_refreshed == 2
        assert result.success_count == 1
        assert result.failure_count == 1
        assert result.concurrently is False


class TestListViewNames:
    """Tests for GET /api/admin/materialized-views/list/names endpoint."""

    @pytest.mark.asyncio
    async def test_list_view_names(self) -> None:
        """Test listing view names returns all managed views."""
        result = await list_view_names()

        assert isinstance(result, list)
        assert len(result) > 0
        assert "mv_daily_detection_counts" in result
        assert "mv_hourly_event_stats" in result


class TestMaterializedViewSchemas:
    """Tests for materialized view schemas."""

    def test_refresh_request_defaults(self) -> None:
        """Test MaterializedViewRefreshRequest has correct defaults."""
        request = MaterializedViewRefreshRequest()

        assert request.view_name is None  # All views
        assert request.concurrently is True

    def test_refresh_request_with_view_name(self) -> None:
        """Test MaterializedViewRefreshRequest with specific view."""
        request = MaterializedViewRefreshRequest(
            view_name="mv_daily_detection_counts",
            concurrently=False,
        )

        assert request.view_name == "mv_daily_detection_counts"
        assert request.concurrently is False
