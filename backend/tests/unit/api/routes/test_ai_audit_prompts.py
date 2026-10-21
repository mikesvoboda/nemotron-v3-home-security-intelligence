"""Unit tests for AI audit prompt management API endpoints."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from backend.api.schemas.prompt_management import (
    AIModelEnum,
    AllPromptsResponse,
    ModelPromptConfig,
    NemotronConfig,
    PromptHistoryResponse,
    PromptRestoreResponse,
    PromptsExportResponse,
    PromptsImportRequest,
    PromptsImportResponse,
    PromptTestRequest,
    PromptTestResult,
    PromptUpdateRequest,
    PromptVersionInfo,
)


class TestAIModelEnum:
    """Tests for AIModelEnum values."""

    def test_all_model_values_exist(self):
        """Test that all expected model values are defined."""
        assert AIModelEnum.NEMOTRON.value == "nemotron"

    def test_enum_count(self):
        """Test that we have exactly 1 supported model (the four vision models retired
        with the R8 S2/S3 sweep, B3.3 box 4)."""
        assert len(AIModelEnum) == 1


class TestNemotronConfig:
    """Tests for NemotronConfig schema."""

    def test_valid_config(self):
        """Test NemotronConfig with valid data."""
        config = NemotronConfig(
            system_prompt="You are a security analyst...",
            version=1,
        )
        assert config.system_prompt == "You are a security analyst..."
        assert config.version == 1

    def test_missing_system_prompt(self):
        """Test NemotronConfig raises error without system_prompt."""
        with pytest.raises(ValidationError):
            NemotronConfig()  # type: ignore[call-arg]

    def test_optional_version(self):
        """Test that version is optional."""
        config = NemotronConfig(system_prompt="Test prompt")
        assert config.version is None


class TestModelPromptConfig:
    """Tests for ModelPromptConfig schema."""

    def test_valid_config(self):
        """Test ModelPromptConfig with valid data."""
        config = ModelPromptConfig(
            model=AIModelEnum.NEMOTRON,
            config={"system_prompt": "Test prompt"},
            version=1,
            created_at=datetime.now(),
            created_by="test_user",
            change_description="Initial version",
        )
        assert config.model == AIModelEnum.NEMOTRON
        assert config.version == 1

    def test_minimal_config(self):
        """Test ModelPromptConfig with minimal required fields."""
        config = ModelPromptConfig(
            model=AIModelEnum.NEMOTRON,
            config={"system_prompt": "Test"},
            version=1,
        )
        assert config.model == AIModelEnum.NEMOTRON
        assert config.created_at is None
        assert config.created_by is None


class TestAllPromptsResponse:
    """Tests for AllPromptsResponse schema."""

    def test_valid_response(self):
        """Test AllPromptsResponse with valid data."""
        response = AllPromptsResponse(
            version="1.0",
            exported_at=datetime.now(),
            prompts={
                "nemotron": {"system_prompt": "Test"},
            },
        )
        assert response.version == "1.0"
        assert len(response.prompts) == 1


class TestPromptUpdateRequest:
    """Tests for PromptUpdateRequest schema."""

    def test_valid_request(self):
        """Test PromptUpdateRequest with valid data."""
        request = PromptUpdateRequest(
            config={"system_prompt": "New prompt"},
            change_description="Updated system prompt",
        )
        assert request.config["system_prompt"] == "New prompt"
        assert request.change_description == "Updated system prompt"

    def test_empty_config_rejected(self):
        """Test that empty config is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            PromptUpdateRequest(config={})
        assert "cannot be empty" in str(exc_info.value)

    def test_optional_change_description(self):
        """Test that change_description is optional."""
        request = PromptUpdateRequest(config={"key": "value"})
        assert request.change_description is None


class TestPromptTestRequest:
    """Tests for PromptTestRequest schema."""

    def test_valid_request_with_event(self):
        """Test PromptTestRequest with event_id."""
        request = PromptTestRequest(
            model=AIModelEnum.NEMOTRON,
            config={"system_prompt": "Test"},
            event_id=123,
        )
        assert request.model == AIModelEnum.NEMOTRON
        assert request.event_id == 123
        assert request.image_path is None

    def test_valid_request_with_image(self):
        """Test PromptTestRequest with image_path."""
        request = PromptTestRequest(
            model=AIModelEnum.NEMOTRON,
            config={"system_prompt": "Test"},
            image_path="/path/to/image.jpg",
        )
        assert request.image_path == "/path/to/image.jpg"
        assert request.event_id is None


class TestPromptTestResult:
    """Tests for PromptTestResult schema."""

    def test_successful_result(self):
        """Test PromptTestResult with successful test."""
        result = PromptTestResult(
            model=AIModelEnum.NEMOTRON,
            before_score=50,
            after_score=35,
            before_response={"risk_score": 50},
            after_response={"risk_score": 35},
            improved=True,
            test_duration_ms=1500,
            error=None,
        )
        assert result.improved is True
        assert result.test_duration_ms == 1500
        assert result.error is None

    def test_failed_result(self):
        """Test PromptTestResult with error."""
        result = PromptTestResult(
            model=AIModelEnum.NEMOTRON,
            test_duration_ms=100,
            error="LLM timeout",
        )
        assert result.error == "LLM timeout"
        assert result.before_score is None


class TestPromptVersionInfo:
    """Tests for PromptVersionInfo schema."""

    def test_valid_version_info(self):
        """Test PromptVersionInfo with valid data."""
        info = PromptVersionInfo(
            id=1,
            model=AIModelEnum.NEMOTRON,
            version=3,
            created_at=datetime.now(),
            created_by="user@example.com",
            change_description="Added new risk factors",
            is_active=True,
        )
        assert info.id == 1
        assert info.version == 3
        assert info.is_active is True


class TestPromptHistoryResponse:
    """Tests for PromptHistoryResponse schema."""

    def test_valid_history_response(self):
        """Test PromptHistoryResponse with versions."""
        response = PromptHistoryResponse(
            versions=[
                PromptVersionInfo(
                    id=1,
                    model=AIModelEnum.NEMOTRON,
                    version=1,
                    created_at=datetime.now(),
                    created_by=None,
                    change_description=None,
                    is_active=False,
                ),
                PromptVersionInfo(
                    id=2,
                    model=AIModelEnum.NEMOTRON,
                    version=2,
                    created_at=datetime.now(),
                    created_by=None,
                    change_description=None,
                    is_active=True,
                ),
            ],
            total_count=2,
        )
        assert len(response.versions) == 2
        assert response.total_count == 2


class TestPromptRestoreResponse:
    """Tests for PromptRestoreResponse schema."""

    def test_valid_restore_response(self):
        """Test PromptRestoreResponse with valid data."""
        response = PromptRestoreResponse(
            restored_version=1,
            model=AIModelEnum.NEMOTRON,
            new_version=3,
            message="Successfully restored version 1 as new version 3",
        )
        assert response.restored_version == 1
        assert response.new_version == 3


class TestPromptsExportResponse:
    """Tests for PromptsExportResponse schema."""

    def test_valid_export_response(self):
        """Test PromptsExportResponse with valid data."""
        response = PromptsExportResponse(
            version="1.0",
            exported_at=datetime.now(),
            prompts={
                "nemotron": {"system_prompt": "Test", "version": 1},
            },
        )
        assert response.version == "1.0"
        assert len(response.prompts) == 1


class TestPromptsImportRequest:
    """Tests for PromptsImportRequest schema."""

    def test_valid_import_request(self):
        """Test PromptsImportRequest with valid data."""
        request = PromptsImportRequest(
            version="1.0",
            prompts={
                "nemotron": {"system_prompt": "Imported prompt"},
            },
        )
        assert request.version == "1.0"
        assert len(request.prompts) == 1

    def test_empty_prompts_rejected(self):
        """Test that empty prompts dict is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            PromptsImportRequest(version="1.0", prompts={})
        assert "cannot be empty" in str(exc_info.value)


class TestPromptsImportResponse:
    """Tests for PromptsImportResponse schema."""

    def test_valid_import_response(self):
        """Test PromptsImportResponse with valid data."""
        response = PromptsImportResponse(
            imported_models=["nemotron"],
            skipped_models=["unknown_model"],
            new_versions={"nemotron": 2},
            message="Imported 1 model configuration",
        )
        assert len(response.imported_models) == 1
        assert len(response.skipped_models) == 1
        assert response.new_versions["nemotron"] == 2
