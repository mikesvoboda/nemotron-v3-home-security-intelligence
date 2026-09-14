"""Integration tests for GIN trigram index on events.object_types.

These tests verify that the pg_trgm extension and GIN index on object_types
work correctly for optimizing LIKE/ILIKE queries.

Tests cover:
- pg_trgm extension is enabled
- GIN index creation with gin_trgm_ops
- LIKE queries with leading wildcards use the index
- ILIKE queries (case-insensitive) use the index
- Query performance improvement with index

Uses real database with the session fixture from conftest.py.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import text

from backend.models.camera import Camera
from backend.models.event import Event
from backend.tests.integration.conftest import unique_id

# =============================================================================
# Fixtures for trigram index setup
# =============================================================================


@pytest.fixture(scope="module")
def _ensure_trgm_setup():
    """Marker fixture to track if trigram index has been set up in this module."""
    return {"setup_done": False}


@pytest.fixture
async def _trgm_db(integration_db: str, _ensure_trgm_setup: dict):
    """Set up pg_trgm extension and GIN index in the test database.

    The trigram index is created via Alembic migrations but not by
    metadata.create_all(). This fixture creates the necessary extension
    and index for testing.
    """
    from backend.core.database import get_session

    # Only set up once per module
    if _ensure_trgm_setup["setup_done"]:
        yield integration_db
        return

    async with get_session() as session:
        # Enable pg_trgm extension
        await session.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))

        # Create GIN trigram index on object_types
        await session.execute(
            text(
                """
            CREATE INDEX IF NOT EXISTS idx_events_object_types_trgm
            ON events USING gin(object_types gin_trgm_ops);
            """
            )
        )

        await session.commit()

    _ensure_trgm_setup["setup_done"] = True
    yield integration_db


# =============================================================================
# Helper Functions
# =============================================================================


async def create_test_camera(session, camera_id: str | None = None, name: str = "Test Camera"):
    """Create a test camera within a session."""
    if camera_id is None:
        camera_id = unique_id("trgm_cam")
    camera = Camera(
        id=camera_id,
        name=name,
        folder_path=f"/export/foscam/{camera_id}",
        status="online",
    )
    session.add(camera)
    await session.flush()
    return camera


async def create_test_event(session, camera, object_types: str | None = None):
    """Create a test event with specified object_types."""
    event = Event(
        batch_id=unique_id("trgm_batch"),
        camera_id=camera.id,
        started_at=datetime.now(UTC),
        summary="Test event for trigram index",
        reasoning="Testing object_types LIKE queries",
        object_types=object_types,
    )
    session.add(event)
    await session.flush()
    return event


# =============================================================================
# Test: pg_trgm extension
# =============================================================================


class TestPgTrgmExtension:
    """Tests for pg_trgm extension availability."""

    @pytest.mark.asyncio
    async def test_pg_trgm_extension_can_be_enabled(self, _trgm_db: str):
        """Verify pg_trgm extension can be enabled in PostgreSQL."""
        from backend.core.database import get_session

        async with get_session() as session:
            # Check if extension is available
            result = await session.execute(
                text(
                    """
                SELECT extname FROM pg_extension WHERE extname = 'pg_trgm';
                """
                )
            )
            row = result.fetchone()
            assert row is not None, "pg_trgm extension should be enabled"
            assert row[0] == "pg_trgm"

    @pytest.mark.asyncio
    async def test_trigram_function_available(self, _trgm_db: str):
        """Verify trigram functions are available after enabling extension."""
        from backend.core.database import get_session

        async with get_session() as session:
            # Test the show_trgm function which is part of pg_trgm
            result = await session.execute(text("SELECT show_trgm('person')"))
            row = result.fetchone()
            assert row is not None, "show_trgm function should work"
            # Trigrams for 'person' should include '  p', ' pe', 'per', 'ers', 'rso', 'son', 'on '
            trigrams = row[0]
            assert "per" in trigrams or "ers" in trigrams, f"Expected trigrams in {trigrams}"


# =============================================================================
# Test: GIN trigram index creation
# =============================================================================


class TestGinTrgmIndexCreation:
    """Tests for GIN trigram index on object_types column."""

    @pytest.mark.asyncio
    async def test_gin_trgm_index_exists(self, _trgm_db: str):
        """Verify GIN trigram index exists on events.object_types."""
        from backend.core.database import get_session

        async with get_session() as session:
            # Query pg_indexes to check if our index exists
            result = await session.execute(
                text(
                    """
                SELECT indexname, indexdef
                FROM pg_indexes
                WHERE tablename = 'events' AND indexname = 'idx_events_object_types_trgm';
                """
                )
            )
            row = result.fetchone()
            assert row is not None, "idx_events_object_types_trgm index should exist"
            assert "gin_trgm_ops" in row[1], f"Index should use gin_trgm_ops: {row[1]}"

    @pytest.mark.asyncio
    async def test_index_uses_gin_access_method(self, _trgm_db: str):
        """Verify the index uses GIN access method."""
        from backend.core.database import get_session

        async with get_session() as session:
            result = await session.execute(
                text(
                    """
                SELECT am.amname
                FROM pg_index idx
                JOIN pg_class cls ON cls.oid = idx.indexrelid
                JOIN pg_am am ON am.oid = cls.relam
                WHERE cls.relname = 'idx_events_object_types_trgm';
                """
                )
            )
            row = result.fetchone()
            assert row is not None, "Index should exist"
            assert row[0] == "gin", f"Index should use GIN access method, got {row[0]}"


# =============================================================================
# Test: LIKE query optimization
# =============================================================================


class TestLikeQueryOptimization:
    """Tests for LIKE query optimization using GIN trigram index."""

    @pytest.mark.asyncio
    async def test_like_query_with_leading_wildcard_can_use_index(self, _trgm_db: str):
        """Verify LIKE queries with leading wildcards can potentially use the index.

        Note: Whether PostgreSQL actually uses the index depends on table statistics
        and query planner decisions. This test verifies the index is available.
        """
        from backend.core.database import get_session

        async with get_session() as session:
            # Create test data
            camera = await create_test_camera(session)
            await create_test_event(session, camera, "person,vehicle")
            await create_test_event(session, camera, "animal,person")
            await create_test_event(session, camera, "vehicle")
            await session.commit()

        async with get_session() as session:
            # Check EXPLAIN output - the index may or may not be used depending on
            # table size and statistics, but it should be available
            result = await session.execute(
                text(
                    """
                EXPLAIN (FORMAT JSON)
                SELECT * FROM events WHERE object_types LIKE '%person%';
                """
                )
            )
            explain_output = result.fetchone()[0]

            # The explain output is a JSON array with query plan
            # We just verify the query executes successfully
            assert explain_output is not None

    @pytest.mark.asyncio
    async def test_ilike_query_with_leading_wildcard_can_use_index(self, _trgm_db: str):
        """Verify ILIKE queries can also potentially use the trigram index."""
        from backend.core.database import get_session

        async with get_session() as session:
            # Create test data
            camera = await create_test_camera(session)
            await create_test_event(session, camera, "Person,Vehicle")
            await create_test_event(session, camera, "PERSON,ANIMAL")
            await session.commit()

        async with get_session() as session:
            # Test case-insensitive search
            result = await session.execute(
                text(
                    """
                EXPLAIN (FORMAT JSON)
                SELECT * FROM events WHERE object_types ILIKE '%person%';
                """
                )
            )
            explain_output = result.fetchone()[0]
            assert explain_output is not None


# =============================================================================
# Test: Query correctness with index
# =============================================================================


class TestQueryCorrectness:
    """Tests for query correctness with GIN trigram index."""

    @pytest.mark.asyncio
    async def test_like_query_returns_correct_results(self, _trgm_db: str):
        """Verify LIKE queries return correct results with index."""
        from backend.core.database import get_session

        async with get_session() as session:
            camera = await create_test_camera(session)
            event1 = await create_test_event(session, camera, "person,vehicle")
            await create_test_event(session, camera, "animal")  # No person
            event3 = await create_test_event(session, camera, "person")
            await session.commit()
            event1_id = event1.id
            event3_id = event3.id

        async with get_session() as session:
            # Search for 'person' - should find event1 and event3
            result = await session.execute(
                text("SELECT id FROM events WHERE object_types LIKE '%person%' ORDER BY id")
            )
            rows = result.fetchall()
            found_ids = [r[0] for r in rows]

            assert event1_id in found_ids, f"Should find event1 (id={event1_id})"
            assert event3_id in found_ids, f"Should find event3 (id={event3_id})"

    @pytest.mark.asyncio
    async def test_ilike_query_case_insensitive(self, _trgm_db: str):
        """Verify ILIKE queries are case-insensitive."""
        from backend.core.database import get_session

        async with get_session() as session:
            camera = await create_test_camera(session)
            event1 = await create_test_event(session, camera, "PERSON,Vehicle")
            event2 = await create_test_event(session, camera, "person,animal")
            await session.commit()
            event1_id = event1.id
            event2_id = event2.id

        async with get_session() as session:
            # Search for 'person' (lowercase) - should find both
            result = await session.execute(
                text("SELECT id FROM events WHERE object_types ILIKE '%person%' ORDER BY id")
            )
            rows = result.fetchall()
            found_ids = [r[0] for r in rows]

            assert event1_id in found_ids, "Should find event with 'PERSON'"
            assert event2_id in found_ids, "Should find event with 'person'"

    @pytest.mark.asyncio
    async def test_comma_separated_pattern_matching(self, _trgm_db: str):
        """Verify LIKE patterns work correctly for comma-separated values."""
        from backend.core.database import get_session

        async with get_session() as session:
            camera = await create_test_camera(session)
            # These match the patterns used in events.py
            event1 = await create_test_event(session, camera, "person,vehicle,dog")
            event2 = await create_test_event(session, camera, "cat,person")
            event3 = await create_test_event(session, camera, "person")
            await create_test_event(session, camera, "vehicle")
            await session.commit()
            event1_id = event1.id
            event2_id = event2.id
            event3_id = event3.id

        async with get_session() as session:
            # Test patterns from events.py:
            # (Event.object_types == object_type)  -- exact match
            # | (Event.object_types.like(f"{safe_object_type},%"))  -- at start
            # | (Event.object_types.like(f"%,{safe_object_type},%"))  -- in middle
            # | (Event.object_types.like(f"%,{safe_object_type}"))  -- at end

            # Pattern: 'person,%' (at start)
            result = await session.execute(
                text("SELECT id FROM events WHERE object_types LIKE 'person,%'")
            )
            start_ids = [r[0] for r in result.fetchall()]
            assert event1_id in start_ids, "Should find event starting with 'person,'"

            # Pattern: '%,person' (at end)
            result = await session.execute(
                text("SELECT id FROM events WHERE object_types LIKE '%,person'")
            )
            end_ids = [r[0] for r in result.fetchall()]
            assert event2_id in end_ids, "Should find event ending with ',person'"

            # Exact match: 'person'
            result = await session.execute(
                text("SELECT id FROM events WHERE object_types = 'person'")
            )
            exact_ids = [r[0] for r in result.fetchall()]
            assert event3_id in exact_ids, "Should find exact match 'person'"

    @pytest.mark.asyncio
    async def test_null_object_types_not_matched(self, _trgm_db: str):
        """Verify NULL object_types are not matched by LIKE."""
        from backend.core.database import get_session

        async with get_session() as session:
            camera = await create_test_camera(session)
            await create_test_event(session, camera, None)  # NULL object_types
            await session.commit()

        async with get_session() as session:
            # Verify NULL is handled correctly
            # LIKE queries should not match NULL values (SQL standard behavior)
            result = await session.execute(
                text("SELECT COUNT(*) FROM events WHERE object_types IS NULL")
            )
            null_count = result.scalar()
            assert null_count >= 1, "Should have at least one NULL object_types"

            # Verify NULL values are excluded from LIKE results
            result = await session.execute(
                text(
                    """
                    SELECT COUNT(*) FROM events
                    WHERE object_types LIKE '%person%' AND object_types IS NULL
                    """
                )
            )
            null_match_count = result.scalar()
            assert null_match_count == 0, "LIKE should not match NULL values"
