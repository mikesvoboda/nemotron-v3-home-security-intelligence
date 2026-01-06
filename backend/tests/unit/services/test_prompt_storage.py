"""Unit tests for prompt storage service (prompt_storage.py).

This module provides comprehensive tests for the PromptStorageService class
which handles file-based storage for AI model prompt configurations with
version history tracking.

Tests cover:
- Service initialization and storage path setup
- Configuration CRUD operations
- Version history and pagination
- Version restoration
- Import/export functionality
- Model-specific validation rules
- Mock testing functionality
- Singleton pattern

All tests use temporary directories to avoid file system side effects.
"""

from __future__ import annotations

import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from backend.services.prompt_storage import (
    DEFAULT_CONFIGS,
    DEFAULT_PROMPT_STORAGE_PATH,
    SUPPORTED_MODELS,
    PromptStorageService,
    PromptVersion,
    get_prompt_storage,
    reset_prompt_storage,
)

# Mark all tests in this file as unit tests
pytestmark = pytest.mark.unit


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def temp_storage_dir() -> Path:
    """Create a temporary directory for storage tests.

    Returns:
        Path to temporary directory that will be cleaned up after test.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def storage_service(temp_storage_dir: Path) -> PromptStorageService:
    """Create a PromptStorageService with a temporary storage directory.

    Args:
        temp_storage_dir: Temporary directory fixture

    Returns:
        Fresh PromptStorageService instance using temporary storage.
    """
    return PromptStorageService(storage_path=temp_storage_dir)


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset the singleton before and after each test."""
    reset_prompt_storage()
    yield
    reset_prompt_storage()


# =============================================================================
# Test: Module Constants
# =============================================================================


class TestModuleConstants:
    """Tests for module-level constants."""

    def test_supported_models_is_frozenset(self):
        """Test SUPPORTED_MODELS is an immutable frozenset."""
        assert isinstance(SUPPORTED_MODELS, frozenset)

    def test_supported_models_contains_expected_models(self):
        """Test SUPPORTED_MODELS contains all expected model names."""
        expected = {"nemotron", "florence2", "yolo_world", "xclip", "fashion_clip"}
        assert expected == SUPPORTED_MODELS

    def test_default_configs_has_all_models(self):
        """Test DEFAULT_CONFIGS has configuration for all supported models."""
        for model in SUPPORTED_MODELS:
            assert model in DEFAULT_CONFIGS

    def test_default_prompt_storage_path_is_path(self):
        """Test DEFAULT_PROMPT_STORAGE_PATH is a Path object."""
        assert isinstance(DEFAULT_PROMPT_STORAGE_PATH, Path)

    def test_default_prompt_storage_path_ends_with_prompts(self):
        """Test DEFAULT_PROMPT_STORAGE_PATH points to prompts directory."""
        assert DEFAULT_PROMPT_STORAGE_PATH.name == "prompts"
        assert DEFAULT_PROMPT_STORAGE_PATH.parent.name == "data"


# =============================================================================
# Test: Default Configurations
# =============================================================================


class TestDefaultConfigs:
    """Tests for default configuration values."""

    def test_nemotron_default_has_system_prompt(self):
        """Test Nemotron default config has system_prompt field."""
        config = DEFAULT_CONFIGS["nemotron"]
        assert "system_prompt" in config
        assert isinstance(config["system_prompt"], str)
        assert len(config["system_prompt"]) > 100  # Non-trivial prompt

    def test_nemotron_default_has_temperature(self):
        """Test Nemotron default config has temperature field."""
        config = DEFAULT_CONFIGS["nemotron"]
        assert "temperature" in config
        assert 0 <= config["temperature"] <= 2

    def test_nemotron_default_has_max_tokens(self):
        """Test Nemotron default config has max_tokens field."""
        config = DEFAULT_CONFIGS["nemotron"]
        assert "max_tokens" in config
        assert isinstance(config["max_tokens"], int)
        assert config["max_tokens"] > 0

    def test_florence2_default_has_vqa_queries(self):
        """Test Florence-2 default config has vqa_queries list."""
        config = DEFAULT_CONFIGS["florence2"]
        assert "vqa_queries" in config
        assert isinstance(config["vqa_queries"], list)
        assert len(config["vqa_queries"]) >= 4

    def test_yolo_world_default_has_object_classes(self):
        """Test YOLO-World default config has object_classes list."""
        config = DEFAULT_CONFIGS["yolo_world"]
        assert "object_classes" in config
        assert isinstance(config["object_classes"], list)
        assert "person" in config["object_classes"]

    def test_yolo_world_default_has_confidence_threshold(self):
        """Test YOLO-World default config has confidence_threshold."""
        config = DEFAULT_CONFIGS["yolo_world"]
        assert "confidence_threshold" in config
        assert 0 < config["confidence_threshold"] < 1

    def test_xclip_default_has_action_classes(self):
        """Test X-CLIP default config has action_classes list."""
        config = DEFAULT_CONFIGS["xclip"]
        assert "action_classes" in config
        assert isinstance(config["action_classes"], list)
        assert len(config["action_classes"]) > 0
        assert "walking" in config["action_classes"]

    def test_fashion_clip_default_has_clothing_categories(self):
        """Test Fashion-CLIP default config has clothing_categories list."""
        config = DEFAULT_CONFIGS["fashion_clip"]
        assert "clothing_categories" in config
        assert isinstance(config["clothing_categories"], list)
        assert len(config["clothing_categories"]) > 0

    def test_fashion_clip_default_has_suspicious_indicators(self):
        """Test Fashion-CLIP default config has suspicious_indicators list."""
        config = DEFAULT_CONFIGS["fashion_clip"]
        assert "suspicious_indicators" in config
        assert isinstance(config["suspicious_indicators"], list)
        assert len(config["suspicious_indicators"]) > 0


# =============================================================================
# Test: PromptVersion Dataclass
# =============================================================================


class TestPromptVersionDataclass:
    """Tests for PromptVersion dataclass."""

    def test_prompt_version_creation(self):
        """Test creating a PromptVersion instance."""
        now = datetime.now(UTC)
        version = PromptVersion(
            version=1,
            config={"key": "value"},
            created_at=now,
            created_by="test_user",
            description="Test version",
        )
        assert version.version == 1
        assert version.config == {"key": "value"}
        assert version.created_at == now
        assert version.created_by == "test_user"
        assert version.description == "Test version"

    def test_prompt_version_with_none_description(self):
        """Test PromptVersion with None description."""
        version = PromptVersion(
            version=1,
            config={},
            created_at=datetime.now(UTC),
            created_by="user",
            description=None,
        )
        assert version.description is None


# =============================================================================
# Test: Service Initialization
# =============================================================================


class TestServiceInitialization:
    """Tests for PromptStorageService initialization."""

    def test_init_with_custom_storage_path(self, temp_storage_dir: Path):
        """Test initialization with custom storage path."""
        service = PromptStorageService(storage_path=temp_storage_dir)
        assert service.storage_path == temp_storage_dir

    def test_init_with_default_storage_path(self):
        """Test initialization uses default path when none provided."""
        service = PromptStorageService()
        assert service.storage_path == DEFAULT_PROMPT_STORAGE_PATH

    def test_init_creates_model_directories(self, temp_storage_dir: Path):
        """Test initialization creates directories for all supported models."""
        PromptStorageService(storage_path=temp_storage_dir)
        for model in SUPPORTED_MODELS:
            model_dir = temp_storage_dir / model
            assert model_dir.exists()
            assert model_dir.is_dir()

    def test_init_creates_history_directories(self, temp_storage_dir: Path):
        """Test initialization creates history directories for all models."""
        PromptStorageService(storage_path=temp_storage_dir)
        for model in SUPPORTED_MODELS:
            history_dir = temp_storage_dir / model / "history"
            assert history_dir.exists()
            assert history_dir.is_dir()

    def test_init_idempotent(self, temp_storage_dir: Path):
        """Test multiple initializations don't cause errors."""
        PromptStorageService(storage_path=temp_storage_dir)
        # Second initialization should work fine
        service = PromptStorageService(storage_path=temp_storage_dir)
        assert service.storage_path == temp_storage_dir


# =============================================================================
# Test: get_config()
# =============================================================================


class TestGetConfig:
    """Tests for get_config() method."""

    def test_get_config_returns_default_when_no_file(
        self, storage_service: PromptStorageService, temp_storage_dir: Path
    ):
        """Test get_config returns default config when no file exists."""
        config = storage_service.get_config("nemotron")
        assert "system_prompt" in config
        # Should create the default config file
        assert (temp_storage_dir / "nemotron" / "current.json").exists()

    def test_get_config_returns_stored_config(self, storage_service: PromptStorageService):
        """Test get_config returns stored configuration."""
        # Store a custom config
        custom_config = {"system_prompt": "Custom prompt", "temperature": 0.5}
        storage_service.update_config("nemotron", custom_config, created_by="test")

        # Retrieve it
        config = storage_service.get_config("nemotron")
        assert config["system_prompt"] == "Custom prompt"
        assert config["temperature"] == 0.5

    def test_get_config_unsupported_model_raises(self, storage_service: PromptStorageService):
        """Test get_config raises ValueError for unsupported model."""
        with pytest.raises(ValueError) as exc_info:
            storage_service.get_config("unknown_model")
        assert "Unsupported model" in str(exc_info.value)

    def test_get_config_for_all_models(self, storage_service: PromptStorageService):
        """Test get_config works for all supported models."""
        for model in SUPPORTED_MODELS:
            config = storage_service.get_config(model)
            assert isinstance(config, dict)

    def test_get_config_handles_malformed_json(self, temp_storage_dir: Path):
        """Test get_config handles malformed JSON gracefully."""
        service = PromptStorageService(storage_path=temp_storage_dir)

        # Write malformed JSON to current.json
        current_path = temp_storage_dir / "nemotron" / "current.json"
        current_path.write_text("not valid json {{{")

        # Should return default config
        config = service.get_config("nemotron")
        assert "system_prompt" in config


# =============================================================================
# Test: get_config_with_metadata()
# =============================================================================


class TestGetConfigWithMetadata:
    """Tests for get_config_with_metadata() method."""

    def test_get_config_with_metadata_returns_dict(self, storage_service: PromptStorageService):
        """Test get_config_with_metadata returns a dict with metadata."""
        result = storage_service.get_config_with_metadata("nemotron")
        assert isinstance(result, dict)
        assert "config" in result
        assert "version" in result
        assert "model_name" in result

    def test_get_config_with_metadata_has_updated_at(self, storage_service: PromptStorageService):
        """Test get_config_with_metadata includes updated_at timestamp."""
        result = storage_service.get_config_with_metadata("nemotron")
        assert "updated_at" in result

    def test_get_config_with_metadata_creates_default(
        self, storage_service: PromptStorageService, temp_storage_dir: Path
    ):
        """Test get_config_with_metadata creates default if none exists."""
        # Ensure no current.json exists
        current_path = temp_storage_dir / "florence2" / "current.json"
        if current_path.exists():
            current_path.unlink()

        result = storage_service.get_config_with_metadata("florence2")
        assert result["model_name"] == "florence2"
        assert "config" in result

    def test_get_config_with_metadata_unsupported_model(
        self, storage_service: PromptStorageService
    ):
        """Test get_config_with_metadata raises for unsupported model."""
        with pytest.raises(ValueError) as exc_info:
            storage_service.get_config_with_metadata("fake_model")
        assert "Unsupported model" in str(exc_info.value)


# =============================================================================
# Test: update_config()
# =============================================================================


class TestUpdateConfig:
    """Tests for update_config() method."""

    def test_update_config_creates_version_1(self, storage_service: PromptStorageService):
        """Test update_config creates version 1 for first update."""
        result = storage_service.update_config(
            model_name="nemotron",
            config={"system_prompt": "New prompt"},
            created_by="test_user",
            description="Initial config",
        )
        assert result.version == 1
        assert result.config["system_prompt"] == "New prompt"
        assert result.created_by == "test_user"
        assert result.description == "Initial config"

    def test_update_config_increments_version(self, storage_service: PromptStorageService):
        """Test update_config increments version number."""
        storage_service.update_config(
            model_name="nemotron",
            config={"system_prompt": "V1"},
            created_by="user",
        )
        result = storage_service.update_config(
            model_name="nemotron",
            config={"system_prompt": "V2"},
            created_by="user",
        )
        assert result.version == 2

    def test_update_config_saves_to_history(
        self, storage_service: PromptStorageService, temp_storage_dir: Path
    ):
        """Test update_config saves version to history directory."""
        storage_service.update_config(
            model_name="nemotron",
            config={"system_prompt": "Test"},
            created_by="user",
        )
        history_path = temp_storage_dir / "nemotron" / "history" / "v1.json"
        assert history_path.exists()

    def test_update_config_updates_current(
        self, storage_service: PromptStorageService, temp_storage_dir: Path
    ):
        """Test update_config updates current.json."""
        storage_service.update_config(
            model_name="nemotron",
            config={"system_prompt": "Updated"},
            created_by="user",
        )
        current_path = temp_storage_dir / "nemotron" / "current.json"
        assert current_path.exists()
        data = json.loads(current_path.read_text())
        assert data["config"]["system_prompt"] == "Updated"

    def test_update_config_returns_prompt_version(self, storage_service: PromptStorageService):
        """Test update_config returns a PromptVersion object."""
        result = storage_service.update_config(
            model_name="nemotron",
            config={"system_prompt": "Test"},
            created_by="test",
        )
        assert isinstance(result, PromptVersion)
        assert isinstance(result.created_at, datetime)

    def test_update_config_unsupported_model_raises(self, storage_service: PromptStorageService):
        """Test update_config raises ValueError for unsupported model."""
        with pytest.raises(ValueError) as exc_info:
            storage_service.update_config(
                model_name="invalid",
                config={},
                created_by="user",
            )
        assert "Unsupported model" in str(exc_info.value)

    def test_update_config_default_created_by(self, storage_service: PromptStorageService):
        """Test update_config has default created_by value."""
        result = storage_service.update_config(
            model_name="nemotron",
            config={"system_prompt": "Test"},
        )
        assert result.created_by == "user"

    def test_update_config_none_description(self, storage_service: PromptStorageService):
        """Test update_config allows None description."""
        result = storage_service.update_config(
            model_name="nemotron",
            config={"system_prompt": "Test"},
            description=None,
        )
        assert result.description is None


# =============================================================================
# Test: get_history()
# =============================================================================


class TestGetHistory:
    """Tests for get_history() method."""

    def test_get_history_empty_when_no_versions(self, storage_service: PromptStorageService):
        """Test get_history returns empty list when no versions exist."""
        history = storage_service.get_history("nemotron")
        assert history == []

    def test_get_history_returns_versions(self, storage_service: PromptStorageService):
        """Test get_history returns created versions."""
        # Create multiple versions
        for i in range(3):
            storage_service.update_config(
                model_name="nemotron",
                config={"system_prompt": f"Version {i + 1}"},
                created_by="user",
            )

        history = storage_service.get_history("nemotron")
        assert len(history) == 3

    def test_get_history_newest_first(self, storage_service: PromptStorageService):
        """Test get_history returns versions in descending order (newest first)."""
        for i in range(3):
            storage_service.update_config(
                model_name="nemotron",
                config={"system_prompt": f"V{i + 1}"},
                created_by="user",
            )

        history = storage_service.get_history("nemotron")
        assert history[0].version == 3
        assert history[1].version == 2
        assert history[2].version == 1

    def test_get_history_pagination_limit(self, storage_service: PromptStorageService):
        """Test get_history respects limit parameter."""
        for i in range(10):
            storage_service.update_config(
                model_name="nemotron",
                config={"system_prompt": f"V{i + 1}"},
                created_by="user",
            )

        history = storage_service.get_history("nemotron", limit=3)
        assert len(history) == 3
        assert history[0].version == 10  # Newest first

    def test_get_history_pagination_offset(self, storage_service: PromptStorageService):
        """Test get_history respects offset parameter."""
        for i in range(10):
            storage_service.update_config(
                model_name="nemotron",
                config={"system_prompt": f"V{i + 1}"},
                created_by="user",
            )

        history = storage_service.get_history("nemotron", limit=3, offset=2)
        assert len(history) == 3
        assert history[0].version == 8  # Skipped v10, v9

    def test_get_history_pagination_beyond_total(self, storage_service: PromptStorageService):
        """Test get_history with offset beyond total versions."""
        storage_service.update_config(
            model_name="nemotron",
            config={"system_prompt": "Test"},
            created_by="user",
        )

        history = storage_service.get_history("nemotron", offset=100)
        assert history == []

    def test_get_history_returns_prompt_versions(self, storage_service: PromptStorageService):
        """Test get_history returns list of PromptVersion objects."""
        storage_service.update_config(
            model_name="nemotron",
            config={"system_prompt": "Test"},
            created_by="test_user",
            description="Test desc",
        )

        history = storage_service.get_history("nemotron")
        assert len(history) == 1
        assert isinstance(history[0], PromptVersion)
        assert history[0].created_by == "test_user"
        assert history[0].description == "Test desc"

    def test_get_history_unsupported_model(self, storage_service: PromptStorageService):
        """Test get_history raises for unsupported model."""
        with pytest.raises(ValueError) as exc_info:
            storage_service.get_history("unknown")
        assert "Unsupported model" in str(exc_info.value)


# =============================================================================
# Test: get_version()
# =============================================================================


class TestGetVersion:
    """Tests for get_version() method."""

    def test_get_version_returns_specific_version(self, storage_service: PromptStorageService):
        """Test get_version retrieves a specific version."""
        storage_service.update_config(
            model_name="nemotron",
            config={"system_prompt": "Version 1"},
            created_by="user1",
        )
        storage_service.update_config(
            model_name="nemotron",
            config={"system_prompt": "Version 2"},
            created_by="user2",
        )

        version = storage_service.get_version("nemotron", 1)
        assert version is not None
        assert version.version == 1
        assert version.config["system_prompt"] == "Version 1"
        assert version.created_by == "user1"

    def test_get_version_returns_none_for_nonexistent(self, storage_service: PromptStorageService):
        """Test get_version returns None for nonexistent version."""
        version = storage_service.get_version("nemotron", 999)
        assert version is None

    def test_get_version_unsupported_model(self, storage_service: PromptStorageService):
        """Test get_version raises for unsupported model."""
        with pytest.raises(ValueError) as exc_info:
            storage_service.get_version("unknown", 1)
        assert "Unsupported model" in str(exc_info.value)


# =============================================================================
# Test: get_total_versions()
# =============================================================================


class TestGetTotalVersions:
    """Tests for get_total_versions() method."""

    def test_get_total_versions_returns_zero_when_empty(
        self, storage_service: PromptStorageService
    ):
        """Test get_total_versions returns 0 when no versions exist."""
        total = storage_service.get_total_versions("nemotron")
        assert total == 0

    def test_get_total_versions_counts_correctly(self, storage_service: PromptStorageService):
        """Test get_total_versions returns correct count."""
        for i in range(5):
            storage_service.update_config(
                model_name="nemotron",
                config={"system_prompt": f"V{i + 1}"},
                created_by="user",
            )

        total = storage_service.get_total_versions("nemotron")
        assert total == 5


# =============================================================================
# Test: restore_version()
# =============================================================================


class TestRestoreVersion:
    """Tests for restore_version() method."""

    def test_restore_version_creates_new_version(self, storage_service: PromptStorageService):
        """Test restore_version creates a new version with old config."""
        # Create initial versions
        storage_service.update_config(
            model_name="nemotron",
            config={"system_prompt": "Original"},
            created_by="user",
        )
        storage_service.update_config(
            model_name="nemotron",
            config={"system_prompt": "Modified"},
            created_by="user",
        )

        # Restore version 1
        result = storage_service.restore_version(
            model_name="nemotron",
            version=1,
            created_by="admin",
        )

        assert result.version == 3  # New version created
        assert result.config["system_prompt"] == "Original"

    def test_restore_version_with_custom_description(self, storage_service: PromptStorageService):
        """Test restore_version with custom description."""
        storage_service.update_config(
            model_name="nemotron",
            config={"system_prompt": "Test"},
            created_by="user",
        )

        result = storage_service.restore_version(
            model_name="nemotron",
            version=1,
            created_by="admin",
            description="Custom restore reason",
        )

        assert result.description == "Custom restore reason"

    def test_restore_version_default_description(self, storage_service: PromptStorageService):
        """Test restore_version generates default description."""
        storage_service.update_config(
            model_name="nemotron",
            config={"system_prompt": "Test"},
            created_by="user",
        )

        result = storage_service.restore_version(
            model_name="nemotron",
            version=1,
            created_by="admin",
        )

        assert "Restored from version 1" in result.description

    def test_restore_version_nonexistent_raises(self, storage_service: PromptStorageService):
        """Test restore_version raises ValueError for nonexistent version."""
        with pytest.raises(ValueError) as exc_info:
            storage_service.restore_version(
                model_name="nemotron",
                version=999,
                created_by="admin",
            )
        assert "not found" in str(exc_info.value)


# =============================================================================
# Test: get_all_configs()
# =============================================================================


class TestGetAllConfigs:
    """Tests for get_all_configs() method."""

    def test_get_all_configs_returns_all_models(self, storage_service: PromptStorageService):
        """Test get_all_configs returns configs for all supported models."""
        configs = storage_service.get_all_configs()
        assert len(configs) == len(SUPPORTED_MODELS)
        for model in SUPPORTED_MODELS:
            assert model in configs

    def test_get_all_configs_includes_metadata(self, storage_service: PromptStorageService):
        """Test get_all_configs includes metadata for each model."""
        configs = storage_service.get_all_configs()
        for model, data in configs.items():
            assert "config" in data or model in data  # Has config data


# =============================================================================
# Test: export_all()
# =============================================================================


class TestExportAll:
    """Tests for export_all() method."""

    def test_export_all_returns_export_format(self, storage_service: PromptStorageService):
        """Test export_all returns correct export format."""
        export_data = storage_service.export_all()

        assert "exported_at" in export_data
        assert "version" in export_data
        assert "prompts" in export_data

    def test_export_all_version_is_1_0(self, storage_service: PromptStorageService):
        """Test export_all uses version 1.0."""
        export_data = storage_service.export_all()
        assert export_data["version"] == "1.0"

    def test_export_all_includes_all_models(self, storage_service: PromptStorageService):
        """Test export_all includes all supported models."""
        export_data = storage_service.export_all()
        assert len(export_data["prompts"]) == len(SUPPORTED_MODELS)
        for model in SUPPORTED_MODELS:
            assert model in export_data["prompts"]

    def test_export_all_has_valid_timestamp(self, storage_service: PromptStorageService):
        """Test export_all includes valid ISO timestamp."""
        export_data = storage_service.export_all()
        # Should be parseable as ISO format
        timestamp = datetime.fromisoformat(export_data["exported_at"])
        assert isinstance(timestamp, datetime)


# =============================================================================
# Test: import_configs()
# =============================================================================


class TestImportConfigs:
    """Tests for import_configs() method."""

    def test_import_configs_imports_valid_models(self, storage_service: PromptStorageService):
        """Test import_configs imports valid model configurations."""
        configs = {
            "nemotron": {"system_prompt": "Imported prompt"},
            "florence2": {"vqa_queries": ["Test query"]},
        }

        result = storage_service.import_configs(configs, created_by="import_test")

        assert "nemotron" in result["imported"]
        assert "florence2" in result["imported"]

    def test_import_configs_skips_existing_without_overwrite(
        self, storage_service: PromptStorageService
    ):
        """Test import_configs skips existing configs when overwrite=False."""
        # Create existing config
        storage_service.update_config(
            model_name="nemotron",
            config={"system_prompt": "Existing"},
            created_by="user",
        )

        configs = {"nemotron": {"system_prompt": "New"}}
        result = storage_service.import_configs(configs, overwrite=False)

        assert "nemotron" in result["skipped"]

    def test_import_configs_overwrites_with_flag(self, storage_service: PromptStorageService):
        """Test import_configs overwrites existing when overwrite=True."""
        # Create existing config
        storage_service.update_config(
            model_name="nemotron",
            config={"system_prompt": "Existing"},
            created_by="user",
        )

        configs = {"nemotron": {"system_prompt": "New"}}
        result = storage_service.import_configs(configs, overwrite=True)

        assert "nemotron" in result["imported"]
        # Verify config was updated
        config = storage_service.get_config("nemotron")
        assert config["system_prompt"] == "New"

    def test_import_configs_reports_unsupported_models(self, storage_service: PromptStorageService):
        """Test import_configs reports unsupported model names as errors."""
        configs = {
            "nemotron": {"system_prompt": "Valid"},
            "unknown_model": {"data": "invalid"},
        }

        result = storage_service.import_configs(configs)

        assert "unknown_model" in result["errors"]

    def test_import_configs_returns_none_for_empty_results(
        self, storage_service: PromptStorageService
    ):
        """Test import_configs returns 'none' strings for empty result lists."""
        # Import with no configs
        result = storage_service.import_configs({})

        assert result["imported"] == "none"
        assert result["errors"] == "none"


# =============================================================================
# Test: validate_config()
# =============================================================================


class TestValidateConfig:
    """Tests for validate_config() method."""

    def test_validate_config_unsupported_model(self, storage_service: PromptStorageService):
        """Test validate_config returns error for unsupported model."""
        errors = storage_service.validate_config("unknown", {})
        assert len(errors) == 1
        assert "Unsupported model" in errors[0]

    # Nemotron validation tests
    def test_validate_nemotron_valid_config(self, storage_service: PromptStorageService):
        """Test validate_config passes for valid Nemotron config."""
        config = {
            "system_prompt": "You are a helpful assistant.",
            "temperature": 0.7,
        }
        errors = storage_service.validate_config("nemotron", config)
        assert errors == []

    def test_validate_nemotron_missing_system_prompt(self, storage_service: PromptStorageService):
        """Test validate_config catches missing system_prompt for Nemotron."""
        errors = storage_service.validate_config("nemotron", {})
        assert any("system_prompt" in e for e in errors)

    def test_validate_nemotron_system_prompt_not_string(
        self, storage_service: PromptStorageService
    ):
        """Test validate_config catches non-string system_prompt."""
        config = {"system_prompt": 123}
        errors = storage_service.validate_config("nemotron", config)
        assert any("must be a string" in e for e in errors)

    def test_validate_nemotron_temperature_out_of_range(
        self, storage_service: PromptStorageService
    ):
        """Test validate_config catches temperature out of range."""
        config = {"system_prompt": "Test", "temperature": 3.0}
        errors = storage_service.validate_config("nemotron", config)
        assert any("temperature" in e and "0" in e and "2" in e for e in errors)

    def test_validate_nemotron_temperature_valid_edge(self, storage_service: PromptStorageService):
        """Test validate_config accepts edge temperature values."""
        config = {"system_prompt": "Test", "temperature": 0}
        errors = storage_service.validate_config("nemotron", config)
        assert errors == []

        config = {"system_prompt": "Test", "temperature": 2}
        errors = storage_service.validate_config("nemotron", config)
        assert errors == []

    # Florence2 validation tests
    def test_validate_florence2_valid_config(self, storage_service: PromptStorageService):
        """Test validate_config passes for valid Florence-2 config."""
        config = {"vqa_queries": ["What is this?", "Describe the scene."]}
        errors = storage_service.validate_config("florence2", config)
        assert errors == []

    def test_validate_florence2_missing_queries(self, storage_service: PromptStorageService):
        """Test validate_config catches missing vqa_queries for Florence-2."""
        errors = storage_service.validate_config("florence2", {})
        assert any("vqa_queries" in e for e in errors)

    def test_validate_florence2_empty_queries(self, storage_service: PromptStorageService):
        """Test validate_config catches empty vqa_queries list."""
        config = {"vqa_queries": []}
        errors = storage_service.validate_config("florence2", config)
        assert any("at least one" in e for e in errors)

    def test_validate_florence2_queries_not_list(self, storage_service: PromptStorageService):
        """Test validate_config catches non-list vqa_queries."""
        config = {"vqa_queries": "not a list"}
        errors = storage_service.validate_config("florence2", config)
        assert any("must be a list" in e for e in errors)

    # YOLO-World validation tests
    def test_validate_yolo_world_valid_config(self, storage_service: PromptStorageService):
        """Test validate_config passes for valid YOLO-World config."""
        config = {
            "object_classes": ["person", "car"],
            "confidence_threshold": 0.5,
        }
        errors = storage_service.validate_config("yolo_world", config)
        assert errors == []

    def test_validate_yolo_world_missing_classes(self, storage_service: PromptStorageService):
        """Test validate_config catches missing object_classes for YOLO-World."""
        config = {"confidence_threshold": 0.5}
        errors = storage_service.validate_config("yolo_world", config)
        assert any("object_classes" in e for e in errors)

    def test_validate_yolo_world_threshold_out_of_range(
        self, storage_service: PromptStorageService
    ):
        """Test validate_config catches confidence_threshold out of range."""
        config = {"object_classes": ["person"], "confidence_threshold": 1.5}
        errors = storage_service.validate_config("yolo_world", config)
        assert any("confidence_threshold" in e for e in errors)

    # X-CLIP validation tests
    def test_validate_xclip_valid_config(self, storage_service: PromptStorageService):
        """Test validate_config passes for valid X-CLIP config."""
        config = {"action_classes": ["walking", "running"]}
        errors = storage_service.validate_config("xclip", config)
        assert errors == []

    def test_validate_xclip_missing_action_classes(self, storage_service: PromptStorageService):
        """Test validate_config catches missing action_classes for X-CLIP."""
        errors = storage_service.validate_config("xclip", {})
        assert any("action_classes" in e for e in errors)

    # Fashion-CLIP validation tests
    def test_validate_fashion_clip_valid_config(self, storage_service: PromptStorageService):
        """Test validate_config passes for valid Fashion-CLIP config."""
        config = {"clothing_categories": ["casual", "formal"]}
        errors = storage_service.validate_config("fashion_clip", config)
        assert errors == []

    def test_validate_fashion_clip_missing_categories(self, storage_service: PromptStorageService):
        """Test validate_config catches missing clothing_categories."""
        errors = storage_service.validate_config("fashion_clip", {})
        assert any("clothing_categories" in e for e in errors)


# =============================================================================
# Test: run_mock_test()
# =============================================================================


class TestRunMockTest:
    """Tests for run_mock_test() method."""

    def test_run_mock_test_returns_result_format(self, storage_service: PromptStorageService):
        """Test run_mock_test returns correct result format."""
        config = {"system_prompt": "Test prompt", "temperature": 0.7}
        result = storage_service.run_mock_test(
            model_name="nemotron",
            config=config,
            event_id=123,
        )

        assert "before" in result
        assert "after" in result
        assert "improved" in result
        assert "inference_time_ms" in result

    def test_run_mock_test_before_after_structure(self, storage_service: PromptStorageService):
        """Test run_mock_test before/after have correct structure."""
        config = {"system_prompt": "Test"}
        result = storage_service.run_mock_test(
            model_name="nemotron",
            config=config,
            event_id=1,
        )

        for key in ["before", "after"]:
            assert "score" in result[key]
            assert "risk_level" in result[key]
            assert "summary" in result[key]

    def test_run_mock_test_risk_levels_valid(self, storage_service: PromptStorageService):
        """Test run_mock_test returns valid risk levels."""
        config = {"system_prompt": "Test"}
        result = storage_service.run_mock_test(
            model_name="nemotron",
            config=config,
            event_id=1,
        )

        valid_levels = {"low", "medium", "high", "critical"}
        assert result["before"]["risk_level"] in valid_levels
        assert result["after"]["risk_level"] in valid_levels

    def test_run_mock_test_improved_is_boolean(self, storage_service: PromptStorageService):
        """Test run_mock_test improved field is boolean."""
        config = {"system_prompt": "Test"}
        result = storage_service.run_mock_test(
            model_name="nemotron",
            config=config,
            event_id=1,
        )
        assert isinstance(result["improved"], bool)

    def test_run_mock_test_inference_time_positive(self, storage_service: PromptStorageService):
        """Test run_mock_test inference_time_ms is positive."""
        config = {"system_prompt": "Test"}
        result = storage_service.run_mock_test(
            model_name="nemotron",
            config=config,
            event_id=1,
        )
        assert result["inference_time_ms"] >= 0

    def test_run_mock_test_invalid_config_raises(self, storage_service: PromptStorageService):
        """Test run_mock_test raises ValueError for invalid config."""
        config = {}  # Missing system_prompt for nemotron
        with pytest.raises(ValueError) as exc_info:
            storage_service.run_mock_test(
                model_name="nemotron",
                config=config,
                event_id=1,
            )
        assert "Invalid configuration" in str(exc_info.value)

    def test_run_mock_test_summary_includes_model_name(self, storage_service: PromptStorageService):
        """Test run_mock_test summary includes model name."""
        config = {"system_prompt": "Test"}
        result = storage_service.run_mock_test(
            model_name="nemotron",
            config=config,
            event_id=42,
        )
        assert "nemotron" in result["before"]["summary"]
        assert "42" in result["before"]["summary"]


# =============================================================================
# Test: Singleton Pattern
# =============================================================================


class TestSingletonPattern:
    """Tests for the singleton pattern."""

    def test_get_prompt_storage_returns_instance(self):
        """Test get_prompt_storage returns a PromptStorageService instance."""
        service = get_prompt_storage()
        assert isinstance(service, PromptStorageService)

    def test_get_prompt_storage_returns_same_instance(self):
        """Test get_prompt_storage returns the same instance on repeated calls."""
        service1 = get_prompt_storage()
        service2 = get_prompt_storage()
        assert service1 is service2

    def test_reset_prompt_storage_clears_singleton(self):
        """Test reset_prompt_storage clears the singleton."""
        service1 = get_prompt_storage()
        reset_prompt_storage()
        service2 = get_prompt_storage()
        assert service1 is not service2


# =============================================================================
# Test: Private Helper Methods
# =============================================================================


class TestPrivateHelpers:
    """Tests for private helper methods."""

    def test_get_model_dir_returns_correct_path(
        self, storage_service: PromptStorageService, temp_storage_dir: Path
    ):
        """Test _get_model_dir returns correct directory path."""
        model_dir = storage_service._get_model_dir("nemotron")
        assert model_dir == temp_storage_dir / "nemotron"

    def test_get_model_dir_raises_for_invalid(self, storage_service: PromptStorageService):
        """Test _get_model_dir raises ValueError for invalid model."""
        with pytest.raises(ValueError):
            storage_service._get_model_dir("invalid_model")

    def test_get_current_path(self, storage_service: PromptStorageService, temp_storage_dir: Path):
        """Test _get_current_path returns correct path."""
        path = storage_service._get_current_path("nemotron")
        assert path == temp_storage_dir / "nemotron" / "current.json"

    def test_get_history_dir(self, storage_service: PromptStorageService, temp_storage_dir: Path):
        """Test _get_history_dir returns correct path."""
        path = storage_service._get_history_dir("nemotron")
        assert path == temp_storage_dir / "nemotron" / "history"

    def test_read_json_returns_none_for_missing_file(
        self, storage_service: PromptStorageService, temp_storage_dir: Path
    ):
        """Test _read_json returns None for missing file."""
        result = storage_service._read_json(temp_storage_dir / "nonexistent.json")
        assert result is None

    def test_read_json_returns_parsed_data(
        self, storage_service: PromptStorageService, temp_storage_dir: Path
    ):
        """Test _read_json returns parsed JSON data."""
        test_file = temp_storage_dir / "test.json"
        test_file.write_text('{"key": "value"}')
        result = storage_service._read_json(test_file)
        assert result == {"key": "value"}

    def test_read_json_handles_invalid_json(
        self, storage_service: PromptStorageService, temp_storage_dir: Path
    ):
        """Test _read_json handles invalid JSON gracefully."""
        test_file = temp_storage_dir / "bad.json"
        test_file.write_text("not valid json")
        result = storage_service._read_json(test_file)
        assert result is None

    def test_write_json_creates_file(
        self, storage_service: PromptStorageService, temp_storage_dir: Path
    ):
        """Test _write_json creates file with correct content."""
        test_file = temp_storage_dir / "output.json"
        data = {"test": "data", "number": 42}
        storage_service._write_json(test_file, data)

        assert test_file.exists()
        content = json.loads(test_file.read_text())
        assert content["test"] == "data"
        assert content["number"] == 42

    def test_write_json_creates_parent_directories(
        self, storage_service: PromptStorageService, temp_storage_dir: Path
    ):
        """Test _write_json creates parent directories if needed."""
        nested_path = temp_storage_dir / "nested" / "dir" / "file.json"
        storage_service._write_json(nested_path, {"key": "value"})
        assert nested_path.exists()

    def test_get_next_version_returns_1_for_empty(self, storage_service: PromptStorageService):
        """Test _get_next_version returns 1 when no versions exist."""
        version = storage_service._get_next_version("nemotron")
        assert version == 1

    def test_get_next_version_increments(self, storage_service: PromptStorageService):
        """Test _get_next_version increments from existing versions."""
        storage_service.update_config(
            model_name="nemotron",
            config={"system_prompt": "Test"},
            created_by="user",
        )
        version = storage_service._get_next_version("nemotron")
        assert version == 2


# =============================================================================
# Test: Edge Cases and Error Handling
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_config(self, storage_service: PromptStorageService):
        """Test handling of empty configuration."""
        result = storage_service.update_config(
            model_name="nemotron",
            config={},
            created_by="user",
        )
        assert result.config == {}

    def test_large_config(self, storage_service: PromptStorageService):
        """Test handling of large configuration."""
        large_prompt = "A" * 100000  # 100KB prompt
        config = {"system_prompt": large_prompt}
        result = storage_service.update_config(
            model_name="nemotron",
            config=config,
            created_by="user",
        )
        assert result.config["system_prompt"] == large_prompt

    def test_special_characters_in_description(self, storage_service: PromptStorageService):
        """Test handling of special characters in description."""
        result = storage_service.update_config(
            model_name="nemotron",
            config={"system_prompt": "Test"},
            created_by="user",
            description="Test with 'quotes' and \"double quotes\" and\nnewlines",
        )
        assert result.description is not None
        assert "quotes" in result.description

    def test_unicode_in_config(self, storage_service: PromptStorageService):
        """Test handling of unicode characters in config."""
        config = {"system_prompt": "Test with emojis: ", "data": ""}
        storage_service.update_config(
            model_name="nemotron",
            config=config,
            created_by="user",
        )
        # Verify it can be read back
        retrieved = storage_service.get_config("nemotron")
        assert "" in retrieved["system_prompt"]

    def test_concurrent_version_creation(self, temp_storage_dir: Path):
        """Test version numbers are unique under concurrent updates."""
        service = PromptStorageService(storage_path=temp_storage_dir)

        # Create multiple versions rapidly
        versions = []
        for i in range(10):
            result = service.update_config(
                model_name="nemotron",
                config={"system_prompt": f"Version {i}"},
                created_by="user",
            )
            versions.append(result.version)

        # All versions should be unique
        assert len(versions) == len(set(versions))
        # Versions should be sequential
        assert versions == list(range(1, 11))


# =============================================================================
# Test: File System Error Handling
# =============================================================================


class TestFileSystemErrors:
    """Tests for file system error handling."""

    def test_read_json_handles_os_error(
        self, storage_service: PromptStorageService, temp_storage_dir: Path
    ):
        """Test _read_json handles OSError gracefully."""
        test_file = temp_storage_dir / "test.json"
        test_file.write_text('{"key": "value"}')

        # Mock open to raise OSError
        with patch("builtins.open", side_effect=OSError("Permission denied")):
            result = storage_service._read_json(test_file)
            assert result is None

    def test_history_with_malformed_version_files(self, temp_storage_dir: Path):
        """Test get_history handles malformed version files."""
        service = PromptStorageService(storage_path=temp_storage_dir)

        # Create a valid version
        service.update_config(
            model_name="nemotron",
            config={"system_prompt": "Test"},
            created_by="user",
        )

        # Create a malformed version file
        bad_file = temp_storage_dir / "nemotron" / "history" / "v2.json"
        bad_file.write_text("invalid json")

        # Should still return valid versions, skipping malformed ones
        history = service.get_history("nemotron")
        assert len(history) >= 1


# =============================================================================
# Test: Validation Helper Methods
# =============================================================================


class TestValidationHelpers:
    """Tests for validation helper methods."""

    def test_validate_required_string_missing(self, storage_service: PromptStorageService):
        """Test _validate_required_string catches missing field."""
        errors: list[str] = []
        storage_service._validate_required_string({}, "field_name", errors)
        assert any("Missing required field" in e for e in errors)

    def test_validate_required_string_wrong_type(self, storage_service: PromptStorageService):
        """Test _validate_required_string catches wrong type."""
        errors: list[str] = []
        storage_service._validate_required_string({"field_name": 123}, "field_name", errors)
        assert any("must be a string" in e for e in errors)

    def test_validate_required_string_valid(self, storage_service: PromptStorageService):
        """Test _validate_required_string passes for valid string."""
        errors: list[str] = []
        storage_service._validate_required_string({"field_name": "value"}, "field_name", errors)
        assert errors == []

    def test_validate_required_list_missing(self, storage_service: PromptStorageService):
        """Test _validate_required_list catches missing field."""
        errors: list[str] = []
        storage_service._validate_required_list({}, "items", "item", errors)
        assert any("Missing required field" in e for e in errors)

    def test_validate_required_list_wrong_type(self, storage_service: PromptStorageService):
        """Test _validate_required_list catches wrong type."""
        errors: list[str] = []
        storage_service._validate_required_list({"items": "not a list"}, "items", "item", errors)
        assert any("must be a list" in e for e in errors)

    def test_validate_required_list_empty(self, storage_service: PromptStorageService):
        """Test _validate_required_list catches empty list."""
        errors: list[str] = []
        storage_service._validate_required_list({"items": []}, "items", "item", errors)
        assert any("at least one" in e for e in errors)

    def test_validate_required_list_valid(self, storage_service: PromptStorageService):
        """Test _validate_required_list passes for valid list."""
        errors: list[str] = []
        storage_service._validate_required_list({"items": ["a", "b"]}, "items", "item", errors)
        assert errors == []

    def test_validate_number_range_missing_ok(self, storage_service: PromptStorageService):
        """Test _validate_number_range allows missing optional field."""
        errors: list[str] = []
        storage_service._validate_number_range({}, "value", 0, 1, errors)
        assert errors == []

    def test_validate_number_range_below_min(self, storage_service: PromptStorageService):
        """Test _validate_number_range catches value below minimum."""
        errors: list[str] = []
        storage_service._validate_number_range({"value": -1}, "value", 0, 1, errors)
        assert len(errors) == 1

    def test_validate_number_range_above_max(self, storage_service: PromptStorageService):
        """Test _validate_number_range catches value above maximum."""
        errors: list[str] = []
        storage_service._validate_number_range({"value": 2}, "value", 0, 1, errors)
        assert len(errors) == 1

    def test_validate_number_range_wrong_type(self, storage_service: PromptStorageService):
        """Test _validate_number_range catches non-numeric value."""
        errors: list[str] = []
        storage_service._validate_number_range({"value": "not a number"}, "value", 0, 1, errors)
        assert len(errors) == 1

    def test_validate_number_range_valid(self, storage_service: PromptStorageService):
        """Test _validate_number_range passes for valid number."""
        errors: list[str] = []
        storage_service._validate_number_range({"value": 0.5}, "value", 0, 1, errors)
        assert errors == []


# =============================================================================
# Test: Risk Level Helper in run_mock_test
# =============================================================================


class TestRiskLevelMapping:
    """Tests for risk level score-to-level mapping in run_mock_test."""

    def test_score_to_level_low(self, storage_service: PromptStorageService):
        """Test low risk level for scores under 30."""
        # Use mock to control random scores
        with (
            patch("random.randint", return_value=15),
            patch("random.uniform", return_value=0.1),
        ):
            result = storage_service.run_mock_test(
                model_name="nemotron",
                config={"system_prompt": "Test"},
                event_id=1,
            )
            assert result["before"]["risk_level"] == "low"

    def test_score_to_level_medium(self, storage_service: PromptStorageService):
        """Test medium risk level for scores 30-59."""
        with (
            patch("random.randint", return_value=45),
            patch("random.uniform", return_value=0.1),
        ):
            result = storage_service.run_mock_test(
                model_name="nemotron",
                config={"system_prompt": "Test"},
                event_id=1,
            )
            assert result["before"]["risk_level"] == "medium"

    def test_score_to_level_high(self, storage_service: PromptStorageService):
        """Test high risk level for scores 60-84."""
        with (
            patch("random.randint", return_value=75),
            patch("random.uniform", return_value=0.1),
        ):
            result = storage_service.run_mock_test(
                model_name="nemotron",
                config={"system_prompt": "Test"},
                event_id=1,
            )
            assert result["before"]["risk_level"] == "high"

    def test_score_to_level_critical(self, storage_service: PromptStorageService):
        """Test critical risk level for scores 85+."""
        with (
            patch("random.randint", return_value=90),
            patch("random.uniform", return_value=0.1),
        ):
            result = storage_service.run_mock_test(
                model_name="nemotron",
                config={"system_prompt": "Test"},
                event_id=1,
            )
            assert result["before"]["risk_level"] == "critical"


# =============================================================================
# Test: Initialize Default Config
# =============================================================================


class TestInitializeDefaultConfig:
    """Tests for _initialize_default_config method."""

    def test_initialize_default_config_creates_file(
        self, storage_service: PromptStorageService, temp_storage_dir: Path
    ):
        """Test _initialize_default_config creates the config file."""
        # Call internal method directly
        config = storage_service._initialize_default_config("nemotron")

        # Should have returned default config
        assert "system_prompt" in config

        # Should have created current.json
        assert (temp_storage_dir / "nemotron" / "current.json").exists()

    def test_initialize_default_config_creates_history(
        self, storage_service: PromptStorageService, temp_storage_dir: Path
    ):
        """Test _initialize_default_config creates history entry."""
        storage_service._initialize_default_config("florence2")

        # Should have created history entry
        history_dir = temp_storage_dir / "florence2" / "history"
        history_files = list(history_dir.glob("v*.json"))
        assert len(history_files) == 1


# =============================================================================
# Test: Additional Edge Cases for 100% Coverage
# =============================================================================


class TestHistoryDirNotExists:
    """Tests for when history directory doesn't exist."""

    def test_get_next_version_no_history_dir(self, temp_storage_dir: Path):
        """Test _get_next_version returns 1 when history dir doesn't exist."""
        # Create service without any model directories
        service = PromptStorageService(storage_path=temp_storage_dir)

        # Remove the history directory manually
        import shutil

        history_dir = temp_storage_dir / "nemotron" / "history"
        if history_dir.exists():
            shutil.rmtree(history_dir)

        # Should return 1
        version = service._get_next_version("nemotron")
        assert version == 1

    def test_get_history_no_history_dir(self, temp_storage_dir: Path):
        """Test get_history returns empty list when history dir doesn't exist."""
        service = PromptStorageService(storage_path=temp_storage_dir)

        # Remove the history directory manually
        import shutil

        history_dir = temp_storage_dir / "nemotron" / "history"
        if history_dir.exists():
            shutil.rmtree(history_dir)

        # Should return empty list
        history = service.get_history("nemotron")
        assert history == []

    def test_get_total_versions_no_history_dir(self, temp_storage_dir: Path):
        """Test get_total_versions returns 0 when history dir doesn't exist."""
        service = PromptStorageService(storage_path=temp_storage_dir)

        # Remove the history directory manually
        import shutil

        history_dir = temp_storage_dir / "nemotron" / "history"
        if history_dir.exists():
            shutil.rmtree(history_dir)

        # Should return 0
        total = service.get_total_versions("nemotron")
        assert total == 0


class TestInvalidVersionFilenames:
    """Tests for handling invalid version filename formats."""

    def test_get_next_version_ignores_invalid_filenames(self, temp_storage_dir: Path):
        """Test _get_next_version ignores malformed version filenames."""
        service = PromptStorageService(storage_path=temp_storage_dir)

        # Create a valid version first
        service.update_config(
            model_name="nemotron",
            config={"system_prompt": "Test"},
            created_by="user",
        )

        # Create invalid version files
        history_dir = temp_storage_dir / "nemotron" / "history"
        (history_dir / "vnotanumber.json").write_text('{"config": {}}')
        (history_dir / "invalid.json").write_text('{"config": {}}')
        (history_dir / "v.json").write_text('{"config": {}}')

        # Should still work, ignoring invalid files
        version = service._get_next_version("nemotron")
        assert version == 2  # v1 exists, next should be 2

    def test_get_history_ignores_invalid_filenames(self, temp_storage_dir: Path):
        """Test get_history ignores malformed version filenames."""
        service = PromptStorageService(storage_path=temp_storage_dir)

        # Create a valid version
        service.update_config(
            model_name="nemotron",
            config={"system_prompt": "Test"},
            created_by="user",
        )

        # Create invalid version files
        history_dir = temp_storage_dir / "nemotron" / "history"
        (history_dir / "vxyz.json").write_text('{"config": {}}')
        (history_dir / "notversion.json").write_text('{"config": {}}')

        # Should only return valid versions
        history = service.get_history("nemotron")
        assert len(history) == 1
        assert history[0].version == 1


class TestImportConfigsExceptionHandling:
    """Tests for exception handling in import_configs."""

    def test_import_configs_handles_exception_during_update(self, temp_storage_dir: Path):
        """Test import_configs catches and reports exceptions during import."""
        service = PromptStorageService(storage_path=temp_storage_dir)

        # Create a config that will cause an exception during update
        # by mocking the update_config to raise an exception
        configs = {"nemotron": {"system_prompt": "Test"}}

        original_update = service.update_config

        def failing_update(*args, **kwargs):
            if kwargs.get("model_name") == "nemotron" or (args and args[0] == "nemotron"):
                raise RuntimeError("Simulated failure")
            return original_update(*args, **kwargs)

        service.update_config = failing_update

        result = service.import_configs(configs, overwrite=True)

        # Should report the error
        assert "nemotron" in result["errors"]
        assert "Simulated failure" in result["errors"]

    def test_import_configs_handles_partial_failure(self, temp_storage_dir: Path):
        """Test import_configs handles partial failures gracefully."""
        service = PromptStorageService(storage_path=temp_storage_dir)

        configs = {
            "florence2": {"vqa_queries": ["Test"]},  # This should work
            "invalid_model": {"data": "test"},  # This will be reported as unsupported
        }

        result = service.import_configs(configs, overwrite=True)

        # Florence2 should be imported
        assert "florence2" in result["imported"]
        # Invalid model should be in errors
        assert "invalid_model" in result["errors"]
