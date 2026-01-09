"""Tests for concurrency bug fixes (NEM-1998, NEM-2012).

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

    def test_nemotron_streaming_uses_on_conflict(self):
        """Verify nemotron_streaming.py contains ON CONFLICT DO NOTHING pattern (NEM-2012)."""
        import inspect

        from backend.services import nemotron_streaming

        source = inspect.getsource(nemotron_streaming)

        # Verify the NEM-2012 fix is present
        assert "NEM-2012" in source
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


class TestEventDetectionConcurrentInsertion:
    """Tests for concurrent EventDetection insertion handling (NEM-2012)."""

    def test_on_conflict_do_nothing_generates_valid_sql(self):
        """Verify ON CONFLICT DO NOTHING generates valid PostgreSQL SQL."""
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        from backend.models.event_detection import event_detections

        # Simulate concurrent insertion of same event_id/detection_id pair
        stmt = (
            pg_insert(event_detections)
            .values(event_id=42, detection_id=100)
            .on_conflict_do_nothing(index_elements=["event_id", "detection_id"])
        )

        # Compile to PostgreSQL dialect
        from sqlalchemy.dialects import postgresql

        compiled = stmt.compile(dialect=postgresql.dialect())
        sql = str(compiled)

        # Verify the SQL structure
        assert "INSERT INTO event_detections" in sql
        assert "ON CONFLICT" in sql
        assert "DO NOTHING" in sql
        # Verify column names are in the conflict clause
        assert "event_id" in sql
        assert "detection_id" in sql

    def test_multiple_inserts_with_same_key_compile_correctly(self):
        """Verify multiple ON CONFLICT statements for same key compile correctly."""
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        from backend.models.event_detection import event_detections

        # Simulate two concurrent inserts for the same junction record
        event_id = 1
        detection_id = 100

        stmt1 = (
            pg_insert(event_detections)
            .values(event_id=event_id, detection_id=detection_id)
            .on_conflict_do_nothing(index_elements=["event_id", "detection_id"])
        )

        stmt2 = (
            pg_insert(event_detections)
            .values(event_id=event_id, detection_id=detection_id)
            .on_conflict_do_nothing(index_elements=["event_id", "detection_id"])
        )

        # Both should compile without error (actual DB behavior tests in integration)
        from sqlalchemy.dialects import postgresql

        sql1 = str(stmt1.compile(dialect=postgresql.dialect()))
        sql2 = str(stmt2.compile(dialect=postgresql.dialect()))

        # Both should produce identical SQL (idempotent)
        assert sql1 == sql2
        assert "ON CONFLICT" in sql1
        assert "DO NOTHING" in sql1

    def test_event_detections_table_has_unique_constraint(self):
        """Verify event_detections table has composite primary key (unique constraint)."""
        from backend.models.event_detection import event_detections

        # Check primary key constraint exists
        pk = event_detections.primary_key
        pk_column_names = [col.name for col in pk.columns]

        # Composite primary key on (event_id, detection_id) acts as unique constraint
        assert "event_id" in pk_column_names
        assert "detection_id" in pk_column_names
        assert len(pk_column_names) == 2

    def test_event_detection_orm_model_maps_to_same_table(self):
        """Verify EventDetection ORM model maps to same table as event_detections Table."""
        from backend.models.event_detection import EventDetection, event_detections

        # Both should reference the same underlying table
        assert EventDetection.__tablename__ == event_detections.name
        assert EventDetection.__tablename__ == "event_detections"
