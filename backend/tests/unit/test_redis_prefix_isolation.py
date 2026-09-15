"""Unit tests for the PrefixedRedis wrapper (mock-only, no services).

M3 Task 3 (audit 1.3): the real-Redis half of this module carried
@pytest.mark.integration (permanently skipped under /unit/ by the
root-conftest skip rule) and moved to
`backend/tests/integration/test_redis_prefix_isolation.py`.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.tests.integration.conftest import PrefixedRedis


class TestPrefixedRedisUnit:
    """Unit tests for PrefixedRedis that don't require real Redis."""

    def test_prefix_property(self) -> None:
        """Verify the prefix property returns the configured prefix."""
        mock_client = MagicMock()
        prefixed = PrefixedRedis(mock_client, prefix="test:gw0:")
        assert prefixed.prefix == "test:gw0:"

    def test_prefixed_key_single(self) -> None:
        """Verify _prefixed_key correctly prefixes a single key."""
        mock_client = MagicMock()
        prefixed = PrefixedRedis(mock_client, prefix="test:gw0:")

        assert prefixed._prefixed_key("foo") == "test:gw0:foo"
        assert prefixed._prefixed_key("bar:baz") == "test:gw0:bar:baz"
        assert prefixed._prefixed_key("") == "test:gw0:"

    def test_prefixed_keys_multiple(self) -> None:
        """Verify _prefixed_keys correctly prefixes multiple keys."""
        mock_client = MagicMock()
        prefixed = PrefixedRedis(mock_client, prefix="test:gw1:")

        keys = prefixed._prefixed_keys("a", "b", "c")
        assert keys == ["test:gw1:a", "test:gw1:b", "test:gw1:c"]

    def test_prefixed_keys_empty(self) -> None:
        """Verify _prefixed_keys handles empty input."""
        mock_client = MagicMock()
        prefixed = PrefixedRedis(mock_client, prefix="test:main:")

        keys = prefixed._prefixed_keys()
        assert keys == []

    @pytest.mark.asyncio
    async def test_get_calls_client_with_prefix(self) -> None:
        """Verify get calls the underlying client with prefixed key."""
        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value={"data": "value"})
        prefixed = PrefixedRedis(mock_client, prefix="test:gw0:")

        result = await prefixed.get("my_key")

        mock_client.get.assert_called_once_with("test:gw0:my_key")
        assert result == {"data": "value"}

    @pytest.mark.asyncio
    async def test_set_calls_client_with_prefix(self) -> None:
        """Verify set calls the underlying client with prefixed key."""
        mock_client = MagicMock()
        mock_client.set = AsyncMock(return_value=True)
        prefixed = PrefixedRedis(mock_client, prefix="test:gw0:")

        result = await prefixed.set("my_key", {"value": 42}, expire=300)

        mock_client.set.assert_called_once_with("test:gw0:my_key", {"value": 42}, 300, nx=False)
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_calls_client_with_prefixed_keys(self) -> None:
        """Verify delete calls the underlying client with prefixed keys."""
        mock_client = MagicMock()
        mock_client.delete = AsyncMock(return_value=2)
        prefixed = PrefixedRedis(mock_client, prefix="test:gw0:")

        result = await prefixed.delete("key1", "key2")

        mock_client.delete.assert_called_once_with("test:gw0:key1", "test:gw0:key2")
        assert result == 2

    @pytest.mark.asyncio
    async def test_exists_calls_client_with_prefixed_keys(self) -> None:
        """Verify exists calls the underlying client with prefixed keys."""
        mock_client = MagicMock()
        mock_client.exists = AsyncMock(return_value=1)
        prefixed = PrefixedRedis(mock_client, prefix="test:gw0:")

        result = await prefixed.exists("key1", "key2")

        mock_client.exists.assert_called_once_with("test:gw0:key1", "test:gw0:key2")
        assert result == 1

    @pytest.mark.asyncio
    async def test_lpush_calls_client_with_prefix(self) -> None:
        """Verify lpush calls the underlying client with prefixed key."""
        mock_client = MagicMock()
        mock_client.lpush = AsyncMock(return_value=2)
        prefixed = PrefixedRedis(mock_client, prefix="test:gw0:")

        result = await prefixed.lpush("my_list", "a", "b")

        mock_client.lpush.assert_called_once_with("test:gw0:my_list", "a", "b")
        assert result == 2

    @pytest.mark.asyncio
    async def test_zadd_calls_client_with_prefix(self) -> None:
        """Verify zadd calls the underlying client with prefixed key."""
        mock_client = MagicMock()
        mock_client.zadd = AsyncMock(return_value=2)
        prefixed = PrefixedRedis(mock_client, prefix="test:gw0:")

        result = await prefixed.zadd("my_zset", {"a": 1.0, "b": 2.0})

        mock_client.zadd.assert_called_once_with("test:gw0:my_zset", {"a": 1.0, "b": 2.0})
        assert result == 2

    @pytest.mark.asyncio
    async def test_publish_calls_client_with_prefix(self) -> None:
        """Verify publish calls the underlying client with prefixed channel."""
        mock_client = MagicMock()
        mock_client.publish = AsyncMock(return_value=1)
        prefixed = PrefixedRedis(mock_client, prefix="test:gw0:")

        result = await prefixed.publish("my_channel", {"event": "data"})

        mock_client.publish.assert_called_once_with("test:gw0:my_channel", {"event": "data"})
        assert result == 1

    @pytest.mark.asyncio
    async def test_health_check_passes_through(self) -> None:
        """Verify health_check doesn't modify anything (passthrough)."""
        mock_client = MagicMock()
        mock_client.health_check = AsyncMock(return_value={"status": "healthy", "connected": True})
        prefixed = PrefixedRedis(mock_client, prefix="test:gw0:")

        result = await prefixed.health_check()

        mock_client.health_check.assert_called_once_with()
        assert result == {"status": "healthy", "connected": True}

    @pytest.mark.asyncio
    async def test_add_to_queue_safe_prefixes_queue_and_dlq(self) -> None:
        """Verify add_to_queue_safe prefixes both queue name and DLQ name."""
        mock_client = MagicMock()
        mock_client.add_to_queue_safe = AsyncMock(return_value=MagicMock(success=True))
        prefixed = PrefixedRedis(mock_client, prefix="test:gw0:")

        await prefixed.add_to_queue_safe("my_queue", {"data": 1}, dlq_name="my_dlq")

        mock_client.add_to_queue_safe.assert_called_once_with(
            "test:gw0:my_queue",
            {"data": 1},
            None,
            None,
            "test:gw0:my_dlq",
        )

    @pytest.mark.asyncio
    async def test_add_to_queue_safe_with_no_dlq(self) -> None:
        """Verify add_to_queue_safe handles None DLQ correctly."""
        mock_client = MagicMock()
        mock_client.add_to_queue_safe = AsyncMock(return_value=MagicMock(success=True))
        prefixed = PrefixedRedis(mock_client, prefix="test:gw0:")

        await prefixed.add_to_queue_safe("my_queue", {"data": 1})

        mock_client.add_to_queue_safe.assert_called_once_with(
            "test:gw0:my_queue",
            {"data": 1},
            None,
            None,
            None,  # DLQ should be None, not prefixed
        )

    @pytest.mark.asyncio
    async def test_cleanup_scans_and_deletes_prefixed_keys(self) -> None:
        """Verify cleanup scans for prefixed keys and deletes them."""
        mock_redis_client = MagicMock()

        # Mock the internal Redis client with scan_iter
        mock_internal_client = AsyncMock()

        async def mock_scan_iter(*args, **kwargs):
            for key in ["test:gw0:key1", "test:gw0:key2", "test:gw0:list1"]:
                yield key

        mock_internal_client.scan_iter = mock_scan_iter
        mock_internal_client.delete = AsyncMock(return_value=3)

        mock_redis_client._client = mock_internal_client

        prefixed = PrefixedRedis(mock_redis_client, prefix="test:gw0:")
        deleted = await prefixed.cleanup()

        mock_internal_client.delete.assert_called_once_with(
            "test:gw0:key1", "test:gw0:key2", "test:gw0:list1"
        )
        assert deleted == 3
