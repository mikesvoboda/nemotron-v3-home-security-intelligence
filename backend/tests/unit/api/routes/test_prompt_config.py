"""Unit tests for database-backed prompt config API endpoints.

Tests cover:
- GET /api/ai-audit/prompt-config/{model} - Get prompt config from database
- PUT /api/ai-audit/prompt-config/{model} - Update prompt config in database
"""

import os
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

# Set DATABASE_URL for tests before importing any backend modules
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://test:test@localhost:5432/test",  # pragma: allowlist secret
)

from backend.api.routes.ai_audit import router
from backend.api.schemas.ai_audit import PromptConfigRequest, PromptConfigResponse
from backend.models.prompt_config import PromptConfig


def create_mock_prompt_config(
    config_id: int = 1,
    model: str = "nemotron",
    system_prompt: str = "You are a security analyst...",
    temperature: float = 0.7,
    max_tokens: int = 2048,
    version: int = 1,
) -> MagicMock:
    """Create a mock PromptConfig object."""
    config = MagicMock(spec=PromptConfig)
    config.id = config_id
    config.model = model
    config.system_prompt = system_prompt
    config.temperature = temperature
    config.max_tokens = max_tokens
    config.version = version
    config.created_at = datetime(2026, 1, 5, 12, 0, 0, tzinfo=UTC)
    config.updated_at = datetime(2026, 1, 5, 12, 0, 0, tzinfo=UTC)
    return config


@pytest.fixture
def mock_db_session() -> MagicMock:
    """Create a mock database session."""
    session = MagicMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()
    return session


@pytest.fixture
def client(mock_db_session: MagicMock) -> TestClient:
    """Create a test client with mocked dependencies."""
    from backend.core.database import get_db

    app = FastAPI()
    app.include_router(router)

    # Override the database dependency
    async def override_get_db():
        yield mock_db_session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client


class TestGetPromptConfigEndpoint:
    """Tests for GET /api/ai-audit/prompt-config/{model} endpoint."""

    def test_get_prompt_config_returns_config(
        self,
        client: TestClient,
        mock_db_session: MagicMock,
    ) -> None:
        """Test successful retrieval of prompt configuration."""
        mock_config = create_mock_prompt_config(
            model="nemotron",
            system_prompt="Test prompt",
            temperature=0.8,
            max_tokens=4096,
            version=3,
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_config
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = client.get("/api/ai-audit/prompt-config/nemotron")

        assert response.status_code == 200
        data = response.json()
        assert data["model"] == "nemotron"
        assert data["systemPrompt"] == "Test prompt"
        assert data["temperature"] == 0.8
        assert data["maxTokens"] == 4096
        assert data["version"] == 3
        assert "updatedAt" in data

    def test_get_prompt_config_unknown_model_404(
        self,
        client: TestClient,
        mock_db_session: MagicMock,
    ) -> None:
        """Test 404 returned for unknown model name."""
        response = client.get("/api/ai-audit/prompt-config/unknown-model")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
        # Note: Error message intentionally does not expose supported model list for security

    def test_get_prompt_config_no_config_exists_404(
        self,
        client: TestClient,
        mock_db_session: MagicMock,
    ) -> None:
        """Test 404 when no configuration exists for model."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = client.get("/api/ai-audit/prompt-config/nemotron")

        assert response.status_code == 404
        assert "No configuration found" in response.json()["detail"]

    def test_get_prompt_config_all_supported_models(
        self,
        client: TestClient,
        mock_db_session: MagicMock,
    ) -> None:
        """Test that all supported model names are accepted."""
        supported_models = [
            "nemotron",
            "florence-2",
            "yolo-world",
            "x-clip",
            "fashion-clip",
        ]

        for model in supported_models:
            mock_config = create_mock_prompt_config(model=model)
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_config
            mock_db_session.execute = AsyncMock(return_value=mock_result)

            response = client.get(f"/api/ai-audit/prompt-config/{model}")

            # Should not return 404 for "unknown model"
            # May return 404 for "no configuration found" which is OK
            if response.status_code == 404:
                assert (
                    "not found" not in response.json()["detail"].lower()
                    or "No configuration found" in response.json()["detail"]
                )


class TestUpdatePromptConfigEndpoint:
    """Tests for PUT /api/ai-audit/prompt-config/{model} endpoint."""

    def test_update_prompt_config_creates_new(
        self,
        client: TestClient,
        mock_db_session: MagicMock,
    ) -> None:
        """Test creating a new configuration when none exists."""
        # No existing config
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        # After commit/refresh, return the new config
        def mock_refresh(config):
            config.id = 1
            config.version = 1
            config.updated_at = datetime(2026, 1, 5, 12, 0, 0, tzinfo=UTC)

        mock_db_session.refresh = AsyncMock(side_effect=mock_refresh)

        response = client.put(
            "/api/ai-audit/prompt-config/nemotron",
            json={
                "systemPrompt": "New system prompt",
                "temperature": 0.9,
                "maxTokens": 3000,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["model"] == "nemotron"
        assert data["systemPrompt"] == "New system prompt"
        assert data["temperature"] == 0.9
        assert data["maxTokens"] == 3000
        assert data["version"] == 1

        # Verify db.add was called
        mock_db_session.add.assert_called_once()

    def test_update_prompt_config_increments_version(
        self,
        client: TestClient,
        mock_db_session: MagicMock,
    ) -> None:
        """Test that updating existing config increments version."""
        # Existing config with version 2
        mock_config = create_mock_prompt_config(version=2)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_config
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = client.put(
            "/api/ai-audit/prompt-config/nemotron",
            json={
                "systemPrompt": "Updated prompt",
                "temperature": 0.5,
                "maxTokens": 2000,
            },
        )

        assert response.status_code == 200
        data = response.json()
        # Version should be incremented from 2 to 3
        assert data["version"] == 3
        assert data["systemPrompt"] == "Updated prompt"
        assert data["temperature"] == 0.5
        assert data["maxTokens"] == 2000

        # Verify db.add was NOT called (we're updating, not creating)
        mock_db_session.add.assert_not_called()

    def test_update_prompt_config_validates_temperature(
        self,
        client: TestClient,
        mock_db_session: MagicMock,
    ) -> None:
        """Test temperature validation (0-2 range)."""
        # Temperature too high
        response = client.put(
            "/api/ai-audit/prompt-config/nemotron",
            json={
                "systemPrompt": "Test prompt",
                "temperature": 2.5,
                "maxTokens": 2048,
            },
        )
        assert response.status_code == 422

        # Temperature too low
        response = client.put(
            "/api/ai-audit/prompt-config/nemotron",
            json={
                "systemPrompt": "Test prompt",
                "temperature": -0.1,
                "maxTokens": 2048,
            },
        )
        assert response.status_code == 422

    def test_update_prompt_config_validates_max_tokens(
        self,
        client: TestClient,
        mock_db_session: MagicMock,
    ) -> None:
        """Test max_tokens validation (100-8192 range)."""
        # Too low
        response = client.put(
            "/api/ai-audit/prompt-config/nemotron",
            json={
                "systemPrompt": "Test prompt",
                "temperature": 0.7,
                "maxTokens": 50,
            },
        )
        assert response.status_code == 422

        # Too high
        response = client.put(
            "/api/ai-audit/prompt-config/nemotron",
            json={
                "systemPrompt": "Test prompt",
                "temperature": 0.7,
                "maxTokens": 10000,
            },
        )
        assert response.status_code == 422

    def test_update_prompt_config_requires_system_prompt(
        self,
        client: TestClient,
        mock_db_session: MagicMock,
    ) -> None:
        """Test that system_prompt is required."""
        response = client.put(
            "/api/ai-audit/prompt-config/nemotron",
            json={
                "temperature": 0.7,
                "maxTokens": 2048,
            },
        )
        assert response.status_code == 422

    def test_update_prompt_config_unknown_model_404(
        self,
        client: TestClient,
        mock_db_session: MagicMock,
    ) -> None:
        """Test 404 returned for unknown model name."""
        response = client.put(
            "/api/ai-audit/prompt-config/unknown-model",
            json={
                "systemPrompt": "Test prompt",
                "temperature": 0.7,
                "maxTokens": 2048,
            },
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_update_prompt_config_default_values(
        self,
        client: TestClient,
        mock_db_session: MagicMock,
    ) -> None:
        """Test that temperature and max_tokens use defaults when not provided."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        def mock_refresh(config):
            config.id = 1
            config.version = 1
            config.updated_at = datetime(2026, 1, 5, 12, 0, 0, tzinfo=UTC)

        mock_db_session.refresh = AsyncMock(side_effect=mock_refresh)

        response = client.put(
            "/api/ai-audit/prompt-config/nemotron",
            json={
                "systemPrompt": "Only system prompt provided",
            },
        )

        assert response.status_code == 200
        data = response.json()
        # Default values should be used
        assert data["temperature"] == 0.7
        assert data["maxTokens"] == 2048


class TestPromptConfigRequestSchema:
    """Tests for PromptConfigRequest Pydantic schema."""

    def test_valid_request(self) -> None:
        """Test PromptConfigRequest with valid data."""
        request = PromptConfigRequest(
            system_prompt="Test prompt",
            temperature=0.8,
            max_tokens=4096,
        )
        assert request.system_prompt == "Test prompt"
        assert request.temperature == 0.8
        assert request.max_tokens == 4096

    def test_camel_case_alias(self) -> None:
        """Test that camelCase aliases work."""
        # Should work with camelCase (from frontend)
        request = PromptConfigRequest.model_validate(
            {
                "systemPrompt": "Test prompt",
                "temperature": 0.8,
                "maxTokens": 4096,
            }
        )
        assert request.system_prompt == "Test prompt"
        assert request.max_tokens == 4096

    def test_snake_case_also_works(self) -> None:
        """Test that snake_case also works (populate_by_name=True)."""
        request = PromptConfigRequest.model_validate(
            {
                "system_prompt": "Test prompt",
                "temperature": 0.8,
                "max_tokens": 4096,
            }
        )
        assert request.system_prompt == "Test prompt"
        assert request.max_tokens == 4096

    def test_empty_system_prompt_rejected(self) -> None:
        """Test that empty system_prompt is rejected."""
        with pytest.raises(ValidationError):
            PromptConfigRequest(
                system_prompt="",
                temperature=0.7,
                max_tokens=2048,
            )

    def test_temperature_range_validation(self) -> None:
        """Test temperature must be between 0 and 2."""
        with pytest.raises(ValidationError):
            PromptConfigRequest(
                system_prompt="Test",
                temperature=3.0,
                max_tokens=2048,
            )

    def test_max_tokens_range_validation(self) -> None:
        """Test max_tokens must be between 100 and 8192."""
        with pytest.raises(ValidationError):
            PromptConfigRequest(
                system_prompt="Test",
                temperature=0.7,
                max_tokens=50,
            )


class TestPromptConfigResponseSchema:
    """Tests for PromptConfigResponse Pydantic schema."""

    def test_valid_response(self) -> None:
        """Test PromptConfigResponse with valid data."""
        response = PromptConfigResponse(
            model="nemotron",
            system_prompt="Test prompt",
            temperature=0.8,
            max_tokens=4096,
            version=1,
            updated_at=datetime(2026, 1, 5, 12, 0, 0, tzinfo=UTC),
        )
        assert response.model == "nemotron"
        assert response.system_prompt == "Test prompt"
        assert response.version == 1

    def test_json_serialization_uses_camel_case(self) -> None:
        """Test that JSON serialization uses camelCase aliases."""
        response = PromptConfigResponse(
            model="nemotron",
            system_prompt="Test prompt",
            temperature=0.8,
            max_tokens=4096,
            version=1,
            updated_at=datetime(2026, 1, 5, 12, 0, 0, tzinfo=UTC),
        )
        data = response.model_dump(by_alias=True)
        assert "systemPrompt" in data
        assert "maxTokens" in data
        assert "updatedAt" in data
