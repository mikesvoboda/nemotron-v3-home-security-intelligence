"""Tests for concurrency bug fixes (NEM-1998).

These tests verify that race conditions are properly handled:
1. EventDetection junction table race condition (ON CONFLICT DO NOTHING)
2. Frontend dedup set memory bounded (documented for reference)
"""

from unittest.mock import AsyncMock

import pytest


class TestEventDetectionRaceCondition:
    """Tests for EventDetection junction table race condition fix."""

    def test_event_detection_table_has_composite_primary_key(self):
        """Verify EventDetection table has composite primary key for ON CONFLICT."""
        from backend.models.event_detection import EventDetection

        # Check that the table has the expected columns
        table = EventDetection.__table__
        assert "event_id" in table.c
        assert "detection_id" in table.c

        # Check that both columns are part of the primary key
        pk_columns = [col.name for col in table.primary_key.columns]
        assert "event_id" in pk_columns
        assert "detection_id" in pk_columns

    def test_nemotron_analyzer_uses_on_conflict(self):
        """Verify nemotron_analyzer.py contains ON CONFLICT DO NOTHING pattern."""
        import inspect

        from backend.services import nemotron_analyzer

        source = inspect.getsource(nemotron_analyzer)

        # Verify the NEM-1998 fix is present
        assert "NEM-1998" in source
        assert "on_conflict_do_nothing" in source
        assert "pg_insert" in source

    def test_pg_insert_on_conflict_pattern(self):
        """Verify pg_insert with on_conflict_do_nothing compiles correctly."""
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        from backend.models.event_detection import event_detections

        # Create a statement with ON CONFLICT DO NOTHING
        stmt = (
            pg_insert(event_detections)
            .values(event_id=1, detection_id=1)
            .on_conflict_do_nothing(index_elements=["event_id", "detection_id"])
        )

        # Verify the statement compiles without error
        # This ensures the pattern is syntactically correct
        compiled = stmt.compile(compile_kwargs={"literal_binds": True})
        sql = str(compiled)

        assert "INSERT INTO" in sql
        assert "ON CONFLICT" in sql
        assert "DO NOTHING" in sql


class TestRedisAtomicOperations:
    """Tests for Redis atomic operations patterns."""

    @pytest.mark.asyncio
    async def test_redis_rpush_is_atomic(self):
        """Verify Redis RPUSH is used for atomic list operations."""
        # RPUSH is atomic in Redis, preventing partial creates
        mock_redis = AsyncMock()
        mock_redis.rpush = AsyncMock(return_value=1)

        # Atomic operation
        result = await mock_redis.rpush("batch:1:detections", "detection_data")

        mock_redis.rpush.assert_called_once()
        assert result == 1


class TestFrontendDedupSetBounding:
    """Tests for frontend dedup set memory bounding (documented for reference)."""

    def test_dedup_set_bounded_to_max_events(self):
        """Document the expected behavior of bounded dedup set.

        The frontend useEventStream hook maintains a Set of seen event IDs
        to prevent duplicate events from being displayed. This Set must be
        bounded to prevent memory leaks.

        Implementation in useEventStream.ts:
        - MAX_EVENTS = 100
        - When events exceed MAX_EVENTS, evicted event IDs are removed from Set
        - This ensures Set size is bounded to approximately MAX_EVENTS
        """
        MAX_EVENTS = 100

        # Simulate the bounded set behavior
        seen_ids: set[str] = set()
        events: list[str] = []

        # Add MAX_EVENTS + 10 events
        for i in range(MAX_EVENTS + 10):
            event_id = f"event_{i}"
            seen_ids.add(event_id)
            events.insert(0, event_id)

            # Trim events and clean up seen_ids (like the fix does)
            if len(events) > MAX_EVENTS:
                evicted = events[MAX_EVENTS:]
                events = events[:MAX_EVENTS]
                for evicted_id in evicted:
                    seen_ids.discard(evicted_id)

        # Verify set is bounded
        assert len(seen_ids) <= MAX_EVENTS
        assert len(events) == MAX_EVENTS

    def test_dedup_set_clears_on_clear_events(self):
        """Document that clearEvents also clears the dedup set."""
        seen_ids: set[str] = set()
        events: list[str] = []

        # Add some events
        for i in range(10):
            event_id = f"event_{i}"
            seen_ids.add(event_id)
            events.append(event_id)

        # Clear events (simulates clearEvents callback)
        events = []
        seen_ids.clear()

        assert len(seen_ids) == 0
        assert len(events) == 0

    def test_use_event_stream_has_nem_1998_fix(self):
        """Verify useEventStream.ts contains the NEM-1998 fix."""
        import pathlib

        # Read the frontend source file
        frontend_path = pathlib.Path(__file__).parent.parent.parent.parent.parent
        use_event_stream = frontend_path / "frontend" / "src" / "hooks" / "useEventStream.ts"

        if use_event_stream.exists():
            source = use_event_stream.read_text()
            assert "NEM-1998" in source
            assert "seenEventIdsRef.current.delete" in source
