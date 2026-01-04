"""Unit tests for Prompt Management API routes.

This module tests the prompt management endpoints including:
- Get all prompts
- Get prompt for specific model
- Update prompt for model
- Export prompts
- Import prompts (and preview)
- Version history
- Restore versions

Tests use mocking for the PromptService to isolate route logic.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.routes import prompt_management as pm_routes
from backend.api.routes.prompt_management import _compute_config_diff
from backend.api.schemas.prompt_management import (
    AIModelEnum,
    AllPromptsResponse,
    ModelPromptConfig,
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
)
from backend.models.prompt_version import PromptVersion


class TestGetAllPrompts:
    """Tests for GET /api/ai-audit/prompts endpoint."""

    @pytest.mark.asyncio
    async def test_get_all_prompts_returns_all_models(self) -> None:
        """Test that get_all_prompts returns configurations for all AI models."""
        mock_db = AsyncMock(spec=AsyncSession)
        mock_prompts = {
            "nemotron": {"system_prompt": "Test prompt", "version": 1},
            "florence2": {"queries": ["What is happening?"]},
            "yolo_world": {"classes": ["knife", "gun"], "confidence_threshold": 0.35},
            "xclip": {"action_classes": ["loitering", "running"]},
            "fashion_clip": {"clothing_categories": ["dark hoodie"]},
        }

        with patch.object(pm_routes, "get_prompt_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_all_prompts = AsyncMock(return_value=mock_prompts)
            mock_get_service.return_value = mock_service

            response = await pm_routes.get_all_prompts(db=mock_db)

            assert isinstance(response, AllPromptsResponse)
            assert response.version == "1.0"
            assert response.exported_at is not None
            assert len(response.prompts) == 5
            assert "nemotron" in response.prompts
            assert response.prompts["nemotron"]["system_prompt"] == "Test prompt"

    @pytest.mark.asyncio
    async def test_get_all_prompts_empty_database(self) -> None:
        """Test that get_all_prompts handles empty database gracefully."""
        mock_db = AsyncMock(spec=AsyncSession)

        with patch.object(pm_routes, "get_prompt_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_all_prompts = AsyncMock(return_value={})
            mock_get_service.return_value = mock_service

            response = await pm_routes.get_all_prompts(db=mock_db)

            assert isinstance(response, AllPromptsResponse)
            assert response.prompts == {}


class TestGetPromptForModel:
    """Tests for GET /api/ai-audit/prompts/{model} endpoint."""

    @pytest.mark.asyncio
    async def test_get_prompt_for_model_success(self) -> None:
        """Test successful retrieval of prompt for a specific model."""
        mock_db = AsyncMock(spec=AsyncSession)
        mock_config = {
            "system_prompt": "You are a security analyst...",
            "version": 3,
        }

        with patch.object(pm_routes, "get_prompt_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_prompt_for_model = AsyncMock(return_value=mock_config)
            mock_get_service.return_value = mock_service

            response = await pm_routes.get_prompt_for_model(
                model=AIModelEnum.NEMOTRON,
                db=mock_db,
            )

            assert isinstance(response, ModelPromptConfig)
            assert response.model == AIModelEnum.NEMOTRON
            assert response.config["system_prompt"] == "You are a security analyst..."
            assert response.version == 3

    @pytest.mark.asyncio
    async def test_get_prompt_for_model_not_found(self) -> None:
        """Test 404 response when no configuration exists for model."""
        mock_db = AsyncMock(spec=AsyncSession)

        with patch.object(pm_routes, "get_prompt_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_prompt_for_model = AsyncMock(return_value=None)
            mock_get_service.return_value = mock_service

            with pytest.raises(HTTPException) as exc_info:
                await pm_routes.get_prompt_for_model(
                    model=AIModelEnum.NEMOTRON,
                    db=mock_db,
                )

            assert exc_info.value.status_code == 404
            assert "No configuration found" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_get_prompt_for_model_all_supported_models(self) -> None:
        """Test that all AIModelEnum values can be requested."""
        mock_db = AsyncMock(spec=AsyncSession)

        for model in AIModelEnum:
            mock_config = {"test_key": "test_value", "version": 1}

            with patch.object(pm_routes, "get_prompt_service") as mock_get_service:
                mock_service = MagicMock()
                mock_service.get_prompt_for_model = AsyncMock(return_value=mock_config)
                mock_get_service.return_value = mock_service

                response = await pm_routes.get_prompt_for_model(
                    model=model,
                    db=mock_db,
                )

                assert response.model == model


class TestUpdatePromptForModel:
    """Tests for PUT /api/ai-audit/prompts/{model} endpoint."""

    @pytest.mark.asyncio
    async def test_update_prompt_success(self) -> None:
        """Test successful prompt update creates new version."""
        mock_db = AsyncMock(spec=AsyncSession)
        request = PromptUpdateRequest(
            config={"system_prompt": "New security prompt"},
            change_description="Updated risk factors",
        )

        mock_version = MagicMock(spec=PromptVersion)
        mock_version.model = "nemotron"
        mock_version.version = 2
        mock_version.config = {"system_prompt": "New security prompt"}
        mock_version.created_at = datetime.now(UTC)
        mock_version.created_by = None
        mock_version.change_description = "Updated risk factors"

        with patch.object(pm_routes, "get_prompt_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.update_prompt_for_model = AsyncMock(return_value=mock_version)
            mock_get_service.return_value = mock_service

            response = await pm_routes.update_prompt_for_model(
                model=AIModelEnum.NEMOTRON,
                request=request,
                db=mock_db,
            )

            assert isinstance(response, ModelPromptConfig)
            assert response.model == AIModelEnum.NEMOTRON
            assert response.version == 2
            assert response.change_description == "Updated risk factors"

    @pytest.mark.asyncio
    async def test_update_prompt_without_description(self) -> None:
        """Test prompt update without change description."""
        mock_db = AsyncMock(spec=AsyncSession)
        request = PromptUpdateRequest(
            config={"queries": ["What is happening?"]},
        )

        mock_version = MagicMock(spec=PromptVersion)
        mock_version.model = "florence2"
        mock_version.version = 1
        mock_version.config = {"queries": ["What is happening?"]}
        mock_version.created_at = datetime.now(UTC)
        mock_version.created_by = None
        mock_version.change_description = None

        with patch.object(pm_routes, "get_prompt_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.update_prompt_for_model = AsyncMock(return_value=mock_version)
            mock_get_service.return_value = mock_service

            response = await pm_routes.update_prompt_for_model(
                model=AIModelEnum.FLORENCE2,
                request=request,
                db=mock_db,
            )

            assert response.change_description is None


class TestExportPrompts:
    """Tests for GET /api/ai-audit/prompts/export endpoint."""

    @pytest.mark.asyncio
    async def test_export_prompts_success(self) -> None:
        """Test successful export of all prompts."""
        mock_db = AsyncMock(spec=AsyncSession)
        mock_export = {
            "version": "1.0",
            "exported_at": datetime.now(UTC),
            "prompts": {
                "nemotron": {"system_prompt": "Test", "version": 1},
                "florence2": {"queries": ["Question?"]},
            },
        }

        with patch.object(pm_routes, "get_prompt_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.export_all_prompts = AsyncMock(return_value=mock_export)
            mock_get_service.return_value = mock_service

            response = await pm_routes.export_prompts(db=mock_db)

            assert isinstance(response, PromptsExportResponse)
            assert response.version == "1.0"
            assert len(response.prompts) == 2

    @pytest.mark.asyncio
    async def test_export_prompts_iso_string_date(self) -> None:
        """Test export handles ISO string date format from service."""
        mock_db = AsyncMock(spec=AsyncSession)
        mock_export = {
            "version": "1.0",
            "exported_at": "2024-01-15T12:00:00+00:00",
            "prompts": {"nemotron": {"system_prompt": "Test"}},
        }

        with patch.object(pm_routes, "get_prompt_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.export_all_prompts = AsyncMock(return_value=mock_export)
            mock_get_service.return_value = mock_service

            response = await pm_routes.export_prompts(db=mock_db)

            assert response.exported_at is not None
            assert isinstance(response.exported_at, datetime)

    @pytest.mark.asyncio
    async def test_export_prompts_z_suffix_date(self) -> None:
        """Test export handles Z suffix in ISO date format."""
        mock_db = AsyncMock(spec=AsyncSession)
        mock_export = {
            "version": "1.0",
            "exported_at": "2024-01-15T12:00:00Z",
            "prompts": {"nemotron": {"system_prompt": "Test"}},
        }

        with patch.object(pm_routes, "get_prompt_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.export_all_prompts = AsyncMock(return_value=mock_export)
            mock_get_service.return_value = mock_service

            response = await pm_routes.export_prompts(db=mock_db)

            assert response.exported_at is not None


class TestPromptHistory:
    """Tests for GET /api/ai-audit/prompts/history endpoint."""

    @pytest.mark.asyncio
    async def test_get_history_unfiltered(self) -> None:
        """Test getting full version history without model filter."""
        mock_db = AsyncMock(spec=AsyncSession)

        mock_versions = [
            MagicMock(
                id=2,
                model="nemotron",
                version=2,
                created_at=datetime.now(UTC),
                created_by="user@test.com",
                change_description="Updated prompt",
                is_active=True,
            ),
            MagicMock(
                id=1,
                model="nemotron",
                version=1,
                created_at=datetime.now(UTC),
                created_by=None,
                change_description="Initial version",
                is_active=False,
            ),
        ]

        with patch.object(pm_routes, "get_prompt_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_version_history = AsyncMock(return_value=(mock_versions, 2))
            mock_get_service.return_value = mock_service

            response = await pm_routes.get_prompt_history(
                model=None,
                limit=50,
                offset=0,
                db=mock_db,
            )

            assert isinstance(response, PromptHistoryResponse)
            assert response.total_count == 2
            assert len(response.versions) == 2
            assert response.versions[0].is_active is True
            assert response.versions[1].is_active is False

    @pytest.mark.asyncio
    async def test_get_history_filtered_by_model(self) -> None:
        """Test getting history filtered by specific model."""
        mock_db = AsyncMock(spec=AsyncSession)

        mock_versions = [
            MagicMock(
                id=1,
                model="florence2",
                version=1,
                created_at=datetime.now(UTC),
                created_by=None,
                change_description=None,
                is_active=True,
            ),
        ]

        with patch.object(pm_routes, "get_prompt_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_version_history = AsyncMock(return_value=(mock_versions, 1))
            mock_get_service.return_value = mock_service

            response = await pm_routes.get_prompt_history(
                model=AIModelEnum.FLORENCE2,
                limit=50,
                offset=0,
                db=mock_db,
            )

            mock_service.get_version_history.assert_called_once_with(
                session=mock_db,
                model="florence2",
                limit=50,
                offset=0,
            )
            assert len(response.versions) == 1
            assert response.versions[0].model == AIModelEnum.FLORENCE2

    @pytest.mark.asyncio
    async def test_get_history_pagination(self) -> None:
        """Test history pagination with limit and offset."""
        mock_db = AsyncMock(spec=AsyncSession)

        with patch.object(pm_routes, "get_prompt_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_version_history = AsyncMock(return_value=([], 100))
            mock_get_service.return_value = mock_service

            response = await pm_routes.get_prompt_history(
                model=None,
                limit=10,
                offset=50,
                db=mock_db,
            )

            mock_service.get_version_history.assert_called_once_with(
                session=mock_db,
                model=None,
                limit=10,
                offset=50,
            )
            assert response.total_count == 100


class TestTestPrompt:
    """Tests for POST /api/ai-audit/prompts/test endpoint."""

    @pytest.mark.asyncio
    async def test_prompt_success(self) -> None:
        """Test successful prompt testing."""
        mock_db = AsyncMock(spec=AsyncSession)
        request = PromptTestRequest(
            model=AIModelEnum.NEMOTRON,
            config={"system_prompt": "New prompt to test"},
            event_id=123,
        )

        mock_result = {
            "before_score": 75,
            "after_score": 60,
            "before_response": {"risk_score": 75},
            "after_response": {"risk_score": 60},
            "improved": True,
            "test_duration_ms": 1500,
            "error": None,
        }

        with patch.object(pm_routes, "get_prompt_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.test_prompt = AsyncMock(return_value=mock_result)
            mock_get_service.return_value = mock_service

            response = await pm_routes.test_prompt(request=request, db=mock_db)

            assert isinstance(response, PromptTestResult)
            assert response.model == AIModelEnum.NEMOTRON
            assert response.before_score == 75
            assert response.after_score == 60
            assert response.improved is True
            assert response.test_duration_ms == 1500
            assert response.error is None

    @pytest.mark.asyncio
    async def test_prompt_with_error(self) -> None:
        """Test prompt testing that returns an error."""
        mock_db = AsyncMock(spec=AsyncSession)
        request = PromptTestRequest(
            model=AIModelEnum.FLORENCE2,
            config={"queries": ["Test query"]},
        )

        mock_result = {
            "before_score": None,
            "after_score": None,
            "before_response": None,
            "after_response": None,
            "improved": None,
            "test_duration_ms": 100,
            "error": "Testing for model 'florence2' not yet implemented",
        }

        with patch.object(pm_routes, "get_prompt_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.test_prompt = AsyncMock(return_value=mock_result)
            mock_get_service.return_value = mock_service

            response = await pm_routes.test_prompt(request=request, db=mock_db)

            assert response.error == "Testing for model 'florence2' not yet implemented"
            assert response.improved is None

    @pytest.mark.asyncio
    async def test_prompt_with_image_path(self) -> None:
        """Test prompt testing with image path instead of event ID."""
        mock_db = AsyncMock(spec=AsyncSession)
        request = PromptTestRequest(
            model=AIModelEnum.NEMOTRON,
            config={"system_prompt": "Test prompt"},
            image_path="/path/to/image.jpg",
        )

        mock_result = {
            "test_duration_ms": 500,
            "error": None,
        }

        with patch.object(pm_routes, "get_prompt_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.test_prompt = AsyncMock(return_value=mock_result)
            mock_get_service.return_value = mock_service

            await pm_routes.test_prompt(request=request, db=mock_db)

            mock_service.test_prompt.assert_called_once_with(
                session=mock_db,
                model="nemotron",
                config={"system_prompt": "Test prompt"},
                event_id=None,
                image_path="/path/to/image.jpg",
            )


class TestImportPrompts:
    """Tests for POST /api/ai-audit/prompts/import endpoint."""

    @pytest.mark.asyncio
    async def test_import_prompts_success(self) -> None:
        """Test successful import of prompt configurations."""
        mock_db = AsyncMock(spec=AsyncSession)
        request = PromptsImportRequest(
            version="1.0",
            prompts={
                "nemotron": {"system_prompt": "Imported prompt"},
                "florence2": {"queries": ["Imported query"]},
            },
        )

        mock_result = {
            "imported_models": ["nemotron", "florence2"],
            "skipped_models": [],
            "new_versions": {"nemotron": 2, "florence2": 3},
            "message": "Imported 2 model configurations",
        }

        with patch.object(pm_routes, "get_prompt_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.import_prompts = AsyncMock(return_value=mock_result)
            mock_get_service.return_value = mock_service

            response = await pm_routes.import_prompts(request=request, db=mock_db)

            assert isinstance(response, PromptsImportResponse)
            assert response.imported_models == ["nemotron", "florence2"]
            assert response.skipped_models == []
            assert response.new_versions["nemotron"] == 2

    @pytest.mark.asyncio
    async def test_import_prompts_with_skipped_models(self) -> None:
        """Test import with some unknown models that get skipped."""
        mock_db = AsyncMock(spec=AsyncSession)
        request = PromptsImportRequest(
            version="1.0",
            prompts={
                "nemotron": {"system_prompt": "Valid prompt"},
                "unknown_model": {"config": "value"},
            },
        )

        mock_result = {
            "imported_models": ["nemotron"],
            "skipped_models": ["unknown_model"],
            "new_versions": {"nemotron": 1},
            "message": "Imported 1 model configurations",
        }

        with patch.object(pm_routes, "get_prompt_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.import_prompts = AsyncMock(return_value=mock_result)
            mock_get_service.return_value = mock_service

            response = await pm_routes.import_prompts(request=request, db=mock_db)

            assert "unknown_model" in response.skipped_models


class TestImportPreview:
    """Tests for POST /api/ai-audit/prompts/import/preview endpoint."""

    @pytest.mark.asyncio
    async def test_preview_import_with_changes(self) -> None:
        """Test preview shows diffs between current and imported configs."""
        mock_db = AsyncMock(spec=AsyncSession)
        request = PromptsImportPreviewRequest(
            version="1.0",
            prompts={
                "nemotron": {"system_prompt": "New prompt", "version": 2},
            },
        )

        current_config = {"system_prompt": "Old prompt", "version": 1}

        with patch.object(pm_routes, "get_prompt_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_prompt_for_model = AsyncMock(return_value=current_config)
            mock_get_service.return_value = mock_service

            response = await pm_routes.preview_import_prompts(request=request, db=mock_db)

            assert isinstance(response, PromptsImportPreviewResponse)
            assert response.valid is True
            assert response.total_changes == 1
            assert len(response.diffs) == 1
            assert response.diffs[0].has_changes is True

    @pytest.mark.asyncio
    async def test_preview_import_unsupported_version(self) -> None:
        """Test preview rejects unsupported version format."""
        mock_db = AsyncMock(spec=AsyncSession)
        request = PromptsImportPreviewRequest(
            version="2.0",  # Unsupported version
            prompts={
                "nemotron": {"system_prompt": "Test"},
            },
        )

        with patch.object(pm_routes, "get_prompt_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_prompt_for_model = AsyncMock(return_value=None)
            mock_get_service.return_value = mock_service

            response = await pm_routes.preview_import_prompts(request=request, db=mock_db)

            assert response.valid is False
            assert any("Unsupported version" in err for err in response.validation_errors)

    @pytest.mark.asyncio
    async def test_preview_import_unknown_models(self) -> None:
        """Test preview identifies unknown models."""
        mock_db = AsyncMock(spec=AsyncSession)
        request = PromptsImportPreviewRequest(
            version="1.0",
            prompts={
                "nemotron": {"system_prompt": "Valid"},
                "invalid_model": {"config": "value"},
                "another_unknown": {"config": "value"},
            },
        )

        with patch.object(pm_routes, "get_prompt_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_prompt_for_model = AsyncMock(
                return_value={"system_prompt": "Existing"}
            )
            mock_get_service.return_value = mock_service

            response = await pm_routes.preview_import_prompts(request=request, db=mock_db)

            assert "invalid_model" in response.unknown_models
            assert "another_unknown" in response.unknown_models
            assert len(response.diffs) == 1  # Only valid model has diff

    @pytest.mark.asyncio
    async def test_preview_import_no_changes(self) -> None:
        """Test preview when imported config matches current config."""
        mock_db = AsyncMock(spec=AsyncSession)
        same_config = {"system_prompt": "Same prompt"}
        request = PromptsImportPreviewRequest(
            version="1.0",
            prompts={
                "nemotron": same_config.copy(),
            },
        )

        with patch.object(pm_routes, "get_prompt_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_prompt_for_model = AsyncMock(return_value=same_config.copy())
            mock_get_service.return_value = mock_service

            response = await pm_routes.preview_import_prompts(request=request, db=mock_db)

            assert response.total_changes == 0
            assert response.diffs[0].has_changes is False

    @pytest.mark.asyncio
    async def test_preview_import_new_config(self) -> None:
        """Test preview for model with no existing configuration."""
        mock_db = AsyncMock(spec=AsyncSession)
        request = PromptsImportPreviewRequest(
            version="1.0",
            prompts={
                "nemotron": {"system_prompt": "Brand new prompt"},
            },
        )

        with patch.object(pm_routes, "get_prompt_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_prompt_for_model = AsyncMock(return_value=None)
            mock_get_service.return_value = mock_service

            response = await pm_routes.preview_import_prompts(request=request, db=mock_db)

            assert response.diffs[0].has_changes is True
            assert "New configuration" in response.diffs[0].changes[0]


class TestRestorePromptVersion:
    """Tests for POST /api/ai-audit/prompts/history/{version_id} endpoint."""

    @pytest.mark.asyncio
    async def test_restore_version_success(self) -> None:
        """Test successful restoration of a previous version."""
        mock_db = AsyncMock(spec=AsyncSession)

        # Mock the restored version
        mock_new_version = MagicMock(spec=PromptVersion)
        mock_new_version.model = "nemotron"
        mock_new_version.version = 5

        # Mock the original version query
        mock_original = MagicMock()
        mock_original.version = 2

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_original

        with patch.object(pm_routes, "get_prompt_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.restore_version = AsyncMock(return_value=mock_new_version)
            mock_get_service.return_value = mock_service

            mock_db.execute = AsyncMock(return_value=mock_result)

            response = await pm_routes.restore_prompt_version(
                version_id=123,
                db=mock_db,
            )

            assert isinstance(response, PromptRestoreResponse)
            assert response.restored_version == 2
            assert response.new_version == 5
            assert response.model == AIModelEnum.NEMOTRON
            assert "Successfully restored" in response.message

    @pytest.mark.asyncio
    async def test_restore_version_not_found(self) -> None:
        """Test 404 response when version ID doesn't exist."""
        mock_db = AsyncMock(spec=AsyncSession)

        with patch.object(pm_routes, "get_prompt_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.restore_version = AsyncMock(
                side_effect=ValueError("Version 999 not found")
            )
            mock_get_service.return_value = mock_service

            with pytest.raises(HTTPException) as exc_info:
                await pm_routes.restore_prompt_version(
                    version_id=999,
                    db=mock_db,
                )

            assert exc_info.value.status_code == 404
            assert "not found" in str(exc_info.value.detail).lower()


class TestComputeConfigDiff:
    """Tests for _compute_config_diff helper function."""

    def test_diff_no_current_config(self) -> None:
        """Test diff when there's no current configuration."""
        imported = {"system_prompt": "New prompt"}

        has_changes, changes = _compute_config_diff(None, imported)

        assert has_changes is True
        assert "New configuration" in changes[0]

    def test_diff_added_key(self) -> None:
        """Test diff detects added keys."""
        current = {"key1": "value1"}
        imported = {"key1": "value1", "key2": "value2"}

        has_changes, changes = _compute_config_diff(current, imported)

        assert has_changes is True
        assert any("Added: key2" in c for c in changes)

    def test_diff_removed_key(self) -> None:
        """Test diff detects removed keys."""
        current = {"key1": "value1", "key2": "value2"}
        imported = {"key1": "value1"}

        has_changes, changes = _compute_config_diff(current, imported)

        assert has_changes is True
        assert any("Removed: key2" in c for c in changes)

    def test_diff_changed_value(self) -> None:
        """Test diff detects changed values."""
        current = {"prompt": "Old prompt"}
        imported = {"prompt": "New prompt"}

        has_changes, changes = _compute_config_diff(current, imported)

        assert has_changes is True
        assert any("Changed: prompt" in c for c in changes)

    def test_diff_list_additions(self) -> None:
        """Test diff handles list additions correctly."""
        current = {"classes": ["knife", "gun"]}
        imported = {"classes": ["knife", "gun", "crowbar"]}

        has_changes, changes = _compute_config_diff(current, imported)

        assert has_changes is True
        assert any("crowbar" in c for c in changes)

    def test_diff_list_removals(self) -> None:
        """Test diff handles list removals correctly."""
        current = {"classes": ["knife", "gun", "crowbar"]}
        imported = {"classes": ["knife", "gun"]}

        has_changes, changes = _compute_config_diff(current, imported)

        assert has_changes is True
        assert any("crowbar" in c for c in changes)

    def test_diff_no_changes(self) -> None:
        """Test diff when configs are identical."""
        config = {"prompt": "Same prompt", "threshold": 0.5}

        has_changes, changes = _compute_config_diff(config.copy(), config.copy())

        assert has_changes is False
        assert len(changes) == 0

    def test_diff_ignores_version_field(self) -> None:
        """Test diff ignores version field differences."""
        current = {"prompt": "Same", "version": 1}
        imported = {"prompt": "Same", "version": 2}

        has_changes, changes = _compute_config_diff(current, imported)

        assert has_changes is False
        assert len(changes) == 0

    def test_diff_multiple_changes(self) -> None:
        """Test diff with multiple types of changes."""
        current = {
            "prompt": "Old prompt",
            "threshold": 0.3,
            "classes": ["a", "b"],
            "removed_key": "value",
        }
        imported = {
            "prompt": "New prompt",
            "threshold": 0.5,
            "classes": ["b", "c"],
            "new_key": "value",
        }

        has_changes, changes = _compute_config_diff(current, imported)

        assert has_changes is True
        assert len(changes) >= 4  # Added, removed, 2 changed


class TestRouterConfiguration:
    """Tests for router configuration and metadata."""

    def test_router_prefix(self) -> None:
        """Test that router has correct prefix."""
        assert pm_routes.router.prefix == "/api/ai-audit/prompts"

    def test_router_tags(self) -> None:
        """Test that router has correct tags."""
        assert "prompt-management" in pm_routes.router.tags
