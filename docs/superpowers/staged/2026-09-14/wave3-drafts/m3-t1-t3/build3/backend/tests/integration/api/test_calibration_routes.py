"""Integration tests for UserCalibration API routes (NEM-2316).

Tests the calibration CRUD endpoints:
- GET    /api/calibration           - Get current user's calibration
- PUT    /api/calibration           - Update calibration thresholds
- POST   /api/calibration/reset     - Reset to default thresholds
- GET    /api/calibration/defaults  - Get default threshold values
"""

import pytest

# Default threshold values (must match calibration.py)
DEFAULT_LOW_THRESHOLD = 30
DEFAULT_MEDIUM_THRESHOLD = 60
DEFAULT_HIGH_THRESHOLD = 85
DEFAULT_DECAY_FACTOR = 0.1


# === GET /api/calibration Tests ===


@pytest.mark.asyncio
async def test_get_calibration_auto_creates_default(client):
    """Test that GET auto-creates calibration with defaults if not exists."""
    response = await client.get("/api/calibration")

    assert response.status_code == 200
    data = response.json()

    # Verify default values
    assert data["low_threshold"] == DEFAULT_LOW_THRESHOLD
    assert data["medium_threshold"] == DEFAULT_MEDIUM_THRESHOLD
    assert data["high_threshold"] == DEFAULT_HIGH_THRESHOLD
    assert data["decay_factor"] == DEFAULT_DECAY_FACTOR

    # Verify default user_id
    assert data["user_id"] == "default"

    # Verify feedback counts start at zero
    assert data["false_positive_count"] == 0
    assert data["missed_threat_count"] == 0

    # Verify timestamps exist
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


@pytest.mark.asyncio
async def test_get_calibration_returns_existing(client):
    """Test that GET returns existing calibration without creating duplicate."""
    # First GET creates the calibration
    response1 = await client.get("/api/calibration")
    assert response1.status_code == 200
    id1 = response1.json()["id"]

    # Second GET returns same calibration
    response2 = await client.get("/api/calibration")
    assert response2.status_code == 200
    id2 = response2.json()["id"]

    assert id1 == id2


@pytest.mark.asyncio
async def test_get_calibration_response_schema(client):
    """Test that GET response includes all expected fields."""
    response = await client.get("/api/calibration")

    assert response.status_code == 200
    data = response.json()

    # Verify all required fields
    required_fields = [
        "id",
        "user_id",
        "low_threshold",
        "medium_threshold",
        "high_threshold",
        "decay_factor",
        "false_positive_count",
        "missed_threat_count",
        "created_at",
        "updated_at",
    ]
    for field in required_fields:
        assert field in data, f"Missing field: {field}"


# === PUT /api/calibration Tests ===


@pytest.mark.asyncio
async def test_update_calibration_single_threshold(client):
    """Test updating a single threshold value."""
    # First GET to ensure calibration exists
    await client.get("/api/calibration")

    # Update low_threshold only
    response = await client.put(
        "/api/calibration",
        json={"low_threshold": 25},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["low_threshold"] == 25
    # Other thresholds unchanged
    assert data["medium_threshold"] == DEFAULT_MEDIUM_THRESHOLD
    assert data["high_threshold"] == DEFAULT_HIGH_THRESHOLD


# === PATCH /api/calibration Tests ===


@pytest.mark.asyncio
async def test_patch_calibration_single_threshold(client):
    """Test patching a single threshold value via PATCH endpoint."""
    # First GET to ensure calibration exists
    await client.get("/api/calibration")

    # Patch low_threshold only
    response = await client.patch(
        "/api/calibration",
        json={"low_threshold": 22},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["low_threshold"] == 22
    # Other thresholds unchanged
    assert data["medium_threshold"] == DEFAULT_MEDIUM_THRESHOLD
    assert data["high_threshold"] == DEFAULT_HIGH_THRESHOLD


@pytest.mark.asyncio
async def test_patch_calibration_multiple_thresholds(client):
    """Test patching multiple thresholds at once via PATCH endpoint."""
    # First GET to ensure calibration exists
    await client.get("/api/calibration")

    response = await client.patch(
        "/api/calibration",
        json={
            "low_threshold": 15,
            "medium_threshold": 45,
            "high_threshold": 75,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["low_threshold"] == 15
    assert data["medium_threshold"] == 45
    assert data["high_threshold"] == 75


@pytest.mark.asyncio
async def test_patch_calibration_invalid_ordering(client):
    """Test that PATCH validates threshold ordering."""
    await client.get("/api/calibration")

    # Try to set low >= medium via PATCH
    response = await client.patch(
        "/api/calibration",
        json={"low_threshold": 65},  # Would exceed default medium (60)
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_patch_calibration_auto_creates(client):
    """Test that PATCH auto-creates calibration if not exists."""
    # PATCH without prior GET should auto-create
    response = await client.patch(
        "/api/calibration",
        json={"low_threshold": 28},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["low_threshold"] == 28
    assert data["user_id"] == "default"


@pytest.mark.asyncio
async def test_patch_calibration_decay_factor(client):
    """Test patching decay factor via PATCH endpoint."""
    await client.get("/api/calibration")

    response = await client.patch(
        "/api/calibration",
        json={"decay_factor": 0.25},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["decay_factor"] == 0.25


@pytest.mark.asyncio
async def test_update_calibration_multiple_thresholds(client):
    """Test updating multiple thresholds at once."""
    # First GET to ensure calibration exists
    await client.get("/api/calibration")

    response = await client.put(
        "/api/calibration",
        json={
            "low_threshold": 20,
            "medium_threshold": 50,
            "high_threshold": 80,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["low_threshold"] == 20
    assert data["medium_threshold"] == 50
    assert data["high_threshold"] == 80


@pytest.mark.asyncio
async def test_update_calibration_decay_factor(client):
    """Test updating decay factor."""
    await client.get("/api/calibration")

    response = await client.put(
        "/api/calibration",
        json={"decay_factor": 0.2},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["decay_factor"] == 0.2


@pytest.mark.asyncio
async def test_update_calibration_empty_payload(client):
    """Test that empty payload doesn't change anything."""
    # First GET and record original values
    get_response = await client.get("/api/calibration")
    original = get_response.json()

    # Update with empty payload
    response = await client.put("/api/calibration", json={})

    assert response.status_code == 200
    data = response.json()

    # All values should be unchanged
    assert data["low_threshold"] == original["low_threshold"]
    assert data["medium_threshold"] == original["medium_threshold"]
    assert data["high_threshold"] == original["high_threshold"]
    assert data["decay_factor"] == original["decay_factor"]


@pytest.mark.asyncio
async def test_update_calibration_auto_creates(client):
    """Test that PUT auto-creates calibration if not exists."""
    # PUT without prior GET should auto-create
    response = await client.put(
        "/api/calibration",
        json={"low_threshold": 25},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["low_threshold"] == 25
    assert data["user_id"] == "default"


# === Threshold Validation Tests ===


@pytest.mark.asyncio
async def test_update_calibration_invalid_ordering_low_ge_medium(client):
    """Test that low >= medium threshold is rejected."""
    await client.get("/api/calibration")

    # Try to set low >= medium
    response = await client.put(
        "/api/calibration",
        json={
            "low_threshold": 60,  # Equal to default medium
        },
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_update_calibration_invalid_ordering_medium_ge_high(client):
    """Test that medium >= high threshold is rejected."""
    await client.get("/api/calibration")

    # Try to set medium >= high
    response = await client.put(
        "/api/calibration",
        json={
            "medium_threshold": 85,  # Equal to default high
        },
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_update_calibration_invalid_ordering_all_thresholds(client):
    """Test that completely invalid ordering is rejected."""
    await client.get("/api/calibration")

    # All thresholds in wrong order
    response = await client.put(
        "/api/calibration",
        json={
            "low_threshold": 80,
            "medium_threshold": 50,
            "high_threshold": 30,
        },
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_update_calibration_boundary_values_valid(client):
    """Test valid boundary threshold values."""
    await client.get("/api/calibration")

    # Valid ordering with spread-out values
    response = await client.put(
        "/api/calibration",
        json={
            "low_threshold": 1,
            "medium_threshold": 2,
            "high_threshold": 3,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["low_threshold"] == 1
    assert data["medium_threshold"] == 2
    assert data["high_threshold"] == 3


@pytest.mark.asyncio
async def test_update_calibration_threshold_out_of_range(client):
    """Test that thresholds out of 0-100 range are rejected."""
    await client.get("/api/calibration")

    # Threshold > 100
    response = await client.put(
        "/api/calibration",
        json={"high_threshold": 101},
    )
    assert response.status_code == 422

    # Threshold < 0
    response = await client.put(
        "/api/calibration",
        json={"low_threshold": -1},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_update_calibration_decay_factor_out_of_range(client):
    """Test that decay_factor out of 0.0-1.0 range is rejected."""
    await client.get("/api/calibration")

    # decay_factor > 1.0
    response = await client.put(
        "/api/calibration",
        json={"decay_factor": 1.5},
    )
    assert response.status_code == 422

    # decay_factor < 0.0
    response = await client.put(
        "/api/calibration",
        json={"decay_factor": -0.1},
    )
    assert response.status_code == 422


# === POST /api/calibration/reset Tests ===


@pytest.mark.asyncio
async def test_reset_calibration_restores_defaults(client):
    """Test that reset restores default threshold values."""
    # First modify the calibration
    await client.put(
        "/api/calibration",
        json={
            "low_threshold": 20,
            "medium_threshold": 50,
            "high_threshold": 80,
            "decay_factor": 0.5,
        },
    )

    # Reset to defaults
    response = await client.post("/api/calibration/reset")

    assert response.status_code == 200
    data = response.json()

    # Verify response structure
    assert "message" in data
    assert "calibration" in data
    assert "reset" in data["message"].lower()

    # Verify defaults restored
    calibration = data["calibration"]
    assert calibration["low_threshold"] == DEFAULT_LOW_THRESHOLD
    assert calibration["medium_threshold"] == DEFAULT_MEDIUM_THRESHOLD
    assert calibration["high_threshold"] == DEFAULT_HIGH_THRESHOLD
    assert calibration["decay_factor"] == DEFAULT_DECAY_FACTOR


@pytest.mark.asyncio
async def test_reset_calibration_preserves_feedback_counts(client):
    """Test that reset preserves feedback statistics."""
    # Note: We can't directly modify feedback counts via API,
    # but we can verify they're not reset to zero if they already exist
    # This test verifies the structure but not the preservation logic
    # (which requires direct database manipulation)

    # Reset should work even on fresh calibration
    response = await client.post("/api/calibration/reset")

    assert response.status_code == 200
    data = response.json()

    # Verify feedback counts exist in response
    calibration = data["calibration"]
    assert "false_positive_count" in calibration
    assert "missed_threat_count" in calibration


@pytest.mark.asyncio
async def test_reset_calibration_auto_creates(client):
    """Test that reset auto-creates calibration if not exists."""
    # Reset without prior GET should auto-create with defaults
    response = await client.post("/api/calibration/reset")

    assert response.status_code == 200
    data = response.json()
    calibration = data["calibration"]
    assert calibration["low_threshold"] == DEFAULT_LOW_THRESHOLD
    assert calibration["user_id"] == "default"


# === GET /api/calibration/defaults Tests ===


@pytest.mark.asyncio
async def test_get_defaults_returns_correct_values(client):
    """Test that defaults endpoint returns expected values."""
    response = await client.get("/api/calibration/defaults")

    assert response.status_code == 200
    data = response.json()

    assert data["low_threshold"] == DEFAULT_LOW_THRESHOLD
    assert data["medium_threshold"] == DEFAULT_MEDIUM_THRESHOLD
    assert data["high_threshold"] == DEFAULT_HIGH_THRESHOLD
    assert data["decay_factor"] == DEFAULT_DECAY_FACTOR


@pytest.mark.asyncio
async def test_get_defaults_does_not_require_calibration(client):
    """Test that defaults endpoint works without existing calibration."""
    # Defaults should be returned regardless of whether calibration exists
    response = await client.get("/api/calibration/defaults")

    assert response.status_code == 200
    data = response.json()

    # All default fields should be present
    assert "low_threshold" in data
    assert "medium_threshold" in data
    assert "high_threshold" in data
    assert "decay_factor" in data


@pytest.mark.asyncio
async def test_get_defaults_response_schema(client):
    """Test defaults response includes exactly expected fields."""
    response = await client.get("/api/calibration/defaults")

    assert response.status_code == 200
    data = response.json()

    # Should have exactly these fields (no more, no less)
    expected_fields = {"low_threshold", "medium_threshold", "high_threshold", "decay_factor"}
    assert set(data.keys()) == expected_fields


# === Update Timestamp Tests ===


@pytest.mark.asyncio
async def test_update_calibration_changes_updated_at(client):
    """Test that updating calibration changes updated_at timestamp."""
    import asyncio

    # Get initial calibration
    response1 = await client.get("/api/calibration")
    original_updated_at = response1.json()["updated_at"]

    # Small delay to ensure timestamp difference
    await asyncio.sleep(0.01)

    # Update calibration
    response2 = await client.put(
        "/api/calibration",
        json={"low_threshold": 25},
    )

    assert response2.status_code == 200
    new_updated_at = response2.json()["updated_at"]

    # updated_at should have changed
    assert new_updated_at != original_updated_at


@pytest.mark.asyncio
async def test_reset_calibration_changes_updated_at(client):
    """Test that resetting calibration changes updated_at timestamp."""
    import asyncio

    # Create calibration with custom values
    await client.put(
        "/api/calibration",
        json={"low_threshold": 20},
    )

    # Get current updated_at
    response1 = await client.get("/api/calibration")
    original_updated_at = response1.json()["updated_at"]

    # Small delay to ensure timestamp difference
    await asyncio.sleep(0.01)

    # Reset calibration
    response2 = await client.post("/api/calibration/reset")

    assert response2.status_code == 200
    new_updated_at = response2.json()["calibration"]["updated_at"]

    # updated_at should have changed
    assert new_updated_at != original_updated_at


# === Edge Cases ===


@pytest.mark.asyncio
async def test_update_preserves_created_at(client):
    """Test that updating calibration preserves created_at timestamp."""
    # Get initial calibration
    response1 = await client.get("/api/calibration")
    original_created_at = response1.json()["created_at"]

    # Update calibration
    response2 = await client.put(
        "/api/calibration",
        json={"low_threshold": 25},
    )

    assert response2.status_code == 200
    new_created_at = response2.json()["created_at"]

    # created_at should be unchanged
    assert new_created_at == original_created_at


@pytest.mark.asyncio
async def test_reset_preserves_created_at(client):
    """Test that resetting calibration preserves created_at timestamp."""
    # Get initial calibration
    response1 = await client.get("/api/calibration")
    original_created_at = response1.json()["created_at"]

    # Reset calibration
    response2 = await client.post("/api/calibration/reset")

    assert response2.status_code == 200
    new_created_at = response2.json()["calibration"]["created_at"]

    # created_at should be unchanged
    assert new_created_at == original_created_at


@pytest.mark.asyncio
async def test_update_calibration_boundary_decay_factors(client):
    """Test boundary values for decay_factor (0.0 and 1.0)."""
    await client.get("/api/calibration")

    # Test minimum (0.0)
    response = await client.put(
        "/api/calibration",
        json={"decay_factor": 0.0},
    )
    assert response.status_code == 200
    assert response.json()["decay_factor"] == 0.0

    # Test maximum (1.0)
    response = await client.put(
        "/api/calibration",
        json={"decay_factor": 1.0},
    )
    assert response.status_code == 200
    assert response.json()["decay_factor"] == 1.0


@pytest.mark.asyncio
async def test_update_calibration_boundary_thresholds(client):
    """Test boundary values for thresholds (0 and 100)."""
    await client.get("/api/calibration")

    # Test with extreme valid values
    response = await client.put(
        "/api/calibration",
        json={
            "low_threshold": 0,
            "medium_threshold": 50,
            "high_threshold": 100,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["low_threshold"] == 0
    assert data["high_threshold"] == 100


# === Idempotency Tests ===


@pytest.mark.asyncio
async def test_get_calibration_idempotent(client):
    """Test that multiple GETs return consistent data."""
    response1 = await client.get("/api/calibration")
    response2 = await client.get("/api/calibration")

    assert response1.status_code == 200
    assert response2.status_code == 200

    # Should return same data (excluding updated_at which might differ)
    data1 = response1.json()
    data2 = response2.json()

    assert data1["id"] == data2["id"]
    assert data1["low_threshold"] == data2["low_threshold"]
    assert data1["medium_threshold"] == data2["medium_threshold"]
    assert data1["high_threshold"] == data2["high_threshold"]


@pytest.mark.asyncio
async def test_reset_calibration_idempotent(client):
    """Test that multiple resets have same effect."""
    # First reset
    response1 = await client.post("/api/calibration/reset")
    assert response1.status_code == 200

    # Second reset
    response2 = await client.post("/api/calibration/reset")
    assert response2.status_code == 200

    # Both should have same threshold values
    cal1 = response1.json()["calibration"]
    cal2 = response2.json()["calibration"]

    assert cal1["low_threshold"] == cal2["low_threshold"]
    assert cal1["medium_threshold"] == cal2["medium_threshold"]
    assert cal1["high_threshold"] == cal2["high_threshold"]
    assert cal1["decay_factor"] == cal2["decay_factor"]
