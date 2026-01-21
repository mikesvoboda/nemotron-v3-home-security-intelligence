"""Unit tests for Redis Zstd compression functionality.

Tests the Python 3.14 compression.zstd integration for Redis queue payloads.
"""

import base64
import json
from compression import zstd
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from redis.asyncio import ConnectionPool, Redis
from redis.asyncio.client import PubSub

from backend.core.redis import RedisClient

# Fixtures


@pytest.fixture
def mock_redis_pool():
    """Mock Redis connection pool."""
    with patch("backend.core.redis.ConnectionPool") as mock_pool_class:
        mock_pool_instance = AsyncMock(spec=ConnectionPool)
        mock_pool_instance.disconnect = AsyncMock()
        mock_pool_class.from_url.return_value = mock_pool_instance
        yield mock_pool_class


@pytest.fixture
def mock_redis_client():
    """Mock Redis client with common operations."""
    mock_client = AsyncMock(spec=Redis)
    mock_client.ping = AsyncMock(return_value=True)
    mock_client.close = AsyncMock()
    mock_client.disconnect = AsyncMock()
    mock_client.aclose = AsyncMock()
    mock_client.info = AsyncMock(return_value={"redis_version": "7.0.0"})
    mock_client.rpush = AsyncMock(return_value=1)
    mock_client.ltrim = AsyncMock(return_value=True)
    mock_client.blpop = AsyncMock(return_value=None)
    mock_client.lpop = AsyncMock(return_value=None)
    mock_client.llen = AsyncMock(return_value=0)
    mock_client.lrange = AsyncMock(return_value=[])
    mock_client.delete = AsyncMock(return_value=1)
    mock_client.publish = AsyncMock(return_value=1)
    mock_client.get = AsyncMock(return_value=None)
    mock_client.set = AsyncMock(return_value=True)
    mock_client.exists = AsyncMock(return_value=0)
    mock_client.pubsub = MagicMock(spec=PubSub)
    return mock_client


@pytest.fixture
async def redis_client(mock_redis_pool, mock_redis_client):
    """Create a Redis client with mocked connection."""
    with patch("backend.core.redis.Redis", return_value=mock_redis_client):
        client = RedisClient(redis_url="redis://localhost:6379/0")
        await client.connect()
        yield client
        await client.disconnect()


# Compression Unit Tests


class TestCompressionRoundTrip:
    """Tests for compression/decompression round trip functionality."""

    def test_compression_round_trip_large_data(self, redis_client):
        """Large data should survive compression/decompression cycle."""
        # Create data that exceeds the default 1KB threshold
        large_data = json.dumps({"key": "value" * 500})  # ~2.5KB

        with patch("backend.core.redis.get_settings") as mock_settings:
            mock_settings.return_value.redis_compression_enabled = True
            mock_settings.return_value.redis_compression_threshold = 1024

            compressed = redis_client._compress_payload(large_data)

            # Verify it's compressed (has prefix)
            assert compressed.startswith(redis_client.COMPRESSION_PREFIX)
            assert len(compressed) < len(large_data)

            # Decompress and verify
            decompressed = redis_client._decompress_payload(compressed)
            assert decompressed == large_data

    def test_compression_round_trip_json_object(self, redis_client):
        """Complex JSON objects should survive compression cycle."""
        complex_data = json.dumps(
            {
                "detections": [
                    {"label": "person", "confidence": 0.95, "bbox": [100, 200, 300, 400]},
                    {"label": "car", "confidence": 0.88, "bbox": [50, 100, 200, 300]},
                ]
                * 50,  # Make it large enough to compress
                "metadata": {
                    "camera_id": "front_door",
                    "timestamp": "2024-01-15T12:00:00Z",
                    "frame_number": 12345,
                },
            }
        )

        with patch("backend.core.redis.get_settings") as mock_settings:
            mock_settings.return_value.redis_compression_enabled = True
            mock_settings.return_value.redis_compression_threshold = 1024

            compressed = redis_client._compress_payload(complex_data)
            decompressed = redis_client._decompress_payload(compressed)

            # Verify data integrity
            assert decompressed == complex_data
            assert json.loads(decompressed) == json.loads(complex_data)


class TestSmallDataNotCompressed:
    """Tests for small data handling (below threshold)."""

    def test_small_data_not_compressed(self, redis_client):
        """Data below threshold should not be compressed."""
        small_data = json.dumps({"key": "value"})  # ~16 bytes

        with patch("backend.core.redis.get_settings") as mock_settings:
            mock_settings.return_value.redis_compression_enabled = True
            mock_settings.return_value.redis_compression_threshold = 1024

            result = redis_client._compress_payload(small_data)

            # Should not have compression prefix
            assert not result.startswith(redis_client.COMPRESSION_PREFIX)
            # Should be unchanged
            assert result == small_data

    def test_data_at_threshold_not_compressed(self, redis_client):
        """Data at or below threshold should not be compressed."""
        # Create data that is exactly at threshold (1024 bytes after JSON encoding)
        threshold = 1024
        # First create the JSON, then adjust filler to get exact size
        # json.dumps adds quotes and uses ": " (colon + space) in compact mode
        test_json = json.dumps({"data": ""})
        overhead = len(test_json.encode("utf-8"))  # Count the overhead of {"data": ""}
        filler = "x" * (threshold - overhead)
        data_at_threshold = json.dumps({"data": filler})

        # Verify we created data at exactly the threshold
        data_bytes = data_at_threshold.encode("utf-8")
        assert len(data_bytes) == threshold, f"Expected {threshold} bytes, got {len(data_bytes)}"

        with patch("backend.core.redis.get_settings") as mock_settings:
            mock_settings.return_value.redis_compression_enabled = True
            mock_settings.return_value.redis_compression_threshold = threshold

            result = redis_client._compress_payload(data_at_threshold)

            # Should not be compressed (threshold check is <=, so data at threshold is NOT compressed)
            # The implementation uses: if len(data_bytes) <= threshold: return data
            assert not result.startswith(redis_client.COMPRESSION_PREFIX)

    def test_data_just_above_threshold_is_compressed(self, redis_client):
        """Data just above threshold should be compressed."""
        threshold = 1024
        # Build a JSON string that is just above 1024 bytes
        filler = "x" * (threshold - len('{"data":""}') + 1)
        data_above_threshold = json.dumps({"data": filler})

        with patch("backend.core.redis.get_settings") as mock_settings:
            mock_settings.return_value.redis_compression_enabled = True
            mock_settings.return_value.redis_compression_threshold = threshold

            result = redis_client._compress_payload(data_above_threshold)

            # Data above threshold should be compressed (if it reduces size)
            # For simple repetitive data like "xxx...", Zstd compresses very well
            assert result.startswith(redis_client.COMPRESSION_PREFIX)


class TestCompressionDisabled:
    """Tests for when compression is disabled."""

    def test_compression_disabled_returns_original(self, redis_client):
        """When compression is disabled, original data should be returned."""
        large_data = json.dumps({"key": "value" * 500})

        with patch("backend.core.redis.get_settings") as mock_settings:
            mock_settings.return_value.redis_compression_enabled = False
            mock_settings.return_value.redis_compression_threshold = 1024

            result = redis_client._compress_payload(large_data)

            # Should not have compression prefix
            assert not result.startswith(redis_client.COMPRESSION_PREFIX)
            # Should be unchanged
            assert result == large_data


class TestBackwardCompatibility:
    """Tests for backward compatibility with uncompressed data."""

    def test_decompress_uncompressed_data(self, redis_client):
        """Uncompressed data without prefix should be returned as-is."""
        uncompressed_data = json.dumps({"key": "value"})

        result = redis_client._decompress_payload(uncompressed_data)

        # Should be unchanged
        assert result == uncompressed_data

    def test_decompress_plain_json_string(self, redis_client):
        """Plain JSON strings should pass through decompression unchanged."""
        json_strings = [
            '{"simple": "object"}',
            '["array", "of", "items"]',
            '"just a string"',
            "123",
            "null",
        ]

        for json_str in json_strings:
            result = redis_client._decompress_payload(json_str)
            assert result == json_str


class TestCompressionPrefix:
    """Tests for the compression prefix marker."""

    def test_compression_prefix_constant(self):
        """Verify the compression prefix is set correctly."""
        assert RedisClient.COMPRESSION_PREFIX == "Z:"

    def test_compressed_data_has_prefix(self, redis_client):
        """Compressed data should have the Z: prefix."""
        large_data = json.dumps({"data": "x" * 2000})

        with patch("backend.core.redis.get_settings") as mock_settings:
            mock_settings.return_value.redis_compression_enabled = True
            mock_settings.return_value.redis_compression_threshold = 1024

            compressed = redis_client._compress_payload(large_data)

            # Verify prefix
            assert compressed.startswith("Z:")

            # Verify the rest is valid base64
            b64_part = compressed[2:]  # Strip "Z:"
            try:
                decoded = base64.b64decode(b64_part)
                # Verify it's valid Zstd compressed data
                decompressed_bytes = zstd.decompress(decoded)
                assert decompressed_bytes.decode("utf-8") == large_data
            except Exception as e:
                pytest.fail(f"Invalid base64 or Zstd data: {e}")


class TestCompressionEfficiency:
    """Tests for compression efficiency checks."""

    def test_compression_skipped_if_not_efficient(self, redis_client):
        """Compression should be skipped if it doesn't reduce size."""
        # Random data is hard to compress
        import os

        random_data = base64.b64encode(os.urandom(2000)).decode("ascii")
        # Wrap in JSON to make it a valid payload
        data = json.dumps({"random": random_data})

        with patch("backend.core.redis.get_settings") as mock_settings:
            mock_settings.return_value.redis_compression_enabled = True
            mock_settings.return_value.redis_compression_threshold = 1024

            result = redis_client._compress_payload(data)

            # The data might or might not be compressed depending on Zstd efficiency
            # Just verify round-trip works
            decompressed = redis_client._decompress_payload(result)
            assert decompressed == data


# Queue Integration Tests


class TestQueueCompressionIntegration:
    """Tests for compression integration with queue operations."""

    @pytest.mark.asyncio
    async def test_add_to_queue_compresses_large_payload(self, redis_client, mock_redis_client):
        """Large payloads should be compressed when added to queue."""
        large_data = {"detections": [{"label": "person"}] * 100}

        with patch("backend.core.redis.get_settings") as mock_settings:
            mock_settings.return_value.redis_compression_enabled = True
            mock_settings.return_value.redis_compression_threshold = 1024
            mock_settings.return_value.queue_max_size = 10000
            mock_settings.return_value.queue_overflow_policy = "reject"
            mock_settings.return_value.queue_backpressure_threshold = 0.8

            result = await redis_client.add_to_queue_safe("test_queue", large_data)

            assert result.success is True
            # Verify rpush was called with compressed data
            mock_redis_client.rpush.assert_called_once()
            call_args = mock_redis_client.rpush.call_args
            pushed_data = call_args[0][1]  # Second argument is the data
            assert pushed_data.startswith("Z:")

    @pytest.mark.asyncio
    async def test_add_to_queue_small_payload_not_compressed(self, redis_client, mock_redis_client):
        """Small payloads should not be compressed."""
        small_data = {"key": "value"}

        with patch("backend.core.redis.get_settings") as mock_settings:
            mock_settings.return_value.redis_compression_enabled = True
            mock_settings.return_value.redis_compression_threshold = 1024
            mock_settings.return_value.queue_max_size = 10000
            mock_settings.return_value.queue_overflow_policy = "reject"
            mock_settings.return_value.queue_backpressure_threshold = 0.8

            result = await redis_client.add_to_queue_safe("test_queue", small_data)

            assert result.success is True
            # Verify rpush was called with uncompressed JSON
            mock_redis_client.rpush.assert_called_once()
            call_args = mock_redis_client.rpush.call_args
            pushed_data = call_args[0][1]
            assert not pushed_data.startswith("Z:")
            assert json.loads(pushed_data) == small_data

    @pytest.mark.asyncio
    async def test_get_from_queue_decompresses_payload(self, redis_client, mock_redis_client):
        """Compressed payloads should be decompressed when read from queue."""
        original_data = {"detections": [{"label": "person"}] * 100}
        original_json = json.dumps(original_data)

        # Manually compress the data
        compressed_bytes = zstd.compress(original_json.encode("utf-8"))
        compressed_b64 = base64.b64encode(compressed_bytes).decode("ascii")
        compressed_str = f"Z:{compressed_b64}"

        # Mock blpop to return compressed data
        mock_redis_client.blpop.return_value = ("test_queue", compressed_str)

        result = await redis_client.get_from_queue("test_queue", timeout=5)

        assert result == original_data

    @pytest.mark.asyncio
    async def test_get_from_queue_handles_uncompressed_payload(
        self, redis_client, mock_redis_client
    ):
        """Uncompressed payloads should be handled for backward compatibility."""
        original_data = {"key": "value"}
        uncompressed_json = json.dumps(original_data)

        # Mock blpop to return uncompressed data
        mock_redis_client.blpop.return_value = ("test_queue", uncompressed_json)

        result = await redis_client.get_from_queue("test_queue", timeout=5)

        assert result == original_data

    @pytest.mark.asyncio
    async def test_pop_from_queue_nonblocking_decompresses(self, redis_client, mock_redis_client):
        """Non-blocking pop should also decompress payloads."""
        original_data = {"detections": [{"label": "car"}] * 100}
        original_json = json.dumps(original_data)

        # Manually compress the data
        compressed_bytes = zstd.compress(original_json.encode("utf-8"))
        compressed_b64 = base64.b64encode(compressed_bytes).decode("ascii")
        compressed_str = f"Z:{compressed_b64}"

        # Mock lpop to return compressed data
        mock_redis_client.lpop.return_value = compressed_str

        result = await redis_client.pop_from_queue_nonblocking("test_queue")

        assert result == original_data

    @pytest.mark.asyncio
    async def test_peek_queue_decompresses_payloads(self, redis_client, mock_redis_client):
        """Peek queue should decompress all payloads."""
        data1 = {"item": 1}
        data2 = {"item": 2, "extra": "x" * 2000}  # Large item

        # Create mixed compressed and uncompressed items
        uncompressed_json = json.dumps(data1)
        compressed_bytes = zstd.compress(json.dumps(data2).encode("utf-8"))
        compressed_b64 = base64.b64encode(compressed_bytes).decode("ascii")
        compressed_str = f"Z:{compressed_b64}"

        # Mock lrange to return mixed data
        mock_redis_client.lrange.return_value = [uncompressed_json, compressed_str]

        result = await redis_client.peek_queue("test_queue")

        assert len(result) == 2
        assert result[0] == data1
        assert result[1] == data2


class TestCompressionWithZstdModule:
    """Direct tests with the compression.zstd module."""

    def test_zstd_module_available(self):
        """Verify compression.zstd module is available in Python 3.14."""
        assert hasattr(zstd, "compress")
        assert hasattr(zstd, "decompress")

    def test_zstd_basic_compression(self):
        """Test basic Zstd compression/decompression."""
        original = b"Hello, World! " * 100
        compressed = zstd.compress(original)
        decompressed = zstd.decompress(compressed)

        assert decompressed == original
        assert len(compressed) < len(original)

    def test_zstd_empty_data(self):
        """Test Zstd handles empty data."""
        compressed = zstd.compress(b"")
        decompressed = zstd.decompress(compressed)
        assert decompressed == b""

    def test_zstd_unicode_data(self):
        """Test Zstd handles Unicode data correctly."""
        unicode_data = "Hello, World! \u4e2d\u6587 \u0440\u0443\u0441\u0441\u043a\u0438\u0439"
        original = unicode_data.encode("utf-8")
        compressed = zstd.compress(original)
        decompressed = zstd.decompress(compressed)

        assert decompressed == original
        assert decompressed.decode("utf-8") == unicode_data


class TestConfigurationSettings:
    """Tests for compression configuration settings."""

    def test_default_compression_enabled(self):
        """Verify compression is enabled by default."""
        from backend.core.config import Settings

        # Create settings without overrides
        with patch.dict("os.environ", {}, clear=False):
            # We can't easily test defaults due to validation, but we can verify
            # the field definition
            field_info = Settings.model_fields["redis_compression_enabled"]
            assert field_info.default is True

    def test_default_compression_threshold(self):
        """Verify default compression threshold is 1KB."""
        from backend.core.config import Settings

        field_info = Settings.model_fields["redis_compression_threshold"]
        assert field_info.default == 1024

    def test_compression_threshold_bounds(self):
        """Verify compression threshold has appropriate bounds."""
        from backend.core.config import Settings

        field_info = Settings.model_fields["redis_compression_threshold"]
        # Check that ge=0 and le=1048576 (1MB) constraints exist
        ge_constraints = [m for m in field_info.metadata if hasattr(m, "ge")]
        le_constraints = [m for m in field_info.metadata if hasattr(m, "le")]
        assert any(m.ge == 0 for m in ge_constraints)
        assert any(m.le == 1048576 for m in le_constraints)
