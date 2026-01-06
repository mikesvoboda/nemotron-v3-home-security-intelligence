"""Unit tests for prompt management service."""

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.api.schemas.prompt_management import AIModelEnum
from backend.models.prompt_version import AIModel, PromptVersion
from backend.services.prompt_service import (
    DEFAULT_CONFIGS,
    PromptService,
    get_prompt_service,
    reset_prompt_service,
)


class TestDefaultConfigs:
    """Tests for default configuration values."""

    def test_all_models_have_defaults(self):
        """Test that all supported models have default configs."""
        for model_enum in AIModelEnum:
            assert model_enum.value in DEFAULT_CONFIGS

    def test_nemotron_default_has_system_prompt(self):
        """Test Nemotron default config has system_prompt."""
        config = DEFAULT_CONFIGS[AIModelEnum.NEMOTRON.value]
        assert "system_prompt" in config
        assert len(config["system_prompt"]) > 100  # Non-trivial prompt

    def test_florence2_default_has_queries(self):
        """Test Florence-2 default config has queries."""
        config = DEFAULT_CONFIGS[AIModelEnum.FLORENCE2.value]
        assert "queries" in config
        assert len(config["queries"]) >= 4

    def test_yolo_world_default_has_classes_and_threshold(self):
        """Test YOLO-World default config has classes and threshold."""
        config = DEFAULT_CONFIGS[AIModelEnum.YOLO_WORLD.value]
        assert "classes" in config
        assert "confidence_threshold" in config
        assert 0 < config["confidence_threshold"] < 1

    def test_xclip_default_has_action_classes(self):
        """Test X-CLIP default config has action_classes."""
        config = DEFAULT_CONFIGS[AIModelEnum.XCLIP.value]
        assert "action_classes" in config
        assert len(config["action_classes"]) > 0

    def test_fashion_clip_default_has_categories(self):
        """Test Fashion-CLIP default config has clothing_categories."""
        config = DEFAULT_CONFIGS[AIModelEnum.FASHION_CLIP.value]
        assert "clothing_categories" in config
        assert len(config["clothing_categories"]) > 0


class TestPromptVersionModel:
    """Tests for PromptVersion SQLAlchemy model."""

    def test_config_property_parses_json(self):
        """Test config property correctly parses JSON."""
        version = PromptVersion(
            model=AIModel.NEMOTRON.value,
            version=1,
            config_json='{"key": "value", "nested": {"a": 1}}',
            created_at=datetime.now(UTC),
        )
        assert version.config == {"key": "value", "nested": {"a": 1}}

    def test_config_property_returns_empty_on_invalid_json(self):
        """Test config property returns empty dict on invalid JSON."""
        version = PromptVersion(
            model=AIModel.NEMOTRON.value,
            version=1,
            config_json="not valid json",
            created_at=datetime.now(UTC),
        )
        assert version.config == {}

    def test_set_config_serializes_to_json(self):
        """Test set_config method serializes dict to JSON."""
        version = PromptVersion(
            model=AIModel.NEMOTRON.value,
            version=1,
            config_json="{}",
            created_at=datetime.now(UTC),
        )
        version.set_config({"test": "data", "number": 42})

        # Verify it was serialized
        assert version.config_json is not None
        parsed = json.loads(version.config_json)
        assert parsed["test"] == "data"
        assert parsed["number"] == 42

    def test_repr(self):
        """Test string representation."""
        version = PromptVersion(
            id=1,
            model=AIModel.NEMOTRON.value,
            version=3,
            config_json="{}",
            is_active=True,
            created_at=datetime.now(UTC),
        )
        repr_str = repr(version)
        assert "id=1" in repr_str
        assert "version=3" in repr_str
        assert "active=True" in repr_str


class TestPromptServiceSingleton:
    """Tests for prompt service singleton pattern."""

    def test_get_prompt_service_returns_instance(self):
        """Test get_prompt_service returns a PromptService instance."""
        reset_prompt_service()  # Clean state
        service = get_prompt_service()
        assert isinstance(service, PromptService)

    def test_get_prompt_service_returns_same_instance(self):
        """Test get_prompt_service returns the same instance."""
        reset_prompt_service()
        service1 = get_prompt_service()
        service2 = get_prompt_service()
        assert service1 is service2

    def test_reset_prompt_service_clears_singleton(self):
        """Test reset_prompt_service clears the singleton."""
        reset_prompt_service()
        service1 = get_prompt_service()
        reset_prompt_service()
        service2 = get_prompt_service()
        assert service1 is not service2


class TestPromptService:
    """Tests for PromptService methods."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        session = AsyncMock()
        session.execute = AsyncMock()
        session.add = MagicMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        return session

    @pytest.fixture
    def service(self):
        """Create a fresh PromptService instance."""
        reset_prompt_service()
        return PromptService()

    @pytest.mark.asyncio
    async def test_get_prompt_for_model_returns_default_when_no_version(
        self, service, mock_session
    ):
        """Test get_prompt_for_model returns default config when no version exists."""
        # Mock no version found
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_session.execute.return_value = mock_result

        config = await service.get_prompt_for_model(mock_session, "nemotron")

        # Should return default config
        assert "system_prompt" in config

    @pytest.mark.asyncio
    async def test_get_prompt_for_model_returns_active_version(self, service, mock_session):
        """Test get_prompt_for_model returns the active version config."""
        # Create mock version
        mock_version = MagicMock()
        mock_version.config = {"system_prompt": "Custom prompt"}
        mock_version.version = 2

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_version)
        mock_session.execute.return_value = mock_result

        config = await service.get_prompt_for_model(mock_session, "nemotron")

        assert config["system_prompt"] == "Custom prompt"
        assert config["version"] == 2

    @pytest.mark.asyncio
    async def test_get_all_prompts_returns_all_models(self, service, mock_session):
        """Test get_all_prompts returns config for all models."""
        # Mock no versions found (returns defaults)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_session.execute.return_value = mock_result

        prompts = await service.get_all_prompts(mock_session)

        # Should have all 5 models
        assert len(prompts) == 5
        assert "nemotron" in prompts
        assert "florence2" in prompts
        assert "yolo_world" in prompts
        assert "xclip" in prompts
        assert "fashion_clip" in prompts

    @pytest.mark.asyncio
    async def test_update_prompt_for_model_creates_new_version(self, service, mock_session):
        """Test update_prompt_for_model creates a new version."""
        # Mock max version query returns 1
        max_result = MagicMock()
        max_result.scalar = MagicMock(return_value=1)

        # Mock update query
        update_result = MagicMock()

        mock_session.execute.side_effect = [max_result, update_result]

        new_config = {"system_prompt": "Updated prompt"}
        _new_version = await service.update_prompt_for_model(
            session=mock_session,
            model="nemotron",
            config=new_config,
            change_description="Test update",
        )

        # Verify session.add was called
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()

        # Verify the new version has correct data
        added_version = mock_session.add.call_args[0][0]
        assert added_version.model == "nemotron"
        assert added_version.version == 2
        assert added_version.is_active is True
        assert added_version.change_description == "Test update"

    @pytest.mark.asyncio
    async def test_get_version_history_returns_versions(self, service, mock_session):
        """Test get_version_history returns paginated versions."""
        # Mock count query
        count_result = MagicMock()
        count_result.scalar = MagicMock(return_value=10)

        # Mock versions query
        mock_versions = [
            MagicMock(id=1, model="nemotron", version=1, created_at=datetime.now(UTC)),
            MagicMock(id=2, model="nemotron", version=2, created_at=datetime.now(UTC)),
        ]
        versions_result = MagicMock()
        versions_result.scalars = MagicMock(
            return_value=MagicMock(all=MagicMock(return_value=mock_versions))
        )

        mock_session.execute.side_effect = [count_result, versions_result]

        versions, total = await service.get_version_history(
            session=mock_session,
            model="nemotron",
            limit=10,
            offset=0,
        )

        assert total == 10
        assert len(versions) == 2

    @pytest.mark.asyncio
    async def test_restore_version_creates_new_version(self, service, mock_session):
        """Test restore_version creates new version with old config."""
        # Mock finding the old version
        old_version = MagicMock()
        old_version.model = "nemotron"
        old_version.version = 1
        old_version.config = {"system_prompt": "Old prompt"}

        find_result = MagicMock()
        find_result.scalar_one_or_none = MagicMock(return_value=old_version)

        # Mock for update operation (max version + update)
        max_result = MagicMock()
        max_result.scalar = MagicMock(return_value=2)

        update_result = MagicMock()

        mock_session.execute.side_effect = [find_result, max_result, update_result]

        _new_version = await service.restore_version(
            session=mock_session,
            version_id=1,
        )

        # Verify new version was created
        mock_session.add.assert_called()
        added = mock_session.add.call_args[0][0]
        assert added.version == 3
        assert "Restored from version" in (added.change_description or "")

    @pytest.mark.asyncio
    async def test_restore_version_raises_on_not_found(self, service, mock_session):
        """Test restore_version raises ValueError when version not found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_session.execute.return_value = mock_result

        with pytest.raises(ValueError) as exc_info:
            await service.restore_version(mock_session, version_id=999)

        assert "999" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_export_all_prompts_returns_export_format(self, service, mock_session):
        """Test export_all_prompts returns correct export format."""
        # Mock no versions (returns defaults)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_session.execute.return_value = mock_result

        export_data = await service.export_all_prompts(mock_session)

        assert "version" in export_data
        assert export_data["version"] == "1.0"
        assert "exported_at" in export_data
        assert "prompts" in export_data
        assert len(export_data["prompts"]) == 5

    @pytest.mark.asyncio
    async def test_import_prompts_imports_valid_models(self, service, mock_session):
        """Test import_prompts imports valid model configs."""
        # Mock for each update operation
        max_result = MagicMock()
        max_result.scalar = MagicMock(return_value=0)

        update_result = MagicMock()

        # Need results for 2 models (2 calls per model: max query + update)
        mock_session.execute.side_effect = [
            max_result,
            update_result,
            max_result,
            update_result,
        ]

        import_data = {
            "nemotron": {"system_prompt": "Imported prompt"},
            "florence2": {"queries": ["Test query"]},
        }

        result = await service.import_prompts(mock_session, import_data)

        assert len(result["imported_models"]) == 2
        assert "nemotron" in result["imported_models"]
        assert "florence2" in result["imported_models"]

    @pytest.mark.asyncio
    async def test_import_prompts_skips_unknown_models(self, service, mock_session):
        """Test import_prompts skips unknown model names."""
        # Mock for valid model import
        max_result = MagicMock()
        max_result.scalar = MagicMock(return_value=0)

        update_result = MagicMock()
        mock_session.execute.side_effect = [max_result, update_result]

        import_data = {
            "nemotron": {"system_prompt": "Valid"},
            "unknown_model": {"some": "config"},
            "another_fake": {"data": "here"},
        }

        result = await service.import_prompts(mock_session, import_data)

        assert "nemotron" in result["imported_models"]
        assert "unknown_model" in result["skipped_models"]
        assert "another_fake" in result["skipped_models"]


class TestPromptTestFunction:
    """Tests for prompt testing functionality."""

    @pytest.fixture
    def service(self):
        """Create a fresh PromptService instance."""
        reset_prompt_service()
        return PromptService()

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        session = AsyncMock()
        session.execute = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_test_prompt_requires_event_or_image(self, service, mock_session):
        """Test that test_prompt requires either event_id or image_path."""
        result = await service.test_prompt(
            session=mock_session,
            model="nemotron",
            config={"system_prompt": "Test"},
            event_id=None,
            image_path=None,
        )

        assert result["error"] is not None
        assert "event_id or image_path" in result["error"]

    @pytest.mark.asyncio
    async def test_test_prompt_unsupported_model(self, service, mock_session):
        """Test that test_prompt returns error for unsupported models."""
        result = await service.test_prompt(
            session=mock_session,
            model="florence2",  # Not yet implemented
            config={"queries": []},
            event_id=123,
        )

        assert result["error"] is not None
        assert "not yet implemented" in result["error"]

    @pytest.mark.asyncio
    async def test_test_prompt_event_not_found(self, service, mock_session):
        """Test that test_prompt returns error when event not found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_session.execute.return_value = mock_result

        result = await service.test_prompt(
            session=mock_session,
            model="nemotron",
            config={"system_prompt": "Test"},
            event_id=999,
        )

        assert result["error"] is not None
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_test_prompt_returns_duration(self, service, mock_session):
        """Test that test_prompt always returns test_duration_ms."""
        result = await service.test_prompt(
            session=mock_session,
            model="nemotron",
            config={"system_prompt": "Test"},
            event_id=None,
            image_path=None,
        )

        assert "test_duration_ms" in result
        assert result["test_duration_ms"] >= 0
