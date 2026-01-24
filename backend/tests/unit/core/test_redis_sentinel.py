"""Unit tests for Redis Sentinel high availability functionality (NEM-3413)."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from redis.asyncio import Redis
from redis.asyncio.sentinel import Sentinel
from redis.exceptions import ConnectionError

from backend.core.redis import (
    SentinelClient,
    _get_sentinel_init_lock,
    close_sentinel,
    get_sentinel_redis,
    get_sentinel_redis_slave,
)

# Fixtures


@pytest.fixture
def mock_sentinel():
    """Create a mock Sentinel instance."""
    mock = MagicMock(spec=Sentinel)
    return mock


@pytest.fixture
def mock_master_redis():
    """Create a mock Redis master client."""
    mock = AsyncMock(spec=Redis)
    mock.ping = AsyncMock(return_value=True)
    mock.info = AsyncMock(return_value={"redis_version": "7.4.0"})
    mock.aclose = AsyncMock()
    mock.get = AsyncMock(return_value=None)
    mock.set = AsyncMock(return_value=True)
    return mock


@pytest.fixture
def mock_slave_redis():
    """Create a mock Redis slave client."""
    mock = AsyncMock(spec=Redis)
    mock.ping = AsyncMock(return_value=True)
    mock.aclose = AsyncMock()
    mock.get = AsyncMock(return_value=None)
    return mock


@pytest.fixture
def mock_settings():
    """Create mock settings for Sentinel configuration."""
    settings = MagicMock()
    settings.redis_use_sentinel = True
    settings.redis_sentinel_master_name = "mymaster"
    settings.redis_sentinel_hosts = "sentinel1:26379,sentinel2:26379,sentinel3:26379"
    settings.redis_sentinel_socket_timeout = 0.1
    settings.redis_password = None
    settings.redis_pool_size = 50
    return settings


# SentinelClient Tests


class TestSentinelClientParsing:
    """Tests for Sentinel host parsing."""

    def test_parse_sentinel_hosts_valid(self):
        """Test parsing valid sentinel host string."""
        hosts = SentinelClient._parse_sentinel_hosts(
            "sentinel1:26379,sentinel2:26379,sentinel3:26379"
        )
        assert hosts == [
            ("sentinel1", 26379),
            ("sentinel2", 26379),
            ("sentinel3", 26379),
        ]

    def test_parse_sentinel_hosts_with_spaces(self):
        """Test parsing sentinel hosts with whitespace."""
        hosts = SentinelClient._parse_sentinel_hosts(
            "sentinel1:26379, sentinel2:26379 , sentinel3:26379"
        )
        assert hosts == [
            ("sentinel1", 26379),
            ("sentinel2", 26379),
            ("sentinel3", 26379),
        ]

    def test_parse_sentinel_hosts_single_host(self):
        """Test parsing a single sentinel host."""
        hosts = SentinelClient._parse_sentinel_hosts("localhost:26379")
        assert hosts == [("localhost", 26379)]

    def test_parse_sentinel_hosts_ipv4(self):
        """Test parsing IPv4 addresses."""
        hosts = SentinelClient._parse_sentinel_hosts("192.168.1.1:26379,192.168.1.2:26379")
        assert hosts == [
            ("192.168.1.1", 26379),
            ("192.168.1.2", 26379),
        ]

    def test_parse_sentinel_hosts_invalid_format(self):
        """Test parsing invalid host format raises ValueError."""
        with pytest.raises(ValueError, match="Invalid Sentinel host format"):
            SentinelClient._parse_sentinel_hosts("invalid-no-port")

    def test_parse_sentinel_hosts_invalid_port(self):
        """Test parsing invalid port raises ValueError."""
        with pytest.raises(ValueError, match="Invalid Sentinel host format"):
            SentinelClient._parse_sentinel_hosts("sentinel1:notaport")

    def test_parse_sentinel_hosts_empty_string(self):
        """Test parsing empty string raises ValueError."""
        with pytest.raises(ValueError, match="No valid Sentinel hosts"):
            SentinelClient._parse_sentinel_hosts("")

    def test_parse_sentinel_hosts_only_whitespace(self):
        """Test parsing whitespace-only string raises ValueError."""
        with pytest.raises(ValueError, match="No valid Sentinel hosts"):
            SentinelClient._parse_sentinel_hosts("   ")


class TestSentinelClientInit:
    """Tests for SentinelClient initialization."""

    def test_init_with_defaults(self, mock_settings):
        """Test initialization with default settings."""
        with patch("backend.core.redis.get_settings", return_value=mock_settings):
            client = SentinelClient()

            assert client._master_name == "mymaster"
            assert client._socket_timeout == 0.1
            assert client._sentinel_hosts == [
                ("sentinel1", 26379),
                ("sentinel2", 26379),
                ("sentinel3", 26379),
            ]
            assert client._sentinel is None
            assert client._master is None
            assert client._slave is None

    def test_init_with_custom_values(self, mock_settings):
        """Test initialization with custom values."""
        with patch("backend.core.redis.get_settings", return_value=mock_settings):
            client = SentinelClient(
                sentinel_hosts=[("custom1", 26379), ("custom2", 26379)],
                master_name="custom_master",
                socket_timeout=0.5,
                password="secret",  # pragma: allowlist secret
            )

            assert client._master_name == "custom_master"
            assert client._socket_timeout == 0.5
            assert client._sentinel_hosts == [("custom1", 26379), ("custom2", 26379)]
            assert client._password == "secret"  # pragma: allowlist secret

    def test_init_with_secretstr_password(self, mock_settings):
        """Test initialization extracts password from SecretStr."""
        mock_secret = MagicMock()
        mock_secret.get_secret_value.return_value = "secret_from_secretstr"
        mock_settings.redis_password = mock_secret

        with patch("backend.core.redis.get_settings", return_value=mock_settings):
            client = SentinelClient()

            assert client._password == "secret_from_secretstr"  # pragma: allowlist secret


class TestSentinelClientConnection:
    """Tests for SentinelClient connection management."""

    @pytest.mark.asyncio
    async def test_connect_success(
        self, mock_settings, mock_sentinel, mock_master_redis, mock_slave_redis
    ):
        """Test successful connection to Sentinel and master/slave."""
        mock_sentinel.master_for.return_value = mock_master_redis
        mock_sentinel.slave_for.return_value = mock_slave_redis

        with (
            patch("backend.core.redis.get_settings", return_value=mock_settings),
            patch("backend.core.redis.Sentinel", return_value=mock_sentinel),
        ):
            client = SentinelClient()
            await client.connect()

            assert client._sentinel is not None
            assert client._master is not None
            assert client._slave is not None
            mock_master_redis.ping.assert_awaited_once()
            mock_slave_redis.ping.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_connect_master_failure(self, mock_settings, mock_sentinel):
        """Test connection failure when master is unreachable."""
        mock_master = AsyncMock(spec=Redis)
        mock_master.ping = AsyncMock(side_effect=ConnectionError("Master unreachable"))
        mock_sentinel.master_for.return_value = mock_master

        with (
            patch("backend.core.redis.get_settings", return_value=mock_settings),
            patch("backend.core.redis.Sentinel", return_value=mock_sentinel),
        ):
            client = SentinelClient()

            with pytest.raises(ConnectionError, match="Cannot connect to Redis master"):
                await client.connect()

    @pytest.mark.asyncio
    async def test_connect_slave_failure_uses_master(
        self, mock_settings, mock_sentinel, mock_master_redis
    ):
        """Test that slave failure falls back to master for reads."""
        mock_slave = AsyncMock(spec=Redis)
        mock_slave.ping = AsyncMock(side_effect=Exception("Slave unreachable"))
        mock_sentinel.master_for.return_value = mock_master_redis
        mock_sentinel.slave_for.return_value = mock_slave

        with (
            patch("backend.core.redis.get_settings", return_value=mock_settings),
            patch("backend.core.redis.Sentinel", return_value=mock_sentinel),
        ):
            client = SentinelClient()
            await client.connect()

            # Slave should fall back to master
            assert client._slave == client._master

    @pytest.mark.asyncio
    async def test_disconnect(
        self, mock_settings, mock_sentinel, mock_master_redis, mock_slave_redis
    ):
        """Test disconnection closes all connections."""
        mock_sentinel.master_for.return_value = mock_master_redis
        mock_sentinel.slave_for.return_value = mock_slave_redis

        with (
            patch("backend.core.redis.get_settings", return_value=mock_settings),
            patch("backend.core.redis.Sentinel", return_value=mock_sentinel),
        ):
            client = SentinelClient()
            await client.connect()
            await client.disconnect()

            assert client._master is None
            assert client._slave is None
            assert client._sentinel is None
            mock_master_redis.aclose.assert_awaited_once()
            mock_slave_redis.aclose.assert_awaited_once()


class TestSentinelClientOperations:
    """Tests for SentinelClient operations."""

    @pytest.mark.asyncio
    async def test_get_master_when_connected(
        self, mock_settings, mock_sentinel, mock_master_redis, mock_slave_redis
    ):
        """Test get_master returns master connection."""
        mock_sentinel.master_for.return_value = mock_master_redis
        mock_sentinel.slave_for.return_value = mock_slave_redis

        with (
            patch("backend.core.redis.get_settings", return_value=mock_settings),
            patch("backend.core.redis.Sentinel", return_value=mock_sentinel),
        ):
            client = SentinelClient()
            await client.connect()

            master = client.get_master()
            assert master == mock_master_redis

    def test_get_master_when_not_connected(self, mock_settings):
        """Test get_master raises RuntimeError when not connected."""
        with patch("backend.core.redis.get_settings", return_value=mock_settings):
            client = SentinelClient()

            with pytest.raises(RuntimeError, match="not connected"):
                client.get_master()

    @pytest.mark.asyncio
    async def test_get_slave_when_connected(
        self, mock_settings, mock_sentinel, mock_master_redis, mock_slave_redis
    ):
        """Test get_slave returns slave connection."""
        mock_sentinel.master_for.return_value = mock_master_redis
        mock_sentinel.slave_for.return_value = mock_slave_redis

        with (
            patch("backend.core.redis.get_settings", return_value=mock_settings),
            patch("backend.core.redis.Sentinel", return_value=mock_sentinel),
        ):
            client = SentinelClient()
            await client.connect()

            slave = client.get_slave()
            assert slave == mock_slave_redis

    def test_get_slave_when_not_connected(self, mock_settings):
        """Test get_slave raises RuntimeError when not connected."""
        with patch("backend.core.redis.get_settings", return_value=mock_settings):
            client = SentinelClient()

            with pytest.raises(RuntimeError, match="not connected"):
                client.get_slave()


class TestSentinelClientHealthCheck:
    """Tests for SentinelClient health check."""

    @pytest.mark.asyncio
    async def test_health_check_healthy(
        self, mock_settings, mock_sentinel, mock_master_redis, mock_slave_redis
    ):
        """Test health check returns healthy status."""
        mock_sentinel.master_for.return_value = mock_master_redis
        mock_sentinel.slave_for.return_value = mock_slave_redis

        with (
            patch("backend.core.redis.get_settings", return_value=mock_settings),
            patch("backend.core.redis.Sentinel", return_value=mock_sentinel),
        ):
            client = SentinelClient()
            await client.connect()

            health = await client.health_check()

            assert health["status"] == "healthy"
            assert health["mode"] == "sentinel"
            assert health["master"]["connected"] is True
            assert health["slave"]["connected"] is True

    @pytest.mark.asyncio
    async def test_health_check_master_unhealthy(
        self, mock_settings, mock_sentinel, mock_master_redis, mock_slave_redis
    ):
        """Test health check returns unhealthy when master fails."""
        mock_sentinel.master_for.return_value = mock_master_redis
        mock_sentinel.slave_for.return_value = mock_slave_redis

        with (
            patch("backend.core.redis.get_settings", return_value=mock_settings),
            patch("backend.core.redis.Sentinel", return_value=mock_sentinel),
        ):
            client = SentinelClient()
            await client.connect()

            # Make master ping fail during health check
            mock_master_redis.ping.side_effect = ConnectionError("Master down")

            health = await client.health_check()

            assert health["status"] == "unhealthy"
            assert health["master"]["connected"] is False


# Module-level function tests


class TestGetSentinelRedis:
    """Tests for get_sentinel_redis function."""

    @pytest.fixture(autouse=True)
    async def cleanup(self):
        """Clean up global sentinel client after each test."""
        yield
        await close_sentinel()

    @pytest.mark.asyncio
    async def test_get_sentinel_redis_not_enabled(self):
        """Test get_sentinel_redis raises when Sentinel not enabled."""
        mock_settings = MagicMock()
        mock_settings.redis_use_sentinel = False

        with patch("backend.core.redis.get_settings", return_value=mock_settings):
            with pytest.raises(RuntimeError, match="Sentinel mode not enabled"):
                await get_sentinel_redis()

    @pytest.mark.asyncio
    async def test_get_sentinel_redis_success(
        self, mock_settings, mock_sentinel, mock_master_redis, mock_slave_redis
    ):
        """Test get_sentinel_redis returns master connection."""
        mock_sentinel.master_for.return_value = mock_master_redis
        mock_sentinel.slave_for.return_value = mock_slave_redis

        with (
            patch("backend.core.redis.get_settings", return_value=mock_settings),
            patch("backend.core.redis.Sentinel", return_value=mock_sentinel),
        ):
            master = await get_sentinel_redis()

            assert master == mock_master_redis

    @pytest.mark.asyncio
    async def test_get_sentinel_redis_caches_client(
        self, mock_settings, mock_sentinel, mock_master_redis, mock_slave_redis
    ):
        """Test get_sentinel_redis caches and reuses client."""
        mock_sentinel.master_for.return_value = mock_master_redis
        mock_sentinel.slave_for.return_value = mock_slave_redis

        with (
            patch("backend.core.redis.get_settings", return_value=mock_settings),
            patch("backend.core.redis.Sentinel", return_value=mock_sentinel) as mock_cls,
        ):
            # Call twice
            await get_sentinel_redis()
            await get_sentinel_redis()

            # Sentinel should only be created once
            assert mock_cls.call_count == 1


class TestGetSentinelRedisSlave:
    """Tests for get_sentinel_redis_slave function."""

    @pytest.fixture(autouse=True)
    async def cleanup(self):
        """Clean up global sentinel client after each test."""
        yield
        await close_sentinel()

    @pytest.mark.asyncio
    async def test_get_sentinel_redis_slave_not_enabled(self):
        """Test get_sentinel_redis_slave raises when Sentinel not enabled."""
        mock_settings = MagicMock()
        mock_settings.redis_use_sentinel = False

        with patch("backend.core.redis.get_settings", return_value=mock_settings):
            with pytest.raises(RuntimeError, match="Sentinel mode not enabled"):
                await get_sentinel_redis_slave()

    @pytest.mark.asyncio
    async def test_get_sentinel_redis_slave_success(
        self, mock_settings, mock_sentinel, mock_master_redis, mock_slave_redis
    ):
        """Test get_sentinel_redis_slave returns slave connection."""
        mock_sentinel.master_for.return_value = mock_master_redis
        mock_sentinel.slave_for.return_value = mock_slave_redis

        with (
            patch("backend.core.redis.get_settings", return_value=mock_settings),
            patch("backend.core.redis.Sentinel", return_value=mock_sentinel),
        ):
            slave = await get_sentinel_redis_slave()

            assert slave == mock_slave_redis


class TestCloseSentinel:
    """Tests for close_sentinel function."""

    @pytest.mark.asyncio
    async def test_close_sentinel_disconnects_client(
        self, mock_settings, mock_sentinel, mock_master_redis, mock_slave_redis
    ):
        """Test close_sentinel properly disconnects the client."""
        mock_sentinel.master_for.return_value = mock_master_redis
        mock_sentinel.slave_for.return_value = mock_slave_redis

        with (
            patch("backend.core.redis.get_settings", return_value=mock_settings),
            patch("backend.core.redis.Sentinel", return_value=mock_sentinel),
        ):
            # Initialize client
            await get_sentinel_redis()

            # Close it
            await close_sentinel()

            mock_master_redis.aclose.assert_awaited()

    @pytest.mark.asyncio
    async def test_close_sentinel_when_not_initialized(self):
        """Test close_sentinel is safe when client not initialized."""
        # Should not raise
        await close_sentinel()


class TestSentinelInitLock:
    """Tests for Sentinel initialization lock."""

    def test_get_sentinel_init_lock_creates_lock(self):
        """Test that _get_sentinel_init_lock creates an asyncio.Lock."""
        import backend.core.redis as redis_module

        # Reset the lock
        redis_module._sentinel_init_lock = None

        lock = _get_sentinel_init_lock()

        assert isinstance(lock, asyncio.Lock)

    def test_get_sentinel_init_lock_returns_same_lock(self):
        """Test that _get_sentinel_init_lock returns the same lock on subsequent calls."""
        import backend.core.redis as redis_module

        # Reset the lock
        redis_module._sentinel_init_lock = None

        lock1 = _get_sentinel_init_lock()
        lock2 = _get_sentinel_init_lock()

        assert lock1 is lock2
