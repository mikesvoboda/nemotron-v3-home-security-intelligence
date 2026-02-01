"""Unit tests for baseline configuration service.

Tests the service layer that manages per-camera baseline configurations
and handles baseline data reset operations.

TDD: These tests are written FIRST to define expected behavior (Red phase).
The implementation should be written to make these tests pass (Green phase).
"""

from unittest.mock import MagicMock

import pytest


class TestGetCameraConfig:
    """Tests for get_camera_config method."""

    @pytest.mark.asyncio
    async def test_get_camera_config_no_override(self) -> None:
        """Test returns global defaults when no camera-specific config exists."""
        from backend.services.baseline_config import BaselineConfigService, _camera_configs

        # Clear any existing config
        _camera_configs.clear()

        service = BaselineConfigService()
        config = await service.get_camera_config("camera-1")

        assert config["threshold_stdev"] == 2.0  # Global default
        assert config["min_samples"] == 10  # Global default
        assert config["override_global_config"] is False
        assert "global_config" in config

    @pytest.mark.asyncio
    async def test_get_camera_config_with_override(self) -> None:
        """Test returns per-camera values when override exists."""
        from backend.services.baseline_config import BaselineConfigService, _camera_configs

        # Setup in-memory override
        _camera_configs.clear()
        _camera_configs["camera-1"] = {
            "threshold_stdev": 3.5,
            "min_samples": 20,
            "override_global_config": True,
        }

        service = BaselineConfigService()
        config = await service.get_camera_config("camera-1")

        assert config["threshold_stdev"] == 3.5
        assert config["min_samples"] == 20
        assert config["override_global_config"] is True


class TestSetCameraConfig:
    """Tests for set_camera_config method."""

    @pytest.mark.asyncio
    async def test_set_camera_config_creates_record(self) -> None:
        """Test creates new config record when none exists."""
        from backend.services.baseline_config import BaselineConfigService, _camera_configs

        _camera_configs.clear()

        service = BaselineConfigService()
        config = await service.set_camera_config(
            camera_id="camera-1",
            threshold_stdev=3.0,
            min_samples=15,
            override_global_config=True,
        )

        # Should store in-memory config
        assert "camera-1" in _camera_configs
        assert _camera_configs["camera-1"]["threshold_stdev"] == 3.0
        assert _camera_configs["camera-1"]["min_samples"] == 15
        assert config["threshold_stdev"] == 3.0
        assert config["min_samples"] == 15

    @pytest.mark.asyncio
    async def test_set_camera_config_updates_record(self) -> None:
        """Test updates existing config when record exists."""
        from backend.services.baseline_config import BaselineConfigService, _camera_configs

        # Setup existing in-memory config
        _camera_configs.clear()
        _camera_configs["camera-1"] = {
            "threshold_stdev": 2.0,
            "min_samples": 10,
            "override_global_config": True,
        }

        service = BaselineConfigService()
        config = await service.set_camera_config(
            camera_id="camera-1",
            threshold_stdev=4.0,
            min_samples=25,
            override_global_config=True,
        )

        # Should update in-memory config
        assert _camera_configs["camera-1"]["threshold_stdev"] == 4.0
        assert _camera_configs["camera-1"]["min_samples"] == 25
        assert config["threshold_stdev"] == 4.0
        assert config["min_samples"] == 25


class TestResetCameraBaseline:
    """Tests for reset_camera_baseline method."""

    @pytest.mark.asyncio
    async def test_reset_camera_baseline_deletes_all(self) -> None:
        """Test deletes both activity and class baselines."""
        from unittest.mock import AsyncMock

        from backend.services.baseline_config import BaselineConfigService

        mock_session = AsyncMock()

        # Mock delete results
        mock_activity_result = MagicMock()
        mock_activity_result.rowcount = 168

        mock_class_result = MagicMock()
        mock_class_result.rowcount = 42

        mock_session.execute.side_effect = [mock_activity_result, mock_class_result]

        service = BaselineConfigService()
        result = await service.reset_camera_baseline(camera_id="camera-1", session=mock_session)

        assert result["activity_baselines_deleted"] == 168
        assert result["class_baselines_deleted"] == 42
        # Should execute 2 delete queries
        assert mock_session.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_reset_camera_baseline_returns_counts(self) -> None:
        """Test returns correct deletion counts."""
        from unittest.mock import AsyncMock

        from backend.services.baseline_config import BaselineConfigService

        mock_session = AsyncMock()

        # Mock delete results with specific counts
        mock_activity_result = MagicMock()
        mock_activity_result.rowcount = 50

        mock_class_result = MagicMock()
        mock_class_result.rowcount = 15

        mock_session.execute.side_effect = [mock_activity_result, mock_class_result]

        service = BaselineConfigService()
        result = await service.reset_camera_baseline(camera_id="camera-1", session=mock_session)

        assert result["activity_baselines_deleted"] == 50
        assert result["class_baselines_deleted"] == 15

    @pytest.mark.asyncio
    async def test_reset_camera_baseline_no_side_effects(self) -> None:
        """Test doesn't affect other cameras' baselines."""
        from unittest.mock import AsyncMock

        from backend.services.baseline_config import BaselineConfigService

        mock_session = AsyncMock()

        # Mock delete results for camera-1 only
        mock_activity_result = MagicMock()
        mock_activity_result.rowcount = 100

        mock_class_result = MagicMock()
        mock_class_result.rowcount = 30

        mock_session.execute.side_effect = [mock_activity_result, mock_class_result]

        service = BaselineConfigService()
        result = await service.reset_camera_baseline(camera_id="camera-1", session=mock_session)

        # Verify deletion counts are specific to camera-1
        assert result["activity_baselines_deleted"] == 100
        assert result["class_baselines_deleted"] == 30

        # Verify delete queries were executed with camera_id filter
        assert mock_session.execute.call_count == 2


class TestBaselineConfigValidation:
    """Tests for configuration validation."""

    @pytest.mark.asyncio
    async def test_set_camera_config_validates_threshold_min(self) -> None:
        """Test validates threshold_stdev minimum value (0.5)."""
        from backend.services.baseline_config import BaselineConfigService, _camera_configs

        _camera_configs.clear()
        service = BaselineConfigService()

        with pytest.raises(ValueError) as exc_info:
            await service.set_camera_config(
                camera_id="camera-1",
                threshold_stdev=0.3,  # Below minimum
            )

        assert "threshold_stdev" in str(exc_info.value).lower()
        assert "0.5" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_set_camera_config_validates_min_samples(self) -> None:
        """Test validates min_samples minimum value (1)."""
        from backend.services.baseline_config import BaselineConfigService, _camera_configs

        _camera_configs.clear()
        service = BaselineConfigService()

        with pytest.raises(ValueError) as exc_info:
            await service.set_camera_config(
                camera_id="camera-1",
                min_samples=0,  # Below minimum
            )

        assert "min_samples" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_set_camera_config_accepts_valid_range(self) -> None:
        """Test accepts values within valid range."""
        from backend.services.baseline_config import BaselineConfigService, _camera_configs

        _camera_configs.clear()
        service = BaselineConfigService()

        # Should not raise for valid values
        config = await service.set_camera_config(
            camera_id="camera-1",
            threshold_stdev=2.5,  # Valid: between 0.5 and infinity
            min_samples=10,  # Valid: >= 1
            override_global_config=True,
        )

        assert config["threshold_stdev"] == 2.5
        assert config["min_samples"] == 10


class TestBaselineConfigDefaults:
    """Tests for default configuration values."""

    @pytest.mark.asyncio
    async def test_get_camera_config_returns_global_defaults(self) -> None:
        """Test returns correct global default values."""
        from backend.services.baseline_config import BaselineConfigService, _camera_configs

        _camera_configs.clear()
        service = BaselineConfigService()
        config = await service.get_camera_config("camera-1")

        # Verify global defaults
        assert config["global_config"]["threshold_stdev"] == 2.0
        assert config["global_config"]["min_samples"] == 10
        assert config["global_config"]["decay_factor"] == 0.1
        assert config["global_config"]["window_days"] == 30

    @pytest.mark.asyncio
    async def test_set_camera_config_sets_override_flag(self) -> None:
        """Test setting config enables override flag."""
        from backend.services.baseline_config import BaselineConfigService, _camera_configs

        _camera_configs.clear()
        service = BaselineConfigService()
        config = await service.set_camera_config(
            camera_id="camera-1",
            threshold_stdev=3.0,
            override_global_config=True,
        )

        # Verify override flag was set in returned config
        assert config["override_global_config"] is True
        # Verify stored in memory
        assert _camera_configs["camera-1"]["override_global_config"] is True


class TestAutoSessionHandling:
    """Tests for automatic session management."""

    @pytest.mark.asyncio
    async def test_get_camera_config_without_session(self) -> None:
        """Test get_camera_config works without session (in-memory storage)."""
        from backend.services.baseline_config import BaselineConfigService, _camera_configs

        _camera_configs.clear()
        service = BaselineConfigService()

        # Should work without session since it uses in-memory storage
        config = await service.get_camera_config("camera-1")

        assert config["override_global_config"] is False

    @pytest.mark.asyncio
    async def test_set_camera_config_without_session(self) -> None:
        """Test set_camera_config works without session (in-memory storage)."""
        from backend.services.baseline_config import BaselineConfigService, _camera_configs

        _camera_configs.clear()
        service = BaselineConfigService()

        # Should work without session since it uses in-memory storage
        config = await service.set_camera_config(
            camera_id="camera-1",
            threshold_stdev=3.0,
            override_global_config=True,
        )

        assert config["threshold_stdev"] == 3.0
        assert "camera-1" in _camera_configs

    @pytest.mark.asyncio
    async def test_reset_camera_baseline_with_session(self) -> None:
        """Test reset_camera_baseline requires session for DB operations."""
        from unittest.mock import AsyncMock

        from backend.services.baseline_config import BaselineConfigService

        service = BaselineConfigService()

        # Mock session for DB operations
        mock_session = AsyncMock()
        mock_activity_result = MagicMock()
        mock_activity_result.rowcount = 100
        mock_class_result = MagicMock()
        mock_class_result.rowcount = 30
        mock_session.execute.side_effect = [mock_activity_result, mock_class_result]

        result = await service.reset_camera_baseline(camera_id="camera-1", session=mock_session)

        assert result["activity_baselines_deleted"] == 100
        assert result["class_baselines_deleted"] == 30
        mock_session.commit.assert_called_once()
