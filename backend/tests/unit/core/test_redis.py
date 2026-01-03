"""Unit tests for Redis client operations.

Tests cover:
- add_to_queue_safe() - Backpressure handling with REJECT, DLQ, DROP_OLDEST policies
- Queue operations: add_to_queue(), get_from_queue(), pop_from_queue_nonblocking(),
  get_queue_length(), peek_queue(), clear_queue()
- Pub/Sub: publish(), subscribe(), subscribe_dedicated(), listen()
- SSL/TLS context creation (_create_ssl_context())
- Health check endpoint behavior
- Cache operations: get(), set(), delete(), exists(), expire()
- Connection and initialization lifecycle

Uses mocks for Redis operations to ensure isolation.
"""

import ssl
import warnings
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.core.redis import (
    QueueAddResult,
    QueueOverflowPolicy,
    QueuePressureMetrics,
    RedisClient,
    close_redis,
    get_redis,
    get_redis_optional,
    init_redis,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_settings() -> MagicMock:
    """Create mock settings for testing."""
    return MagicMock(
        redis_url="redis://localhost:6379/0",
        redis_ssl_enabled=False,
        redis_ssl_cert_reqs="required",
        redis_ssl_ca_certs=None,
        redis_ssl_certfile=None,
        redis_ssl_keyfile=None,
        redis_ssl_check_hostname=True,
        queue_max_size=1000,
        queue_overflow_policy="reject",
        queue_backpressure_threshold=0.8,
    )


@pytest.fixture
def redis_client(mock_settings: MagicMock) -> RedisClient:
    """Create a RedisClient instance for testing."""
    with patch("backend.core.redis.get_settings", return_value=mock_settings):
        return RedisClient()


@pytest.fixture
def connected_redis_client(redis_client: RedisClient) -> RedisClient:
    """Create a RedisClient with mocked connection."""
    mock_redis = AsyncMock()
    mock_redis.rpush = AsyncMock(return_value=1)
    mock_redis.llen = AsyncMock(return_value=0)
    mock_redis.blpop = AsyncMock(return_value=None)
    mock_redis.lpop = AsyncMock(return_value=None)
    mock_redis.lrange = AsyncMock(return_value=[])
    mock_redis.ltrim = AsyncMock(return_value=True)
    mock_redis.delete = AsyncMock(return_value=1)
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.set = AsyncMock(return_value=True)
    mock_redis.exists = AsyncMock(return_value=0)
    mock_redis.expire = AsyncMock(return_value=True)
    mock_redis.publish = AsyncMock(return_value=1)
    mock_redis.ping = AsyncMock(return_value=True)
    mock_redis.info = AsyncMock(return_value={"redis_version": "7.0.0"})
    mock_redis.pubsub = MagicMock()
    redis_client._client = mock_redis
    return redis_client


# =============================================================================
# QueueAddResult Tests
# =============================================================================


class TestQueueAddResult:
    """Tests for QueueAddResult dataclass."""

    def test_success_result_no_backpressure(self) -> None:
        """Test successful result without backpressure."""
        result = QueueAddResult(success=True, queue_length=10)
        assert result.success is True
        assert result.queue_length == 10
        assert result.dropped_count == 0
        assert result.moved_to_dlq_count == 0
        assert result.error is None
        assert result.warning is None
        assert result.had_backpressure is False

    def test_result_with_dropped_items(self) -> None:
        """Test result with dropped items indicates backpressure."""
        result = QueueAddResult(success=True, queue_length=100, dropped_count=5)
        assert result.had_backpressure is True

    def test_result_with_dlq_items(self) -> None:
        """Test result with DLQ items indicates backpressure."""
        result = QueueAddResult(success=True, queue_length=100, moved_to_dlq_count=3)
        assert result.had_backpressure is True

    def test_result_with_error(self) -> None:
        """Test result with error indicates backpressure."""
        result = QueueAddResult(success=False, queue_length=1000, error="Queue full")
        assert result.had_backpressure is True

    def test_result_with_warning(self) -> None:
        """Test result with warning but no backpressure."""
        result = QueueAddResult(success=True, queue_length=100, warning="Approaching limit")
        assert result.had_backpressure is False


# =============================================================================
# Queue Operations Tests
# =============================================================================


class TestAddToQueue:
    """Tests for add_to_queue method (legacy, deprecated)."""

    @pytest.mark.asyncio
    async def test_add_to_queue_emits_deprecation_warning(
        self, connected_redis_client: RedisClient
    ) -> None:
        """Test that add_to_queue emits deprecation warning."""
        connected_redis_client._client.rpush = AsyncMock(return_value=1)

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            await connected_redis_client.add_to_queue("test_queue", {"key": "value"})

        assert len(w) == 1
        assert issubclass(w[0].category, DeprecationWarning)
        assert "add_to_queue_safe" in str(w[0].message)

    @pytest.mark.asyncio
    async def test_add_to_queue_serializes_dict(self, connected_redis_client: RedisClient) -> None:
        """Test that dict data is JSON serialized."""
        mock_client = connected_redis_client._client
        mock_client.rpush = AsyncMock(return_value=1)

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            await connected_redis_client.add_to_queue("test_queue", {"key": "value"})

        call_args = mock_client.rpush.call_args[0]
        assert call_args[0] == "test_queue"
        assert call_args[1] == '{"key": "value"}'

    @pytest.mark.asyncio
    async def test_add_to_queue_string_not_double_serialized(
        self, connected_redis_client: RedisClient
    ) -> None:
        """Test that string data is not double serialized."""
        mock_client = connected_redis_client._client
        mock_client.rpush = AsyncMock(return_value=1)

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            await connected_redis_client.add_to_queue("test_queue", "already a string")

        call_args = mock_client.rpush.call_args[0]
        assert call_args[1] == "already a string"

    @pytest.mark.asyncio
    async def test_add_to_queue_trims_when_oversized(
        self, connected_redis_client: RedisClient
    ) -> None:
        """Test that queue is trimmed when it exceeds max_size."""
        mock_client = connected_redis_client._client
        mock_client.rpush = AsyncMock(return_value=150)  # Queue is now 150 items
        mock_client.ltrim = AsyncMock(return_value=True)

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            await connected_redis_client.add_to_queue("test_queue", "data", max_size=100)

        mock_client.ltrim.assert_called_once_with("test_queue", -100, -1)

    @pytest.mark.asyncio
    async def test_add_to_queue_no_trim_when_disabled(
        self, connected_redis_client: RedisClient
    ) -> None:
        """Test that queue is not trimmed when max_size=0."""
        mock_client = connected_redis_client._client
        mock_client.rpush = AsyncMock(return_value=1000)
        mock_client.ltrim = AsyncMock()

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            await connected_redis_client.add_to_queue("test_queue", "data", max_size=0)

        mock_client.ltrim.assert_not_called()


class TestAddToQueueSafe:
    """Tests for add_to_queue_safe method with backpressure handling."""

    @pytest.mark.asyncio
    async def test_add_success_below_threshold(
        self, connected_redis_client: RedisClient, mock_settings: MagicMock
    ) -> None:
        """Test successful add when queue is below threshold."""
        mock_client = connected_redis_client._client
        mock_client.llen = AsyncMock(return_value=100)  # 10% of 1000
        mock_client.rpush = AsyncMock(return_value=101)

        with patch("backend.core.redis.get_settings", return_value=mock_settings):
            result = await connected_redis_client.add_to_queue_safe("test_queue", {"data": "value"})

        assert result.success is True
        assert result.queue_length == 101
        assert result.dropped_count == 0
        assert result.moved_to_dlq_count == 0
        assert result.error is None

    @pytest.mark.asyncio
    async def test_add_logs_warning_at_pressure_threshold(
        self, connected_redis_client: RedisClient, mock_settings: MagicMock
    ) -> None:
        """Test that warning is logged when queue reaches pressure threshold."""
        mock_client = connected_redis_client._client
        mock_client.llen = AsyncMock(return_value=850)  # 85% of 1000
        mock_client.rpush = AsyncMock(return_value=851)

        with (
            patch("backend.core.redis.get_settings", return_value=mock_settings),
            patch("backend.core.redis.logger") as mock_logger,
        ):
            result = await connected_redis_client.add_to_queue_safe("test_queue", {"data": "value"})

        assert result.success is True
        mock_logger.warning.assert_called()
        warning_msg = str(mock_logger.warning.call_args)
        assert "pressure warning" in warning_msg

    @pytest.mark.asyncio
    async def test_reject_policy_when_queue_full(
        self, connected_redis_client: RedisClient, mock_settings: MagicMock
    ) -> None:
        """Test REJECT policy rejects items when queue is full."""
        mock_client = connected_redis_client._client
        mock_client.llen = AsyncMock(return_value=1000)  # Queue is full

        with (
            patch("backend.core.redis.get_settings", return_value=mock_settings),
            patch("backend.core.redis.record_queue_overflow") as mock_overflow,
            patch("backend.core.redis.record_queue_items_rejected") as mock_rejected,
        ):
            result = await connected_redis_client.add_to_queue_safe(
                "test_queue",
                {"data": "value"},
                overflow_policy=QueueOverflowPolicy.REJECT,
            )

        assert result.success is False
        assert result.queue_length == 1000
        assert "full" in result.error.lower()
        mock_overflow.assert_called_once()
        mock_rejected.assert_called_once()

    @pytest.mark.asyncio
    async def test_dlq_policy_moves_oldest_to_dlq(
        self, connected_redis_client: RedisClient, mock_settings: MagicMock
    ) -> None:
        """Test DLQ policy moves oldest items to dead-letter queue."""
        mock_client = connected_redis_client._client
        mock_client.llen = AsyncMock(return_value=1000)  # Queue is full
        mock_client.lpop = AsyncMock(return_value='{"old": "data"}')
        mock_client.rpush = AsyncMock(return_value=1000)

        with (
            patch("backend.core.redis.get_settings", return_value=mock_settings),
            patch("backend.core.redis.record_queue_overflow") as mock_overflow,
            patch("backend.core.redis.record_queue_items_moved_to_dlq") as mock_moved,
        ):
            result = await connected_redis_client.add_to_queue_safe(
                "test_queue",
                {"data": "value"},
                max_size=1000,
                overflow_policy=QueueOverflowPolicy.DLQ,
                dlq_name="dlq:test_queue",
            )

        assert result.success is True
        assert result.moved_to_dlq_count == 1
        mock_overflow.assert_called_once()
        mock_moved.assert_called_once()

    @pytest.mark.asyncio
    async def test_drop_oldest_policy_trims_queue(
        self, connected_redis_client: RedisClient, mock_settings: MagicMock
    ) -> None:
        """Test DROP_OLDEST policy trims queue to max_size."""
        mock_client = connected_redis_client._client
        mock_client.llen = AsyncMock(return_value=1000)  # Queue is full
        mock_client.rpush = AsyncMock(return_value=1001)  # After adding
        mock_client.ltrim = AsyncMock(return_value=True)

        with (
            patch("backend.core.redis.get_settings", return_value=mock_settings),
            patch("backend.core.redis.record_queue_overflow") as mock_overflow,
            patch("backend.core.redis.record_queue_items_dropped") as mock_dropped,
        ):
            result = await connected_redis_client.add_to_queue_safe(
                "test_queue",
                {"data": "value"},
                max_size=1000,
                overflow_policy=QueueOverflowPolicy.DROP_OLDEST,
            )

        assert result.success is True
        assert result.dropped_count == 1
        mock_client.ltrim.assert_called_once_with("test_queue", -1000, -1)
        mock_overflow.assert_called_once()
        mock_dropped.assert_called_once()

    @pytest.mark.asyncio
    async def test_string_overflow_policy_normalized(
        self, connected_redis_client: RedisClient, mock_settings: MagicMock
    ) -> None:
        """Test that string overflow policy is normalized to enum."""
        mock_client = connected_redis_client._client
        mock_client.llen = AsyncMock(return_value=1000)

        with patch("backend.core.redis.get_settings", return_value=mock_settings):
            result = await connected_redis_client.add_to_queue_safe(
                "test_queue",
                {"data": "value"},
                overflow_policy="REJECT",  # Uppercase string
            )

        assert result.success is False
        assert "full" in result.error.lower()

    @pytest.mark.asyncio
    async def test_invalid_policy_defaults_to_reject(
        self, connected_redis_client: RedisClient, mock_settings: MagicMock
    ) -> None:
        """Test that invalid policy string defaults to REJECT."""
        mock_client = connected_redis_client._client
        mock_client.llen = AsyncMock(return_value=1000)

        with patch("backend.core.redis.get_settings", return_value=mock_settings):
            result = await connected_redis_client.add_to_queue_safe(
                "test_queue",
                {"data": "value"},
                overflow_policy="invalid_policy",
            )

        assert result.success is False


class TestGetFromQueue:
    """Tests for get_from_queue method."""

    @pytest.mark.asyncio
    async def test_get_from_queue_returns_deserialized_json(
        self, connected_redis_client: RedisClient
    ) -> None:
        """Test that JSON data is deserialized."""
        mock_client = connected_redis_client._client
        mock_client.blpop = AsyncMock(return_value=("test_queue", '{"key": "value"}'))

        result = await connected_redis_client.get_from_queue("test_queue", timeout=5)

        assert result == {"key": "value"}

    @pytest.mark.asyncio
    async def test_get_from_queue_returns_string_on_json_error(
        self, connected_redis_client: RedisClient
    ) -> None:
        """Test that non-JSON data is returned as string."""
        mock_client = connected_redis_client._client
        mock_client.blpop = AsyncMock(return_value=("test_queue", "not json"))

        result = await connected_redis_client.get_from_queue("test_queue", timeout=5)

        assert result == "not json"

    @pytest.mark.asyncio
    async def test_get_from_queue_returns_none_on_timeout(
        self, connected_redis_client: RedisClient
    ) -> None:
        """Test that None is returned on timeout."""
        mock_client = connected_redis_client._client
        mock_client.blpop = AsyncMock(return_value=None)

        result = await connected_redis_client.get_from_queue("test_queue", timeout=1)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_from_queue_enforces_minimum_timeout(
        self, connected_redis_client: RedisClient
    ) -> None:
        """Test that minimum timeout of 5 seconds is enforced."""
        mock_client = connected_redis_client._client
        mock_client.blpop = AsyncMock(return_value=None)

        await connected_redis_client.get_from_queue("test_queue", timeout=0)

        # Should use minimum timeout of 5 seconds
        call_kwargs = mock_client.blpop.call_args[1]
        assert call_kwargs["timeout"] == 5


class TestPopFromQueueNonblocking:
    """Tests for pop_from_queue_nonblocking method."""

    @pytest.mark.asyncio
    async def test_pop_returns_deserialized_json(self, connected_redis_client: RedisClient) -> None:
        """Test that JSON data is deserialized."""
        mock_client = connected_redis_client._client
        mock_client.lpop = AsyncMock(return_value='{"key": "value"}')

        result = await connected_redis_client.pop_from_queue_nonblocking("test_queue")

        assert result == {"key": "value"}

    @pytest.mark.asyncio
    async def test_pop_returns_string_on_json_error(
        self, connected_redis_client: RedisClient
    ) -> None:
        """Test that non-JSON data is returned as string."""
        mock_client = connected_redis_client._client
        mock_client.lpop = AsyncMock(return_value="plain string")

        result = await connected_redis_client.pop_from_queue_nonblocking("test_queue")

        assert result == "plain string"

    @pytest.mark.asyncio
    async def test_pop_returns_none_when_empty(self, connected_redis_client: RedisClient) -> None:
        """Test that None is returned when queue is empty."""
        mock_client = connected_redis_client._client
        mock_client.lpop = AsyncMock(return_value=None)

        result = await connected_redis_client.pop_from_queue_nonblocking("test_queue")

        assert result is None


class TestGetQueueLength:
    """Tests for get_queue_length method."""

    @pytest.mark.asyncio
    async def test_get_queue_length_returns_count(
        self, connected_redis_client: RedisClient
    ) -> None:
        """Test that queue length is returned."""
        mock_client = connected_redis_client._client
        mock_client.llen = AsyncMock(return_value=42)

        result = await connected_redis_client.get_queue_length("test_queue")

        assert result == 42
        mock_client.llen.assert_called_once_with("test_queue")


class TestPeekQueue:
    """Tests for peek_queue method."""

    @pytest.mark.asyncio
    async def test_peek_returns_deserialized_items(
        self, connected_redis_client: RedisClient
    ) -> None:
        """Test that items are deserialized from JSON."""
        mock_client = connected_redis_client._client
        mock_client.lrange = AsyncMock(return_value=['{"a": 1}', '{"b": 2}', '{"c": 3}'])

        result = await connected_redis_client.peek_queue("test_queue", start=0, end=2)

        assert result == [{"a": 1}, {"b": 2}, {"c": 3}]

    @pytest.mark.asyncio
    async def test_peek_returns_string_on_json_error(
        self, connected_redis_client: RedisClient
    ) -> None:
        """Test that non-JSON items are returned as strings."""
        mock_client = connected_redis_client._client
        mock_client.lrange = AsyncMock(return_value=["not json", '{"valid": true}'])

        result = await connected_redis_client.peek_queue("test_queue")

        assert result == ["not json", {"valid": True}]

    @pytest.mark.asyncio
    async def test_peek_respects_max_items(self, connected_redis_client: RedisClient) -> None:
        """Test that max_items caps the range."""
        mock_client = connected_redis_client._client
        mock_client.lrange = AsyncMock(return_value=[])

        await connected_redis_client.peek_queue("test_queue", start=0, end=-1, max_items=50)

        mock_client.lrange.assert_called_once_with("test_queue", 0, 49)


class TestClearQueue:
    """Tests for clear_queue method."""

    @pytest.mark.asyncio
    async def test_clear_queue_returns_true_when_deleted(
        self, connected_redis_client: RedisClient
    ) -> None:
        """Test that True is returned when queue exists."""
        mock_client = connected_redis_client._client
        mock_client.delete = AsyncMock(return_value=1)

        result = await connected_redis_client.clear_queue("test_queue")

        assert result is True

    @pytest.mark.asyncio
    async def test_clear_queue_returns_false_when_not_exists(
        self, connected_redis_client: RedisClient
    ) -> None:
        """Test that False is returned when queue doesn't exist."""
        mock_client = connected_redis_client._client
        mock_client.delete = AsyncMock(return_value=0)

        result = await connected_redis_client.clear_queue("test_queue")

        assert result is False


class TestQueuePressure:
    """Tests for get_queue_pressure method."""

    @pytest.mark.asyncio
    async def test_queue_pressure_metrics(
        self, connected_redis_client: RedisClient, mock_settings: MagicMock
    ) -> None:
        """Test that pressure metrics are calculated correctly."""
        mock_client = connected_redis_client._client
        mock_client.llen = AsyncMock(return_value=500)

        with patch("backend.core.redis.get_settings", return_value=mock_settings):
            result = await connected_redis_client.get_queue_pressure("test_queue", max_size=1000)

        assert isinstance(result, QueuePressureMetrics)
        assert result.queue_name == "test_queue"
        assert result.current_length == 500
        assert result.max_size == 1000
        assert result.fill_ratio == 0.5
        assert result.is_at_pressure_threshold is False
        assert result.is_full is False

    @pytest.mark.asyncio
    async def test_queue_pressure_at_threshold(
        self, connected_redis_client: RedisClient, mock_settings: MagicMock
    ) -> None:
        """Test pressure at threshold (80%)."""
        mock_client = connected_redis_client._client
        mock_client.llen = AsyncMock(return_value=800)

        with patch("backend.core.redis.get_settings", return_value=mock_settings):
            result = await connected_redis_client.get_queue_pressure("test_queue", max_size=1000)

        assert result.is_at_pressure_threshold is True
        assert result.is_full is False

    @pytest.mark.asyncio
    async def test_queue_pressure_when_full(
        self, connected_redis_client: RedisClient, mock_settings: MagicMock
    ) -> None:
        """Test pressure when queue is full."""
        mock_client = connected_redis_client._client
        mock_client.llen = AsyncMock(return_value=1000)

        with patch("backend.core.redis.get_settings", return_value=mock_settings):
            result = await connected_redis_client.get_queue_pressure("test_queue", max_size=1000)

        assert result.is_at_pressure_threshold is True
        assert result.is_full is True


# =============================================================================
# Pub/Sub Tests
# =============================================================================


class TestPubSub:
    """Tests for Pub/Sub operations."""

    def test_get_pubsub_creates_shared_instance(self, connected_redis_client: RedisClient) -> None:
        """Test that get_pubsub creates a shared PubSub instance."""
        mock_client = connected_redis_client._client
        mock_pubsub = MagicMock()
        mock_client.pubsub = MagicMock(return_value=mock_pubsub)

        pubsub1 = connected_redis_client.get_pubsub()
        pubsub2 = connected_redis_client.get_pubsub()

        assert pubsub1 is pubsub2
        mock_client.pubsub.assert_called_once()

    def test_create_pubsub_creates_new_instance(self, connected_redis_client: RedisClient) -> None:
        """Test that create_pubsub creates a new PubSub instance each time."""
        mock_client = connected_redis_client._client
        mock_client.pubsub = MagicMock(side_effect=[MagicMock(), MagicMock()])

        pubsub1 = connected_redis_client.create_pubsub()
        pubsub2 = connected_redis_client.create_pubsub()

        assert pubsub1 is not pubsub2
        assert mock_client.pubsub.call_count == 2

    @pytest.mark.asyncio
    async def test_publish_serializes_message(self, connected_redis_client: RedisClient) -> None:
        """Test that publish serializes dict messages."""
        mock_client = connected_redis_client._client
        mock_client.publish = AsyncMock(return_value=3)

        result = await connected_redis_client.publish("channel", {"event": "test"})

        assert result == 3
        mock_client.publish.assert_called_once_with("channel", '{"event": "test"}')

    @pytest.mark.asyncio
    async def test_publish_string_not_double_serialized(
        self, connected_redis_client: RedisClient
    ) -> None:
        """Test that string messages are not double serialized."""
        mock_client = connected_redis_client._client
        mock_client.publish = AsyncMock(return_value=1)

        await connected_redis_client.publish("channel", "plain message")

        mock_client.publish.assert_called_once_with("channel", "plain message")

    @pytest.mark.asyncio
    async def test_subscribe_returns_pubsub(self, connected_redis_client: RedisClient) -> None:
        """Test that subscribe returns PubSub instance."""
        mock_pubsub = AsyncMock()
        mock_pubsub.subscribe = AsyncMock()
        connected_redis_client._pubsub = mock_pubsub

        result = await connected_redis_client.subscribe("channel1", "channel2")

        assert result is mock_pubsub
        mock_pubsub.subscribe.assert_called_once_with("channel1", "channel2")

    @pytest.mark.asyncio
    async def test_subscribe_dedicated_creates_new_pubsub(
        self, connected_redis_client: RedisClient
    ) -> None:
        """Test that subscribe_dedicated creates a new PubSub."""
        mock_pubsub = AsyncMock()
        mock_pubsub.subscribe = AsyncMock()
        connected_redis_client._client.pubsub = MagicMock(return_value=mock_pubsub)

        result = await connected_redis_client.subscribe_dedicated("channel")

        assert result is mock_pubsub
        mock_pubsub.subscribe.assert_called_once_with("channel")

    @pytest.mark.asyncio
    async def test_unsubscribe_calls_pubsub(self, connected_redis_client: RedisClient) -> None:
        """Test that unsubscribe calls PubSub.unsubscribe."""
        mock_pubsub = AsyncMock()
        mock_pubsub.unsubscribe = AsyncMock()
        connected_redis_client._pubsub = mock_pubsub

        await connected_redis_client.unsubscribe("channel1", "channel2")

        mock_pubsub.unsubscribe.assert_called_once_with("channel1", "channel2")

    @pytest.mark.asyncio
    async def test_unsubscribe_noop_when_no_pubsub(
        self, connected_redis_client: RedisClient
    ) -> None:
        """Test that unsubscribe is a no-op when PubSub is None."""
        connected_redis_client._pubsub = None

        # Should not raise
        await connected_redis_client.unsubscribe("channel")

    @pytest.mark.asyncio
    async def test_listen_yields_messages(self, connected_redis_client: RedisClient) -> None:
        """Test that listen yields deserialized messages."""

        async def mock_listen() -> Any:
            yield {"type": "subscribe", "channel": "test", "data": 1}
            yield {"type": "message", "channel": "test", "data": '{"event": "test"}'}
            yield {"type": "message", "channel": "test", "data": "plain string"}

        mock_pubsub = AsyncMock()
        mock_pubsub.listen = mock_listen

        messages = []
        async for message in connected_redis_client.listen(mock_pubsub):
            messages.append(message)

        # Only message type events should be yielded
        assert len(messages) == 2
        assert messages[0]["data"] == {"event": "test"}
        assert messages[1]["data"] == "plain string"


# =============================================================================
# SSL/TLS Tests
# =============================================================================


class TestSSLContext:
    """Tests for SSL context creation."""

    def test_ssl_disabled_returns_none(self, mock_settings: MagicMock) -> None:
        """Test that None is returned when SSL is disabled."""
        mock_settings.redis_ssl_enabled = False

        with patch("backend.core.redis.get_settings", return_value=mock_settings):
            client = RedisClient()
            result = client._create_ssl_context()

        assert result is None

    def test_ssl_enabled_creates_context(self, mock_settings: MagicMock) -> None:
        """Test that SSL context is created when enabled."""
        mock_settings.redis_ssl_enabled = True
        mock_settings.redis_ssl_ca_certs = None
        mock_settings.redis_ssl_certfile = None

        with patch("backend.core.redis.get_settings", return_value=mock_settings):
            client = RedisClient()
            result = client._create_ssl_context()

        assert isinstance(result, ssl.SSLContext)

    def test_ssl_cert_reqs_none(self, mock_settings: MagicMock) -> None:
        """Test SSL with CERT_NONE verification mode."""
        mock_settings.redis_ssl_enabled = True
        mock_settings.redis_ssl_cert_reqs = "none"

        with patch("backend.core.redis.get_settings", return_value=mock_settings):
            client = RedisClient()
            result = client._create_ssl_context()

        assert result.verify_mode == ssl.CERT_NONE
        assert result.check_hostname is False

    def test_ssl_cert_reqs_optional(self, mock_settings: MagicMock) -> None:
        """Test SSL with CERT_OPTIONAL verification mode."""
        mock_settings.redis_ssl_enabled = True
        mock_settings.redis_ssl_cert_reqs = "optional"
        mock_settings.redis_ssl_check_hostname = False

        with patch("backend.core.redis.get_settings", return_value=mock_settings):
            client = RedisClient()
            result = client._create_ssl_context()

        assert result.verify_mode == ssl.CERT_OPTIONAL

    def test_ssl_cert_reqs_required(self, mock_settings: MagicMock) -> None:
        """Test SSL with CERT_REQUIRED verification mode."""
        mock_settings.redis_ssl_enabled = True
        mock_settings.redis_ssl_cert_reqs = "required"

        with patch("backend.core.redis.get_settings", return_value=mock_settings):
            client = RedisClient()
            result = client._create_ssl_context()

        assert result.verify_mode == ssl.CERT_REQUIRED

    def test_ssl_ca_certs_not_found_raises(self, mock_settings: MagicMock) -> None:
        """Test that missing CA cert file raises FileNotFoundError."""
        mock_settings.redis_ssl_enabled = True
        mock_settings.redis_ssl_ca_certs = "/nonexistent/ca.crt"

        with patch("backend.core.redis.get_settings", return_value=mock_settings):
            client = RedisClient()

            with pytest.raises(FileNotFoundError) as exc_info:
                client._create_ssl_context()

        assert "CA certificate" in str(exc_info.value)

    def test_ssl_client_cert_not_found_raises(self, mock_settings: MagicMock) -> None:
        """Test that missing client cert file raises FileNotFoundError."""
        mock_settings.redis_ssl_enabled = True
        mock_settings.redis_ssl_certfile = "/nonexistent/client.crt"

        with patch("backend.core.redis.get_settings", return_value=mock_settings):
            client = RedisClient()

            with pytest.raises(FileNotFoundError) as exc_info:
                client._create_ssl_context()

        assert "client certificate" in str(exc_info.value)

    def test_ssl_client_key_not_found_raises(self, mock_settings: MagicMock) -> None:
        """Test that missing client key file raises FileNotFoundError."""
        mock_settings.redis_ssl_enabled = True

        # Create a temporary cert file
        with NamedTemporaryFile(mode="w", suffix=".crt", delete=False) as f:
            f.write("dummy cert")
            cert_path = f.name

        mock_settings.redis_ssl_certfile = cert_path
        mock_settings.redis_ssl_keyfile = "/nonexistent/client.key"

        try:
            with patch("backend.core.redis.get_settings", return_value=mock_settings):
                client = RedisClient()

                with pytest.raises(FileNotFoundError) as exc_info:
                    client._create_ssl_context()

            assert "client key" in str(exc_info.value)
        finally:
            Path(cert_path).unlink()


# =============================================================================
# Health Check Tests
# =============================================================================


class TestHealthCheck:
    """Tests for health check functionality."""

    @pytest.mark.asyncio
    async def test_health_check_healthy(self, connected_redis_client: RedisClient) -> None:
        """Test health check returns healthy status."""
        mock_client = connected_redis_client._client
        mock_client.ping = AsyncMock(return_value=True)
        mock_client.info = AsyncMock(return_value={"redis_version": "7.2.0"})

        result = await connected_redis_client.health_check()

        assert result["status"] == "healthy"
        assert result["connected"] is True
        assert result["redis_version"] == "7.2.0"

    @pytest.mark.asyncio
    async def test_health_check_unhealthy_on_ping_failure(
        self, connected_redis_client: RedisClient
    ) -> None:
        """Test health check returns unhealthy on ping failure."""
        mock_client = connected_redis_client._client
        mock_client.ping = AsyncMock(side_effect=Exception("Connection lost"))

        result = await connected_redis_client.health_check()

        assert result["status"] == "unhealthy"
        assert result["connected"] is False
        assert "Connection lost" in result["error"]

    @pytest.mark.asyncio
    async def test_health_check_not_connected_raises(self, redis_client: RedisClient) -> None:
        """Test health check raises when not connected."""
        # Client is not connected (_client is None)
        result = await redis_client.health_check()

        assert result["status"] == "unhealthy"
        assert result["connected"] is False


# =============================================================================
# Cache Operations Tests
# =============================================================================


class TestCacheOperations:
    """Tests for cache get/set operations."""

    @pytest.mark.asyncio
    async def test_get_returns_deserialized_value(
        self, connected_redis_client: RedisClient
    ) -> None:
        """Test that get returns deserialized JSON value."""
        mock_client = connected_redis_client._client
        mock_client.get = AsyncMock(return_value='{"key": "value"}')

        result = await connected_redis_client.get("test_key")

        assert result == {"key": "value"}

    @pytest.mark.asyncio
    async def test_get_returns_string_on_json_error(
        self, connected_redis_client: RedisClient
    ) -> None:
        """Test that get returns string on JSON decode error."""
        mock_client = connected_redis_client._client
        mock_client.get = AsyncMock(return_value="not json")

        result = await connected_redis_client.get("test_key")

        assert result == "not json"

    @pytest.mark.asyncio
    async def test_get_returns_none_for_missing_key(
        self, connected_redis_client: RedisClient
    ) -> None:
        """Test that get returns None for missing key."""
        mock_client = connected_redis_client._client
        mock_client.get = AsyncMock(return_value=None)

        result = await connected_redis_client.get("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_set_serializes_value(self, connected_redis_client: RedisClient) -> None:
        """Test that set serializes value as JSON."""
        mock_client = connected_redis_client._client
        mock_client.set = AsyncMock(return_value=True)

        result = await connected_redis_client.set("test_key", {"key": "value"})

        assert result is True
        mock_client.set.assert_called_once_with("test_key", '{"key": "value"}', ex=None)

    @pytest.mark.asyncio
    async def test_set_with_expiration(self, connected_redis_client: RedisClient) -> None:
        """Test that set respects expiration time."""
        mock_client = connected_redis_client._client
        mock_client.set = AsyncMock(return_value=True)

        await connected_redis_client.set("test_key", "value", expire=3600)

        mock_client.set.assert_called_once_with("test_key", '"value"', ex=3600)

    @pytest.mark.asyncio
    async def test_delete_returns_count(self, connected_redis_client: RedisClient) -> None:
        """Test that delete returns count of deleted keys."""
        mock_client = connected_redis_client._client
        mock_client.delete = AsyncMock(return_value=2)

        result = await connected_redis_client.delete("key1", "key2")

        assert result == 2

    @pytest.mark.asyncio
    async def test_exists_returns_count(self, connected_redis_client: RedisClient) -> None:
        """Test that exists returns count of existing keys."""
        mock_client = connected_redis_client._client
        mock_client.exists = AsyncMock(return_value=1)

        result = await connected_redis_client.exists("key1", "key2")

        assert result == 1

    @pytest.mark.asyncio
    async def test_expire_sets_ttl(self, connected_redis_client: RedisClient) -> None:
        """Test that expire sets TTL on key."""
        mock_client = connected_redis_client._client
        mock_client.expire = AsyncMock(return_value=True)

        result = await connected_redis_client.expire("test_key", 3600)

        assert result is True
        mock_client.expire.assert_called_once_with("test_key", 3600)


# =============================================================================
# Connection Lifecycle Tests
# =============================================================================


class TestConnectionLifecycle:
    """Tests for connection and disconnection lifecycle."""

    @pytest.mark.asyncio
    async def test_ensure_connected_raises_when_not_connected(
        self, redis_client: RedisClient
    ) -> None:
        """Test that _ensure_connected raises when not connected."""
        with pytest.raises(RuntimeError) as exc_info:
            redis_client._ensure_connected()

        assert "not connected" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_ensure_connected_returns_client(
        self, connected_redis_client: RedisClient
    ) -> None:
        """Test that _ensure_connected returns client when connected."""
        result = connected_redis_client._ensure_connected()

        assert result is connected_redis_client._client

    @pytest.mark.asyncio
    async def test_disconnect_cleans_up_resources(
        self, connected_redis_client: RedisClient
    ) -> None:
        """Test that disconnect cleans up all resources."""
        mock_pubsub = AsyncMock()
        mock_pubsub.aclose = AsyncMock()
        connected_redis_client._pubsub = mock_pubsub

        mock_client = connected_redis_client._client
        mock_client.aclose = AsyncMock()

        mock_pool = AsyncMock()
        mock_pool.disconnect = AsyncMock()
        connected_redis_client._pool = mock_pool

        await connected_redis_client.disconnect()

        assert connected_redis_client._pubsub is None
        assert connected_redis_client._client is None
        assert connected_redis_client._pool is None


# =============================================================================
# Module-Level Functions Tests
# =============================================================================


class TestModuleFunctions:
    """Tests for module-level functions."""

    @pytest.mark.asyncio
    async def test_init_redis_creates_client(self, mock_settings: MagicMock) -> None:
        """Test that init_redis creates and connects a client."""
        # Reset global state
        import backend.core.redis as redis_module

        redis_module._redis_client = None
        redis_module._redis_init_lock = None

        mock_client = AsyncMock()
        mock_client.connect = AsyncMock()

        with (
            patch("backend.core.redis.get_settings", return_value=mock_settings),
            patch("backend.core.redis.RedisClient", return_value=mock_client),
        ):
            result = await init_redis()

        assert result is mock_client
        mock_client.connect.assert_called_once()

        # Cleanup
        redis_module._redis_client = None

    @pytest.mark.asyncio
    async def test_close_redis_disconnects_client(self, mock_settings: MagicMock) -> None:
        """Test that close_redis disconnects the client."""
        import backend.core.redis as redis_module

        mock_client = AsyncMock()
        mock_client.disconnect = AsyncMock()
        redis_module._redis_client = mock_client

        await close_redis()

        mock_client.disconnect.assert_called_once()
        assert redis_module._redis_client is None

    @pytest.mark.asyncio
    async def test_get_redis_dependency_yields_client(self, mock_settings: MagicMock) -> None:
        """Test that get_redis dependency yields the client."""
        import backend.core.redis as redis_module

        mock_client = AsyncMock()
        redis_module._redis_client = mock_client

        async for client in get_redis():
            assert client is mock_client
            break

        # Cleanup
        redis_module._redis_client = None

    @pytest.mark.asyncio
    async def test_get_redis_optional_returns_none_on_error(self, mock_settings: MagicMock) -> None:
        """Test that get_redis_optional returns None on connection error."""
        from redis.exceptions import ConnectionError

        import backend.core.redis as redis_module

        redis_module._redis_client = None
        redis_module._redis_init_lock = None

        mock_client = MagicMock()
        mock_client.connect = AsyncMock(side_effect=ConnectionError("Failed"))

        with (
            patch("backend.core.redis.get_settings", return_value=mock_settings),
            patch("backend.core.redis.RedisClient", return_value=mock_client),
        ):
            async for client in get_redis_optional():
                assert client is None
                break

        # Cleanup
        redis_module._redis_client = None
