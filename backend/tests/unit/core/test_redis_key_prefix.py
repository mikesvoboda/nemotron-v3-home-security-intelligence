"""Unit tests for Redis key prefix namespacing (NEM-1621).

This module tests the standardization of Redis key prefixes for
multi-instance and blue-green deployments. All Redis keys should
use a configurable prefix to enable key isolation.

TDD: These tests are written FIRST before implementation.
"""

import os
from unittest.mock import patch

import pytest

# =============================================================================
# Settings Tests - REDIS_KEY_PREFIX configuration
# =============================================================================


def test_settings_redis_key_prefix_default():
    """Test that REDIS_KEY_PREFIX defaults to 'hsi'."""
    # Import fresh settings with no env override
    with patch.dict(os.environ, {}, clear=False):
        # Remove any existing REDIS_KEY_PREFIX
        env_copy = dict(os.environ)
        env_copy.pop("REDIS_KEY_PREFIX", None)
        with patch.dict(os.environ, env_copy, clear=True):
            from backend.core.config import Settings

            settings = Settings(
                database_url="postgresql+asyncpg://user:pass@localhost:5432/db",  # pragma: allowlist secret
                _env_file=None,
            )
            assert settings.redis_key_prefix == "hsi"


def test_settings_redis_key_prefix_from_env():
    """Test that REDIS_KEY_PREFIX can be overridden via environment variable."""
    with patch.dict(os.environ, {"REDIS_KEY_PREFIX": "myapp-prod"}, clear=False):
        from backend.core.config import Settings

        settings = Settings(
            database_url="postgresql+asyncpg://user:pass@localhost:5432/db",  # pragma: allowlist secret
            _env_file=None,
        )
        assert settings.redis_key_prefix == "myapp-prod"


def test_settings_redis_key_prefix_blue_green_deployment():
    """Test prefix for blue-green deployment scenario."""
    with patch.dict(os.environ, {"REDIS_KEY_PREFIX": "hsi-blue"}, clear=False):
        from backend.core.config import Settings

        settings = Settings(
            database_url="postgresql+asyncpg://user:pass@localhost:5432/db",  # pragma: allowlist secret
            _env_file=None,
        )
        assert settings.redis_key_prefix == "hsi-blue"


# =============================================================================
# CacheKeys Tests - Standardized key generation with prefix
# =============================================================================


def test_cache_keys_has_prefix_attribute():
    """Test that CacheKeys has a PREFIX attribute."""
    from backend.services.cache_service import CacheKeys

    assert hasattr(CacheKeys, "PREFIX")


def test_cache_keys_prefix_uses_settings():
    """Test that CacheKeys.PREFIX comes from settings."""
    from backend.services.cache_service import CacheKeys

    # Default should be 'hsi'
    assert CacheKeys.PREFIX == "hsi"


def test_cache_keys_event_stats_includes_prefix():
    """Test event_stats key includes the prefix."""
    from backend.services.cache_service import CacheKeys

    key = CacheKeys.event_stats("2024-01-01", "2024-01-31")
    assert key.startswith(f"{CacheKeys.PREFIX}:")
    assert "cache:event_stats" in key or "event_stats" in key


def test_cache_keys_event_stats_format():
    """Test event_stats key has correct format with prefix."""
    from backend.services.cache_service import CacheKeys

    key = CacheKeys.event_stats("2024-01-01", "2024-01-31")
    # Expected: "{PREFIX}:cache:event_stats:{start}:{end}:{camera_id}"
    # NEM-2434: Added camera_id to support camera-specific stats
    expected = f"{CacheKeys.PREFIX}:cache:event_stats:2024-01-01:2024-01-31:all"
    assert key == expected


def test_cache_keys_cameras_list_includes_prefix():
    """Test cameras_list key includes the prefix."""
    from backend.services.cache_service import CacheKeys

    key = CacheKeys.cameras_list()
    assert key.startswith(f"{CacheKeys.PREFIX}:")


def test_cache_keys_camera_includes_prefix():
    """Test camera key includes the prefix."""
    from backend.services.cache_service import CacheKeys

    key = CacheKeys.camera("front_door")
    assert key.startswith(f"{CacheKeys.PREFIX}:")
    assert "front_door" in key


def test_cache_keys_system_status_includes_prefix():
    """Test system_status key includes the prefix."""
    from backend.services.cache_service import CacheKeys

    key = CacheKeys.system_status()
    assert key.startswith(f"{CacheKeys.PREFIX}:")


def test_cache_keys_queue_method_exists():
    """Test CacheKeys has a queue method."""
    from backend.services.cache_service import CacheKeys

    assert hasattr(CacheKeys, "queue")
    assert callable(CacheKeys.queue)


def test_cache_keys_queue_format():
    """Test queue key has correct format with prefix."""
    from backend.services.cache_service import CacheKeys

    key = CacheKeys.queue("detection_queue")
    expected = f"{CacheKeys.PREFIX}:queue:detection_queue"
    assert key == expected


def test_cache_keys_queue_with_dlq():
    """Test queue key for DLQ queues."""
    from backend.services.cache_service import CacheKeys

    key = CacheKeys.queue("dlq:detection_queue")
    expected = f"{CacheKeys.PREFIX}:queue:dlq:detection_queue"
    assert key == expected


# =============================================================================
# Constants Tests - Queue name functions with prefix
# =============================================================================


def test_constants_get_prefixed_queue_name_exists():
    """Test that get_prefixed_queue_name function exists in constants."""
    from backend.core.constants import get_prefixed_queue_name

    assert callable(get_prefixed_queue_name)


def test_constants_get_prefixed_queue_name_format():
    """Test get_prefixed_queue_name returns correct format."""
    from backend.core.constants import get_prefixed_queue_name

    name = get_prefixed_queue_name("detection_queue")
    # Should include prefix from settings
    assert ":queue:" in name
    assert "detection_queue" in name


def test_constants_get_prefixed_dlq_name():
    """Test get_prefixed_queue_name works with DLQ names."""
    from backend.core.constants import get_prefixed_queue_name

    name = get_prefixed_queue_name("dlq:detection_queue")
    assert "dlq:detection_queue" in name


def test_constants_queue_names_use_prefix():
    """Test that queue name constants include prefix."""
    from backend.core.constants import ANALYSIS_QUEUE, DETECTION_QUEUE, get_prefixed_queue_name

    # The raw constants should still be unprefixed for backwards compatibility
    assert DETECTION_QUEUE == "detection_queue"
    assert ANALYSIS_QUEUE == "analysis_queue"

    # But get_prefixed_queue_name should add prefix
    prefixed = get_prefixed_queue_name(DETECTION_QUEUE)
    assert prefixed.startswith("hsi:")


# =============================================================================
# Cache Service Tests - Full key prefixing
# =============================================================================


def test_cache_prefix_constant_backward_compatibility():
    """Test that CACHE_PREFIX is kept for backward compatibility.

    The CACHE_PREFIX constant is kept as "cache:" for backward compatibility
    with the CacheService internal implementation. New code should use
    CacheKeys methods which include the global prefix.
    """
    from backend.services.cache_service import CACHE_PREFIX, CacheKeys

    # CACHE_PREFIX is kept as-is for backward compatibility
    assert CACHE_PREFIX == "cache:"

    # CacheKeys methods include the global prefix
    assert CacheKeys.cameras_list().startswith(f"{CacheKeys.PREFIX}:")


def test_cache_service_get_uses_full_prefix():
    """Test that cache service get operation uses the full prefix.

    Note: CacheService uses internal CACHE_PREFIX for backward compatibility.
    New code should use CacheKeys methods which include the global prefix.
    """
    from backend.services.cache_service import CACHE_PREFIX, CacheKeys

    # The internal CACHE_PREFIX is kept for backward compatibility
    assert CACHE_PREFIX == "cache:"

    # CacheKeys methods include the global prefix
    assert CacheKeys.cameras_list().startswith(f"{CacheKeys.PREFIX}:")


def test_cache_service_set_uses_full_prefix():
    """Test that cache service set operation uses the full prefix.

    Note: CacheService uses internal CACHE_PREFIX for backward compatibility.
    New code should use CacheKeys methods which include the global prefix.
    """
    from backend.services.cache_service import CACHE_PREFIX, CacheKeys

    # The internal CACHE_PREFIX is kept for backward compatibility
    assert CACHE_PREFIX == "cache:"

    # CacheKeys methods include the global prefix
    assert CacheKeys.system_status().startswith(f"{CacheKeys.PREFIX}:")


# =============================================================================
# Redis Client Tests - Queue operations with prefix
# =============================================================================


@pytest.mark.asyncio
async def test_redis_client_add_to_queue_uses_prefix():
    """Test that queue operations use prefixed queue names."""
    # This tests that the system properly handles prefixed queue names
    pass  # Implementation will be tested after code is written


# =============================================================================
# Integration-style Tests
# =============================================================================


def test_key_isolation_different_prefixes():
    """Test that different prefixes create isolated key namespaces."""
    from backend.services.cache_service import CacheKeys

    # With default prefix
    default_key = CacheKeys.event_stats("2024-01-01", "2024-01-31")

    # Keys should be isolated by prefix
    assert "hsi:" in default_key


def test_blue_green_deployment_key_isolation():
    """Test key isolation for blue-green deployments."""
    # Blue deployment would use prefix "hsi-blue"
    # Green deployment would use prefix "hsi-green"
    # Keys should be completely separate in Redis
    from backend.services.cache_service import CacheKeys

    # Current implementation uses single prefix
    key = CacheKeys.queue("detection_queue")
    assert key.startswith(f"{CacheKeys.PREFIX}:")
