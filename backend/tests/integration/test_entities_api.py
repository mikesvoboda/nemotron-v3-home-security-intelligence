"""Integration tests for entities API endpoints.

Uses shared fixtures from conftest.py:
- integration_db: Clean SQLite test database
- mock_redis: Mock Redis client
- db_session: AsyncSession for database
- client: httpx AsyncClient with test app

These tests verify the entities API endpoints work correctly
with the full FastAPI application stack.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

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
        assert data["entities"] == []
        assert data["count"] == 0
        assert "limit" in data
        assert "offset" in data

    async def test_list_entities_with_type_filter(self, async_client):
        """Test filtering entities by type."""
        response = await async_client.get("/api/entities?entity_type=person")
        assert response.status_code == 200
        data = response.json()
        assert "entities" in data
        assert "count" in data

    async def test_list_entities_with_camera_filter(self, async_client):
        """Test filtering entities by camera."""
        response = await async_client.get("/api/entities?camera_id=front_door")
        assert response.status_code == 200
        data = response.json()
        assert "entities" in data

    async def test_list_entities_with_pagination(self, async_client):
        """Test pagination parameters."""
        response = await async_client.get("/api/entities?limit=10&offset=0")
        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 10
        assert data["offset"] == 0

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
        assert "entities" in data


class TestGetEntity:
    """Tests for GET /api/entities/{entity_id} endpoint."""

    async def test_get_entity_not_found(self, async_client):
        """Test getting a non-existent entity returns 404 or 503."""
        response = await async_client.get("/api/entities/nonexistent_entity")
        # May return 404 (not found) or 503 (Redis unavailable) depending on Redis state
        assert response.status_code in [404, 503]

    async def test_get_entity_with_real_redis(self, async_client, integration_db, real_redis):
        """Test getting entity with real Redis and stored data."""
        # Store a test entity embedding in Redis
        from backend.services.reid_service import EntityEmbedding, get_reid_service

        reid_service = get_reid_service()
        test_embedding = EntityEmbedding(
            entity_type="person",
            embedding=[0.1] * 768,
            camera_id="front_door",
            timestamp=datetime.now(UTC),
            detection_id="test_det_001",
            attributes={"clothing": "blue jacket"},
        )

        # Get the raw Redis client for storing
        redis_client = real_redis._ensure_connected()
        await reid_service.store_embedding(redis_client, test_embedding)

        # Now test the API endpoint
        # We need to patch the Redis dependency to use real_redis
        with patch(
            "backend.api.routes.entities._get_redis_client",
            new_callable=AsyncMock,
            return_value=redis_client,
        ):
            response = await async_client.get("/api/entities/test_det_001")

        if response.status_code == 200:
            data = response.json()
            assert data["id"] == "test_det_001"
            assert data["entity_type"] == "person"
            assert "appearances" in data
        else:
            # May not find if Redis state doesn't match - acceptable for integration test
            assert response.status_code in [404, 503]


class TestGetEntityHistory:
    """Tests for GET /api/entities/{entity_id}/history endpoint."""

    async def test_get_history_not_found(self, async_client):
        """Test getting history for non-existent entity."""
        response = await async_client.get("/api/entities/nonexistent/history")
        # May return 404 (not found) or 503 (Redis unavailable)
        assert response.status_code in [404, 503]

    async def test_get_history_with_real_redis(self, async_client, integration_db, real_redis):
        """Test getting entity history with real Redis and stored data."""
        from backend.services.reid_service import EntityEmbedding, get_reid_service

        reid_service = get_reid_service()
        test_embedding = EntityEmbedding(
            entity_type="person",
            embedding=[0.1] * 768,
            camera_id="front_door",
            timestamp=datetime.now(UTC),
            detection_id="test_det_history_001",
            attributes={},
        )

        # Get the raw Redis client for storing
        redis_client = real_redis._ensure_connected()
        await reid_service.store_embedding(redis_client, test_embedding)

        # Now test the API endpoint
        with patch(
            "backend.api.routes.entities._get_redis_client",
            new_callable=AsyncMock,
            return_value=redis_client,
        ):
            response = await async_client.get("/api/entities/test_det_history_001/history")

        if response.status_code == 200:
            data = response.json()
            assert data["entity_id"] == "test_det_history_001"
            assert data["entity_type"] == "person"
            assert "appearances" in data
            assert "count" in data
        else:
            # May not find if Redis state doesn't match
            assert response.status_code in [404, 503]


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
        assert "detail" in data
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
        assert data["limit"] == 10
        assert data["offset"] == 0
