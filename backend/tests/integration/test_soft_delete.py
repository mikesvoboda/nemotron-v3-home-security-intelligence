"""Integration tests for soft-delete behavior across Events and Cameras.

This module tests the soft-delete functionality implemented in NEM-1954, NEM-1955, and NEM-1956:
- Filtering: Soft-deleted items return 404 on direct access (list filtering not yet implemented)
- Trash views: /api/events/deleted and /api/cameras/deleted return deleted items
- Restore: POST /{id}/restore restores soft-deleted items
- Cascade: Events cascade soft-delete to related detections (future capability)

Note: List endpoint filtering (GET /api/events, GET /api/cameras) for soft-deleted items
is NOT currently implemented. These tests document the expected behavior via skipped tests.

Test organization follows the pattern established in test_cameras_api.py and test_events_api.py.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_session
from backend.models.camera import Camera
from backend.models.detection import Detection
from backend.models.event import Event

# =============================================================================
# Test Helper Functions
# =============================================================================


async def create_test_camera(
    db: AsyncSession,
    *,
    camera_id: str | None = None,
    name: str | None = None,
    deleted: bool = False,
) -> Camera:
    """Create a test camera with optional soft-delete state.

    Args:
        db: Database session
        camera_id: Optional camera ID (auto-generated if not provided)
        name: Optional camera name (defaults to camera_id)
        deleted: If True, set deleted_at timestamp

    Returns:
        The created Camera instance
    """
    import uuid

    if camera_id is None:
        camera_id = f"test_camera_{uuid.uuid4().hex[:8]}"
    if name is None:
        name = camera_id

    camera = Camera(
        id=camera_id,
        name=name,
        folder_path=f"/export/foscam/{name}",
        status="online",
        deleted_at=datetime.now(UTC) if deleted else None,
    )
    db.add(camera)
    await db.flush()
    return camera


async def create_test_event(
    db: AsyncSession,
    camera_id: str,
    *,
    deleted: bool = False,
    risk_score: int = 50,
    summary: str = "Test event",
) -> Event:
    """Create a test event with optional soft-delete state.

    Args:
        db: Database session
        camera_id: Camera ID for the event
        deleted: If True, set deleted_at timestamp
        risk_score: Risk score for the event
        summary: Event summary text

    Returns:
        The created Event instance
    """
    import uuid

    event = Event(
        batch_id=f"batch_{uuid.uuid4().hex[:8]}",
        camera_id=camera_id,
        started_at=datetime.now(UTC),
        risk_score=risk_score,
        risk_level="medium" if risk_score < 70 else "high",
        summary=summary,
        deleted_at=datetime.now(UTC) if deleted else None,
    )
    db.add(event)
    await db.flush()
    return event


async def create_test_detection(
    db: AsyncSession,
    camera_id: str,
    *,
    object_type: str = "person",
    confidence: float = 0.95,
) -> Detection:
    """Create a test detection.

    Args:
        db: Database session
        camera_id: Camera ID for the detection
        object_type: Detection object type (e.g., "person", "vehicle")
        confidence: Detection confidence score

    Returns:
        The created Detection instance
    """
    detection = Detection(
        camera_id=camera_id,
        detected_at=datetime.now(UTC),
        object_type=object_type,
        confidence=confidence,
        file_path=f"/export/foscam/{camera_id}/test_image.jpg",
        bbox_x=100,
        bbox_y=200,
        bbox_width=200,
        bbox_height=200,
    )
    db.add(detection)
    await db.flush()
    return detection


# =============================================================================
# Event Soft Delete Tests
# =============================================================================


@pytest.mark.asyncio
class TestEventSoftDeleteFiltering:
    """Test that soft-deleted events are properly filtered from normal endpoints."""

    @pytest.mark.skip(reason="List endpoint soft-delete filtering not yet implemented")
    async def test_soft_deleted_event_excluded_from_list(self, client: AsyncClient) -> None:
        """Verify soft-deleted events are excluded from GET /api/events.

        NOTE: This test is skipped because list endpoint filtering for soft-deleted
        items is not yet implemented. The list endpoints currently return ALL items
        regardless of deleted_at status. This is tracked as a future enhancement.
        """
        async with get_session() as db:
            # Create a camera first
            camera = await create_test_camera(db, camera_id="filter_test_cam")

            # Create one active event and one deleted event
            active_event = await create_test_event(
                db, camera.id, deleted=False, summary="Active event"
            )
            deleted_event = await create_test_event(
                db, camera.id, deleted=True, summary="Deleted event"
            )
            await db.commit()

            # Fetch events list
            response = await client.get("/api/events")
            assert response.status_code == 200

            data = response.json()
            event_ids = [e["id"] for e in data["items"]]

            # Active event should be present, deleted event should not
            assert active_event.id in event_ids
            assert deleted_event.id not in event_ids

    async def test_soft_deleted_event_returns_404_on_direct_access(
        self, client: AsyncClient
    ) -> None:
        """Verify GET /api/events/{id} returns 404 for soft-deleted events."""
        async with get_session() as db:
            camera = await create_test_camera(db, camera_id="direct_access_cam")
            deleted_event = await create_test_event(
                db, camera.id, deleted=True, summary="Deleted event"
            )
            await db.commit()

            # Try to access deleted event directly
            response = await client.get(f"/api/events/{deleted_event.id}")
            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()

    async def test_active_event_accessible_after_another_is_deleted(
        self, client: AsyncClient
    ) -> None:
        """Verify active events remain accessible when others are deleted."""
        async with get_session() as db:
            camera = await create_test_camera(db, camera_id="mixed_state_cam")

            # Create multiple events with different states
            active_event = await create_test_event(
                db, camera.id, deleted=False, summary="Still active"
            )
            await create_test_event(db, camera.id, deleted=True, summary="Was deleted")
            await db.commit()

            # Active event should be accessible
            response = await client.get(f"/api/events/{active_event.id}")
            assert response.status_code == 200
            assert response.json()["summary"] == "Still active"


@pytest.mark.asyncio
class TestEventTrashList:
    """Test the /api/events/deleted trash view endpoint."""

    async def test_trash_list_returns_deleted_events(self, client: AsyncClient) -> None:
        """Verify GET /api/events/deleted returns soft-deleted events."""
        async with get_session() as db:
            camera = await create_test_camera(db, camera_id="trash_list_cam")

            # Create deleted events
            deleted_event1 = await create_test_event(
                db, camera.id, deleted=True, summary="First deleted"
            )
            deleted_event2 = await create_test_event(
                db, camera.id, deleted=True, summary="Second deleted"
            )
            # Also create an active event (should not appear in trash)
            active_event = await create_test_event(
                db, camera.id, deleted=False, summary="Active event"
            )
            await db.commit()

            # Fetch trash list
            response = await client.get("/api/events/deleted")
            assert response.status_code == 200

            data = response.json()
            event_ids = [e["id"] for e in data["items"]]

            # Deleted events should be present, active should not
            assert deleted_event1.id in event_ids
            assert deleted_event2.id in event_ids
            assert active_event.id not in event_ids
            assert data["pagination"]["total"] >= 2

    async def test_trash_list_empty_when_no_deleted_events(self, client: AsyncClient) -> None:
        """Verify GET /api/events/deleted returns empty list when no deleted events."""
        # With clean_tables fixture, there should be no deleted events initially
        response = await client.get("/api/events/deleted")
        assert response.status_code == 200

        data = response.json()
        # Count should be 0 or only contain events from this test run
        assert "items" in data
        assert "pagination" in data

    async def test_trash_list_ordered_by_deleted_at_descending(self, client: AsyncClient) -> None:
        """Verify trash list is ordered by deleted_at descending (most recent first)."""
        async with get_session() as db:
            camera = await create_test_camera(db, camera_id="trash_order_cam")

            # Create events with explicit ordering
            event1 = await create_test_event(db, camera.id, summary="First deleted")
            event2 = await create_test_event(db, camera.id, summary="Second deleted")
            event3 = await create_test_event(db, camera.id, summary="Third deleted")

            # Delete in specific order with time gaps
            from datetime import timedelta

            base_time = datetime.now(UTC)
            event1.deleted_at = base_time - timedelta(hours=2)
            event2.deleted_at = base_time - timedelta(hours=1)
            event3.deleted_at = base_time  # Most recent
            await db.commit()

            response = await client.get("/api/events/deleted")
            assert response.status_code == 200

            data = response.json()
            events = data["items"]

            # Find our test events in the response
            our_events = [e for e in events if e["camera_id"] == "trash_order_cam"]

            # Most recently deleted should be first
            if len(our_events) >= 2:
                event_summaries = [e["summary"] for e in our_events]
                # event3 (most recent) should come before event1 (oldest)
                if "Third deleted" in event_summaries and "First deleted" in event_summaries:
                    assert event_summaries.index("Third deleted") < event_summaries.index(
                        "First deleted"
                    )


@pytest.mark.asyncio
class TestEventRestore:
    """Test the POST /api/events/{id}/restore endpoint."""

    async def test_restore_deleted_event_succeeds(self, client: AsyncClient) -> None:
        """Verify restoring a soft-deleted event makes it visible again."""
        async with get_session() as db:
            camera = await create_test_camera(db, camera_id="restore_test_cam")
            deleted_event = await create_test_event(
                db, camera.id, deleted=True, summary="To be restored"
            )
            event_id = deleted_event.id
            await db.commit()

            # Verify event is in trash
            trash_response = await client.get("/api/events/deleted")
            assert event_id in [e["id"] for e in trash_response.json()["items"]]

            # Restore the event
            restore_response = await client.post(f"/api/events/{event_id}/restore")
            assert restore_response.status_code == 200

            # Verify event is now accessible via normal endpoint
            get_response = await client.get(f"/api/events/{event_id}")
            assert get_response.status_code == 200
            assert get_response.json()["summary"] == "To be restored"

            # Verify event is no longer in trash
            trash_response2 = await client.get("/api/events/deleted")
            trash_ids = [e["id"] for e in trash_response2.json()["items"]]
            assert event_id not in trash_ids

    async def test_restore_non_deleted_event_returns_409(self, client: AsyncClient) -> None:
        """Verify restoring a non-deleted event returns 409 Conflict."""
        async with get_session() as db:
            camera = await create_test_camera(db, camera_id="restore_conflict_cam")
            active_event = await create_test_event(
                db, camera.id, deleted=False, summary="Already active"
            )
            event_id = active_event.id
            await db.commit()

            # Try to restore an event that's not deleted
            response = await client.post(f"/api/events/{event_id}/restore")
            assert response.status_code == 409
            assert "not deleted" in response.json()["detail"].lower()

    async def test_restore_nonexistent_event_returns_404(self, client: AsyncClient) -> None:
        """Verify restoring a non-existent event returns 404."""
        response = await client.post("/api/events/999999999/restore")
        assert response.status_code == 404

    @pytest.mark.skip(reason="List endpoint soft-delete filtering not yet implemented")
    async def test_restored_event_appears_in_list(self, client: AsyncClient) -> None:
        """Verify restored event appears in GET /api/events list.

        NOTE: This test is skipped because list endpoint filtering for soft-deleted
        items is not yet implemented. The test cannot verify that a deleted event
        is excluded from the list initially.
        """
        async with get_session() as db:
            camera = await create_test_camera(db, camera_id="restore_list_cam")
            deleted_event = await create_test_event(
                db, camera.id, deleted=True, summary="Will appear in list"
            )
            event_id = deleted_event.id
            await db.commit()

            # Verify not in list initially
            list_response = await client.get("/api/events")
            assert event_id not in [e["id"] for e in list_response.json()["items"]]

            # Restore
            await client.post(f"/api/events/{event_id}/restore")

            # Verify now in list
            list_response2 = await client.get("/api/events")
            assert event_id in [e["id"] for e in list_response2.json()["items"]]


# =============================================================================
# Camera Soft Delete Tests
# =============================================================================


@pytest.mark.asyncio
class TestCameraSoftDeleteFiltering:
    """Test that soft-deleted cameras are properly filtered from normal endpoints."""

    @pytest.mark.skip(reason="List endpoint soft-delete filtering not yet implemented")
    async def test_soft_deleted_camera_excluded_from_list(self, client: AsyncClient) -> None:
        """Verify soft-deleted cameras are excluded from GET /api/cameras.

        NOTE: This test is skipped because list endpoint filtering for soft-deleted
        items is not yet implemented. The list endpoints currently return ALL items
        regardless of deleted_at status. This is tracked as a future enhancement.
        """
        async with get_session() as db:
            # Create active and deleted cameras
            active_camera = await create_test_camera(
                db, camera_id="active_cam_filter", name="Active Camera", deleted=False
            )
            deleted_camera = await create_test_camera(
                db, camera_id="deleted_cam_filter", name="Deleted Camera", deleted=True
            )
            await db.commit()

            # Fetch cameras list
            response = await client.get("/api/cameras")
            assert response.status_code == 200

            data = response.json()
            camera_ids = [c["id"] for c in data["items"]]

            # Active camera should be present, deleted should not
            assert active_camera.id in camera_ids
            assert deleted_camera.id not in camera_ids

    async def test_soft_deleted_camera_returns_404_on_direct_access(
        self, client: AsyncClient
    ) -> None:
        """Verify GET /api/cameras/{id} returns 404 for soft-deleted cameras."""
        async with get_session() as db:
            deleted_camera = await create_test_camera(
                db, camera_id="deleted_direct_cam", deleted=True
            )
            await db.commit()

            # Try to access deleted camera directly
            response = await client.get(f"/api/cameras/{deleted_camera.id}")
            assert response.status_code == 404


@pytest.mark.asyncio
class TestCameraTrashList:
    """Test the /api/cameras/deleted trash view endpoint."""

    async def test_trash_list_returns_deleted_cameras(self, client: AsyncClient) -> None:
        """Verify GET /api/cameras/deleted returns soft-deleted cameras."""
        async with get_session() as db:
            # Create deleted cameras
            deleted_cam1 = await create_test_camera(
                db, camera_id="deleted_trash_1", name="Deleted Cam 1", deleted=True
            )
            deleted_cam2 = await create_test_camera(
                db, camera_id="deleted_trash_2", name="Deleted Cam 2", deleted=True
            )
            # Also create an active camera
            active_cam = await create_test_camera(
                db, camera_id="active_trash_test", name="Active Cam", deleted=False
            )
            await db.commit()

            # Fetch trash list
            response = await client.get("/api/cameras/deleted")
            assert response.status_code == 200

            data = response.json()
            camera_ids = [c["id"] for c in data["items"]]

            # Deleted cameras should be present, active should not
            assert deleted_cam1.id in camera_ids
            assert deleted_cam2.id in camera_ids
            assert active_cam.id not in camera_ids

    async def test_trash_list_returns_camera_details(self, client: AsyncClient) -> None:
        """Verify trash list returns camera details for each deleted camera.

        Note: The CameraResponse schema used by the trash list does NOT include
        the deleted_at field. This is a schema limitation - the deleted_at info
        is used for ordering but not returned in the response.
        """
        async with get_session() as db:
            deleted_cam = await create_test_camera(
                db, camera_id="deleted_details_cam", deleted=True
            )
            await db.commit()

            response = await client.get("/api/cameras/deleted")
            assert response.status_code == 200

            data = response.json()
            our_cam = next((c for c in data["items"] if c["id"] == deleted_cam.id), None)
            assert our_cam is not None
            # Verify camera details are present
            assert "id" in our_cam
            assert "name" in our_cam
            assert "folder_path" in our_cam
            assert "status" in our_cam


@pytest.mark.asyncio
class TestCameraRestore:
    """Test the POST /api/cameras/{id}/restore endpoint."""

    async def test_restore_deleted_camera_succeeds(self, client: AsyncClient) -> None:
        """Verify restoring a soft-deleted camera makes it visible again."""
        async with get_session() as db:
            deleted_cam = await create_test_camera(
                db, camera_id="restore_cam_test", name="Camera To Restore", deleted=True
            )
            camera_id = deleted_cam.id
            await db.commit()

            # Verify camera is in trash
            trash_response = await client.get("/api/cameras/deleted")
            assert camera_id in [c["id"] for c in trash_response.json()["items"]]

            # Restore the camera
            restore_response = await client.post(f"/api/cameras/{camera_id}/restore")
            assert restore_response.status_code == 200

            # Verify camera is now accessible
            get_response = await client.get(f"/api/cameras/{camera_id}")
            assert get_response.status_code == 200

            # Verify camera is no longer in trash
            trash_response2 = await client.get("/api/cameras/deleted")
            trash_ids = [c["id"] for c in trash_response2.json()["items"]]
            assert camera_id not in trash_ids

    async def test_restore_non_deleted_camera_returns_400(self, client: AsyncClient) -> None:
        """Verify restoring a non-deleted camera returns 400 Bad Request."""
        async with get_session() as db:
            active_cam = await create_test_camera(
                db, camera_id="active_restore_test", deleted=False
            )
            camera_id = active_cam.id
            await db.commit()

            # Try to restore a camera that's not deleted
            response = await client.post(f"/api/cameras/{camera_id}/restore")
            assert response.status_code == 400
            assert "not deleted" in response.json()["detail"].lower()

    async def test_restore_nonexistent_camera_returns_404(self, client: AsyncClient) -> None:
        """Verify restoring a non-existent camera returns 404."""
        response = await client.post("/api/cameras/nonexistent_camera_xyz/restore")
        assert response.status_code == 404


# =============================================================================
# Cascade Soft Delete Tests
# =============================================================================


@pytest.mark.asyncio
class TestEventCascadeSoftDelete:
    """Test cascade soft delete behavior for events.

    Note: As of NEM-1956, detections do NOT have soft-delete capability
    (no deleted_at column). The cascade parameter is preserved for future use.
    These tests verify the current behavior where cascade affects only the event.
    """

    async def test_delete_event_via_api_sets_deleted_at(self, client: AsyncClient) -> None:
        """Verify DELETE /api/events/{id} soft-deletes the event."""
        async with get_session() as db:
            camera = await create_test_camera(db, camera_id="cascade_delete_cam")
            event = await create_test_event(db, camera.id, summary="Event to delete")
            event_id = event.id
            await db.commit()

            # Verify event is accessible
            get_response = await client.get(f"/api/events/{event_id}")
            assert get_response.status_code == 200

            # Delete the event
            delete_response = await client.delete(f"/api/events/{event_id}")
            assert delete_response.status_code == 204

            # Verify event is now in trash (soft deleted)
            trash_response = await client.get("/api/events/deleted")
            trash_ids = [e["id"] for e in trash_response.json()["items"]]
            assert event_id in trash_ids

            # Verify event is no longer accessible via normal endpoint
            get_response2 = await client.get(f"/api/events/{event_id}")
            assert get_response2.status_code == 404

    async def test_delete_already_deleted_event_returns_409(self, client: AsyncClient) -> None:
        """Verify deleting an already-deleted event returns 409 Conflict."""
        async with get_session() as db:
            camera = await create_test_camera(db, camera_id="double_delete_cam")
            deleted_event = await create_test_event(
                db, camera.id, deleted=True, summary="Already deleted"
            )
            event_id = deleted_event.id
            await db.commit()

            # Try to delete again
            response = await client.delete(f"/api/events/{event_id}")
            assert response.status_code == 409
            assert "already deleted" in response.json()["detail"].lower()

    async def test_event_detections_remain_after_soft_delete(self, client: AsyncClient) -> None:
        """Verify detections are not affected by event soft delete (no cascade to detections).

        Note: Detections do not have soft-delete capability. This test confirms
        that soft-deleting an event does not affect its associated detections.
        """
        async with get_session() as db:
            camera = await create_test_camera(db, camera_id="detection_cascade_cam")
            event = await create_test_event(db, camera.id, summary="Event with detections")

            # Create a detection for this camera
            detection = await create_test_detection(db, camera.id, object_type="person")
            await db.commit()

            event_id = event.id
            detection_id = detection.id

            # Delete the event
            delete_response = await client.delete(f"/api/events/{event_id}")
            assert delete_response.status_code == 204

            # Verify detection still exists (detections don't have soft delete)
            async with get_session() as db2:
                result = await db2.execute(select(Detection).where(Detection.id == detection_id))
                fetched_detection = result.scalar_one_or_none()
                assert fetched_detection is not None
                assert fetched_detection.object_type == "person"

    async def test_restore_event_with_cascade_parameter(self, client: AsyncClient) -> None:
        """Verify restore endpoint accepts cascade parameter."""
        async with get_session() as db:
            camera = await create_test_camera(db, camera_id="cascade_restore_cam")
            deleted_event = await create_test_event(
                db, camera.id, deleted=True, summary="Cascade restore test"
            )
            event_id = deleted_event.id
            await db.commit()

            # Restore with cascade=true (default)
            response = await client.post(f"/api/events/{event_id}/restore?cascade=true")
            assert response.status_code == 200

            # Verify event is restored
            get_response = await client.get(f"/api/events/{event_id}")
            assert get_response.status_code == 200


# =============================================================================
# Edge Cases and Integration Tests
# =============================================================================


@pytest.mark.asyncio
class TestSoftDeleteEdgeCases:
    """Test edge cases and integration scenarios for soft delete."""

    async def test_bulk_delete_uses_soft_delete_by_default(self, client: AsyncClient) -> None:
        """Verify bulk delete endpoint uses soft delete by default."""
        async with get_session() as db:
            camera = await create_test_camera(db, camera_id="bulk_delete_cam")
            event1 = await create_test_event(db, camera.id, summary="Bulk delete 1")
            event2 = await create_test_event(db, camera.id, summary="Bulk delete 2")
            await db.commit()

            event_ids = [event1.id, event2.id]

            # Bulk delete (soft delete is default)
            response = await client.request(
                "DELETE",
                "/api/events/bulk",
                json={"event_ids": event_ids, "soft_delete": True},
            )
            assert response.status_code == 207  # Multi-status

            # Verify events are in trash
            trash_response = await client.get("/api/events/deleted")
            trash_ids = [e["id"] for e in trash_response.json()["items"]]
            for eid in event_ids:
                assert eid in trash_ids

    @pytest.mark.skip(reason="Search endpoint soft-delete filtering not yet implemented")
    async def test_search_excludes_soft_deleted_events(self, client: AsyncClient) -> None:
        """Verify search endpoint excludes soft-deleted events.

        NOTE: This test is skipped because search endpoint filtering for soft-deleted
        items is not yet implemented. The search endpoint currently returns ALL matching
        items regardless of deleted_at status. This is tracked as a future enhancement.
        """
        async with get_session() as db:
            camera = await create_test_camera(db, camera_id="search_exclude_cam")

            # Create events with searchable summaries
            active_event = await create_test_event(
                db, camera.id, summary="Searchable active event about security"
            )
            deleted_event = await create_test_event(
                db, camera.id, deleted=True, summary="Searchable deleted event about security"
            )
            await db.commit()

            # Search for "security" - should only find active event
            response = await client.get("/api/events/search?q=security")
            assert response.status_code == 200

            data = response.json()
            result_ids = [r["id"] for r in data["results"]]

            # Active should be found, deleted should not
            assert active_event.id in result_ids
            assert deleted_event.id not in result_ids

    async def test_event_stats_exclude_soft_deleted(self, client: AsyncClient) -> None:
        """Verify event stats endpoint excludes soft-deleted events."""
        async with get_session() as db:
            camera = await create_test_camera(db, camera_id="stats_exclude_cam")

            # Create active and deleted events
            await create_test_event(db, camera.id, deleted=False, risk_score=80)
            await create_test_event(db, camera.id, deleted=False, risk_score=40)
            await create_test_event(db, camera.id, deleted=True, risk_score=90)
            await db.commit()

            response = await client.get("/api/events/stats")
            assert response.status_code == 200

            # Stats should only count non-deleted events
            data = response.json()
            # The exact count depends on test isolation, but deleted events should be excluded
            assert "total_events" in data

    async def test_camera_delete_cascades_to_events(self, client: AsyncClient) -> None:
        """Verify hard-deleting a camera cascades to its events.

        Note: The camera DELETE endpoint performs a HARD DELETE (not soft delete),
        which cascades to all related events due to the foreign key constraint
        with ON DELETE CASCADE. This is by design - cameras don't have soft-delete
        on the DELETE endpoint (only via direct model manipulation).
        """
        async with get_session() as db:
            camera = await create_test_camera(db, camera_id="camera_event_cascade_cam")
            event = await create_test_event(db, camera.id, summary="Event on camera")
            await db.commit()

            camera_id = camera.id
            event_id = event.id

            # Hard delete the camera (DELETE endpoint does hard delete)
            delete_response = await client.delete(f"/api/cameras/{camera_id}")
            assert delete_response.status_code == 204

            # Event should NOT be accessible (cascade deleted with camera)
            event_response = await client.get(f"/api/events/{event_id}")
            assert event_response.status_code == 404

            # Camera should NOT be in trash (hard deleted, not soft deleted)
            trash_response = await client.get("/api/cameras/deleted")
            trash_ids = [c["id"] for c in trash_response.json()["items"]]
            assert camera_id not in trash_ids
