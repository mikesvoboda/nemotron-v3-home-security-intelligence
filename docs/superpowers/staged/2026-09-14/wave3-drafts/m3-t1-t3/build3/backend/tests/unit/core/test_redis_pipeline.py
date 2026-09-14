"""Unit tests for Redis pipeline batching for multi-key operations (NEM-3763).

Tests cover:
- pipeline() context manager - Basic pipeline creation and execution
- batch_get() - Batched GET operations
- batch_set() - Batched SET operations
- batch_delete() - Batched DELETE operations
- batch_hgetall() - Batched hash operations
- Transaction support via MULTI/EXEC
- Error handling and partial failures

Uses mocks for Redis operations.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.core.redis import RedisClient

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def redis_client() -> RedisClient:
    """Create a RedisClient instance for testing.

    Returns a client with mock settings for pipeline testing.
    """
    with patch("backend.core.redis.get_settings") as mock_settings:
        mock_settings.return_value = MagicMock(
            redis_url="redis://localhost:6379/0",
            redis_ssl_enabled=False,
            redis_ssl_cert_reqs="required",
            redis_ssl_ca_certs=None,
            redis_ssl_certfile=None,
            redis_ssl_keyfile=None,
            redis_ssl_check_hostname=True,
            redis_password=None,
            redis_pool_dedicated_enabled=False,
            redis_pool_size=50,
            redis_pool_size_cache=20,
            redis_pool_size_queue=20,
            redis_pool_size_pubsub=10,
            redis_pool_size_ratelimit=10,
            redis_compression_enabled=False,
            redis_compression_threshold=1024,
        )
        client = RedisClient()
        # Mock the Redis client
        client._client = MagicMock()
        return client


@pytest.fixture
def mock_pipeline() -> MagicMock:
    """Create a mock Redis pipeline."""
    pipeline = MagicMock()
    pipeline.get = MagicMock(return_value=pipeline)
    pipeline.set = MagicMock(return_value=pipeline)
    pipeline.delete = MagicMock(return_value=pipeline)
    pipeline.hgetall = MagicMock(return_value=pipeline)
    pipeline.incr = MagicMock(return_value=pipeline)
    pipeline.expire = MagicMock(return_value=pipeline)
    pipeline.execute = AsyncMock(return_value=[])
    pipeline.__aenter__ = AsyncMock(return_value=pipeline)
    pipeline.__aexit__ = AsyncMock(return_value=None)
    return pipeline


# =============================================================================
# Pipeline Context Manager Tests
# =============================================================================


class TestPipelineContextManager:
    """Tests for the pipeline context manager."""

    @pytest.mark.asyncio
    async def test_pipeline_returns_context_manager(
        self, redis_client: RedisClient, mock_pipeline: MagicMock
    ) -> None:
        """Test that pipeline() returns an async context manager."""
        redis_client._client.pipeline = MagicMock(return_value=mock_pipeline)

        async with redis_client.pipeline() as pipe:
            assert pipe is mock_pipeline

    @pytest.mark.asyncio
    async def test_pipeline_auto_executes_on_exit(
        self, redis_client: RedisClient, mock_pipeline: MagicMock
    ) -> None:
        """Test that pipeline commands are executed on context exit."""
        mock_pipeline.execute = AsyncMock(return_value=["value1", "value2"])
        redis_client._client.pipeline = MagicMock(return_value=mock_pipeline)

        async with redis_client.pipeline() as pipe:
            pipe.get("key1")
            pipe.get("key2")

        mock_pipeline.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_pipeline_with_transaction(
        self, redis_client: RedisClient, mock_pipeline: MagicMock
    ) -> None:
        """Test that pipeline can be created with transaction=True."""
        redis_client._client.pipeline = MagicMock(return_value=mock_pipeline)

        async with redis_client.pipeline(transaction=True) as pipe:
            pipe.set("key1", "value1")
            pipe.set("key2", "value2")

        redis_client._client.pipeline.assert_called_once_with(transaction=True)


# =============================================================================
# batch_get Tests
# =============================================================================


class TestBatchGet:
    """Tests for batch_get() method."""

    @pytest.mark.asyncio
    async def test_batch_get_single_key(
        self, redis_client: RedisClient, mock_pipeline: MagicMock
    ) -> None:
        """Test batch_get with a single key."""
        mock_pipeline.execute = AsyncMock(return_value=['{"id": 1}'])
        redis_client._client.pipeline = MagicMock(return_value=mock_pipeline)

        results = await redis_client.batch_get(["key1"])

        assert results == [{"id": 1}]
        mock_pipeline.get.assert_called_once_with("key1")

    @pytest.mark.asyncio
    async def test_batch_get_multiple_keys(
        self, redis_client: RedisClient, mock_pipeline: MagicMock
    ) -> None:
        """Test batch_get with multiple keys."""
        mock_pipeline.execute = AsyncMock(return_value=['{"id": 1}', '{"id": 2}', '{"id": 3}'])
        redis_client._client.pipeline = MagicMock(return_value=mock_pipeline)

        results = await redis_client.batch_get(["key1", "key2", "key3"])

        assert results == [{"id": 1}, {"id": 2}, {"id": 3}]
        assert mock_pipeline.get.call_count == 3

    @pytest.mark.asyncio
    async def test_batch_get_with_missing_keys(
        self, redis_client: RedisClient, mock_pipeline: MagicMock
    ) -> None:
        """Test batch_get handles missing keys (returns None)."""
        mock_pipeline.execute = AsyncMock(return_value=['{"id": 1}', None, '{"id": 3}'])
        redis_client._client.pipeline = MagicMock(return_value=mock_pipeline)

        results = await redis_client.batch_get(["key1", "key2", "key3"])

        assert results == [{"id": 1}, None, {"id": 3}]

    @pytest.mark.asyncio
    async def test_batch_get_empty_list(self, redis_client: RedisClient) -> None:
        """Test batch_get with empty key list."""
        results = await redis_client.batch_get([])

        assert results == []

    @pytest.mark.asyncio
    async def test_batch_get_preserves_order(
        self, redis_client: RedisClient, mock_pipeline: MagicMock
    ) -> None:
        """Test that batch_get preserves key order in results."""
        mock_pipeline.execute = AsyncMock(
            return_value=['{"name": "a"}', '{"name": "b"}', '{"name": "c"}']
        )
        redis_client._client.pipeline = MagicMock(return_value=mock_pipeline)

        results = await redis_client.batch_get(["key_a", "key_b", "key_c"])

        assert results[0]["name"] == "a"
        assert results[1]["name"] == "b"
        assert results[2]["name"] == "c"


# =============================================================================
# batch_set Tests
# =============================================================================


class TestBatchSet:
    """Tests for batch_set() method."""

    @pytest.mark.asyncio
    async def test_batch_set_single_item(
        self, redis_client: RedisClient, mock_pipeline: MagicMock
    ) -> None:
        """Test batch_set with a single key-value pair."""
        mock_pipeline.execute = AsyncMock(return_value=[True])
        redis_client._client.pipeline = MagicMock(return_value=mock_pipeline)

        result = await redis_client.batch_set({"key1": {"id": 1}})

        assert result is True
        mock_pipeline.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_batch_set_multiple_items(
        self, redis_client: RedisClient, mock_pipeline: MagicMock
    ) -> None:
        """Test batch_set with multiple key-value pairs."""
        mock_pipeline.execute = AsyncMock(return_value=[True, True, True])
        redis_client._client.pipeline = MagicMock(return_value=mock_pipeline)

        result = await redis_client.batch_set(
            {
                "key1": {"id": 1},
                "key2": {"id": 2},
                "key3": {"id": 3},
            }
        )

        assert result is True
        assert mock_pipeline.set.call_count == 3

    @pytest.mark.asyncio
    async def test_batch_set_with_ttl(
        self, redis_client: RedisClient, mock_pipeline: MagicMock
    ) -> None:
        """Test batch_set with TTL for all keys."""
        mock_pipeline.execute = AsyncMock(return_value=[True, True])
        redis_client._client.pipeline = MagicMock(return_value=mock_pipeline)

        await redis_client.batch_set({"key1": {"id": 1}, "key2": {"id": 2}}, expire=300)

        # Verify set was called with expiration
        calls = mock_pipeline.set.call_args_list
        for call in calls:
            assert call[1].get("ex") == 300

    @pytest.mark.asyncio
    async def test_batch_set_empty_dict(self, redis_client: RedisClient) -> None:
        """Test batch_set with empty dictionary."""
        result = await redis_client.batch_set({})

        assert result is True


# =============================================================================
# batch_delete Tests
# =============================================================================


class TestBatchDelete:
    """Tests for batch_delete() method."""

    @pytest.mark.asyncio
    async def test_batch_delete_single_key(
        self, redis_client: RedisClient, mock_pipeline: MagicMock
    ) -> None:
        """Test batch_delete with a single key."""
        mock_pipeline.execute = AsyncMock(return_value=[1])
        redis_client._client.pipeline = MagicMock(return_value=mock_pipeline)

        count = await redis_client.batch_delete(["key1"])

        assert count == 1
        mock_pipeline.delete.assert_called_once_with("key1")

    @pytest.mark.asyncio
    async def test_batch_delete_multiple_keys(
        self, redis_client: RedisClient, mock_pipeline: MagicMock
    ) -> None:
        """Test batch_delete with multiple keys."""
        mock_pipeline.execute = AsyncMock(return_value=[1, 1, 0])  # 0 = key didn't exist
        redis_client._client.pipeline = MagicMock(return_value=mock_pipeline)

        count = await redis_client.batch_delete(["key1", "key2", "key3"])

        assert count == 2  # Only 2 keys were actually deleted
        assert mock_pipeline.delete.call_count == 3

    @pytest.mark.asyncio
    async def test_batch_delete_empty_list(self, redis_client: RedisClient) -> None:
        """Test batch_delete with empty key list."""
        count = await redis_client.batch_delete([])

        assert count == 0


# =============================================================================
# batch_hgetall Tests
# =============================================================================


class TestBatchHGetAll:
    """Tests for batch_hgetall() method for hash operations."""

    @pytest.mark.asyncio
    async def test_batch_hgetall_single_key(
        self, redis_client: RedisClient, mock_pipeline: MagicMock
    ) -> None:
        """Test batch_hgetall with a single hash key."""
        mock_pipeline.execute = AsyncMock(return_value=[{"field1": "value1", "field2": "value2"}])
        redis_client._client.pipeline = MagicMock(return_value=mock_pipeline)

        results = await redis_client.batch_hgetall(["hash:1"])

        assert results == [{"field1": "value1", "field2": "value2"}]
        mock_pipeline.hgetall.assert_called_once_with("hash:1")

    @pytest.mark.asyncio
    async def test_batch_hgetall_multiple_keys(
        self, redis_client: RedisClient, mock_pipeline: MagicMock
    ) -> None:
        """Test batch_hgetall with multiple hash keys."""
        mock_pipeline.execute = AsyncMock(
            return_value=[
                {"id": "1", "name": "item1"},
                {"id": "2", "name": "item2"},
            ]
        )
        redis_client._client.pipeline = MagicMock(return_value=mock_pipeline)

        results = await redis_client.batch_hgetall(["hash:1", "hash:2"])

        assert len(results) == 2
        assert results[0]["id"] == "1"
        assert results[1]["id"] == "2"

    @pytest.mark.asyncio
    async def test_batch_hgetall_with_missing_keys(
        self, redis_client: RedisClient, mock_pipeline: MagicMock
    ) -> None:
        """Test batch_hgetall handles missing hash keys."""
        mock_pipeline.execute = AsyncMock(
            return_value=[{"id": "1"}, {}, {"id": "3"}]  # Empty dict for missing
        )
        redis_client._client.pipeline = MagicMock(return_value=mock_pipeline)

        results = await redis_client.batch_hgetall(["hash:1", "hash:2", "hash:3"])

        assert results[0] == {"id": "1"}
        assert results[1] == {}  # Missing key returns empty dict
        assert results[2] == {"id": "3"}

    @pytest.mark.asyncio
    async def test_batch_hgetall_empty_list(self, redis_client: RedisClient) -> None:
        """Test batch_hgetall with empty key list."""
        results = await redis_client.batch_hgetall([])

        assert results == []


# =============================================================================
# batch_incr Tests
# =============================================================================


class TestBatchIncr:
    """Tests for batch_incr() method."""

    @pytest.mark.asyncio
    async def test_batch_incr_single_key(
        self, redis_client: RedisClient, mock_pipeline: MagicMock
    ) -> None:
        """Test batch_incr with a single key."""
        mock_pipeline.execute = AsyncMock(return_value=[5])
        redis_client._client.pipeline = MagicMock(return_value=mock_pipeline)

        results = await redis_client.batch_incr(["counter:1"])

        assert results == [5]
        mock_pipeline.incr.assert_called_once_with("counter:1")

    @pytest.mark.asyncio
    async def test_batch_incr_multiple_keys(
        self, redis_client: RedisClient, mock_pipeline: MagicMock
    ) -> None:
        """Test batch_incr with multiple keys."""
        mock_pipeline.execute = AsyncMock(return_value=[1, 5, 10])
        redis_client._client.pipeline = MagicMock(return_value=mock_pipeline)

        results = await redis_client.batch_incr(["c1", "c2", "c3"])

        assert results == [1, 5, 10]
        assert mock_pipeline.incr.call_count == 3

    @pytest.mark.asyncio
    async def test_batch_incr_empty_list(self, redis_client: RedisClient) -> None:
        """Test batch_incr with empty key list."""
        results = await redis_client.batch_incr([])

        assert results == []


# =============================================================================
# batch_exists Tests
# =============================================================================


class TestBatchExists:
    """Tests for batch_exists() method."""

    @pytest.mark.asyncio
    async def test_batch_exists_all_exist(
        self, redis_client: RedisClient, mock_pipeline: MagicMock
    ) -> None:
        """Test batch_exists when all keys exist."""
        mock_pipeline.exists = MagicMock(return_value=mock_pipeline)
        mock_pipeline.execute = AsyncMock(return_value=[1, 1, 1])
        redis_client._client.pipeline = MagicMock(return_value=mock_pipeline)

        results = await redis_client.batch_exists(["key1", "key2", "key3"])

        assert results == [True, True, True]

    @pytest.mark.asyncio
    async def test_batch_exists_mixed(
        self, redis_client: RedisClient, mock_pipeline: MagicMock
    ) -> None:
        """Test batch_exists with some missing keys."""
        mock_pipeline.exists = MagicMock(return_value=mock_pipeline)
        mock_pipeline.execute = AsyncMock(return_value=[1, 0, 1])
        redis_client._client.pipeline = MagicMock(return_value=mock_pipeline)

        results = await redis_client.batch_exists(["key1", "key2", "key3"])

        assert results == [True, False, True]

    @pytest.mark.asyncio
    async def test_batch_exists_empty_list(self, redis_client: RedisClient) -> None:
        """Test batch_exists with empty key list."""
        results = await redis_client.batch_exists([])

        assert results == []


# =============================================================================
# Transaction Tests
# =============================================================================


class TestPipelineTransactions:
    """Tests for pipeline transaction support (MULTI/EXEC)."""

    @pytest.mark.asyncio
    async def test_transaction_mode_multi_exec(
        self, redis_client: RedisClient, mock_pipeline: MagicMock
    ) -> None:
        """Test that transaction mode wraps commands in MULTI/EXEC."""
        mock_pipeline.execute = AsyncMock(return_value=[True, True])
        redis_client._client.pipeline = MagicMock(return_value=mock_pipeline)

        async with redis_client.pipeline(transaction=True) as pipe:
            pipe.set("key1", "value1")
            pipe.set("key2", "value2")

        # Verify pipeline was created with transaction=True
        redis_client._client.pipeline.assert_called_with(transaction=True)

    @pytest.mark.asyncio
    async def test_batch_set_atomic(
        self, redis_client: RedisClient, mock_pipeline: MagicMock
    ) -> None:
        """Test batch_set with atomic=True uses transaction."""
        mock_pipeline.execute = AsyncMock(return_value=[True, True])
        redis_client._client.pipeline = MagicMock(return_value=mock_pipeline)

        await redis_client.batch_set({"key1": "value1", "key2": "value2"}, atomic=True)

        redis_client._client.pipeline.assert_called_with(transaction=True)


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestPipelineErrorHandling:
    """Tests for error handling in pipeline operations."""

    @pytest.mark.asyncio
    async def test_pipeline_partial_failure(
        self, redis_client: RedisClient, mock_pipeline: MagicMock
    ) -> None:
        """Test handling of partial failures in pipeline."""
        from redis.exceptions import ResponseError

        # Simulate partial failure - one command fails
        mock_pipeline.execute = AsyncMock(
            return_value=['{"id": 1}', ResponseError("WRONGTYPE"), '{"id": 3}']
        )
        redis_client._client.pipeline = MagicMock(return_value=mock_pipeline)

        results = await redis_client.batch_get(["key1", "key2", "key3"])

        # Should handle the error gracefully
        assert results[0] == {"id": 1}
        assert results[1] is None  # Error converted to None
        assert results[2] == {"id": 3}

    @pytest.mark.asyncio
    async def test_pipeline_connection_error(
        self, redis_client: RedisClient, mock_pipeline: MagicMock
    ) -> None:
        """Test that connection errors propagate correctly."""
        from redis.exceptions import ConnectionError

        mock_pipeline.execute = AsyncMock(side_effect=ConnectionError("Connection lost"))
        redis_client._client.pipeline = MagicMock(return_value=mock_pipeline)

        with pytest.raises(ConnectionError):
            await redis_client.batch_get(["key1", "key2"])


# =============================================================================
# Performance Optimization Tests
# =============================================================================


class TestPipelinePerformance:
    """Tests for pipeline performance characteristics."""

    @pytest.mark.asyncio
    async def test_single_round_trip_for_batch_get(
        self, redis_client: RedisClient, mock_pipeline: MagicMock
    ) -> None:
        """Test that batch_get uses only one round-trip."""
        mock_pipeline.execute = AsyncMock(return_value=["v1", "v2", "v3"])
        redis_client._client.pipeline = MagicMock(return_value=mock_pipeline)

        await redis_client.batch_get(["k1", "k2", "k3"])

        # Execute should only be called once
        mock_pipeline.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_large_batch_operation(
        self, redis_client: RedisClient, mock_pipeline: MagicMock
    ) -> None:
        """Test pipeline with large number of keys."""
        num_keys = 1000
        mock_pipeline.execute = AsyncMock(return_value=[f'{{"id": {i}}}' for i in range(num_keys)])
        redis_client._client.pipeline = MagicMock(return_value=mock_pipeline)

        keys = [f"key:{i}" for i in range(num_keys)]
        results = await redis_client.batch_get(keys)

        assert len(results) == num_keys
        # Still only one execute call
        mock_pipeline.execute.assert_called_once()


# =============================================================================
# Chunk Processing Tests
# =============================================================================


class TestPipelineChunking:
    """Tests for pipeline chunking to avoid memory issues."""

    @pytest.mark.asyncio
    async def test_batch_get_with_chunk_size(
        self, redis_client: RedisClient, mock_pipeline: MagicMock
    ) -> None:
        """Test that large batches are chunked."""
        # Create a fresh mock for each pipeline() call
        call_count = 0

        def create_mock_pipeline(transaction: bool = False):
            nonlocal call_count
            call_count += 1
            pipe = MagicMock()
            pipe.get = MagicMock(return_value=pipe)
            pipe.execute = AsyncMock(return_value=[f'{{"chunk": {call_count}}}' for _ in range(50)])
            pipe.__aenter__ = AsyncMock(return_value=pipe)
            pipe.__aexit__ = AsyncMock(return_value=None)
            return pipe

        redis_client._client.pipeline = MagicMock(side_effect=create_mock_pipeline)

        keys = [f"key:{i}" for i in range(100)]
        results = await redis_client.batch_get(keys, chunk_size=50)

        # Should have created 2 pipelines (2 chunks of 50)
        assert redis_client._client.pipeline.call_count == 2
        assert len(results) == 100


# =============================================================================
# Mixed Operations Tests
# =============================================================================


class TestMixedPipelineOperations:
    """Tests for pipelines with mixed operation types."""

    @pytest.mark.asyncio
    async def test_pipeline_mixed_operations(
        self, redis_client: RedisClient, mock_pipeline: MagicMock
    ) -> None:
        """Test pipeline with different command types."""
        mock_pipeline.execute = AsyncMock(
            return_value=['{"id": 1}', True, 5]  # get, set, incr results
        )
        redis_client._client.pipeline = MagicMock(return_value=mock_pipeline)

        async with redis_client.pipeline() as pipe:
            pipe.get("cache:key")
            pipe.set("cache:new", "value")
            pipe.incr("counter:visits")

        # All operations should be batched in one execute
        mock_pipeline.execute.assert_called_once()
