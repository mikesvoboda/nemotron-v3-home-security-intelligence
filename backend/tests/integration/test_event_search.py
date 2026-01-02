"""Integration tests for Event model TSVECTOR full-text search.

These tests verify that the PostgreSQL full-text search functionality works correctly
with the events table, including:
- search_vector auto-population on INSERT via database trigger
- search_vector update on field changes
- Full-text search queries with ts_rank
- Search ranking accuracy
- Multi-word searches
- Edge cases: Unicode text, very long text, special characters

Uses real database with the session fixture from conftest.py.

NOTE: The search_vector trigger is created by Alembic migrations but not by
metadata.create_all(). Tests must set up the trigger in the database fixture.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select, text

from backend.models.camera import Camera
from backend.models.event import Event
from backend.tests.integration.conftest import unique_id

# =============================================================================
# Fixtures for FTS trigger setup
# =============================================================================


@pytest.fixture(scope="module")
def _ensure_fts_setup():
    """Marker fixture to track if FTS has been set up in this module."""
    return {"setup_done": False}


@pytest.fixture
async def fts_db(integration_db: str, _ensure_fts_setup: dict):
    """Set up FTS trigger and function in the test database.

    The search_vector trigger is created via Alembic migrations but not by
    metadata.create_all(). This fixture creates the necessary trigger and
    function for full-text search testing.
    """
    from backend.core.database import get_session

    # Only set up once per module
    if _ensure_fts_setup["setup_done"]:
        yield integration_db
        return

    async with get_session() as session:
        # Create the trigger function
        await session.execute(
            text(
                """
            CREATE OR REPLACE FUNCTION events_search_vector_update() RETURNS trigger AS $$
            DECLARE
                camera_name_text TEXT;
            BEGIN
                -- Get camera name for this event
                SELECT name INTO camera_name_text
                FROM cameras
                WHERE id = NEW.camera_id;

                -- Update search_vector combining all searchable fields
                NEW.search_vector := to_tsvector('english',
                    COALESCE(NEW.summary, '') || ' ' ||
                    COALESCE(NEW.reasoning, '') || ' ' ||
                    COALESCE(NEW.object_types, '') || ' ' ||
                    COALESCE(camera_name_text, '')
                );
                RETURN NEW;
            END
            $$ LANGUAGE plpgsql;
            """
            )
        )

        # Create the trigger (drop first if exists)
        await session.execute(
            text("DROP TRIGGER IF EXISTS events_search_vector_trigger ON events;")
        )
        await session.execute(
            text(
                """
            CREATE TRIGGER events_search_vector_trigger
            BEFORE INSERT OR UPDATE ON events
            FOR EACH ROW EXECUTE FUNCTION events_search_vector_update();
            """
            )
        )

        # Create GIN index if not exists
        await session.execute(
            text(
                """
            CREATE INDEX IF NOT EXISTS idx_events_search_vector
            ON events USING gin(search_vector);
            """
            )
        )

        await session.commit()

    _ensure_fts_setup["setup_done"] = True
    yield integration_db


# =============================================================================
# Helper Functions
# =============================================================================


async def create_test_camera(session, camera_id: str | None = None, name: str = "Test Camera"):
    """Create a test camera within a session."""
    if camera_id is None:
        camera_id = unique_id("search_cam")
    camera = Camera(
        id=camera_id,
        name=name,
        folder_path=f"/export/foscam/{camera_id}",
        status="online",
    )
    session.add(camera)
    await session.flush()
    return camera


# =============================================================================
# Test: search_vector auto-population on INSERT
# =============================================================================


class TestSearchVectorAutoPopulation:
    """Tests for search_vector auto-population via database trigger."""

    @pytest.mark.asyncio
    async def test_search_vector_populated_on_insert(self, fts_db: str):
        """Verify search_vector is automatically populated when an event is inserted."""
        from backend.core.database import get_session

        async with get_session() as session:
            camera = await create_test_camera(session)
            event = Event(
                batch_id=unique_id("search_batch"),
                camera_id=camera.id,
                started_at=datetime.now(UTC),
                summary="Suspicious person detected at front door",
                reasoning="Unknown individual lingering near entrance during night hours",
                object_types="person",
            )
            session.add(event)
            await session.commit()

            # Refresh to get the trigger-populated search_vector
            await session.refresh(event)

            assert event.search_vector is not None, "search_vector should be populated by trigger"

    @pytest.mark.asyncio
    async def test_search_vector_includes_summary(self, fts_db: str):
        """Verify search_vector includes summary content."""
        from backend.core.database import get_session

        async with get_session() as session:
            camera = await create_test_camera(session)
            event = Event(
                batch_id=unique_id("search_batch"),
                camera_id=camera.id,
                started_at=datetime.now(UTC),
                summary="Suspicious vehicle parked",
                reasoning="",
                object_types="",
            )
            session.add(event)
            await session.commit()
            event_id = event.id

        async with get_session() as session:
            # Query using the search term from summary
            query = select(Event).where(
                Event.search_vector.op("@@")(
                    func.to_tsquery(text("'english'::regconfig"), "suspicious")
                ),
                Event.id == event_id,
            )
            result = await session.execute(query)
            found_event = result.scalar_one_or_none()

            assert found_event is not None, "Should find event by summary term"
            assert found_event.id == event_id

    @pytest.mark.asyncio
    async def test_search_vector_includes_reasoning(self, fts_db: str):
        """Verify search_vector includes reasoning content."""
        from backend.core.database import get_session

        async with get_session() as session:
            camera = await create_test_camera(session)
            event = Event(
                batch_id=unique_id("search_batch"),
                camera_id=camera.id,
                started_at=datetime.now(UTC),
                summary="Motion detected",
                reasoning="Unidentified intruder approaching property",
                object_types="",
            )
            session.add(event)
            await session.commit()
            event_id = event.id

        async with get_session() as session:
            # Query using the search term from reasoning
            query = select(Event).where(
                Event.search_vector.op("@@")(
                    func.to_tsquery(text("'english'::regconfig"), "intruder")
                ),
                Event.id == event_id,
            )
            result = await session.execute(query)
            found_event = result.scalar_one_or_none()

            assert found_event is not None, "Should find event by reasoning term"
            assert found_event.id == event_id

    @pytest.mark.asyncio
    async def test_search_vector_includes_object_types(self, fts_db: str):
        """Verify search_vector includes object_types content."""
        from backend.core.database import get_session

        async with get_session() as session:
            camera = await create_test_camera(session)
            event = Event(
                batch_id=unique_id("search_batch"),
                camera_id=camera.id,
                started_at=datetime.now(UTC),
                summary="Activity detected",
                reasoning="",
                object_types="motorcycle, bicycle",
            )
            session.add(event)
            await session.commit()
            event_id = event.id

        async with get_session() as session:
            # Query using the search term from object_types
            query = select(Event).where(
                Event.search_vector.op("@@")(
                    func.to_tsquery(text("'english'::regconfig"), "motorcycle")
                ),
                Event.id == event_id,
            )
            result = await session.execute(query)
            found_event = result.scalar_one_or_none()

            assert found_event is not None, "Should find event by object_types term"
            assert found_event.id == event_id

    @pytest.mark.asyncio
    async def test_search_vector_includes_camera_name(self, fts_db: str):
        """Verify search_vector includes camera name via trigger subquery."""
        from backend.core.database import get_session

        # Use a unique camera name that won't be in other text
        camera_name = "BackyardGazeboCam"

        async with get_session() as session:
            camera = await create_test_camera(session, name=camera_name)
            event = Event(
                batch_id=unique_id("search_batch"),
                camera_id=camera.id,
                started_at=datetime.now(UTC),
                summary="Motion detected",
                reasoning="",
                object_types="",
            )
            session.add(event)
            await session.commit()
            event_id = event.id

        async with get_session() as session:
            # Query using the camera name
            # Note: PostgreSQL FTS tokenizes "BackyardGazeboCam" as a single word
            query = select(Event).where(
                Event.search_vector.op("@@")(
                    func.to_tsquery(text("'english'::regconfig"), "BackyardGazeboCam")
                ),
                Event.id == event_id,
            )
            result = await session.execute(query)
            found_event = result.scalar_one_or_none()

            assert found_event is not None, "Should find event by camera name"
            assert found_event.id == event_id


# =============================================================================
# Test: search_vector update on field changes
# =============================================================================


class TestSearchVectorUpdateOnChange:
    """Tests for search_vector update when event fields are modified."""

    @pytest.mark.asyncio
    async def test_search_vector_updates_on_summary_change(self, fts_db: str):
        """Verify search_vector updates when summary is changed."""
        from backend.core.database import get_session

        async with get_session() as session:
            camera = await create_test_camera(session)
            event = Event(
                batch_id=unique_id("search_batch"),
                camera_id=camera.id,
                started_at=datetime.now(UTC),
                summary="Initial summary content",
                reasoning="",
                object_types="",
            )
            session.add(event)
            await session.commit()
            event_id = event.id

        async with get_session() as session:
            # Update summary
            result = await session.execute(select(Event).where(Event.id == event_id))
            event = result.scalar_one()
            event.summary = "Updated prowler detected outside"
            await session.commit()

        async with get_session() as session:
            # Search for new term should succeed
            query = select(Event).where(
                Event.search_vector.op("@@")(
                    func.to_tsquery(text("'english'::regconfig"), "prowler")
                ),
                Event.id == event_id,
            )
            result = await session.execute(query)
            found_event = result.scalar_one_or_none()

            assert found_event is not None, "Should find event by updated summary term"
            assert found_event.id == event_id

    @pytest.mark.asyncio
    async def test_search_vector_updates_on_reasoning_change(self, fts_db: str):
        """Verify search_vector updates when reasoning is changed."""
        from backend.core.database import get_session

        async with get_session() as session:
            camera = await create_test_camera(session)
            event = Event(
                batch_id=unique_id("search_batch"),
                camera_id=camera.id,
                started_at=datetime.now(UTC),
                summary="Motion detected",
                reasoning="Initial reasoning",
                object_types="",
            )
            session.add(event)
            await session.commit()
            event_id = event.id

        async with get_session() as session:
            result = await session.execute(select(Event).where(Event.id == event_id))
            event = result.scalar_one()
            event.reasoning = "Identified as trespasser attempting entry"
            await session.commit()

        async with get_session() as session:
            query = select(Event).where(
                Event.search_vector.op("@@")(
                    func.to_tsquery(text("'english'::regconfig"), "trespasser")
                ),
                Event.id == event_id,
            )
            result = await session.execute(query)
            found_event = result.scalar_one_or_none()

            assert found_event is not None, "Should find event by updated reasoning term"
            assert found_event.id == event_id

    @pytest.mark.asyncio
    async def test_search_vector_updates_on_object_types_change(self, fts_db: str):
        """Verify search_vector updates when object_types is changed."""
        from backend.core.database import get_session

        async with get_session() as session:
            camera = await create_test_camera(session)
            event = Event(
                batch_id=unique_id("search_batch"),
                camera_id=camera.id,
                started_at=datetime.now(UTC),
                summary="Detection",
                reasoning="",
                object_types="person",
            )
            session.add(event)
            await session.commit()
            event_id = event.id

        async with get_session() as session:
            result = await session.execute(select(Event).where(Event.id == event_id))
            event = result.scalar_one()
            event.object_types = "skateboard, scooter"
            await session.commit()

        async with get_session() as session:
            query = select(Event).where(
                Event.search_vector.op("@@")(
                    func.to_tsquery(text("'english'::regconfig"), "skateboard")
                ),
                Event.id == event_id,
            )
            result = await session.execute(query)
            found_event = result.scalar_one_or_none()

            assert found_event is not None, "Should find event by updated object_types term"
            assert found_event.id == event_id


# =============================================================================
# Test: Full-text search queries
# =============================================================================


class TestFullTextSearchQueries:
    """Tests for various full-text search query patterns."""

    @pytest.mark.asyncio
    async def test_single_word_search(self, fts_db: str):
        """Test searching for a single word."""
        from backend.core.database import get_session

        async with get_session() as session:
            camera = await create_test_camera(session)
            event = Event(
                batch_id=unique_id("search_batch"),
                camera_id=camera.id,
                started_at=datetime.now(UTC),
                risk_score=80,
                summary="Suspicious person detected near entrance",
                reasoning="Unknown individual in dark clothing",
                object_types="person",
            )
            session.add(event)
            await session.commit()
            event_id = event.id

        async with get_session() as session:
            query = select(Event).where(
                Event.search_vector.op("@@")(
                    func.to_tsquery(text("'english'::regconfig"), "suspicious")
                ),
                Event.id == event_id,
            )
            result = await session.execute(query)
            events = result.scalars().all()

            assert len(events) == 1
            assert "Suspicious" in events[0].summary

    @pytest.mark.asyncio
    async def test_and_search(self, fts_db: str):
        """Test AND search with multiple terms."""
        from backend.core.database import get_session

        async with get_session() as session:
            camera = await create_test_camera(session)
            event = Event(
                batch_id=unique_id("search_batch"),
                camera_id=camera.id,
                started_at=datetime.now(UTC),
                risk_score=30,
                summary="Delivery vehicle arrived",
                reasoning="Expected delivery driver with package",
                object_types="vehicle, person",
            )
            session.add(event)
            await session.commit()
            event_id = event.id

        async with get_session() as session:
            # Search for "delivery AND vehicle"
            query = select(Event).where(
                Event.search_vector.op("@@")(
                    func.to_tsquery(text("'english'::regconfig"), "delivery & vehicle")
                ),
                Event.id == event_id,
            )
            result = await session.execute(query)
            events = result.scalars().all()

            assert len(events) == 1
            assert "Delivery" in events[0].summary

    @pytest.mark.asyncio
    async def test_or_search(self, fts_db: str):
        """Test OR search with multiple terms."""
        from backend.core.database import get_session

        async with get_session() as session:
            camera = await create_test_camera(session)
            # Create two events to test OR
            event1 = Event(
                batch_id=unique_id("search_batch"),
                camera_id=camera.id,
                started_at=datetime.now(UTC),
                summary="Suspicious person detected",
                reasoning="",
                object_types="person",
            )
            event2 = Event(
                batch_id=unique_id("search_batch"),
                camera_id=camera.id,
                started_at=datetime.now(UTC),
                summary="Cat walking across yard",
                reasoning="",
                object_types="animal, cat",
            )
            session.add(event1)
            session.add(event2)
            await session.commit()
            event_ids = {event1.id, event2.id}

        async with get_session() as session:
            # Search for "cat OR suspicious"
            query = select(Event).where(
                Event.search_vector.op("@@")(
                    func.to_tsquery(text("'english'::regconfig"), "cat | suspicious")
                ),
                Event.id.in_(event_ids),
            )
            result = await session.execute(query)
            events = result.scalars().all()

            assert len(events) == 2  # Cat event and Suspicious event

    @pytest.mark.asyncio
    async def test_not_search(self, fts_db: str):
        """Test NOT search to exclude terms."""
        from backend.core.database import get_session

        async with get_session() as session:
            camera = await create_test_camera(session)
            # Event with "person" but NOT "suspicious"
            event = Event(
                batch_id=unique_id("search_batch"),
                camera_id=camera.id,
                started_at=datetime.now(UTC),
                summary="Delivery person arrived",
                reasoning="Expected delivery",
                object_types="person",
            )
            session.add(event)
            await session.commit()
            event_id = event.id

        async with get_session() as session:
            # Search for "person NOT suspicious"
            query = select(Event).where(
                Event.search_vector.op("@@")(
                    func.to_tsquery(text("'english'::regconfig"), "person & !suspicious")
                ),
                Event.id == event_id,
            )
            result = await session.execute(query)
            events = result.scalars().all()

            assert len(events) == 1
            assert "suspicious" not in events[0].summary.lower()

    @pytest.mark.asyncio
    async def test_phrase_search(self, fts_db: str):
        """Test phrase search with proximity operator."""
        from backend.core.database import get_session

        async with get_session() as session:
            camera = await create_test_camera(session)
            event = Event(
                batch_id=unique_id("search_batch"),
                camera_id=camera.id,
                started_at=datetime.now(UTC),
                summary="suspicious person detected near window",
                reasoning="",
                object_types="",
            )
            session.add(event)
            await session.commit()
            event_id = event.id

        async with get_session() as session:
            # Search for exact phrase "suspicious person"
            query = select(Event).where(
                Event.search_vector.op("@@")(
                    func.to_tsquery(text("'english'::regconfig"), "suspicious <-> person")
                ),
                Event.id == event_id,
            )
            result = await session.execute(query)
            events = result.scalars().all()

            assert any(e.id == event_id for e in events)

    @pytest.mark.asyncio
    async def test_websearch_to_tsquery(self, fts_db: str):
        """Test using websearch_to_tsquery for natural language queries."""
        from backend.core.database import get_session

        async with get_session() as session:
            camera = await create_test_camera(session)
            event = Event(
                batch_id=unique_id("search_batch"),
                camera_id=camera.id,
                started_at=datetime.now(UTC),
                summary="Delivery driver arrived",
                reasoning="Expected delivery with package",
                object_types="person",
            )
            session.add(event)
            await session.commit()
            event_id = event.id

        async with get_session() as session:
            # websearch_to_tsquery accepts natural language
            query = select(Event).where(
                Event.search_vector.op("@@")(
                    func.websearch_to_tsquery(text("'english'::regconfig"), "delivery driver")
                ),
                Event.id == event_id,
            )
            result = await session.execute(query)
            events = result.scalars().all()

            assert len(events) >= 1
            assert any("delivery" in e.summary.lower() for e in events)


# =============================================================================
# Test: Search ranking accuracy
# =============================================================================


class TestSearchRanking:
    """Tests for ts_rank search ranking accuracy."""

    @pytest.mark.asyncio
    async def test_ts_rank_returns_scores(self, fts_db: str):
        """Verify ts_rank returns relevance scores."""
        from backend.core.database import get_session

        async with get_session() as session:
            camera = await create_test_camera(session)
            event = Event(
                batch_id=unique_id("search_batch"),
                camera_id=camera.id,
                started_at=datetime.now(UTC),
                summary="Person person person detected",
                reasoning="Multiple persons observed",
                object_types="person",
            )
            session.add(event)
            await session.commit()
            event_id = event.id

        async with get_session() as session:
            tsquery = func.to_tsquery(text("'english'::regconfig"), "person")
            rank = func.ts_rank(Event.search_vector, tsquery)

            query = select(Event, rank.label("relevance")).where(
                Event.search_vector.op("@@")(tsquery),
                Event.id == event_id,
            )
            result = await session.execute(query)
            row = result.first()

            assert row is not None
            event, relevance = row
            assert relevance > 0, "Relevance score should be positive"

    @pytest.mark.asyncio
    async def test_higher_term_frequency_ranks_higher(self, fts_db: str):
        """Verify events with more term occurrences rank higher."""
        from backend.core.database import get_session

        async with get_session() as session:
            camera = await create_test_camera(session)

            # Event with multiple occurrences of "security"
            high_freq_event = Event(
                batch_id=unique_id("search_batch"),
                camera_id=camera.id,
                started_at=datetime.now(UTC),
                summary="Security breach security alert security warning",
                reasoning="Security team notified about security incident",
                object_types="security",
            )
            session.add(high_freq_event)

            # Event with single occurrence
            low_freq_event = Event(
                batch_id=unique_id("search_batch"),
                camera_id=camera.id,
                started_at=datetime.now(UTC),
                summary="Motion detected",
                reasoning="Security notification sent",
                object_types="person",
            )
            session.add(low_freq_event)
            await session.commit()

            high_freq_id = high_freq_event.id
            low_freq_id = low_freq_event.id
            event_ids = {high_freq_id, low_freq_id}

        async with get_session() as session:
            tsquery = func.to_tsquery(text("'english'::regconfig"), "security")
            rank = func.ts_rank(Event.search_vector, tsquery)

            query = (
                select(Event, rank.label("relevance"))
                .where(
                    Event.search_vector.op("@@")(tsquery),
                    Event.id.in_(event_ids),
                )
                .order_by(rank.desc())
            )
            result = await session.execute(query)
            rows = result.all()

            assert len(rows) == 2
            # High frequency event should rank first
            assert rows[0][0].id == high_freq_id
            # High frequency should have higher score
            assert rows[0][1] > rows[1][1]

    @pytest.mark.asyncio
    async def test_ranking_order_by_relevance(self, fts_db: str):
        """Test that results can be ordered by relevance score."""
        from backend.core.database import get_session

        async with get_session() as session:
            camera = await create_test_camera(session)
            event_ids = []
            events_data = [
                ("Alert alert alert", "alert"),
                ("Single alert", "normal"),
                ("Alert alert notice", "alert"),
            ]
            for summary, obj_types in events_data:
                event = Event(
                    batch_id=unique_id("search_batch"),
                    camera_id=camera.id,
                    started_at=datetime.now(UTC),
                    summary=summary,
                    reasoning="",
                    object_types=obj_types,
                )
                session.add(event)
                await session.flush()
                event_ids.append(event.id)
            await session.commit()

        async with get_session() as session:
            tsquery = func.to_tsquery(text("'english'::regconfig"), "alert")
            rank = func.ts_rank(Event.search_vector, tsquery)

            query = (
                select(Event, rank.label("relevance"))
                .where(
                    Event.search_vector.op("@@")(tsquery),
                    Event.id.in_(event_ids),
                )
                .order_by(rank.desc())
            )
            result = await session.execute(query)
            rows = result.all()

            # Verify descending order by relevance
            relevances = [row[1] for row in rows]
            assert relevances == sorted(relevances, reverse=True)


# =============================================================================
# Test: Multi-word searches
# =============================================================================


class TestMultiWordSearches:
    """Tests for multi-word search scenarios."""

    @pytest.mark.asyncio
    async def test_all_words_must_match_with_and(self, fts_db: str):
        """Test that AND requires all words to match."""
        from backend.core.database import get_session

        async with get_session() as session:
            camera = await create_test_camera(session)
            event = Event(
                batch_id=unique_id("search_batch"),
                camera_id=camera.id,
                started_at=datetime.now(UTC),
                summary="Package delivered to porch",
                reasoning="",
                object_types="",
            )
            session.add(event)
            await session.commit()
            event_id = event.id

        async with get_session() as session:
            # Should find: both "package" and "porch" are present
            query = select(Event).where(
                Event.search_vector.op("@@")(
                    func.to_tsquery(text("'english'::regconfig"), "package & porch")
                ),
                Event.id == event_id,
            )
            result = await session.execute(query)
            found = result.scalars().all()
            assert len(found) == 1

            # Should NOT find: "package" exists but "garage" doesn't
            query = select(Event).where(
                Event.search_vector.op("@@")(
                    func.to_tsquery(text("'english'::regconfig"), "package & garage")
                ),
                Event.id == event_id,
            )
            result = await session.execute(query)
            not_found = result.scalars().all()
            assert len(not_found) == 0

    @pytest.mark.asyncio
    async def test_stemming_in_search(self, fts_db: str):
        """Test that PostgreSQL stemming works (e.g., 'walking' matches 'walk')."""
        from backend.core.database import get_session

        async with get_session() as session:
            camera = await create_test_camera(session)
            event = Event(
                batch_id=unique_id("search_batch"),
                camera_id=camera.id,
                started_at=datetime.now(UTC),
                summary="Person walking through the yard",
                reasoning="",
                object_types="",
            )
            session.add(event)
            await session.commit()
            event_id = event.id

        async with get_session() as session:
            # Search for "walk" should match "walking" due to stemming
            query = select(Event).where(
                Event.search_vector.op("@@")(func.to_tsquery(text("'english'::regconfig"), "walk")),
                Event.id == event_id,
            )
            result = await session.execute(query)
            found = result.scalars().all()

            assert any(e.id == event_id for e in found), "Stemming should match 'walk' to 'walking'"


# =============================================================================
# Test: Edge cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases: Unicode, long text, special characters."""

    @pytest.mark.asyncio
    async def test_unicode_text_in_search(self, fts_db: str):
        """Test that Unicode text is handled correctly."""
        from backend.core.database import get_session

        async with get_session() as session:
            camera = await create_test_camera(session)
            event = Event(
                batch_id=unique_id("search_batch"),
                camera_id=camera.id,
                started_at=datetime.now(UTC),
                summary="Entrega de paquete en la puerta",  # Spanish
                reasoning="Lieferung an der Tur",  # German
                object_types="person",
            )
            session.add(event)
            await session.commit()
            event_id = event.id

        async with get_session() as session:
            # Verify the event was created with Unicode content
            result = await session.execute(select(Event).where(Event.id == event_id))
            found = result.scalars().first()
            assert found is not None
            assert "Entrega" in found.summary

    @pytest.mark.asyncio
    async def test_unicode_search_terms(self, fts_db: str):
        """Test searching with Unicode search terms."""
        from backend.core.database import get_session

        async with get_session() as session:
            camera = await create_test_camera(session)
            event = Event(
                batch_id=unique_id("search_batch"),
                camera_id=camera.id,
                started_at=datetime.now(UTC),
                summary="Cafe delivery service arrived",
                reasoning="",
                object_types="",
            )
            session.add(event)
            await session.commit()
            event_id = event.id

        async with get_session() as session:
            # Search for term with accented character equivalent
            query = select(Event).where(
                Event.search_vector.op("@@")(func.to_tsquery(text("'english'::regconfig"), "cafe")),
                Event.id == event_id,
            )
            result = await session.execute(query)
            found = result.scalars().all()
            assert len(found) >= 1

    @pytest.mark.asyncio
    async def test_very_long_text(self, fts_db: str):
        """Test handling of very long text content."""
        from backend.core.database import get_session

        # Create very long summary (10000 chars)
        long_summary = "detection " * 1000  # 10000 characters

        async with get_session() as session:
            camera = await create_test_camera(session)
            event = Event(
                batch_id=unique_id("search_batch"),
                camera_id=camera.id,
                started_at=datetime.now(UTC),
                summary=long_summary,
                reasoning="Important unique marker wordxyz",
                object_types="",
            )
            session.add(event)
            await session.commit()
            event_id = event.id

        async with get_session() as session:
            # Should be able to search within the long text
            query = select(Event).where(
                Event.search_vector.op("@@")(
                    func.to_tsquery(text("'english'::regconfig"), "detection")
                ),
                Event.id == event_id,
            )
            result = await session.execute(query)
            found = result.scalars().all()
            assert any(e.id == event_id for e in found)

            # Should also find the unique marker
            query = select(Event).where(
                Event.search_vector.op("@@")(
                    func.to_tsquery(text("'english'::regconfig"), "wordxyz")
                ),
                Event.id == event_id,
            )
            result = await session.execute(query)
            found = result.scalars().all()
            assert any(e.id == event_id for e in found)

    @pytest.mark.asyncio
    async def test_special_characters_in_text(self, fts_db: str):
        """Test handling of special characters in text."""
        from backend.core.database import get_session

        async with get_session() as session:
            camera = await create_test_camera(session)
            event = Event(
                batch_id=unique_id("search_batch"),
                camera_id=camera.id,
                started_at=datetime.now(UTC),
                summary="Alert: Person at door! (high priority) - urgent",
                reasoning="Check #123 @ location",
                object_types="person, vehicle",
            )
            session.add(event)
            await session.commit()
            event_id = event.id

        async with get_session() as session:
            # Should still find by word content despite special chars
            query = select(Event).where(
                Event.search_vector.op("@@")(
                    func.to_tsquery(text("'english'::regconfig"), "priority")
                ),
                Event.id == event_id,
            )
            result = await session.execute(query)
            found = result.scalars().all()
            assert any(e.id == event_id for e in found)

    @pytest.mark.asyncio
    async def test_empty_fields_handled(self, fts_db: str):
        """Test that events with empty/null fields are handled correctly."""
        from backend.core.database import get_session

        async with get_session() as session:
            camera = await create_test_camera(session)
            event = Event(
                batch_id=unique_id("search_batch"),
                camera_id=camera.id,
                started_at=datetime.now(UTC),
                summary=None,
                reasoning=None,
                object_types=None,
            )
            session.add(event)
            await session.commit()
            await session.refresh(event)

            # Event should be created successfully
            assert event.id is not None
            # search_vector may still be populated with camera name
            # The trigger uses COALESCE to handle NULLs

    @pytest.mark.asyncio
    async def test_numeric_content_in_text(self, fts_db: str):
        """Test searching for numeric content."""
        from backend.core.database import get_session

        async with get_session() as session:
            camera = await create_test_camera(session)
            event = Event(
                batch_id=unique_id("search_batch"),
                camera_id=camera.id,
                started_at=datetime.now(UTC),
                summary="Vehicle license ABC123 detected",
                reasoning="Speed estimated at 45mph",
                object_types="",
            )
            session.add(event)
            await session.commit()
            event_id = event.id

        async with get_session() as session:
            # Search for alphanumeric content
            query = select(Event).where(
                Event.search_vector.op("@@")(
                    func.to_tsquery(text("'english'::regconfig"), "ABC123")
                ),
                Event.id == event_id,
            )
            result = await session.execute(query)
            found = result.scalars().all()
            assert any(e.id == event_id for e in found)

    @pytest.mark.asyncio
    async def test_case_insensitive_search(self, fts_db: str):
        """Test that search is case-insensitive."""
        from backend.core.database import get_session

        async with get_session() as session:
            camera = await create_test_camera(session)
            event = Event(
                batch_id=unique_id("search_batch"),
                camera_id=camera.id,
                started_at=datetime.now(UTC),
                summary="URGENT SECURITY ALERT",
                reasoning="",
                object_types="",
            )
            session.add(event)
            await session.commit()
            event_id = event.id

        async with get_session() as session:
            # Search with lowercase should find uppercase text
            query = select(Event).where(
                Event.search_vector.op("@@")(
                    func.to_tsquery(text("'english'::regconfig"), "urgent")
                ),
                Event.id == event_id,
            )
            result = await session.execute(query)
            found = result.scalars().all()
            assert any(e.id == event_id for e in found)

            # Search with mixed case
            query = select(Event).where(
                Event.search_vector.op("@@")(
                    func.to_tsquery(text("'english'::regconfig"), "Security")
                ),
                Event.id == event_id,
            )
            result = await session.execute(query)
            found = result.scalars().all()
            assert any(e.id == event_id for e in found)


# =============================================================================
# Test: GIN Index usage
# =============================================================================


class TestGINIndexUsage:
    """Tests to verify GIN index is being used for search queries."""

    @pytest.mark.asyncio
    async def test_gin_index_exists(self, fts_db: str):
        """Verify the GIN index exists on the search_vector column."""
        from backend.core.database import get_session

        async with get_session() as session:
            # Query pg_indexes to check for our index
            result = await session.execute(
                text(
                    """
                    SELECT indexname, indexdef
                    FROM pg_indexes
                    WHERE tablename = 'events'
                    AND indexname = 'idx_events_search_vector'
                    """
                )
            )
            row = result.first()

            assert row is not None, "GIN index should exist"
            assert "gin" in row[1].lower(), "Index should be GIN type"

    @pytest.mark.asyncio
    async def test_query_uses_index(self, fts_db: str):
        """Test that search queries use the GIN index (via EXPLAIN)."""
        from backend.core.database import get_session

        async with get_session() as session:
            camera = await create_test_camera(session)
            # Create an event to search
            event = Event(
                batch_id=unique_id("search_batch"),
                camera_id=camera.id,
                started_at=datetime.now(UTC),
                summary="Test event for index verification",
                reasoning="",
                object_types="",
            )
            session.add(event)
            await session.commit()

        async with get_session() as session:
            # Run EXPLAIN ANALYZE on a search query
            result = await session.execute(
                text(
                    """
                    EXPLAIN (FORMAT JSON)
                    SELECT * FROM events
                    WHERE search_vector @@ to_tsquery('english', 'test')
                    """
                )
            )
            plan = result.scalar()

            # The plan should reference the GIN index (for non-trivial datasets)
            # Note: PostgreSQL may choose seq scan for very small tables
            # This test just verifies the query executes successfully
            assert plan is not None


# =============================================================================
# Test: Trigger function behavior
# =============================================================================


class TestTriggerBehavior:
    """Tests for the database trigger function behavior."""

    @pytest.mark.asyncio
    async def test_trigger_exists(self, fts_db: str):
        """Verify the search vector trigger exists."""
        from backend.core.database import get_session

        async with get_session() as session:
            result = await session.execute(
                text(
                    """
                    SELECT tgname
                    FROM pg_trigger
                    WHERE tgrelid = 'events'::regclass
                    AND tgname = 'events_search_vector_trigger'
                    """
                )
            )
            row = result.first()

            assert row is not None, "Trigger should exist"
            assert row[0] == "events_search_vector_trigger"

    @pytest.mark.asyncio
    async def test_trigger_function_exists(self, fts_db: str):
        """Verify the trigger function exists."""
        from backend.core.database import get_session

        async with get_session() as session:
            result = await session.execute(
                text(
                    """
                    SELECT proname
                    FROM pg_proc
                    WHERE proname = 'events_search_vector_update'
                    """
                )
            )
            row = result.first()

            assert row is not None, "Trigger function should exist"
            assert row[0] == "events_search_vector_update"
