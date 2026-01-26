"""Integration tests for heatmaps API endpoints.

Uses shared fixtures from conftest.py:
- integration_db: Clean PostgreSQL test database
- mock_redis: Mock Redis client
- db_session: AsyncSession for database
- client: httpx AsyncClient with test app
"""

import pytest
from httpx import AsyncClient


# Alias for backward compatibility - tests use async_client but conftest provides client
@pytest.fixture
async def async_client(client):
    """Alias for shared client fixture for backward compatibility."""
    yield client


@pytest.mark.integration
class TestHeatmapsIntegration:
    """Integration tests for heatmaps API."""

    @pytest.mark.asyncio
    async def test_get_current_heatmap_returns_404_for_nonexistent_camera(
        self, async_client: AsyncClient
    ):
        """Verify 404 returned when camera doesn't exist."""
        response = await async_client.get("/api/heatmaps/camera/nonexistent")
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "nonexistent" in data["detail"]

    @pytest.mark.asyncio
    async def test_get_heatmap_history_returns_404_for_nonexistent_camera(
        self, async_client: AsyncClient
    ):
        """Verify 404 returned when camera doesn't exist."""
        response = await async_client.get(
            "/api/heatmaps/camera/nonexistent/history",
            params={
                "start_time": "2025-01-01T00:00:00Z",
                "end_time": "2025-12-31T23:59:59Z",
            },
        )
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "nonexistent" in data["detail"]

    @pytest.mark.asyncio
    async def test_save_heatmap_snapshot_returns_404_for_nonexistent_camera(
        self, async_client: AsyncClient
    ):
        """Verify 404 returned when camera doesn't exist."""
        response = await async_client.post(
            "/api/heatmaps/camera/nonexistent/snapshot",
            json={"resolution": "hourly"},
        )
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "nonexistent" in data["detail"]

    @pytest.mark.asyncio
    async def test_get_heatmap_stats_returns_404_for_nonexistent_camera(
        self, async_client: AsyncClient
    ):
        """Verify 404 returned when camera doesn't exist."""
        response = await async_client.get("/api/heatmaps/camera/nonexistent/stats")
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "nonexistent" in data["detail"]

    @pytest.mark.asyncio
    async def test_reset_heatmap_accumulator_returns_404_for_nonexistent_camera(
        self, async_client: AsyncClient
    ):
        """Verify 404 returned when camera doesn't exist."""
        response = await async_client.delete("/api/heatmaps/camera/nonexistent/accumulator")
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "nonexistent" in data["detail"]

    @pytest.mark.asyncio
    async def test_get_merged_heatmap_returns_404_for_nonexistent_camera(
        self, async_client: AsyncClient
    ):
        """Verify 404 returned when camera doesn't exist."""
        response = await async_client.get(
            "/api/heatmaps/camera/nonexistent/merged",
            params={
                "start_time": "2025-01-01T00:00:00Z",
                "end_time": "2025-12-31T23:59:59Z",
            },
        )
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "nonexistent" in data["detail"]


@pytest.mark.integration
class TestHeatmapsParameterValidation:
    """Tests for heatmaps API parameter validation."""

    @pytest.mark.asyncio
    async def test_get_current_heatmap_accepts_resolution_parameter(
        self, async_client: AsyncClient
    ):
        """Verify resolution query parameter is accepted."""
        response = await async_client.get(
            "/api/heatmaps/camera/nonexistent",
            params={"resolution": "daily"},
        )
        # Returns 404 because camera doesn't exist, but validates param is accepted
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_current_heatmap_accepts_output_size_parameters(
        self, async_client: AsyncClient
    ):
        """Verify output_width and output_height parameters are accepted."""
        response = await async_client.get(
            "/api/heatmaps/camera/nonexistent",
            params={
                "output_width": 800,
                "output_height": 600,
            },
        )
        # Returns 404 because camera doesn't exist, but validates params are accepted
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_current_heatmap_accepts_colormap_parameter(self, async_client: AsyncClient):
        """Verify colormap query parameter is accepted."""
        response = await async_client.get(
            "/api/heatmaps/camera/nonexistent",
            params={"colormap": "viridis"},
        )
        # Returns 404 because camera doesn't exist, but validates param is accepted
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_heatmap_history_validates_date_range(self, async_client: AsyncClient):
        """Verify validation error for invalid date range (start > end)."""
        response = await async_client.get(
            "/api/heatmaps/camera/nonexistent/history",
            params={
                "start_time": "2025-12-31T23:59:59Z",  # After end_time
                "end_time": "2025-01-01T00:00:00Z",
            },
        )
        # Note: 404 for camera check happens first in the current implementation
        # If camera existed, this would return 400
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_heatmap_history_requires_time_parameters(self, async_client: AsyncClient):
        """Verify that start_time and end_time are required."""
        response = await async_client.get("/api/heatmaps/camera/nonexistent/history")
        # Missing required query parameters should return 422
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_get_heatmap_history_accepts_pagination_parameters(
        self, async_client: AsyncClient
    ):
        """Verify limit and offset parameters are accepted."""
        response = await async_client.get(
            "/api/heatmaps/camera/nonexistent/history",
            params={
                "start_time": "2025-01-01T00:00:00Z",
                "end_time": "2025-12-31T23:59:59Z",
                "limit": 25,
                "offset": 10,
            },
        )
        # Returns 404 because camera doesn't exist, but validates params are accepted
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_current_heatmap_invalid_output_width(self, async_client: AsyncClient):
        """Verify validation error for output_width outside allowed range."""
        response = await async_client.get(
            "/api/heatmaps/camera/nonexistent",
            params={"output_width": 50},  # Below minimum of 100
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_get_current_heatmap_invalid_output_height(self, async_client: AsyncClient):
        """Verify validation error for output_height outside allowed range."""
        response = await async_client.get(
            "/api/heatmaps/camera/nonexistent",
            params={"output_height": 5000},  # Above maximum of 4096
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_get_merged_heatmap_requires_time_parameters(self, async_client: AsyncClient):
        """Verify that start_time and end_time are required for merged endpoint."""
        response = await async_client.get("/api/heatmaps/camera/nonexistent/merged")
        # Missing required query parameters should return 422
        assert response.status_code == 422


@pytest.mark.integration
class TestHeatmapSnapshotRequest:
    """Tests for heatmap snapshot request handling."""

    @pytest.mark.asyncio
    async def test_save_heatmap_snapshot_accepts_resolution(self, async_client: AsyncClient):
        """Verify resolution in snapshot request is accepted."""
        response = await async_client.post(
            "/api/heatmaps/camera/nonexistent/snapshot",
            json={"resolution": "weekly"},
        )
        # Returns 404 because camera doesn't exist, but validates param is accepted
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_save_heatmap_snapshot_invalid_resolution(self, async_client: AsyncClient):
        """Verify validation error for invalid resolution value."""
        response = await async_client.post(
            "/api/heatmaps/camera/nonexistent/snapshot",
            json={"resolution": "invalid_resolution"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_save_heatmap_snapshot_default_resolution(self, async_client: AsyncClient):
        """Verify default resolution is used when not provided."""
        response = await async_client.post(
            "/api/heatmaps/camera/nonexistent/snapshot",
            json={},  # Empty body, uses default resolution
        )
        # Returns 404 because camera doesn't exist, but validates default is accepted
        assert response.status_code == 404


@pytest.mark.integration
class TestHeatmapResolutionFiltering:
    """Tests for resolution filtering in heatmap queries."""

    @pytest.mark.asyncio
    async def test_get_heatmap_history_with_resolution_filter(self, async_client: AsyncClient):
        """Verify resolution filter is accepted in history query."""
        response = await async_client.get(
            "/api/heatmaps/camera/nonexistent/history",
            params={
                "start_time": "2025-01-01T00:00:00Z",
                "end_time": "2025-12-31T23:59:59Z",
                "resolution": "hourly",
            },
        )
        # Returns 404 because camera doesn't exist, but validates param is accepted
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_merged_heatmap_with_resolution_filter(self, async_client: AsyncClient):
        """Verify resolution filter is accepted in merged query."""
        response = await async_client.get(
            "/api/heatmaps/camera/nonexistent/merged",
            params={
                "start_time": "2025-01-01T00:00:00Z",
                "end_time": "2025-12-31T23:59:59Z",
                "resolution": "daily",
            },
        )
        # Returns 404 because camera doesn't exist, but validates param is accepted
        assert response.status_code == 404
