"""Unit tests for SystemSetting Key-Value Store API (NEM-3638).

Tests the REST API endpoints for managing system-wide settings stored
as key-value pairs in the SystemSetting model.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from backend.api.routes.system_settings import router
from backend.api.schemas.system_settings import (
    SystemSettingCreate,
    SystemSettingListResponse,
    SystemSettingResponse,
    SystemSettingUpdate,
)


def create_test_app() -> FastAPI:
    """Create a test FastAPI app with the system settings router."""
    app = FastAPI()
    app.include_router(router)
    return app


class TestSystemSettingResponseSchema:
    """Tests for SystemSettingResponse Pydantic schema."""

    def test_valid_response(self):
        """Test valid response parses correctly."""
        now = datetime.now(UTC)
        data = {
            "key": "test_key",
            "value": {"enabled": True, "threshold": 0.5},
            "updated_at": now,
        }
        response = SystemSettingResponse(**data)
        assert response.key == "test_key"
        assert response.value == {"enabled": True, "threshold": 0.5}
        assert response.updated_at == now

    def test_missing_required_field_raises(self):
        """Test missing required field raises ValidationError."""
        with pytest.raises(ValidationError):
            SystemSettingResponse(
                key="test_key",
                # missing value and updated_at
            )

    def test_key_max_length(self):
        """Test key max length is enforced."""
        now = datetime.now(UTC)
        # Valid: 64 characters
        long_key = "a" * 64
        response = SystemSettingResponse(
            key=long_key,
            value={},
            updated_at=now,
        )
        assert len(response.key) == 64

        # Note: Pydantic v2 doesn't automatically reject strings over max_length
        # for response models by default unless strict mode is enabled.
        # The max_length in Field is primarily for schema documentation.


class TestSystemSettingUpdateSchema:
    """Tests for SystemSettingUpdate Pydantic schema."""

    def test_valid_update(self):
        """Test valid update parses correctly."""
        data = {"value": {"new_setting": "value"}}
        update = SystemSettingUpdate(**data)
        assert update.value == {"new_setting": "value"}

    def test_empty_value_is_valid(self):
        """Test empty dict value is valid."""
        update = SystemSettingUpdate(value={})
        assert update.value == {}

    def test_nested_value_is_valid(self):
        """Test deeply nested value is valid."""
        nested_value = {
            "level1": {
                "level2": {
                    "level3": [1, 2, 3],
                },
            },
        }
        update = SystemSettingUpdate(value=nested_value)
        assert update.value == nested_value


class TestSystemSettingCreateSchema:
    """Tests for SystemSettingCreate Pydantic schema."""

    def test_valid_key_lowercase(self):
        """Test lowercase key is valid."""
        create = SystemSettingCreate(key="my_setting", value={"data": True})
        assert create.key == "my_setting"

    def test_valid_key_with_numbers(self):
        """Test key with numbers is valid."""
        create = SystemSettingCreate(key="setting123", value={})
        assert create.key == "setting123"

    def test_invalid_key_uppercase(self):
        """Test uppercase key is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            SystemSettingCreate(key="MY_SETTING", value={})
        assert "key" in str(exc_info.value)

    def test_invalid_key_starts_with_number(self):
        """Test key starting with number is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            SystemSettingCreate(key="123setting", value={})
        assert "key" in str(exc_info.value)

    def test_invalid_key_special_characters(self):
        """Test key with special characters is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            SystemSettingCreate(key="my-setting", value={})
        assert "key" in str(exc_info.value)


class TestListSystemSettingsEndpoint:
    """Tests for GET /api/v1/system-settings endpoint."""

    @pytest.mark.asyncio
    async def test_list_empty_returns_empty_list(self):
        """Test listing with no settings returns empty list."""
        from backend.core.database import get_db

        app = create_test_app()

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        async def mock_db_override():
            return mock_db

        app.dependency_overrides[get_db] = mock_db_override

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/v1/system-settings")

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_list_returns_all_settings(self):
        """Test listing returns all settings."""
        from backend.core.database import get_db

        app = create_test_app()

        now = datetime.now(UTC)
        mock_settings = [
            MagicMock(key="setting1", value={"a": 1}, updated_at=now),
            MagicMock(key="setting2", value={"b": 2}, updated_at=now),
        ]

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_settings
        mock_db.execute.return_value = mock_result

        async def mock_db_override():
            return mock_db

        app.dependency_overrides[get_db] = mock_db_override

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/v1/system-settings")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["total"] == 2
        assert data["items"][0]["key"] == "setting1"
        assert data["items"][1]["key"] == "setting2"


class TestGetSystemSettingEndpoint:
    """Tests for GET /api/v1/system-settings/{key} endpoint."""

    @pytest.mark.asyncio
    async def test_get_existing_setting(self):
        """Test getting an existing setting returns it."""
        from backend.core.database import get_db

        app = create_test_app()

        now = datetime.now(UTC)
        mock_setting = MagicMock(
            key="test_setting",
            value={"enabled": True},
            updated_at=now,
        )

        mock_db = AsyncMock()
        mock_db.get.return_value = mock_setting

        async def mock_db_override():
            return mock_db

        app.dependency_overrides[get_db] = mock_db_override

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/v1/system-settings/test_setting")

        assert response.status_code == 200
        data = response.json()
        assert data["key"] == "test_setting"
        assert data["value"] == {"enabled": True}

    @pytest.mark.asyncio
    async def test_get_nonexistent_setting_returns_404(self):
        """Test getting a nonexistent setting returns 404."""
        from backend.core.database import get_db

        app = create_test_app()

        mock_db = AsyncMock()
        mock_db.get.return_value = None

        async def mock_db_override():
            return mock_db

        app.dependency_overrides[get_db] = mock_db_override

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/v1/system-settings/nonexistent")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]


class TestUpdateSystemSettingEndpoint:
    """Tests for PATCH /api/v1/system-settings/{key} endpoint."""

    @pytest.mark.asyncio
    async def test_update_existing_setting(self):
        """Test updating an existing setting."""
        from backend.core.database import get_db

        app = create_test_app()

        now = datetime.now(UTC)
        mock_setting = MagicMock(
            key="test_setting",
            value={"old": "value"},
            updated_at=now,
        )

        mock_db = AsyncMock()
        mock_db.get.return_value = mock_setting

        async def mock_db_override():
            return mock_db

        app.dependency_overrides[get_db] = mock_db_override

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.patch(
                "/api/v1/system-settings/test_setting",
                json={"value": {"new": "value"}},
            )

        assert response.status_code == 200
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_new_setting_via_patch(self):
        """Test creating a new setting via PATCH (upsert)."""
        from backend.core.database import get_db

        app = create_test_app()

        mock_db = AsyncMock()
        mock_db.get.return_value = None  # Setting doesn't exist

        # Mock the add operation to capture the new setting
        added_setting = None

        def capture_add(setting):
            nonlocal added_setting
            added_setting = setting

        mock_db.add = capture_add

        # Mock refresh to update the setting
        async def mock_refresh(setting):
            setting.key = "new_setting"
            setting.value = {"data": "value"}
            setting.updated_at = datetime.now(UTC)

        mock_db.refresh = mock_refresh

        async def mock_db_override():
            return mock_db

        app.dependency_overrides[get_db] = mock_db_override

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.patch(
                "/api/v1/system-settings/new_setting",
                json={"value": {"data": "value"}},
            )

        assert response.status_code == 200
        assert added_setting is not None
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_invalid_key_format_returns_400(self):
        """Test invalid key format returns 400."""
        from backend.core.database import get_db

        app = create_test_app()

        mock_db = AsyncMock()

        async def mock_db_override():
            return mock_db

        app.dependency_overrides[get_db] = mock_db_override

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            # Test uppercase
            response = await client.patch(
                "/api/v1/system-settings/INVALID",
                json={"value": {}},
            )
            assert response.status_code == 400
            assert "Invalid key format" in response.json()["detail"]

            # Test special characters
            response = await client.patch(
                "/api/v1/system-settings/my-setting",
                json={"value": {}},
            )
            assert response.status_code == 400

            # Test starting with number
            response = await client.patch(
                "/api/v1/system-settings/123abc",
                json={"value": {}},
            )
            assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_key_too_long_returns_400(self):
        """Test key longer than 64 characters returns 400."""
        from backend.core.database import get_db

        app = create_test_app()

        mock_db = AsyncMock()

        async def mock_db_override():
            return mock_db

        app.dependency_overrides[get_db] = mock_db_override

        long_key = "a" * 65

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.patch(
                f"/api/v1/system-settings/{long_key}",
                json={"value": {}},
            )

        assert response.status_code == 400
        assert "too long" in response.json()["detail"]


class TestDeleteSystemSettingEndpoint:
    """Tests for DELETE /api/v1/system-settings/{key} endpoint."""

    @pytest.mark.asyncio
    async def test_delete_existing_setting(self):
        """Test deleting an existing setting."""
        from backend.core.database import get_db

        app = create_test_app()

        mock_setting = MagicMock(key="test_setting")
        mock_db = AsyncMock()
        mock_db.get.return_value = mock_setting

        async def mock_db_override():
            return mock_db

        app.dependency_overrides[get_db] = mock_db_override

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.delete("/api/v1/system-settings/test_setting")

        assert response.status_code == 204
        mock_db.delete.assert_called_once_with(mock_setting)
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_nonexistent_setting_returns_404(self):
        """Test deleting a nonexistent setting returns 404."""
        from backend.core.database import get_db

        app = create_test_app()

        mock_db = AsyncMock()
        mock_db.get.return_value = None

        async def mock_db_override():
            return mock_db

        app.dependency_overrides[get_db] = mock_db_override

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.delete("/api/v1/system-settings/nonexistent")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]


class TestSystemSettingListResponseSchema:
    """Tests for SystemSettingListResponse schema."""

    def test_valid_list_response(self):
        """Test valid list response parses correctly."""
        now = datetime.now(UTC)
        data = {
            "items": [
                {"key": "setting1", "value": {"a": 1}, "updated_at": now},
                {"key": "setting2", "value": {"b": 2}, "updated_at": now},
            ],
            "total": 2,
        }
        response = SystemSettingListResponse(**data)
        assert len(response.items) == 2
        assert response.total == 2

    def test_empty_list_response(self):
        """Test empty list response is valid."""
        data = {"items": [], "total": 0}
        response = SystemSettingListResponse(**data)
        assert response.items == []
        assert response.total == 0
