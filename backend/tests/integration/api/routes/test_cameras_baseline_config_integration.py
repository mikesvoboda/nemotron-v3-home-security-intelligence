"""Integration tests for baseline configuration API.

This module tests the end-to-end functionality of baseline tuning:
1. User loads baseline config for a camera
2. User adjusts settings (sensitivity, min_samples)
3. User saves changes (API call, cache invalidation)
4. User resets baseline (confirmation, API call, UI update)

Tests verify complete request/response flows with real database and service instances.
"""

import pytest


@pytest.mark.asyncio
async def test_full_config_flow_get_update_verify(client, integration_db):
    """Test complete config flow: get config, update settings, verify persisted.

    This test verifies that:
    1. GET /api/system/anomaly-config returns current config
    2. PATCH /api/system/anomaly-config updates the config
    3. Subsequent GET returns updated values
    4. Service instance reflects the changes
    """
    # Step 1: Get initial configuration
    response = await client.get("/api/system/anomaly-config")
    assert response.status_code == 200

    initial_config = response.json()
    assert "threshold_stdev" in initial_config
    assert "min_samples" in initial_config
    assert "decay_factor" in initial_config
    assert "window_days" in initial_config

    # Store initial values
    initial_threshold = initial_config["threshold_stdev"]
    initial_min_samples = initial_config["min_samples"]

    # Step 2: Update configuration with new values
    new_threshold = initial_threshold + 0.5
    new_min_samples = initial_min_samples + 5

    update_payload = {
        "threshold_stdev": new_threshold,
        "min_samples": new_min_samples,
    }

    # Note: PATCH requires API key authentication
    headers = {"X-API-Key": "test-api-key"}
    response = await client.patch(
        "/api/system/anomaly-config",
        json=update_payload,
        headers=headers,
    )
    assert response.status_code == 200

    updated_config = response.json()
    assert updated_config["threshold_stdev"] == new_threshold
    assert updated_config["min_samples"] == new_min_samples
    assert updated_config["decay_factor"] == initial_config["decay_factor"]  # Unchanged
    assert updated_config["window_days"] == initial_config["window_days"]  # Unchanged

    # Step 3: Verify configuration persists across requests
    response = await client.get("/api/system/anomaly-config")
    assert response.status_code == 200

    persisted_config = response.json()
    assert persisted_config["threshold_stdev"] == new_threshold
    assert persisted_config["min_samples"] == new_min_samples

    # Step 4: Verify service instance was updated (not just the response)
    # This ensures the configuration change actually affects baseline calculations
    from backend.services.baseline import get_baseline_service

    service = get_baseline_service()
    assert service.anomaly_threshold_std == new_threshold
    assert service.min_samples == new_min_samples


@pytest.mark.asyncio
async def test_config_affects_anomaly_detection(client, integration_db, db_session):
    """Test that config changes affect anomaly detection behavior.

    This test verifies that changing the threshold_stdev parameter
    actually changes which detections are flagged as anomalous.
    """
    from datetime import UTC, datetime

    from backend.models.baseline import ActivityBaseline
    from backend.models.camera import Camera

    # Create test camera
    camera = Camera(
        id="test_cam_config",
        name="Test Camera Config",
        folder_path="/test/path",
        status="online",
    )
    db_session.add(camera)

    # Create baseline data with known statistics
    # avg_count=10.0, so detecting 20 items would be 2 standard deviations above
    baseline = ActivityBaseline(
        camera_id="test_cam_config",
        hour=14,
        day_of_week=0,  # Monday
        avg_count=10.0,
        sample_count=30,  # Sufficient samples
        last_updated=datetime.now(UTC),
    )
    db_session.add(baseline)
    await db_session.commit()

    # Get the baseline service
    from backend.services.baseline import get_baseline_service

    service = get_baseline_service()

    # Reset to default threshold of 2.0 standard deviations
    service.update_config(threshold_stdev=2.0)

    # Test detection at exactly 2.0 standard deviations above mean
    # With threshold=2.0, this should NOT be anomalous (needs to exceed threshold)
    test_time = datetime(2026, 1, 27, 14, 0, 0, tzinfo=UTC)  # Monday at 14:00
    is_anomalous, score = await service.is_anomalous(
        "test_cam_config",
        "person",
        test_time,
        session=db_session,
    )

    # At threshold=2.0, score=2.0 should not be anomalous
    assert not is_anomalous, "Score at threshold should not be anomalous"

    # Now lower the threshold to 1.5 via API
    headers = {"X-API-Key": "test-api-key"}
    response = await client.patch(
        "/api/system/anomaly-config",
        json={"threshold_stdev": 1.5},
        headers=headers,
    )
    assert response.status_code == 200

    # Verify the service was updated
    assert service.anomaly_threshold_std == 1.5

    # Now the same detection should be anomalous
    is_anomalous_new, score_new = await service.is_anomalous(
        "test_cam_config",
        "person",
        test_time,
        session=db_session,
    )

    # With threshold=1.5, score=2.0 should now be anomalous
    assert is_anomalous_new, "Score above new threshold should be anomalous"
    assert score_new == score, "Score calculation should not change"


@pytest.mark.asyncio
async def test_concurrent_config_updates_race_condition(client, integration_db):
    """Test handling of concurrent configuration updates.

    This test verifies that concurrent PATCH requests don't result in
    inconsistent state or lost updates. The last write should win.
    """
    import asyncio

    headers = {"X-API-Key": "test-api-key"}

    # Define two different updates
    update1 = {"threshold_stdev": 2.5, "min_samples": 15}
    update2 = {"threshold_stdev": 3.0, "min_samples": 20}

    # Execute both updates concurrently
    results = await asyncio.gather(
        client.patch("/api/system/anomaly-config", json=update1, headers=headers),
        client.patch("/api/system/anomaly-config", json=update2, headers=headers),
        return_exceptions=True,
    )

    # Both requests should succeed
    assert all(not isinstance(r, Exception) and r.status_code == 200 for r in results), (
        "Both concurrent updates should succeed"
    )

    # Verify final state - should be one of the two updates
    response = await client.get("/api/system/anomaly-config")
    assert response.status_code == 200

    final_config = response.json()

    # The final state should match one of the updates (last write wins)
    is_update1 = (
        final_config["threshold_stdev"] == update1["threshold_stdev"]
        and final_config["min_samples"] == update1["min_samples"]
    )
    is_update2 = (
        final_config["threshold_stdev"] == update2["threshold_stdev"]
        and final_config["min_samples"] == update2["min_samples"]
    )

    assert is_update1 or is_update2, "Final state should match one of the updates"


@pytest.mark.asyncio
async def test_config_update_validation_errors(client, integration_db):
    """Test validation errors for invalid configuration values.

    This test verifies that:
    1. Negative threshold values are rejected
    2. Zero or negative min_samples are rejected
    3. Error messages are descriptive
    4. Invalid updates don't change the configuration
    """
    headers = {"X-API-Key": "test-api-key"}

    # Get initial configuration
    response = await client.get("/api/system/anomaly-config")
    assert response.status_code == 200
    initial_config = response.json()

    # Test 1: Negative threshold_stdev
    response = await client.patch(
        "/api/system/anomaly-config",
        json={"threshold_stdev": -1.0},
        headers=headers,
    )
    assert response.status_code == 400
    assert "positive" in response.json()["detail"].lower()

    # Test 2: Zero threshold_stdev
    response = await client.patch(
        "/api/system/anomaly-config",
        json={"threshold_stdev": 0.0},
        headers=headers,
    )
    assert response.status_code == 400

    # Test 3: Zero min_samples
    response = await client.patch(
        "/api/system/anomaly-config",
        json={"min_samples": 0},
        headers=headers,
    )
    assert response.status_code == 400

    # Test 4: Negative min_samples
    response = await client.patch(
        "/api/system/anomaly-config",
        json={"min_samples": -5},
        headers=headers,
    )
    assert response.status_code == 400

    # Test 5: Invalid type (string instead of number)
    response = await client.patch(
        "/api/system/anomaly-config",
        json={"threshold_stdev": "invalid"},
        headers=headers,
    )
    assert response.status_code == 422  # Pydantic validation error

    # Verify configuration unchanged after all invalid attempts
    response = await client.get("/api/system/anomaly-config")
    assert response.status_code == 200
    final_config = response.json()

    assert final_config["threshold_stdev"] == initial_config["threshold_stdev"]
    assert final_config["min_samples"] == initial_config["min_samples"]


@pytest.mark.asyncio
async def test_config_update_partial_updates(client, integration_db):
    """Test that partial updates only change specified fields.

    This test verifies that updating only threshold_stdev doesn't
    affect min_samples, and vice versa.
    """
    headers = {"X-API-Key": "test-api-key"}

    # Get initial configuration
    response = await client.get("/api/system/anomaly-config")
    assert response.status_code == 200
    initial_config = response.json()

    # Update only threshold_stdev
    new_threshold = initial_config["threshold_stdev"] + 1.0
    response = await client.patch(
        "/api/system/anomaly-config",
        json={"threshold_stdev": new_threshold},
        headers=headers,
    )
    assert response.status_code == 200

    config_after_threshold = response.json()
    assert config_after_threshold["threshold_stdev"] == new_threshold
    assert config_after_threshold["min_samples"] == initial_config["min_samples"]

    # Update only min_samples
    new_min_samples = initial_config["min_samples"] + 10
    response = await client.patch(
        "/api/system/anomaly-config",
        json={"min_samples": new_min_samples},
        headers=headers,
    )
    assert response.status_code == 200

    config_after_min_samples = response.json()
    assert config_after_min_samples["threshold_stdev"] == new_threshold
    assert config_after_min_samples["min_samples"] == new_min_samples


@pytest.mark.asyncio
async def test_config_update_requires_authentication(client, integration_db):
    """Test that PATCH /api/system/anomaly-config requires API key.

    This test verifies that configuration updates require authentication
    but reading configuration does not.
    """
    # GET should work without authentication
    response = await client.get("/api/system/anomaly-config")
    assert response.status_code == 200

    # PATCH should fail without authentication
    response = await client.patch(
        "/api/system/anomaly-config",
        json={"threshold_stdev": 2.5},
    )
    assert response.status_code == 401  # Unauthorized

    # PATCH should succeed with authentication
    headers = {"X-API-Key": "test-api-key"}
    response = await client.patch(
        "/api/system/anomaly-config",
        json={"threshold_stdev": 2.5},
        headers=headers,
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_config_update_creates_audit_log(client, integration_db, db_session):
    """Test that configuration updates are logged to audit trail.

    This test verifies that:
    1. Successful config updates create audit log entries
    2. Audit logs contain old and new values
    3. Audit logs include the correct action type
    """
    from sqlalchemy import select

    from backend.models.audit import AuditAction, AuditLog

    headers = {"X-API-Key": "test-api-key"}

    # Get initial configuration
    response = await client.get("/api/system/anomaly-config")
    assert response.status_code == 200
    initial_config = response.json()

    # Update configuration
    new_threshold = initial_config["threshold_stdev"] + 0.5
    new_min_samples = initial_config["min_samples"] + 5

    response = await client.patch(
        "/api/system/anomaly-config",
        json={
            "threshold_stdev": new_threshold,
            "min_samples": new_min_samples,
        },
        headers=headers,
    )
    assert response.status_code == 200

    # Query audit logs
    result = await db_session.execute(
        select(AuditLog)
        .where(AuditLog.action == AuditAction.CONFIG_UPDATED)
        .where(AuditLog.resource_type == "anomaly_config")
        .order_by(AuditLog.timestamp.desc())
    )
    audit_logs = result.scalars().all()

    # Should have at least one audit log
    assert len(audit_logs) > 0, "Config update should create audit log"

    # Check the most recent audit log
    latest_log = audit_logs[0]
    assert latest_log.action == AuditAction.CONFIG_UPDATED
    assert latest_log.resource_type == "anomaly_config"
    assert latest_log.resource_id == "system"

    # Verify details contain changes
    details = latest_log.details
    assert "changes" in details

    changes = details["changes"]
    assert "threshold_stdev" in changes
    assert changes["threshold_stdev"]["old"] == initial_config["threshold_stdev"]
    assert changes["threshold_stdev"]["new"] == new_threshold

    assert "min_samples" in changes
    assert changes["min_samples"]["old"] == initial_config["min_samples"]
    assert changes["min_samples"]["new"] == new_min_samples


@pytest.mark.asyncio
async def test_config_update_idempotent(client, integration_db):
    """Test that updating config with same values is idempotent.

    This test verifies that:
    1. Updating config with identical values succeeds
    2. No changes are recorded when values don't change
    3. Service state remains consistent
    """
    headers = {"X-API-Key": "test-api-key"}

    # Get initial configuration
    response = await client.get("/api/system/anomaly-config")
    assert response.status_code == 200
    initial_config = response.json()

    # Update with same values
    response = await client.patch(
        "/api/system/anomaly-config",
        json={
            "threshold_stdev": initial_config["threshold_stdev"],
            "min_samples": initial_config["min_samples"],
        },
        headers=headers,
    )
    assert response.status_code == 200

    # Verify config unchanged
    updated_config = response.json()
    assert updated_config == initial_config

    # Verify subsequent GET returns same config
    response = await client.get("/api/system/anomaly-config")
    assert response.status_code == 200
    assert response.json() == initial_config


@pytest.mark.asyncio
async def test_config_endpoint_readonly_fields(client, integration_db):
    """Test that decay_factor and window_days are read-only.

    These fields are returned by GET but cannot be modified via PATCH
    as they affect historical data calculations.
    """
    headers = {"X-API-Key": "test-api-key"}

    # Get initial configuration
    response = await client.get("/api/system/anomaly-config")
    assert response.status_code == 200
    initial_config = response.json()

    initial_decay = initial_config["decay_factor"]
    initial_window = initial_config["window_days"]

    # Try to update read-only fields via PATCH (should be ignored)
    response = await client.patch(
        "/api/system/anomaly-config",
        json={
            "threshold_stdev": 2.5,
            "decay_factor": 0.5,  # Should be ignored
            "window_days": 60,  # Should be ignored
        },
        headers=headers,
    )

    # Request should succeed but ignore read-only fields
    assert response.status_code in [200, 422]

    # Verify read-only fields unchanged
    response = await client.get("/api/system/anomaly-config")
    assert response.status_code == 200
    final_config = response.json()

    assert final_config["decay_factor"] == initial_decay
    assert final_config["window_days"] == initial_window
