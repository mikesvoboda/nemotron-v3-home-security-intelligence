"""Test to verify database cleanup and isolation between integration tests.

This test validates that:
1. Database cleanup works properly between tests
2. No savepoint errors occur
3. No unique constraint violations occur from leftover data
4. Foreign key constraints are properly handled during cleanup

Related: Flaky integration test investigation
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from backend.models.camera import Camera
from backend.models.event import Event


@pytest.mark.integration
class TestDatabaseCleanupIsolation:
    """Test database cleanup and isolation between tests."""

    @pytest.mark.asyncio
    async def test_first_camera_creation(self, db_session) -> None:
        """Create a camera with a fixed ID - should succeed."""
        camera_id = "test_cleanup_camera_fixed"
        camera = Camera(
            id=camera_id,
            name="Test Cleanup Camera",
            folder_path=f"/test/cleanup/{camera_id}",
            status="online",
        )
        db_session.add(camera)
        await db_session.flush()

        # Verify it was created
        result = await db_session.execute(select(Camera).where(Camera.id == camera_id))
        found = result.scalar_one_or_none()
        assert found is not None
        assert found.id == camera_id

    @pytest.mark.asyncio
    async def test_second_camera_creation_same_id(self, db_session) -> None:
        """Create a camera with the same fixed ID - should succeed if cleanup worked.

        If cleanup didn't work, this will fail with:
        - duplicate key value violates unique constraint
        """
        camera_id = "test_cleanup_camera_fixed"
        camera = Camera(
            id=camera_id,
            name="Test Cleanup Camera",
            folder_path=f"/test/cleanup/{camera_id}",
            status="online",
        )
        db_session.add(camera)
        await db_session.flush()

        # Verify it was created
        result = await db_session.execute(select(Camera).where(Camera.id == camera_id))
        found = result.scalar_one_or_none()
        assert found is not None
        assert found.id == camera_id

    @pytest.mark.asyncio
    async def test_event_with_camera_foreign_key(self, db_session) -> None:
        """Create an event with a camera FK - verify cleanup doesn't violate FK constraints."""
        camera_id = f"test_fk_camera_{uuid.uuid4().hex[:8]}"

        # Create camera
        camera = Camera(
            id=camera_id,
            name="Test FK Camera",
            folder_path=f"/test/fk/{camera_id}",
            status="online",
        )
        db_session.add(camera)
        await db_session.flush()

        # Create event referencing camera
        event = Event(
            batch_id=str(uuid.uuid4()),
            camera_id=camera_id,
            risk_score=50,
            summary="Test event for FK",
        )
        db_session.add(event)
        await db_session.flush()

        # Verify event was created
        result = await db_session.execute(select(Event).where(Event.camera_id == camera_id))
        found = result.scalar_one_or_none()
        assert found is not None
        assert found.camera_id == camera_id

    @pytest.mark.asyncio
    async def test_no_leftover_data_from_previous_tests(self, db_session) -> None:
        """Verify no data from previous tests remains in the database.

        This test checks that cleanup is working by verifying we start fresh.
        If cleanup failed, we'd see leftover cameras/events from previous tests.
        """
        # Check no cameras exist from previous tests
        result = await db_session.execute(select(Camera))
        cameras = result.scalars().all()

        # Should be empty at start of test (clean_tables fixture)
        # If not empty, cleanup didn't work
        assert len(cameras) == 0, f"Found {len(cameras)} leftover cameras from previous tests"

        # Check no events exist from previous tests
        result = await db_session.execute(select(Event))
        events = result.scalars().all()
        assert len(events) == 0, f"Found {len(events)} leftover events from previous tests"

    @pytest.mark.asyncio
    async def test_session_not_in_invalid_savepoint_state(self, db_session) -> None:
        """Verify the session is not in an invalid savepoint state.

        If there are leftover savepoints or transaction issues, operations will fail.
        """
        from sqlalchemy import text

        # This should work without "savepoint does not exist" errors
        camera_id = f"test_savepoint_camera_{uuid.uuid4().hex[:8]}"
        camera = Camera(
            id=camera_id,
            name="Test Savepoint Camera",
            folder_path=f"/test/savepoint/{camera_id}",
            status="online",
        )
        db_session.add(camera)

        # Flush should work without savepoint errors
        await db_session.flush()

        # Verify we can execute raw SQL without issues
        result = await db_session.execute(text("SELECT 1"))
        assert result.scalar() == 1

    @pytest.mark.asyncio
    async def test_multiple_flushes_no_savepoint_errors(self, db_session) -> None:
        """Test multiple flushes don't cause savepoint errors."""
        # Create camera
        camera_id = f"test_multi_flush_{uuid.uuid4().hex[:8]}"
        camera = Camera(
            id=camera_id,
            name="Test Multi Flush Camera",
            folder_path=f"/test/multiflush/{camera_id}",
            status="online",
        )
        db_session.add(camera)
        await db_session.flush()  # First flush

        # Create event
        event = Event(
            batch_id=str(uuid.uuid4()),
            camera_id=camera_id,
            risk_score=75,
            summary="Test multi-flush event",
        )
        db_session.add(event)
        await db_session.flush()  # Second flush

        # Verify both exist
        camera_result = await db_session.execute(select(Camera).where(Camera.id == camera_id))
        assert camera_result.scalar_one_or_none() is not None

        event_result = await db_session.execute(select(Event).where(Event.camera_id == camera_id))
        assert event_result.scalar_one_or_none() is not None
