"""Integration tests for zone-household linkage API endpoints.

Tests cover:
- Zone household config CRUD operations
- Trust level checking endpoints
- Member/vehicle zone lookup endpoints
- Validation and error handling
- Foreign key constraints

Implements NEM-3190: Backend Zone-Household Linkage API.
"""

import uuid

import pytest

from backend.tests.integration.test_helpers import get_error_message

# === Helper Functions ===


def unique_id(prefix: str = "test") -> str:
    """Generate a unique ID for test objects to prevent conflicts in parallel execution."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def valid_rectangle_coordinates() -> list[list[float]]:
    """Return valid rectangle coordinates for zone creation."""
    return [[0.1, 0.2], [0.3, 0.2], [0.3, 0.8], [0.1, 0.8]]


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
) -> dict:
    """Create a test zone and return the response data."""
    zone_data = {
        "name": name or f"Test Zone {unique_id()}",
        "zone_type": "other",
        "coordinates": valid_rectangle_coordinates(),
        "shape": "rectangle",
        "color": "#FF5733",
        "enabled": True,
        "priority": 5,
    }
    response = await client.post(f"/api/cameras/{camera_id}/zones", json=zone_data)
    assert response.status_code == 201, f"Failed to create zone: {response.json()}"
    return response.json()


async def create_test_member(client, name: str | None = None) -> dict:
    """Create a test household member and return the response data."""
    member_data = {
        "name": name or f"Test Member {unique_id()}",
        "role": "resident",
        "trusted_level": "full",
    }
    response = await client.post("/api/household/members", json=member_data)
    assert response.status_code == 201, f"Failed to create member: {response.json()}"
    return response.json()


async def create_test_vehicle(client, description: str | None = None) -> dict:
    """Create a test registered vehicle and return the response data."""
    vehicle_data = {
        "description": description or f"Test Vehicle {unique_id()}",
        "license_plate": f"ABC{unique_id()[:4].upper()}",
        "vehicle_type": "car",
        "color": "silver",
        "trusted": True,
    }
    response = await client.post("/api/household/vehicles", json=vehicle_data)
    assert response.status_code == 201, f"Failed to create vehicle: {response.json()}"
    return response.json()


# === GET Config Tests ===


@pytest.mark.asyncio
async def test_get_config_returns_null_when_not_configured(client):
    """Test that GET returns null when zone has no household config."""
    camera_id = await create_test_camera(client)
    zone = await create_test_zone(client, camera_id)

    response = await client.get(f"/api/zones/{zone['id']}/household")

    assert response.status_code == 200
    assert response.json() is None


@pytest.mark.asyncio
async def test_get_config_returns_config_when_exists(client):
    """Test that GET returns config when it exists."""
    camera_id = await create_test_camera(client)
    zone = await create_test_zone(client, camera_id)
    member = await create_test_member(client)

    # Create config
    config_data = {
        "owner_id": member["id"],
        "allowed_member_ids": [],
        "allowed_vehicle_ids": [],
        "access_schedules": [],
    }
    await client.put(f"/api/zones/{zone['id']}/household", json=config_data)

    # Get config
    response = await client.get(f"/api/zones/{zone['id']}/household")

    assert response.status_code == 200
    data = response.json()
    assert data is not None
    assert data["zone_id"] == zone["id"]
    assert data["owner_id"] == member["id"]


@pytest.mark.asyncio
async def test_get_config_nonexistent_zone_returns_404(client):
    """Test that GET returns 404 for nonexistent zone."""
    fake_zone_id = str(uuid.uuid4())

    response = await client.get(f"/api/zones/{fake_zone_id}/household")

    assert response.status_code == 404


# === PUT (Upsert) Config Tests ===


@pytest.mark.asyncio
async def test_create_config_with_owner(client):
    """Test creating a config with an owner."""
    camera_id = await create_test_camera(client)
    zone = await create_test_zone(client, camera_id)
    member = await create_test_member(client)

    config_data = {
        "owner_id": member["id"],
        "allowed_member_ids": [],
        "allowed_vehicle_ids": [],
        "access_schedules": [],
    }

    response = await client.put(f"/api/zones/{zone['id']}/household", json=config_data)

    assert response.status_code == 200
    data = response.json()
    assert data["zone_id"] == zone["id"]
    assert data["owner_id"] == member["id"]
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


@pytest.mark.asyncio
async def test_create_config_with_allowed_members(client):
    """Test creating a config with allowed members."""
    camera_id = await create_test_camera(client)
    zone = await create_test_zone(client, camera_id)
    member1 = await create_test_member(client, "Member 1")
    member2 = await create_test_member(client, "Member 2")

    config_data = {
        "owner_id": None,
        "allowed_member_ids": [member1["id"], member2["id"]],
        "allowed_vehicle_ids": [],
        "access_schedules": [],
    }

    response = await client.put(f"/api/zones/{zone['id']}/household", json=config_data)

    assert response.status_code == 200
    data = response.json()
    assert set(data["allowed_member_ids"]) == {member1["id"], member2["id"]}


@pytest.mark.asyncio
async def test_create_config_with_allowed_vehicles(client):
    """Test creating a config with allowed vehicles."""
    camera_id = await create_test_camera(client)
    zone = await create_test_zone(client, camera_id)
    vehicle = await create_test_vehicle(client)

    config_data = {
        "owner_id": None,
        "allowed_member_ids": [],
        "allowed_vehicle_ids": [vehicle["id"]],
        "access_schedules": [],
    }

    response = await client.put(f"/api/zones/{zone['id']}/household", json=config_data)

    assert response.status_code == 200
    data = response.json()
    assert vehicle["id"] in data["allowed_vehicle_ids"]


@pytest.mark.asyncio
async def test_create_config_with_access_schedules(client):
    """Test creating a config with access schedules."""
    camera_id = await create_test_camera(client)
    zone = await create_test_zone(client, camera_id)
    member = await create_test_member(client)

    config_data = {
        "owner_id": None,
        "allowed_member_ids": [],
        "allowed_vehicle_ids": [],
        "access_schedules": [
            {
                "member_ids": [member["id"]],
                "cron_expression": "0 9-17 * * 1-5",
                "description": "Weekday business hours",
            }
        ],
    }

    response = await client.put(f"/api/zones/{zone['id']}/household", json=config_data)

    assert response.status_code == 200
    data = response.json()
    assert len(data["access_schedules"]) == 1
    assert data["access_schedules"][0]["cron_expression"] == "0 9-17 * * 1-5"


@pytest.mark.asyncio
async def test_update_existing_config(client):
    """Test that PUT updates existing config."""
    camera_id = await create_test_camera(client)
    zone = await create_test_zone(client, camera_id)
    member1 = await create_test_member(client, "Member 1")
    member2 = await create_test_member(client, "Member 2")

    # Create initial config
    initial_config = {
        "owner_id": member1["id"],
        "allowed_member_ids": [],
        "allowed_vehicle_ids": [],
        "access_schedules": [],
    }
    response1 = await client.put(f"/api/zones/{zone['id']}/household", json=initial_config)
    assert response1.status_code == 200
    config_id = response1.json()["id"]

    # Update config
    updated_config = {
        "owner_id": member2["id"],
        "allowed_member_ids": [member1["id"]],
        "allowed_vehicle_ids": [],
        "access_schedules": [],
    }
    response2 = await client.put(f"/api/zones/{zone['id']}/household", json=updated_config)

    assert response2.status_code == 200
    data = response2.json()
    # Same config ID (updated, not created new)
    assert data["id"] == config_id
    assert data["owner_id"] == member2["id"]
    assert member1["id"] in data["allowed_member_ids"]


@pytest.mark.asyncio
async def test_create_config_with_nonexistent_owner_returns_404(client):
    """Test that config with nonexistent owner returns 404."""
    camera_id = await create_test_camera(client)
    zone = await create_test_zone(client, camera_id)

    config_data = {
        "owner_id": 999999,  # Nonexistent
        "allowed_member_ids": [],
        "allowed_vehicle_ids": [],
        "access_schedules": [],
    }

    response = await client.put(f"/api/zones/{zone['id']}/household", json=config_data)

    assert response.status_code == 404
    assert "not found" in get_error_message(response.json()).lower()


@pytest.mark.asyncio
async def test_create_config_with_nonexistent_member_returns_404(client):
    """Test that config with nonexistent allowed member returns 404."""
    camera_id = await create_test_camera(client)
    zone = await create_test_zone(client, camera_id)

    config_data = {
        "owner_id": None,
        "allowed_member_ids": [999999],  # Nonexistent
        "allowed_vehicle_ids": [],
        "access_schedules": [],
    }

    response = await client.put(f"/api/zones/{zone['id']}/household", json=config_data)

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_config_with_nonexistent_vehicle_returns_404(client):
    """Test that config with nonexistent allowed vehicle returns 404."""
    camera_id = await create_test_camera(client)
    zone = await create_test_zone(client, camera_id)

    config_data = {
        "owner_id": None,
        "allowed_member_ids": [],
        "allowed_vehicle_ids": [999999],  # Nonexistent
        "access_schedules": [],
    }

    response = await client.put(f"/api/zones/{zone['id']}/household", json=config_data)

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_config_nonexistent_zone_returns_404(client):
    """Test that PUT returns 404 for nonexistent zone."""
    fake_zone_id = str(uuid.uuid4())

    config_data = {
        "owner_id": None,
        "allowed_member_ids": [],
        "allowed_vehicle_ids": [],
        "access_schedules": [],
    }

    response = await client.put(f"/api/zones/{fake_zone_id}/household", json=config_data)

    assert response.status_code == 404


# === PATCH Config Tests ===


@pytest.mark.asyncio
async def test_patch_config_updates_single_field(client):
    """Test that PATCH updates only specified fields."""
    camera_id = await create_test_camera(client)
    zone = await create_test_zone(client, camera_id)
    member1 = await create_test_member(client, "Member 1")
    member2 = await create_test_member(client, "Member 2")

    # Create initial config
    initial_config = {
        "owner_id": member1["id"],
        "allowed_member_ids": [],
        "allowed_vehicle_ids": [],
        "access_schedules": [],
    }
    await client.put(f"/api/zones/{zone['id']}/household", json=initial_config)

    # Patch only allowed_member_ids
    response = await client.patch(
        f"/api/zones/{zone['id']}/household",
        json={"allowed_member_ids": [member2["id"]]},
    )

    assert response.status_code == 200
    data = response.json()
    # Owner should remain unchanged
    assert data["owner_id"] == member1["id"]
    # Allowed members should be updated
    assert data["allowed_member_ids"] == [member2["id"]]


@pytest.mark.asyncio
async def test_patch_config_without_existing_returns_404(client):
    """Test that PATCH returns 404 when no config exists."""
    camera_id = await create_test_camera(client)
    zone = await create_test_zone(client, camera_id)

    response = await client.patch(
        f"/api/zones/{zone['id']}/household",
        json={"owner_id": None},
    )

    assert response.status_code == 404


# === DELETE Config Tests ===


@pytest.mark.asyncio
async def test_delete_config_success(client):
    """Test successful config deletion."""
    camera_id = await create_test_camera(client)
    zone = await create_test_zone(client, camera_id)

    # Create config
    config_data = {
        "owner_id": None,
        "allowed_member_ids": [],
        "allowed_vehicle_ids": [],
        "access_schedules": [],
    }
    await client.put(f"/api/zones/{zone['id']}/household", json=config_data)

    # Delete config
    response = await client.delete(f"/api/zones/{zone['id']}/household")

    assert response.status_code == 204

    # Verify deleted
    get_response = await client.get(f"/api/zones/{zone['id']}/household")
    assert get_response.status_code == 200
    assert get_response.json() is None


@pytest.mark.asyncio
async def test_delete_config_without_existing_returns_404(client):
    """Test that DELETE returns 404 when no config exists."""
    camera_id = await create_test_camera(client)
    zone = await create_test_zone(client, camera_id)

    response = await client.delete(f"/api/zones/{zone['id']}/household")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_config_nonexistent_zone_returns_404(client):
    """Test that DELETE returns 404 for nonexistent zone."""
    fake_zone_id = str(uuid.uuid4())

    response = await client.delete(f"/api/zones/{fake_zone_id}/household")

    assert response.status_code == 404


# === Trust Check Tests ===


@pytest.mark.asyncio
async def test_trust_check_full_for_owner(client):
    """Test that zone owner gets full trust level."""
    camera_id = await create_test_camera(client)
    zone = await create_test_zone(client, camera_id)
    member = await create_test_member(client)

    # Create config with owner
    config_data = {
        "owner_id": member["id"],
        "allowed_member_ids": [],
        "allowed_vehicle_ids": [],
        "access_schedules": [],
    }
    await client.put(f"/api/zones/{zone['id']}/household", json=config_data)

    # Check trust level
    response = await client.get(f"/api/zones/{zone['id']}/household/trust/member/{member['id']}")

    assert response.status_code == 200
    data = response.json()
    assert data["trust_level"] == "full"
    assert data["entity_type"] == "member"
    assert data["entity_id"] == member["id"]


@pytest.mark.asyncio
async def test_trust_check_partial_for_allowed_member(client):
    """Test that allowed member gets partial trust level."""
    camera_id = await create_test_camera(client)
    zone = await create_test_zone(client, camera_id)
    owner = await create_test_member(client, "Owner")
    allowed = await create_test_member(client, "Allowed")

    # Create config
    config_data = {
        "owner_id": owner["id"],
        "allowed_member_ids": [allowed["id"]],
        "allowed_vehicle_ids": [],
        "access_schedules": [],
    }
    await client.put(f"/api/zones/{zone['id']}/household", json=config_data)

    # Check trust level for allowed member
    response = await client.get(f"/api/zones/{zone['id']}/household/trust/member/{allowed['id']}")

    assert response.status_code == 200
    assert response.json()["trust_level"] == "partial"


@pytest.mark.asyncio
async def test_trust_check_partial_for_allowed_vehicle(client):
    """Test that allowed vehicle gets partial trust level."""
    camera_id = await create_test_camera(client)
    zone = await create_test_zone(client, camera_id)
    vehicle = await create_test_vehicle(client)

    # Create config
    config_data = {
        "owner_id": None,
        "allowed_member_ids": [],
        "allowed_vehicle_ids": [vehicle["id"]],
        "access_schedules": [],
    }
    await client.put(f"/api/zones/{zone['id']}/household", json=config_data)

    # Check trust level for allowed vehicle
    response = await client.get(f"/api/zones/{zone['id']}/household/trust/vehicle/{vehicle['id']}")

    assert response.status_code == 200
    assert response.json()["trust_level"] == "partial"


@pytest.mark.asyncio
async def test_trust_check_none_for_unknown_entity(client):
    """Test that unknown entity gets no trust level."""
    camera_id = await create_test_camera(client)
    zone = await create_test_zone(client, camera_id)
    owner = await create_test_member(client, "Owner")

    # Create config
    config_data = {
        "owner_id": owner["id"],
        "allowed_member_ids": [],
        "allowed_vehicle_ids": [],
        "access_schedules": [],
    }
    await client.put(f"/api/zones/{zone['id']}/household", json=config_data)

    # Check trust level for unknown member
    response = await client.get(f"/api/zones/{zone['id']}/household/trust/member/999999")

    assert response.status_code == 200
    assert response.json()["trust_level"] == "none"


@pytest.mark.asyncio
async def test_trust_check_none_when_no_config(client):
    """Test that entity gets no trust when zone has no config."""
    camera_id = await create_test_camera(client)
    zone = await create_test_zone(client, camera_id)

    # Check trust level without creating config
    response = await client.get(f"/api/zones/{zone['id']}/household/trust/member/1")

    assert response.status_code == 200
    assert response.json()["trust_level"] == "none"


@pytest.mark.asyncio
async def test_trust_check_nonexistent_zone_returns_404(client):
    """Test that trust check returns 404 for nonexistent zone."""
    fake_zone_id = str(uuid.uuid4())

    response = await client.get(f"/api/zones/{fake_zone_id}/household/trust/member/1")

    assert response.status_code == 404


# === Member Zones Lookup Tests ===


@pytest.mark.asyncio
async def test_get_member_zones_empty(client):
    """Test getting zones for member with no access."""
    response = await client.get("/api/zones/member/999999/zones")

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_get_member_zones_as_owner(client):
    """Test getting zones where member is owner."""
    camera_id = await create_test_camera(client)
    zone = await create_test_zone(client, camera_id)
    member = await create_test_member(client)

    # Create config with member as owner
    config_data = {
        "owner_id": member["id"],
        "allowed_member_ids": [],
        "allowed_vehicle_ids": [],
        "access_schedules": [],
    }
    await client.put(f"/api/zones/{zone['id']}/household", json=config_data)

    # Get member's zones
    response = await client.get(f"/api/zones/member/{member['id']}/zones")

    assert response.status_code == 200
    zones = response.json()
    assert len(zones) == 1
    assert zones[0]["zone_id"] == zone["id"]
    assert zones[0]["trust_level"] == "full"


@pytest.mark.asyncio
async def test_get_member_zones_as_allowed(client):
    """Test getting zones where member is in allowed list."""
    camera_id = await create_test_camera(client)
    zone = await create_test_zone(client, camera_id)
    owner = await create_test_member(client, "Owner")
    allowed = await create_test_member(client, "Allowed")

    # Create config
    config_data = {
        "owner_id": owner["id"],
        "allowed_member_ids": [allowed["id"]],
        "allowed_vehicle_ids": [],
        "access_schedules": [],
    }
    await client.put(f"/api/zones/{zone['id']}/household", json=config_data)

    # Get allowed member's zones
    response = await client.get(f"/api/zones/member/{allowed['id']}/zones")

    assert response.status_code == 200
    zones = response.json()
    assert len(zones) == 1
    assert zones[0]["trust_level"] == "partial"


# === Vehicle Zones Lookup Tests ===


@pytest.mark.asyncio
async def test_get_vehicle_zones_empty(client):
    """Test getting zones for vehicle with no access."""
    response = await client.get("/api/zones/vehicle/999999/zones")

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_get_vehicle_zones_as_allowed(client):
    """Test getting zones where vehicle is in allowed list."""
    camera_id = await create_test_camera(client)
    zone = await create_test_zone(client, camera_id)
    vehicle = await create_test_vehicle(client)

    # Create config
    config_data = {
        "owner_id": None,
        "allowed_member_ids": [],
        "allowed_vehicle_ids": [vehicle["id"]],
        "access_schedules": [],
    }
    await client.put(f"/api/zones/{zone['id']}/household", json=config_data)

    # Get vehicle's zones
    response = await client.get(f"/api/zones/vehicle/{vehicle['id']}/zones")

    assert response.status_code == 200
    zones = response.json()
    assert len(zones) == 1
    assert zones[0]["zone_id"] == zone["id"]
    assert zones[0]["trust_level"] == "partial"


# === Cascade Deletion Tests ===


@pytest.mark.asyncio
async def test_config_deleted_when_zone_deleted(client):
    """Test that household config is deleted when zone is deleted."""
    camera_id = await create_test_camera(client)
    zone = await create_test_zone(client, camera_id)

    # Create config
    config_data = {
        "owner_id": None,
        "allowed_member_ids": [],
        "allowed_vehicle_ids": [],
        "access_schedules": [],
    }
    await client.put(f"/api/zones/{zone['id']}/household", json=config_data)

    # Verify config exists
    get_response = await client.get(f"/api/zones/{zone['id']}/household")
    assert get_response.json() is not None

    # Delete zone
    delete_response = await client.delete(f"/api/cameras/{camera_id}/zones/{zone['id']}")
    assert delete_response.status_code == 204

    # Verify config is also deleted (zone doesn't exist anymore)
    final_response = await client.get(f"/api/zones/{zone['id']}/household")
    assert final_response.status_code == 404


@pytest.mark.asyncio
async def test_owner_id_nulled_when_member_deleted(client):
    """Test that owner_id is set to NULL when member is deleted."""
    camera_id = await create_test_camera(client)
    zone = await create_test_zone(client, camera_id)
    member = await create_test_member(client)

    # Create config with owner
    config_data = {
        "owner_id": member["id"],
        "allowed_member_ids": [],
        "allowed_vehicle_ids": [],
        "access_schedules": [],
    }
    await client.put(f"/api/zones/{zone['id']}/household", json=config_data)

    # Delete member
    delete_response = await client.delete(f"/api/household/members/{member['id']}")
    assert delete_response.status_code == 204

    # Verify owner_id is now NULL
    get_response = await client.get(f"/api/zones/{zone['id']}/household")
    assert get_response.status_code == 200
    assert get_response.json()["owner_id"] is None


# === Validation Tests ===


@pytest.mark.asyncio
async def test_access_schedule_requires_member_ids(client):
    """Test that access schedules require member_ids."""
    camera_id = await create_test_camera(client)
    zone = await create_test_zone(client, camera_id)

    config_data = {
        "owner_id": None,
        "allowed_member_ids": [],
        "allowed_vehicle_ids": [],
        "access_schedules": [
            {
                # Missing member_ids
                "cron_expression": "* * * * *",
            }
        ],
    }

    response = await client.put(f"/api/zones/{zone['id']}/household", json=config_data)

    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_access_schedule_requires_cron_expression(client):
    """Test that access schedules require cron_expression."""
    camera_id = await create_test_camera(client)
    zone = await create_test_zone(client, camera_id)

    config_data = {
        "owner_id": None,
        "allowed_member_ids": [],
        "allowed_vehicle_ids": [],
        "access_schedules": [
            {
                "member_ids": [1],
                # Missing cron_expression
            }
        ],
    }

    response = await client.put(f"/api/zones/{zone['id']}/household", json=config_data)

    assert response.status_code == 422  # Validation error
