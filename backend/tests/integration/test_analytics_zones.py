"""Integration tests for analytics zones API endpoints.

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
class TestLineZonesIntegration:
    """Integration tests for line zones API."""

    @pytest.mark.asyncio
    async def test_create_line_zone_requires_valid_camera(self, async_client: AsyncClient):
        """Verify 404 returned when camera doesn't exist."""
        response = await async_client.post(
            "/api/analytics-zones/line-zones",
            json={
                "camera_id": "nonexistent",
                "name": "Test Line",
                "start_x": 0,
                "start_y": 100,
                "end_x": 640,
                "end_y": 100,
            },
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_line_zone_returns_404_when_not_found(self, async_client: AsyncClient):
        """Verify 404 returned when line zone doesn't exist."""
        response = await async_client.get("/api/analytics-zones/line-zones/999999")
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "999999" in data["detail"]

    @pytest.mark.asyncio
    async def test_get_line_zones_by_camera_requires_valid_camera(self, async_client: AsyncClient):
        """Verify 404 returned when camera doesn't exist."""
        response = await async_client.get("/api/analytics-zones/line-zones/camera/nonexistent")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_line_zone_returns_404_when_not_found(self, async_client: AsyncClient):
        """Verify 404 returned when line zone doesn't exist for update."""
        response = await async_client.patch(
            "/api/analytics-zones/line-zones/999999",
            json={"name": "Updated Name"},
        )
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "999999" in data["detail"]

    @pytest.mark.asyncio
    async def test_delete_line_zone_returns_404_when_not_found(self, async_client: AsyncClient):
        """Verify 404 returned when line zone doesn't exist for delete."""
        response = await async_client.delete("/api/analytics-zones/line-zones/999999")
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "999999" in data["detail"]

    @pytest.mark.asyncio
    async def test_reset_line_zone_counts_returns_404_when_not_found(
        self, async_client: AsyncClient
    ):
        """Verify 404 returned when line zone doesn't exist for reset counts."""
        response = await async_client.post("/api/analytics-zones/line-zones/999999/reset-counts")
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "999999" in data["detail"]


@pytest.mark.integration
class TestPolygonZonesIntegration:
    """Integration tests for polygon zones API."""

    @pytest.mark.asyncio
    async def test_create_polygon_zone_requires_valid_camera(self, async_client: AsyncClient):
        """Verify 404 returned when camera doesn't exist."""
        response = await async_client.post(
            "/api/analytics-zones/polygon-zones",
            json={
                "camera_id": "nonexistent",
                "name": "Test Polygon",
                "polygon": [[100, 100], [400, 100], [400, 300], [100, 300]],
            },
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_polygon_zone_returns_404_when_not_found(self, async_client: AsyncClient):
        """Verify 404 returned when polygon zone doesn't exist."""
        response = await async_client.get("/api/analytics-zones/polygon-zones/999999")
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "999999" in data["detail"]

    @pytest.mark.asyncio
    async def test_get_polygon_zones_by_camera_requires_valid_camera(
        self, async_client: AsyncClient
    ):
        """Verify 404 returned when camera doesn't exist."""
        response = await async_client.get("/api/analytics-zones/polygon-zones/camera/nonexistent")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_polygon_zones_by_camera_with_active_only_filter(
        self, async_client: AsyncClient
    ):
        """Verify active_only query parameter is accepted.

        Note: Returns 404 because camera doesn't exist, but validates
        the query parameter is accepted.
        """
        response = await async_client.get(
            "/api/analytics-zones/polygon-zones/camera/nonexistent?active_only=false"
        )
        # Still 404 because camera doesn't exist, but validates parameter is accepted
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_polygon_zone_returns_404_when_not_found(self, async_client: AsyncClient):
        """Verify 404 returned when polygon zone doesn't exist for update."""
        response = await async_client.patch(
            "/api/analytics-zones/polygon-zones/999999",
            json={"name": "Updated Name"},
        )
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "999999" in data["detail"]

    @pytest.mark.asyncio
    async def test_delete_polygon_zone_returns_404_when_not_found(self, async_client: AsyncClient):
        """Verify 404 returned when polygon zone doesn't exist for delete."""
        response = await async_client.delete("/api/analytics-zones/polygon-zones/999999")
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "999999" in data["detail"]

    @pytest.mark.asyncio
    async def test_toggle_polygon_zone_active_returns_404_when_not_found(
        self, async_client: AsyncClient
    ):
        """Verify 404 returned when polygon zone doesn't exist for toggle active."""
        response = await async_client.post(
            "/api/analytics-zones/polygon-zones/999999/toggle-active"
        )
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "999999" in data["detail"]


@pytest.mark.integration
class TestDwellTimeEndpointsIntegration:
    """Integration tests for dwell time endpoints under polygon zones."""

    @pytest.mark.asyncio
    async def test_get_active_dwellers_returns_404_when_zone_not_found(
        self, async_client: AsyncClient
    ):
        """Verify 404 returned when polygon zone doesn't exist."""
        response = await async_client.get("/api/analytics-zones/polygon-zones/999999/dwellers")
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "999999" in data["detail"]

    @pytest.mark.asyncio
    async def test_get_dwell_history_returns_404_when_zone_not_found(
        self, async_client: AsyncClient
    ):
        """Verify 404 returned when polygon zone doesn't exist."""
        response = await async_client.get("/api/analytics-zones/polygon-zones/999999/dwell-history")
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "999999" in data["detail"]

    @pytest.mark.asyncio
    async def test_check_loitering_returns_404_when_zone_not_found(self, async_client: AsyncClient):
        """Verify 404 returned when polygon zone doesn't exist."""
        response = await async_client.post(
            "/api/analytics-zones/polygon-zones/999999/check-loitering",
            json={"threshold_seconds": 60},
        )
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "999999" in data["detail"]

    @pytest.mark.asyncio
    async def test_get_dwell_statistics_returns_404_when_zone_not_found(
        self, async_client: AsyncClient
    ):
        """Verify 404 returned when polygon zone doesn't exist."""
        response = await async_client.get(
            "/api/analytics-zones/polygon-zones/999999/dwell-statistics"
        )
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "999999" in data["detail"]


@pytest.mark.integration
class TestAnalyticsZonesValidation:
    """Tests for analytics zones API request validation."""

    @pytest.mark.asyncio
    async def test_create_line_zone_invalid_coordinates(self, async_client: AsyncClient):
        """Verify validation error for invalid coordinates."""
        response = await async_client.post(
            "/api/analytics-zones/line-zones",
            json={
                "camera_id": "test_camera",
                "name": "Test Line",
                "start_x": -1,  # Invalid: negative coordinate
                "start_y": 100,
                "end_x": 640,
                "end_y": 100,
            },
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_line_zone_empty_name(self, async_client: AsyncClient):
        """Verify validation error for empty name."""
        response = await async_client.post(
            "/api/analytics-zones/line-zones",
            json={
                "camera_id": "test_camera",
                "name": "",  # Invalid: empty name
                "start_x": 0,
                "start_y": 100,
                "end_x": 640,
                "end_y": 100,
            },
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_polygon_zone_invalid_polygon_points(self, async_client: AsyncClient):
        """Verify validation error for polygon with less than 3 points."""
        response = await async_client.post(
            "/api/analytics-zones/polygon-zones",
            json={
                "camera_id": "test_camera",
                "name": "Test Polygon",
                "polygon": [[100, 100], [400, 100]],  # Invalid: only 2 points
            },
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_polygon_zone_invalid_color_format(self, async_client: AsyncClient):
        """Verify validation error for invalid color format."""
        response = await async_client.post(
            "/api/analytics-zones/polygon-zones",
            json={
                "camera_id": "test_camera",
                "name": "Test Polygon",
                "polygon": [[100, 100], [400, 100], [400, 300], [100, 300]],
                "color": "red",  # Invalid: not hex format
            },
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_line_zone_empty_target_classes(self, async_client: AsyncClient):
        """Verify validation error for empty target_classes."""
        response = await async_client.post(
            "/api/analytics-zones/line-zones",
            json={
                "camera_id": "test_camera",
                "name": "Test Line",
                "start_x": 0,
                "start_y": 100,
                "end_x": 640,
                "end_y": 100,
                "target_classes": [],  # Invalid: empty list
            },
        )
        assert response.status_code == 422
