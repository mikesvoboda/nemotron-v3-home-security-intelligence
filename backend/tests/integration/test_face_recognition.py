"""Integration tests for face recognition API endpoints.

Tests verify API routes work correctly with database and services.
"""

import pytest
from httpx import AsyncClient


@pytest.fixture
async def async_client(client):
    """Alias for shared client fixture."""
    yield client


@pytest.mark.integration
class TestKnownPersonsAPIIntegration:
    """Integration tests for known persons API."""

    @pytest.mark.asyncio
    async def test_list_known_persons_returns_empty_list(self, async_client: AsyncClient):
        """Verify empty list returned when no known persons exist."""
        response = await async_client.get("/api/known-persons")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert data == []

    @pytest.mark.asyncio
    async def test_get_known_person_returns_404_when_not_found(self, async_client: AsyncClient):
        """Verify 404 returned when known person doesn't exist."""
        response = await async_client.get("/api/known-persons/999999")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_known_person_returns_404_when_not_found(self, async_client: AsyncClient):
        """Verify 404 returned when known person doesn't exist for delete."""
        response = await async_client.delete("/api/known-persons/999999")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_embeddings_returns_404_when_person_not_found(
        self, async_client: AsyncClient
    ):
        """Verify 404 returned when known person doesn't exist."""
        response = await async_client.get("/api/known-persons/999999/embeddings")
        assert response.status_code == 404


@pytest.mark.integration
class TestFaceEventsAPIIntegration:
    """Integration tests for face events API."""

    @pytest.mark.asyncio
    async def test_list_face_events_returns_empty_list(self, async_client: AsyncClient):
        """Verify empty list returned when no face events exist."""
        response = await async_client.get("/api/face-events")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert data == []

    @pytest.mark.asyncio
    async def test_list_unknown_faces_returns_empty_list(self, async_client: AsyncClient):
        """Verify empty list returned when no unknown faces exist."""
        response = await async_client.get("/api/face-events/unknown")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert data == []
