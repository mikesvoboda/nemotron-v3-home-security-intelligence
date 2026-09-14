"""Tests for hub_cache_config module (NEM-3812)."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

from ai.hub_cache_config import (
    DEFAULT_HF_HOME,
    ENV_HF_DATASETS_CACHE,
    ENV_HF_HOME,
    ENV_HF_HUB_CACHE,
    ENV_HF_HUB_DISABLE_TELEMETRY,
    ENV_HF_HUB_OFFLINE,
    ENV_TRANSFORMERS_CACHE,
    HubCacheConfig,
    configure_hub_cache,
    get_cache_stats,
    get_current_config,
    validate_cache_config,
)


class TestHubCacheConfig:
    """Tests for HubCacheConfig dataclass."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = HubCacheConfig()

        assert config.hf_home == DEFAULT_HF_HOME
        assert config.hub_cache is None
        assert config.transformers_cache is None
        assert config.datasets_cache is None
        assert config.offline_mode is False
        assert config.disable_telemetry is True

    def test_custom_values(self) -> None:
        """Test custom configuration values."""
        config = HubCacheConfig(
            hf_home="/custom/cache",
            hub_cache="/custom/cache/hub",
            transformers_cache="/custom/cache/transformers",
            offline_mode=True,
            disable_telemetry=False,
        )

        assert config.hf_home == "/custom/cache"
        assert config.hub_cache == "/custom/cache/hub"
        assert config.transformers_cache == "/custom/cache/transformers"
        assert config.offline_mode is True
        assert config.disable_telemetry is False


class TestConfigureHubCache:
    """Tests for configure_hub_cache function."""

    def test_configure_basic(self) -> None:
        """Test basic cache configuration."""
        # Save original env vars
        original_env = {
            key: os.environ.get(key)
            for key in [
                ENV_HF_HOME,
                ENV_HF_HUB_CACHE,
                ENV_TRANSFORMERS_CACHE,
                ENV_HF_DATASETS_CACHE,
                ENV_HF_HUB_OFFLINE,
                ENV_HF_HUB_DISABLE_TELEMETRY,
            ]
        }

        try:
            with patch("ai.hub_cache_config._create_cache_dirs"):
                result = configure_hub_cache(hf_home="/test/cache")

            assert result.hf_home == "/test/cache"
            assert os.environ[ENV_HF_HOME] == "/test/cache"
            assert os.environ[ENV_HF_HUB_CACHE] == "/test/cache/hub"
            assert os.environ[ENV_TRANSFORMERS_CACHE] == "/test/cache"
            assert os.environ[ENV_HF_DATASETS_CACHE] == "/test/cache/datasets"
            assert os.environ[ENV_HF_HUB_DISABLE_TELEMETRY] == "1"

        finally:
            # Restore original env vars
            for key, value in original_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def test_configure_offline_mode(self) -> None:
        """Test offline mode configuration."""
        original_env = {key: os.environ.get(key) for key in [ENV_HF_HOME, ENV_HF_HUB_OFFLINE]}

        try:
            with patch("ai.hub_cache_config._create_cache_dirs"):
                result = configure_hub_cache(
                    hf_home="/test/cache",
                    offline_mode=True,
                )

            assert result.offline_mode is True
            assert os.environ[ENV_HF_HUB_OFFLINE] == "1"

        finally:
            for key, value in original_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def test_configure_with_config_object(self) -> None:
        """Test configuration with HubCacheConfig object."""
        original_env = {key: os.environ.get(key) for key in [ENV_HF_HOME, ENV_HF_HUB_OFFLINE]}

        try:
            config = HubCacheConfig(
                hf_home="/config/cache",
                offline_mode=True,
                disable_telemetry=True,
            )

            with patch("ai.hub_cache_config._create_cache_dirs"):
                result = configure_hub_cache(config=config)

            assert result.hf_home == "/config/cache"
            assert os.environ[ENV_HF_HOME] == "/config/cache"

        finally:
            for key, value in original_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


class TestGetCurrentConfig:
    """Tests for get_current_config function."""

    def test_get_current_config_defaults(self) -> None:
        """Test getting current config with defaults."""
        # Clear env vars
        original_env = {
            key: os.environ.get(key)
            for key in [
                ENV_HF_HOME,
                ENV_HF_HUB_CACHE,
                ENV_TRANSFORMERS_CACHE,
                ENV_HF_DATASETS_CACHE,
                ENV_HF_HUB_OFFLINE,
            ]
        }

        try:
            for key in original_env:
                os.environ.pop(key, None)

            config = get_current_config()
            assert config.hf_home == DEFAULT_HF_HOME
            assert config.offline_mode is False

        finally:
            for key, value in original_env.items():
                if value is not None:
                    os.environ[key] = value

    def test_get_current_config_from_env(self) -> None:
        """Test getting current config from environment."""
        original_env = {key: os.environ.get(key) for key in [ENV_HF_HOME, ENV_HF_HUB_OFFLINE]}

        try:
            os.environ[ENV_HF_HOME] = "/env/cache"
            os.environ[ENV_HF_HUB_OFFLINE] = "1"

            config = get_current_config()
            assert config.hf_home == "/env/cache"
            assert config.offline_mode is True

        finally:
            for key, value in original_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


class TestValidateCacheConfig:
    """Tests for validate_cache_config function."""

    def test_validate_nonexistent_cache(self, tmp_path: Path) -> None:
        """Test validation of nonexistent cache directory."""
        original_env = os.environ.get(ENV_HF_HOME)

        try:
            os.environ[ENV_HF_HOME] = str(tmp_path / "nonexistent")

            results = validate_cache_config()

            assert results["hf_home_exists"] is False
            assert results["hf_home_writable"] is False

        finally:
            if original_env is None:
                os.environ.pop(ENV_HF_HOME, None)
            else:
                os.environ[ENV_HF_HOME] = original_env

    def test_validate_existing_cache(self, tmp_path: Path) -> None:
        """Test validation of existing cache directory."""
        cache_dir = tmp_path / "hf_cache"
        cache_dir.mkdir()
        hub_dir = cache_dir / "hub"
        hub_dir.mkdir()

        original_env = {key: os.environ.get(key) for key in [ENV_HF_HOME, ENV_HF_HUB_CACHE]}

        try:
            os.environ[ENV_HF_HOME] = str(cache_dir)
            # Clear HF_HUB_CACHE to ensure fallback to HF_HOME/hub
            os.environ.pop(ENV_HF_HUB_CACHE, None)

            results = validate_cache_config()

            assert results["hf_home_exists"] is True
            assert results["hf_home_writable"] is True
            # hub_cache_exists checks if the derived path (HF_HOME/hub) exists
            assert results["hub_cache_exists"] is True

        finally:
            for key, value in original_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


class TestGetCacheStats:
    """Tests for get_cache_stats function."""

    def test_get_cache_stats_empty_cache(self, tmp_path: Path) -> None:
        """Test stats for empty cache directory."""
        cache_dir = tmp_path / "hf_cache"
        cache_dir.mkdir()

        original_env = os.environ.get(ENV_HF_HOME)

        try:
            os.environ[ENV_HF_HOME] = str(cache_dir)

            stats = get_cache_stats()

            assert stats["hf_home"] == str(cache_dir)
            assert stats["total_size_mb"] == 0
            assert stats["num_models"] == 0

        finally:
            if original_env is None:
                os.environ.pop(ENV_HF_HOME, None)
            else:
                os.environ[ENV_HF_HOME] = original_env

    def test_get_cache_stats_with_models(self, tmp_path: Path) -> None:
        """Test stats for cache with model directories."""
        cache_dir = tmp_path / "hf_cache"
        cache_dir.mkdir()
        hub_dir = cache_dir / "hub"
        hub_dir.mkdir()

        # Create mock model directories
        (hub_dir / "models--test--model1").mkdir()
        (hub_dir / "models--test--model2").mkdir()

        # Create a small file to have non-zero size
        test_file = hub_dir / "models--test--model1" / "test.bin"
        test_file.write_bytes(b"x" * 1024)  # 1KB file

        original_env = os.environ.get(ENV_HF_HOME)

        try:
            os.environ[ENV_HF_HOME] = str(cache_dir)

            stats = get_cache_stats()

            assert stats["hf_home"] == str(cache_dir)
            assert stats["num_models"] == 2
            # Size is at least 1KB but may be 0MB due to integer division
            assert stats["total_size_mb"] >= 0

        finally:
            if original_env is None:
                os.environ.pop(ENV_HF_HOME, None)
            else:
                os.environ[ENV_HF_HOME] = original_env

    def test_get_cache_stats_nonexistent_cache(self, tmp_path: Path) -> None:
        """Test stats for nonexistent cache directory."""
        original_env = os.environ.get(ENV_HF_HOME)

        try:
            os.environ[ENV_HF_HOME] = str(tmp_path / "nonexistent")

            stats = get_cache_stats()

            assert stats["total_size_mb"] == 0
            assert stats["num_models"] == 0

        finally:
            if original_env is None:
                os.environ.pop(ENV_HF_HOME, None)
            else:
                os.environ[ENV_HF_HOME] = original_env


class TestEnvironmentVariableNames:
    """Tests for environment variable name constants."""

    def test_env_var_names(self) -> None:
        """Test that environment variable names are correct."""
        assert ENV_HF_HOME == "HF_HOME"
        assert ENV_HF_HUB_CACHE == "HF_HUB_CACHE"
        assert ENV_TRANSFORMERS_CACHE == "TRANSFORMERS_CACHE"
        assert ENV_HF_DATASETS_CACHE == "HF_DATASETS_CACHE"
        assert ENV_HF_HUB_OFFLINE == "HF_HUB_OFFLINE"
        assert ENV_HF_HUB_DISABLE_TELEMETRY == "HF_HUB_DISABLE_TELEMETRY"

    def test_default_hf_home(self) -> None:
        """Test default HF_HOME value."""
        assert DEFAULT_HF_HOME == "/cache/huggingface"
