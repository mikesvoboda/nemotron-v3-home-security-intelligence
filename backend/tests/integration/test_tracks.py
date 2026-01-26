"""Integration tests for tracks API endpoints.

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
class TestTracksIntegration:
    """Integration tests for tracks API."""

    @pytest.mark.asyncio
    async def test_get_track_history_returns_404_when_not_found(self, async_client: AsyncClient):
        """Verify 404 returned when track doesn't exist."""
        response = await async_client.get("/api/tracks/camera1/999")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_tracks_by_camera_returns_empty_list(self, async_client: AsyncClient):
        """Verify empty list returned for camera with no tracks."""
        response = await async_client.get("/api/tracks/camera/nonexistent")
        assert response.status_code == 200
        data = response.json()
        assert data["tracks"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_get_track_trajectory_returns_404_when_not_found(self, async_client: AsyncClient):
        """Verify 404 returned when track doesn't exist for trajectory endpoint."""
        response = await async_client.get("/api/tracks/camera1/999/trajectory")
        assert response.status_code == 404


@pytest.mark.integration
class TestTracksParameterValidation:
    """Tests for tracks API parameter validation."""

    @pytest.mark.asyncio
    async def test_get_tracks_by_camera_with_pagination(self, async_client: AsyncClient):
        """Verify pagination parameters are accepted."""
        response = await async_client.get("/api/tracks/camera/test_camera?page=1&page_size=25")
        assert response.status_code == 200
        data = response.json()
        assert "tracks" in data
        assert "total" in data

    @pytest.mark.asyncio
    async def test_get_tracks_by_camera_with_object_class_filter(self, async_client: AsyncClient):
        """Verify object_class filter parameter is accepted."""
        response = await async_client.get("/api/tracks/camera/test_camera?object_class=person")
        assert response.status_code == 200
        data = response.json()
        assert "tracks" in data

    @pytest.mark.asyncio
    async def test_get_tracks_by_camera_with_time_filters(self, async_client: AsyncClient):
        """Verify time filter parameters are accepted."""
        response = await async_client.get(
            "/api/tracks/camera/test_camera"
            "?start_time=2025-01-01T00:00:00"
            "&end_time=2025-12-31T23:59:59"
        )
        assert response.status_code == 200
        data = response.json()
        assert "tracks" in data

    @pytest.mark.asyncio
    async def test_get_track_trajectory_with_limit(self, async_client: AsyncClient):
        """Verify trajectory endpoint accepts limit parameter."""
        # This will return 404 since the track doesn't exist,
        # but validates the endpoint accepts the limit parameter
        response = await async_client.get("/api/tracks/camera1/999/trajectory?limit=50")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_tracks_by_camera_invalid_page_size(self, async_client: AsyncClient):
        """Verify invalid page_size returns validation error."""
        # page_size > 100 should fail validation
        response = await async_client.get("/api/tracks/camera/test_camera?page_size=200")
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_get_tracks_by_camera_invalid_page(self, async_client: AsyncClient):
        """Verify invalid page number returns validation error."""
        # page < 1 should fail validation
        response = await async_client.get("/api/tracks/camera/test_camera?page=0")
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_get_track_trajectory_invalid_limit(self, async_client: AsyncClient):
        """Verify trajectory endpoint rejects invalid limit parameter."""
        # limit > 1000 should fail validation
        response = await async_client.get("/api/tracks/camera1/999/trajectory?limit=2000")
        assert response.status_code == 422


@pytest.mark.integration
class TestTracksResponseSchema:
    """Tests for tracks API response schema validation."""

    @pytest.mark.asyncio
    async def test_get_tracks_by_camera_response_schema(self, async_client: AsyncClient):
        """Verify response schema for get_tracks_by_camera."""
        response = await async_client.get("/api/tracks/camera/any_camera")
        assert response.status_code == 200
        data = response.json()

        # Verify required fields exist
        assert "tracks" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data

        # Verify field types
        assert isinstance(data["tracks"], list)
        assert isinstance(data["total"], int)
        assert isinstance(data["page"], int)
        assert isinstance(data["page_size"], int)

    @pytest.mark.asyncio
    async def test_track_history_404_response_contains_detail(self, async_client: AsyncClient):
        """Verify 404 response contains meaningful error detail."""
        response = await async_client.get("/api/tracks/test_camera/12345")
        assert response.status_code == 404
        data = response.json()

        # Should contain error detail
        assert "detail" in data
        assert "12345" in data["detail"]  # Track ID should be in error message
        assert "test_camera" in data["detail"]  # Camera ID should be in error message
