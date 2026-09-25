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
        """Shipped contract (R-T9-ACTIONEVENTS404): the camera route is a pure
        filter — action_events.py:225 never checks camera existence (declared
        error responses are 422/500 only), so an unknown camera answers 200
        with an empty page, not 404."""
        response = await async_client.get("/api/action-events/camera/nonexistent")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["pagination"]["total"] == 0

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

    @pytest.mark.asyncio
    async def test_analyze_endpoint_removed(self, async_client: AsyncClient):
        """X-CLIP full-removal ruling (2026-09-23): POST /api/action-events/analyze
        is gone — the router keeps only CRUD on pipeline-written rows, so the verb
        on that path answers 405, not 200/503."""
        response = await async_client.post(
            "/api/action-events/analyze",
            json={"camera_id": "front_door", "frame_paths": ["export/frames/f1.jpg"]},
        )
        assert response.status_code == 405
