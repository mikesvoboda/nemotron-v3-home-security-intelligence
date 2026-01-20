"""Unit tests for settings API routes.

Tests the GET /api/v1/settings endpoint that exposes user-configurable
system settings grouped by category, and PATCH endpoint for runtime updates.

Phase 2.1: GET endpoint (NEM-3119)
Phase 2.2: PATCH endpoint (NEM-3120)
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.api.routes.settings_api import router
from backend.api.schemas.settings_api import SettingsResponse, SettingsUpdate


def create_test_app() -> FastAPI:
    """Create a test FastAPI app with the settings router.

    Returns:
        FastAPI app configured for testing.
    """
    app = FastAPI()
    app.include_router(router)
    return app


def create_mock_settings(
    detection_confidence_threshold: float = 0.5,
    fast_path_confidence_threshold: float = 0.9,
    batch_window_seconds: int = 90,
    batch_idle_timeout_seconds: int = 30,
    severity_low_max: int = 29,
    severity_medium_max: int = 59,
    severity_high_max: int = 84,
    vision_extraction_enabled: bool = True,
    reid_enabled: bool = True,
    scene_change_enabled: bool = True,
    clip_generation_enabled: bool = True,
    image_quality_enabled: bool = True,
    background_evaluation_enabled: bool = True,
    rate_limit_enabled: bool = True,
    rate_limit_requests_per_minute: int = 60,
    rate_limit_burst: int = 10,
    queue_max_size: int = 10000,
    queue_backpressure_threshold: float = 0.8,
    retention_days: int = 30,
    log_retention_days: int = 7,
) -> MagicMock:
    """Create a mock Settings object with configurable values.

    Args:
        All arguments correspond to Settings fields with sensible defaults.

    Returns:
        MagicMock configured to return the specified settings values.
    """
    mock = MagicMock()
    mock.detection_confidence_threshold = detection_confidence_threshold
    mock.fast_path_confidence_threshold = fast_path_confidence_threshold
    mock.batch_window_seconds = batch_window_seconds
    mock.batch_idle_timeout_seconds = batch_idle_timeout_seconds
    mock.severity_low_max = severity_low_max
    mock.severity_medium_max = severity_medium_max
    mock.severity_high_max = severity_high_max
    mock.vision_extraction_enabled = vision_extraction_enabled
    mock.reid_enabled = reid_enabled
    mock.scene_change_enabled = scene_change_enabled
    mock.clip_generation_enabled = clip_generation_enabled
    mock.image_quality_enabled = image_quality_enabled
    mock.background_evaluation_enabled = background_evaluation_enabled
    mock.rate_limit_enabled = rate_limit_enabled
    mock.rate_limit_requests_per_minute = rate_limit_requests_per_minute
    mock.rate_limit_burst = rate_limit_burst
    mock.queue_max_size = queue_max_size
    mock.queue_backpressure_threshold = queue_backpressure_threshold
    mock.retention_days = retention_days
    mock.log_retention_days = log_retention_days
    return mock


class TestGetSettingsEndpoint:
    """Tests for GET /api/v1/settings endpoint."""

    @pytest.mark.asyncio
    async def test_returns_200_with_all_settings_groups(self) -> None:
        """Test that endpoint returns 200 and all expected settings groups."""
        mock_settings = create_mock_settings()
        app = create_test_app()

        with patch("backend.api.routes.settings_api.get_settings", return_value=mock_settings):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get("/api/v1/settings")

        assert response.status_code == 200
        data = response.json()

        # Verify all groups are present
        assert "detection" in data
        assert "batch" in data
        assert "severity" in data
        assert "features" in data
        assert "rate_limiting" in data
        assert "queue" in data
        assert "retention" in data

    @pytest.mark.asyncio
    async def test_returns_correct_detection_settings(self) -> None:
        """Test that detection settings are returned correctly."""
        mock_settings = create_mock_settings(
            detection_confidence_threshold=0.65,
            fast_path_confidence_threshold=0.95,
        )
        app = create_test_app()

        with patch("backend.api.routes.settings_api.get_settings", return_value=mock_settings):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get("/api/v1/settings")

        assert response.status_code == 200
        data = response.json()

        assert data["detection"]["confidence_threshold"] == 0.65
        assert data["detection"]["fast_path_threshold"] == 0.95

    @pytest.mark.asyncio
    async def test_returns_correct_batch_settings(self) -> None:
        """Test that batch settings are returned correctly."""
        mock_settings = create_mock_settings(
            batch_window_seconds=120,
            batch_idle_timeout_seconds=45,
        )
        app = create_test_app()

        with patch("backend.api.routes.settings_api.get_settings", return_value=mock_settings):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get("/api/v1/settings")

        assert response.status_code == 200
        data = response.json()

        assert data["batch"]["window_seconds"] == 120
        assert data["batch"]["idle_timeout_seconds"] == 45

    @pytest.mark.asyncio
    async def test_returns_correct_severity_settings(self) -> None:
        """Test that severity settings are returned correctly."""
        mock_settings = create_mock_settings(
            severity_low_max=25,
            severity_medium_max=55,
            severity_high_max=80,
        )
        app = create_test_app()

        with patch("backend.api.routes.settings_api.get_settings", return_value=mock_settings):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get("/api/v1/settings")

        assert response.status_code == 200
        data = response.json()

        assert data["severity"]["low_max"] == 25
        assert data["severity"]["medium_max"] == 55
        assert data["severity"]["high_max"] == 80

    @pytest.mark.asyncio
    async def test_returns_correct_feature_settings(self) -> None:
        """Test that feature toggle settings are returned correctly."""
        mock_settings = create_mock_settings(
            vision_extraction_enabled=False,
            reid_enabled=True,
            scene_change_enabled=False,
            clip_generation_enabled=True,
            image_quality_enabled=False,
            background_evaluation_enabled=True,
        )
        app = create_test_app()

        with patch("backend.api.routes.settings_api.get_settings", return_value=mock_settings):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get("/api/v1/settings")

        assert response.status_code == 200
        data = response.json()

        assert data["features"]["vision_extraction_enabled"] is False
        assert data["features"]["reid_enabled"] is True
        assert data["features"]["scene_change_enabled"] is False
        assert data["features"]["clip_generation_enabled"] is True
        assert data["features"]["image_quality_enabled"] is False
        assert data["features"]["background_eval_enabled"] is True

    @pytest.mark.asyncio
    async def test_returns_correct_rate_limiting_settings(self) -> None:
        """Test that rate limiting settings are returned correctly."""
        mock_settings = create_mock_settings(
            rate_limit_enabled=False,
            rate_limit_requests_per_minute=120,
            rate_limit_burst=20,
        )
        app = create_test_app()

        with patch("backend.api.routes.settings_api.get_settings", return_value=mock_settings):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get("/api/v1/settings")

        assert response.status_code == 200
        data = response.json()

        assert data["rate_limiting"]["enabled"] is False
        assert data["rate_limiting"]["requests_per_minute"] == 120
        assert data["rate_limiting"]["burst_size"] == 20

    @pytest.mark.asyncio
    async def test_returns_correct_queue_settings(self) -> None:
        """Test that queue settings are returned correctly."""
        mock_settings = create_mock_settings(
            queue_max_size=20000,
            queue_backpressure_threshold=0.9,
        )
        app = create_test_app()

        with patch("backend.api.routes.settings_api.get_settings", return_value=mock_settings):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get("/api/v1/settings")

        assert response.status_code == 200
        data = response.json()

        assert data["queue"]["max_size"] == 20000
        assert data["queue"]["backpressure_threshold"] == 0.9

    @pytest.mark.asyncio
    async def test_returns_correct_retention_settings(self) -> None:
        """Test that retention settings are returned correctly."""
        mock_settings = create_mock_settings(
            retention_days=60,
            log_retention_days=14,
        )
        app = create_test_app()

        with patch("backend.api.routes.settings_api.get_settings", return_value=mock_settings):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get("/api/v1/settings")

        assert response.status_code == 200
        data = response.json()

        assert data["retention"]["days"] == 60
        assert data["retention"]["log_days"] == 14

    @pytest.mark.asyncio
    async def test_response_matches_schema(self) -> None:
        """Test that response can be parsed by SettingsResponse schema."""
        mock_settings = create_mock_settings()
        app = create_test_app()

        with patch("backend.api.routes.settings_api.get_settings", return_value=mock_settings):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get("/api/v1/settings")

        assert response.status_code == 200

        # Verify response can be parsed by the schema
        settings_response = SettingsResponse.model_validate(response.json())
        assert settings_response.detection.confidence_threshold == 0.5
        assert settings_response.batch.window_seconds == 90
        assert settings_response.severity.low_max == 29
        assert settings_response.features.vision_extraction_enabled is True
        assert settings_response.rate_limiting.enabled is True
        assert settings_response.queue.max_size == 10000
        assert settings_response.retention.days == 30


class TestSettingsResponseSchema:
    """Tests for SettingsResponse Pydantic schema validation."""

    def test_valid_response_parses_correctly(self) -> None:
        """Test that a valid response structure parses correctly."""
        data = {
            "detection": {
                "confidence_threshold": 0.5,
                "fast_path_threshold": 0.9,
            },
            "batch": {
                "window_seconds": 90,
                "idle_timeout_seconds": 30,
            },
            "severity": {
                "low_max": 29,
                "medium_max": 59,
                "high_max": 84,
            },
            "features": {
                "vision_extraction_enabled": True,
                "reid_enabled": True,
                "scene_change_enabled": True,
                "clip_generation_enabled": True,
                "image_quality_enabled": True,
                "background_eval_enabled": True,
            },
            "rate_limiting": {
                "enabled": True,
                "requests_per_minute": 60,
                "burst_size": 10,
            },
            "queue": {
                "max_size": 10000,
                "backpressure_threshold": 0.8,
            },
            "retention": {
                "days": 30,
                "log_days": 7,
            },
        }

        response = SettingsResponse.model_validate(data)
        assert response.detection.confidence_threshold == 0.5
        assert response.features.reid_enabled is True

    def test_missing_field_raises_validation_error(self) -> None:
        """Test that missing required fields raise validation errors."""
        from pydantic import ValidationError

        # Missing 'features' group
        data = {
            "detection": {
                "confidence_threshold": 0.5,
                "fast_path_threshold": 0.9,
            },
            "batch": {
                "window_seconds": 90,
                "idle_timeout_seconds": 30,
            },
            "severity": {
                "low_max": 29,
                "medium_max": 59,
                "high_max": 84,
            },
            # features missing
            "rate_limiting": {
                "enabled": True,
                "requests_per_minute": 60,
                "burst_size": 10,
            },
            "queue": {
                "max_size": 10000,
                "backpressure_threshold": 0.8,
            },
            "retention": {
                "days": 30,
                "log_days": 7,
            },
        }

        with pytest.raises(ValidationError) as exc_info:
            SettingsResponse.model_validate(data)

        assert "features" in str(exc_info.value)

    def test_invalid_detection_threshold_raises_validation_error(self) -> None:
        """Test that invalid detection threshold values are rejected."""
        from pydantic import ValidationError

        from backend.api.schemas.settings_api import DetectionSettings

        # Threshold above 1.0
        with pytest.raises(ValidationError):
            DetectionSettings(
                confidence_threshold=1.5,
                fast_path_threshold=0.9,
            )

        # Threshold below 0.0
        with pytest.raises(ValidationError):
            DetectionSettings(
                confidence_threshold=-0.1,
                fast_path_threshold=0.9,
            )

    def test_invalid_queue_backpressure_raises_validation_error(self) -> None:
        """Test that invalid backpressure threshold values are rejected."""
        from pydantic import ValidationError

        from backend.api.schemas.settings_api import QueueSettings

        # Threshold above 1.0
        with pytest.raises(ValidationError):
            QueueSettings(
                max_size=10000,
                backpressure_threshold=1.5,
            )

        # Threshold below 0.5
        with pytest.raises(ValidationError):
            QueueSettings(
                max_size=10000,
                backpressure_threshold=0.3,
            )


# =============================================================================
# PATCH Endpoint Tests (Phase 2.2 - NEM-3120)
# =============================================================================


class TestPatchSettingsEndpoint:
    """Tests for PATCH /api/v1/settings endpoint."""

    @pytest.fixture
    def temp_runtime_env(self, tmp_path: Path) -> Path:
        """Create a temporary runtime.env file.

        Returns:
            Path to temporary runtime.env file.
        """
        runtime_env = tmp_path / "runtime.env"
        return runtime_env

    @pytest.mark.asyncio
    async def test_patch_detection_confidence_threshold(self, temp_runtime_env: Path) -> None:
        """Test updating detection confidence threshold."""
        mock_settings = create_mock_settings()
        app = create_test_app()

        with (
            patch("backend.api.routes.settings_api.get_settings", return_value=mock_settings),
            patch(
                "backend.api.routes.settings_api._get_runtime_env_path",
                return_value=temp_runtime_env,
            ),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.patch(
                    "/api/v1/settings",
                    json={"detection": {"confidence_threshold": 0.7}},
                )

        assert response.status_code == 200

        # Verify file was written
        assert temp_runtime_env.exists()
        content = temp_runtime_env.read_text()
        assert "DETECTION_CONFIDENCE_THRESHOLD=0.7" in content

    @pytest.mark.asyncio
    async def test_patch_multiple_settings(self, temp_runtime_env: Path) -> None:
        """Test updating multiple settings at once."""
        mock_settings = create_mock_settings()
        app = create_test_app()

        with (
            patch("backend.api.routes.settings_api.get_settings", return_value=mock_settings),
            patch(
                "backend.api.routes.settings_api._get_runtime_env_path",
                return_value=temp_runtime_env,
            ),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.patch(
                    "/api/v1/settings",
                    json={
                        "detection": {"confidence_threshold": 0.6},
                        "batch": {"window_seconds": 120},
                        "features": {"reid_enabled": False},
                    },
                )

        assert response.status_code == 200

        content = temp_runtime_env.read_text()
        assert "DETECTION_CONFIDENCE_THRESHOLD=0.6" in content
        assert "BATCH_WINDOW_SECONDS=120" in content
        assert "REID_ENABLED=false" in content

    @pytest.mark.asyncio
    async def test_patch_preserves_existing_settings(self, temp_runtime_env: Path) -> None:
        """Test that patching preserves existing runtime.env settings."""
        # Pre-populate runtime.env with existing settings
        temp_runtime_env.write_text(
            "# Existing settings\nDETECTION_CONFIDENCE_THRESHOLD=0.5\nEXISTING_SETTING=keep_me\n"
        )

        mock_settings = create_mock_settings()
        app = create_test_app()

        with (
            patch("backend.api.routes.settings_api.get_settings", return_value=mock_settings),
            patch(
                "backend.api.routes.settings_api._get_runtime_env_path",
                return_value=temp_runtime_env,
            ),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.patch(
                    "/api/v1/settings",
                    json={"detection": {"confidence_threshold": 0.8}},
                )

        assert response.status_code == 200

        content = temp_runtime_env.read_text()
        # New value should be updated
        assert "DETECTION_CONFIDENCE_THRESHOLD=0.8" in content
        # Existing setting should be preserved
        assert "EXISTING_SETTING=keep_me" in content

    @pytest.mark.asyncio
    async def test_patch_empty_update_returns_current_settings(
        self, temp_runtime_env: Path
    ) -> None:
        """Test that empty update returns current settings without changes."""
        mock_settings = create_mock_settings()
        app = create_test_app()

        with (
            patch("backend.api.routes.settings_api.get_settings", return_value=mock_settings),
            patch(
                "backend.api.routes.settings_api._get_runtime_env_path",
                return_value=temp_runtime_env,
            ),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.patch(
                    "/api/v1/settings",
                    json={},
                )

        assert response.status_code == 200
        # File should not be created for empty update
        assert not temp_runtime_env.exists()

    @pytest.mark.asyncio
    async def test_patch_boolean_feature_toggle(self, temp_runtime_env: Path) -> None:
        """Test toggling boolean feature settings."""
        mock_settings = create_mock_settings()
        app = create_test_app()

        with (
            patch("backend.api.routes.settings_api.get_settings", return_value=mock_settings),
            patch(
                "backend.api.routes.settings_api._get_runtime_env_path",
                return_value=temp_runtime_env,
            ),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.patch(
                    "/api/v1/settings",
                    json={
                        "features": {
                            "vision_extraction_enabled": False,
                            "scene_change_enabled": True,
                        }
                    },
                )

        assert response.status_code == 200

        content = temp_runtime_env.read_text()
        # Booleans should be lowercase
        assert "VISION_EXTRACTION_ENABLED=false" in content
        assert "SCENE_CHANGE_ENABLED=true" in content

    @pytest.mark.asyncio
    async def test_patch_invalid_confidence_threshold_validation(
        self, temp_runtime_env: Path
    ) -> None:
        """Test that invalid confidence threshold values are rejected by Pydantic."""
        mock_settings = create_mock_settings()
        app = create_test_app()

        with (
            patch("backend.api.routes.settings_api.get_settings", return_value=mock_settings),
            patch(
                "backend.api.routes.settings_api._get_runtime_env_path",
                return_value=temp_runtime_env,
            ),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                # Value above 1.0 should fail validation
                response = await client.patch(
                    "/api/v1/settings",
                    json={"detection": {"confidence_threshold": 1.5}},
                )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_patch_severity_ordering_validation(self, temp_runtime_env: Path) -> None:
        """Test that severity threshold ordering is validated."""
        # Mock settings with default severity values
        mock_settings = create_mock_settings(
            severity_low_max=29,
            severity_medium_max=59,
            severity_high_max=84,
        )
        app = create_test_app()

        with (
            patch("backend.api.routes.settings_api.get_settings", return_value=mock_settings),
            patch(
                "backend.api.routes.settings_api._get_runtime_env_path",
                return_value=temp_runtime_env,
            ),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                # Setting low_max higher than current medium_max should fail
                response = await client.patch(
                    "/api/v1/settings",
                    json={"severity": {"low_max": 70}},  # Current medium_max is 59
                )

        assert response.status_code == 422
        assert "low_max" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_patch_severity_valid_ordering(self, temp_runtime_env: Path) -> None:
        """Test that valid severity thresholds are accepted."""
        mock_settings = create_mock_settings()
        app = create_test_app()

        with (
            patch("backend.api.routes.settings_api.get_settings", return_value=mock_settings),
            patch(
                "backend.api.routes.settings_api._get_runtime_env_path",
                return_value=temp_runtime_env,
            ),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                # Update all three with valid ordering
                response = await client.patch(
                    "/api/v1/settings",
                    json={
                        "severity": {
                            "low_max": 20,
                            "medium_max": 50,
                            "high_max": 80,
                        }
                    },
                )

        assert response.status_code == 200

        content = temp_runtime_env.read_text()
        assert "SEVERITY_LOW_MAX=20" in content
        assert "SEVERITY_MEDIUM_MAX=50" in content
        assert "SEVERITY_HIGH_MAX=80" in content

    @pytest.mark.asyncio
    async def test_patch_retention_days_range(self, temp_runtime_env: Path) -> None:
        """Test retention days within valid range."""
        mock_settings = create_mock_settings()
        app = create_test_app()

        with (
            patch("backend.api.routes.settings_api.get_settings", return_value=mock_settings),
            patch(
                "backend.api.routes.settings_api._get_runtime_env_path",
                return_value=temp_runtime_env,
            ),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.patch(
                    "/api/v1/settings",
                    json={"retention": {"days": 90, "log_days": 14}},
                )

        assert response.status_code == 200

        content = temp_runtime_env.read_text()
        assert "RETENTION_DAYS=90" in content
        assert "LOG_RETENTION_DAYS=14" in content

    @pytest.mark.asyncio
    async def test_patch_retention_days_exceeds_max(self, temp_runtime_env: Path) -> None:
        """Test that retention days exceeding 365 is rejected."""
        mock_settings = create_mock_settings()
        app = create_test_app()

        with (
            patch("backend.api.routes.settings_api.get_settings", return_value=mock_settings),
            patch(
                "backend.api.routes.settings_api._get_runtime_env_path",
                return_value=temp_runtime_env,
            ),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.patch(
                    "/api/v1/settings",
                    json={"retention": {"days": 400}},
                )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_patch_rate_limiting_settings(self, temp_runtime_env: Path) -> None:
        """Test updating rate limiting settings."""
        mock_settings = create_mock_settings()
        app = create_test_app()

        with (
            patch("backend.api.routes.settings_api.get_settings", return_value=mock_settings),
            patch(
                "backend.api.routes.settings_api._get_runtime_env_path",
                return_value=temp_runtime_env,
            ),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.patch(
                    "/api/v1/settings",
                    json={
                        "rate_limiting": {
                            "enabled": False,
                            "requests_per_minute": 120,
                            "burst_size": 20,
                        }
                    },
                )

        assert response.status_code == 200

        content = temp_runtime_env.read_text()
        assert "RATE_LIMIT_ENABLED=false" in content
        assert "RATE_LIMIT_REQUESTS_PER_MINUTE=120" in content
        assert "RATE_LIMIT_BURST=20" in content

    @pytest.mark.asyncio
    async def test_patch_queue_settings(self, temp_runtime_env: Path) -> None:
        """Test updating queue settings."""
        mock_settings = create_mock_settings()
        app = create_test_app()

        with (
            patch("backend.api.routes.settings_api.get_settings", return_value=mock_settings),
            patch(
                "backend.api.routes.settings_api._get_runtime_env_path",
                return_value=temp_runtime_env,
            ),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.patch(
                    "/api/v1/settings",
                    json={
                        "queue": {
                            "max_size": 15000,
                            "backpressure_threshold": 0.9,
                        }
                    },
                )

        assert response.status_code == 200

        content = temp_runtime_env.read_text()
        assert "QUEUE_MAX_SIZE=15000" in content
        assert "QUEUE_BACKPRESSURE_THRESHOLD=0.9" in content

    @pytest.mark.asyncio
    async def test_patch_clears_settings_cache(self, temp_runtime_env: Path) -> None:
        """Test that PATCH clears the settings cache."""
        mock_settings = create_mock_settings()
        cache_clear_called = False

        def mock_cache_clear() -> None:
            nonlocal cache_clear_called
            cache_clear_called = True

        # Create mock get_settings with cache_clear method
        mock_get_settings = MagicMock(return_value=mock_settings)
        mock_get_settings.cache_clear = mock_cache_clear

        app = create_test_app()

        with (
            patch("backend.api.routes.settings_api.get_settings", mock_get_settings),
            patch(
                "backend.api.routes.settings_api._get_runtime_env_path",
                return_value=temp_runtime_env,
            ),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.patch(
                    "/api/v1/settings",
                    json={"detection": {"confidence_threshold": 0.6}},
                )

        assert response.status_code == 200
        assert cache_clear_called, "cache_clear should have been called"

    @pytest.mark.asyncio
    async def test_patch_file_write_error_returns_500(self, temp_runtime_env: Path) -> None:
        """Test that file write errors return 500."""
        mock_settings = create_mock_settings()
        app = create_test_app()

        # Make the runtime env path point to a read-only location
        # by using a non-writable path
        readonly_path = Path("/nonexistent/readonly/runtime.env")

        with (
            patch("backend.api.routes.settings_api.get_settings", return_value=mock_settings),
            patch(
                "backend.api.routes.settings_api._get_runtime_env_path",
                return_value=readonly_path,
            ),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.patch(
                    "/api/v1/settings",
                    json={"detection": {"confidence_threshold": 0.6}},
                )

        assert response.status_code == 500
        assert "Failed to write settings" in response.json()["detail"]


class TestSettingsUpdateSchema:
    """Tests for SettingsUpdate Pydantic schema validation."""

    def test_empty_update_is_valid(self) -> None:
        """Test that an empty update is valid."""
        update = SettingsUpdate.model_validate({})
        assert update.detection is None
        assert update.batch is None

    def test_partial_update_parses_correctly(self) -> None:
        """Test that partial update parses correctly."""
        data = {
            "detection": {"confidence_threshold": 0.7},
        }
        update = SettingsUpdate.model_validate(data)
        assert update.detection is not None
        assert update.detection.confidence_threshold == 0.7
        assert update.detection.fast_path_threshold is None
        assert update.batch is None

    def test_severity_ordering_validation_in_schema(self) -> None:
        """Test that severity ordering is validated within schema."""
        from pydantic import ValidationError

        from backend.api.schemas.settings_api import SeveritySettingsUpdate

        # Valid ordering
        valid = SeveritySettingsUpdate(low_max=20, medium_max=50, high_max=80)
        assert valid.low_max == 20

        # Invalid: low >= medium
        with pytest.raises(ValidationError):
            SeveritySettingsUpdate(low_max=60, medium_max=50, high_max=80)

        # Invalid: medium >= high
        with pytest.raises(ValidationError):
            SeveritySettingsUpdate(low_max=20, medium_max=90, high_max=80)

    def test_all_fields_optional_in_nested_schemas(self) -> None:
        """Test that nested update schemas have all optional fields."""
        from backend.api.schemas.settings_api import (
            BatchSettingsUpdate,
            DetectionSettingsUpdate,
            FeatureSettingsUpdate,
        )

        # All should parse with no fields
        det = DetectionSettingsUpdate.model_validate({})
        assert det.confidence_threshold is None
        assert det.fast_path_threshold is None

        batch = BatchSettingsUpdate.model_validate({})
        assert batch.window_seconds is None
        assert batch.idle_timeout_seconds is None

        feat = FeatureSettingsUpdate.model_validate({})
        assert feat.vision_extraction_enabled is None
        assert feat.reid_enabled is None
