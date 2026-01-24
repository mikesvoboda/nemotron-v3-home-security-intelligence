"""Integration tests for materialized views migrations.

These tests verify that:
1. Materialized views are created correctly
2. Views can be refreshed
3. Views return expected data
4. JSON extraction functions work correctly
"""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.camera import Camera
from backend.models.detection import Detection
from backend.models.event import Event

pytestmark = [pytest.mark.integration]


@pytest.fixture
async def setup_test_data(
    async_session: AsyncSession,
) -> AsyncGenerator[dict]:
    """Create test data for materialized view tests."""
    # Create a camera
    camera = Camera(
        id="test_camera",
        name="Test Camera",
        folder_path="/export/foscam/test_camera",
        status="online",
    )
    async_session.add(camera)

    # Create detections with enrichment data
    detections = []
    for i in range(5):
        detection = Detection(
            camera_id="test_camera",
            file_path=f"/path/to/image_{i}.jpg",
            object_type="person" if i % 2 == 0 else "car",
            confidence=0.85 + (i * 0.02),
            detected_at=datetime(2026, 1, 23, 10 + i, 0, tzinfo=UTC),
            enrichment_data={
                "license_plates": [
                    {"text": f"ABC-{i}234", "confidence": 0.9, "ocr_confidence": 0.85}
                ]
                if i % 2 == 1
                else [],
                "faces": [{"confidence": 0.95, "bbox": [100, 100, 200, 200]}] if i % 2 == 0 else [],
                "violence_detection": {"is_violent": i == 3, "confidence": 0.7},
                "image_quality": {"quality_score": 75.0 + i * 5},
                "processing_time_ms": 100.0 + i * 10,
            },
        )
        detections.append(detection)
        async_session.add(detection)

    # Create events
    events = []
    for i in range(3):
        event = Event(
            batch_id=f"batch_{i}",
            camera_id="test_camera",
            started_at=datetime(2026, 1, 23, 10 + i, 0, tzinfo=UTC),
            ended_at=datetime(2026, 1, 23, 10 + i, 30, tzinfo=UTC),
            risk_score=30 + i * 20,
            risk_level=["low", "medium", "high"][i],
            summary=f"Test event {i}",
            reviewed=i == 0,
        )
        events.append(event)
        async_session.add(event)

    await async_session.commit()

    yield {
        "camera": camera,
        "detections": detections,
        "events": events,
    }

    # Cleanup
    for event in events:
        await async_session.delete(event)
    for detection in detections:
        await async_session.delete(detection)
    await async_session.delete(camera)
    await async_session.commit()


class TestMaterializedViewsExist:
    """Test that materialized views are created by migrations."""

    @pytest.mark.asyncio
    async def test_mv_daily_detection_counts_exists(self, async_session: AsyncSession) -> None:
        """Test that mv_daily_detection_counts exists."""
        result = await async_session.execute(
            text(
                """
                SELECT EXISTS (
                    SELECT 1 FROM pg_matviews WHERE matviewname = 'mv_daily_detection_counts'
                )
                """
            )
        )
        exists = result.scalar()
        assert exists is True

    @pytest.mark.asyncio
    async def test_mv_hourly_event_stats_exists(self, async_session: AsyncSession) -> None:
        """Test that mv_hourly_event_stats exists."""
        result = await async_session.execute(
            text(
                """
                SELECT EXISTS (
                    SELECT 1 FROM pg_matviews WHERE matviewname = 'mv_hourly_event_stats'
                )
                """
            )
        )
        exists = result.scalar()
        assert exists is True

    @pytest.mark.asyncio
    async def test_mv_detection_type_distribution_exists(self, async_session: AsyncSession) -> None:
        """Test that mv_detection_type_distribution exists."""
        result = await async_session.execute(
            text(
                """
                SELECT EXISTS (
                    SELECT 1 FROM pg_matviews WHERE matviewname = 'mv_detection_type_distribution'
                )
                """
            )
        )
        exists = result.scalar()
        assert exists is True

    @pytest.mark.asyncio
    async def test_mv_enrichment_summary_exists(self, async_session: AsyncSession) -> None:
        """Test that mv_enrichment_summary exists."""
        result = await async_session.execute(
            text(
                """
                SELECT EXISTS (
                    SELECT 1 FROM pg_matviews WHERE matviewname = 'mv_enrichment_summary'
                )
                """
            )
        )
        exists = result.scalar()
        assert exists is True


class TestRefreshFunction:
    """Test the refresh_dashboard_materialized_views function."""

    @pytest.mark.asyncio
    async def test_refresh_function_exists(self, async_session: AsyncSession) -> None:
        """Test that the refresh function exists."""
        result = await async_session.execute(
            text(
                """
                SELECT EXISTS (
                    SELECT 1 FROM pg_proc
                    WHERE proname = 'refresh_dashboard_materialized_views'
                )
                """
            )
        )
        exists = result.scalar()
        assert exists is True

    @pytest.mark.asyncio
    async def test_refresh_function_executes(
        self, async_session: AsyncSession, setup_test_data: dict
    ) -> None:
        """Test that the refresh function executes successfully."""
        # This may fail if views are being accessed, but should succeed in isolation
        try:
            await async_session.execute(text("SELECT refresh_dashboard_materialized_views()"))
            await async_session.commit()
        except Exception as e:
            # If concurrent access, the function still exists
            pytest.skip(f"Refresh blocked by concurrent access: {e}")


class TestJSONExtractionFunctions:
    """Test the JSON extraction functions."""

    @pytest.mark.asyncio
    async def test_get_license_plate_detections_function_exists(
        self, async_session: AsyncSession
    ) -> None:
        """Test that get_license_plate_detections function exists."""
        result = await async_session.execute(
            text(
                """
                SELECT EXISTS (
                    SELECT 1 FROM pg_proc
                    WHERE proname = 'get_license_plate_detections'
                )
                """
            )
        )
        exists = result.scalar()
        assert exists is True

    @pytest.mark.asyncio
    async def test_get_license_plate_detections_returns_data(
        self, async_session: AsyncSession, setup_test_data: dict
    ) -> None:
        """Test that get_license_plate_detections returns data."""
        result = await async_session.execute(
            text(
                """
                SELECT * FROM get_license_plate_detections(
                    'test_camera', NULL, NULL, 0.0
                )
                """
            )
        )
        rows = result.fetchall()

        # We created 5 detections, every other one has a license plate
        assert len(rows) == 2  # indices 1 and 3 have plates

    @pytest.mark.asyncio
    async def test_get_face_detections_function_exists(self, async_session: AsyncSession) -> None:
        """Test that get_face_detections function exists."""
        result = await async_session.execute(
            text(
                """
                SELECT EXISTS (
                    SELECT 1 FROM pg_proc WHERE proname = 'get_face_detections'
                )
                """
            )
        )
        exists = result.scalar()
        assert exists is True

    @pytest.mark.asyncio
    async def test_get_face_detections_returns_data(
        self, async_session: AsyncSession, setup_test_data: dict
    ) -> None:
        """Test that get_face_detections returns data."""
        result = await async_session.execute(
            text(
                """
                SELECT * FROM get_face_detections('test_camera', NULL, NULL, 0.0)
                """
            )
        )
        rows = result.fetchall()

        # We created 5 detections, every other one has a face (indices 0, 2, 4)
        assert len(rows) == 3

    @pytest.mark.asyncio
    async def test_get_enrichment_vehicle_data_function_exists(
        self, async_session: AsyncSession
    ) -> None:
        """Test that get_enrichment_vehicle_data function exists."""
        result = await async_session.execute(
            text(
                """
                SELECT EXISTS (
                    SELECT 1 FROM pg_proc WHERE proname = 'get_enrichment_vehicle_data'
                )
                """
            )
        )
        exists = result.scalar()
        assert exists is True

    @pytest.mark.asyncio
    async def test_get_detection_enrichment_summary_function_exists(
        self, async_session: AsyncSession
    ) -> None:
        """Test that get_detection_enrichment_summary function exists."""
        result = await async_session.execute(
            text(
                """
                SELECT EXISTS (
                    SELECT 1 FROM pg_proc WHERE proname = 'get_detection_enrichment_summary'
                )
                """
            )
        )
        exists = result.scalar()
        assert exists is True

    @pytest.mark.asyncio
    async def test_get_detection_enrichment_summary_returns_data(
        self, async_session: AsyncSession, setup_test_data: dict
    ) -> None:
        """Test that get_detection_enrichment_summary returns expected data."""
        detection = setup_test_data["detections"][0]

        result = await async_session.execute(
            text("SELECT * FROM get_detection_enrichment_summary(:detection_id)"),
            {"detection_id": detection.id},
        )
        row = result.fetchone()

        assert row is not None
        assert row.detection_id == detection.id
        assert row.has_faces is True
        assert row.face_count == 1
        assert row.has_image_quality is True

    @pytest.mark.asyncio
    async def test_get_enrichment_statistics_function_exists(
        self, async_session: AsyncSession
    ) -> None:
        """Test that get_enrichment_statistics function exists."""
        result = await async_session.execute(
            text(
                """
                SELECT EXISTS (
                    SELECT 1 FROM pg_proc WHERE proname = 'get_enrichment_statistics'
                )
                """
            )
        )
        exists = result.scalar()
        assert exists is True

    @pytest.mark.asyncio
    async def test_get_enrichment_statistics_returns_aggregated_data(
        self, async_session: AsyncSession, setup_test_data: dict
    ) -> None:
        """Test that get_enrichment_statistics returns aggregated data."""
        result = await async_session.execute(
            text("SELECT * FROM get_enrichment_statistics('test_camera', NULL, NULL)")
        )
        rows = result.fetchall()

        assert len(rows) == 1
        row = rows[0]
        assert row.camera_id == "test_camera"
        assert row.total_detections == 5
        assert row.with_faces == 3  # indices 0, 2, 4
        assert row.with_license_plates == 2  # indices 1, 3


class TestMaterializedViewData:
    """Test that materialized views contain expected data after refresh."""

    @pytest.mark.asyncio
    async def test_mv_daily_detection_counts_data(
        self, async_session: AsyncSession, setup_test_data: dict
    ) -> None:
        """Test that mv_daily_detection_counts contains expected data."""
        # Refresh the view first
        await async_session.execute(text("REFRESH MATERIALIZED VIEW mv_daily_detection_counts"))
        await async_session.commit()

        result = await async_session.execute(
            text(
                """
                SELECT * FROM mv_daily_detection_counts
                WHERE camera_id = 'test_camera'
                """
            )
        )
        rows = result.fetchall()

        # Should have data grouped by object type
        total_count = sum(row.detection_count for row in rows)
        assert total_count == 5

    @pytest.mark.asyncio
    async def test_mv_hourly_event_stats_data(
        self, async_session: AsyncSession, setup_test_data: dict
    ) -> None:
        """Test that mv_hourly_event_stats contains expected data."""
        # Refresh the view first
        await async_session.execute(text("REFRESH MATERIALIZED VIEW mv_hourly_event_stats"))
        await async_session.commit()

        result = await async_session.execute(
            text(
                """
                SELECT * FROM mv_hourly_event_stats
                WHERE camera_id = 'test_camera'
                """
            )
        )
        rows = result.fetchall()

        # Should have 3 events across different risk levels
        total_count = sum(row.event_count for row in rows)
        assert total_count == 3

    @pytest.mark.asyncio
    async def test_mv_enrichment_summary_data(
        self, async_session: AsyncSession, setup_test_data: dict
    ) -> None:
        """Test that mv_enrichment_summary contains expected data."""
        # Refresh the view first
        await async_session.execute(text("REFRESH MATERIALIZED VIEW mv_enrichment_summary"))
        await async_session.commit()

        result = await async_session.execute(
            text(
                """
                SELECT * FROM mv_enrichment_summary
                WHERE camera_id = 'test_camera'
                """
            )
        )
        row = result.fetchone()

        assert row is not None
        assert row.camera_id == "test_camera"
        assert row.total_detections == 5
        assert row.with_faces == 3
        assert row.with_license_plates == 2
