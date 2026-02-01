"""Integration tests for RTSP camera configuration (Phase 1: Basic RTSP Fields).

NEM-4743: Test-Driven Development for RTSP Camera Configuration UI.
Phase 1 focuses on basic RTSP field integration with the backend API.

These tests verify:
- RTSP camera creation with all required fields
- RTSP camera updates (partial and full)
- RTSP field validation (URL format, required fields)
- Security: RTSP password is NEVER exposed in API responses
"""

import uuid

import pytest

# =============================================================================
# CREATE Tests - RTSP Camera Creation
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.integration
async def test_create_rtsp_camera_success(client):
    """Test successful creation of RTSP camera with all fields.

    EXPECTED TO FAIL: This test should pass once backend properly handles RTSP fields.
    """
    unique_id = str(uuid.uuid4())[:8]
    camera_data = {
        "name": f"Test RTSP Camera {unique_id}",
        "folder_path": f"/export/rtsp/camera_{unique_id}",
        "status": "online",
        "ingestion_mode": "rtsp",
        "rtsp_url": "rtsp://192.168.1.100:554/stream1",
        "rtsp_username": "admin",
        "rtsp_password": "secret123",  # pragma: allowlist secret
        "stream_profile": "main",
        "motion_sensitivity": 0.75,
    }

    response = await client.post("/api/cameras", json=camera_data)

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == camera_data["name"]
    assert data["ingestion_mode"] == "rtsp"
    assert data["rtsp_url"] == "rtsp://192.168.1.100:554/stream1"
    assert data["rtsp_username"] == "admin"
    assert data["stream_profile"] == "main"
    assert data["motion_sensitivity"] == 0.75


@pytest.mark.asyncio
@pytest.mark.integration
async def test_create_rtsp_camera_password_not_exposed(client):
    """Test that RTSP password is NEVER returned in API responses.

    SECURITY CRITICAL: This test MUST PASS to prevent password exposure.
    EXPECTED TO FAIL: Backend currently exposes rtsp_password in responses.

    Fix required: Update CameraResponse schema to exclude rtsp_password field.
    """
    unique_id = str(uuid.uuid4())[:8]
    camera_data = {
        "name": f"Test RTSP Camera {unique_id}",
        "folder_path": f"/export/rtsp/camera_{unique_id}",
        "status": "online",
        "ingestion_mode": "rtsp",
        "rtsp_url": "rtsp://192.168.1.100:554/stream1",
        "rtsp_username": "admin",
        "rtsp_password": "secret123",  # pragma: allowlist secret
        "stream_profile": "main",
    }

    response = await client.post("/api/cameras", json=camera_data)

    assert response.status_code == 201
    data = response.json()
    # SECURITY: Password must NEVER be in response
    assert "rtsp_password" not in data, "SECURITY VIOLATION: rtsp_password exposed in API response"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_create_rtsp_camera_minimal_fields(client):
    """Test creating RTSP camera with only required fields.

    EXPECTED TO FAIL: This test should pass once backend properly handles RTSP fields.
    """
    unique_id = str(uuid.uuid4())[:8]
    camera_data = {
        "name": f"Minimal RTSP Camera {unique_id}",
        "folder_path": f"/export/rtsp/camera_{unique_id}",
        "ingestion_mode": "rtsp",
        "rtsp_url": "rtsp://192.168.1.101:554/stream",
    }

    response = await client.post("/api/cameras", json=camera_data)

    assert response.status_code == 201
    data = response.json()
    assert data["ingestion_mode"] == "rtsp"
    assert data["rtsp_url"] == "rtsp://192.168.1.101:554/stream"
    assert data["rtsp_username"] is None
    assert "rtsp_password" not in data
    assert data["stream_profile"] is None
    assert data["motion_sensitivity"] == 0.5  # Default


# =============================================================================
# VALIDATION Tests - RTSP URL and Required Fields
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.integration
async def test_create_camera_invalid_rtsp_url_format(client):
    """Test that invalid RTSP URL format is rejected.

    EXPECTED TO FAIL: Backend should validate rtsp:// scheme.
    """
    unique_id = str(uuid.uuid4())[:8]
    camera_data = {
        "name": f"Invalid URL Camera {unique_id}",
        "folder_path": f"/export/rtsp/camera_{unique_id}",
        "ingestion_mode": "rtsp",
        "rtsp_url": "http://not-rtsp.com/stream",  # Wrong scheme - should fail
    }

    response = await client.post("/api/cameras", json=camera_data)

    assert response.status_code == 422
    error_data = response.json()
    assert "rtsp_url" in str(error_data).lower()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_create_camera_missing_rtsp_url_for_rtsp_mode(client):
    """Test that rtsp_url is required when ingestion_mode is 'rtsp'.

    EXPECTED TO FAIL: Backend should validate rtsp_url is required for rtsp mode.
    """
    unique_id = str(uuid.uuid4())[:8]
    camera_data = {
        "name": f"Missing URL Camera {unique_id}",
        "folder_path": f"/export/rtsp/camera_{unique_id}",
        "ingestion_mode": "rtsp",
        # Missing rtsp_url - should fail validation
    }

    response = await client.post("/api/cameras", json=camera_data)

    assert response.status_code == 422
    error_data = response.json()
    # Should indicate rtsp_url is required for RTSP mode
    assert "rtsp_url" in str(error_data).lower()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_create_camera_rtsps_url_accepted(client):
    """Test that rtsps:// (secure RTSP) URL is accepted.

    EXPECTED TO FAIL: Backend should accept both rtsp:// and rtsps:// schemes.
    """
    unique_id = str(uuid.uuid4())[:8]
    camera_data = {
        "name": f"Secure RTSP Camera {unique_id}",
        "folder_path": f"/export/rtsp/camera_{unique_id}",
        "ingestion_mode": "rtsp",
        "rtsp_url": "rtsps://192.168.1.100:554/stream",  # Secure RTSP
    }

    response = await client.post("/api/cameras", json=camera_data)

    assert response.status_code == 201
    data = response.json()
    assert data["rtsp_url"] == "rtsps://192.168.1.100:554/stream"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_create_camera_invalid_stream_profile(client):
    """Test that invalid stream_profile value is rejected.

    EXPECTED TO FAIL: Backend should validate stream_profile enum.
    """
    unique_id = str(uuid.uuid4())[:8]
    camera_data = {
        "name": f"Invalid Profile Camera {unique_id}",
        "folder_path": f"/export/rtsp/camera_{unique_id}",
        "ingestion_mode": "rtsp",
        "rtsp_url": "rtsp://192.168.1.100:554/stream",
        "stream_profile": "invalid_value",  # Not in (main, sub, both)
    }

    response = await client.post("/api/cameras", json=camera_data)

    assert response.status_code == 422


@pytest.mark.asyncio
@pytest.mark.integration
async def test_create_camera_motion_sensitivity_out_of_range(client):
    """Test that motion_sensitivity outside [0.0, 1.0] is rejected.

    EXPECTED TO FAIL: Backend should validate motion_sensitivity range.
    """
    unique_id = str(uuid.uuid4())[:8]
    camera_data = {
        "name": f"Invalid Sensitivity Camera {unique_id}",
        "folder_path": f"/export/rtsp/camera_{unique_id}",
        "ingestion_mode": "rtsp",
        "rtsp_url": "rtsp://192.168.1.100:554/stream",
        "motion_sensitivity": 1.5,  # Out of range [0.0, 1.0]
    }

    response = await client.post("/api/cameras", json=camera_data)

    assert response.status_code == 422


# =============================================================================
# UPDATE Tests - RTSP Camera Updates
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.integration
async def test_update_camera_rtsp_url(client):
    """Test updating an existing camera's RTSP URL.

    EXPECTED TO FAIL: Backend should support partial RTSP field updates.
    """
    # Create RTSP camera
    unique_id = str(uuid.uuid4())[:8]
    camera_data = {
        "name": f"Update Test Camera {unique_id}",
        "folder_path": f"/export/rtsp/camera_{unique_id}",
        "ingestion_mode": "rtsp",
        "rtsp_url": "rtsp://192.168.1.100:554/stream1",
    }
    create_response = await client.post("/api/cameras", json=camera_data)
    assert create_response.status_code == 201
    camera_id = create_response.json()["id"]

    # Update RTSP URL
    update_data = {
        "rtsp_url": "rtsp://192.168.1.100:554/stream2",
    }
    response = await client.patch(f"/api/cameras/{camera_id}", json=update_data)

    assert response.status_code == 200
    data = response.json()
    assert data["rtsp_url"] == "rtsp://192.168.1.100:554/stream2"
    # Other fields should remain unchanged
    assert data["ingestion_mode"] == "rtsp"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_update_camera_rtsp_credentials(client):
    """Test updating RTSP username and password.

    EXPECTED TO FAIL: Backend should support credential updates.
    SECURITY: Password must not be in response.
    """
    # Create RTSP camera
    unique_id = str(uuid.uuid4())[:8]
    camera_data = {
        "name": f"Credentials Test Camera {unique_id}",
        "folder_path": f"/export/rtsp/camera_{unique_id}",
        "ingestion_mode": "rtsp",
        "rtsp_url": "rtsp://192.168.1.100:554/stream",
        "rtsp_username": "olduser",
        "rtsp_password": "oldpass",  # pragma: allowlist secret
    }
    create_response = await client.post("/api/cameras", json=camera_data)
    assert create_response.status_code == 201
    camera_id = create_response.json()["id"]

    # Update credentials
    update_data = {
        "rtsp_username": "newuser",
        "rtsp_password": "newpass",  # pragma: allowlist secret
    }
    response = await client.patch(f"/api/cameras/{camera_id}", json=update_data)

    assert response.status_code == 200
    data = response.json()
    assert data["rtsp_username"] == "newuser"
    # SECURITY: Password must NEVER be in response
    assert "rtsp_password" not in data


@pytest.mark.asyncio
@pytest.mark.integration
async def test_update_camera_to_rtsp_mode_from_ftp(client):
    """Test converting an FTP camera to RTSP mode.

    EXPECTED TO FAIL: Backend should support mode migration.
    """
    # Create FTP camera
    unique_id = str(uuid.uuid4())[:8]
    camera_data = {
        "name": f"FTP to RTSP Camera {unique_id}",
        "folder_path": f"/export/foscam/camera_{unique_id}",
        "ingestion_mode": "ftp",
    }
    create_response = await client.post("/api/cameras", json=camera_data)
    assert create_response.status_code == 201
    camera_id = create_response.json()["id"]

    # Convert to RTSP mode
    update_data = {
        "ingestion_mode": "rtsp",
        "rtsp_url": "rtsp://192.168.1.100:554/stream",
    }
    response = await client.patch(f"/api/cameras/{camera_id}", json=update_data)

    assert response.status_code == 200
    data = response.json()
    assert data["ingestion_mode"] == "rtsp"
    assert data["rtsp_url"] == "rtsp://192.168.1.100:554/stream"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_update_camera_stream_profile(client):
    """Test updating stream_profile field.

    EXPECTED TO FAIL: Backend should support stream_profile updates.
    """
    # Create RTSP camera
    unique_id = str(uuid.uuid4())[:8]
    camera_data = {
        "name": f"Stream Profile Test Camera {unique_id}",
        "folder_path": f"/export/rtsp/camera_{unique_id}",
        "ingestion_mode": "rtsp",
        "rtsp_url": "rtsp://192.168.1.100:554/stream",
        "stream_profile": "main",
    }
    create_response = await client.post("/api/cameras", json=camera_data)
    assert create_response.status_code == 201
    camera_id = create_response.json()["id"]

    # Update stream_profile
    update_data = {"stream_profile": "both"}
    response = await client.patch(f"/api/cameras/{camera_id}", json=update_data)

    assert response.status_code == 200
    data = response.json()
    assert data["stream_profile"] == "both"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_update_camera_motion_sensitivity(client):
    """Test updating motion_sensitivity field.

    EXPECTED TO FAIL: Backend should support motion_sensitivity updates.
    """
    # Create camera
    unique_id = str(uuid.uuid4())[:8]
    camera_data = {
        "name": f"Motion Test Camera {unique_id}",
        "folder_path": f"/export/camera_{unique_id}",
        "motion_sensitivity": 0.5,
    }
    create_response = await client.post("/api/cameras", json=camera_data)
    assert create_response.status_code == 201
    camera_id = create_response.json()["id"]

    # Update motion_sensitivity
    update_data = {"motion_sensitivity": 0.8}
    response = await client.patch(f"/api/cameras/{camera_id}", json=update_data)

    assert response.status_code == 200
    data = response.json()
    assert data["motion_sensitivity"] == 0.8


# =============================================================================
# GET Tests - RTSP Fields in Responses
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_camera_returns_rtsp_fields_except_password(client):
    """Test that GET /api/cameras/{id} returns RTSP fields except password.

    EXPECTED TO FAIL: Backend should return RTSP fields in GET responses.
    SECURITY: Password must not be in response.
    """
    # Create RTSP camera
    unique_id = str(uuid.uuid4())[:8]
    camera_data = {
        "name": f"GET Test Camera {unique_id}",
        "folder_path": f"/export/rtsp/camera_{unique_id}",
        "ingestion_mode": "rtsp",
        "rtsp_url": "rtsp://192.168.1.100:554/stream",
        "rtsp_username": "admin",
        "rtsp_password": "secret",  # pragma: allowlist secret
        "stream_profile": "main",
        "motion_sensitivity": 0.7,
    }
    create_response = await client.post("/api/cameras", json=camera_data)
    assert create_response.status_code == 201
    camera_id = create_response.json()["id"]

    # Get camera
    response = await client.get(f"/api/cameras/{camera_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["ingestion_mode"] == "rtsp"
    assert data["rtsp_url"] == "rtsp://192.168.1.100:554/stream"
    assert data["rtsp_username"] == "admin"
    assert data["stream_profile"] == "main"
    assert data["motion_sensitivity"] == 0.7
    # SECURITY: Password must NEVER be in response
    assert "rtsp_password" not in data


@pytest.mark.asyncio
@pytest.mark.integration
async def test_list_cameras_includes_rtsp_fields_except_password(client):
    """Test that GET /api/cameras returns RTSP fields except password.

    EXPECTED TO FAIL: Backend should return RTSP fields in list responses.
    SECURITY: Password must not be in response.
    """
    # Create RTSP camera
    unique_id = str(uuid.uuid4())[:8]
    camera_data = {
        "name": f"List Test Camera {unique_id}",
        "folder_path": f"/export/rtsp/camera_{unique_id}",
        "ingestion_mode": "rtsp",
        "rtsp_url": "rtsp://192.168.1.100:554/stream",
        "rtsp_username": "admin",
        "rtsp_password": "secret",  # pragma: allowlist secret
        "stream_profile": "main",
    }
    await client.post("/api/cameras", json=camera_data)

    # List cameras
    response = await client.get("/api/cameras")

    assert response.status_code == 200
    data = response.json()

    # Find our camera in results
    rtsp_cam = next(
        (c for c in data["items"] if c["name"] == f"List Test Camera {unique_id}"),
        None,
    )
    assert rtsp_cam is not None
    assert rtsp_cam["ingestion_mode"] == "rtsp"
    assert rtsp_cam["rtsp_url"] == "rtsp://192.168.1.100:554/stream"
    assert rtsp_cam["rtsp_username"] == "admin"
    assert rtsp_cam["stream_profile"] == "main"
    # SECURITY: Password must NEVER be in response
    assert "rtsp_password" not in rtsp_cam


# =============================================================================
# EDGE CASES and DEFAULTS
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.integration
async def test_create_ftp_camera_rtsp_fields_default_to_none(client):
    """Test that FTP cameras have RTSP fields defaulting to None.

    EXPECTED TO FAIL: Backend should set RTSP fields to None for FTP cameras.
    """
    unique_id = str(uuid.uuid4())[:8]
    camera_data = {
        "name": f"FTP Camera {unique_id}",
        "folder_path": f"/export/foscam/camera_{unique_id}",
        "ingestion_mode": "ftp",
    }

    response = await client.post("/api/cameras", json=camera_data)

    assert response.status_code == 201
    data = response.json()
    assert data["ingestion_mode"] == "ftp"
    assert data["rtsp_url"] is None
    assert data["rtsp_username"] is None
    assert "rtsp_password" not in data
    assert data["stream_profile"] is None
    assert data["motion_sensitivity"] == 0.5  # Default


@pytest.mark.asyncio
@pytest.mark.integration
async def test_create_onvif_camera_with_rtsp_url(client):
    """Test creating ONVIF camera with RTSP URL.

    EXPECTED TO FAIL: Backend should support ONVIF mode.
    """
    unique_id = str(uuid.uuid4())[:8]
    camera_data = {
        "name": f"ONVIF Camera {unique_id}",
        "folder_path": f"/export/onvif/camera_{unique_id}",
        "ingestion_mode": "onvif",
        "rtsp_url": "rtsp://192.168.1.100:554/onvif1",
        "rtsp_username": "admin",
        "rtsp_password": "secret",  # pragma: allowlist secret
    }

    response = await client.post("/api/cameras", json=camera_data)

    assert response.status_code == 201
    data = response.json()
    assert data["ingestion_mode"] == "onvif"
    assert data["rtsp_url"] == "rtsp://192.168.1.100:554/onvif1"
    assert "rtsp_password" not in data


@pytest.mark.asyncio
@pytest.mark.integration
async def test_update_camera_clear_rtsp_fields_when_switching_to_ftp(client):
    """Test that switching from RTSP to FTP clears RTSP fields.

    EXPECTED TO FAIL: Backend should clear RTSP fields when switching to FTP.
    """
    # Create RTSP camera
    unique_id = str(uuid.uuid4())[:8]
    camera_data = {
        "name": f"Switch to FTP Camera {unique_id}",
        "folder_path": f"/export/camera_{unique_id}",
        "ingestion_mode": "rtsp",
        "rtsp_url": "rtsp://192.168.1.100:554/stream",
        "rtsp_username": "admin",
        "rtsp_password": "secret",  # pragma: allowlist secret
    }
    create_response = await client.post("/api/cameras", json=camera_data)
    assert create_response.status_code == 201
    camera_id = create_response.json()["id"]

    # Switch to FTP mode
    update_data = {"ingestion_mode": "ftp"}
    response = await client.patch(f"/api/cameras/{camera_id}", json=update_data)

    assert response.status_code == 200
    data = response.json()
    assert data["ingestion_mode"] == "ftp"
    # RTSP fields should be cleared
    assert data["rtsp_url"] is None
    assert data["rtsp_username"] is None
    assert "rtsp_password" not in data
