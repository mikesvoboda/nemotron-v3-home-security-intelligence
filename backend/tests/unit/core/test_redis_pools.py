"""Unit tests for Redis dedicated connection pools (NEM-3368).

This module tests the dedicated connection pool configuration and PoolType enum.
"""

from unittest.mock import patch

from backend.core.redis import PoolType, RedisClient

# =============================================================================
# PoolType Enumeration Tests
# =============================================================================


def test_pool_type_values():
    """Test PoolType enum has expected values."""
    assert PoolType.CACHE.value == "cache"
    assert PoolType.QUEUE.value == "queue"
    assert PoolType.PUBSUB.value == "pubsub"
    assert PoolType.RATELIMIT.value == "ratelimit"
    assert PoolType.DEFAULT.value == "default"


def test_pool_type_is_string_enum():
    """Test PoolType values can be used as strings."""
    assert f"pool:{PoolType.CACHE.value}" == "pool:cache"
    assert PoolType.QUEUE.value == "queue"


def test_all_pool_types_are_defined():
    """Test all expected pool types exist."""
    expected_types = {"cache", "queue", "pubsub", "ratelimit", "default"}
    actual_types = {pt.value for pt in PoolType}
    assert expected_types == actual_types


# =============================================================================
# RedisClient Initialization Tests
# =============================================================================


def test_redis_client_init_with_dedicated_pools():
    """Test RedisClient initialization with dedicated pools enabled."""
    with patch("backend.core.redis.get_settings") as mock_settings:
        mock_settings.return_value.redis_url = "redis://localhost:6379"
        mock_settings.return_value.redis_password = None
        mock_settings.return_value.redis_ssl_enabled = False
        mock_settings.return_value.redis_ssl_cert_reqs = "required"
        mock_settings.return_value.redis_ssl_ca_certs = None
        mock_settings.return_value.redis_ssl_certfile = None
        mock_settings.return_value.redis_ssl_keyfile = None
        mock_settings.return_value.redis_ssl_check_hostname = True
        mock_settings.return_value.redis_pool_dedicated_enabled = True
        mock_settings.return_value.redis_pool_size = 50
        mock_settings.return_value.redis_pool_size_cache = 20
        mock_settings.return_value.redis_pool_size_queue = 15
        mock_settings.return_value.redis_pool_size_pubsub = 10
        mock_settings.return_value.redis_pool_size_ratelimit = 10

        client = RedisClient()

        assert client._dedicated_pools_enabled is True
        assert PoolType.CACHE in client._pool_sizes
        assert client._pool_sizes[PoolType.CACHE] == 20
        assert client._pool_sizes[PoolType.QUEUE] == 15
        assert client._pool_sizes[PoolType.PUBSUB] == 10
        assert client._pool_sizes[PoolType.RATELIMIT] == 10


def test_redis_client_init_dedicated_pools_disabled():
    """Test RedisClient initialization with dedicated pools disabled."""
    with patch("backend.core.redis.get_settings") as mock_settings:
        mock_settings.return_value.redis_url = "redis://localhost:6379"
        mock_settings.return_value.redis_password = None
        mock_settings.return_value.redis_ssl_enabled = False
        mock_settings.return_value.redis_ssl_cert_reqs = "required"
        mock_settings.return_value.redis_ssl_ca_certs = None
        mock_settings.return_value.redis_ssl_certfile = None
        mock_settings.return_value.redis_ssl_keyfile = None
        mock_settings.return_value.redis_ssl_check_hostname = True
        mock_settings.return_value.redis_pool_dedicated_enabled = False
        mock_settings.return_value.redis_pool_size = 50
        mock_settings.return_value.redis_pool_size_cache = 20
        mock_settings.return_value.redis_pool_size_queue = 15
        mock_settings.return_value.redis_pool_size_pubsub = 10
        mock_settings.return_value.redis_pool_size_ratelimit = 10

        client = RedisClient(dedicated_pools=False)

        assert client._dedicated_pools_enabled is False


def test_redis_client_init_override_dedicated_pools():
    """Test RedisClient can override dedicated_pools setting."""
    with patch("backend.core.redis.get_settings") as mock_settings:
        mock_settings.return_value.redis_url = "redis://localhost:6379"
        mock_settings.return_value.redis_password = None
        mock_settings.return_value.redis_ssl_enabled = False
        mock_settings.return_value.redis_ssl_cert_reqs = "required"
        mock_settings.return_value.redis_ssl_ca_certs = None
        mock_settings.return_value.redis_ssl_certfile = None
        mock_settings.return_value.redis_ssl_keyfile = None
        mock_settings.return_value.redis_ssl_check_hostname = True
        mock_settings.return_value.redis_pool_dedicated_enabled = True  # Settings says True
        mock_settings.return_value.redis_pool_size = 50
        mock_settings.return_value.redis_pool_size_cache = 20
        mock_settings.return_value.redis_pool_size_queue = 15
        mock_settings.return_value.redis_pool_size_pubsub = 10
        mock_settings.return_value.redis_pool_size_ratelimit = 10

        # But constructor says False
        client = RedisClient(dedicated_pools=False)

        assert client._dedicated_pools_enabled is False


def test_redis_client_pool_sizes_configured():
    """Test pool sizes are configured from settings."""
    with patch("backend.core.redis.get_settings") as mock_settings:
        mock_settings.return_value.redis_url = "redis://localhost:6379"
        mock_settings.return_value.redis_password = None
        mock_settings.return_value.redis_ssl_enabled = False
        mock_settings.return_value.redis_ssl_cert_reqs = "required"
        mock_settings.return_value.redis_ssl_ca_certs = None
        mock_settings.return_value.redis_ssl_certfile = None
        mock_settings.return_value.redis_ssl_keyfile = None
        mock_settings.return_value.redis_ssl_check_hostname = True
        mock_settings.return_value.redis_pool_dedicated_enabled = True
        mock_settings.return_value.redis_pool_size = 100
        mock_settings.return_value.redis_pool_size_cache = 30
        mock_settings.return_value.redis_pool_size_queue = 25
        mock_settings.return_value.redis_pool_size_pubsub = 15
        mock_settings.return_value.redis_pool_size_ratelimit = 12

        client = RedisClient()

        # Verify pool sizes
        assert client._pool_sizes[PoolType.CACHE] == 30
        assert client._pool_sizes[PoolType.QUEUE] == 25
        assert client._pool_sizes[PoolType.PUBSUB] == 15
        assert client._pool_sizes[PoolType.RATELIMIT] == 12
        assert client._pool_sizes[PoolType.DEFAULT] == 100


# =============================================================================
# Config Settings Tests
# =============================================================================


def test_config_has_pool_settings():
    """Test configuration has all pool-related settings."""
    from backend.core.config import Settings

    # Get the field names
    field_names = list(Settings.model_fields.keys())

    # Verify pool settings exist
    assert "redis_pool_dedicated_enabled" in field_names
    assert "redis_pool_size_cache" in field_names
    assert "redis_pool_size_queue" in field_names
    assert "redis_pool_size_pubsub" in field_names
    assert "redis_pool_size_ratelimit" in field_names


def test_config_has_swr_settings():
    """Test configuration has SWR-related settings."""
    from backend.core.config import Settings

    # Get the field names
    field_names = list(Settings.model_fields.keys())

    # Verify SWR settings exist
    assert "cache_swr_enabled" in field_names
    assert "cache_swr_stale_ttl" in field_names


def test_config_pool_defaults():
    """Test pool settings have reasonable defaults."""
    from backend.core.config import Settings

    fields = Settings.model_fields

    # Check defaults
    assert fields["redis_pool_dedicated_enabled"].default is True
    assert fields["redis_pool_size_cache"].default == 20
    assert fields["redis_pool_size_queue"].default == 15
    assert fields["redis_pool_size_pubsub"].default == 10
    assert fields["redis_pool_size_ratelimit"].default == 10


def test_config_swr_defaults():
    """Test SWR settings have reasonable defaults."""
    from backend.core.config import Settings

    fields = Settings.model_fields

    # Check defaults
    assert fields["cache_swr_enabled"].default is True
    assert fields["cache_swr_stale_ttl"].default == 60
