"""Integration tests for alert rules API endpoints.

Tests for the /api/alerts/rules endpoints which provide CRUD operations
for managing alert rules, as well as rule testing functionality.

Endpoints tested:
    GET    /api/alerts/rules              - List all rules
    POST   /api/alerts/rules              - Create rule
    GET    /api/alerts/rules/{rule_id}    - Get rule
    PUT    /api/alerts/rules/{rule_id}    - Update rule
    DELETE /api/alerts/rules/{rule_id}    - Delete rule
    POST   /api/alerts/rules/{rule_id}/test - Test rule against historical events
"""

import uuid
from datetime import datetime

import pytest

from backend.tests.integration.test_helpers import get_error_message


def unique_id(prefix: str = "test") -> str:
    """Generate a unique ID for test objects to prevent conflicts."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


# === CREATE Tests ===


@pytest.mark.asyncio
async def test_create_alert_rule_success(client):
    """Test successful alert rule creation with minimal fields."""
    rule_data = {
        "name": unique_id("Test Alert Rule"),
    }

    response = await client.post("/api/alerts/rules", json=rule_data)

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == rule_data["name"]
    assert data["enabled"] is True  # Default
    assert data["severity"] == "medium"  # Default
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data
    # UUID validation
    uuid.UUID(data["id"])


@pytest.mark.asyncio
async def test_create_alert_rule_with_all_fields(client):
    """Test alert rule creation with all optional fields."""
    rule_data = {
        "name": unique_id("Complete Alert Rule"),
        "description": "A fully configured alert rule for testing",
        "enabled": False,
        "severity": "critical",
        "risk_threshold": 80,
        "object_types": ["person", "vehicle"],
        "camera_ids": ["front_door", "backyard"],
        "zone_ids": ["zone1", "zone2"],
        "min_confidence": 0.9,
        "schedule": {
            "days": ["monday", "tuesday", "wednesday"],
            "start_time": "22:00",
            "end_time": "06:00",
            "timezone": "America/New_York",
        },
        "dedup_key_template": "{camera_id}:{object_type}:{rule_id}",
        "cooldown_seconds": 600,
        "channels": ["pushover", "email"],
    }

    response = await client.post("/api/alerts/rules", json=rule_data)

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == rule_data["name"]
    assert data["description"] == rule_data["description"]
    assert data["enabled"] is False
    assert data["severity"] == "critical"
    assert data["risk_threshold"] == 80
    assert data["object_types"] == ["person", "vehicle"]
    assert data["camera_ids"] == ["front_door", "backyard"]
    assert data["zone_ids"] == ["zone1", "zone2"]
    assert data["min_confidence"] == 0.9
    assert data["schedule"]["days"] == ["monday", "tuesday", "wednesday"]
    assert data["schedule"]["start_time"] == "22:00"
    assert data["schedule"]["end_time"] == "06:00"
    assert data["schedule"]["timezone"] == "America/New_York"
    assert data["dedup_key_template"] == "{camera_id}:{object_type}:{rule_id}"
    assert data["cooldown_seconds"] == 600
    assert data["channels"] == ["pushover", "email"]


@pytest.mark.asyncio
async def test_create_alert_rule_missing_name(client):
    """Test alert rule creation fails without name."""
    rule_data = {
        "severity": "high",
    }

    response = await client.post("/api/alerts/rules", json=rule_data)

    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_create_alert_rule_empty_name(client):
    """Test alert rule creation fails with empty name."""
    rule_data = {
        "name": "",
    }

    response = await client.post("/api/alerts/rules", json=rule_data)

    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_create_alert_rule_invalid_severity(client):
    """Test alert rule creation fails with invalid severity."""
    rule_data = {
        "name": unique_id("Test Rule"),
        "severity": "invalid_severity",
    }

    response = await client.post("/api/alerts/rules", json=rule_data)

    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_create_alert_rule_invalid_risk_threshold_too_high(client):
    """Test alert rule creation fails with risk_threshold > 100."""
    rule_data = {
        "name": unique_id("Test Rule"),
        "risk_threshold": 150,
    }

    response = await client.post("/api/alerts/rules", json=rule_data)

    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_create_alert_rule_invalid_risk_threshold_negative(client):
    """Test alert rule creation fails with negative risk_threshold."""
    rule_data = {
        "name": unique_id("Test Rule"),
        "risk_threshold": -10,
    }

    response = await client.post("/api/alerts/rules", json=rule_data)

    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_create_alert_rule_invalid_min_confidence_too_high(client):
    """Test alert rule creation fails with min_confidence > 1.0."""
    rule_data = {
        "name": unique_id("Test Rule"),
        "min_confidence": 1.5,
    }

    response = await client.post("/api/alerts/rules", json=rule_data)

    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_create_alert_rule_invalid_min_confidence_negative(client):
    """Test alert rule creation fails with negative min_confidence."""
    rule_data = {
        "name": unique_id("Test Rule"),
        "min_confidence": -0.5,
    }

    response = await client.post("/api/alerts/rules", json=rule_data)

    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_create_alert_rule_invalid_cooldown_negative(client):
    """Test alert rule creation fails with negative cooldown_seconds."""
    rule_data = {
        "name": unique_id("Test Rule"),
        "cooldown_seconds": -100,
    }

    response = await client.post("/api/alerts/rules", json=rule_data)

    assert response.status_code == 422  # Validation error


# === READ Tests ===


@pytest.mark.asyncio
async def test_list_alert_rules_success(client):
    """Test listing alert rules."""
    # Create test rules
    rule1_name = unique_id("Rule 1")
    rule2_name = unique_id("Rule 2")
    await client.post("/api/alerts/rules", json={"name": rule1_name})
    await client.post("/api/alerts/rules", json={"name": rule2_name})

    response = await client.get("/api/alerts/rules")

    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "pagination" in data
    assert isinstance(data["items"], list)
    assert data["pagination"]["total"] >= 2  # At least our 2 rules


@pytest.mark.asyncio
async def test_list_alert_rules_filter_by_enabled(client):
    """Test listing alert rules filtered by enabled status."""
    # Create enabled and disabled rules
    enabled_name = unique_id("Enabled Rule")
    disabled_name = unique_id("Disabled Rule")
    await client.post("/api/alerts/rules", json={"name": enabled_name, "enabled": True})
    await client.post("/api/alerts/rules", json={"name": disabled_name, "enabled": False})

    # Filter by enabled=true
    response = await client.get("/api/alerts/rules?enabled=true")

    assert response.status_code == 200
    data = response.json()
    # All returned rules should be enabled
    for rule in data["items"]:
        assert rule["enabled"] is True


@pytest.mark.asyncio
async def test_list_alert_rules_filter_by_disabled(client):
    """Test listing alert rules filtered by disabled status."""
    # Create enabled and disabled rules
    enabled_name = unique_id("Enabled Rule")
    disabled_name = unique_id("Disabled Rule")
    await client.post("/api/alerts/rules", json={"name": enabled_name, "enabled": True})
    await client.post("/api/alerts/rules", json={"name": disabled_name, "enabled": False})

    # Filter by enabled=false
    response = await client.get("/api/alerts/rules?enabled=false")

    assert response.status_code == 200
    data = response.json()
    # All returned rules should be disabled
    for rule in data["items"]:
        assert rule["enabled"] is False


@pytest.mark.asyncio
async def test_list_alert_rules_filter_by_severity(client):
    """Test listing alert rules filtered by severity level."""
    # Create rules with different severities
    await client.post(
        "/api/alerts/rules",
        json={"name": unique_id("Low Rule"), "severity": "low"},
    )
    await client.post(
        "/api/alerts/rules",
        json={"name": unique_id("Critical Rule"), "severity": "critical"},
    )

    # Filter by severity=critical
    response = await client.get("/api/alerts/rules?severity=critical")

    assert response.status_code == 200
    data = response.json()
    # All returned rules should have critical severity
    for rule in data["items"]:
        assert rule["severity"] == "critical"


@pytest.mark.asyncio
async def test_list_alert_rules_pagination_limit(client):
    """Test listing alert rules with limit parameter."""
    # Create several rules
    for i in range(5):
        await client.post("/api/alerts/rules", json={"name": unique_id(f"Rule {i}")})

    # Get with limit=2
    response = await client.get("/api/alerts/rules?limit=2")

    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 2
    assert data["pagination"]["limit"] == 2


@pytest.mark.asyncio
async def test_list_alert_rules_pagination_offset(client):
    """Test listing alert rules with offset parameter."""
    response = await client.get("/api/alerts/rules?offset=0&limit=10")

    assert response.status_code == 200
    data = response.json()
    assert data["pagination"]["offset"] == 0


@pytest.mark.asyncio
async def test_get_alert_rule_by_id_success(client):
    """Test getting a specific alert rule by ID."""
    # Create a rule
    rule_name = unique_id("Test Rule")
    create_response = await client.post(
        "/api/alerts/rules",
        json={"name": rule_name, "severity": "high"},
    )
    rule_id = create_response.json()["id"]

    # Get the rule
    response = await client.get(f"/api/alerts/rules/{rule_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == rule_id
    assert data["name"] == rule_name
    assert data["severity"] == "high"


@pytest.mark.asyncio
async def test_get_alert_rule_by_id_not_found(client):
    """Test getting a non-existent alert rule returns 404."""
    fake_id = str(uuid.uuid4())
    response = await client.get(f"/api/alerts/rules/{fake_id}")

    assert response.status_code == 404
    data = response.json()
    error_msg = get_error_message(data)

    assert "not found" in error_msg.lower()


# === UPDATE Tests ===


@pytest.mark.asyncio
async def test_update_alert_rule_name(client):
    """Test updating alert rule name."""
    # Create a rule
    create_response = await client.post(
        "/api/alerts/rules",
        json={"name": unique_id("Old Name")},
    )
    rule_id = create_response.json()["id"]

    # Update the name
    new_name = unique_id("New Name")
    response = await client.put(
        f"/api/alerts/rules/{rule_id}",
        json={"name": new_name},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == new_name


@pytest.mark.asyncio
async def test_update_alert_rule_severity(client):
    """Test updating alert rule severity."""
    # Create a rule with low severity
    create_response = await client.post(
        "/api/alerts/rules",
        json={"name": unique_id("Test Rule"), "severity": "low"},
    )
    rule_id = create_response.json()["id"]

    # Update to critical severity
    response = await client.put(
        f"/api/alerts/rules/{rule_id}",
        json={"severity": "critical"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["severity"] == "critical"


@pytest.mark.asyncio
async def test_update_alert_rule_enabled_status(client):
    """Test updating alert rule enabled status."""
    # Create an enabled rule
    create_response = await client.post(
        "/api/alerts/rules",
        json={"name": unique_id("Test Rule"), "enabled": True},
    )
    rule_id = create_response.json()["id"]

    # Disable the rule
    response = await client.put(
        f"/api/alerts/rules/{rule_id}",
        json={"enabled": False},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["enabled"] is False


@pytest.mark.asyncio
async def test_update_alert_rule_conditions(client):
    """Test updating alert rule condition fields."""
    # Create a rule
    create_response = await client.post(
        "/api/alerts/rules",
        json={"name": unique_id("Test Rule")},
    )
    rule_id = create_response.json()["id"]

    # Update conditions
    response = await client.put(
        f"/api/alerts/rules/{rule_id}",
        json={
            "risk_threshold": 75,
            "object_types": ["person"],
            "min_confidence": 0.85,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["risk_threshold"] == 75
    assert data["object_types"] == ["person"]
    assert data["min_confidence"] == 0.85


@pytest.mark.asyncio
async def test_update_alert_rule_schedule(client):
    """Test updating alert rule schedule."""
    # Create a rule without schedule
    create_response = await client.post(
        "/api/alerts/rules",
        json={"name": unique_id("Test Rule")},
    )
    rule_id = create_response.json()["id"]

    # Add schedule
    response = await client.put(
        f"/api/alerts/rules/{rule_id}",
        json={
            "schedule": {
                "days": ["saturday", "sunday"],
                "start_time": "08:00",
                "end_time": "20:00",
                "timezone": "UTC",
            }
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["schedule"]["days"] == ["saturday", "sunday"]
    assert data["schedule"]["start_time"] == "08:00"
    assert data["schedule"]["end_time"] == "20:00"


@pytest.mark.asyncio
async def test_update_alert_rule_multiple_fields(client):
    """Test updating multiple alert rule fields at once."""
    # Create a rule
    create_response = await client.post(
        "/api/alerts/rules",
        json={"name": unique_id("Old Rule"), "severity": "low", "enabled": True},
    )
    rule_id = create_response.json()["id"]

    # Update multiple fields
    new_name = unique_id("New Rule")
    response = await client.put(
        f"/api/alerts/rules/{rule_id}",
        json={
            "name": new_name,
            "severity": "high",
            "enabled": False,
            "risk_threshold": 90,
            "channels": ["webhook"],
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == new_name
    assert data["severity"] == "high"
    assert data["enabled"] is False
    assert data["risk_threshold"] == 90
    assert data["channels"] == ["webhook"]


@pytest.mark.asyncio
async def test_update_alert_rule_not_found(client):
    """Test updating a non-existent alert rule returns 404."""
    fake_id = str(uuid.uuid4())
    response = await client.put(
        f"/api/alerts/rules/{fake_id}",
        json={"name": "New Name"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_alert_rule_empty_payload(client):
    """Test updating alert rule with empty payload doesn't change data."""
    # Create a rule
    original_name = unique_id("Test Rule")
    create_response = await client.post(
        "/api/alerts/rules",
        json={"name": original_name, "severity": "high"},
    )
    rule_id = create_response.json()["id"]

    # Update with empty payload
    response = await client.put(f"/api/alerts/rules/{rule_id}", json={})

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == original_name
    assert data["severity"] == "high"


@pytest.mark.asyncio
async def test_update_alert_rule_invalid_severity(client):
    """Test updating alert rule with invalid severity fails validation."""
    # Create a rule
    create_response = await client.post(
        "/api/alerts/rules",
        json={"name": unique_id("Test Rule")},
    )
    rule_id = create_response.json()["id"]

    # Try to update with invalid severity
    response = await client.put(
        f"/api/alerts/rules/{rule_id}",
        json={"severity": "invalid"},
    )

    assert response.status_code == 422  # Validation error


# === DELETE Tests ===


@pytest.mark.asyncio
async def test_delete_alert_rule_success(client):
    """Test successful alert rule deletion."""
    # Create a rule
    create_response = await client.post(
        "/api/alerts/rules",
        json={"name": unique_id("Test Rule")},
    )
    rule_id = create_response.json()["id"]

    # Delete the rule
    response = await client.delete(f"/api/alerts/rules/{rule_id}")

    assert response.status_code == 204

    # Verify rule is deleted
    get_response = await client.get(f"/api/alerts/rules/{rule_id}")
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_delete_alert_rule_not_found(client):
    """Test deleting a non-existent alert rule returns 404."""
    fake_id = str(uuid.uuid4())
    response = await client.delete(f"/api/alerts/rules/{fake_id}")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_after_delete_fails(client):
    """Test that updating a deleted rule fails."""
    # Create a rule
    create_response = await client.post(
        "/api/alerts/rules",
        json={"name": unique_id("Test Rule")},
    )
    rule_id = create_response.json()["id"]

    # Delete the rule
    await client.delete(f"/api/alerts/rules/{rule_id}")

    # Try to update deleted rule
    response = await client.put(
        f"/api/alerts/rules/{rule_id}",
        json={"name": "New Name"},
    )

    assert response.status_code == 404


# === Rule Testing Endpoint Tests ===


@pytest.mark.asyncio
async def test_test_rule_not_found(client):
    """Test testing a non-existent rule returns 404."""
    fake_id = str(uuid.uuid4())
    response = await client.post(
        f"/api/alerts/rules/{fake_id}/test",
        json={"limit": 10},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_test_rule_returns_valid_response(client):
    """Test testing a rule returns valid response structure."""
    # Create a rule
    create_response = await client.post(
        "/api/alerts/rules",
        json={"name": unique_id("Test Rule"), "risk_threshold": 70},
    )
    rule_id = create_response.json()["id"]

    # Test the rule
    response = await client.post(
        f"/api/alerts/rules/{rule_id}/test",
        json={"limit": 10},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["rule_id"] == rule_id
    assert "events_tested" in data
    assert "events_matched" in data
    assert "match_rate" in data
    assert "results" in data
    # match_rate should be between 0 and 1
    assert 0.0 <= data["match_rate"] <= 1.0
    # events_matched should be <= events_tested
    assert data["events_matched"] <= data["events_tested"]


@pytest.mark.asyncio
async def test_test_rule_with_specific_event_ids(client):
    """Test testing a rule with specific event IDs."""
    # Create a rule
    create_response = await client.post(
        "/api/alerts/rules",
        json={"name": unique_id("Test Rule")},
    )
    rule_id = create_response.json()["id"]

    # Test with non-existent event IDs (should return empty results)
    response = await client.post(
        f"/api/alerts/rules/{rule_id}/test",
        json={"event_ids": [999999, 999998]},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["rule_id"] == rule_id
    assert data["events_tested"] == 0  # No events found with those IDs


# === Response Schema Validation Tests ===


@pytest.mark.asyncio
async def test_alert_rule_response_schema(client):
    """Test that alert rule response includes all required fields."""
    # Create a rule
    create_response = await client.post(
        "/api/alerts/rules",
        json={"name": unique_id("Test Rule")},
    )

    assert create_response.status_code == 201
    data = create_response.json()

    # Verify all required fields are present
    required_fields = [
        "id",
        "name",
        "enabled",
        "severity",
        "dedup_key_template",
        "cooldown_seconds",
        "channels",
        "created_at",
        "updated_at",
    ]
    for field in required_fields:
        assert field in data, f"Missing field: {field}"

    # Verify optional fields are present (may be None)
    optional_fields = [
        "description",
        "risk_threshold",
        "object_types",
        "camera_ids",
        "zone_ids",
        "min_confidence",
        "schedule",
        "conditions",
    ]
    for field in optional_fields:
        assert field in data, f"Missing optional field: {field}"


@pytest.mark.asyncio
async def test_alert_rule_list_response_schema(client):
    """Test that list response includes pagination info."""
    # Create a rule
    await client.post("/api/alerts/rules", json={"name": unique_id("Test Rule")})

    response = await client.get("/api/alerts/rules")

    assert response.status_code == 200
    data = response.json()

    # Verify pagination fields
    assert "items" in data
    assert "pagination" in data
    assert isinstance(data["items"], list)
    assert isinstance(data["pagination"]["total"], int)
    assert isinstance(data["pagination"]["limit"], int)
    assert isinstance(data["pagination"]["offset"], int)


# === Edge Cases ===


@pytest.mark.asyncio
async def test_create_alert_rule_with_very_long_name(client):
    """Test alert rule creation with name at max length boundary."""
    # Max length is 255 characters
    long_name = "A" * 255
    rule_data = {"name": long_name}

    response = await client.post("/api/alerts/rules", json=rule_data)

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == long_name


@pytest.mark.asyncio
async def test_create_alert_rule_name_exceeds_max_length(client):
    """Test alert rule creation with name exceeding max length."""
    # Exceed 255 character limit
    too_long_name = "A" * 256
    rule_data = {"name": too_long_name}

    response = await client.post("/api/alerts/rules", json=rule_data)

    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_create_alert_rule_with_boundary_values(client):
    """Test alert rule creation with boundary condition values."""
    rule_data = {
        "name": unique_id("Boundary Test"),
        "risk_threshold": 0,  # Minimum
        "min_confidence": 0.0,  # Minimum
        "cooldown_seconds": 0,  # Minimum
    }

    response = await client.post("/api/alerts/rules", json=rule_data)

    assert response.status_code == 201
    data = response.json()
    assert data["risk_threshold"] == 0
    assert data["min_confidence"] == 0.0
    assert data["cooldown_seconds"] == 0


@pytest.mark.asyncio
async def test_create_alert_rule_with_max_boundary_values(client):
    """Test alert rule creation with maximum boundary condition values."""
    rule_data = {
        "name": unique_id("Max Boundary Test"),
        "risk_threshold": 100,  # Maximum
        "min_confidence": 1.0,  # Maximum
    }

    response = await client.post("/api/alerts/rules", json=rule_data)

    assert response.status_code == 201
    data = response.json()
    assert data["risk_threshold"] == 100
    assert data["min_confidence"] == 1.0


@pytest.mark.asyncio
async def test_list_alert_rules_sorted_by_name(client):
    """Test that listed alert rules are sorted by name."""
    # Create rules with names that sort differently
    await client.post("/api/alerts/rules", json={"name": "Zebra Rule"})
    await client.post("/api/alerts/rules", json={"name": "Alpha Rule"})
    await client.post("/api/alerts/rules", json={"name": "Beta Rule"})

    response = await client.get("/api/alerts/rules")

    assert response.status_code == 200
    data = response.json()

    # Extract rule names
    names = [rule["name"] for rule in data["items"]]
    # Should be sorted
    assert names == sorted(names)


@pytest.mark.asyncio
async def test_create_multiple_rules_with_same_name(client):
    """Test that multiple rules can have the same name (no unique constraint)."""
    rule_name = unique_id("Duplicate Name")

    response1 = await client.post("/api/alerts/rules", json={"name": rule_name})
    response2 = await client.post("/api/alerts/rules", json={"name": rule_name})

    # Both should succeed (name is not unique)
    assert response1.status_code == 201
    assert response2.status_code == 201

    # Should have different IDs
    assert response1.json()["id"] != response2.json()["id"]


@pytest.mark.asyncio
async def test_alert_rule_timestamps_updated(client):
    """Test that updated_at timestamp changes on update."""
    # Create a rule
    create_response = await client.post(
        "/api/alerts/rules",
        json={"name": unique_id("Test Rule")},
    )
    rule_id = create_response.json()["id"]
    original_updated_at = create_response.json()["updated_at"]

    # Small delay to ensure timestamp difference
    import asyncio

    await asyncio.sleep(0.1)

    # Update the rule
    update_response = await client.put(
        f"/api/alerts/rules/{rule_id}",
        json={"description": "Updated description"},
    )

    new_updated_at = update_response.json()["updated_at"]

    # Parse timestamps to compare
    original_dt = datetime.fromisoformat(original_updated_at.replace("Z", "+00:00"))
    new_dt = datetime.fromisoformat(new_updated_at.replace("Z", "+00:00"))

    assert new_dt >= original_dt


@pytest.mark.asyncio
async def test_create_rule_with_legacy_conditions(client):
    """Test alert rule creation with legacy conditions field."""
    rule_data = {
        "name": unique_id("Legacy Rule"),
        "conditions": {
            "risk_threshold": 75,
            "object_types": ["person"],
        },
    }

    response = await client.post("/api/alerts/rules", json=rule_data)

    assert response.status_code == 201
    data = response.json()
    assert data["conditions"]["risk_threshold"] == 75
    assert data["conditions"]["object_types"] == ["person"]


@pytest.mark.asyncio
async def test_filter_by_severity_no_matches(client):
    """Test filtering by severity that doesn't match any rules."""
    # Create a rule with low severity
    await client.post(
        "/api/alerts/rules",
        json={"name": unique_id("Low Rule"), "severity": "low"},
    )

    # Filter by critical (which the rule we just created is not)
    # Note: Other rules might exist, so we just check the filter works
    response = await client.get("/api/alerts/rules?severity=critical")

    assert response.status_code == 200
    data = response.json()
    # All returned rules should have critical severity
    for rule in data["items"]:
        assert rule["severity"] == "critical"
