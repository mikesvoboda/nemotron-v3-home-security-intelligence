"""Integration tests for tracks API endpoints.

Uses shared fixtures from conftest.py:
- integration_db: Clean PostgreSQL test database
- mock_redis: Mock Redis client
- db_session: AsyncSession for database
- client: httpx AsyncClient with test app

Rewritten to the SHIPPED route surface (api/routes/tracks.py). The previous
version targeted pre-normalization ghost paths that no longer exist
(/api/tracks/camera/{id}, /api/tracks/{camera}/{id}, .../trajectory); every
request 404ed at the router and the "validation" tests passed vacuously or
failed outright. Shipped contract (ledger R-T9-TRACKS):
- GET /api/tracks                       list, camera_id/object_class/page/page_size
- GET /api/tracks/{track_id}            track_id is an int PK; 404 detail is
                                        "Track with id {track_id} not found" (no camera ID)
- GET /api/tracks/{track_id}/history    no limit query param exists
- GET /api/cameras/{camera_id}/tracks   page ge=1, page_size ge=1 le=1000,
                                        object_class only — no time filters
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
    async def test_get_track_returns_404_when_not_found(self, async_client: AsyncClient):
        """Verify 404 returned when track doesn't exist."""
        response = await async_client.get("/api/tracks/999")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_tracks_by_camera_returns_empty_list(self, async_client: AsyncClient):
        """Verify empty list returned for camera with no tracks."""
        response = await async_client.get("/api/cameras/nonexistent/tracks")
        assert response.status_code == 200
        data = response.json()
        assert data["tracks"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_get_track_history_returns_404_when_not_found(self, async_client: AsyncClient):
        """Verify 404 returned when track doesn't exist for the history endpoint."""
        response = await async_client.get("/api/tracks/999/history")
        assert response.status_code == 404


@pytest.mark.integration
class TestTracksParameterValidation:
    """Tests for tracks API parameter validation."""

    @pytest.mark.asyncio
    async def test_get_tracks_by_camera_with_pagination(self, async_client: AsyncClient):
        """Verify pagination parameters are accepted."""
        response = await async_client.get("/api/cameras/test_camera/tracks?page=1&page_size=25")
        assert response.status_code == 200
        data = response.json()
        assert "tracks" in data
        assert "total" in data

    @pytest.mark.asyncio
    async def test_get_tracks_by_camera_with_object_class_filter(self, async_client: AsyncClient):
        """Verify object_class filter parameter is accepted."""
        response = await async_client.get("/api/cameras/test_camera/tracks?object_class=person")
        assert response.status_code == 200
        data = response.json()
        assert "tracks" in data

    @pytest.mark.asyncio
    async def test_get_tracks_by_camera_ignores_unknown_time_params(
        self, async_client: AsyncClient
    ):
        """Shipped list route takes no time filters; unknown params are ignored, not rejected."""
        response = await async_client.get(
            "/api/cameras/test_camera/tracks"
            "?start_time=2025-01-01T00:00:00"
            "&end_time=2025-12-31T23:59:59"
        )
        assert response.status_code == 200
        data = response.json()
        assert "tracks" in data

    @pytest.mark.asyncio
    async def test_get_track_history_ignores_limit_param(self, async_client: AsyncClient):
        """Shipped history route takes no limit param; extras are ignored and the 404 still stands."""
        response = await async_client.get("/api/tracks/999/history?limit=50")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_tracks_by_camera_invalid_page_size(self, async_client: AsyncClient):
        """Verify invalid page_size returns validation error."""
        # shipped bound is page_size le=1000, so 2000 fails validation
        response = await async_client.get("/api/cameras/test_camera/tracks?page_size=2000")
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_get_tracks_by_camera_invalid_page(self, async_client: AsyncClient):
        """Verify invalid page number returns validation error."""
        # page < 1 should fail validation
        response = await async_client.get("/api/cameras/test_camera/tracks?page=0")
        assert response.status_code == 422


@pytest.mark.integration
class TestTracksResponseSchema:
    """Tests for tracks API response schema validation."""

    @pytest.mark.asyncio
    async def test_get_tracks_by_camera_response_schema(self, async_client: AsyncClient):
        """Verify response schema for the camera tracks list endpoint."""
        response = await async_client.get("/api/cameras/any_camera/tracks")
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
    async def test_track_404_response_contains_detail(self, async_client: AsyncClient):
        """Verify 404 response contains meaningful error detail.

        Shipped detail for GET /api/tracks/{track_id} names only the track ID
        (routes/tracks.py: "Track with id {track_id} not found") — there is no
        camera ID in the message, unlike the ghost endpoint this test once
        targeted.
        """
        response = await async_client.get("/api/tracks/12345")
        assert response.status_code == 404
        data = response.json()

        # Should contain error detail
        assert "detail" in data
        assert "12345" in data["detail"]  # Track ID should be in error message
