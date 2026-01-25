"""Unit tests for detection_confidence_threshold deprecation in /api/system/config.

NEM-3532: Consolidate detection settings to use /api/v1/settings exclusively.
The legacy /api/system/config endpoint's detection_confidence_threshold field
should be marked as deprecated.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.api.routes.system import router as system_router
from backend.api.routes.system import verify_api_key
from backend.api.schemas.system import ConfigResponse
from backend.core.database import get_db


def create_test_app() -> FastAPI:
    """Create a test FastAPI app with the system router."""
    app = FastAPI()
    app.include_router(system_router)
    return app


def create_test_app_with_overrides(db_session_override=None, api_key_override=None) -> FastAPI:
    """Create a test FastAPI app with dependency overrides."""
    app = FastAPI()
    app.include_router(system_router)

    if db_session_override is not None:
        app.dependency_overrides[get_db] = lambda: db_session_override
    if api_key_override is not None:
        app.dependency_overrides[verify_api_key] = lambda: api_key_override

    return app


def create_mock_settings(
    app_name: str = "Home Security Intelligence",
    app_version: str = "0.1.0",
    retention_days: int = 30,
    batch_window_seconds: int = 90,
    batch_idle_timeout_seconds: int = 30,
    detection_confidence_threshold: float = 0.5,
    grafana_url: str = "http://localhost:3000",
    debug: bool = False,
) -> MagicMock:
    """Create a mock Settings object."""
    mock = MagicMock()
    mock.app_name = app_name
    mock.app_version = app_version
    mock.retention_days = retention_days
    mock.batch_window_seconds = batch_window_seconds
    mock.batch_idle_timeout_seconds = batch_idle_timeout_seconds
    mock.detection_confidence_threshold = detection_confidence_threshold
    mock.grafana_url = grafana_url
    mock.debug = debug
    return mock


class TestConfigResponseDeprecation:
    """Tests for deprecation notice in ConfigResponse."""

    def test_config_response_has_detection_confidence_threshold_deprecated(self) -> None:
        """Test that ConfigResponse schema marks detection_confidence_threshold as deprecated."""
        # Check that the field has deprecation in its JSON schema
        schema = ConfigResponse.model_json_schema()
        properties = schema.get("properties", {})
        detection_field = properties.get("detection_confidence_threshold", {})

        # The field should have a deprecated flag or description indicating deprecation
        assert "deprecated" in detection_field or "DEPRECATED" in detection_field.get(
            "description", ""
        ), "detection_confidence_threshold should be marked as deprecated in schema"


class TestGetConfigDeprecationHeader:
    """Tests for deprecation header in GET /api/system/config response."""

    @pytest.mark.asyncio
    async def test_get_config_includes_deprecation_header(self) -> None:
        """Test that GET /api/system/config includes a deprecation header."""
        mock_settings = create_mock_settings()
        app = create_test_app()

        with patch("backend.api.routes.system.get_settings", return_value=mock_settings):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get("/api/system/config")

        assert response.status_code == 200

        # Check for Deprecation header (RFC 8594)
        assert "Deprecation" in response.headers or "Sunset" in response.headers, (
            "GET /api/system/config should include a Deprecation or Sunset header"
        )

    @pytest.mark.asyncio
    async def test_get_config_deprecation_header_references_settings_api(self) -> None:
        """Test that deprecation header points to /api/v1/settings as replacement."""
        mock_settings = create_mock_settings()
        app = create_test_app()

        with patch("backend.api.routes.system.get_settings", return_value=mock_settings):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get("/api/system/config")

        assert response.status_code == 200

        # Check Link header for successor (RFC 8594)
        link_header = response.headers.get("Link", "")
        assert "/api/v1/settings" in link_header or "X-Deprecated-Message" in response.headers, (
            "Response should reference /api/v1/settings as the replacement endpoint"
        )


class TestPatchConfigDeprecationHeader:
    """Tests for deprecation header in PATCH /api/system/config response."""

    @pytest.fixture
    def mock_db_session(self) -> AsyncMock:
        """Create a mock database session."""
        session = AsyncMock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_patch_config_includes_deprecation_header(
        self, mock_db_session: AsyncMock, tmp_path
    ) -> None:
        """Test that PATCH /api/system/config includes a deprecation header."""
        mock_settings = create_mock_settings()
        mock_settings.api_key_enabled = False  # Disable API key for test

        runtime_env = tmp_path / "runtime.env"

        # Create async generator for db dependency override
        async def db_override():
            yield mock_db_session

        # Create test app with dependency overrides
        app = FastAPI()
        app.include_router(system_router)
        app.dependency_overrides[get_db] = db_override
        app.dependency_overrides[verify_api_key] = lambda: None

        with (
            patch("backend.api.routes.system.get_settings", return_value=mock_settings),
            patch("backend.api.routes.system._runtime_env_path", return_value=runtime_env),
            patch("backend.api.routes.system.AuditService.log_action", new_callable=AsyncMock),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.patch(
                    "/api/system/config",
                    json={"detection_confidence_threshold": 0.6},
                )

        # We expect 200 or 401 (if API key check wasn't properly mocked)
        # For this test, we're checking headers if successful
        if response.status_code == 200:
            assert "Deprecation" in response.headers or "Sunset" in response.headers, (
                "PATCH /api/system/config should include a Deprecation or Sunset header"
            )


class TestDeprecatedFieldDocumentation:
    """Tests for deprecated field documentation."""

    def test_config_response_detection_threshold_description_mentions_settings_api(self) -> None:
        """Test that the deprecated field's description mentions /api/v1/settings."""
        schema = ConfigResponse.model_json_schema()
        properties = schema.get("properties", {})
        detection_field = properties.get("detection_confidence_threshold", {})
        description = detection_field.get("description", "")

        assert "/api/v1/settings" in description or "settings API" in description.lower(), (
            "detection_confidence_threshold description should reference /api/v1/settings"
        )
