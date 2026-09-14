"""Unit tests for Redis Cluster support (NEM-3761)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.core.redis_cluster import (
    ClusterHealthStatus,
    ClusterNodeInfo,
    RedisClusterClient,
    close_redis_cluster,
    get_redis_cluster,
)


@pytest.fixture
def mock_settings():
    """Mock settings for cluster tests."""
    settings = MagicMock()
    settings.redis_cluster_enabled = True
    settings.redis_cluster_nodes = "redis-node1:6379,redis-node2:6379,redis-node3:6379"
    settings.redis_cluster_read_from_replicas = True
    settings.redis_cluster_max_connections_per_node = 10
    settings.redis_password = None
    settings.redis_ssl_enabled = False
    return settings


@pytest.fixture
def mock_cluster_connection():
    """Mock Redis cluster connection."""
    cluster = AsyncMock()
    cluster.ping = AsyncMock(return_value=True)
    cluster.aclose = AsyncMock()
    cluster.get = AsyncMock(return_value=None)
    cluster.set = AsyncMock(return_value=True)
    cluster.delete = AsyncMock(return_value=1)
    cluster.exists = AsyncMock(return_value=1)
    cluster.expire = AsyncMock(return_value=True)
    cluster.lpush = AsyncMock(return_value=1)
    cluster.rpush = AsyncMock(return_value=1)
    cluster.lpop = AsyncMock(return_value=None)
    cluster.llen = AsyncMock(return_value=0)
    cluster.publish = AsyncMock(return_value=1)
    cluster.cluster_info = AsyncMock(
        return_value={"cluster_state": "ok", "cluster_slots_ok": 16384}
    )
    cluster.cluster_nodes = AsyncMock(return_value={})
    cluster.cluster_keyslot = AsyncMock(return_value=5000)
    cluster.cluster_slots = AsyncMock(return_value=[])
    return cluster


class TestClusterNodeInfo:
    """Tests for ClusterNodeInfo dataclass."""

    def test_node_info_master(self):
        """Test master node info."""
        node = ClusterNodeInfo(
            host="redis-node1",
            port=6379,
            node_id="abc123",
            role="master",
            is_connected=True,
        )
        assert node.role == "master"
        assert node.is_connected is True

    def test_node_info_replica(self):
        """Test replica node info."""
        node = ClusterNodeInfo(
            host="redis-node2",
            port=6379,
            role="replica",
            is_connected=True,
        )
        assert node.role == "replica"


class TestClusterHealthStatus:
    """Tests for ClusterHealthStatus dataclass."""

    def test_health_status_healthy(self):
        """Test healthy cluster status."""
        status = ClusterHealthStatus(
            healthy=True,
            cluster_state="ok",
            total_nodes=6,
            connected_nodes=6,
            master_nodes=3,
            replica_nodes=3,
            total_slots_covered=16384,
            nodes=[],
        )
        assert status.healthy is True
        assert status.cluster_state == "ok"
        assert status.error is None

    def test_health_status_unhealthy(self):
        """Test unhealthy cluster status."""
        status = ClusterHealthStatus(
            healthy=False,
            cluster_state="fail",
            total_nodes=6,
            connected_nodes=4,
            master_nodes=3,
            replica_nodes=3,
            total_slots_covered=12288,
            nodes=[],
            error="2 nodes disconnected",
        )
        assert status.healthy is False
        assert status.error is not None


class TestRedisClusterClient:
    """Tests for RedisClusterClient class."""

    def test_parse_cluster_nodes(self):
        """Test parsing comma-separated cluster nodes."""
        nodes = RedisClusterClient._parse_cluster_nodes("node1:6379,node2:6379,node3:6380")
        assert nodes == ["node1:6379", "node2:6379", "node3:6380"]

    def test_parse_cluster_nodes_with_spaces(self):
        """Test parsing nodes with whitespace."""
        nodes = RedisClusterClient._parse_cluster_nodes("node1:6379, node2:6379 , node3:6380")
        assert nodes == ["node1:6379", "node2:6379", "node3:6380"]

    def test_parse_cluster_nodes_empty(self):
        """Test parsing empty nodes string."""
        nodes = RedisClusterClient._parse_cluster_nodes("")
        assert nodes == []

    def test_parse_node_addresses(self):
        """Test parsing node addresses to tuples."""
        addresses = RedisClusterClient._parse_node_addresses(["node1:6379", "node2:6380"])
        assert addresses == [("node1", 6379), ("node2", 6380)]

    def test_parse_node_addresses_invalid(self):
        """Test parsing invalid node addresses raises ValueError."""
        with pytest.raises(ValueError, match="Invalid cluster node format"):
            RedisClusterClient._parse_node_addresses(["invalid_format"])

    @pytest.mark.asyncio
    async def test_connect_success(self, mock_settings, mock_cluster_connection):
        """Test successful cluster connection."""
        with (
            patch("backend.core.redis_cluster.get_settings", return_value=mock_settings),
            patch("redis.asyncio.cluster.RedisCluster", return_value=mock_cluster_connection),
        ):
            client = RedisClusterClient(cluster_nodes=["redis-node1:6379", "redis-node2:6379"])
            await client.connect()

            assert client._connected is True
            mock_cluster_connection.ping.assert_awaited_once()

            await client.disconnect()

    @pytest.mark.asyncio
    async def test_disconnect(self, mock_settings, mock_cluster_connection):
        """Test cluster disconnection."""
        with (
            patch("backend.core.redis_cluster.get_settings", return_value=mock_settings),
            patch("redis.asyncio.cluster.RedisCluster", return_value=mock_cluster_connection),
        ):
            client = RedisClusterClient(cluster_nodes=["redis-node1:6379", "redis-node2:6379"])
            await client.connect()
            await client.disconnect()

            assert client._connected is False
            mock_cluster_connection.aclose.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_ensure_connected_raises(self, mock_settings):
        """Test _ensure_connected raises when not connected."""
        with patch("backend.core.redis_cluster.get_settings", return_value=mock_settings):
            client = RedisClusterClient()

        with pytest.raises(RuntimeError, match="Redis Cluster not connected"):
            client._ensure_connected()

    @pytest.mark.asyncio
    async def test_get_set_operations(self, mock_settings, mock_cluster_connection):
        """Test basic get/set operations."""
        mock_cluster_connection.get.return_value = '{"key": "value"}'

        with (
            patch("backend.core.redis_cluster.get_settings", return_value=mock_settings),
            patch("redis.asyncio.cluster.RedisCluster", return_value=mock_cluster_connection),
        ):
            client = RedisClusterClient()
            await client.connect()

            # Test get
            value = await client.get("test_key")
            assert value == {"key": "value"}

            # Test set
            result = await client.set("test_key", {"data": "value"}, expire=300)
            assert result is True

            await client.disconnect()

    @pytest.mark.asyncio
    async def test_delete_operation(self, mock_settings, mock_cluster_connection):
        """Test delete operation."""
        mock_cluster_connection.delete.return_value = 2

        with (
            patch("backend.core.redis_cluster.get_settings", return_value=mock_settings),
            patch("redis.asyncio.cluster.RedisCluster", return_value=mock_cluster_connection),
        ):
            client = RedisClusterClient()
            await client.connect()

            deleted = await client.delete("key1", "key2")
            assert deleted == 2

            await client.disconnect()

    @pytest.mark.asyncio
    async def test_list_operations(self, mock_settings, mock_cluster_connection):
        """Test list operations."""
        mock_cluster_connection.rpush.return_value = 5
        mock_cluster_connection.llen.return_value = 5

        with (
            patch("backend.core.redis_cluster.get_settings", return_value=mock_settings),
            patch("redis.asyncio.cluster.RedisCluster", return_value=mock_cluster_connection),
        ):
            client = RedisClusterClient()
            await client.connect()

            # Test rpush
            length = await client.rpush("queue", "item1", "item2")
            assert length == 5

            # Test llen
            length = await client.llen("queue")
            assert length == 5

            await client.disconnect()

    @pytest.mark.asyncio
    async def test_publish(self, mock_settings, mock_cluster_connection):
        """Test pub/sub publish."""
        mock_cluster_connection.publish.return_value = 3

        with (
            patch("backend.core.redis_cluster.get_settings", return_value=mock_settings),
            patch("redis.asyncio.cluster.RedisCluster", return_value=mock_cluster_connection),
        ):
            client = RedisClusterClient()
            await client.connect()

            subscribers = await client.publish("channel", {"event": "test"})
            assert subscribers == 3

            await client.disconnect()

    @pytest.mark.asyncio
    async def test_health_check_healthy(self, mock_settings, mock_cluster_connection):
        """Test health check for healthy cluster."""
        mock_cluster_connection.cluster_info.return_value = {
            "cluster_state": "ok",
            "cluster_slots_ok": 16384,
        }
        mock_cluster_connection.cluster_nodes.return_value = {
            "node1": {"host": "redis-1", "port": 6379, "flags": "master,connected"},
            "node2": {"host": "redis-2", "port": 6379, "flags": "slave,connected"},
        }

        with (
            patch("backend.core.redis_cluster.get_settings", return_value=mock_settings),
            patch("redis.asyncio.cluster.RedisCluster", return_value=mock_cluster_connection),
        ):
            client = RedisClusterClient()
            await client.connect()

            health = await client.health_check()

            assert health.healthy is True
            assert health.cluster_state == "ok"
            assert health.total_slots_covered == 16384

            await client.disconnect()

    @pytest.mark.asyncio
    async def test_health_check_error(self, mock_settings, mock_cluster_connection):
        """Test health check when cluster returns error."""
        mock_cluster_connection.cluster_info.side_effect = Exception("Connection lost")

        with (
            patch("backend.core.redis_cluster.get_settings", return_value=mock_settings),
            patch("redis.asyncio.cluster.RedisCluster", return_value=mock_cluster_connection),
        ):
            client = RedisClusterClient()
            await client.connect()

            health = await client.health_check()

            assert health.healthy is False
            assert "Connection lost" in health.error

            await client.disconnect()

    @pytest.mark.asyncio
    async def test_get_slot_for_key(self, mock_settings, mock_cluster_connection):
        """Test getting cluster slot for a key."""
        mock_cluster_connection.cluster_keyslot.return_value = 12345

        with (
            patch("backend.core.redis_cluster.get_settings", return_value=mock_settings),
            patch("redis.asyncio.cluster.RedisCluster", return_value=mock_cluster_connection),
        ):
            client = RedisClusterClient()
            await client.connect()

            slot = await client.get_slot_for_key("my_key")

            assert slot == 12345
            mock_cluster_connection.cluster_keyslot.assert_awaited_once_with("my_key")

            await client.disconnect()


class TestGetRedisCluster:
    """Tests for get_redis_cluster function."""

    @pytest.mark.asyncio
    async def test_cluster_disabled_raises(self, mock_settings):
        """Test get_redis_cluster raises when cluster is disabled."""
        mock_settings.redis_cluster_enabled = False

        with patch("backend.core.redis_cluster.get_settings", return_value=mock_settings):
            with pytest.raises(RuntimeError, match="Redis Cluster mode not enabled"):
                await get_redis_cluster()

    @pytest.mark.asyncio
    async def test_singleton_behavior(self, mock_settings, mock_cluster_connection):
        """Test get_redis_cluster returns singleton."""
        # Reset global state
        import backend.core.redis_cluster as cluster_module

        cluster_module._cluster_client = None
        cluster_module._cluster_init_lock = None

        with (
            patch("backend.core.redis_cluster.get_settings", return_value=mock_settings),
            patch("redis.asyncio.cluster.RedisCluster", return_value=mock_cluster_connection),
        ):
            client1 = await get_redis_cluster()
            client2 = await get_redis_cluster()

            assert client1 is client2

        # Cleanup
        await close_redis_cluster()


class TestCloseRedisCluster:
    """Tests for close_redis_cluster function."""

    @pytest.mark.asyncio
    async def test_close_when_not_connected(self):
        """Test closing when no client exists."""
        # Reset global state
        import backend.core.redis_cluster as cluster_module

        cluster_module._cluster_client = None

        # Should not raise
        await close_redis_cluster()

    @pytest.mark.asyncio
    async def test_close_resets_state(self, mock_settings, mock_cluster_connection):
        """Test closing resets global state."""
        import backend.core.redis_cluster as cluster_module

        # Reset global state
        cluster_module._cluster_client = None
        cluster_module._cluster_init_lock = None

        with (
            patch("backend.core.redis_cluster.get_settings", return_value=mock_settings),
            patch("redis.asyncio.cluster.RedisCluster", return_value=mock_cluster_connection),
        ):
            await get_redis_cluster()
            assert cluster_module._cluster_client is not None

            await close_redis_cluster()
            assert cluster_module._cluster_client is None
