"""Snapshot tests for calibration API schema validation (NEM-5021).

These tests validate API response schemas using syrupy snapshots.
Structure-only snapshots ensure schema changes are detected while
ignoring dynamic data like timestamps and IDs.

When schemas change intentionally:
1. Review the snapshot diff carefully
2. Run: pytest backend/tests/integration/api/test_calibration_routes_snapshots.py --snapshot-update
3. Commit the updated snapshot file
"""

import pytest
from syrupy.assertion import SnapshotAssertion

from backend.tests.conftest import extract_schema

# Default threshold values (must match calibration.py)
DEFAULT_LOW_THRESHOLD = 30
DEFAULT_MEDIUM_THRESHOLD = 60
DEFAULT_HIGH_THRESHOLD = 85
DEFAULT_DECAY_FACTOR = 0.1


# === GET /api/calibration Snapshots ===


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_calibration_response_schema_snapshot(
    client,
    snapshot: SnapshotAssertion,
):
    """Test GET /api/calibration response schema with snapshot."""
    response = await client.get("/api/calibration")
    assert response.status_code == 200

    # Extract structure-only schema
    schema = extract_schema(response.json())
    assert schema == snapshot


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_calibration_field_types_snapshot(
    client,
    snapshot: SnapshotAssertion,
):
    """Test GET /api/calibration field types match expected schema."""
    response = await client.get("/api/calibration")
    assert response.status_code == 200

    data = response.json()

    # Verify field types (structure validation)
    field_types = {field: type(value).__name__ for field, value in data.items()}
    assert field_types == snapshot


# === PUT /api/calibration Snapshots ===


@pytest.mark.integration
@pytest.mark.asyncio
async def test_update_calibration_response_schema_snapshot(
    client,
    snapshot: SnapshotAssertion,
):
    """Test PUT /api/calibration response schema with snapshot."""
    # First ensure calibration exists
    await client.get("/api/calibration")

    # Update thresholds
    response = await client.put(
        "/api/calibration",
        json={
            "low_threshold": 25,
            "medium_threshold": 55,
            "high_threshold": 80,
        },
    )
    assert response.status_code == 200

    schema = extract_schema(response.json())
    assert schema == snapshot


@pytest.mark.integration
@pytest.mark.asyncio
async def test_update_calibration_partial_schema_snapshot(
    client,
    snapshot: SnapshotAssertion,
):
    """Test PUT with partial update maintains same schema."""
    await client.get("/api/calibration")

    # Update only one field
    response = await client.put(
        "/api/calibration",
        json={"decay_factor": 0.2},
    )
    assert response.status_code == 200

    schema = extract_schema(response.json())
    assert schema == snapshot


# === PATCH /api/calibration Snapshots ===


@pytest.mark.integration
@pytest.mark.asyncio
async def test_patch_calibration_response_schema_snapshot(
    client,
    snapshot: SnapshotAssertion,
):
    """Test PATCH /api/calibration response schema with snapshot."""
    await client.get("/api/calibration")

    response = await client.patch(
        "/api/calibration",
        json={"low_threshold": 22},
    )
    assert response.status_code == 200

    schema = extract_schema(response.json())
    assert schema == snapshot


# === POST /api/calibration/reset Snapshots ===


@pytest.mark.integration
@pytest.mark.asyncio
async def test_reset_calibration_response_schema_snapshot(
    client,
    snapshot: SnapshotAssertion,
):
    """Test POST /api/calibration/reset response schema with snapshot."""
    # Create calibration with custom values
    await client.put(
        "/api/calibration",
        json={
            "low_threshold": 20,
            "medium_threshold": 50,
            "high_threshold": 80,
        },
    )

    # Reset to defaults
    response = await client.post("/api/calibration/reset")
    assert response.status_code == 200

    schema = extract_schema(response.json())
    assert schema == snapshot


# === GET /api/calibration/defaults Snapshots ===


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_defaults_response_schema_snapshot(
    client,
    snapshot: SnapshotAssertion,
):
    """Test GET /api/calibration/defaults response schema with snapshot."""
    response = await client.get("/api/calibration/defaults")
    assert response.status_code == 200

    schema = extract_schema(response.json())
    assert schema == snapshot


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_defaults_field_count_snapshot(
    client,
    snapshot: SnapshotAssertion,
):
    """Test defaults endpoint returns exactly expected fields."""
    response = await client.get("/api/calibration/defaults")
    assert response.status_code == 200

    data = response.json()
    # Snapshot the sorted field names for deterministic comparison
    fields = sorted(data.keys())
    assert fields == snapshot


# === Error Response Snapshots ===


@pytest.mark.integration
@pytest.mark.asyncio
async def test_calibration_validation_error_schema_snapshot(
    client,
    snapshot: SnapshotAssertion,
):
    """Test that validation errors have consistent schema."""
    await client.get("/api/calibration")

    # Attempt invalid threshold ordering
    response = await client.put(
        "/api/calibration",
        json={
            "low_threshold": 80,
            "medium_threshold": 50,
            "high_threshold": 30,
        },
    )
    assert response.status_code == 422

    schema = extract_schema(response.json())
    assert schema == snapshot


@pytest.mark.integration
@pytest.mark.asyncio
async def test_calibration_out_of_range_error_schema_snapshot(
    client,
    snapshot: SnapshotAssertion,
):
    """Test that out-of-range errors have consistent schema."""
    await client.get("/api/calibration")

    response = await client.put(
        "/api/calibration",
        json={"high_threshold": 101},
    )
    assert response.status_code == 422

    schema = extract_schema(response.json())
    assert schema == snapshot


# === Multi-Response Comparison Snapshots ===


@pytest.mark.integration
@pytest.mark.asyncio
async def test_calibration_create_vs_update_schema_consistency(
    client,
    snapshot: SnapshotAssertion,
):
    """Test that GET, PUT, and PATCH return identical schemas."""
    # GET (auto-creates)
    get_response = await client.get("/api/calibration")
    get_schema = extract_schema(get_response.json())

    # PUT (update)
    put_response = await client.put(
        "/api/calibration",
        json={"low_threshold": 25},
    )
    put_schema = extract_schema(put_response.json())

    # PATCH (partial update)
    patch_response = await client.patch(
        "/api/calibration",
        json={"medium_threshold": 55},
    )
    patch_schema = extract_schema(patch_response.json())

    # All should have identical schema
    assert get_schema == put_schema == patch_schema

    # Snapshot the common schema
    assert get_schema == snapshot
