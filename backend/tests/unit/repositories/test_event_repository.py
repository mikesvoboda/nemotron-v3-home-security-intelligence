"""Unit tests for EventRepository.

Tests follow TDD approach - these tests are written BEFORE the implementation.
Run with: uv run pytest backend/tests/unit/repositories/test_event_repository.py -v
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from backend.models import Camera, Event
from backend.repositories.event_repository import EventRepository
from backend.tests.conftest import unique_id


async def create_test_camera(session, camera_id: str | None = None) -> Camera:
    """Helper to create a test camera."""
    if camera_id is None:
        camera_id = unique_id("camera")
    camera = Camera(
        id=camera_id,
        name=f"Test Camera {camera_id}",
        folder_path=f"/export/foscam/{camera_id}",
    )
    session.add(camera)
    await session.flush()
    return camera


class TestEventRepositoryBasicCRUD:
    """Test basic CRUD operations inherited from Repository base class."""

    @pytest.mark.asyncio
    async def test_create_event(self, test_db):
        """Test creating a new event."""
        async with test_db() as session:
            camera = await create_test_camera(session)
            repo = EventRepository(session)

            event = Event(
                batch_id=unique_id("batch"),
                camera_id=camera.id,
                started_at=datetime.now(UTC),
                risk_score=50,
                risk_level="medium",
                summary="Test event",
            )

            created = await repo.create(event)

            assert created.id is not None
            assert created.camera_id == camera.id
            assert created.risk_score == 50
            assert created.risk_level == "medium"

    @pytest.mark.asyncio
    async def test_get_by_id_existing(self, test_db):
        """Test retrieving an existing event by ID."""
        async with test_db() as session:
            camera = await create_test_camera(session)
            repo = EventRepository(session)

            event = Event(
                batch_id=unique_id("batch"),
                camera_id=camera.id,
                started_at=datetime.now(UTC),
                summary="Test event",
            )
            await repo.create(event)

            retrieved = await repo.get_by_id(event.id)

            assert retrieved is not None
            assert retrieved.id == event.id
            assert retrieved.summary == "Test event"

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, test_db):
        """Test retrieving a non-existent event returns None."""
        async with test_db() as session:
            repo = EventRepository(session)

            result = await repo.get_by_id(999999)

            assert result is None

    @pytest.mark.asyncio
    async def test_update_event(self, test_db):
        """Test updating an event's properties."""
        async with test_db() as session:
            camera = await create_test_camera(session)
            repo = EventRepository(session)

            event = Event(
                batch_id=unique_id("batch"),
                camera_id=camera.id,
                started_at=datetime.now(UTC),
                risk_score=30,
                risk_level="low",
            )
            await repo.create(event)

            event.risk_score = 75
            event.risk_level = "high"
            updated = await repo.update(event)

            assert updated.risk_score == 75
            assert updated.risk_level == "high"

    @pytest.mark.asyncio
    async def test_delete_event(self, test_db):
        """Test deleting an event."""
        async with test_db() as session:
            camera = await create_test_camera(session)
            repo = EventRepository(session)

            event = Event(
                batch_id=unique_id("batch"),
                camera_id=camera.id,
                started_at=datetime.now(UTC),
            )
            await repo.create(event)
            event_id = event.id

            await repo.delete(event)

            result = await repo.get_by_id(event_id)
            assert result is None

    @pytest.mark.asyncio
    async def test_exists(self, test_db):
        """Test checking if an event exists."""
        async with test_db() as session:
            camera = await create_test_camera(session)
            repo = EventRepository(session)

            event = Event(
                batch_id=unique_id("batch"),
                camera_id=camera.id,
                started_at=datetime.now(UTC),
            )
            await repo.create(event)

            assert await repo.exists(event.id) is True
            assert await repo.exists(999999) is False

    @pytest.mark.asyncio
    async def test_count(self, test_db):
        """Test counting events."""
        async with test_db() as session:
            camera = await create_test_camera(session)
            repo = EventRepository(session)

            initial_count = await repo.count()

            for i in range(3):
                event = Event(
                    batch_id=unique_id(f"batch{i}"),
                    camera_id=camera.id,
                    started_at=datetime.now(UTC),
                )
                await repo.create(event)

            new_count = await repo.count()
            assert new_count == initial_count + 3


class TestEventRepositorySpecificMethods:
    """Test event-specific repository methods."""

    @pytest.mark.asyncio
    async def test_get_by_camera_id(self, test_db):
        """Test getting events for a specific camera."""
        async with test_db() as session:
            camera1 = await create_test_camera(session)
            camera2 = await create_test_camera(session)
            repo = EventRepository(session)

            event1 = Event(
                batch_id=unique_id("batch1"),
                camera_id=camera1.id,
                started_at=datetime.now(UTC),
            )
            event2 = Event(
                batch_id=unique_id("batch2"),
                camera_id=camera1.id,
                started_at=datetime.now(UTC),
            )
            event3 = Event(
                batch_id=unique_id("batch3"),
                camera_id=camera2.id,
                started_at=datetime.now(UTC),
            )
            await repo.create(event1)
            await repo.create(event2)
            await repo.create(event3)

            # Get events for camera1 only
            camera1_events = await repo.get_by_camera_id(camera1.id)

            event_ids = [e.id for e in camera1_events]
            assert event1.id in event_ids
            assert event2.id in event_ids
            assert event3.id not in event_ids

    @pytest.mark.asyncio
    async def test_get_by_batch_id(self, test_db):
        """Test getting events by batch ID."""
        async with test_db() as session:
            camera = await create_test_camera(session)
            repo = EventRepository(session)
            batch_id = unique_id("batch")

            event = Event(
                batch_id=batch_id,
                camera_id=camera.id,
                started_at=datetime.now(UTC),
            )
            await repo.create(event)

            found = await repo.get_by_batch_id(batch_id)

            assert found is not None
            assert found.batch_id == batch_id

    @pytest.mark.asyncio
    async def test_get_by_batch_id_not_found(self, test_db):
        """Test get_by_batch_id returns None for non-existent batch."""
        async with test_db() as session:
            repo = EventRepository(session)

            result = await repo.get_by_batch_id("nonexistent_batch")

            assert result is None

    @pytest.mark.asyncio
    async def test_get_unreviewed(self, test_db):
        """Test getting events that haven't been reviewed."""
        async with test_db() as session:
            camera = await create_test_camera(session)
            repo = EventRepository(session)

            reviewed = Event(
                batch_id=unique_id("reviewed"),
                camera_id=camera.id,
                started_at=datetime.now(UTC),
                reviewed=True,
            )
            unreviewed = Event(
                batch_id=unique_id("unreviewed"),
                camera_id=camera.id,
                started_at=datetime.now(UTC),
                reviewed=False,
            )
            await repo.create(reviewed)
            await repo.create(unreviewed)

            unreviewed_events = await repo.get_unreviewed()

            event_ids = [e.id for e in unreviewed_events]
            assert unreviewed.id in event_ids
            assert reviewed.id not in event_ids

    @pytest.mark.asyncio
    async def test_get_by_risk_level(self, test_db):
        """Test filtering events by risk level."""
        async with test_db() as session:
            camera = await create_test_camera(session)
            repo = EventRepository(session)

            high = Event(
                batch_id=unique_id("high"),
                camera_id=camera.id,
                started_at=datetime.now(UTC),
                risk_score=85,
                risk_level="high",
            )
            low = Event(
                batch_id=unique_id("low"),
                camera_id=camera.id,
                started_at=datetime.now(UTC),
                risk_score=20,
                risk_level="low",
            )
            await repo.create(high)
            await repo.create(low)

            high_risk_events = await repo.get_by_risk_level("high")

            event_ids = [e.id for e in high_risk_events]
            assert high.id in event_ids
            assert low.id not in event_ids

    @pytest.mark.asyncio
    async def test_get_in_date_range(self, test_db):
        """Test getting events within a date range."""
        async with test_db() as session:
            camera = await create_test_camera(session)
            repo = EventRepository(session)

            now = datetime.now(UTC)
            yesterday = now - timedelta(days=1)
            last_week = now - timedelta(days=7)
            two_weeks_ago = now - timedelta(days=14)

            recent = Event(
                batch_id=unique_id("recent"),
                camera_id=camera.id,
                started_at=yesterday,
            )
            old = Event(
                batch_id=unique_id("old"),
                camera_id=camera.id,
                started_at=two_weeks_ago,
            )
            await repo.create(recent)
            await repo.create(old)

            # Query for last week's events
            events_in_range = await repo.get_in_date_range(last_week, now)

            event_ids = [e.id for e in events_in_range]
            assert recent.id in event_ids
            assert old.id not in event_ids

    @pytest.mark.asyncio
    async def test_get_recent(self, test_db):
        """Test getting most recent events with limit."""
        async with test_db() as session:
            camera = await create_test_camera(session)
            repo = EventRepository(session)

            now = datetime.now(UTC)
            events_data = []
            for i in range(5):
                event = Event(
                    batch_id=unique_id(f"batch{i}"),
                    camera_id=camera.id,
                    started_at=now - timedelta(hours=i),
                )
                await repo.create(event)
                events_data.append(event)

            # Get 3 most recent
            recent = await repo.get_recent(limit=3)

            assert len(recent) == 3
            # Should be in reverse chronological order (most recent first)
            recent_ids = [e.id for e in recent]
            assert events_data[0].id in recent_ids  # Most recent
            assert events_data[1].id in recent_ids
            assert events_data[2].id in recent_ids
            assert events_data[4].id not in recent_ids  # Oldest should not be included

    @pytest.mark.asyncio
    async def test_mark_reviewed(self, test_db):
        """Test marking an event as reviewed with optional notes."""
        async with test_db() as session:
            camera = await create_test_camera(session)
            repo = EventRepository(session)

            event = Event(
                batch_id=unique_id("batch"),
                camera_id=camera.id,
                started_at=datetime.now(UTC),
                reviewed=False,
            )
            await repo.create(event)

            # Mark as reviewed
            updated = await repo.mark_reviewed(event.id, notes="False alarm - neighbor's cat")

            assert updated is not None
            assert updated.reviewed is True
            assert updated.notes == "False alarm - neighbor's cat"

    @pytest.mark.asyncio
    async def test_mark_reviewed_not_found(self, test_db):
        """Test mark_reviewed returns None for non-existent event."""
        async with test_db() as session:
            repo = EventRepository(session)

            result = await repo.mark_reviewed(999999, notes="Test")

            assert result is None

    @pytest.mark.asyncio
    async def test_get_high_risk_events(self, test_db):
        """Test getting events above a risk score threshold."""
        async with test_db() as session:
            camera = await create_test_camera(session)
            repo = EventRepository(session)

            high = Event(
                batch_id=unique_id("high"),
                camera_id=camera.id,
                started_at=datetime.now(UTC),
                risk_score=85,
            )
            medium = Event(
                batch_id=unique_id("medium"),
                camera_id=camera.id,
                started_at=datetime.now(UTC),
                risk_score=50,
            )
            low = Event(
                batch_id=unique_id("low"),
                camera_id=camera.id,
                started_at=datetime.now(UTC),
                risk_score=20,
            )
            await repo.create(high)
            await repo.create(medium)
            await repo.create(low)

            # Get events with risk >= 60
            high_risk = await repo.get_high_risk_events(threshold=60)

            event_ids = [e.id for e in high_risk]
            assert high.id in event_ids
            assert medium.id not in event_ids
            assert low.id not in event_ids

    @pytest.mark.asyncio
    async def test_get_unreviewed_count(self, test_db):
        """Test counting unreviewed events."""
        async with test_db() as session:
            camera = await create_test_camera(session)
            repo = EventRepository(session)

            reviewed = Event(
                batch_id=unique_id("reviewed"),
                camera_id=camera.id,
                started_at=datetime.now(UTC),
                reviewed=True,
            )
            unreviewed1 = Event(
                batch_id=unique_id("unreviewed1"),
                camera_id=camera.id,
                started_at=datetime.now(UTC),
                reviewed=False,
            )
            unreviewed2 = Event(
                batch_id=unique_id("unreviewed2"),
                camera_id=camera.id,
                started_at=datetime.now(UTC),
                reviewed=False,
            )
            await repo.create(reviewed)
            await repo.create(unreviewed1)
            await repo.create(unreviewed2)

            count = await repo.get_unreviewed_count()

            # Should include the 2 unreviewed events (may have more from other tests)
            assert count >= 2
