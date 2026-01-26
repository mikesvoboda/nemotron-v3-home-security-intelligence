"""Integration tests for action events API endpoints.

Tests verify API routes work correctly with database and services.
"""

import pytest
from httpx import AsyncClient


@pytest.fixture
async def async_client(client):
    """Alias for shared client fixture."""
    yield client


@pytest.mark.integration
class TestActionEventsAPIIntegration:
    """Integration tests for action events API."""

    @pytest.mark.asyncio
    async def test_list_action_events_returns_empty_list(self, async_client: AsyncClient):
        """Verify empty list returned when no action events exist."""
        response = await async_client.get("/api/action-events")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert data["items"] == []

    @pytest.mark.asyncio
    async def test_get_action_event_returns_404_when_not_found(self, async_client: AsyncClient):
        """Verify 404 returned when action event doesn't exist."""
        response = await async_client.get("/api/action-events/999999")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_camera_action_events_returns_404_for_nonexistent_camera(
        self, async_client: AsyncClient
    ):
        """Verify 404 returned when camera doesn't exist."""
        response = await async_client.get("/api/action-events/camera/nonexistent")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_list_suspicious_actions_returns_empty_list(self, async_client: AsyncClient):
        """Verify empty list returned when no suspicious actions exist."""
        response = await async_client.get("/api/action-events/suspicious")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert data["items"] == []

    @pytest.mark.asyncio
    async def test_delete_action_event_returns_404_when_not_found(self, async_client: AsyncClient):
        """Verify 404 returned when action event doesn't exist for delete."""
        response = await async_client.delete("/api/action-events/999999")
        assert response.status_code == 404
