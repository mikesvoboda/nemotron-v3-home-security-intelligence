"""Integration tests for entities API endpoints.

Uses shared fixtures from conftest.py:
- integration_db: Clean SQLite test database
- mock_redis: Mock Redis client
- db_session: AsyncSession for database
- client: httpx AsyncClient with test app

These tests verify the entities API endpoints work correctly
with the full FastAPI application stack.
"""

import pytest

from backend.tests.integration.test_helpers import get_error_message


# Alias for backward compatibility - tests use async_client but conftest provides client
@pytest.fixture
async def async_client(client):
    """Alias for shared client fixture for backward compatibility."""
    yield client


class TestListEntities:
    """Tests for GET /api/entities endpoint."""

    async def test_list_entities_empty_without_redis(self, async_client):
        """Test listing entities when no data exists."""
        response = await async_client.get("/api/entities")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["pagination"]["total"] == 0
        assert "limit" in data["pagination"]
        assert "offset" in data["pagination"]

    async def test_list_entities_with_type_filter(self, async_client):
        """Test filtering entities by type."""
        response = await async_client.get("/api/entities?entity_type=person")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "pagination" in data

    async def test_list_entities_with_camera_filter(self, async_client):
        """Test filtering entities by camera."""
        response = await async_client.get("/api/entities?camera_id=front_door")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data

    async def test_list_entities_with_pagination(self, async_client):
        """Test pagination parameters."""
        response = await async_client.get("/api/entities?limit=10&offset=0")
        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["limit"] == 10
        assert data["pagination"]["offset"] == 0

    async def test_list_entities_invalid_limit(self, async_client):
        """Test validation of limit parameter."""
        response = await async_client.get("/api/entities?limit=0")
        assert response.status_code == 422  # Validation error

    async def test_list_entities_invalid_offset(self, async_client):
        """Test validation of offset parameter."""
        response = await async_client.get("/api/entities?offset=-1")
        assert response.status_code == 422  # Validation error

    async def test_list_entities_with_since_filter(self, async_client):
        """Test filtering entities by timestamp."""
        since = "2025-12-23T00:00:00Z"
        response = await async_client.get(f"/api/entities?since={since}")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data


class TestGetEntity:
    """Tests for GET /api/entities/{entity_id} endpoint."""

    async def test_get_entity_not_found(self, async_client):
        """Test getting a non-existent entity returns 404."""
        # Use a valid UUID that doesn't exist in the database
        nonexistent_uuid = "00000000-0000-4000-a000-000000000000"
        response = await async_client.get(f"/api/entities/{nonexistent_uuid}")
        # Entity not found - will return 404
        assert response.status_code == 404

    @pytest.mark.skip(
        reason="Entity API now uses PostgreSQL with UUID entity_id, not Redis detection_id lookup"
    )
    async def test_get_entity_with_real_redis(self, async_client, integration_db, real_redis):
        """Test getting entity with real Redis and stored data.

        Note: This test is skipped because the entity API was refactored in NEM-2500
        to use PostgreSQL with UUID-based entity_id instead of Redis with detection_id.
        """
        pass


class TestGetEntityHistory:
    """Tests for GET /api/entities/{entity_id}/history endpoint."""

    async def test_get_history_not_found(self, async_client):
        """Test getting history for non-existent entity returns 404."""
        # Use a valid UUID that doesn't exist in the database
        nonexistent_uuid = "00000000-0000-4000-a000-000000000001"
        response = await async_client.get(f"/api/entities/{nonexistent_uuid}/history")
        # Entity not found - will return 404
        assert response.status_code == 404

    @pytest.mark.skip(
        reason="Entity API now uses PostgreSQL with UUID entity_id, not Redis detection_id lookup"
    )
    async def test_get_history_with_real_redis(self, async_client, integration_db, real_redis):
        """Test getting entity history with real Redis and stored data.

        Note: This test is skipped because the entity history API was refactored in NEM-2500
        to use PostgreSQL with UUID-based entity_id instead of Redis with detection_id.
        """
        pass


class TestEntitiesAPIValidation:
    """Tests for API parameter validation."""

    async def test_limit_max_value(self, async_client):
        """Test that limit respects maximum value."""
        response = await async_client.get("/api/entities?limit=2000")
        assert response.status_code == 422  # Exceeds max of 1000

    async def test_entity_type_filter_values(self, async_client):
        """Test entity type filter accepts valid values."""
        for entity_type in ["person", "vehicle"]:
            response = await async_client.get(f"/api/entities?entity_type={entity_type}")
            assert response.status_code == 200

    async def test_entity_type_invalid_value(self, async_client):
        """Test that invalid entity type returns 422 error."""
        response = await async_client.get("/api/entities?entity_type=invalid")
        assert response.status_code == 422
        data = response.json()
        # Support both old ("detail") and new ("error") formats
        assert "detail" in data or "error" in data
        # Verify the error message mentions the valid options
        error_detail = get_error_message(data)
        assert "entity_type" in error_detail.lower() or "person" in error_detail.lower()

    async def test_combined_filters(self, async_client):
        """Test combining multiple filters."""
        response = await async_client.get(
            "/api/entities?entity_type=person&camera_id=front_door&limit=10&offset=0"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["limit"] == 10
        assert data["pagination"]["offset"] == 0
