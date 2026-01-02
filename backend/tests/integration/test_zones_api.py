"""Integration tests for camera zones API endpoints."""

import uuid

import pytest

# === Helper Functions ===


def unique_id(prefix: str = "test") -> str:
    """Generate a unique ID for test objects to prevent conflicts in parallel execution."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def valid_rectangle_coordinates() -> list[list[float]]:
    """Return valid rectangle coordinates for zone creation."""
    return [[0.1, 0.2], [0.3, 0.2], [0.3, 0.8], [0.1, 0.8]]


def valid_polygon_coordinates() -> list[list[float]]:
    """Return valid polygon coordinates for zone creation (pentagon)."""
    return [[0.2, 0.1], [0.4, 0.2], [0.45, 0.5], [0.3, 0.7], [0.1, 0.4]]


async def create_test_camera(client, suffix: str = "") -> str:
    """Create a test camera and return its ID."""
    unique_suffix = suffix or unique_id()
    camera_data = {
        "name": f"Test Camera {unique_suffix}",
        "folder_path": f"/export/foscam/test_{unique_suffix}",
        "status": "online",
    }
    response = await client.post("/api/cameras", json=camera_data)
    assert response.status_code == 201, f"Failed to create camera: {response.json()}"
    return response.json()["id"]


async def create_test_zone(
    client,
    camera_id: str,
    name: str | None = None,
    zone_type: str = "other",
    coordinates: list[list[float]] | None = None,
) -> dict:
    """Create a test zone and return the response data."""
    zone_data = {
        "name": name or f"Test Zone {unique_id()}",
        "zone_type": zone_type,
        "coordinates": coordinates or valid_rectangle_coordinates(),
        "shape": "rectangle",
        "color": "#FF5733",
        "enabled": True,
        "priority": 5,
    }
    response = await client.post(f"/api/cameras/{camera_id}/zones", json=zone_data)
    assert response.status_code == 201, f"Failed to create zone: {response.json()}"
    return response.json()


# === CREATE Tests ===


@pytest.mark.asyncio
async def test_create_zone_success(client):
    """Test successful zone creation."""
    camera_id = await create_test_camera(client)

    zone_data = {
        "name": "Front Door Zone",
        "zone_type": "entry_point",
        "coordinates": valid_rectangle_coordinates(),
        "shape": "rectangle",
        "color": "#3B82F6",
        "enabled": True,
        "priority": 10,
    }

    response = await client.post(f"/api/cameras/{camera_id}/zones", json=zone_data)

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == zone_data["name"]
    assert data["zone_type"] == zone_data["zone_type"]
    assert data["coordinates"] == zone_data["coordinates"]
    assert data["shape"] == zone_data["shape"]
    assert data["color"] == zone_data["color"]
    assert data["enabled"] == zone_data["enabled"]
    assert data["priority"] == zone_data["priority"]
    assert data["camera_id"] == camera_id
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data
    # UUID validation
    uuid.UUID(data["id"])


@pytest.mark.asyncio
async def test_create_zone_with_default_values(client):
    """Test zone creation with default values."""
    camera_id = await create_test_camera(client)

    zone_data = {
        "name": "Default Zone",
        "coordinates": valid_rectangle_coordinates(),
    }

    response = await client.post(f"/api/cameras/{camera_id}/zones", json=zone_data)

    assert response.status_code == 201
    data = response.json()
    assert data["zone_type"] == "other"  # Default
    assert data["shape"] == "rectangle"  # Default
    assert data["color"] == "#3B82F6"  # Default
    assert data["enabled"] is True  # Default
    assert data["priority"] == 0  # Default


@pytest.mark.asyncio
async def test_create_zone_with_polygon_shape(client):
    """Test zone creation with polygon shape."""
    camera_id = await create_test_camera(client)

    zone_data = {
        "name": "Polygon Zone",
        "zone_type": "yard",
        "coordinates": valid_polygon_coordinates(),
        "shape": "polygon",
    }

    response = await client.post(f"/api/cameras/{camera_id}/zones", json=zone_data)

    assert response.status_code == 201
    data = response.json()
    assert data["shape"] == "polygon"
    assert len(data["coordinates"]) == 5


@pytest.mark.asyncio
async def test_create_zone_nonexistent_camera(client):
    """Test zone creation for non-existent camera returns 404."""
    fake_camera_id = str(uuid.uuid4())

    zone_data = {
        "name": "Test Zone",
        "coordinates": valid_rectangle_coordinates(),
    }

    response = await client.post(f"/api/cameras/{fake_camera_id}/zones", json=zone_data)

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_create_zone_missing_name(client):
    """Test zone creation fails without name."""
    camera_id = await create_test_camera(client)

    zone_data = {
        "coordinates": valid_rectangle_coordinates(),
    }

    response = await client.post(f"/api/cameras/{camera_id}/zones", json=zone_data)

    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_create_zone_missing_coordinates(client):
    """Test zone creation fails without coordinates."""
    camera_id = await create_test_camera(client)

    zone_data = {
        "name": "Test Zone",
    }

    response = await client.post(f"/api/cameras/{camera_id}/zones", json=zone_data)

    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_create_zone_empty_name(client):
    """Test zone creation fails with empty name."""
    camera_id = await create_test_camera(client)

    zone_data = {
        "name": "",
        "coordinates": valid_rectangle_coordinates(),
    }

    response = await client.post(f"/api/cameras/{camera_id}/zones", json=zone_data)

    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_create_zone_name_too_long(client):
    """Test zone creation fails with name exceeding max length."""
    camera_id = await create_test_camera(client)

    zone_data = {
        "name": "A" * 256,  # Exceeds 255 character limit
        "coordinates": valid_rectangle_coordinates(),
    }

    response = await client.post(f"/api/cameras/{camera_id}/zones", json=zone_data)

    assert response.status_code == 422  # Validation error


# === Invalid Polygon Validation Tests ===


@pytest.mark.asyncio
async def test_create_zone_too_few_points(client):
    """Test zone creation fails with less than 3 points."""
    camera_id = await create_test_camera(client)

    zone_data = {
        "name": "Invalid Zone",
        "coordinates": [[0.1, 0.2], [0.3, 0.4]],  # Only 2 points
    }

    response = await client.post(f"/api/cameras/{camera_id}/zones", json=zone_data)

    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_create_zone_coordinates_out_of_range(client):
    """Test zone creation fails with coordinates outside 0-1 range."""
    camera_id = await create_test_camera(client)

    # Coordinates outside 0-1 range
    zone_data = {
        "name": "Invalid Zone",
        "coordinates": [[0.1, 0.2], [1.5, 0.2], [0.3, 0.8], [0.1, 0.8]],  # 1.5 > 1
    }

    response = await client.post(f"/api/cameras/{camera_id}/zones", json=zone_data)

    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_create_zone_negative_coordinates(client):
    """Test zone creation fails with negative coordinates."""
    camera_id = await create_test_camera(client)

    zone_data = {
        "name": "Invalid Zone",
        "coordinates": [[-0.1, 0.2], [0.3, 0.2], [0.3, 0.8], [0.1, 0.8]],  # -0.1 < 0
    }

    response = await client.post(f"/api/cameras/{camera_id}/zones", json=zone_data)

    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_create_zone_invalid_point_format(client):
    """Test zone creation fails with points having wrong number of values."""
    camera_id = await create_test_camera(client)

    zone_data = {
        "name": "Invalid Zone",
        "coordinates": [[0.1, 0.2, 0.3], [0.3, 0.2], [0.3, 0.8], [0.1, 0.8]],  # 3 values
    }

    response = await client.post(f"/api/cameras/{camera_id}/zones", json=zone_data)

    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_create_zone_duplicate_consecutive_points(client):
    """Test zone creation fails with duplicate consecutive points."""
    camera_id = await create_test_camera(client)

    zone_data = {
        "name": "Invalid Zone",
        "coordinates": [
            [0.1, 0.2],
            [0.1, 0.2],  # Duplicate of first point
            [0.3, 0.8],
            [0.1, 0.8],
        ],
    }

    response = await client.post(f"/api/cameras/{camera_id}/zones", json=zone_data)

    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_create_zone_degenerate_polygon(client):
    """Test zone creation fails with collinear points (zero area)."""
    camera_id = await create_test_camera(client)

    # All points on a line (degenerate polygon with zero area)
    zone_data = {
        "name": "Invalid Zone",
        "coordinates": [[0.1, 0.1], [0.2, 0.1], [0.3, 0.1]],
    }

    response = await client.post(f"/api/cameras/{camera_id}/zones", json=zone_data)

    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_create_zone_self_intersecting_polygon(client):
    """Test zone creation fails with self-intersecting polygon."""
    camera_id = await create_test_camera(client)

    # Figure-8 / bowtie shape (self-intersecting)
    zone_data = {
        "name": "Invalid Zone",
        "coordinates": [[0.1, 0.1], [0.4, 0.4], [0.1, 0.4], [0.4, 0.1]],
    }

    response = await client.post(f"/api/cameras/{camera_id}/zones", json=zone_data)

    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_create_zone_invalid_color_format(client):
    """Test zone creation fails with invalid hex color."""
    camera_id = await create_test_camera(client)

    zone_data = {
        "name": "Invalid Zone",
        "coordinates": valid_rectangle_coordinates(),
        "color": "invalid",  # Not a valid hex color
    }

    response = await client.post(f"/api/cameras/{camera_id}/zones", json=zone_data)

    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_create_zone_priority_out_of_range(client):
    """Test zone creation fails with priority outside valid range."""
    camera_id = await create_test_camera(client)

    zone_data = {
        "name": "Invalid Zone",
        "coordinates": valid_rectangle_coordinates(),
        "priority": 101,  # Max is 100
    }

    response = await client.post(f"/api/cameras/{camera_id}/zones", json=zone_data)

    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_create_zone_negative_priority(client):
    """Test zone creation fails with negative priority."""
    camera_id = await create_test_camera(client)

    zone_data = {
        "name": "Invalid Zone",
        "coordinates": valid_rectangle_coordinates(),
        "priority": -1,  # Min is 0
    }

    response = await client.post(f"/api/cameras/{camera_id}/zones", json=zone_data)

    assert response.status_code == 422  # Validation error


# === READ Tests (List) ===


@pytest.mark.asyncio
async def test_list_zones_empty(client):
    """Test listing zones when camera has none."""
    camera_id = await create_test_camera(client)

    response = await client.get(f"/api/cameras/{camera_id}/zones")

    assert response.status_code == 200
    data = response.json()
    assert data["zones"] == []
    assert data["count"] == 0


@pytest.mark.asyncio
async def test_list_zones_with_data(client):
    """Test listing zones with existing data."""
    camera_id = await create_test_camera(client)

    # Create multiple zones
    zone_names = ["Zone 1", "Zone 2", "Zone 3"]
    for name in zone_names:
        await create_test_zone(client, camera_id, name=name)

    response = await client.get(f"/api/cameras/{camera_id}/zones")

    assert response.status_code == 200
    data = response.json()
    assert len(data["zones"]) == 3
    assert data["count"] == 3


@pytest.mark.asyncio
async def test_list_zones_filter_by_enabled(client):
    """Test listing zones filtered by enabled status."""
    camera_id = await create_test_camera(client)

    # Create enabled zone
    zone_data_enabled = {
        "name": "Enabled Zone",
        "coordinates": valid_rectangle_coordinates(),
        "enabled": True,
    }
    await client.post(f"/api/cameras/{camera_id}/zones", json=zone_data_enabled)

    # Create disabled zone
    zone_data_disabled = {
        "name": "Disabled Zone",
        "coordinates": [[0.5, 0.5], [0.7, 0.5], [0.7, 0.9], [0.5, 0.9]],
        "enabled": False,
    }
    await client.post(f"/api/cameras/{camera_id}/zones", json=zone_data_disabled)

    # Filter by enabled=true
    response = await client.get(f"/api/cameras/{camera_id}/zones?enabled=true")

    assert response.status_code == 200
    data = response.json()
    assert len(data["zones"]) == 1
    assert data["zones"][0]["name"] == "Enabled Zone"
    assert data["count"] == 1

    # Filter by enabled=false
    response = await client.get(f"/api/cameras/{camera_id}/zones?enabled=false")

    assert response.status_code == 200
    data = response.json()
    assert len(data["zones"]) == 1
    assert data["zones"][0]["name"] == "Disabled Zone"
    assert data["count"] == 1


@pytest.mark.asyncio
async def test_list_zones_ordered_by_priority(client):
    """Test that zones are ordered by priority descending."""
    camera_id = await create_test_camera(client)

    # Create zones with different priorities
    priorities = [10, 50, 30]
    for idx, priority in enumerate(priorities):
        zone_data = {
            "name": f"Priority {priority} Zone",
            "coordinates": [
                [0.1 + idx * 0.01, 0.1],
                [0.2 + idx * 0.01, 0.1],
                [0.2 + idx * 0.01, 0.2],
                [0.1 + idx * 0.01, 0.2],
            ],
            "priority": priority,
        }
        await client.post(f"/api/cameras/{camera_id}/zones", json=zone_data)

    response = await client.get(f"/api/cameras/{camera_id}/zones")

    assert response.status_code == 200
    data = response.json()
    # Should be ordered by priority descending: 50, 30, 10
    assert data["zones"][0]["priority"] == 50
    assert data["zones"][1]["priority"] == 30
    assert data["zones"][2]["priority"] == 10


@pytest.mark.asyncio
async def test_list_zones_nonexistent_camera(client):
    """Test listing zones for non-existent camera returns 404."""
    fake_camera_id = str(uuid.uuid4())

    response = await client.get(f"/api/cameras/{fake_camera_id}/zones")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_zones_camera_isolation(client):
    """Test that zones are isolated per camera."""
    uid = unique_id()
    camera_id_1 = await create_test_camera(client, f"isolation_cam1_{uid}")
    camera_id_2 = await create_test_camera(client, f"isolation_cam2_{uid}")

    # Create zones for camera 1
    await create_test_zone(client, camera_id_1, name=f"Camera 1 Zone A {uid}")
    await create_test_zone(client, camera_id_2, name=f"Camera 2 Zone A {uid}")
    await create_test_zone(client, camera_id_2, name=f"Camera 2 Zone B {uid}")

    # Camera 1 should have 1 zone
    response1 = await client.get(f"/api/cameras/{camera_id_1}/zones")
    assert response1.status_code == 200
    data1 = response1.json()
    assert data1["count"] == 1
    assert f"Camera 1 Zone A {uid}" in data1["zones"][0]["name"]

    # Camera 2 should have 2 zones
    response2 = await client.get(f"/api/cameras/{camera_id_2}/zones")
    assert response2.status_code == 200
    data2 = response2.json()
    assert data2["count"] == 2


# === READ Tests (Single) ===


@pytest.mark.asyncio
async def test_get_zone_by_id_success(client):
    """Test getting a specific zone by ID."""
    camera_id = await create_test_camera(client)
    created_zone = await create_test_zone(client, camera_id, name="Get Test Zone")

    response = await client.get(f"/api/cameras/{camera_id}/zones/{created_zone['id']}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == created_zone["id"]
    assert data["name"] == "Get Test Zone"
    assert data["camera_id"] == camera_id


@pytest.mark.asyncio
async def test_get_zone_nonexistent_zone(client):
    """Test getting a non-existent zone returns 404."""
    camera_id = await create_test_camera(client)
    fake_zone_id = str(uuid.uuid4())

    response = await client.get(f"/api/cameras/{camera_id}/zones/{fake_zone_id}")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_zone_nonexistent_camera(client):
    """Test getting a zone with non-existent camera returns 404."""
    fake_camera_id = str(uuid.uuid4())
    fake_zone_id = str(uuid.uuid4())

    response = await client.get(f"/api/cameras/{fake_camera_id}/zones/{fake_zone_id}")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_zone_wrong_camera(client):
    """Test getting a zone from wrong camera returns 404."""
    uid = unique_id()
    camera_id_1 = await create_test_camera(client, f"cam1_{uid}")
    camera_id_2 = await create_test_camera(client, f"cam2_{uid}")

    # Create zone for camera 1
    created_zone = await create_test_zone(client, camera_id_1, name=f"Camera 1 Zone {uid}")

    # Try to get it via camera 2
    response = await client.get(f"/api/cameras/{camera_id_2}/zones/{created_zone['id']}")

    assert response.status_code == 404


# === UPDATE Tests ===


@pytest.mark.asyncio
async def test_update_zone_name(client):
    """Test updating zone name."""
    camera_id = await create_test_camera(client)
    created_zone = await create_test_zone(client, camera_id, name="Old Name")

    response = await client.put(
        f"/api/cameras/{camera_id}/zones/{created_zone['id']}",
        json={"name": "New Name"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "New Name"
    # Other fields unchanged
    assert data["zone_type"] == created_zone["zone_type"]
    assert data["coordinates"] == created_zone["coordinates"]


@pytest.mark.asyncio
async def test_update_zone_type(client):
    """Test updating zone type."""
    camera_id = await create_test_camera(client)
    created_zone = await create_test_zone(client, camera_id, zone_type="other")

    response = await client.put(
        f"/api/cameras/{camera_id}/zones/{created_zone['id']}",
        json={"zone_type": "driveway"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["zone_type"] == "driveway"


@pytest.mark.asyncio
async def test_update_zone_coordinates(client):
    """Test updating zone coordinates."""
    camera_id = await create_test_camera(client)
    created_zone = await create_test_zone(client, camera_id)

    new_coordinates = [[0.2, 0.3], [0.5, 0.3], [0.5, 0.7], [0.2, 0.7]]

    response = await client.put(
        f"/api/cameras/{camera_id}/zones/{created_zone['id']}",
        json={"coordinates": new_coordinates},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["coordinates"] == new_coordinates


@pytest.mark.asyncio
async def test_update_zone_enabled_status(client):
    """Test updating zone enabled status."""
    camera_id = await create_test_camera(client)
    created_zone = await create_test_zone(client, camera_id)
    assert created_zone["enabled"] is True

    response = await client.put(
        f"/api/cameras/{camera_id}/zones/{created_zone['id']}",
        json={"enabled": False},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["enabled"] is False


@pytest.mark.asyncio
async def test_update_zone_multiple_fields(client):
    """Test updating multiple zone fields at once."""
    camera_id = await create_test_camera(client)
    created_zone = await create_test_zone(client, camera_id)

    response = await client.put(
        f"/api/cameras/{camera_id}/zones/{created_zone['id']}",
        json={
            "name": "Updated Zone",
            "zone_type": "entry_point",
            "color": "#00FF00",
            "priority": 99,
            "enabled": False,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Zone"
    assert data["zone_type"] == "entry_point"
    assert data["color"] == "#00FF00"
    assert data["priority"] == 99
    assert data["enabled"] is False


@pytest.mark.asyncio
async def test_update_zone_empty_payload(client):
    """Test updating zone with empty payload (no changes)."""
    camera_id = await create_test_camera(client)
    created_zone = await create_test_zone(client, camera_id, name="Original Name")

    response = await client.put(
        f"/api/cameras/{camera_id}/zones/{created_zone['id']}",
        json={},
    )

    assert response.status_code == 200
    data = response.json()
    # Nothing should change
    assert data["name"] == "Original Name"


@pytest.mark.asyncio
async def test_update_zone_nonexistent_zone(client):
    """Test updating a non-existent zone returns 404."""
    camera_id = await create_test_camera(client)
    fake_zone_id = str(uuid.uuid4())

    response = await client.put(
        f"/api/cameras/{camera_id}/zones/{fake_zone_id}",
        json={"name": "New Name"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_zone_nonexistent_camera(client):
    """Test updating a zone with non-existent camera returns 404."""
    fake_camera_id = str(uuid.uuid4())
    fake_zone_id = str(uuid.uuid4())

    response = await client.put(
        f"/api/cameras/{fake_camera_id}/zones/{fake_zone_id}",
        json={"name": "New Name"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_zone_invalid_coordinates(client):
    """Test updating zone with invalid coordinates fails validation."""
    camera_id = await create_test_camera(client)
    created_zone = await create_test_zone(client, camera_id)

    response = await client.put(
        f"/api/cameras/{camera_id}/zones/{created_zone['id']}",
        json={"coordinates": [[0.1, 0.2], [0.3, 0.4]]},  # Too few points
    )

    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_update_zone_invalid_empty_name(client):
    """Test updating zone with empty name fails validation."""
    camera_id = await create_test_camera(client)
    created_zone = await create_test_zone(client, camera_id)

    response = await client.put(
        f"/api/cameras/{camera_id}/zones/{created_zone['id']}",
        json={"name": ""},
    )

    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_update_zone_updated_at_changes(client):
    """Test that updated_at timestamp changes on update."""
    import asyncio

    camera_id = await create_test_camera(client)
    created_zone = await create_test_zone(client, camera_id)
    original_updated_at = created_zone["updated_at"]

    # Wait a moment to ensure timestamp difference
    await asyncio.sleep(0.01)

    response = await client.put(
        f"/api/cameras/{camera_id}/zones/{created_zone['id']}",
        json={"name": "Updated Name"},
    )

    assert response.status_code == 200
    data = response.json()
    # updated_at should have changed
    assert data["updated_at"] != original_updated_at
    # created_at should be unchanged
    assert data["created_at"] == created_zone["created_at"]


# === DELETE Tests ===


@pytest.mark.asyncio
async def test_delete_zone_success(client):
    """Test successful zone deletion."""
    camera_id = await create_test_camera(client)
    created_zone = await create_test_zone(client, camera_id)

    response = await client.delete(f"/api/cameras/{camera_id}/zones/{created_zone['id']}")

    assert response.status_code == 204

    # Verify zone is deleted
    get_response = await client.get(f"/api/cameras/{camera_id}/zones/{created_zone['id']}")
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_delete_zone_nonexistent_zone(client):
    """Test deleting a non-existent zone returns 404."""
    camera_id = await create_test_camera(client)
    fake_zone_id = str(uuid.uuid4())

    response = await client.delete(f"/api/cameras/{camera_id}/zones/{fake_zone_id}")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_zone_nonexistent_camera(client):
    """Test deleting a zone with non-existent camera returns 404."""
    fake_camera_id = str(uuid.uuid4())
    fake_zone_id = str(uuid.uuid4())

    response = await client.delete(f"/api/cameras/{fake_camera_id}/zones/{fake_zone_id}")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_zone_does_not_affect_other_zones(client):
    """Test that deleting one zone doesn't affect others."""
    camera_id = await create_test_camera(client)

    zone1 = await create_test_zone(client, camera_id, name="Zone 1")
    zone2 = await create_test_zone(client, camera_id, name="Zone 2")
    zone3 = await create_test_zone(client, camera_id, name="Zone 3")

    # Delete zone 2
    response = await client.delete(f"/api/cameras/{camera_id}/zones/{zone2['id']}")
    assert response.status_code == 204

    # Zone 1 and 3 should still exist
    response1 = await client.get(f"/api/cameras/{camera_id}/zones/{zone1['id']}")
    assert response1.status_code == 200
    assert response1.json()["name"] == "Zone 1"

    response3 = await client.get(f"/api/cameras/{camera_id}/zones/{zone3['id']}")
    assert response3.status_code == 200
    assert response3.json()["name"] == "Zone 3"

    # Zone 2 should be gone
    response2 = await client.get(f"/api/cameras/{camera_id}/zones/{zone2['id']}")
    assert response2.status_code == 404


@pytest.mark.asyncio
async def test_update_after_delete_fails(client):
    """Test that updating a deleted zone fails."""
    camera_id = await create_test_camera(client)
    created_zone = await create_test_zone(client, camera_id)

    # Delete the zone
    await client.delete(f"/api/cameras/{camera_id}/zones/{created_zone['id']}")

    # Try to update deleted zone
    response = await client.put(
        f"/api/cameras/{camera_id}/zones/{created_zone['id']}",
        json={"name": "New Name"},
    )

    assert response.status_code == 404


# === Schema and Response Format Tests ===


@pytest.mark.asyncio
async def test_zone_list_response_schema(client):
    """Test that list zones endpoint returns correct response schema."""
    camera_id = await create_test_camera(client)
    await create_test_zone(client, camera_id)

    response = await client.get(f"/api/cameras/{camera_id}/zones")

    assert response.status_code == 200
    data = response.json()
    # Verify schema structure
    assert "zones" in data
    assert "count" in data
    assert isinstance(data["zones"], list)
    assert isinstance(data["count"], int)


@pytest.mark.asyncio
async def test_zone_response_includes_all_fields(client):
    """Test that zone response includes all expected fields."""
    camera_id = await create_test_camera(client)

    zone_data = {
        "name": "Complete Zone",
        "zone_type": "entry_point",
        "coordinates": valid_rectangle_coordinates(),
        "shape": "rectangle",
        "color": "#3B82F6",
        "enabled": True,
        "priority": 5,
    }

    response = await client.post(f"/api/cameras/{camera_id}/zones", json=zone_data)

    assert response.status_code == 201
    data = response.json()

    required_fields = [
        "id",
        "camera_id",
        "name",
        "zone_type",
        "coordinates",
        "shape",
        "color",
        "enabled",
        "priority",
        "created_at",
        "updated_at",
    ]
    for field in required_fields:
        assert field in data, f"Missing field: {field}"


# === Zone Type Tests ===


@pytest.mark.asyncio
async def test_create_zone_all_types(client):
    """Test creating zones with all valid zone types."""
    camera_id = await create_test_camera(client)

    zone_types = ["entry_point", "driveway", "sidewalk", "yard", "other"]

    for idx, zone_type in enumerate(zone_types):
        zone_data = {
            "name": f"{zone_type} zone",
            "zone_type": zone_type,
            "coordinates": [
                [0.1 + idx * 0.01, 0.1],
                [0.2 + idx * 0.01, 0.1],
                [0.2 + idx * 0.01, 0.2],
                [0.1 + idx * 0.01, 0.2],
            ],
        }

        response = await client.post(f"/api/cameras/{camera_id}/zones", json=zone_data)

        assert response.status_code == 201
        assert response.json()["zone_type"] == zone_type


@pytest.mark.asyncio
async def test_create_zone_invalid_type(client):
    """Test zone creation fails with invalid zone type."""
    camera_id = await create_test_camera(client)

    zone_data = {
        "name": "Invalid Type Zone",
        "zone_type": "invalid_type",
        "coordinates": valid_rectangle_coordinates(),
    }

    response = await client.post(f"/api/cameras/{camera_id}/zones", json=zone_data)

    assert response.status_code == 422  # Validation error


# === Shape Tests ===


@pytest.mark.asyncio
async def test_create_zone_all_shapes(client):
    """Test creating zones with all valid shapes."""
    camera_id = await create_test_camera(client)

    shapes = ["rectangle", "polygon"]

    for idx, shape in enumerate(shapes):
        zone_data = {
            "name": f"{shape} zone",
            "shape": shape,
            "coordinates": [
                [0.1 + idx * 0.1, 0.1],
                [0.2 + idx * 0.1, 0.1],
                [0.2 + idx * 0.1, 0.2],
                [0.1 + idx * 0.1, 0.2],
            ],
        }

        response = await client.post(f"/api/cameras/{camera_id}/zones", json=zone_data)

        assert response.status_code == 201
        assert response.json()["shape"] == shape


@pytest.mark.asyncio
async def test_create_zone_invalid_shape(client):
    """Test zone creation fails with invalid shape."""
    camera_id = await create_test_camera(client)

    zone_data = {
        "name": "Invalid Shape Zone",
        "shape": "circle",  # Not a valid shape
        "coordinates": valid_rectangle_coordinates(),
    }

    response = await client.post(f"/api/cameras/{camera_id}/zones", json=zone_data)

    assert response.status_code == 422  # Validation error


# === Edge Cases ===


@pytest.mark.asyncio
async def test_create_multiple_zones_same_camera(client):
    """Test creating multiple zones for the same camera."""
    camera_id = await create_test_camera(client)

    for i in range(5):
        zone_data = {
            "name": f"Zone {i}",
            "coordinates": [
                [0.1 + i * 0.01, 0.1],
                [0.2 + i * 0.01, 0.1],
                [0.2 + i * 0.01, 0.2],
                [0.1 + i * 0.01, 0.2],
            ],
        }
        response = await client.post(f"/api/cameras/{camera_id}/zones", json=zone_data)
        assert response.status_code == 201

    # Verify all were created
    list_response = await client.get(f"/api/cameras/{camera_id}/zones")
    data = list_response.json()
    assert data["count"] == 5


@pytest.mark.asyncio
async def test_zone_boundary_coordinates(client):
    """Test zone creation with boundary coordinates (0 and 1)."""
    camera_id = await create_test_camera(client)

    # Zone that uses exact 0 and 1 boundaries
    zone_data = {
        "name": "Boundary Zone",
        "coordinates": [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]],
    }

    response = await client.post(f"/api/cameras/{camera_id}/zones", json=zone_data)

    assert response.status_code == 201
    data = response.json()
    assert data["coordinates"] == [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]]


@pytest.mark.asyncio
async def test_zone_minimum_valid_triangle(client):
    """Test zone creation with minimum valid polygon (triangle)."""
    camera_id = await create_test_camera(client)

    zone_data = {
        "name": "Triangle Zone",
        "coordinates": [[0.1, 0.1], [0.5, 0.1], [0.3, 0.5]],
        "shape": "polygon",
    }

    response = await client.post(f"/api/cameras/{camera_id}/zones", json=zone_data)

    assert response.status_code == 201
    data = response.json()
    assert len(data["coordinates"]) == 3
