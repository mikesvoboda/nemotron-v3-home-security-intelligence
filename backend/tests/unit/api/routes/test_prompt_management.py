"""Unit tests for prompt_management API routes.

Tests cover:
- GET /api/ai-audit/prompts - Get all prompts
- GET /api/ai-audit/prompts/export - Export all prompts
- GET /api/ai-audit/prompts/history - Get version history
- GET /api/ai-audit/prompts/{model} - Get prompt for specific model
- PUT /api/ai-audit/prompts/{model} - Update prompt for model
- POST /api/ai-audit/prompts/test - Test a prompt configuration
- POST /api/ai-audit/prompts/import - Import prompt configurations
- POST /api/ai-audit/prompts/import/preview - Preview import changes
- POST /api/ai-audit/prompts/history/{version_id} - Restore a version
"""

import json
import os
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Set DATABASE_URL for tests before importing any backend modules
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://test:test@localhost:5432/test",  # pragma: allowlist secret
)

from backend.api.routes.prompt_management import _compute_config_diff, router
from backend.api.schemas.prompt_management import (
    AIModelEnum,
    AllPromptsResponse,
    ModelPromptConfig,
    PromptDiffEntry,
    PromptHistoryResponse,
    PromptRestoreResponse,
    PromptsExportResponse,
    PromptsImportPreviewRequest,
    PromptsImportPreviewResponse,
    PromptsImportRequest,
    PromptsImportResponse,
    PromptTestRequest,
    PromptTestResult,
    PromptUpdateRequest,
    PromptVersionInfo,
)


def create_mock_prompt_version(
    version_id: int = 1,
    model: str = "nemotron",
    version: int = 1,
    config: dict | None = None,
    is_active: bool = True,
    created_by: str | None = "system",
    change_description: str | None = None,
) -> MagicMock:
    """Create a mock PromptVersion object."""
    mock = MagicMock()
    mock.id = version_id
    mock.model = model
    mock.version = version
    mock.config = config or {"system_prompt": "test prompt", "version": version}
    mock.config_json = json.dumps(mock.config)
    mock.is_active = is_active
    mock.created_at = datetime(2025, 12, 23, 12, 0, 0, tzinfo=UTC)
    mock.created_by = created_by
    mock.change_description = change_description
    return mock


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
def mock_prompt_service() -> MagicMock:
    """Create a mock prompt service."""
    service = MagicMock()
    service.get_all_prompts = AsyncMock()
    service.get_prompt_for_model = AsyncMock()
    service.update_prompt_for_model = AsyncMock()
    service.test_prompt = AsyncMock()
    service.get_version_history = AsyncMock()
    service.restore_version = AsyncMock()
    service.export_all_prompts = AsyncMock()
    service.import_prompts = AsyncMock()
    return service


@pytest.fixture
def client(mock_db_session: MagicMock, mock_prompt_service: MagicMock) -> TestClient:
    """Create a test client with mocked dependencies."""
    from backend.core.database import get_db

    app = FastAPI()
    app.include_router(router)

    async def override_get_db():
        yield mock_db_session

    app.dependency_overrides[get_db] = override_get_db

    # Mock Redis to prevent connection errors in CI where Redis is not available
    mock_redis_client = AsyncMock()
    mock_redis_client.health_check.return_value = {
        "status": "healthy",
        "connected": True,
        "redis_version": "7.0.0",
    }

    with (
        patch(
            "backend.api.routes.prompt_management.get_prompt_service",
            return_value=mock_prompt_service,
        ),
        patch("backend.core.redis._redis_client", mock_redis_client),
        patch("backend.core.redis.init_redis", return_value=mock_redis_client),
        patch("backend.core.redis.close_redis", return_value=None),
        TestClient(app) as test_client,
    ):
        yield test_client


class TestGetAllPromptsEndpoint:
    """Tests for GET /api/ai-audit/prompts endpoint."""

    def test_get_all_prompts_success(
        self,
        client: TestClient,
        mock_prompt_service: MagicMock,
    ) -> None:
        """Test successful retrieval of all prompts."""
        mock_prompt_service.get_all_prompts.return_value = {
            "nemotron": {"system_prompt": "test prompt", "version": 1},
            "florence2": {"queries": ["test query"]},
            "yolo_world": {"classes": ["knife"], "confidence_threshold": 0.35},
            "xclip": {"action_classes": ["running"]},
            "fashion_clip": {"clothing_categories": ["hoodie"]},
        }

        response = client.get("/api/ai-audit/prompts")

        assert response.status_code == 200
        data = response.json()
        assert data["version"] == "1.0"
        assert "exported_at" in data
        assert "prompts" in data
        assert "nemotron" in data["prompts"]
        assert data["prompts"]["nemotron"]["system_prompt"] == "test prompt"
        mock_prompt_service.get_all_prompts.assert_called_once()

    def test_get_all_prompts_empty(
        self,
        client: TestClient,
        mock_prompt_service: MagicMock,
    ) -> None:
        """Test retrieval when no prompts are configured."""
        mock_prompt_service.get_all_prompts.return_value = {}

        response = client.get("/api/ai-audit/prompts")

        assert response.status_code == 200
        data = response.json()
        assert data["prompts"] == {}


class TestExportPromptsEndpoint:
    """Tests for GET /api/ai-audit/prompts/export endpoint."""

    def test_export_prompts_success(
        self,
        client: TestClient,
        mock_prompt_service: MagicMock,
    ) -> None:
        """Test successful export of all prompts."""
        mock_prompt_service.export_all_prompts.return_value = {
            "version": "1.0",
            "exported_at": datetime(2025, 12, 23, 12, 0, 0, tzinfo=UTC).isoformat(),
            "prompts": {
                "nemotron": {"system_prompt": "test prompt"},
                "florence2": {"queries": ["test query"]},
            },
        }

        response = client.get("/api/ai-audit/prompts/export")

        assert response.status_code == 200
        data = response.json()
        assert data["version"] == "1.0"
        assert "exported_at" in data
        assert "prompts" in data
        assert "nemotron" in data["prompts"]
        mock_prompt_service.export_all_prompts.assert_called_once()

    def test_export_prompts_with_datetime_object(
        self,
        client: TestClient,
        mock_prompt_service: MagicMock,
    ) -> None:
        """Test export handles datetime object in exported_at."""
        mock_prompt_service.export_all_prompts.return_value = {
            "version": "1.0",
            "exported_at": datetime(2025, 12, 23, 12, 0, 0, tzinfo=UTC),
            "prompts": {"nemotron": {"system_prompt": "test"}},
        }

        response = client.get("/api/ai-audit/prompts/export")

        assert response.status_code == 200


class TestGetPromptHistoryEndpoint:
    """Tests for GET /api/ai-audit/prompts/history endpoint."""

    def test_get_history_success(
        self,
        client: TestClient,
        mock_prompt_service: MagicMock,
    ) -> None:
        """Test successful retrieval of version history."""
        mock_versions = [
            create_mock_prompt_version(version_id=2, version=2, is_active=True),
            create_mock_prompt_version(version_id=1, version=1, is_active=False),
        ]
        mock_prompt_service.get_version_history.return_value = (mock_versions, 2)

        response = client.get("/api/ai-audit/prompts/history")

        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 2
        assert len(data["versions"]) == 2
        assert data["versions"][0]["version"] == 2
        assert data["versions"][0]["is_active"] is True
        mock_prompt_service.get_version_history.assert_called_once()

    def test_get_history_with_model_filter(
        self,
        client: TestClient,
        mock_prompt_service: MagicMock,
    ) -> None:
        """Test history filtered by model."""
        mock_versions = [create_mock_prompt_version(model="florence2")]
        mock_prompt_service.get_version_history.return_value = (mock_versions, 1)

        response = client.get("/api/ai-audit/prompts/history?model=florence2")

        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 1
        # Verify the filter was passed
        call_args = mock_prompt_service.get_version_history.call_args
        assert call_args.kwargs.get("model") == "florence2"

    def test_get_history_with_pagination(
        self,
        client: TestClient,
        mock_prompt_service: MagicMock,
    ) -> None:
        """Test history with pagination parameters."""
        mock_prompt_service.get_version_history.return_value = ([], 100)

        response = client.get("/api/ai-audit/prompts/history?limit=10&offset=20")

        assert response.status_code == 200
        call_args = mock_prompt_service.get_version_history.call_args
        assert call_args.kwargs.get("limit") == 10
        assert call_args.kwargs.get("offset") == 20

    def test_get_history_empty(
        self,
        client: TestClient,
        mock_prompt_service: MagicMock,
    ) -> None:
        """Test history when no versions exist."""
        mock_prompt_service.get_version_history.return_value = ([], 0)

        response = client.get("/api/ai-audit/prompts/history")

        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 0
        assert data["versions"] == []

    def test_get_history_invalid_limit(
        self,
        client: TestClient,
    ) -> None:
        """Test validation error for invalid limit parameter."""
        response = client.get("/api/ai-audit/prompts/history?limit=0")
        assert response.status_code == 422

        response = client.get("/api/ai-audit/prompts/history?limit=101")
        assert response.status_code == 422

    def test_get_history_invalid_offset(
        self,
        client: TestClient,
    ) -> None:
        """Test validation error for invalid offset parameter."""
        response = client.get("/api/ai-audit/prompts/history?offset=-1")
        assert response.status_code == 422

    def test_get_history_invalid_model(
        self,
        client: TestClient,
    ) -> None:
        """Test validation error for invalid model parameter."""
        response = client.get("/api/ai-audit/prompts/history?model=invalid_model")
        assert response.status_code == 422

    def test_get_history_returns_versions_in_descending_order(
        self,
        client: TestClient,
        mock_prompt_service: MagicMock,
    ) -> None:
        """Test that version history is returned newest first (descending order)."""
        # Create versions with descending order (as they should be returned)
        mock_versions = [
            create_mock_prompt_version(version_id=5, version=5, is_active=True),
            create_mock_prompt_version(version_id=4, version=4, is_active=False),
            create_mock_prompt_version(version_id=3, version=3, is_active=False),
            create_mock_prompt_version(version_id=2, version=2, is_active=False),
            create_mock_prompt_version(version_id=1, version=1, is_active=False),
        ]
        # Set distinct timestamps to verify ordering
        for i, mock_v in enumerate(mock_versions):
            mock_v.created_at = datetime(2025, 12, 23, 12, 0, 0, tzinfo=UTC) - timedelta(hours=i)

        mock_prompt_service.get_version_history.return_value = (mock_versions, 5)

        response = client.get("/api/ai-audit/prompts/history")

        assert response.status_code == 200
        data = response.json()
        versions = data["versions"]

        # Verify versions are in descending order by version number
        for i in range(len(versions) - 1):
            assert versions[i]["version"] > versions[i + 1]["version"], (
                f"Version {versions[i]['version']} should be greater than {versions[i + 1]['version']}"
            )

        # Also verify the first (newest) version is marked active
        assert versions[0]["is_active"] is True
        assert versions[0]["version"] == 5

    def test_get_history_pagination_maintains_consistent_ordering(
        self,
        client: TestClient,
        mock_prompt_service: MagicMock,
    ) -> None:
        """Test that pagination maintains consistent ordering across pages."""
        # Simulate first page (offset=0, limit=3) - versions 10, 9, 8
        first_page_versions = [
            create_mock_prompt_version(version_id=10, version=10, is_active=True),
            create_mock_prompt_version(version_id=9, version=9, is_active=False),
            create_mock_prompt_version(version_id=8, version=8, is_active=False),
        ]
        for i, mock_v in enumerate(first_page_versions):
            mock_v.created_at = datetime(2025, 12, 23, 12, 0, 0, tzinfo=UTC) - timedelta(hours=i)

        mock_prompt_service.get_version_history.return_value = (first_page_versions, 10)

        response1 = client.get("/api/ai-audit/prompts/history?limit=3&offset=0")
        assert response1.status_code == 200
        data1 = response1.json()

        # Verify first page ordering
        assert data1["versions"][0]["version"] == 10
        assert data1["versions"][1]["version"] == 9
        assert data1["versions"][2]["version"] == 8

        # Simulate second page (offset=3, limit=3) - versions 7, 6, 5
        second_page_versions = [
            create_mock_prompt_version(version_id=7, version=7, is_active=False),
            create_mock_prompt_version(version_id=6, version=6, is_active=False),
            create_mock_prompt_version(version_id=5, version=5, is_active=False),
        ]
        for i, mock_v in enumerate(second_page_versions):
            mock_v.created_at = datetime(2025, 12, 23, 12, 0, 0, tzinfo=UTC) - timedelta(
                hours=3 + i
            )

        mock_prompt_service.get_version_history.return_value = (second_page_versions, 10)

        response2 = client.get("/api/ai-audit/prompts/history?limit=3&offset=3")
        assert response2.status_code == 200
        data2 = response2.json()

        # Verify second page ordering
        assert data2["versions"][0]["version"] == 7
        assert data2["versions"][1]["version"] == 6
        assert data2["versions"][2]["version"] == 5

        # Verify no overlap and consistent continuation
        last_version_first_page = data1["versions"][-1]["version"]
        first_version_second_page = data2["versions"][0]["version"]
        assert last_version_first_page > first_version_second_page, (
            f"Last version of page 1 ({last_version_first_page}) should be greater than "
            f"first version of page 2 ({first_version_second_page})"
        )

        # Verify total count is consistent across pages
        assert data1["total_count"] == data2["total_count"] == 10

    def test_get_history_same_timestamp_orders_by_version(
        self,
        client: TestClient,
        mock_prompt_service: MagicMock,
    ) -> None:
        """Test that versions with same timestamp are ordered by version number descending."""
        # Create versions with identical timestamps but different version numbers
        same_timestamp = datetime(2025, 12, 23, 12, 0, 0, tzinfo=UTC)
        mock_versions = [
            create_mock_prompt_version(version_id=3, version=3, is_active=True),
            create_mock_prompt_version(version_id=2, version=2, is_active=False),
            create_mock_prompt_version(version_id=1, version=1, is_active=False),
        ]
        # Set all versions to have the same timestamp
        for mock_v in mock_versions:
            mock_v.created_at = same_timestamp

        mock_prompt_service.get_version_history.return_value = (mock_versions, 3)

        response = client.get("/api/ai-audit/prompts/history")

        assert response.status_code == 200
        data = response.json()
        versions = data["versions"]

        # Even with same timestamps, versions should be in descending order by version number
        assert len(versions) == 3
        assert versions[0]["version"] == 3
        assert versions[1]["version"] == 2
        assert versions[2]["version"] == 1

        # Verify ordering invariant
        for i in range(len(versions) - 1):
            assert versions[i]["version"] > versions[i + 1]["version"]

    def test_get_history_model_filter_preserves_ordering(
        self,
        client: TestClient,
        mock_prompt_service: MagicMock,
    ) -> None:
        """Test that filtering by model preserves descending version order."""
        # Create versions for a specific model
        mock_versions = [
            create_mock_prompt_version(version_id=6, version=6, model="florence2", is_active=True),
            create_mock_prompt_version(version_id=4, version=4, model="florence2", is_active=False),
            create_mock_prompt_version(version_id=2, version=2, model="florence2", is_active=False),
        ]
        for i, mock_v in enumerate(mock_versions):
            mock_v.created_at = datetime(2025, 12, 23, 12, 0, 0, tzinfo=UTC) - timedelta(days=i)

        mock_prompt_service.get_version_history.return_value = (mock_versions, 3)

        response = client.get("/api/ai-audit/prompts/history?model=florence2")

        assert response.status_code == 200
        data = response.json()
        versions = data["versions"]

        # All returned versions should be for florence2
        assert all(v["model"] == "florence2" for v in versions)

        # Verify ordering is preserved
        assert versions[0]["version"] == 6
        assert versions[1]["version"] == 4
        assert versions[2]["version"] == 2

        for i in range(len(versions) - 1):
            assert versions[i]["version"] > versions[i + 1]["version"]


class TestGetPromptForModelEndpoint:
    """Tests for GET /api/ai-audit/prompts/{model} endpoint."""

    def test_get_prompt_success(
        self,
        client: TestClient,
        mock_prompt_service: MagicMock,
    ) -> None:
        """Test successful retrieval of prompt for specific model."""
        mock_prompt_service.get_prompt_for_model.return_value = {
            "system_prompt": "test prompt",
            "version": 3,
        }

        response = client.get("/api/ai-audit/prompts/nemotron")

        assert response.status_code == 200
        data = response.json()
        assert data["model"] == "nemotron"
        assert data["version"] == 3
        assert data["config"]["system_prompt"] == "test prompt"

    def test_get_prompt_florence2(
        self,
        client: TestClient,
        mock_prompt_service: MagicMock,
    ) -> None:
        """Test retrieval of florence2 prompt."""
        mock_prompt_service.get_prompt_for_model.return_value = {
            "queries": ["What is happening?", "Who is there?"],
            "version": 1,
        }

        response = client.get("/api/ai-audit/prompts/florence2")

        assert response.status_code == 200
        data = response.json()
        assert data["model"] == "florence2"
        assert "queries" in data["config"]

    def test_get_prompt_yolo_world(
        self,
        client: TestClient,
        mock_prompt_service: MagicMock,
    ) -> None:
        """Test retrieval of yolo_world prompt."""
        mock_prompt_service.get_prompt_for_model.return_value = {
            "classes": ["knife", "gun"],
            "confidence_threshold": 0.4,
            "version": 2,
        }

        response = client.get("/api/ai-audit/prompts/yolo_world")

        assert response.status_code == 200
        data = response.json()
        assert data["model"] == "yolo_world"
        assert data["config"]["confidence_threshold"] == 0.4

    def test_get_prompt_not_found(
        self,
        client: TestClient,
        mock_prompt_service: MagicMock,
    ) -> None:
        """Test 404 when model has no configuration."""
        mock_prompt_service.get_prompt_for_model.return_value = None

        response = client.get("/api/ai-audit/prompts/nemotron")

        assert response.status_code == 404
        assert "No configuration found" in response.json()["detail"]

    def test_get_prompt_invalid_model(
        self,
        client: TestClient,
    ) -> None:
        """Test validation error for invalid model."""
        response = client.get("/api/ai-audit/prompts/invalid_model")

        assert response.status_code == 422


class TestUpdatePromptForModelEndpoint:
    """Tests for PUT /api/ai-audit/prompts/{model} endpoint."""

    def test_update_prompt_success(
        self,
        client: TestClient,
        mock_prompt_service: MagicMock,
    ) -> None:
        """Test successful update of prompt."""
        mock_version = create_mock_prompt_version(
            version_id=2,
            version=2,
            config={"system_prompt": "updated prompt"},
            change_description="Updated system prompt",
        )
        mock_prompt_service.update_prompt_for_model.return_value = mock_version

        response = client.put(
            "/api/ai-audit/prompts/nemotron",
            json={
                "config": {"system_prompt": "updated prompt"},
                "change_description": "Updated system prompt",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["model"] == "nemotron"
        assert data["version"] == 2
        mock_prompt_service.update_prompt_for_model.assert_called_once()

    def test_update_prompt_without_description(
        self,
        client: TestClient,
        mock_prompt_service: MagicMock,
    ) -> None:
        """Test update without change description."""
        mock_version = create_mock_prompt_version(version=2)
        mock_prompt_service.update_prompt_for_model.return_value = mock_version

        response = client.put(
            "/api/ai-audit/prompts/nemotron",
            json={"config": {"system_prompt": "new prompt"}},
        )

        assert response.status_code == 200

    def test_update_prompt_empty_config(
        self,
        client: TestClient,
    ) -> None:
        """Test validation error for empty config."""
        response = client.put(
            "/api/ai-audit/prompts/nemotron",
            json={"config": {}},
        )

        assert response.status_code == 422

    def test_update_prompt_invalid_model(
        self,
        client: TestClient,
    ) -> None:
        """Test validation error for invalid model."""
        response = client.put(
            "/api/ai-audit/prompts/invalid_model",
            json={"config": {"key": "value"}},
        )

        assert response.status_code == 422


class TestTestPromptEndpoint:
    """Tests for POST /api/ai-audit/prompts/test endpoint."""

    def test_test_prompt_success(
        self,
        client: TestClient,
        mock_prompt_service: MagicMock,
    ) -> None:
        """Test successful prompt testing."""
        mock_prompt_service.test_prompt.return_value = {
            "before_score": 70,
            "after_score": 65,
            "before_response": {"risk_score": 70},
            "after_response": {"risk_score": 65},
            "improved": True,
            "test_duration_ms": 1500,
            "error": None,
        }

        response = client.post(
            "/api/ai-audit/prompts/test",
            json={
                "model": "nemotron",
                "config": {"system_prompt": "test prompt"},
                "event_id": 123,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["model"] == "nemotron"
        assert data["before_score"] == 70
        assert data["after_score"] == 65
        assert data["improved"] is True
        assert data["test_duration_ms"] == 1500

    def test_test_prompt_with_image_path(
        self,
        client: TestClient,
        mock_prompt_service: MagicMock,
    ) -> None:
        """Test prompt testing with image path instead of event_id."""
        mock_prompt_service.test_prompt.return_value = {
            "before_score": None,
            "after_score": 80,
            "before_response": None,
            "after_response": {"risk_score": 80},
            "improved": None,
            "test_duration_ms": 2000,
            "error": None,
        }

        response = client.post(
            "/api/ai-audit/prompts/test",
            json={
                "model": "nemotron",
                "config": {"system_prompt": "test"},
                "image_path": "/path/to/image.jpg",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["after_score"] == 80

    def test_test_prompt_with_error(
        self,
        client: TestClient,
        mock_prompt_service: MagicMock,
    ) -> None:
        """Test prompt testing when error occurs."""
        mock_prompt_service.test_prompt.return_value = {
            "before_score": None,
            "after_score": None,
            "before_response": None,
            "after_response": None,
            "improved": None,
            "test_duration_ms": 100,
            "error": "Event not found",
        }

        response = client.post(
            "/api/ai-audit/prompts/test",
            json={
                "model": "nemotron",
                "config": {"system_prompt": "test"},
                "event_id": 999,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["error"] == "Event not found"

    def test_test_prompt_invalid_model(
        self,
        client: TestClient,
    ) -> None:
        """Test validation error for invalid model."""
        response = client.post(
            "/api/ai-audit/prompts/test",
            json={
                "model": "invalid_model",
                "config": {"key": "value"},
            },
        )

        assert response.status_code == 422


class TestImportPromptsEndpoint:
    """Tests for POST /api/ai-audit/prompts/import endpoint."""

    def test_import_prompts_success(
        self,
        client: TestClient,
        mock_prompt_service: MagicMock,
    ) -> None:
        """Test successful import of prompts."""
        mock_prompt_service.import_prompts.return_value = {
            "imported_models": ["nemotron", "florence2"],
            "skipped_models": [],
            "new_versions": {"nemotron": 2, "florence2": 1},
            "message": "Imported 2 model configurations",
        }

        response = client.post(
            "/api/ai-audit/prompts/import",
            json={
                "version": "1.0",
                "prompts": {
                    "nemotron": {"system_prompt": "imported prompt"},
                    "florence2": {"queries": ["query"]},
                },
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["imported_models"]) == 2
        assert "nemotron" in data["imported_models"]
        assert data["new_versions"]["nemotron"] == 2

    def test_import_prompts_partial_success(
        self,
        client: TestClient,
        mock_prompt_service: MagicMock,
    ) -> None:
        """Test import with some models skipped."""
        mock_prompt_service.import_prompts.return_value = {
            "imported_models": ["nemotron"],
            "skipped_models": ["unknown_model"],
            "new_versions": {"nemotron": 3},
            "message": "Imported 1 model configurations",
        }

        response = client.post(
            "/api/ai-audit/prompts/import",
            json={
                "version": "1.0",
                "prompts": {
                    "nemotron": {"system_prompt": "test"},
                    "unknown_model": {"config": "value"},
                },
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "unknown_model" in data["skipped_models"]

    def test_import_prompts_empty_prompts(
        self,
        client: TestClient,
    ) -> None:
        """Test validation error for empty prompts."""
        response = client.post(
            "/api/ai-audit/prompts/import",
            json={"version": "1.0", "prompts": {}},
        )

        assert response.status_code == 422


class TestImportPreviewEndpoint:
    """Tests for POST /api/ai-audit/prompts/import/preview endpoint."""

    def test_import_preview_success(
        self,
        client: TestClient,
        mock_prompt_service: MagicMock,
    ) -> None:
        """Test successful import preview."""
        mock_prompt_service.get_prompt_for_model.return_value = {
            "system_prompt": "old prompt",
            "version": 1,
        }

        response = client.post(
            "/api/ai-audit/prompts/import/preview",
            json={
                "version": "1.0",
                "prompts": {
                    "nemotron": {"system_prompt": "new prompt"},
                },
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["version"] == "1.0"
        assert data["valid"] is True
        assert len(data["diffs"]) == 1
        assert data["diffs"][0]["model"] == "nemotron"
        assert data["diffs"][0]["has_changes"] is True
        assert data["total_changes"] == 1

    def test_import_preview_no_changes(
        self,
        client: TestClient,
        mock_prompt_service: MagicMock,
    ) -> None:
        """Test preview when config is identical."""
        mock_prompt_service.get_prompt_for_model.return_value = {
            "system_prompt": "same prompt",
            "version": 1,
        }

        response = client.post(
            "/api/ai-audit/prompts/import/preview",
            json={
                "version": "1.0",
                "prompts": {
                    "nemotron": {"system_prompt": "same prompt"},
                },
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_changes"] == 0
        # has_changes should be False when configs are identical
        assert data["diffs"][0]["has_changes"] is False

    def test_import_preview_new_configuration(
        self,
        client: TestClient,
        mock_prompt_service: MagicMock,
    ) -> None:
        """Test preview for model with no existing configuration."""
        mock_prompt_service.get_prompt_for_model.return_value = None

        response = client.post(
            "/api/ai-audit/prompts/import/preview",
            json={
                "version": "1.0",
                "prompts": {
                    "florence2": {"queries": ["new query"]},
                },
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["diffs"][0]["has_changes"] is True
        assert "New configuration" in data["diffs"][0]["changes"][0]

    def test_import_preview_unknown_models(
        self,
        client: TestClient,
        mock_prompt_service: MagicMock,
    ) -> None:
        """Test preview with unknown models."""
        mock_prompt_service.get_prompt_for_model.return_value = {}

        response = client.post(
            "/api/ai-audit/prompts/import/preview",
            json={
                "version": "1.0",
                "prompts": {
                    "unknown_model": {"config": "value"},
                },
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "unknown_model" in data["unknown_models"]

    def test_import_preview_invalid_version(
        self,
        client: TestClient,
        mock_prompt_service: MagicMock,
    ) -> None:
        """Test preview with unsupported version."""
        mock_prompt_service.get_prompt_for_model.return_value = {}

        response = client.post(
            "/api/ai-audit/prompts/import/preview",
            json={
                "version": "2.0",
                "prompts": {
                    "nemotron": {"system_prompt": "test"},
                },
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert "Unsupported version" in data["validation_errors"][0]

    def test_import_preview_empty_prompts(
        self,
        client: TestClient,
    ) -> None:
        """Test validation error for empty prompts."""
        response = client.post(
            "/api/ai-audit/prompts/import/preview",
            json={"version": "1.0", "prompts": {}},
        )

        assert response.status_code == 422


class TestRestoreVersionEndpoint:
    """Tests for POST /api/ai-audit/prompts/history/{version_id} endpoint."""

    def test_restore_version_success(
        self,
        client: TestClient,
        mock_db_session: MagicMock,
        mock_prompt_service: MagicMock,
    ) -> None:
        """Test successful version restore."""
        # Mock the new version created by restore
        mock_new_version = create_mock_prompt_version(
            version_id=3,
            version=3,
            model="nemotron",
        )
        mock_prompt_service.restore_version.return_value = mock_new_version

        # Mock the query to get original version info
        mock_original = create_mock_prompt_version(
            version_id=1,
            version=1,
            model="nemotron",
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_original
        mock_db_session.execute.return_value = mock_result

        response = client.post("/api/ai-audit/prompts/history/1")

        assert response.status_code == 200
        data = response.json()
        assert data["restored_version"] == 1
        assert data["new_version"] == 3
        assert data["model"] == "nemotron"
        assert "Successfully restored" in data["message"]

    def test_restore_version_not_found(
        self,
        client: TestClient,
        mock_prompt_service: MagicMock,
    ) -> None:
        """Test 404 when version doesn't exist."""
        mock_prompt_service.restore_version.side_effect = ValueError("Version 999 not found")

        response = client.post("/api/ai-audit/prompts/history/999")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_restore_version_invalid_id(
        self,
        client: TestClient,
    ) -> None:
        """Test validation error for invalid version ID."""
        response = client.post("/api/ai-audit/prompts/history/invalid")

        assert response.status_code == 422


class TestComputeConfigDiff:
    """Tests for _compute_config_diff helper function."""

    def test_diff_new_config(self) -> None:
        """Test diff when no current config exists."""
        has_changes, changes = _compute_config_diff(None, {"key": "value"})

        assert has_changes is True
        assert "New configuration" in changes[0]

    def test_diff_no_changes(self) -> None:
        """Test diff when configs are identical."""
        config = {"key": "value", "version": 1}
        has_changes, changes = _compute_config_diff(config, config.copy())

        assert has_changes is False
        assert len(changes) == 0

    def test_diff_added_key(self) -> None:
        """Test diff detects added keys."""
        current = {"key1": "value1", "version": 1}
        imported = {"key1": "value1", "key2": "value2"}

        has_changes, changes = _compute_config_diff(current, imported)

        assert has_changes is True
        assert any("Added: key2" in c for c in changes)

    def test_diff_removed_key(self) -> None:
        """Test diff detects removed keys."""
        current = {"key1": "value1", "key2": "value2", "version": 1}
        imported = {"key1": "value1"}

        has_changes, changes = _compute_config_diff(current, imported)

        assert has_changes is True
        assert any("Removed: key2" in c for c in changes)

    def test_diff_changed_value(self) -> None:
        """Test diff detects changed values."""
        current = {"key": "old_value", "version": 1}
        imported = {"key": "new_value"}

        has_changes, changes = _compute_config_diff(current, imported)

        assert has_changes is True
        assert any("Changed: key" in c for c in changes)

    def test_diff_list_changes(self) -> None:
        """Test diff detects list item changes."""
        current = {"items": ["a", "b", "c"], "version": 1}
        imported = {"items": ["b", "c", "d"]}

        has_changes, changes = _compute_config_diff(current, imported)

        assert has_changes is True
        # Should detect added 'd' and removed 'a'
        assert any("Added" in c and "d" in c for c in changes)
        assert any("Removed" in c and "a" in c for c in changes)

    def test_diff_ignores_version_field(self) -> None:
        """Test diff ignores version field when comparing."""
        current = {"key": "value", "version": 1}
        imported = {"key": "value", "version": 2}

        has_changes, _changes = _compute_config_diff(current, imported)

        assert has_changes is False


class TestPromptManagementSchemas:
    """Tests for prompt management Pydantic schemas."""

    def test_ai_model_enum_values(self) -> None:
        """Test AIModelEnum has all expected values."""
        assert AIModelEnum.NEMOTRON.value == "nemotron"
        assert AIModelEnum.FLORENCE2.value == "florence2"
        assert AIModelEnum.YOLO_WORLD.value == "yolo_world"
        assert AIModelEnum.XCLIP.value == "xclip"
        assert AIModelEnum.FASHION_CLIP.value == "fashion_clip"

    def test_model_prompt_config_creation(self) -> None:
        """Test ModelPromptConfig creation."""
        config = ModelPromptConfig(
            model=AIModelEnum.NEMOTRON,
            config={"system_prompt": "test"},
            version=1,
            created_at=datetime(2025, 12, 23, 12, 0, 0, tzinfo=UTC),
            created_by="user",
            change_description="Initial version",
        )
        assert config.model == AIModelEnum.NEMOTRON
        assert config.version == 1
        assert config.created_by == "user"

    def test_all_prompts_response_creation(self) -> None:
        """Test AllPromptsResponse creation."""
        response = AllPromptsResponse(
            version="1.0",
            exported_at=datetime(2025, 12, 23, 12, 0, 0, tzinfo=UTC),
            prompts={"nemotron": {"system_prompt": "test"}},
        )
        assert response.version == "1.0"
        assert "nemotron" in response.prompts

    def test_prompt_update_request_validation(self) -> None:
        """Test PromptUpdateRequest validates config is not empty."""
        with pytest.raises(ValueError, match="cannot be empty"):
            PromptUpdateRequest(config={})

    def test_prompt_test_request_creation(self) -> None:
        """Test PromptTestRequest creation."""
        request = PromptTestRequest(
            model=AIModelEnum.NEMOTRON,
            config={"system_prompt": "test"},
            event_id=123,
        )
        assert request.model == AIModelEnum.NEMOTRON
        assert request.event_id == 123
        assert request.image_path is None

    def test_prompt_test_result_creation(self) -> None:
        """Test PromptTestResult creation."""
        result = PromptTestResult(
            model=AIModelEnum.NEMOTRON,
            before_score=70,
            after_score=65,
            improved=True,
            test_duration_ms=1500,
        )
        assert result.improved is True
        assert result.error is None

    def test_prompt_version_info_creation(self) -> None:
        """Test PromptVersionInfo creation."""
        info = PromptVersionInfo(
            id=1,
            model=AIModelEnum.FLORENCE2,
            version=2,
            created_at=datetime(2025, 12, 23, 12, 0, 0, tzinfo=UTC),
            created_by=None,
            change_description="Updated queries",
            is_active=True,
        )
        assert info.id == 1
        assert info.is_active is True

    def test_prompt_history_response_creation(self) -> None:
        """Test PromptHistoryResponse creation."""
        response = PromptHistoryResponse(
            versions=[
                PromptVersionInfo(
                    id=1,
                    model=AIModelEnum.NEMOTRON,
                    version=1,
                    created_at=datetime(2025, 12, 23, tzinfo=UTC),
                    created_by=None,
                    change_description=None,
                    is_active=True,
                )
            ],
            total_count=1,
        )
        assert len(response.versions) == 1
        assert response.total_count == 1

    def test_prompt_restore_response_creation(self) -> None:
        """Test PromptRestoreResponse creation."""
        response = PromptRestoreResponse(
            restored_version=1,
            model=AIModelEnum.NEMOTRON,
            new_version=3,
            message="Restored successfully",
        )
        assert response.restored_version == 1
        assert response.new_version == 3

    def test_prompts_export_response_creation(self) -> None:
        """Test PromptsExportResponse creation."""
        response = PromptsExportResponse(
            version="1.0",
            exported_at=datetime(2025, 12, 23, tzinfo=UTC),
            prompts={"nemotron": {"system_prompt": "test"}},
        )
        assert response.version == "1.0"

    def test_prompts_import_request_validation(self) -> None:
        """Test PromptsImportRequest validates prompts not empty."""
        with pytest.raises(ValueError, match="cannot be empty"):
            PromptsImportRequest(version="1.0", prompts={})

    def test_prompts_import_response_creation(self) -> None:
        """Test PromptsImportResponse creation."""
        response = PromptsImportResponse(
            imported_models=["nemotron"],
            skipped_models=["unknown"],
            new_versions={"nemotron": 2},
            message="Imported 1 model",
        )
        assert len(response.imported_models) == 1
        assert "nemotron" in response.new_versions

    def test_prompt_diff_entry_creation(self) -> None:
        """Test PromptDiffEntry creation."""
        entry = PromptDiffEntry(
            model="nemotron",
            has_changes=True,
            current_version=1,
            current_config={"old": "config"},
            imported_config={"new": "config"},
            changes=["Changed: key"],
        )
        assert entry.has_changes is True
        assert len(entry.changes) == 1

    def test_prompts_import_preview_request_validation(self) -> None:
        """Test PromptsImportPreviewRequest validates prompts not empty."""
        with pytest.raises(ValueError, match="cannot be empty"):
            PromptsImportPreviewRequest(version="1.0", prompts={})

    def test_prompts_import_preview_response_creation(self) -> None:
        """Test PromptsImportPreviewResponse creation."""
        response = PromptsImportPreviewResponse(
            version="1.0",
            valid=True,
            validation_errors=[],
            diffs=[],
            total_changes=0,
            unknown_models=[],
        )
        assert response.valid is True
        assert response.total_changes == 0
