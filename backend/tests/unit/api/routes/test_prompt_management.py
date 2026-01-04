"""Unit tests for prompt management API endpoints.

Tests cover:
- GET /api/ai-audit/prompts - Get all prompts
- GET /api/ai-audit/prompts/{model} - Get prompt for specific model
- PUT /api/ai-audit/prompts/{model} - Update prompt for model
- POST /api/ai-audit/prompts/test - Test prompt with modified config
- GET /api/ai-audit/prompts/history - Get all prompts history
- GET /api/ai-audit/prompts/history/{model} - Get model history
- POST /api/ai-audit/prompts/history/{version} - Restore version
- GET /api/ai-audit/prompts/export - Export all configs
- POST /api/ai-audit/prompts/import - Import configs
"""

import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Set DATABASE_URL for tests before importing any backend modules
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")

from backend.api.routes.ai_audit import router
from backend.core.database import get_db
from backend.services.prompt_storage import (
    PromptStorageService,
    reset_prompt_storage,
)


@pytest.fixture
def temp_storage_dir():
    """Create a temporary directory for prompt storage."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def storage_service(temp_storage_dir: Path) -> PromptStorageService:
    """Create a PromptStorageService with temporary storage."""
    return PromptStorageService(storage_path=temp_storage_dir)


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    db = AsyncMock()
    return db


@pytest.fixture
def client(temp_storage_dir: Path, mock_db: AsyncMock) -> TestClient:
    """Create a test client with mocked dependencies."""
    # Reset the global storage singleton
    reset_prompt_storage()

    app = FastAPI()
    app.include_router(router)

    # Create a storage service with temp directory
    storage = PromptStorageService(storage_path=temp_storage_dir)

    # Override the get_prompt_storage function
    def override_get_prompt_storage():
        return storage

    # Patch the module-level function
    import backend.api.routes.ai_audit as ai_audit_module

    original_get_prompt_storage = ai_audit_module.get_prompt_storage
    ai_audit_module.get_prompt_storage = override_get_prompt_storage

    # Override database dependency
    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    # Cleanup
    ai_audit_module.get_prompt_storage = original_get_prompt_storage
    reset_prompt_storage()


class TestGetAllPrompts:
    """Tests for GET /api/ai-audit/prompts endpoint."""

    def test_get_all_prompts_success(self, client: TestClient) -> None:
        """Test successful retrieval of all prompts."""
        response = client.get("/api/ai-audit/prompts")

        assert response.status_code == 200
        data = response.json()
        assert "prompts" in data

        # Should have all 5 models
        prompts = data["prompts"]
        assert "nemotron" in prompts
        assert "florence2" in prompts
        assert "yolo_world" in prompts
        assert "xclip" in prompts
        assert "fashion_clip" in prompts

    def test_get_all_prompts_has_correct_structure(self, client: TestClient) -> None:
        """Test that each prompt has the correct structure."""
        response = client.get("/api/ai-audit/prompts")

        assert response.status_code == 200
        data = response.json()

        for model_name, prompt_data in data["prompts"].items():
            assert "model_name" in prompt_data
            assert "config" in prompt_data
            assert "version" in prompt_data
            assert "updated_at" in prompt_data
            assert prompt_data["model_name"] == model_name


class TestGetModelPrompt:
    """Tests for GET /api/ai-audit/prompts/{model} endpoint."""

    def test_get_nemotron_prompt(self, client: TestClient) -> None:
        """Test getting nemotron prompt configuration."""
        response = client.get("/api/ai-audit/prompts/nemotron")

        assert response.status_code == 200
        data = response.json()
        assert data["model_name"] == "nemotron"
        assert "system_prompt" in data["config"]

    def test_get_florence2_prompt(self, client: TestClient) -> None:
        """Test getting florence2 prompt configuration."""
        response = client.get("/api/ai-audit/prompts/florence2")

        assert response.status_code == 200
        data = response.json()
        assert data["model_name"] == "florence2"
        assert "vqa_queries" in data["config"]
        assert isinstance(data["config"]["vqa_queries"], list)

    def test_get_yolo_world_prompt(self, client: TestClient) -> None:
        """Test getting yolo_world prompt configuration."""
        response = client.get("/api/ai-audit/prompts/yolo_world")

        assert response.status_code == 200
        data = response.json()
        assert data["model_name"] == "yolo_world"
        assert "object_classes" in data["config"]
        assert "confidence_threshold" in data["config"]

    def test_get_invalid_model_returns_404(self, client: TestClient) -> None:
        """Test that invalid model name returns 404."""
        response = client.get("/api/ai-audit/prompts/invalid_model")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestUpdateModelPrompt:
    """Tests for PUT /api/ai-audit/prompts/{model} endpoint."""

    def test_update_nemotron_prompt(self, client: TestClient) -> None:
        """Test updating nemotron prompt configuration."""
        new_config = {
            "system_prompt": "You are a new security analyzer.",
            "temperature": 0.8,
            "max_tokens": 4096,
        }

        response = client.put(
            "/api/ai-audit/prompts/nemotron",
            json={"config": new_config, "description": "Test update"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["model_name"] == "nemotron"
        assert data["version"] >= 1
        assert data["config"]["system_prompt"] == new_config["system_prompt"]

    def test_update_florence2_prompt(self, client: TestClient) -> None:
        """Test updating florence2 prompt configuration."""
        new_config = {
            "vqa_queries": ["What is happening?", "Who is in the image?"],
        }

        response = client.put(
            "/api/ai-audit/prompts/florence2",
            json={"config": new_config},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["model_name"] == "florence2"
        assert data["config"]["vqa_queries"] == new_config["vqa_queries"]

    def test_update_with_invalid_config_returns_400(self, client: TestClient) -> None:
        """Test that invalid configuration returns 400."""
        # Missing required field
        response = client.put(
            "/api/ai-audit/prompts/nemotron",
            json={"config": {"temperature": 0.5}},  # Missing system_prompt
        )

        assert response.status_code == 400
        assert "system_prompt" in response.json()["detail"].lower()

    def test_update_invalid_model_returns_404(self, client: TestClient) -> None:
        """Test that invalid model returns 404."""
        response = client.put(
            "/api/ai-audit/prompts/invalid_model",
            json={"config": {"test": "value"}},
        )

        assert response.status_code == 404

    def test_update_creates_version_history(self, client: TestClient) -> None:
        """Test that updating creates version history."""
        # Initial update
        client.put(
            "/api/ai-audit/prompts/yolo_world",
            json={
                "config": {
                    "object_classes": ["person"],
                    "confidence_threshold": 0.6,
                },
                "description": "First update",
            },
        )

        # Second update
        response = client.put(
            "/api/ai-audit/prompts/yolo_world",
            json={
                "config": {
                    "object_classes": ["person", "car"],
                    "confidence_threshold": 0.7,
                },
                "description": "Second update",
            },
        )

        assert response.status_code == 200
        # Version should be 2 or higher after two updates
        assert response.json()["version"] >= 2


class TestPromptTest:
    """Tests for POST /api/ai-audit/prompts/test endpoint."""

    def test_test_prompt_event_not_found(self, client: TestClient, mock_db: AsyncMock) -> None:
        """Test that testing with non-existent event returns 404."""
        # Mock the database to return no event
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        response = client.post(
            "/api/ai-audit/prompts/test",
            json={
                "model": "nemotron",
                "config": {"system_prompt": "Test prompt"},
                "event_id": 99999,
            },
        )

        assert response.status_code == 404
        assert "event" in response.json()["detail"].lower()

    def test_test_prompt_invalid_model_returns_404(self, client: TestClient) -> None:
        """Test that testing with invalid model returns 404."""
        response = client.post(
            "/api/ai-audit/prompts/test",
            json={
                "model": "invalid_model",
                "config": {},
                "event_id": 1,
            },
        )

        assert response.status_code == 404

    def test_test_prompt_invalid_config_returns_400(
        self, client: TestClient, mock_db: AsyncMock
    ) -> None:
        """Test that testing with invalid config returns 400."""
        # Mock the database to return an event
        mock_event = MagicMock()
        mock_event.id = 1
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_event
        mock_db.execute.return_value = mock_result

        response = client.post(
            "/api/ai-audit/prompts/test",
            json={
                "model": "nemotron",
                "config": {},  # Invalid - missing system_prompt
                "event_id": 1,
            },
        )

        assert response.status_code == 400


class TestGetPromptHistory:
    """Tests for GET /api/ai-audit/prompts/history endpoints."""

    def test_get_all_history(self, client: TestClient) -> None:
        """Test getting history for all models."""
        # Create some history
        client.put(
            "/api/ai-audit/prompts/nemotron",
            json={"config": {"system_prompt": "V1"}, "description": "Version 1"},
        )

        response = client.get("/api/ai-audit/prompts/history")

        assert response.status_code == 200
        data = response.json()

        # Should have entries for all models
        assert "nemotron" in data
        assert "florence2" in data

    def test_get_model_history(self, client: TestClient) -> None:
        """Test getting history for a specific model."""
        # Create some versions
        client.put(
            "/api/ai-audit/prompts/florence2",
            json={"config": {"vqa_queries": ["Q1"]}, "description": "Version 1"},
        )
        client.put(
            "/api/ai-audit/prompts/florence2",
            json={"config": {"vqa_queries": ["Q1", "Q2"]}, "description": "Version 2"},
        )

        response = client.get("/api/ai-audit/prompts/history/florence2")

        assert response.status_code == 200
        data = response.json()
        assert data["model_name"] == "florence2"
        assert data["total_versions"] >= 2
        assert len(data["versions"]) >= 2

    def test_get_history_invalid_model_returns_404(self, client: TestClient) -> None:
        """Test getting history for invalid model returns 404."""
        response = client.get("/api/ai-audit/prompts/history/invalid_model")

        assert response.status_code == 404

    def test_get_history_with_pagination(self, client: TestClient) -> None:
        """Test history pagination."""
        # Create multiple versions
        for i in range(5):
            client.put(
                "/api/ai-audit/prompts/xclip",
                json={
                    "config": {"action_classes": [f"action_{i}"]},
                    "description": f"Version {i + 1}",
                },
            )

        # Get with limit
        response = client.get("/api/ai-audit/prompts/history/xclip?limit=2")

        assert response.status_code == 200
        data = response.json()
        assert len(data["versions"]) == 2


class TestRestoreVersion:
    """Tests for POST /api/ai-audit/prompts/history/{version} endpoint."""

    def test_restore_version(self, client: TestClient) -> None:
        """Test restoring a previous version."""
        # Create versions
        client.put(
            "/api/ai-audit/prompts/fashion_clip",
            json={
                "config": {
                    "clothing_categories": ["casual"],
                    "suspicious_indicators": ["all black"],
                },
                "description": "Version 1",
            },
        )
        client.put(
            "/api/ai-audit/prompts/fashion_clip",
            json={
                "config": {
                    "clothing_categories": ["formal"],
                    "suspicious_indicators": ["face mask"],
                },
                "description": "Version 2",
            },
        )

        # Restore version 1
        response = client.post(
            "/api/ai-audit/prompts/history/1?model=fashion_clip",
            json={"description": "Restoring version 1"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["restored_version"] == 1
        assert data["new_version"] == 3  # Should be version 3

        # Verify current config matches version 1
        current = client.get("/api/ai-audit/prompts/fashion_clip").json()
        assert "casual" in current["config"]["clothing_categories"]

    def test_restore_nonexistent_version_returns_404(self, client: TestClient) -> None:
        """Test restoring non-existent version returns 404."""
        response = client.post(
            "/api/ai-audit/prompts/history/999?model=nemotron",
        )

        assert response.status_code == 404

    def test_restore_invalid_model_returns_404(self, client: TestClient) -> None:
        """Test restoring with invalid model returns 404."""
        response = client.post(
            "/api/ai-audit/prompts/history/1?model=invalid_model",
        )

        assert response.status_code == 404


class TestExportPrompts:
    """Tests for GET /api/ai-audit/prompts/export endpoint."""

    def test_export_prompts(self, client: TestClient) -> None:
        """Test exporting all prompts."""
        response = client.get("/api/ai-audit/prompts/export")

        assert response.status_code == 200
        data = response.json()

        assert "exported_at" in data
        assert "version" in data
        assert "prompts" in data

        # Should have all models
        assert "nemotron" in data["prompts"]
        assert "florence2" in data["prompts"]

    def test_export_includes_configs(self, client: TestClient) -> None:
        """Test that export includes actual configurations."""
        # Update a config
        client.put(
            "/api/ai-audit/prompts/nemotron",
            json={"config": {"system_prompt": "Exported prompt"}},
        )

        response = client.get("/api/ai-audit/prompts/export")

        assert response.status_code == 200
        data = response.json()
        assert data["prompts"]["nemotron"]["system_prompt"] == "Exported prompt"


class TestImportPrompts:
    """Tests for POST /api/ai-audit/prompts/import endpoint."""

    def test_import_prompts(self, client: TestClient) -> None:
        """Test importing prompts."""
        import_data = {
            "prompts": {
                "nemotron": {
                    "system_prompt": "Imported prompt",
                    "temperature": 0.9,
                    "max_tokens": 1024,
                },
                "florence2": {
                    "vqa_queries": ["Imported query"],
                },
            },
            "overwrite": True,
        }

        response = client.post("/api/ai-audit/prompts/import", json=import_data)

        assert response.status_code == 200
        data = response.json()
        assert data["imported_count"] >= 2

        # Verify imports
        nemotron = client.get("/api/ai-audit/prompts/nemotron").json()
        assert nemotron["config"]["system_prompt"] == "Imported prompt"

    def test_import_without_overwrite_skips_existing(self, client: TestClient) -> None:
        """Test that import without overwrite skips existing configs."""
        # First, create some configs
        client.put(
            "/api/ai-audit/prompts/nemotron",
            json={"config": {"system_prompt": "Original"}},
        )

        # Import without overwrite
        import_data = {
            "prompts": {
                "nemotron": {
                    "system_prompt": "Should be skipped",
                },
            },
            "overwrite": False,
        }

        response = client.post("/api/ai-audit/prompts/import", json=import_data)

        assert response.status_code == 200
        data = response.json()
        assert data["skipped_count"] >= 1

        # Verify original was kept
        nemotron = client.get("/api/ai-audit/prompts/nemotron").json()
        assert nemotron["config"]["system_prompt"] == "Original"

    def test_import_invalid_model_reports_error(self, client: TestClient) -> None:
        """Test that importing invalid model reports error."""
        import_data = {
            "prompts": {
                "invalid_model": {"test": "value"},
            },
            "overwrite": True,
        }

        response = client.post("/api/ai-audit/prompts/import", json=import_data)

        assert response.status_code == 200
        data = response.json()
        assert len(data["errors"]) > 0
        assert "invalid_model" in data["errors"][0].lower()

    def test_import_invalid_config_reports_error(self, client: TestClient) -> None:
        """Test that importing invalid config reports error."""
        import_data = {
            "prompts": {
                "nemotron": {"temperature": 0.5},  # Missing system_prompt
            },
            "overwrite": True,
        }

        response = client.post("/api/ai-audit/prompts/import", json=import_data)

        assert response.status_code == 200
        data = response.json()
        assert len(data["errors"]) > 0


class TestPromptStorageService:
    """Unit tests for PromptStorageService class."""

    def test_initialize_with_custom_path(self, temp_storage_dir: Path) -> None:
        """Test initializing service with custom storage path."""
        service = PromptStorageService(storage_path=temp_storage_dir)
        assert service.storage_path == temp_storage_dir

    def test_get_config_returns_default(self, storage_service: PromptStorageService) -> None:
        """Test that get_config returns default for uninitialized model."""
        config = storage_service.get_config("nemotron")
        assert "system_prompt" in config

    def test_update_config_creates_version(self, storage_service: PromptStorageService) -> None:
        """Test that update_config creates a version."""
        version = storage_service.update_config(
            model_name="florence2",
            config={"vqa_queries": ["Test query"]},
            description="Test version",
        )

        assert version.version >= 1
        assert version.config["vqa_queries"] == ["Test query"]

    def test_get_history_returns_versions(self, storage_service: PromptStorageService) -> None:
        """Test that get_history returns version list."""
        storage_service.update_config(
            model_name="yolo_world",
            config={"object_classes": ["person"], "confidence_threshold": 0.5},
        )
        storage_service.update_config(
            model_name="yolo_world",
            config={"object_classes": ["person", "car"], "confidence_threshold": 0.6},
        )

        history = storage_service.get_history("yolo_world")
        assert len(history) >= 2

    def test_validate_config_nemotron(self, storage_service: PromptStorageService) -> None:
        """Test validation for nemotron config."""
        # Valid config
        errors = storage_service.validate_config(
            "nemotron",
            {"system_prompt": "Test", "temperature": 0.7},
        )
        assert len(errors) == 0

        # Invalid - missing system_prompt
        errors = storage_service.validate_config("nemotron", {"temperature": 0.7})
        assert len(errors) > 0
        assert "system_prompt" in errors[0].lower()

    def test_validate_config_florence2(self, storage_service: PromptStorageService) -> None:
        """Test validation for florence2 config."""
        # Valid config
        errors = storage_service.validate_config("florence2", {"vqa_queries": ["Test"]})
        assert len(errors) == 0

        # Invalid - empty list
        errors = storage_service.validate_config("florence2", {"vqa_queries": []})
        assert len(errors) > 0

    def test_validate_config_yolo_world(self, storage_service: PromptStorageService) -> None:
        """Test validation for yolo_world config."""
        # Valid config
        errors = storage_service.validate_config(
            "yolo_world",
            {"object_classes": ["person"], "confidence_threshold": 0.5},
        )
        assert len(errors) == 0

        # Invalid threshold
        errors = storage_service.validate_config(
            "yolo_world",
            {"object_classes": ["person"], "confidence_threshold": 1.5},
        )
        assert len(errors) > 0

    def test_export_all(self, storage_service: PromptStorageService) -> None:
        """Test exporting all configurations."""
        export_data = storage_service.export_all()

        assert "exported_at" in export_data
        assert "prompts" in export_data
        assert "nemotron" in export_data["prompts"]

    def test_import_configs(self, storage_service: PromptStorageService) -> None:
        """Test importing configurations."""
        configs = {
            "xclip": {"action_classes": ["walking", "running"]},
        }

        results = storage_service.import_configs(configs, overwrite=True)
        assert "xclip" in results["imported"]

    def test_restore_version(self, storage_service: PromptStorageService) -> None:
        """Test restoring a version."""
        # Create versions
        storage_service.update_config(
            "fashion_clip",
            {"clothing_categories": ["v1"], "suspicious_indicators": []},
        )
        storage_service.update_config(
            "fashion_clip",
            {"clothing_categories": ["v2"], "suspicious_indicators": []},
        )

        # Restore version 1
        restored = storage_service.restore_version("fashion_clip", 1)
        assert "v1" in restored.config["clothing_categories"]

    def test_unsupported_model_raises_error(self, storage_service: PromptStorageService) -> None:
        """Test that unsupported model raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            storage_service.update_config("unsupported", {"test": "value"})

        assert "unsupported" in str(exc_info.value).lower()

    def test_run_mock_test(self, storage_service: PromptStorageService) -> None:
        """Test running a mock test."""
        results = storage_service.run_mock_test(
            model_name="nemotron",
            config={"system_prompt": "Test prompt"},
            event_id=123,
        )

        assert "before" in results
        assert "after" in results
        assert "improved" in results
        assert "inference_time_ms" in results

    def test_run_mock_test_invalid_config_raises(
        self, storage_service: PromptStorageService
    ) -> None:
        """Test that mock test with invalid config raises ValueError."""
        with pytest.raises(ValueError):
            storage_service.run_mock_test(
                model_name="nemotron",
                config={},  # Missing system_prompt
                event_id=123,
            )
