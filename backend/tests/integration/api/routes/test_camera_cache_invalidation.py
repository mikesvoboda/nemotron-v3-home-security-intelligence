"""Integration tests for cache invalidation behavior on camera mutation endpoints.

These tests verify that camera mutation operations result in consistent data
being returned from subsequent API calls. This validates cache invalidation
works correctly by observing API behavior rather than directly inspecting
cache keys (which requires complex event loop coordination).

Endpoints tested:
- POST /api/cameras - Create camera
- PATCH /api/cameras/{id} - Update camera
- DELETE /api/cameras/{id} - Delete camera

Each test follows the pattern:
1. Perform a mutation operation (create/update/delete)
2. Verify subsequent GET returns consistent data
3. This proves cache was properly invalidated if fresh data is returned

Uses the standard integration test fixtures.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

# Mark as integration tests
pytestmark = pytest.mark.integration


def _unique_id(prefix: str = "test") -> str:
    """Generate a unique ID for test objects to prevent conflicts."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


# =============================================================================
# Test: POST /api/cameras - Create Camera
# =============================================================================


class TestCreateCameraCacheInvalidation:
    """Test cache invalidation on camera creation."""

    @pytest.mark.asyncio
    async def test_create_camera_returns_in_subsequent_list(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that created camera appears in subsequent list requests.

        This verifies cache invalidation behavior by checking that fresh data
        is returned after mutation, rather than stale cached data.
        """
        # Get initial cameras list to populate cache
        initial_response = await client.get("/api/cameras")
        assert initial_response.status_code == 200
        initial_camera_ids = {c["id"] for c in initial_response.json()["items"]}

        # Create camera via API
        unique_id = _unique_id("cam")
        camera_data = {
            "name": f"Test Camera {unique_id}",
            "folder_path": f"/export/foscam/test_{unique_id}",
            "status": "online",
        }

        response = await client.post("/api/cameras", json=camera_data)
        assert response.status_code == 201
        created_camera_id = response.json()["id"]

        # Verify new camera appears in list (proves cache was invalidated)
        list_response = await client.get("/api/cameras")
        assert list_response.status_code == 200
        new_camera_ids = {c["id"] for c in list_response.json()["items"]}

        assert created_camera_id in new_camera_ids
        assert created_camera_id not in initial_camera_ids

    @pytest.mark.asyncio
    async def test_create_camera_appears_in_filtered_list(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that created camera appears in status-filtered list requests.

        This verifies filtered cache invalidation by checking that the new
        camera appears in the appropriate filtered view.
        """
        # Get initial filtered cameras list to populate cache
        initial_response = await client.get("/api/cameras?status=online")
        assert initial_response.status_code == 200

        # Create online camera via API
        unique_id = _unique_id("cam")
        camera_data = {
            "name": f"Online Camera {unique_id}",
            "folder_path": f"/export/foscam/online_{unique_id}",
            "status": "online",
        }

        response = await client.post("/api/cameras", json=camera_data)
        assert response.status_code == 201
        created_camera_id = response.json()["id"]

        # Verify new camera appears in filtered list (proves cache was invalidated)
        filtered_response = await client.get("/api/cameras?status=online")
        assert filtered_response.status_code == 200
        new_online_ids = {c["id"] for c in filtered_response.json()["items"]}

        assert created_camera_id in new_online_ids

    @pytest.mark.asyncio
    async def test_create_camera_subsequent_get_returns_fresh_data(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that GET after create returns fresh data."""
        # Create camera
        unique_id = _unique_id("cam")
        camera_data = {
            "name": f"Fresh Camera {unique_id}",
            "folder_path": f"/export/foscam/fresh_{unique_id}",
            "status": "online",
        }

        create_response = await client.post("/api/cameras", json=camera_data)
        assert create_response.status_code == 201
        created_camera = create_response.json()

        # GET cameras list - should return fresh data
        list_response = await client.get("/api/cameras")
        assert list_response.status_code == 200
        data = list_response.json()

        # Verify the newly created camera is in the response
        camera_ids = [c["id"] for c in data["items"]]
        assert created_camera["id"] in camera_ids


# =============================================================================
# Test: PATCH /api/cameras/{id} - Update Camera
# =============================================================================


class TestUpdateCameraCacheInvalidation:
    """Test cache invalidation on camera update."""

    @pytest.mark.asyncio
    async def test_update_camera_reflects_in_list(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that camera update is reflected in cameras list."""
        # Create a camera first
        unique_id = _unique_id("cam")
        camera_data = {
            "name": f"Original Camera {unique_id}",
            "folder_path": f"/export/foscam/original_{unique_id}",
            "status": "online",
        }

        create_response = await client.post("/api/cameras", json=camera_data)
        assert create_response.status_code == 201
        camera_id = create_response.json()["id"]

        # Update camera via API
        update_data = {"name": f"Updated Camera {unique_id}", "status": "offline"}
        response = await client.patch(f"/api/cameras/{camera_id}", json=update_data)
        assert response.status_code == 200

        # Verify list shows updated values (proves cache was invalidated)
        list_response = await client.get("/api/cameras")
        assert list_response.status_code == 200
        camera = next((c for c in list_response.json()["items"] if c["id"] == camera_id), None)
        assert camera is not None
        assert camera["name"] == update_data["name"]
        assert camera["status"] == "offline"

    @pytest.mark.asyncio
    async def test_update_camera_reflects_in_filtered_list(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that camera update is reflected in status-filtered list."""
        # Create a camera with online status
        unique_id = _unique_id("cam")
        camera_data = {
            "name": f"Status Camera {unique_id}",
            "folder_path": f"/export/foscam/status_{unique_id}",
            "status": "online",
        }

        create_response = await client.post("/api/cameras", json=camera_data)
        assert create_response.status_code == 201
        camera_id = create_response.json()["id"]

        # Verify camera is in online list
        online_response = await client.get("/api/cameras?status=online")
        assert camera_id in {c["id"] for c in online_response.json()["items"]}

        # Update camera status to offline
        update_data = {"status": "offline"}
        response = await client.patch(f"/api/cameras/{camera_id}", json=update_data)
        assert response.status_code == 200

        # Verify camera is no longer in online list (proves cache was invalidated)
        online_response = await client.get("/api/cameras?status=online")
        assert camera_id not in {c["id"] for c in online_response.json()["items"]}

        # Verify camera is now in offline list
        offline_response = await client.get("/api/cameras?status=offline")
        assert camera_id in {c["id"] for c in offline_response.json()["items"]}

    @pytest.mark.asyncio
    async def test_update_camera_subsequent_get_returns_fresh_data(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that GET after update returns fresh data."""
        # Create a camera
        unique_id = _unique_id("cam")
        camera_data = {
            "name": f"Update Test Camera {unique_id}",
            "folder_path": f"/export/foscam/update_{unique_id}",
            "status": "online",
        }

        create_response = await client.post("/api/cameras", json=camera_data)
        assert create_response.status_code == 201
        camera_id = create_response.json()["id"]

        # Update camera
        new_name = f"Updated Camera {unique_id}"
        update_data = {"name": new_name, "status": "offline"}
        update_response = await client.patch(f"/api/cameras/{camera_id}", json=update_data)
        assert update_response.status_code == 200

        # GET cameras list - should return fresh data with updated values
        list_response = await client.get("/api/cameras")
        assert list_response.status_code == 200
        data = list_response.json()

        # Find the updated camera in the response
        updated_camera = next((c for c in data["items"] if c["id"] == camera_id), None)
        assert updated_camera is not None
        assert updated_camera["name"] == new_name
        assert updated_camera["status"] == "offline"


# =============================================================================
# Test: DELETE /api/cameras/{id} - Delete Camera
# =============================================================================


class TestDeleteCameraCacheInvalidation:
    """Test cache invalidation on camera deletion."""

    @pytest.mark.asyncio
    async def test_delete_camera_removes_from_list(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that deleted camera is removed from cameras list."""
        # Create a camera
        unique_id = _unique_id("cam")
        camera_data = {
            "name": f"Delete Test Camera {unique_id}",
            "folder_path": f"/export/foscam/delete_{unique_id}",
            "status": "online",
        }

        create_response = await client.post("/api/cameras", json=camera_data)
        assert create_response.status_code == 201
        camera_id = create_response.json()["id"]

        # Verify camera is in list
        list_response = await client.get("/api/cameras")
        assert camera_id in {c["id"] for c in list_response.json()["items"]}

        # Delete camera via API
        response = await client.delete(f"/api/cameras/{camera_id}")
        assert response.status_code == 204

        # Verify camera is removed from list (proves cache was invalidated)
        list_response = await client.get("/api/cameras")
        assert camera_id not in {c["id"] for c in list_response.json()["items"]}

    @pytest.mark.asyncio
    async def test_delete_camera_removes_from_filtered_list(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that deleted camera is removed from status-filtered list."""
        # Create a camera
        unique_id = _unique_id("cam")
        camera_data = {
            "name": f"Filtered Delete Camera {unique_id}",
            "folder_path": f"/export/foscam/filtered_delete_{unique_id}",
            "status": "online",
        }

        create_response = await client.post("/api/cameras", json=camera_data)
        assert create_response.status_code == 201
        camera_id = create_response.json()["id"]

        # Verify camera is in filtered list
        filtered_response = await client.get("/api/cameras?status=online")
        assert camera_id in {c["id"] for c in filtered_response.json()["items"]}

        # Delete camera
        response = await client.delete(f"/api/cameras/{camera_id}")
        assert response.status_code == 204

        # Verify camera is removed from filtered list (proves cache was invalidated)
        filtered_response = await client.get("/api/cameras?status=online")
        assert camera_id not in {c["id"] for c in filtered_response.json()["items"]}

    @pytest.mark.asyncio
    async def test_delete_camera_subsequent_get_returns_fresh_data(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that GET after delete returns fresh data without deleted camera."""
        # Create a camera
        unique_id = _unique_id("cam")
        camera_data = {
            "name": f"Delete Fresh Camera {unique_id}",
            "folder_path": f"/export/foscam/delete_fresh_{unique_id}",
            "status": "online",
        }

        create_response = await client.post("/api/cameras", json=camera_data)
        assert create_response.status_code == 201
        camera_id = create_response.json()["id"]

        # Delete camera
        delete_response = await client.delete(f"/api/cameras/{camera_id}")
        assert delete_response.status_code == 204

        # GET cameras list - should return fresh data without deleted camera
        list_response = await client.get("/api/cameras")
        assert list_response.status_code == 200
        data = list_response.json()

        # Verify the deleted camera is NOT in the response
        camera_ids = [c["id"] for c in data["items"]]
        assert camera_id not in camera_ids


# =============================================================================
# Test: Cross-Endpoint Cache Consistency
# =============================================================================


class TestCrossEndpointCacheConsistency:
    """Test cache consistency across different camera mutation endpoints."""

    @pytest.mark.asyncio
    async def test_create_then_update_reflects_in_list(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that creating then updating cameras reflects correctly in list.

        This test verifies cache consistency by checking that the list API
        returns the updated data after both create and update operations.
        """
        # Create camera with online status
        unique_id = _unique_id("cam")
        create_data = {
            "name": f"Consistency Camera {unique_id}",
            "folder_path": f"/export/foscam/consistency_{unique_id}",
            "status": "online",
        }

        response = await client.post("/api/cameras", json=create_data)
        assert response.status_code == 201
        camera_id = response.json()["id"]

        # Verify camera appears in list with online status
        list_response = await client.get("/api/cameras")
        assert list_response.status_code == 200
        camera = next((c for c in list_response.json()["items"] if c["id"] == camera_id), None)
        assert camera is not None
        assert camera["status"] == "online"

        # Update the camera to offline
        update_data = {"status": "offline"}
        response = await client.patch(f"/api/cameras/{camera_id}", json=update_data)
        assert response.status_code == 200

        # Verify list shows updated status (proves cache was invalidated)
        list_response = await client.get("/api/cameras")
        assert list_response.status_code == 200
        camera = next((c for c in list_response.json()["items"] if c["id"] == camera_id), None)
        assert camera is not None
        assert camera["status"] == "offline"

    @pytest.mark.asyncio
    async def test_update_then_delete_reflects_in_list(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that updating then deleting cameras reflects correctly in list.

        This test verifies cache consistency across update and delete operations.
        """
        # Create camera
        unique_id = _unique_id("cam")
        create_data = {
            "name": f"Update Delete Camera {unique_id}",
            "folder_path": f"/export/foscam/update_delete_{unique_id}",
            "status": "online",
        }

        response = await client.post("/api/cameras", json=create_data)
        assert response.status_code == 201
        camera_id = response.json()["id"]
        original_name = create_data["name"]

        # Update camera name
        new_name = f"Updated Camera {unique_id}"
        update_data = {"name": new_name}
        response = await client.patch(f"/api/cameras/{camera_id}", json=update_data)
        assert response.status_code == 200

        # Verify list shows updated name (proves cache was invalidated)
        list_response = await client.get("/api/cameras")
        assert list_response.status_code == 200
        camera = next((c for c in list_response.json()["items"] if c["id"] == camera_id), None)
        assert camera is not None
        assert camera["name"] == new_name
        assert camera["name"] != original_name

        # Delete camera
        response = await client.delete(f"/api/cameras/{camera_id}")
        assert response.status_code == 204

        # Verify camera no longer in list (proves cache was invalidated)
        list_response = await client.get("/api/cameras")
        assert list_response.status_code == 200
        camera_ids = {c["id"] for c in list_response.json()["items"]}
        assert camera_id not in camera_ids

    @pytest.mark.asyncio
    async def test_multiple_creates_all_appear_in_list(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that multiple camera creations all appear in subsequent list.

        This verifies cache invalidation occurs for each create operation
        by checking that all created cameras appear in the list response.
        """
        created_camera_ids = []

        # Create multiple cameras
        for i in range(3):
            unique_id = _unique_id(f"cam{i}")
            camera_data = {
                "name": f"Multi Camera {i} {unique_id}",
                "folder_path": f"/export/foscam/multi_{i}_{unique_id}",
                "status": "online",
            }

            response = await client.post("/api/cameras", json=camera_data)
            assert response.status_code == 201
            created_camera_ids.append(response.json()["id"])

        # Verify ALL created cameras appear in the list
        # (proves cache was invalidated after each create)
        list_response = await client.get("/api/cameras")
        assert list_response.status_code == 200
        listed_camera_ids = {c["id"] for c in list_response.json()["items"]}

        for camera_id in created_camera_ids:
            assert camera_id in listed_camera_ids, (
                f"Camera {camera_id} not found in list. "
                "Cache may not have been invalidated properly."
            )
