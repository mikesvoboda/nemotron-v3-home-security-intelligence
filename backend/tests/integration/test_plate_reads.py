"""Integration tests for plate reads API endpoints.

Tests verify API routes work correctly with database and services.
"""

import pytest
from httpx import AsyncClient


@pytest.fixture
async def async_client(client):
    """Alias for shared client fixture."""
    yield client


@pytest.mark.integration
class TestPlateReadsAPIIntegration:
    """Integration tests for plate reads API."""

    @pytest.mark.asyncio
    async def test_list_plate_reads_returns_empty_list(self, async_client: AsyncClient):
        """Verify empty list returned when no plate reads exist."""
        response = await async_client.get("/api/plate-reads")
        assert response.status_code == 200
        data = response.json()
        # Shipped contract: PlateReadListResponse pagination envelope
        # (plate_reads/page/page_size/total), not a bare list under 'items'.
        assert "plate_reads" in data
        assert data["plate_reads"] == []

    @pytest.mark.asyncio
    async def test_get_plate_read_returns_404_when_not_found(self, async_client: AsyncClient):
        """Verify 404 returned when plate read doesn't exist."""
        response = await async_client.get("/api/plate-reads/999999")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_camera_plate_reads_returns_empty_list_for_nonexistent_camera(
        self, async_client: AsyncClient
    ):
        """Verify empty list returned when camera doesn't exist.

        get_reads_by_camera returns an empty PlateReadListResponse rather than
        404 — unknown cameras have no reads, which is not an error condition.
        """
        response = await async_client.get("/api/plate-reads/camera/nonexistent")
        assert response.status_code == 200
        data = response.json()
        assert "plate_reads" in data
        assert data["plate_reads"] == []

    @pytest.mark.asyncio
    async def test_search_plate_reads_returns_empty_list(self, async_client: AsyncClient):
        """Verify empty list returned when no plates match search."""
        response = await async_client.get("/api/plate-reads/search?text=ABC123")
        assert response.status_code == 200
        data = response.json()
        # Shipped contract: search returns the pagination envelope.
        assert "plate_reads" in data
        assert data["plate_reads"] == []

    @pytest.mark.asyncio
    async def test_get_statistics_returns_defaults(self, async_client: AsyncClient):
        """Verify statistics returns default values when no data."""
        response = await async_client.get("/api/plate-reads/statistics")
        assert response.status_code == 200
        data = response.json()
        assert "total_reads" in data
        assert data["total_reads"] == 0
