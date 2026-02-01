"""Integration tests for baseline configuration service.

Tests cover:
- Camera config get/set operations with database
- Baseline reset operations that delete real database records
- Per-camera override vs global config behavior

NEM-4921: Baseline Tuning UI - Phase 3
"""

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.baseline import ActivityBaseline, ClassBaseline
from backend.models.camera import Camera
from backend.services.baseline_config import (
    BaselineConfigService,
    _camera_configs,
)

# Mark as integration since tests require real PostgreSQL database
pytestmark = pytest.mark.integration


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def baseline_config_service():
    """Create baseline config service instance."""
    return BaselineConfigService()


@pytest.fixture(autouse=True)
def clear_camera_configs():
    """Clear in-memory camera configs before and after each test."""
    _camera_configs.clear()
    yield
    _camera_configs.clear()


async def create_test_camera(session: AsyncSession, camera_id: str) -> Camera:
    """Helper function to create a test camera in the database.

    Args:
        session: Database session
        camera_id: ID for the camera

    Returns:
        Created Camera instance
    """
    camera = Camera(
        id=camera_id,
        name=f"Test Camera {camera_id}",
        folder_path=f"/export/test/{camera_id}",
    )
    session.add(camera)
    await session.commit()
    return camera


# ============================================================================
# Camera Config Tests
# ============================================================================


class TestGetCameraConfig:
    """Tests for get_camera_config method."""

    @pytest.mark.asyncio
    async def test_get_config_returns_global_defaults(
        self, baseline_config_service: BaselineConfigService
    ):
        """Get config for camera without override returns global defaults."""
        config = await baseline_config_service.get_camera_config("test_camera")

        assert "threshold_stdev" in config
        assert "min_samples" in config
        assert "override_global_config" in config
        assert config["override_global_config"] is False
        assert "global_config" in config

    @pytest.mark.asyncio
    async def test_get_config_with_override(self, baseline_config_service: BaselineConfigService):
        """Get config for camera with override returns custom values."""
        # Set custom config first
        await baseline_config_service.set_camera_config(
            "test_camera",
            threshold_stdev=3.5,
            min_samples=20,
            override_global_config=True,
        )

        config = await baseline_config_service.get_camera_config("test_camera")

        assert config["threshold_stdev"] == 3.5
        assert config["min_samples"] == 20
        assert config["override_global_config"] is True


class TestSetCameraConfig:
    """Tests for set_camera_config method."""

    @pytest.mark.asyncio
    async def test_set_config_persists_values(self, baseline_config_service: BaselineConfigService):
        """Set camera config persists values in memory."""
        await baseline_config_service.set_camera_config(
            "test_camera",
            threshold_stdev=2.5,
            min_samples=15,
            override_global_config=True,
        )

        config = await baseline_config_service.get_camera_config("test_camera")
        assert config["threshold_stdev"] == 2.5
        assert config["min_samples"] == 15
        assert config["override_global_config"] is True

    @pytest.mark.asyncio
    async def test_set_config_partial_update(self, baseline_config_service: BaselineConfigService):
        """Set camera config allows partial updates."""
        # Set initial config
        await baseline_config_service.set_camera_config(
            "test_camera",
            threshold_stdev=3.0,
            min_samples=20,
            override_global_config=True,
        )

        # Partial update - only threshold
        await baseline_config_service.set_camera_config(
            "test_camera",
            threshold_stdev=4.0,
        )

        config = await baseline_config_service.get_camera_config("test_camera")
        assert config["threshold_stdev"] == 4.0
        assert config["min_samples"] == 20  # Unchanged

    @pytest.mark.asyncio
    async def test_set_config_validates_threshold_min(
        self, baseline_config_service: BaselineConfigService
    ):
        """Set camera config rejects threshold below 0.5."""
        with pytest.raises(ValueError, match="at least 0.5"):
            await baseline_config_service.set_camera_config(
                "test_camera",
                threshold_stdev=0.3,
            )

    @pytest.mark.asyncio
    async def test_set_config_validates_min_samples(
        self, baseline_config_service: BaselineConfigService
    ):
        """Set camera config rejects min_samples below 1."""
        with pytest.raises(ValueError, match="at least 1"):
            await baseline_config_service.set_camera_config(
                "test_camera",
                min_samples=0,
            )


# ============================================================================
# Reset Baseline Tests (requires real database)
# ============================================================================


class TestResetCameraBaseline:
    """Tests for reset_camera_baseline method with real database."""

    @pytest.mark.asyncio
    async def test_reset_baseline_deletes_activity_records(
        self,
        baseline_config_service: BaselineConfigService,
        db_session: AsyncSession,
    ):
        """Reset baseline deletes ActivityBaseline records for camera."""
        camera_id = "integration_test_camera"

        # Create camera first (required for foreign key constraint)
        await create_test_camera(db_session, camera_id)

        # Create test activity baseline records
        for hour in range(3):
            baseline = ActivityBaseline(
                camera_id=camera_id,
                day_of_week=1,
                hour=hour,
                avg_count=10.0,
                sample_count=50,
                last_updated=datetime.now(UTC),
            )
            db_session.add(baseline)
        await db_session.commit()

        # Reset baseline
        result = await baseline_config_service.reset_camera_baseline(
            camera_id=camera_id,
            session=db_session,
        )

        assert result["activity_baselines_deleted"] == 3

    @pytest.mark.asyncio
    async def test_reset_baseline_deletes_class_records(
        self,
        baseline_config_service: BaselineConfigService,
        db_session: AsyncSession,
    ):
        """Reset baseline deletes ClassBaseline records for camera."""
        camera_id = "integration_test_camera_2"

        # Create camera first (required for foreign key constraint)
        await create_test_camera(db_session, camera_id)

        # Create test class baseline records
        for detection_class_name in ["person", "car", "dog"]:
            baseline = ClassBaseline(
                camera_id=camera_id,
                detection_class=detection_class_name,
                hour=12,
                frequency=5.0,
                sample_count=30,
                last_updated=datetime.now(UTC),
            )
            db_session.add(baseline)
        await db_session.commit()

        # Reset baseline
        result = await baseline_config_service.reset_camera_baseline(
            camera_id=camera_id,
            session=db_session,
        )

        assert result["class_baselines_deleted"] == 3

    @pytest.mark.asyncio
    async def test_reset_baseline_returns_zero_for_no_data(
        self,
        baseline_config_service: BaselineConfigService,
        db_session: AsyncSession,
    ):
        """Reset baseline returns zero counts when no data exists."""
        result = await baseline_config_service.reset_camera_baseline(
            camera_id="nonexistent_camera",
            session=db_session,
        )

        assert result["activity_baselines_deleted"] == 0
        assert result["class_baselines_deleted"] == 0

    @pytest.mark.asyncio
    async def test_reset_baseline_only_affects_target_camera(
        self,
        baseline_config_service: BaselineConfigService,
        db_session: AsyncSession,
    ):
        """Reset baseline only deletes records for specified camera."""
        target_camera = "target_camera"
        other_camera = "other_camera"

        # Create cameras first (required for foreign key constraint)
        await create_test_camera(db_session, target_camera)
        await create_test_camera(db_session, other_camera)

        # Create records for both cameras
        for camera_id in [target_camera, other_camera]:
            baseline = ActivityBaseline(
                camera_id=camera_id,
                day_of_week=1,
                hour=10,
                avg_count=10.0,
                sample_count=50,
                last_updated=datetime.now(UTC),
            )
            db_session.add(baseline)
        await db_session.commit()

        # Reset only target camera
        result = await baseline_config_service.reset_camera_baseline(
            camera_id=target_camera,
            session=db_session,
        )

        assert result["activity_baselines_deleted"] == 1

        # Verify other camera's data is intact
        from sqlalchemy import select

        stmt = select(ActivityBaseline).where(ActivityBaseline.camera_id == other_camera)
        result = await db_session.execute(stmt)
        remaining = result.scalars().all()
        assert len(remaining) == 1


# ============================================================================
# Clear Camera Config Tests
# ============================================================================


class TestClearCameraConfig:
    """Tests for clear_camera_config method."""

    def test_clear_config_removes_override(self, baseline_config_service: BaselineConfigService):
        """Clear camera config removes per-camera settings."""
        # Set config first (synchronously add to dict)
        _camera_configs["test_camera"] = {
            "threshold_stdev": 3.0,
            "min_samples": 20,
            "override_global_config": True,
        }

        baseline_config_service.clear_camera_config("test_camera")

        assert "test_camera" not in _camera_configs

    def test_clear_config_noop_for_nonexistent(
        self, baseline_config_service: BaselineConfigService
    ):
        """Clear camera config does nothing for nonexistent camera."""
        # Should not raise
        baseline_config_service.clear_camera_config("nonexistent_camera")
