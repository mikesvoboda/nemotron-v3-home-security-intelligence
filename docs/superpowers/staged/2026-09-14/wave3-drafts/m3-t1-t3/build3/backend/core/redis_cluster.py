"""Redis Cluster support for horizontal scalability.

This module provides Redis Cluster client support (NEM-3761) for deployments
that require horizontal scaling beyond a single Redis instance.

Redis Cluster provides:
- Automatic data sharding across multiple nodes
- High availability with automatic failover
- Linear scalability for read/write operations

Usage:
    # Enable via environment variables:
    # REDIS_CLUSTER_ENABLED=true
    # REDIS_CLUSTER_NODES=redis-node1:6379,redis-node2:6379,redis-node3:6379

    # Or programmatically:
    cluster = RedisClusterClient(
        cluster_nodes=["redis-node1:6379", "redis-node2:6379"],
    )
    await cluster.connect()
    await cluster.set("key", "value")

Note:
    Not all Redis operations are supported in cluster mode. Operations that
    require keys to be on the same node (like MGET across different slots)
    must use hash tags: {user:123}:profile and {user:123}:settings
"""

import asyncio
import contextlib
import json
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Any, cast

from backend.core.config import get_settings
from backend.core.logging import get_logger

logger = get_logger(__name__)


@dataclass(slots=True)
class ClusterNodeInfo:
    """Information about a cluster node."""

    host: str
    port: int
    node_id: str | None = None
    role: str = "unknown"  # "master" or "replica"
    slots: list[tuple[int, int]] | None = None
    is_connected: bool = False


@dataclass(slots=True)
class ClusterHealthStatus:
    """Health status of the Redis cluster."""

    healthy: bool
    cluster_state: str  # "ok", "fail", "unknown"
    total_nodes: int
    connected_nodes: int
    master_nodes: int
    replica_nodes: int
    total_slots_covered: int
    nodes: list[ClusterNodeInfo]
    error: str | None = None


class RedisClusterClient:
    """Async Redis Cluster client with connection pooling and failover support.

    This client provides a similar interface to RedisClient but connects to
    a Redis Cluster for horizontal scalability. It handles:
    - Automatic slot discovery and key routing
    - Connection pooling per cluster node
    - Automatic failover when nodes become unavailable
    - Cluster topology refresh

    Limitations in cluster mode:
    - Multi-key operations must use hash tags for co-location
    - Lua scripts must only access keys in the same slot
    - Some commands (like KEYS) are not supported cluster-wide
    """

    def __init__(
        self,
        cluster_nodes: list[str] | None = None,
        password: str | None = None,
        ssl_enabled: bool | None = None,
        max_connections_per_node: int = 10,
        read_from_replicas: bool = True,
    ):
        """Initialize Redis Cluster client.

        Args:
            cluster_nodes: List of cluster node addresses ("host:port").
                If not provided, uses settings.redis_cluster_nodes.
            password: Redis password for authentication.
            ssl_enabled: Enable SSL/TLS encryption.
            max_connections_per_node: Max connections per cluster node.
            read_from_replicas: Allow read operations from replica nodes.
        """
        settings = get_settings()

        # Parse cluster nodes
        if cluster_nodes is None:
            cluster_nodes = self._parse_cluster_nodes(settings.redis_cluster_nodes)
        self._startup_nodes = self._parse_node_addresses(cluster_nodes)

        # Authentication
        self._password = password
        if self._password is None and settings.redis_password:
            self._password = (
                settings.redis_password.get_secret_value()
                if hasattr(settings.redis_password, "get_secret_value")
                else str(settings.redis_password)
            )

        # SSL settings
        self._ssl_enabled = ssl_enabled if ssl_enabled is not None else settings.redis_ssl_enabled

        # Connection settings
        self._max_connections = max_connections_per_node
        self._read_from_replicas = read_from_replicas

        # Cluster state
        self._cluster: Any = None  # RedisCluster instance
        self._connected = False

    @staticmethod
    def _parse_cluster_nodes(nodes_str: str) -> list[str]:
        """Parse comma-separated cluster nodes string.

        Args:
            nodes_str: Comma-separated host:port pairs

        Returns:
            List of node address strings
        """
        return [node.strip() for node in nodes_str.split(",") if node.strip()]

    @staticmethod
    def _parse_node_addresses(nodes: list[str]) -> list[tuple[str, int]]:
        """Parse node addresses into (host, port) tuples.

        Args:
            nodes: List of "host:port" strings

        Returns:
            List of (host, port) tuples

        Raises:
            ValueError: If node format is invalid
        """
        result = []
        for node in nodes:
            try:
                host, port_str = node.rsplit(":", 1)
                port = int(port_str)
                result.append((host, port))
            except ValueError as e:
                raise ValueError(
                    f"Invalid cluster node format '{node}'. Expected 'host:port'."
                ) from e
        return result

    async def connect(self) -> None:
        """Establish connection to Redis Cluster.

        Connects to the startup nodes and discovers the full cluster topology.

        Raises:
            ConnectionError: If unable to connect to the cluster
        """
        try:
            from redis.asyncio.cluster import ClusterNode, RedisCluster

            # Build startup nodes for redis-py cluster
            startup_nodes = [
                ClusterNode(host=host, port=port) for host, port in self._startup_nodes
            ]

            # Connection kwargs
            kwargs: dict[str, Any] = {
                "encoding": "utf-8",
                "decode_responses": True,
                "max_connections": self._max_connections,
                "read_from_replicas": self._read_from_replicas,
            }

            if self._password:
                kwargs["password"] = self._password

            if self._ssl_enabled:
                kwargs["ssl"] = True

            # Create cluster client
            self._cluster = RedisCluster(
                startup_nodes=startup_nodes,
                **kwargs,
            )

            # Test connection
            await self._cluster.ping()
            self._connected = True

            logger.info(
                "Connected to Redis Cluster",
                extra={
                    "startup_nodes": [f"{h}:{p}" for h, p in self._startup_nodes],
                    "read_from_replicas": self._read_from_replicas,
                },
            )

        except ImportError as e:
            raise ConnectionError(
                "Redis cluster support requires redis-py[hiredis]. "
                "Install with: pip install redis[hiredis]"
            ) from e
        except Exception as e:
            logger.error(f"Failed to connect to Redis Cluster: {e}")
            raise ConnectionError(f"Cannot connect to Redis Cluster: {e}") from e

    async def disconnect(self) -> None:
        """Close all cluster connections."""
        with contextlib.suppress(Exception):
            if self._cluster:
                await self._cluster.aclose()
                self._cluster = None
            self._connected = False
            logger.info("Redis Cluster connections closed")

    def _ensure_connected(self) -> Any:
        """Ensure cluster client is connected.

        Returns:
            RedisCluster client instance

        Raises:
            RuntimeError: If not connected
        """
        if not self._connected or not self._cluster:
            raise RuntimeError("Redis Cluster not connected. Call connect() first.")
        return self._cluster

    async def health_check(self) -> ClusterHealthStatus:
        """Check cluster health and topology.

        Returns:
            ClusterHealthStatus with detailed cluster information
        """
        try:
            cluster = self._ensure_connected()

            # Get cluster info
            cluster_info = await cluster.cluster_info()
            cluster_state = cluster_info.get("cluster_state", "unknown")

            # Get cluster nodes
            nodes_info = await cluster.cluster_nodes()
            nodes: list[ClusterNodeInfo] = []
            masters = 0
            replicas = 0
            connected = 0

            for node_id, node_data in nodes_info.items():
                role = "master" if "master" in node_data.get("flags", "") else "replica"
                is_connected = "connected" in node_data.get("flags", "")

                if role == "master":
                    masters += 1
                else:
                    replicas += 1

                if is_connected:
                    connected += 1

                nodes.append(
                    ClusterNodeInfo(
                        host=node_data.get("host", ""),
                        port=node_data.get("port", 0),
                        node_id=node_id,
                        role=role,
                        is_connected=is_connected,
                    )
                )

            return ClusterHealthStatus(
                healthy=cluster_state == "ok",
                cluster_state=cluster_state,
                total_nodes=len(nodes),
                connected_nodes=connected,
                master_nodes=masters,
                replica_nodes=replicas,
                total_slots_covered=int(cluster_info.get("cluster_slots_ok", 0)),
                nodes=nodes,
            )

        except Exception as e:
            return ClusterHealthStatus(
                healthy=False,
                cluster_state="unknown",
                total_nodes=0,
                connected_nodes=0,
                master_nodes=0,
                replica_nodes=0,
                total_slots_covered=0,
                nodes=[],
                error=str(e),
            )

    # ==========================================================================
    # Key-Value Operations
    # ==========================================================================

    async def get(self, key: str) -> Any | None:
        """Get a value from the cluster.

        Args:
            key: Cache key

        Returns:
            Deserialized value or None if key doesn't exist
        """
        cluster = self._ensure_connected()
        value = await cluster.get(key)
        if value is not None:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        return None

    async def set(
        self,
        key: str,
        value: Any,
        expire: int | None = None,
        *,
        nx: bool = False,
    ) -> bool:
        """Set a value in the cluster.

        Args:
            key: Cache key
            value: Value to store (will be JSON-serialized)
            expire: Expiration time in seconds (optional)
            nx: Only set if key does not exist

        Returns:
            True if successful (False if nx=True and key exists)
        """
        cluster = self._ensure_connected()
        serialized = json.dumps(value)
        result = await cluster.set(key, serialized, ex=expire, nx=nx)
        return result is not None if nx else cast("bool", result)

    async def delete(self, *keys: str) -> int:
        """Delete one or more keys.

        Note: In cluster mode, keys may be on different nodes, so this
        operation is not atomic across all keys.

        Args:
            *keys: Keys to delete

        Returns:
            Number of keys deleted
        """
        cluster = self._ensure_connected()
        return cast("int", await cluster.delete(*keys))

    async def exists(self, *keys: str) -> int:
        """Check if keys exist.

        Args:
            *keys: Keys to check

        Returns:
            Number of keys that exist
        """
        cluster = self._ensure_connected()
        return cast("int", await cluster.exists(*keys))

    async def expire(self, key: str, seconds: int) -> bool:
        """Set TTL on a key.

        Args:
            key: Key to expire
            seconds: TTL in seconds

        Returns:
            True if timeout was set
        """
        cluster = self._ensure_connected()
        return cast("bool", await cluster.expire(key, seconds))

    # ==========================================================================
    # List Operations (Queue)
    # ==========================================================================

    async def lpush(self, key: str, *values: str) -> int:
        """Push values to the head of a list.

        Args:
            key: List key
            *values: Values to push

        Returns:
            Length of list after push
        """
        cluster = self._ensure_connected()
        return cast("int", await cluster.lpush(key, *values))

    async def rpush(self, key: str, *values: str) -> int:
        """Push values to the tail of a list.

        Args:
            key: List key
            *values: Values to push

        Returns:
            Length of list after push
        """
        cluster = self._ensure_connected()
        return cast("int", await cluster.rpush(key, *values))

    async def lpop(self, key: str) -> str | None:
        """Pop value from the head of a list.

        Args:
            key: List key

        Returns:
            Popped value or None if list is empty
        """
        cluster = self._ensure_connected()
        return cast("str | None", await cluster.lpop(key))

    async def llen(self, key: str) -> int:
        """Get length of a list.

        Args:
            key: List key

        Returns:
            Length of the list
        """
        cluster = self._ensure_connected()
        return cast("int", await cluster.llen(key))

    # Pub/Sub (Cluster-aware)  # noqa: ERA001

    async def publish(self, channel: str, message: Any) -> int:
        """Publish message to a channel.

        In cluster mode, pub/sub messages are broadcast to all nodes.

        Args:
            channel: Channel name
            message: Message to publish (will be JSON-serialized if not string)

        Returns:
            Number of subscribers that received the message
        """
        cluster = self._ensure_connected()
        serialized = json.dumps(message) if not isinstance(message, str) else message
        return cast("int", await cluster.publish(channel, serialized))

    # ==========================================================================
    # Cluster-specific Operations
    # ==========================================================================

    async def get_slot_for_key(self, key: str) -> int:
        """Get the cluster slot for a key.

        Useful for debugging key distribution.

        Args:
            key: Redis key

        Returns:
            Slot number (0-16383)
        """
        cluster = self._ensure_connected()
        return cast("int", await cluster.cluster_keyslot(key))

    async def get_node_for_key(self, key: str) -> ClusterNodeInfo | None:
        """Get the cluster node that owns a key's slot.

        Args:
            key: Redis key

        Returns:
            ClusterNodeInfo for the owning node, or None if not found
        """
        cluster = self._ensure_connected()
        slot = await self.get_slot_for_key(key)

        # Get slot owner
        slots_info = await cluster.cluster_slots()
        for slot_range in slots_info:
            start, end = slot_range[0], slot_range[1]
            if start <= slot <= end:
                master_info = slot_range[2]
                return ClusterNodeInfo(
                    host=master_info[0],
                    port=master_info[1],
                    role="master",
                    is_connected=True,
                )

        return None


# =============================================================================
# Global Cluster Client
# =============================================================================

_cluster_client: RedisClusterClient | None = None
_cluster_init_lock: asyncio.Lock | None = None


def _get_cluster_init_lock() -> asyncio.Lock:
    """Get the cluster initialization lock (lazy initialization)."""
    global _cluster_init_lock  # noqa: PLW0603
    if _cluster_init_lock is None:
        _cluster_init_lock = asyncio.Lock()
    return _cluster_init_lock


async def get_redis_cluster() -> RedisClusterClient:
    """Get the global Redis Cluster client.

    Initializes the client if not already connected.

    Returns:
        Connected RedisClusterClient instance

    Raises:
        RuntimeError: If cluster mode is not enabled
        ConnectionError: If unable to connect to cluster
    """
    global _cluster_client  # noqa: PLW0603

    settings = get_settings()
    if not settings.redis_cluster_enabled:
        raise RuntimeError(
            "Redis Cluster mode not enabled. Set REDIS_CLUSTER_ENABLED=true to use cluster."
        )

    # Fast path: already connected
    if _cluster_client is not None:
        return _cluster_client

    # Slow path: acquire lock and connect
    lock = _get_cluster_init_lock()
    async with lock:
        if _cluster_client is None:
            client = RedisClusterClient()
            await client.connect()
            _cluster_client = client

    return _cluster_client


async def close_redis_cluster() -> None:
    """Close the global Redis Cluster client."""
    global _cluster_client, _cluster_init_lock  # noqa: PLW0603

    if _cluster_client:
        await _cluster_client.disconnect()
        _cluster_client = None
    _cluster_init_lock = None


async def get_redis_cluster_optional() -> AsyncGenerator[RedisClusterClient | None]:
    """Get Redis Cluster client if cluster mode is enabled.

    FastAPI dependency that returns None instead of raising if cluster
    mode is not enabled.

    Yields:
        RedisClusterClient if cluster mode is enabled, None otherwise
    """
    settings = get_settings()
    client: RedisClusterClient | None = None

    if settings.redis_cluster_enabled:
        try:
            client = await get_redis_cluster()
        except Exception as e:
            logger.warning(f"Redis Cluster unavailable: {e}")
            client = None

    yield client
