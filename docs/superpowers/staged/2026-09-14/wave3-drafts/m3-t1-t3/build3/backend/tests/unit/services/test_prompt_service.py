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

    @pytest.mark.asyncio
    async def test_test_prompt_missing_system_prompt_in_config(self, service, mock_session):
        """Test that test_prompt returns error when system_prompt is missing from config."""
        # Mock event found
        mock_event = MagicMock()
        mock_event.risk_score = 50
        mock_event.llm_prompt = "Test context"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_event)
        mock_session.execute.return_value = mock_result

        result = await service.test_prompt(
            session=mock_session,
            model="nemotron",
            config={},  # Missing system_prompt
            event_id=123,
        )

        assert result["error"] is not None
        assert "system_prompt not found" in result["error"]

    @pytest.mark.asyncio
    async def test_test_prompt_successful_llm_test(self, service, mock_session):
        """Test successful LLM test with valid response."""
        from unittest.mock import patch

        # Mock event found
        mock_event = MagicMock()
        mock_event.risk_score = 50
        mock_event.llm_prompt = "Test context"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_event)
        mock_session.execute.return_value = mock_result

        # Mock _run_llm_test to return a risk score
        with patch.object(service, "_run_llm_test", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = {"risk_score": 45, "reasoning": "Test reasoning"}

            result = await service.test_prompt(
                session=mock_session,
                model="nemotron",
                config={"system_prompt": "Test prompt"},
                event_id=123,
            )

            assert result["before_score"] == 50
            assert result["after_score"] == 45
            assert result["after_response"]["reasoning"] == "Test reasoning"
            assert result["improved"] is True  # Difference <= 10
            assert result["error"] is None

    @pytest.mark.asyncio
    async def test_test_prompt_handles_timeout_exception(self, service, mock_session):
        """Test that test_prompt handles httpx.TimeoutException."""
        from unittest.mock import patch

        import httpx

        # Mock event found
        mock_event = MagicMock()
        mock_event.risk_score = 50
        mock_event.llm_prompt = "Test context"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_event)
        mock_session.execute.return_value = mock_result

        # Mock _run_llm_test to raise TimeoutException
        with patch.object(service, "_run_llm_test", new_callable=AsyncMock) as mock_llm:
            mock_llm.side_effect = httpx.TimeoutException("Request timeout")

            result = await service.test_prompt(
                session=mock_session,
                model="nemotron",
                config={"system_prompt": "Test prompt"},
                event_id=123,
            )

            assert "Request timed out" in result["error"]
            assert result["test_duration_ms"] >= 0

    @pytest.mark.asyncio
    async def test_test_prompt_handles_http_status_error(self, service, mock_session):
        """Test that test_prompt handles httpx.HTTPStatusError."""
        from unittest.mock import patch

        import httpx

        # Mock event found
        mock_event = MagicMock()
        mock_event.risk_score = 50
        mock_event.llm_prompt = "Test context"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_event)
        mock_session.execute.return_value = mock_result

        # Create mock response
        mock_response = MagicMock()
        mock_response.status_code = 500

        # Mock _run_llm_test to raise HTTPStatusError
        with patch.object(service, "_run_llm_test", new_callable=AsyncMock) as mock_llm:
            mock_llm.side_effect = httpx.HTTPStatusError(
                "Server error", request=MagicMock(), response=mock_response
            )

            result = await service.test_prompt(
                session=mock_session,
                model="nemotron",
                config={"system_prompt": "Test prompt"},
                event_id=123,
            )

            assert "HTTP error" in result["error"]
            assert result["test_duration_ms"] >= 0

    @pytest.mark.asyncio
    async def test_test_prompt_handles_request_error(self, service, mock_session):
        """Test that test_prompt handles httpx.RequestError."""
        from unittest.mock import patch

        import httpx

        # Mock event found
        mock_event = MagicMock()
        mock_event.risk_score = 50
        mock_event.llm_prompt = "Test context"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_event)
        mock_session.execute.return_value = mock_result

        # Mock _run_llm_test to raise RequestError
        with patch.object(service, "_run_llm_test", new_callable=AsyncMock) as mock_llm:
            mock_llm.side_effect = httpx.RequestError("Connection failed")

            result = await service.test_prompt(
                session=mock_session,
                model="nemotron",
                config={"system_prompt": "Test prompt"},
                event_id=123,
            )

            assert "Request failed" in result["error"]
            assert result["test_duration_ms"] >= 0

    @pytest.mark.asyncio
    async def test_test_prompt_handles_data_error(self, service, mock_session):
        """Test that test_prompt handles KeyError/TypeError/ValueError."""
        from unittest.mock import patch

        # Mock event found
        mock_event = MagicMock()
        mock_event.risk_score = 50
        mock_event.llm_prompt = "Test context"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_event)
        mock_session.execute.return_value = mock_result

        # Mock _run_llm_test to raise ValueError
        with patch.object(service, "_run_llm_test", new_callable=AsyncMock) as mock_llm:
            mock_llm.side_effect = ValueError("Invalid data format")

            result = await service.test_prompt(
                session=mock_session,
                model="nemotron",
                config={"system_prompt": "Test prompt"},
                event_id=123,
            )

            assert "Data error" in result["error"]
            assert result["test_duration_ms"] >= 0


class TestRunLLMTest:
    """Tests for _run_llm_test internal method."""

    @pytest.fixture
    def service(self):
        """Create a fresh PromptService instance."""
        reset_prompt_service()
        return PromptService()

    @pytest.mark.asyncio
    async def test_run_llm_test_no_context(self, service):
        """Test _run_llm_test with no context returns error."""
        result = await service._run_llm_test("System prompt", None)

        assert "error" in result
        assert "No context" in result["error"]

    @pytest.mark.asyncio
    async def test_run_llm_test_successful_json_response(self, service):
        """Test _run_llm_test with successful JSON response."""
        from unittest.mock import AsyncMock, patch

        mock_response = MagicMock()
        mock_response.json.return_value = {"content": '{"risk_score": 75, "reasoning": "Test"}'}

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await service._run_llm_test("System prompt", "User context")

            assert result["risk_score"] == 75
            assert result["reasoning"] == "Test"
            mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_llm_test_non_json_response(self, service):
        """Test _run_llm_test with non-JSON response."""
        from unittest.mock import AsyncMock, patch

        mock_response = MagicMock()
        mock_response.json.return_value = {"content": "This is not JSON content"}

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await service._run_llm_test("System prompt", "User context")

            assert "raw_response" in result
            assert result["raw_response"] == "This is not JSON content"

    @pytest.mark.asyncio
    async def test_run_llm_test_timeout_exception(self, service):
        """Test _run_llm_test handles timeout exception."""
        from unittest.mock import AsyncMock, patch

        import httpx

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await service._run_llm_test("System prompt", "User context")

            assert "error" in result
            assert "timed out" in result["error"]

    @pytest.mark.asyncio
    async def test_run_llm_test_http_status_error(self, service):
        """Test _run_llm_test handles HTTP status error."""
        from unittest.mock import AsyncMock, patch

        import httpx

        mock_response = MagicMock()
        mock_response.status_code = 503

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "Service unavailable",
                request=MagicMock(),
                response=mock_response,
            )
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await service._run_llm_test("System prompt", "User context")

            assert "error" in result
            assert "HTTP error 503" in result["error"]

    @pytest.mark.asyncio
    async def test_run_llm_test_request_error(self, service):
        """Test _run_llm_test handles request error."""
        from unittest.mock import AsyncMock, patch

        import httpx

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.RequestError("Connection failed"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await service._run_llm_test("System prompt", "User context")

            assert "error" in result
            assert "Request failed" in result["error"]


class TestImportPromptsErrorHandling:
    """Tests for import_prompts error handling."""

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
        session.add = MagicMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_import_prompts_handles_update_exception(self, service, mock_session):
        """Test import_prompts handles exceptions during model update."""
        from unittest.mock import patch

        # Mock update_prompt_for_model to raise an exception
        with patch.object(
            service,
            "update_prompt_for_model",
            side_effect=Exception("Database error"),
        ):
            import_data = {
                "nemotron": {"system_prompt": "Test prompt"},
            }

            result = await service.import_prompts(mock_session, import_data)

            assert "nemotron" in result["skipped_models"]
            assert len(result["imported_models"]) == 0
            assert "message" in result

    @pytest.mark.asyncio
    async def test_import_prompts_partial_success(self, service, mock_session):
        """Test import_prompts with partial success (some succeed, some fail)."""
        # Mock for successful nemotron import
        max_result_success = MagicMock()
        max_result_success.scalar = MagicMock(return_value=0)
        update_result_success = MagicMock()

        # Set up execute to succeed for first model
        mock_session.execute.side_effect = [
            max_result_success,
            update_result_success,
        ]

        # Store the original update method
        original_update = service.update_prompt_for_model

        # Create a counter to track calls
        call_count = [0]

        async def mock_update(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                # First call succeeds
                return await original_update(*args, **kwargs)
            else:
                # Second call fails
                raise Exception("Database error")

        from unittest.mock import patch

        with patch.object(service, "update_prompt_for_model", side_effect=mock_update):
            import_data = {
                "nemotron": {"system_prompt": "Valid prompt"},
                "florence2": {"queries": ["Will fail"]},
            }

            result = await service.import_prompts(mock_session, import_data)

            assert "nemotron" in result["imported_models"]
            assert "florence2" in result["skipped_models"]
            assert len(result["imported_models"]) == 1
            assert len(result["skipped_models"]) == 1


class TestVersionConflictHandling:
    """Tests for optimistic locking and version conflict detection."""

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
        session.add = MagicMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_update_prompt_detects_concurrent_modification(self, service, mock_session):
        """Test update_prompt_for_model detects concurrent modifications."""
        from backend.api.schemas.prompt_management import PromptVersionConflictError

        # Mock current version is 5, but we expect version 3
        max_result = MagicMock()
        max_result.scalar = MagicMock(return_value=5)
        mock_session.execute.return_value = max_result

        with pytest.raises(PromptVersionConflictError) as exc_info:
            await service.update_prompt_for_model(
                session=mock_session,
                model="nemotron",
                config={"system_prompt": "New prompt"},
                expected_version=3,
            )

        assert "3" in str(exc_info.value)  # Expected version
        assert "5" in str(exc_info.value)  # Actual version

    @pytest.mark.asyncio
    async def test_update_prompt_allows_first_version_without_conflict(self, service, mock_session):
        """Test update_prompt_for_model allows first version creation with expected_version."""
        # Mock no existing versions (max_version = 0)
        max_result = MagicMock()
        max_result.scalar = MagicMock(return_value=0)
        update_result = MagicMock()
        mock_session.execute.side_effect = [max_result, update_result]

        # Should succeed even with expected_version=None when max_version=0
        _new_version = await service.update_prompt_for_model(
            session=mock_session,
            model="nemotron",
            config={"system_prompt": "First prompt"},
            expected_version=None,
        )

        # Verify new version was created
        mock_session.add.assert_called_once()
        added = mock_session.add.call_args[0][0]
        assert added.version == 1
