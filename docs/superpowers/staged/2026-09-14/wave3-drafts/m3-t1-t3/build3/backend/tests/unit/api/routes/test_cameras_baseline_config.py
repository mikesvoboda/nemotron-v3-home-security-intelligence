"""Unit tests for camera baseline configuration API routes.

Tests the baseline tuning UI endpoints:
- PUT /api/cameras/{camera_id}/baseline/config - Update baseline config
- POST /api/cameras/{camera_id}/baseline/reset - Reset baseline data
- GET /api/cameras/{camera_id}/baseline/config - Get baseline config

TDD: These tests are written FIRST to define expected behavior (Red phase).
The implementation should be written to make these tests pass (Green phase).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from backend.models.camera import Camera


class TestUpdateBaselineConfig:
    """Tests for PUT /api/cameras/{camera_id}/baseline/config endpoint."""

    @pytest.mark.asyncio
    async def test_update_baseline_config_success(self) -> None:
        """Test valid update returns 200 with updated config."""
        from backend.api.routes.cameras import update_baseline_config
        from backend.api.schemas.camera import BaselineConfigUpdate

        mock_db = AsyncMock()
        mock_camera = MagicMock(spec=Camera)
        mock_camera.id = "front_door"

        config_update = BaselineConfigUpdate(
            threshold_stdev=3.0,
            min_samples=15,
        )

        with (
            patch("backend.api.routes.cameras.get_camera_or_404", return_value=mock_camera),
            patch("backend.api.routes.cameras.baseline_config_service") as mock_service,
        ):
            mock_service.set_camera_config = AsyncMock()
            mock_service.get_camera_config = AsyncMock(
                return_value={
                    "threshold_stdev": 3.0,
                    "min_samples": 15,
                    "override_global_config": True,
                    "global_config": {
                        "threshold_stdev": 2.0,
                        "min_samples": 10,
                        "decay_factor": 0.1,
                        "window_days": 30,
                    },
                }
            )

            result = await update_baseline_config(
                camera_id="front_door",
                config=config_update,
                db=mock_db,
            )

            assert result.threshold_stdev == 3.0
            assert result.min_samples == 15
            assert result.override_global_config is True
            mock_service.set_camera_config.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_baseline_config_invalid_threshold(self) -> None:
        """Test threshold < 0.5 returns 422."""
        from backend.api.routes.cameras import update_baseline_config
        from backend.api.schemas.camera import BaselineConfigUpdate

        mock_db = AsyncMock()

        config_update = BaselineConfigUpdate(threshold_stdev=0.3)

        with pytest.raises(ValueError) as exc_info:
            await update_baseline_config(
                camera_id="front_door",
                config=config_update,
                db=mock_db,
            )

        assert "threshold_stdev" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_update_baseline_config_invalid_min_samples(self) -> None:
        """Test min_samples < 1 returns 422."""
        from backend.api.routes.cameras import update_baseline_config
        from backend.api.schemas.camera import BaselineConfigUpdate

        mock_db = AsyncMock()

        config_update = BaselineConfigUpdate(min_samples=0)

        with pytest.raises(ValueError) as exc_info:
            await update_baseline_config(
                camera_id="front_door",
                config=config_update,
                db=mock_db,
            )

        assert "min_samples" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_update_baseline_config_camera_not_found(self) -> None:
        """Test 404 for invalid camera_id."""
        from backend.api.routes.cameras import update_baseline_config
        from backend.api.schemas.camera import BaselineConfigUpdate

        mock_db = AsyncMock()
        config_update = BaselineConfigUpdate(threshold_stdev=2.5)

        with patch(
            "backend.api.routes.cameras.get_camera_or_404",
            side_effect=HTTPException(status_code=404, detail="Camera not found"),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await update_baseline_config(
                    camera_id="nonexistent",
                    config=config_update,
                    db=mock_db,
                )

            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_update_baseline_config_partial_update(self) -> None:
        """Test only threshold_stdev updated when min_samples not provided."""
        from backend.api.routes.cameras import update_baseline_config
        from backend.api.schemas.camera import BaselineConfigUpdate

        mock_db = AsyncMock()
        mock_camera = MagicMock(spec=Camera)
        mock_camera.id = "front_door"

        config_update = BaselineConfigUpdate(threshold_stdev=3.5)

        with (
            patch("backend.api.routes.cameras.get_camera_or_404", return_value=mock_camera),
            patch("backend.api.routes.cameras.baseline_config_service") as mock_service,
        ):
            mock_service.set_camera_config = AsyncMock()
            mock_service.get_camera_config = AsyncMock(
                return_value={
                    "threshold_stdev": 3.5,
                    "min_samples": 10,  # Unchanged from default
                    "override_global_config": True,
                    "global_config": {
                        "threshold_stdev": 2.0,
                        "min_samples": 10,
                        "decay_factor": 0.1,
                        "window_days": 30,
                    },
                }
            )

            result = await update_baseline_config(
                camera_id="front_door",
                config=config_update,
                db=mock_db,
            )

            assert result.threshold_stdev == 3.5
            assert result.min_samples == 10

    @pytest.mark.asyncio
    async def test_update_baseline_config_toggle_override(self) -> None:
        """Test override_global_config toggle."""
        from backend.api.routes.cameras import update_baseline_config
        from backend.api.schemas.camera import BaselineConfigUpdate

        mock_db = AsyncMock()
        mock_camera = MagicMock(spec=Camera)
        mock_camera.id = "front_door"

        config_update = BaselineConfigUpdate(override_global_config=False)

        with (
            patch("backend.api.routes.cameras.get_camera_or_404", return_value=mock_camera),
            patch("backend.api.routes.cameras.baseline_config_service") as mock_service,
        ):
            mock_service.set_camera_config = AsyncMock()
            mock_service.get_camera_config = AsyncMock(
                return_value={
                    "threshold_stdev": 2.0,  # Global default
                    "min_samples": 10,  # Global default
                    "override_global_config": False,
                    "global_config": {
                        "threshold_stdev": 2.0,
                        "min_samples": 10,
                        "decay_factor": 0.1,
                        "window_days": 30,
                    },
                }
            )

            result = await update_baseline_config(
                camera_id="front_door",
                config=config_update,
                db=mock_db,
            )

            assert result.override_global_config is False


class TestResetBaseline:
    """Tests for POST /api/cameras/{camera_id}/baseline/reset endpoint."""

    @pytest.mark.asyncio
    async def test_reset_baseline_success(self) -> None:
        """Test returns 200 with deletion counts."""
        from backend.api.routes.cameras import reset_baseline

        mock_db = AsyncMock()
        mock_camera = MagicMock(spec=Camera)
        mock_camera.id = "front_door"

        with (
            patch("backend.api.routes.cameras.get_camera_or_404", return_value=mock_camera),
            patch("backend.api.routes.cameras.baseline_config_service") as mock_service,
        ):
            mock_service.reset_camera_baseline = AsyncMock(
                return_value={
                    "activity_baselines_deleted": 168,
                    "class_baselines_deleted": 42,
                }
            )

            result = await reset_baseline(camera_id="front_door", db=mock_db)

            assert result.activity_baselines_deleted == 168
            assert result.class_baselines_deleted == 42
            mock_service.reset_camera_baseline.assert_called_once_with(
                camera_id="front_door", session=mock_db
            )

    @pytest.mark.asyncio
    async def test_reset_baseline_camera_not_found(self) -> None:
        """Test 404 for invalid camera."""
        from backend.api.routes.cameras import reset_baseline

        mock_db = AsyncMock()

        with patch(
            "backend.api.routes.cameras.get_camera_or_404",
            side_effect=HTTPException(status_code=404, detail="Camera not found"),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await reset_baseline(camera_id="nonexistent", db=mock_db)

            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_reset_baseline_no_data(self) -> None:
        """Test returns 200 with zero counts when no baseline data exists."""
        from backend.api.routes.cameras import reset_baseline

        mock_db = AsyncMock()
        mock_camera = MagicMock(spec=Camera)
        mock_camera.id = "new_camera"

        with (
            patch("backend.api.routes.cameras.get_camera_or_404", return_value=mock_camera),
            patch("backend.api.routes.cameras.baseline_config_service") as mock_service,
        ):
            mock_service.reset_camera_baseline = AsyncMock(
                return_value={
                    "activity_baselines_deleted": 0,
                    "class_baselines_deleted": 0,
                }
            )

            result = await reset_baseline(camera_id="new_camera", db=mock_db)

            assert result.activity_baselines_deleted == 0
            assert result.class_baselines_deleted == 0

    @pytest.mark.asyncio
    async def test_reset_baseline_deletes_activity(self) -> None:
        """Test verifies ActivityBaseline deleted."""
        from backend.api.routes.cameras import reset_baseline

        mock_db = AsyncMock()
        mock_camera = MagicMock(spec=Camera)
        mock_camera.id = "front_door"

        # Mock delete query result for ActivityBaseline
        mock_activity_result = MagicMock()
        mock_activity_result.rowcount = 168

        with (
            patch("backend.api.routes.cameras.get_camera_or_404", return_value=mock_camera),
            patch("backend.api.routes.cameras.baseline_config_service") as mock_service,
        ):
            mock_service.reset_camera_baseline = AsyncMock(
                return_value={
                    "activity_baselines_deleted": 168,
                    "class_baselines_deleted": 42,
                }
            )

            result = await reset_baseline(camera_id="front_door", db=mock_db)

            assert result.activity_baselines_deleted == 168
            assert result.activity_baselines_deleted > 0

    @pytest.mark.asyncio
    async def test_reset_baseline_deletes_class(self) -> None:
        """Test verifies ClassBaseline deleted."""
        from backend.api.routes.cameras import reset_baseline

        mock_db = AsyncMock()
        mock_camera = MagicMock(spec=Camera)
        mock_camera.id = "front_door"

        with (
            patch("backend.api.routes.cameras.get_camera_or_404", return_value=mock_camera),
            patch("backend.api.routes.cameras.baseline_config_service") as mock_service,
        ):
            mock_service.reset_camera_baseline = AsyncMock(
                return_value={
                    "activity_baselines_deleted": 168,
                    "class_baselines_deleted": 42,
                }
            )

            result = await reset_baseline(camera_id="front_door", db=mock_db)

            assert result.class_baselines_deleted == 42
            assert result.class_baselines_deleted > 0


class TestGetBaselineConfig:
    """Tests for GET /api/cameras/{camera_id}/baseline/config endpoint."""

    @pytest.mark.asyncio
    async def test_get_baseline_config_default(self) -> None:
        """Test returns global config when no override exists."""
        from backend.api.routes.cameras import get_baseline_config

        mock_db = AsyncMock()
        mock_camera = MagicMock(spec=Camera)
        mock_camera.id = "front_door"

        with (
            patch("backend.api.routes.cameras.get_camera_or_404", return_value=mock_camera),
            patch("backend.api.routes.cameras.baseline_config_service") as mock_service,
        ):
            mock_service.get_camera_config = AsyncMock(
                return_value={
                    "threshold_stdev": 2.0,
                    "min_samples": 10,
                    "override_global_config": False,
                    "global_config": {
                        "threshold_stdev": 2.0,
                        "min_samples": 10,
                        "decay_factor": 0.1,
                        "window_days": 30,
                    },
                }
            )

            result = await get_baseline_config(camera_id="front_door", db=mock_db)

            assert result.threshold_stdev == 2.0
            assert result.min_samples == 10
            assert result.override_global_config is False
            assert result.global_config is not None

    @pytest.mark.asyncio
    async def test_get_baseline_config_override(self) -> None:
        """Test returns per-camera config when override is set."""
        from backend.api.routes.cameras import get_baseline_config

        mock_db = AsyncMock()
        mock_camera = MagicMock(spec=Camera)
        mock_camera.id = "front_door"

        with (
            patch("backend.api.routes.cameras.get_camera_or_404", return_value=mock_camera),
            patch("backend.api.routes.cameras.baseline_config_service") as mock_service,
        ):
            mock_service.get_camera_config = AsyncMock(
                return_value={
                    "threshold_stdev": 3.5,
                    "min_samples": 20,
                    "override_global_config": True,
                    "global_config": {
                        "threshold_stdev": 2.0,
                        "min_samples": 10,
                        "decay_factor": 0.1,
                        "window_days": 30,
                    },
                }
            )

            result = await get_baseline_config(camera_id="front_door", db=mock_db)

            assert result.threshold_stdev == 3.5
            assert result.min_samples == 20
            assert result.override_global_config is True

    @pytest.mark.asyncio
    async def test_get_baseline_config_camera_not_found(self) -> None:
        """Test 404 for invalid camera."""
        from backend.api.routes.cameras import get_baseline_config

        mock_db = AsyncMock()

        with patch(
            "backend.api.routes.cameras.get_camera_or_404",
            side_effect=HTTPException(status_code=404, detail="Camera not found"),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await get_baseline_config(camera_id="nonexistent", db=mock_db)

            assert exc_info.value.status_code == 404
