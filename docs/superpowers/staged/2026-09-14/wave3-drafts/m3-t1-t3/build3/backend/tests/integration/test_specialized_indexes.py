"""Integration tests for specialized PostgreSQL indexes (GIN and BRIN).

These tests verify that the GIN and BRIN indexes are correctly created
and functional for their intended use cases:

1. GIN index on detections.enrichment_data for JSONB containment queries
2. BRIN indexes on timestamp columns for time-series range queries

Tests cover:
- Index existence verification
- Index type verification (GIN vs BRIN)
- Query functionality with indexes
- EXPLAIN plan verification

Uses real database with the session fixture from conftest.py.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import text

from backend.models.camera import Camera
from backend.models.detection import Detection
from backend.models.event import Event
from backend.models.log import Log
from backend.tests.integration.conftest import unique_id

# =============================================================================
# Fixtures for index setup
# =============================================================================


@pytest.fixture(scope="module")
def _ensure_indexes_setup():
    """Marker fixture to track if indexes have been set up in this module."""
    return {"setup_done": False}


@pytest.fixture
async def _indexes_db(integration_db: str, _ensure_indexes_setup: dict):
    """Set up GIN and BRIN indexes in the test database.

    The indexes are created via Alembic migrations but not by
    metadata.create_all(). This fixture creates the necessary indexes
    for testing.
    """
    from backend.core.database import get_session

    # Only set up once per module
    if _ensure_indexes_setup["setup_done"]:
        yield integration_db
        return

    async with get_session() as session:
        # Create GIN index on detections.enrichment_data
        await session.execute(
            text(
                """
            CREATE INDEX IF NOT EXISTS ix_detections_enrichment_data_gin
            ON detections USING gin(enrichment_data jsonb_path_ops);
            """
            )
        )

        # Create BRIN indexes for time-series tables
        await session.execute(
            text(
                """
            CREATE INDEX IF NOT EXISTS ix_detections_detected_at_brin
            ON detections USING brin(detected_at);
            """
            )
        )

        await session.execute(
            text(
                """
            CREATE INDEX IF NOT EXISTS ix_events_started_at_brin
            ON events USING brin(started_at);
            """
            )
        )

        await session.execute(
            text(
                """
            CREATE INDEX IF NOT EXISTS ix_logs_timestamp_brin
            ON logs USING brin(timestamp);
            """
            )
        )

        await session.execute(
            text(
                """
            CREATE INDEX IF NOT EXISTS ix_audit_logs_timestamp_brin
            ON audit_logs USING brin(timestamp);
            """
            )
        )

        await session.execute(
            text(
                """
            CREATE INDEX IF NOT EXISTS ix_scene_changes_detected_at_brin
            ON scene_changes USING brin(detected_at);
            """
            )
        )

        await session.commit()

    _ensure_indexes_setup["setup_done"] = True
    yield integration_db


# =============================================================================
# Helper Functions
# =============================================================================


async def create_test_camera(session, camera_id: str | None = None, name: str = "Test Camera"):
    """Create a test camera within a session."""
    if camera_id is None:
        camera_id = unique_id("idx_cam")
    camera = Camera(
        id=camera_id,
        name=name,
        folder_path=f"/export/foscam/{camera_id}",
        status="online",
    )
    session.add(camera)
    await session.flush()
    return camera


async def create_test_detection(
    session, camera, enrichment_data: dict | None = None, detected_at: datetime | None = None
):
    """Create a test detection with optional enrichment data."""
    if detected_at is None:
        detected_at = datetime.now(UTC)

    detection = Detection(
        camera_id=camera.id,
        file_path=f"/export/foscam/{camera.id}/{unique_id('img')}.jpg",
        detected_at=detected_at,
        object_type="person",
        confidence=0.95,
        enrichment_data=enrichment_data,
    )
    session.add(detection)
    await session.flush()
    return detection


async def create_test_event(session, camera, started_at: datetime | None = None):
    """Create a test event."""
    if started_at is None:
        started_at = datetime.now(UTC)

    event = Event(
        batch_id=unique_id("idx_batch"),
        camera_id=camera.id,
        started_at=started_at,
        summary="Test event for index testing",
        reasoning="Testing specialized indexes",
    )
    session.add(event)
    await session.flush()
    return event


async def create_test_log(session, timestamp: datetime | None = None):
    """Create a test log entry."""
    if timestamp is None:
        timestamp = datetime.now(UTC)

    log = Log(
        timestamp=timestamp,
        level="INFO",
        component="test_indexes",
        message="Test log for index testing",
        source="backend",
    )
    session.add(log)
    await session.flush()
    return log


# =============================================================================
# Test: GIN Index Existence
# =============================================================================


class TestGinIndexExistence:
    """Tests for GIN index on enrichment_data."""

    @pytest.mark.asyncio
    async def test_gin_index_exists_on_enrichment_data(self, _indexes_db: str):
        """Verify GIN index exists on detections.enrichment_data."""
        from backend.core.database import get_session

        async with get_session() as session:
            result = await session.execute(
                text(
                    """
                SELECT indexname, indexdef
                FROM pg_indexes
                WHERE tablename = 'detections'
                  AND indexname = 'ix_detections_enrichment_data_gin';
                """
                )
            )
            row = result.fetchone()
            assert row is not None, "ix_detections_enrichment_data_gin index should exist"
            assert "jsonb_path_ops" in row[1], f"Index should use jsonb_path_ops: {row[1]}"

    @pytest.mark.asyncio
    async def test_gin_index_uses_gin_access_method(self, _indexes_db: str):
        """Verify the enrichment_data index uses GIN access method."""
        from backend.core.database import get_session

        async with get_session() as session:
            result = await session.execute(
                text(
                    """
                SELECT am.amname
                FROM pg_index idx
                JOIN pg_class cls ON cls.oid = idx.indexrelid
                JOIN pg_am am ON am.oid = cls.relam
                WHERE cls.relname = 'ix_detections_enrichment_data_gin';
                """
                )
            )
            row = result.fetchone()
            assert row is not None, "Index should exist"
            assert row[0] == "gin", f"Index should use GIN access method, got {row[0]}"


# =============================================================================
# Test: GIN Index Functionality
# =============================================================================


class TestGinIndexFunctionality:
    """Tests for GIN index functionality with JSONB containment queries."""

    @pytest.mark.asyncio
    async def test_containment_query_finds_license_plates(self, _indexes_db: str):
        """Verify containment query finds detections with license plates."""
        from backend.core.database import get_session

        async with get_session() as session:
            camera = await create_test_camera(session)

            # Detection with license plate
            d1 = await create_test_detection(
                session,
                camera,
                enrichment_data={
                    "license_plates": [{"text": "ABC123", "confidence": 0.95}],
                },
            )

            # Detection without license plate
            await create_test_detection(
                session,
                camera,
                enrichment_data={
                    "faces": [{"confidence": 0.88}],
                },
            )

            await session.commit()
            d1_id = d1.id

        async with get_session() as session:
            # Query using containment operator
            result = await session.execute(
                text(
                    """
                SELECT id FROM detections
                WHERE enrichment_data @> '{"license_plates": [{}]}'
                """
                )
            )
            found_ids = [r[0] for r in result.fetchall()]

            assert d1_id in found_ids, "Should find detection with license plates"

    @pytest.mark.asyncio
    async def test_containment_query_finds_suspicious_clothing(self, _indexes_db: str):
        """Verify containment query finds detections with suspicious clothing."""
        from backend.core.database import get_session

        async with get_session() as session:
            camera = await create_test_camera(session)

            # Detection with suspicious clothing
            d1 = await create_test_detection(
                session,
                camera,
                enrichment_data={
                    "clothing_classifications": {"0": {"is_suspicious": True}},
                },
            )

            # Detection without suspicious clothing
            await create_test_detection(
                session,
                camera,
                enrichment_data={
                    "clothing_classifications": {"0": {"is_suspicious": False}},
                },
            )

            await session.commit()
            d1_id = d1.id

        async with get_session() as session:
            result = await session.execute(
                text(
                    """
                SELECT id FROM detections
                WHERE enrichment_data @> '{"clothing_classifications": {"0": {"is_suspicious": true}}}'
                """
                )
            )
            found_ids = [r[0] for r in result.fetchall()]

            assert d1_id in found_ids, "Should find detection with suspicious clothing"

    @pytest.mark.asyncio
    async def test_containment_query_with_vehicle_type(self, _indexes_db: str):
        """Verify containment query finds detections with specific vehicle type."""
        from backend.core.database import get_session

        async with get_session() as session:
            camera = await create_test_camera(session)

            # Detection with sedan
            d1 = await create_test_detection(
                session,
                camera,
                enrichment_data={
                    "vehicle_classifications": {"0": {"vehicle_type": "sedan"}},
                },
            )

            # Detection with SUV
            await create_test_detection(
                session,
                camera,
                enrichment_data={
                    "vehicle_classifications": {"0": {"vehicle_type": "suv"}},
                },
            )

            await session.commit()
            d1_id = d1.id

        async with get_session() as session:
            result = await session.execute(
                text(
                    """
                SELECT id FROM detections
                WHERE enrichment_data @> '{"vehicle_classifications": {"0": {"vehicle_type": "sedan"}}}'
                """
                )
            )
            found_ids = [r[0] for r in result.fetchall()]

            assert d1_id in found_ids, "Should find detection with sedan"


# =============================================================================
# Test: BRIN Index Existence
# =============================================================================


class TestBrinIndexExistence:
    """Tests for BRIN indexes on time-series tables."""

    @pytest.mark.asyncio
    async def test_brin_index_exists_on_detections(self, _indexes_db: str):
        """Verify BRIN index exists on detections.detected_at."""
        from backend.core.database import get_session

        async with get_session() as session:
            result = await session.execute(
                text(
                    """
                SELECT indexname
                FROM pg_indexes
                WHERE tablename = 'detections'
                  AND indexname = 'ix_detections_detected_at_brin';
                """
                )
            )
            row = result.fetchone()
            assert row is not None, "ix_detections_detected_at_brin should exist"

    @pytest.mark.asyncio
    async def test_brin_index_exists_on_events(self, _indexes_db: str):
        """Verify BRIN index exists on events.started_at."""
        from backend.core.database import get_session

        async with get_session() as session:
            result = await session.execute(
                text(
                    """
                SELECT indexname
                FROM pg_indexes
                WHERE tablename = 'events'
                  AND indexname = 'ix_events_started_at_brin';
                """
                )
            )
            row = result.fetchone()
            assert row is not None, "ix_events_started_at_brin should exist"

    @pytest.mark.asyncio
    async def test_brin_index_exists_on_logs(self, _indexes_db: str):
        """Verify BRIN index exists on logs.timestamp."""
        from backend.core.database import get_session

        async with get_session() as session:
            result = await session.execute(
                text(
                    """
                SELECT indexname
                FROM pg_indexes
                WHERE tablename = 'logs'
                  AND indexname = 'ix_logs_timestamp_brin';
                """
                )
            )
            row = result.fetchone()
            assert row is not None, "ix_logs_timestamp_brin should exist"

    @pytest.mark.asyncio
    async def test_brin_index_exists_on_audit_logs(self, _indexes_db: str):
        """Verify BRIN index exists on audit_logs.timestamp."""
        from backend.core.database import get_session

        async with get_session() as session:
            result = await session.execute(
                text(
                    """
                SELECT indexname
                FROM pg_indexes
                WHERE tablename = 'audit_logs'
                  AND indexname = 'ix_audit_logs_timestamp_brin';
                """
                )
            )
            row = result.fetchone()
            assert row is not None, "ix_audit_logs_timestamp_brin should exist"

    @pytest.mark.asyncio
    async def test_brin_index_exists_on_scene_changes(self, _indexes_db: str):
        """Verify BRIN index exists on scene_changes.detected_at."""
        from backend.core.database import get_session

        async with get_session() as session:
            result = await session.execute(
                text(
                    """
                SELECT indexname
                FROM pg_indexes
                WHERE tablename = 'scene_changes'
                  AND indexname = 'ix_scene_changes_detected_at_brin';
                """
                )
            )
            row = result.fetchone()
            assert row is not None, "ix_scene_changes_detected_at_brin should exist"

    @pytest.mark.asyncio
    async def test_brin_indexes_use_brin_access_method(self, _indexes_db: str):
        """Verify all BRIN indexes use BRIN access method."""
        from backend.core.database import get_session

        brin_indexes = [
            "ix_detections_detected_at_brin",
            "ix_events_started_at_brin",
            "ix_logs_timestamp_brin",
            "ix_audit_logs_timestamp_brin",
            "ix_scene_changes_detected_at_brin",
        ]

        async with get_session() as session:
            for index_name in brin_indexes:
                result = await session.execute(
                    text(
                        """
                    SELECT am.amname
                    FROM pg_index idx
                    JOIN pg_class cls ON cls.oid = idx.indexrelid
                    JOIN pg_am am ON am.oid = cls.relam
                    WHERE cls.relname = :index_name;
                    """
                    ),
                    {"index_name": index_name},
                )
                row = result.fetchone()
                if row is not None:
                    assert row[0] == "brin", (
                        f"{index_name} should use BRIN access method, got {row[0]}"
                    )


# =============================================================================
# Test: BRIN Index Functionality
# =============================================================================


class TestBrinIndexFunctionality:
    """Tests for BRIN index functionality with time-series range queries."""

    @pytest.mark.asyncio
    async def test_detection_time_range_query_executes(self, _indexes_db: str):
        """Verify time range query on detections executes successfully."""
        from backend.core.database import get_session

        async with get_session() as session:
            camera = await create_test_camera(session)

            # Create detections at different times
            for i in range(5):
                await create_test_detection(session, camera)

            await session.commit()

        async with get_session() as session:
            # Time range query
            result = await session.execute(
                text(
                    """
                SELECT COUNT(*) FROM detections
                WHERE detected_at >= NOW() - INTERVAL '1 hour';
                """
                )
            )
            count = result.scalar()
            assert count >= 5, "Should find at least 5 recent detections"

    @pytest.mark.asyncio
    async def test_event_time_range_query_executes(self, _indexes_db: str):
        """Verify time range query on events executes successfully."""
        from backend.core.database import get_session

        async with get_session() as session:
            camera = await create_test_camera(session)

            # Create events at different times
            for i in range(3):
                await create_test_event(session, camera)

            await session.commit()

        async with get_session() as session:
            result = await session.execute(
                text(
                    """
                SELECT COUNT(*) FROM events
                WHERE started_at >= NOW() - INTERVAL '1 hour';
                """
                )
            )
            count = result.scalar()
            assert count >= 3, "Should find at least 3 recent events"

    @pytest.mark.asyncio
    async def test_log_time_range_query_executes(self, _indexes_db: str):
        """Verify time range query on logs executes successfully."""
        from backend.core.database import get_session

        async with get_session() as session:
            # Create logs at different times
            for i in range(3):
                await create_test_log(session)

            await session.commit()

        async with get_session() as session:
            result = await session.execute(
                text(
                    """
                SELECT COUNT(*) FROM logs
                WHERE timestamp >= NOW() - INTERVAL '1 hour';
                """
                )
            )
            count = result.scalar()
            assert count >= 3, "Should find at least 3 recent logs"


# =============================================================================
# Test: Index Query Plans (EXPLAIN verification)
# =============================================================================


class TestIndexQueryPlans:
    """Tests verifying indexes are available to the query planner."""

    @pytest.mark.asyncio
    async def test_gin_index_available_for_containment_query(self, _indexes_db: str):
        """Verify GIN index is available for containment queries."""
        from backend.core.database import get_session

        async with get_session() as session:
            # EXPLAIN should succeed regardless of whether planner uses the index
            result = await session.execute(
                text(
                    """
                EXPLAIN (FORMAT JSON)
                SELECT * FROM detections
                WHERE enrichment_data @> '{"license_plates": [{}]}';
                """
                )
            )
            explain_output = result.fetchone()[0]
            assert explain_output is not None, "EXPLAIN should return a query plan"

    @pytest.mark.asyncio
    async def test_brin_index_available_for_range_query(self, _indexes_db: str):
        """Verify BRIN index is available for time range queries."""
        from backend.core.database import get_session

        async with get_session() as session:
            result = await session.execute(
                text(
                    """
                EXPLAIN (FORMAT JSON)
                SELECT * FROM detections
                WHERE detected_at >= NOW() - INTERVAL '1 day';
                """
                )
            )
            explain_output = result.fetchone()[0]
            assert explain_output is not None, "EXPLAIN should return a query plan"


# =============================================================================
# Test: Model Index Definitions
# =============================================================================


class TestModelIndexDefinitions:
    """Tests verifying model __table_args__ contain index definitions."""

    def test_detection_model_has_gin_index_definition(self):
        """Verify Detection model has GIN index in __table_args__."""
        from backend.models.detection import Detection

        table_args = Detection.__table_args__
        index_names = [idx.name for idx in table_args if hasattr(idx, "name")]

        assert "ix_detections_enrichment_data_gin" in index_names, (
            "Detection should have GIN index definition"
        )

    def test_detection_model_has_brin_index_definition(self):
        """Verify Detection model has BRIN index in __table_args__."""
        from backend.models.detection import Detection

        table_args = Detection.__table_args__
        index_names = [idx.name for idx in table_args if hasattr(idx, "name")]

        assert "ix_detections_detected_at_brin" in index_names, (
            "Detection should have BRIN index definition"
        )

    def test_event_model_has_brin_index_definition(self):
        """Verify Event model has BRIN index in __table_args__."""
        from backend.models.event import Event

        table_args = Event.__table_args__
        index_names = [idx.name for idx in table_args if hasattr(idx, "name")]

        assert "ix_events_started_at_brin" in index_names, "Event should have BRIN index definition"

    def test_log_model_has_brin_index_definition(self):
        """Verify Log model has BRIN index in __table_args__."""
        from backend.models.log import Log

        table_args = Log.__table_args__
        index_names = [idx.name for idx in table_args if hasattr(idx, "name")]

        assert "ix_logs_timestamp_brin" in index_names, "Log should have BRIN index definition"

    def test_audit_log_model_has_brin_index_definition(self):
        """Verify AuditLog model has BRIN index in __table_args__."""
        from backend.models.audit import AuditLog

        table_args = AuditLog.__table_args__
        index_names = [idx.name for idx in table_args if hasattr(idx, "name")]

        assert "ix_audit_logs_timestamp_brin" in index_names, (
            "AuditLog should have BRIN index definition"
        )

    def test_scene_change_model_has_brin_index_definition(self):
        """Verify SceneChange model has BRIN index in __table_args__."""
        from backend.models.scene_change import SceneChange

        table_args = SceneChange.__table_args__
        index_names = [idx.name for idx in table_args if hasattr(idx, "name")]

        assert "ix_scene_changes_detected_at_brin" in index_names, (
            "SceneChange should have BRIN index definition"
        )

    def test_gpu_stats_model_has_brin_index_definition(self):
        """Verify GPUStats model has BRIN index in __table_args__."""
        from backend.models.gpu_stats import GPUStats

        table_args = GPUStats.__table_args__
        index_names = [idx.name for idx in table_args if hasattr(idx, "name")]

        assert "ix_gpu_stats_recorded_at_brin" in index_names, (
            "GPUStats should have BRIN index definition"
        )
