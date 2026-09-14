"""Unit tests for Redis memory and HyperLogLog configuration settings (NEM-3414, NEM-3416).

Tests the configuration validation for:
- redis_memory_limit_mb
- redis_memory_policy
- redis_memory_apply_on_startup
- hll_ttl_seconds
- hll_key_prefix
"""

import os
from unittest.mock import patch

import pytest

from backend.core.config import Settings


class TestRedisMemoryPolicyValidation:
    """Tests for redis_memory_policy validator."""

    def test_valid_volatile_lru(self):
        """Test volatile-lru is valid."""
        with patch.dict(os.environ, {"REDIS_MEMORY_POLICY": "volatile-lru"}, clear=False):
            settings = Settings()
            assert settings.redis_memory_policy == "volatile-lru"

    def test_valid_allkeys_lru(self):
        """Test allkeys-lru is valid."""
        with patch.dict(os.environ, {"REDIS_MEMORY_POLICY": "allkeys-lru"}, clear=False):
            settings = Settings()
            assert settings.redis_memory_policy == "allkeys-lru"

    def test_valid_volatile_ttl(self):
        """Test volatile-ttl is valid."""
        with patch.dict(os.environ, {"REDIS_MEMORY_POLICY": "volatile-ttl"}, clear=False):
            settings = Settings()
            assert settings.redis_memory_policy == "volatile-ttl"

    def test_valid_volatile_random(self):
        """Test volatile-random is valid."""
        with patch.dict(os.environ, {"REDIS_MEMORY_POLICY": "volatile-random"}, clear=False):
            settings = Settings()
            assert settings.redis_memory_policy == "volatile-random"

    def test_valid_allkeys_random(self):
        """Test allkeys-random is valid."""
        with patch.dict(os.environ, {"REDIS_MEMORY_POLICY": "allkeys-random"}, clear=False):
            settings = Settings()
            assert settings.redis_memory_policy == "allkeys-random"

    def test_valid_noeviction(self):
        """Test noeviction is valid."""
        with patch.dict(os.environ, {"REDIS_MEMORY_POLICY": "noeviction"}, clear=False):
            settings = Settings()
            assert settings.redis_memory_policy == "noeviction"

    def test_case_insensitive(self):
        """Test policy validation is case insensitive."""
        with patch.dict(os.environ, {"REDIS_MEMORY_POLICY": "VOLATILE-LRU"}, clear=False):
            settings = Settings()
            assert settings.redis_memory_policy == "volatile-lru"

    def test_alias_lru_maps_to_volatile_lru(self):
        """Test 'lru' alias maps to 'volatile-lru'."""
        with patch.dict(os.environ, {"REDIS_MEMORY_POLICY": "lru"}, clear=False):
            settings = Settings()
            assert settings.redis_memory_policy == "volatile-lru"

    def test_alias_ttl_maps_to_volatile_ttl(self):
        """Test 'ttl' alias maps to 'volatile-ttl'."""
        with patch.dict(os.environ, {"REDIS_MEMORY_POLICY": "ttl"}, clear=False):
            settings = Settings()
            assert settings.redis_memory_policy == "volatile-ttl"

    def test_alias_random_maps_to_volatile_random(self):
        """Test 'random' alias maps to 'volatile-random'."""
        with patch.dict(os.environ, {"REDIS_MEMORY_POLICY": "random"}, clear=False):
            settings = Settings()
            assert settings.redis_memory_policy == "volatile-random"

    def test_invalid_policy_raises_error(self):
        """Test invalid policy raises ValueError."""
        with patch.dict(os.environ, {"REDIS_MEMORY_POLICY": "invalid-policy"}, clear=False):
            with pytest.raises(ValueError) as exc_info:
                Settings()
            assert "redis_memory_policy must be one of" in str(exc_info.value)

    def test_default_is_volatile_lru(self):
        """Test default policy is volatile-lru."""
        # Remove the env var if it exists
        env = os.environ.copy()
        env.pop("REDIS_MEMORY_POLICY", None)
        with patch.dict(os.environ, env, clear=True):
            with patch.dict(
                os.environ,
                {"DATABASE_URL": "postgresql://test", "REDIS_URL": "redis://localhost:6379"},
                clear=False,
            ):
                settings = Settings()
                assert settings.redis_memory_policy == "volatile-lru"


class TestRedisMemoryLimitMb:
    """Tests for redis_memory_limit_mb setting."""

    def test_default_is_zero(self):
        """Test default memory limit is 0 (unlimited)."""
        settings = Settings()
        assert settings.redis_memory_limit_mb == 0

    def test_valid_value(self):
        """Test setting a valid memory limit."""
        with patch.dict(os.environ, {"REDIS_MEMORY_LIMIT_MB": "256"}, clear=False):
            settings = Settings()
            assert settings.redis_memory_limit_mb == 256

    def test_large_value(self):
        """Test setting a large memory limit."""
        with patch.dict(os.environ, {"REDIS_MEMORY_LIMIT_MB": "4096"}, clear=False):
            settings = Settings()
            assert settings.redis_memory_limit_mb == 4096

    def test_max_value(self):
        """Test maximum allowed value (128 GB)."""
        with patch.dict(os.environ, {"REDIS_MEMORY_LIMIT_MB": "131072"}, clear=False):
            settings = Settings()
            assert settings.redis_memory_limit_mb == 131072

    def test_negative_value_raises_error(self):
        """Test negative value raises error."""
        with patch.dict(os.environ, {"REDIS_MEMORY_LIMIT_MB": "-1"}, clear=False):
            with pytest.raises(ValueError):
                Settings()

    def test_exceeds_max_raises_error(self):
        """Test value exceeding max raises error."""
        with patch.dict(os.environ, {"REDIS_MEMORY_LIMIT_MB": "999999"}, clear=False):
            with pytest.raises(ValueError):
                Settings()


class TestRedisMemoryApplyOnStartup:
    """Tests for redis_memory_apply_on_startup setting."""

    def test_default_is_false(self):
        """Test default is False (don't apply settings)."""
        settings = Settings()
        assert settings.redis_memory_apply_on_startup is False

    def test_can_enable(self):
        """Test enabling apply on startup."""
        with patch.dict(os.environ, {"REDIS_MEMORY_APPLY_ON_STARTUP": "true"}, clear=False):
            settings = Settings()
            assert settings.redis_memory_apply_on_startup is True

    def test_can_disable_explicitly(self):
        """Test explicitly disabling apply on startup."""
        with patch.dict(os.environ, {"REDIS_MEMORY_APPLY_ON_STARTUP": "false"}, clear=False):
            settings = Settings()
            assert settings.redis_memory_apply_on_startup is False


class TestHllTtlSeconds:
    """Tests for hll_ttl_seconds setting."""

    def test_default_is_one_day(self):
        """Test default TTL is 24 hours."""
        settings = Settings()
        assert settings.hll_ttl_seconds == 86400

    def test_valid_value(self):
        """Test setting a valid TTL."""
        with patch.dict(os.environ, {"HLL_TTL_SECONDS": "172800"}, clear=False):
            settings = Settings()
            assert settings.hll_ttl_seconds == 172800  # 2 days

    def test_minimum_value(self):
        """Test minimum allowed value (1 hour)."""
        with patch.dict(os.environ, {"HLL_TTL_SECONDS": "3600"}, clear=False):
            settings = Settings()
            assert settings.hll_ttl_seconds == 3600

    def test_maximum_value(self):
        """Test maximum allowed value (7 days)."""
        with patch.dict(os.environ, {"HLL_TTL_SECONDS": "604800"}, clear=False):
            settings = Settings()
            assert settings.hll_ttl_seconds == 604800

    def test_below_minimum_raises_error(self):
        """Test value below minimum raises error."""
        with patch.dict(os.environ, {"HLL_TTL_SECONDS": "1800"}, clear=False):
            with pytest.raises(ValueError):
                Settings()

    def test_above_maximum_raises_error(self):
        """Test value above maximum raises error."""
        with patch.dict(os.environ, {"HLL_TTL_SECONDS": "1000000"}, clear=False):
            with pytest.raises(ValueError):
                Settings()


class TestHllKeyPrefix:
    """Tests for hll_key_prefix setting."""

    def test_default_is_hll(self):
        """Test default prefix is 'hll'."""
        settings = Settings()
        assert settings.hll_key_prefix == "hll"

    def test_custom_prefix(self):
        """Test setting a custom prefix."""
        with patch.dict(os.environ, {"HLL_KEY_PREFIX": "hyperloglog"}, clear=False):
            settings = Settings()
            assert settings.hll_key_prefix == "hyperloglog"

    def test_prefix_with_namespace(self):
        """Test prefix with namespace separator."""
        with patch.dict(os.environ, {"HLL_KEY_PREFIX": "analytics:hll"}, clear=False):
            settings = Settings()
            assert settings.hll_key_prefix == "analytics:hll"
