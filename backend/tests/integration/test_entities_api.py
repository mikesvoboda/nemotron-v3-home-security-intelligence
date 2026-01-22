"""Integration tests for entities API endpoints.

Uses shared fixtures from conftest.py:
- integration_db: Clean PostgreSQL test database
- mock_redis: Mock Redis client
- db_session: AsyncSession for database
- client: httpx AsyncClient with test app

These tests verify the entities API endpoints work correctly
with the full FastAPI application stack and PostgreSQL database.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from backend.models.entity import Entity
from backend.tests.integration.test_helpers import get_error_message


# Alias for backward compatibility - tests use async_client but conftest provides client
@pytest.fixture
async def async_client(client):
    """Alias for shared client fixture for backward compatibility."""
    yield client


@pytest.fixture
async def seeded_entities(db_session) -> list[Entity]:
    """Create sample entities in the database for testing."""
    entities = [
        Entity(
            id=uuid4(),
            entity_type="person",
            first_seen_at=datetime(2025, 12, 23, 10, 0, 0, tzinfo=UTC),
            last_seen_at=datetime(2025, 12, 23, 14, 30, 0, tzinfo=UTC),
            detection_count=5,
            entity_metadata={
                "camera_id": "front_door",
                "cameras_seen": ["front_door"],
                "clothing_color": "blue",
            },
        ),
        Entity(
            id=uuid4(),
            entity_type="vehicle",
            first_seen_at=datetime(2025, 12, 23, 9, 0, 0, tzinfo=UTC),
            last_seen_at=datetime(2025, 12, 23, 9, 30, 0, tzinfo=UTC),
            detection_count=2,
            entity_metadata={
                "camera_id": "driveway",
                "cameras_seen": ["driveway"],
                "color": "silver",
            },
        ),
        Entity(
            id=uuid4(),
            entity_type="person",
            first_seen_at=datetime(2025, 12, 22, 15, 0, 0, tzinfo=UTC),
            last_seen_at=datetime(2025, 12, 22, 15, 30, 0, tzinfo=UTC),
            detection_count=3,
            entity_metadata={
                "camera_id": "backyard",
                "cameras_seen": ["backyard"],
            },
        ),
    ]

    for entity in entities:
        db_session.add(entity)

    await db_session.commit()

    # Refresh to get database-generated defaults
    for entity in entities:
        await db_session.refresh(entity)

    return entities


class TestListEntities:
    """Tests for GET /api/entities endpoint.

    NOTE: Entity API uses PostgreSQL (NEM-2451).
    """

    async def test_list_entities_returns_valid_response(self, async_client):
        """Test listing entities returns valid response structure."""
        response = await async_client.get("/api/entities")
        assert response.status_code == 200
        data = response.json()
        # Check response structure
        assert "items" in data
        assert "pagination" in data
        assert isinstance(data["items"], list)
        assert "total" in data["pagination"]
        assert "limit" in data["pagination"]
        assert "offset" in data["pagination"]

    async def test_list_entities_with_seeded_data(self, async_client, seeded_entities):
        """Test listing entities with seeded data."""
        response = await async_client.get("/api/entities")
        assert response.status_code == 200
        data = response.json()

        # Should have at least the seeded entities
        assert data["pagination"]["total"] >= len(seeded_entities)
        assert len(data["items"]) >= len(seeded_entities)

        # Verify entity structure
        for item in data["items"]:
            assert "id" in item
            assert "entity_type" in item
            assert "first_seen" in item
            assert "last_seen" in item
            assert "appearance_count" in item
            assert "cameras_seen" in item

    async def test_list_entities_cameras_seen_populated(self, async_client, seeded_entities):
        """Test that cameras_seen field is properly populated (NEM-3262)."""
        response = await async_client.get("/api/entities")
        assert response.status_code == 200
        data = response.json()

        # All entities should have at least one camera in cameras_seen
        for item in data["items"]:
            assert "cameras_seen" in item, f"Entity {item['id']} missing cameras_seen field"
            cameras = item["cameras_seen"]
            assert isinstance(cameras, list), f"cameras_seen should be a list, got {type(cameras)}"
            # Since each seeded entity has detection_count > 0, they should have been detected
            # by at least one camera, so cameras_seen should not be empty
            if item["appearance_count"] > 0:
                assert len(cameras) > 0, (
                    f"Entity {item['id']} has {item['appearance_count']} appearances "
                    f"but cameras_seen is empty"
                )

    async def test_list_entities_with_type_filter(self, async_client, seeded_entities):
        """Test filtering entities by type."""
        response = await async_client.get("/api/entities?entity_type=person")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "pagination" in data

        # All returned entities should be persons
        for item in data["items"]:
            assert item["entity_type"] == "person"

    async def test_list_entities_with_camera_filter(self, async_client, seeded_entities):
        """Test filtering entities by camera."""
        response = await async_client.get("/api/entities?camera_id=front_door")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data

        # Returned entities should be from front_door camera
        for item in data["items"]:
            if item["cameras_seen"]:
                assert "front_door" in item["cameras_seen"]

    async def test_list_entities_with_pagination(self, async_client, seeded_entities):
        """Test pagination parameters."""
        response = await async_client.get("/api/entities?limit=2&offset=0")
        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["limit"] == 2
        assert data["pagination"]["offset"] == 0
        assert len(data["items"]) <= 2

    async def test_list_entities_invalid_limit(self, async_client):
        """Test validation of limit parameter."""
        response = await async_client.get("/api/entities?limit=0")
        assert response.status_code == 422  # Validation error

    async def test_list_entities_invalid_offset(self, async_client):
        """Test validation of offset parameter."""
        response = await async_client.get("/api/entities?offset=-1")
        assert response.status_code == 422  # Validation error

    async def test_list_entities_with_since_filter(self, async_client, seeded_entities):
        """Test filtering entities by timestamp."""
        since = "2025-12-23T00:00:00Z"
        response = await async_client.get(f"/api/entities?since={since}")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data

        # All entities should be seen after the since timestamp
        since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
        for item in data["items"]:
            last_seen = datetime.fromisoformat(item["last_seen"])
            assert last_seen >= since_dt


class TestGetEntity:
    """Tests for GET /api/entities/{entity_id} endpoint.

    NOTE: Entity API now uses PostgreSQL with UUID entity_id (NEM-2451).
    """

    async def test_get_entity_not_found(self, async_client):
        """Test getting a non-existent entity returns 404."""
        # Use a valid UUID format that doesn't exist in the database
        nonexistent_uuid = str(uuid4())
        response = await async_client.get(f"/api/entities/{nonexistent_uuid}")
        # Should return 404 (not found) for valid UUID that doesn't exist
        assert response.status_code == 404

    async def test_get_entity_invalid_uuid(self, async_client):
        """Test getting an entity with invalid UUID format returns 422."""
        # Non-UUID strings should return 422 (validation error)
        response = await async_client.get("/api/entities/nonexistent_entity")
        assert response.status_code == 422

    async def test_get_entity_with_seeded_data(self, async_client, seeded_entities):
        """Test getting entity from PostgreSQL database."""
        # Use the first seeded entity
        entity = seeded_entities[0]

        response = await async_client.get(f"/api/entities/{entity.id}")

        # Entity should exist
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(entity.id)
        assert data["entity_type"] == entity.entity_type
        assert data["appearance_count"] == entity.detection_count
        assert "appearances" in data

    async def test_get_entity_with_primary_detection_id(self, async_client, db_session):
        """Test getting entity with primary_detection_id set."""
        # Create entity with primary_detection_id (referential integrity not enforced)
        entity = Entity(
            id=uuid4(),
            entity_type="person",
            first_seen_at=datetime.now(UTC),
            last_seen_at=datetime.now(UTC),
            detection_count=1,
            primary_detection_id=999,  # May not exist, just testing field presence
            entity_metadata={"camera_id": "front_door"},
        )
        db_session.add(entity)
        await db_session.commit()
        await db_session.refresh(entity)

        response = await async_client.get(f"/api/entities/{entity.id}")

        # Should succeed even if detection doesn't exist
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(entity.id)
        assert data["entity_type"] == "person"


class TestGetEntityHistory:
    """Tests for GET /api/entities/{entity_id}/history endpoint.

    NOTE: Entity API now uses PostgreSQL with UUID entity_id (NEM-2451).
    """

    async def test_get_history_not_found(self, async_client):
        """Test getting history for non-existent entity."""
        # Use a valid UUID format that doesn't exist in the database
        nonexistent_uuid = str(uuid4())
        response = await async_client.get(f"/api/entities/{nonexistent_uuid}/history")
        # Should return 404 for valid UUID that doesn't exist
        assert response.status_code == 404

    async def test_get_history_invalid_uuid(self, async_client):
        """Test getting history with invalid UUID format returns 422."""
        # Non-UUID strings should return 422 (validation error)
        response = await async_client.get("/api/entities/nonexistent/history")
        assert response.status_code == 422

    async def test_get_history_with_seeded_data(self, async_client, seeded_entities):
        """Test getting entity history from PostgreSQL database."""
        entity = seeded_entities[0]

        response = await async_client.get(f"/api/entities/{entity.id}/history")

        # Should return history
        assert response.status_code == 200
        data = response.json()
        assert data["entity_id"] == str(entity.id)
        assert data["entity_type"] == entity.entity_type
        assert "appearances" in data
        assert "count" in data


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


class TestEntitiesEndToEnd:
    """End-to-end tests for entity tracking flow."""

    async def test_create_and_retrieve_entity(self, async_client, db_session):
        """Test creating entity and retrieving it via API."""
        # Create entity directly in database
        entity_id = uuid4()
        entity = Entity(
            id=entity_id,
            entity_type="person",
            first_seen_at=datetime.now(UTC),
            last_seen_at=datetime.now(UTC),
            detection_count=1,
            entity_metadata={"camera_id": "test_camera"},
        )
        db_session.add(entity)
        await db_session.commit()

        # Retrieve via API
        response = await async_client.get(f"/api/entities/{entity_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(entity_id)
        assert data["entity_type"] == "person"

    async def test_list_includes_newly_created_entity(self, async_client, db_session):
        """Test that list endpoint includes newly created entities."""
        # Get initial count
        response = await async_client.get("/api/entities")
        initial_total = response.json()["pagination"]["total"]

        # Create new entity
        entity = Entity(
            id=uuid4(),
            entity_type="vehicle",
            first_seen_at=datetime.now(UTC),
            last_seen_at=datetime.now(UTC),
            detection_count=1,
            entity_metadata={"camera_id": "test_camera"},
        )
        db_session.add(entity)
        await db_session.commit()

        # List should include new entity
        response = await async_client.get("/api/entities")
        assert response.status_code == 200
        new_total = response.json()["pagination"]["total"]
        assert new_total == initial_total + 1
