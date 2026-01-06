"""Integration tests for API error scenarios (404/400/422/401).

This module provides comprehensive tests for HTTP error responses across all API routes:
- 404 Not Found: Non-existent resource IDs
- 400 Bad Request: Missing required fields, invalid field types
- 422 Validation Error: Out-of-range values, invalid enum values
- 401 Unauthorized: Protected endpoints without API key

Routes covered: alerts, zones, cameras, events, detections, audit, system.

Uses shared fixtures from conftest.py:
- integration_db: Clean test database
- mock_redis: Mock Redis client
- client: httpx AsyncClient with test app
"""

import uuid

import pytest

from backend.tests.integration.test_helpers import get_error_message


def unique_id(prefix: str = "test") -> str:
    """Generate a unique ID for test objects to prevent conflicts."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


# =============================================================================
# 404 Not Found Tests - Non-existent Resource IDs
# =============================================================================


class TestCameras404:
    """Tests for 404 Not Found on cameras endpoints."""

    @pytest.mark.asyncio
    async def test_get_camera_not_found(self, client):
        """Test getting a non-existent camera returns 404."""
        fake_id = str(uuid.uuid4())
        response = await client.get(f"/api/cameras/{fake_id}")
        assert response.status_code == 404
        data = response.json()
        # Support both old and new error formats
        error_msg = get_error_message(data)
        assert error_msg  # Just verify we got an error message

    @pytest.mark.asyncio
    async def test_update_camera_not_found(self, client):
        """Test updating a non-existent camera returns 404."""
        fake_id = str(uuid.uuid4())
        response = await client.patch(
            f"/api/cameras/{fake_id}",
            json={"name": "New Name"},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_camera_not_found(self, client):
        """Test deleting a non-existent camera returns 404."""
        fake_id = str(uuid.uuid4())
        response = await client.delete(f"/api/cameras/{fake_id}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_camera_snapshot_not_found(self, client):
        """Test getting snapshot for non-existent camera returns 404."""
        fake_id = str(uuid.uuid4())
        response = await client.get(f"/api/cameras/{fake_id}/snapshot")
        assert response.status_code == 404


class TestEvents404:
    """Tests for 404 Not Found on events endpoints."""

    @pytest.mark.asyncio
    async def test_get_event_not_found(self, client):
        """Test getting a non-existent event returns 404."""
        response = await client.get("/api/events/999999")
        assert response.status_code == 404
        data = response.json()
        error_msg = get_error_message(data)
        assert "not found" in error_msg.lower()

    @pytest.mark.asyncio
    async def test_update_event_not_found(self, client):
        """Test updating a non-existent event returns 404."""
        response = await client.patch(
            "/api/events/999999",
            json={"reviewed": True},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_event_detections_not_found(self, client):
        """Test getting detections for non-existent event returns 404."""
        response = await client.get("/api/events/999999/detections")
        assert response.status_code == 404


class TestDetections404:
    """Tests for 404 Not Found on detections endpoints."""

    @pytest.mark.asyncio
    async def test_get_detection_not_found(self, client):
        """Test getting a non-existent detection returns 404."""
        response = await client.get("/api/detections/999999")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_detection_image_not_found(self, client):
        """Test getting image for non-existent detection returns 404."""
        response = await client.get("/api/detections/999999/image")
        assert response.status_code == 404


class TestZones404:
    """Tests for 404 Not Found on zones endpoints."""

    @pytest.mark.asyncio
    async def test_list_zones_nonexistent_camera(self, client):
        """Test listing zones for non-existent camera returns 404."""
        fake_camera_id = str(uuid.uuid4())
        response = await client.get(f"/api/cameras/{fake_camera_id}/zones")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_create_zone_nonexistent_camera(self, client):
        """Test creating zone for non-existent camera returns 404."""
        fake_camera_id = str(uuid.uuid4())
        zone_data = {
            "name": "Test Zone",
            "coordinates": [[0.1, 0.2], [0.3, 0.2], [0.3, 0.8], [0.1, 0.8]],
        }
        response = await client.post(
            f"/api/cameras/{fake_camera_id}/zones",
            json=zone_data,
        )
        assert response.status_code == 404
        data = response.json()
        error_msg = get_error_message(data)
        assert "not found" in error_msg.lower()

    @pytest.mark.asyncio
    async def test_get_zone_not_found(self, client):
        """Test getting a non-existent zone returns 404."""
        # First create a camera to test zone not found
        camera_data = {
            "name": unique_id("Test Camera"),
            "folder_path": unique_id("/export/foscam/test"),
        }
        create_resp = await client.post("/api/cameras", json=camera_data)
        camera_id = create_resp.json()["id"]

        fake_zone_id = str(uuid.uuid4())
        response = await client.get(f"/api/cameras/{camera_id}/zones/{fake_zone_id}")
        assert response.status_code == 404
        data = response.json()
        error_msg = get_error_message(data)
        assert "not found" in error_msg.lower()

    @pytest.mark.asyncio
    async def test_update_zone_not_found(self, client):
        """Test updating a non-existent zone returns 404."""
        # First create a camera
        camera_data = {
            "name": unique_id("Test Camera"),
            "folder_path": unique_id("/export/foscam/test"),
        }
        create_resp = await client.post("/api/cameras", json=camera_data)
        camera_id = create_resp.json()["id"]

        fake_zone_id = str(uuid.uuid4())
        response = await client.put(
            f"/api/cameras/{camera_id}/zones/{fake_zone_id}",
            json={"name": "Updated Name"},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_zone_not_found(self, client):
        """Test deleting a non-existent zone returns 404."""
        # First create a camera
        camera_data = {
            "name": unique_id("Test Camera"),
            "folder_path": unique_id("/export/foscam/test"),
        }
        create_resp = await client.post("/api/cameras", json=camera_data)
        camera_id = create_resp.json()["id"]

        fake_zone_id = str(uuid.uuid4())
        response = await client.delete(f"/api/cameras/{camera_id}/zones/{fake_zone_id}")
        assert response.status_code == 404


class TestAlerts404:
    """Tests for 404 Not Found on alerts endpoints."""

    @pytest.mark.asyncio
    async def test_get_alert_rule_not_found(self, client):
        """Test getting a non-existent alert rule returns 404."""
        fake_id = str(uuid.uuid4())
        response = await client.get(f"/api/alerts/rules/{fake_id}")
        assert response.status_code == 404
        data = response.json()
        error_msg = get_error_message(data)
        assert "not found" in error_msg.lower()

    @pytest.mark.asyncio
    async def test_update_alert_rule_not_found(self, client):
        """Test updating a non-existent alert rule returns 404."""
        fake_id = str(uuid.uuid4())
        response = await client.put(
            f"/api/alerts/rules/{fake_id}",
            json={"name": "Updated Rule"},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_alert_rule_not_found(self, client):
        """Test deleting a non-existent alert rule returns 404."""
        fake_id = str(uuid.uuid4())
        response = await client.delete(f"/api/alerts/rules/{fake_id}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_test_alert_rule_not_found(self, client):
        """Test testing a non-existent alert rule returns 404."""
        fake_id = str(uuid.uuid4())
        response = await client.post(
            f"/api/alerts/rules/{fake_id}/test",
            json={"limit": 10},
        )
        assert response.status_code == 404


class TestAudit404:
    """Tests for 404 Not Found on audit endpoints."""

    @pytest.mark.asyncio
    async def test_get_audit_log_not_found(self, client):
        """Test getting a non-existent audit log returns 404."""
        response = await client.get("/api/audit/999999")
        assert response.status_code == 404


# =============================================================================
# 400 Bad Request Tests - Missing Required Fields, Invalid Types
# =============================================================================


class TestCameras400:
    """Tests for 400 Bad Request on cameras endpoints."""

    @pytest.mark.asyncio
    async def test_create_camera_invalid_json(self, client):
        """Test creating camera with invalid JSON returns 422."""
        response = await client.post(
            "/api/cameras",
            content="not valid json",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_update_camera_invalid_json(self, client):
        """Test updating camera with invalid JSON returns 422."""
        # First create a camera
        camera_data = {
            "name": unique_id("Test Camera"),
            "folder_path": unique_id("/export/foscam/test"),
        }
        create_resp = await client.post("/api/cameras", json=camera_data)
        camera_id = create_resp.json()["id"]

        response = await client.patch(
            f"/api/cameras/{camera_id}",
            content="not valid json",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 422


class TestEvents400:
    """Tests for 400 Bad Request on events endpoints."""

    @pytest.mark.asyncio
    async def test_update_event_invalid_json(self, client):
        """Test updating event with invalid JSON returns 422."""
        response = await client.patch(
            "/api/events/1",
            content="not valid json",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 422


class TestZones400:
    """Tests for 400 Bad Request on zones endpoints."""

    @pytest.mark.asyncio
    async def test_create_zone_invalid_json(self, client):
        """Test creating zone with invalid JSON returns 422."""
        # First create a camera
        camera_data = {
            "name": unique_id("Test Camera"),
            "folder_path": unique_id("/export/foscam/test"),
        }
        create_resp = await client.post("/api/cameras", json=camera_data)
        camera_id = create_resp.json()["id"]

        response = await client.post(
            f"/api/cameras/{camera_id}/zones",
            content="not valid json",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 422


class TestAlerts400:
    """Tests for 400 Bad Request on alerts endpoints."""

    @pytest.mark.asyncio
    async def test_create_alert_rule_invalid_json(self, client):
        """Test creating alert rule with invalid JSON returns 422."""
        response = await client.post(
            "/api/alerts/rules",
            content="not valid json",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 422


# =============================================================================
# 422 Validation Error Tests - Missing Fields, Out-of-Range, Invalid Enums
# =============================================================================


class TestCameras422:
    """Tests for 422 Validation Error on cameras endpoints."""

    @pytest.mark.asyncio
    async def test_create_camera_missing_name(self, client):
        """Test creating camera without name returns 422."""
        camera_data = {
            "folder_path": "/export/foscam/test",
        }
        response = await client.post("/api/cameras", json=camera_data)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_camera_missing_folder_path(self, client):
        """Test creating camera without folder_path returns 422."""
        camera_data = {
            "name": unique_id("Test Camera"),
        }
        response = await client.post("/api/cameras", json=camera_data)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_camera_empty_name(self, client):
        """Test creating camera with empty name returns 422."""
        camera_data = {
            "name": "",
            "folder_path": "/export/foscam/test",
        }
        response = await client.post("/api/cameras", json=camera_data)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_camera_empty_folder_path(self, client):
        """Test creating camera with empty folder_path returns 422."""
        camera_data = {
            "name": unique_id("Test Camera"),
            "folder_path": "",
        }
        response = await client.post("/api/cameras", json=camera_data)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_camera_name_too_long(self, client):
        """Test creating camera with name exceeding max length returns 422."""
        camera_data = {
            "name": "A" * 256,  # Exceeds 255 character limit
            "folder_path": "/export/foscam/test",
        }
        response = await client.post("/api/cameras", json=camera_data)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_camera_folder_path_too_long(self, client):
        """Test creating camera with folder_path exceeding max length returns 422."""
        camera_data = {
            "name": unique_id("Test Camera"),
            "folder_path": "/export/foscam/" + "a" * 500,  # Exceeds 500 character limit
        }
        response = await client.post("/api/cameras", json=camera_data)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_update_camera_empty_name(self, client):
        """Test updating camera with empty name returns 422."""
        # First create a camera
        camera_data = {
            "name": unique_id("Test Camera"),
            "folder_path": unique_id("/export/foscam/test"),
        }
        create_resp = await client.post("/api/cameras", json=camera_data)
        camera_id = create_resp.json()["id"]

        response = await client.patch(
            f"/api/cameras/{camera_id}",
            json={"name": ""},
        )
        assert response.status_code == 422


class TestEvents422:
    """Tests for 422 Validation Error on events endpoints."""

    @pytest.mark.asyncio
    async def test_get_event_invalid_id_format(self, client):
        """Test getting event with invalid ID format returns 422."""
        response = await client.get("/api/events/not_a_number")
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_update_event_invalid_reviewed_type(self, client):
        """Test updating event with invalid reviewed type returns 422."""
        # Create a camera first
        camera_data = {
            "name": unique_id("Test Camera"),
            "folder_path": unique_id("/export/foscam/test"),
        }
        await client.post("/api/cameras", json=camera_data)

        response = await client.patch(
            "/api/events/1",
            json={"reviewed": "not_a_boolean"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_list_events_invalid_limit(self, client):
        """Test listing events with invalid limit returns 422."""
        response = await client.get("/api/events?limit=2000")
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_list_events_negative_offset(self, client):
        """Test listing events with negative offset returns 422."""
        response = await client.get("/api/events?offset=-1")
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_list_events_invalid_date_format(self, client):
        """Test listing events with invalid date format returns 422."""
        response = await client.get("/api/events?start_date=invalid-date")
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_list_events_invalid_boolean(self, client):
        """Test listing events with invalid boolean returns 422."""
        response = await client.get("/api/events?reviewed=maybe")
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_get_event_stats_invalid_date(self, client):
        """Test getting event stats with invalid date returns 422."""
        response = await client.get("/api/events/stats?start_date=invalid-date")
        assert response.status_code == 422


class TestDetections422:
    """Tests for 422 Validation Error on detections endpoints."""

    @pytest.mark.asyncio
    async def test_list_detections_invalid_confidence(self, client):
        """Test listing detections with invalid confidence returns 422."""
        response = await client.get("/api/detections?min_confidence=1.5")
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_list_detections_negative_confidence(self, client):
        """Test listing detections with negative confidence returns 422."""
        response = await client.get("/api/detections?min_confidence=-0.5")
        assert response.status_code == 422


class TestZones422:
    """Tests for 422 Validation Error on zones endpoints."""

    @pytest.mark.asyncio
    async def test_create_zone_missing_name(self, client):
        """Test creating zone without name returns 422."""
        # First create a camera
        camera_data = {
            "name": unique_id("Test Camera"),
            "folder_path": unique_id("/export/foscam/test"),
        }
        create_resp = await client.post("/api/cameras", json=camera_data)
        camera_id = create_resp.json()["id"]

        zone_data = {
            "coordinates": [[0.1, 0.2], [0.3, 0.2], [0.3, 0.8], [0.1, 0.8]],
        }
        response = await client.post(f"/api/cameras/{camera_id}/zones", json=zone_data)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_zone_missing_coordinates(self, client):
        """Test creating zone without coordinates returns 422."""
        # First create a camera
        camera_data = {
            "name": unique_id("Test Camera"),
            "folder_path": unique_id("/export/foscam/test"),
        }
        create_resp = await client.post("/api/cameras", json=camera_data)
        camera_id = create_resp.json()["id"]

        zone_data = {
            "name": "Test Zone",
        }
        response = await client.post(f"/api/cameras/{camera_id}/zones", json=zone_data)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_zone_empty_name(self, client):
        """Test creating zone with empty name returns 422."""
        # First create a camera
        camera_data = {
            "name": unique_id("Test Camera"),
            "folder_path": unique_id("/export/foscam/test"),
        }
        create_resp = await client.post("/api/cameras", json=camera_data)
        camera_id = create_resp.json()["id"]

        zone_data = {
            "name": "",
            "coordinates": [[0.1, 0.2], [0.3, 0.2], [0.3, 0.8], [0.1, 0.8]],
        }
        response = await client.post(f"/api/cameras/{camera_id}/zones", json=zone_data)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_zone_name_too_long(self, client):
        """Test creating zone with name exceeding max length returns 422."""
        # First create a camera
        camera_data = {
            "name": unique_id("Test Camera"),
            "folder_path": unique_id("/export/foscam/test"),
        }
        create_resp = await client.post("/api/cameras", json=camera_data)
        camera_id = create_resp.json()["id"]

        zone_data = {
            "name": "A" * 256,  # Exceeds max length
            "coordinates": [[0.1, 0.2], [0.3, 0.2], [0.3, 0.8], [0.1, 0.8]],
        }
        response = await client.post(f"/api/cameras/{camera_id}/zones", json=zone_data)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_zone_too_few_points(self, client):
        """Test creating zone with less than 3 points returns 422."""
        # First create a camera
        camera_data = {
            "name": unique_id("Test Camera"),
            "folder_path": unique_id("/export/foscam/test"),
        }
        create_resp = await client.post("/api/cameras", json=camera_data)
        camera_id = create_resp.json()["id"]

        zone_data = {
            "name": "Invalid Zone",
            "coordinates": [[0.1, 0.2], [0.3, 0.4]],  # Only 2 points
        }
        response = await client.post(f"/api/cameras/{camera_id}/zones", json=zone_data)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_zone_coordinates_out_of_range(self, client):
        """Test creating zone with coordinates > 1 returns 422."""
        # First create a camera
        camera_data = {
            "name": unique_id("Test Camera"),
            "folder_path": unique_id("/export/foscam/test"),
        }
        create_resp = await client.post("/api/cameras", json=camera_data)
        camera_id = create_resp.json()["id"]

        zone_data = {
            "name": "Invalid Zone",
            "coordinates": [[0.1, 0.2], [1.5, 0.2], [0.3, 0.8], [0.1, 0.8]],  # 1.5 > 1
        }
        response = await client.post(f"/api/cameras/{camera_id}/zones", json=zone_data)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_zone_negative_coordinates(self, client):
        """Test creating zone with negative coordinates returns 422."""
        # First create a camera
        camera_data = {
            "name": unique_id("Test Camera"),
            "folder_path": unique_id("/export/foscam/test"),
        }
        create_resp = await client.post("/api/cameras", json=camera_data)
        camera_id = create_resp.json()["id"]

        zone_data = {
            "name": "Invalid Zone",
            "coordinates": [[-0.1, 0.2], [0.3, 0.2], [0.3, 0.8], [0.1, 0.8]],  # -0.1 < 0
        }
        response = await client.post(f"/api/cameras/{camera_id}/zones", json=zone_data)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_zone_invalid_color(self, client):
        """Test creating zone with invalid hex color returns 422."""
        # First create a camera
        camera_data = {
            "name": unique_id("Test Camera"),
            "folder_path": unique_id("/export/foscam/test"),
        }
        create_resp = await client.post("/api/cameras", json=camera_data)
        camera_id = create_resp.json()["id"]

        zone_data = {
            "name": "Invalid Zone",
            "coordinates": [[0.1, 0.2], [0.3, 0.2], [0.3, 0.8], [0.1, 0.8]],
            "color": "invalid",  # Not a valid hex color
        }
        response = await client.post(f"/api/cameras/{camera_id}/zones", json=zone_data)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_zone_priority_out_of_range(self, client):
        """Test creating zone with priority > 100 returns 422."""
        # First create a camera
        camera_data = {
            "name": unique_id("Test Camera"),
            "folder_path": unique_id("/export/foscam/test"),
        }
        create_resp = await client.post("/api/cameras", json=camera_data)
        camera_id = create_resp.json()["id"]

        zone_data = {
            "name": "Invalid Zone",
            "coordinates": [[0.1, 0.2], [0.3, 0.2], [0.3, 0.8], [0.1, 0.8]],
            "priority": 101,  # Max is 100
        }
        response = await client.post(f"/api/cameras/{camera_id}/zones", json=zone_data)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_zone_negative_priority(self, client):
        """Test creating zone with negative priority returns 422."""
        # First create a camera
        camera_data = {
            "name": unique_id("Test Camera"),
            "folder_path": unique_id("/export/foscam/test"),
        }
        create_resp = await client.post("/api/cameras", json=camera_data)
        camera_id = create_resp.json()["id"]

        zone_data = {
            "name": "Invalid Zone",
            "coordinates": [[0.1, 0.2], [0.3, 0.2], [0.3, 0.8], [0.1, 0.8]],
            "priority": -1,  # Min is 0
        }
        response = await client.post(f"/api/cameras/{camera_id}/zones", json=zone_data)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_zone_invalid_type(self, client):
        """Test creating zone with invalid zone type returns 422."""
        # First create a camera
        camera_data = {
            "name": unique_id("Test Camera"),
            "folder_path": unique_id("/export/foscam/test"),
        }
        create_resp = await client.post("/api/cameras", json=camera_data)
        camera_id = create_resp.json()["id"]

        zone_data = {
            "name": "Invalid Zone",
            "zone_type": "invalid_type",  # Not a valid enum value
            "coordinates": [[0.1, 0.2], [0.3, 0.2], [0.3, 0.8], [0.1, 0.8]],
        }
        response = await client.post(f"/api/cameras/{camera_id}/zones", json=zone_data)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_zone_invalid_shape(self, client):
        """Test creating zone with invalid shape returns 422."""
        # First create a camera
        camera_data = {
            "name": unique_id("Test Camera"),
            "folder_path": unique_id("/export/foscam/test"),
        }
        create_resp = await client.post("/api/cameras", json=camera_data)
        camera_id = create_resp.json()["id"]

        zone_data = {
            "name": "Invalid Zone",
            "shape": "circle",  # Not a valid enum value (rectangle/polygon)
            "coordinates": [[0.1, 0.2], [0.3, 0.2], [0.3, 0.8], [0.1, 0.8]],
        }
        response = await client.post(f"/api/cameras/{camera_id}/zones", json=zone_data)
        assert response.status_code == 422


class TestAlerts422:
    """Tests for 422 Validation Error on alerts endpoints."""

    @pytest.mark.asyncio
    async def test_create_alert_rule_missing_name(self, client):
        """Test creating alert rule without name returns 422."""
        rule_data = {
            "severity": "high",
        }
        response = await client.post("/api/alerts/rules", json=rule_data)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_alert_rule_empty_name(self, client):
        """Test creating alert rule with empty name returns 422."""
        rule_data = {
            "name": "",
        }
        response = await client.post("/api/alerts/rules", json=rule_data)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_alert_rule_name_too_long(self, client):
        """Test creating alert rule with name exceeding max length returns 422."""
        rule_data = {
            "name": "A" * 256,  # Exceeds 255 character limit
        }
        response = await client.post("/api/alerts/rules", json=rule_data)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_alert_rule_invalid_severity(self, client):
        """Test creating alert rule with invalid severity returns 422."""
        rule_data = {
            "name": unique_id("Test Rule"),
            "severity": "invalid_severity",
        }
        response = await client.post("/api/alerts/rules", json=rule_data)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_alert_rule_risk_threshold_too_high(self, client):
        """Test creating alert rule with risk_threshold > 100 returns 422."""
        rule_data = {
            "name": unique_id("Test Rule"),
            "risk_threshold": 150,
        }
        response = await client.post("/api/alerts/rules", json=rule_data)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_alert_rule_risk_threshold_negative(self, client):
        """Test creating alert rule with negative risk_threshold returns 422."""
        rule_data = {
            "name": unique_id("Test Rule"),
            "risk_threshold": -10,
        }
        response = await client.post("/api/alerts/rules", json=rule_data)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_alert_rule_min_confidence_too_high(self, client):
        """Test creating alert rule with min_confidence > 1.0 returns 422."""
        rule_data = {
            "name": unique_id("Test Rule"),
            "min_confidence": 1.5,
        }
        response = await client.post("/api/alerts/rules", json=rule_data)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_alert_rule_min_confidence_negative(self, client):
        """Test creating alert rule with negative min_confidence returns 422."""
        rule_data = {
            "name": unique_id("Test Rule"),
            "min_confidence": -0.5,
        }
        response = await client.post("/api/alerts/rules", json=rule_data)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_alert_rule_cooldown_negative(self, client):
        """Test creating alert rule with negative cooldown_seconds returns 422."""
        rule_data = {
            "name": unique_id("Test Rule"),
            "cooldown_seconds": -100,
        }
        response = await client.post("/api/alerts/rules", json=rule_data)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_update_alert_rule_invalid_severity(self, client):
        """Test updating alert rule with invalid severity returns 422."""
        # First create a rule
        create_resp = await client.post(
            "/api/alerts/rules",
            json={"name": unique_id("Test Rule")},
        )
        rule_id = create_resp.json()["id"]

        response = await client.put(
            f"/api/alerts/rules/{rule_id}",
            json={"severity": "invalid"},
        )
        assert response.status_code == 422


class TestSystem422:
    """Tests for 422 Validation Error on system endpoints."""

    @pytest.mark.asyncio
    async def test_gpu_history_invalid_limit(self, client, mock_redis):
        """Test GPU history with invalid limit is clamped (not rejected).

        Note: The GPU history endpoint clamps limit values instead of
        rejecting them with 422. It uses: limit = max(limit, 1) and
        limit = min(limit, 5000). This tests documents that behavior.
        """
        # Negative limit is clamped to 1, not rejected
        response = await client.get("/api/system/gpu/history?limit=-1")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_gpu_history_invalid_since(self, client, mock_redis):
        """Test GPU history with invalid since timestamp returns 422."""
        response = await client.get("/api/system/gpu/history?since=invalid-date")
        assert response.status_code == 422


# =============================================================================
# 401 Unauthorized Tests - Protected Endpoints Without API Key
# =============================================================================


class TestAdmin401:
    """Tests for 401/403 Unauthorized on admin endpoints.

    Admin endpoints require:
    1. DEBUG=true
    2. ADMIN_ENABLED=true
    3. Optional API key (X-Admin-API-Key header)

    In default test configuration, DEBUG is typically false, so admin
    endpoints return 403 Forbidden.
    """

    @pytest.mark.asyncio
    async def test_seed_cameras_without_auth(self, client, mock_redis):
        """Test seeding cameras without admin access returns 403."""
        response = await client.post(
            "/api/admin/seed/cameras",
            json={"count": 3},
        )
        # Admin endpoints return 403 when DEBUG/ADMIN_ENABLED are not set
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_seed_events_without_auth(self, client, mock_redis):
        """Test seeding events without admin access returns 403."""
        response = await client.post(
            "/api/admin/seed/events",
            json={"count": 10},
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_clear_data_without_auth(self, client, mock_redis):
        """Test clearing data without admin access returns 403."""
        response = await client.request(
            "DELETE",
            "/api/admin/seed/clear",
            json={"confirm": "DELETE_ALL_DATA"},
        )
        assert response.status_code == 403


class TestDLQ401:
    """Tests for 401 Unauthorized on DLQ destructive endpoints.

    DLQ endpoints for requeue and clear require API key when
    api_key_enabled is True.
    """

    @pytest.mark.asyncio
    async def test_requeue_dlq_without_auth(self, client, mock_redis):
        """Test requeue DLQ job requires API key when auth enabled.

        Note: This test verifies the endpoint exists and returns expected status.
        When api_key_enabled is False (default in tests), requests are allowed.
        """
        from unittest.mock import patch

        from backend.core.config import Settings

        # Create a mock settings with api_key_enabled=True
        mock_settings = Settings(
            database_url="postgresql+asyncpg://test:test@localhost/test",  # pragma: allowlist secret  # pragma: allowlist secret
            redis_url="redis://localhost:6379",
            api_key_enabled=True,
            api_keys=["test-api-key"],
        )

        with patch("backend.api.routes.dlq.get_settings", return_value=mock_settings):
            response = await client.post("/api/dlq/requeue/dlq:detection")
            # Should return 401 because API key is required but not provided
            assert response.status_code == 401
            data = response.json()
            error_msg = get_error_message(data)
            assert "api key required" in error_msg.lower()

    @pytest.mark.asyncio
    async def test_requeue_all_dlq_without_auth(self, client, mock_redis):
        """Test requeue all DLQ jobs requires API key when auth enabled."""
        from unittest.mock import patch

        from backend.core.config import Settings

        mock_settings = Settings(
            database_url="postgresql+asyncpg://test:test@localhost/test",  # pragma: allowlist secret  # pragma: allowlist secret
            redis_url="redis://localhost:6379",
            api_key_enabled=True,
            api_keys=["test-api-key"],
        )

        with patch("backend.api.routes.dlq.get_settings", return_value=mock_settings):
            response = await client.post("/api/dlq/requeue-all/dlq:detection")
            assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_clear_dlq_without_auth(self, client, mock_redis):
        """Test clear DLQ requires API key when auth enabled."""
        from unittest.mock import patch

        from backend.core.config import Settings

        mock_settings = Settings(
            database_url="postgresql+asyncpg://test:test@localhost/test",  # pragma: allowlist secret
            redis_url="redis://localhost:6379",
            api_key_enabled=True,
            api_keys=["test-api-key"],
        )

        with patch("backend.api.routes.dlq.get_settings", return_value=mock_settings):
            response = await client.delete("/api/dlq/dlq:detection")
            assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_dlq_invalid_api_key(self, client, mock_redis):
        """Test DLQ endpoints reject invalid API key."""
        from unittest.mock import patch

        from backend.core.config import Settings

        mock_settings = Settings(
            database_url="postgresql+asyncpg://test:test@localhost/test",  # pragma: allowlist secret
            redis_url="redis://localhost:6379",
            api_key_enabled=True,
            api_keys=["valid-api-key"],
        )

        with patch("backend.api.routes.dlq.get_settings", return_value=mock_settings):
            response = await client.post(
                "/api/dlq/requeue/dlq:detection",
                headers={"X-API-Key": "invalid-key"},
            )
            assert response.status_code == 401
            data = response.json()
            error_msg = get_error_message(data)
            assert "invalid" in error_msg.lower()


# =============================================================================
# General Error Handling Tests
# =============================================================================


class TestGeneralErrors:
    """Tests for general API error handling."""

    @pytest.mark.asyncio
    async def test_nonexistent_endpoint_returns_404(self, client, mock_redis):
        """Test accessing non-existent endpoint returns 404."""
        response = await client.get("/api/nonexistent-endpoint")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_wrong_http_method_returns_405(self, client, mock_redis):
        """Test using wrong HTTP method returns 405."""
        # POST to an endpoint that only accepts GET
        response = await client.post("/api/events")
        assert response.status_code == 405

    @pytest.mark.asyncio
    async def test_error_responses_are_json(self, client, mock_redis):
        """Test that error responses have JSON content type."""
        response = await client.get("/api/cameras/invalid-uuid-format-too-long-to-be-valid")
        # 404 for camera not found
        assert response.status_code == 404
        assert "application/json" in response.headers.get("content-type", "")

    @pytest.mark.asyncio
    async def test_error_response_has_detail(self, client, mock_redis):
        """Test that error responses include error message in either format."""
        response = await client.get("/api/events/999999")
        assert response.status_code == 404
        data = response.json()
        # Should have error message in either old or new format
        error_msg = get_error_message(data)
        assert error_msg


class TestAuditErrors:
    """Tests for audit endpoint error handling."""

    @pytest.mark.asyncio
    async def test_list_audit_logs_invalid_limit(self, client, mock_redis):
        """Test listing audit logs with invalid limit."""
        response = await client.get("/api/audit?limit=10000")
        # May return 422 if limit is validated, or 200 with clamped value
        assert response.status_code in [200, 422]

    @pytest.mark.asyncio
    async def test_list_audit_logs_negative_offset(self, client, mock_redis):
        """Test listing audit logs with negative offset."""
        response = await client.get("/api/audit?offset=-1")
        assert response.status_code == 422
