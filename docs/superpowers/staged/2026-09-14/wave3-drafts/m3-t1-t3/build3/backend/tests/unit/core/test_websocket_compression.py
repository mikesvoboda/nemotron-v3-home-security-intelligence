"""Unit tests for WebSocket message compression utilities (NEM-3154, NEM-3737).

Tests cover:
- Compression threshold logic
- Message compression and decompression
- Magic byte protocol
- Compression statistics tracking
- Configuration settings integration
- Serialization format detection (NEM-3737)
- MessagePack integration (NEM-3737)
"""

import json
import zlib
from unittest.mock import patch

import pytest

from backend.core.websocket.compression import (
    COMPRESSION_MAGIC_BYTE,
    MSGPACK_MAGIC_BYTE,
    CompressionStats,
    SerializationFormat,
    compress_message,
    decode_message_auto,
    decompress_message,
    detect_format,
    get_compression_stats,
    is_compressed_message,
    is_msgpack_message,
    prepare_message,
    prepare_message_with_format,
    reset_compression_stats,
    should_compress,
)


class TestCompressionMagicByte:
    """Tests for compression magic byte handling."""

    def test_magic_byte_value(self):
        """Magic byte should be 0x00 (not valid JSON/UTF-8 start)."""
        assert COMPRESSION_MAGIC_BYTE == b"\x00"
        assert len(COMPRESSION_MAGIC_BYTE) == 1

    def test_is_compressed_message_with_magic_byte(self):
        """Should detect compressed messages by magic byte prefix."""
        compressed = COMPRESSION_MAGIC_BYTE + b"compressed_data"
        assert is_compressed_message(compressed)

    def test_is_compressed_message_without_magic_byte(self):
        """Should return False for messages without magic byte."""
        uncompressed = b'{"type": "event"}'
        assert not is_compressed_message(uncompressed)

    def test_is_compressed_message_empty(self):
        """Should return False for empty messages."""
        assert not is_compressed_message(b"")

    def test_is_compressed_message_string(self):
        """Should return False for string messages (not bytes)."""
        # We need to check bytes first
        assert not is_compressed_message("not bytes")


class TestShouldCompress:
    """Tests for compression threshold logic."""

    def test_should_compress_above_threshold(self):
        """Should return True for messages above threshold."""
        large_message = "x" * 2000  # 2KB message
        with patch("backend.core.websocket.compression.get_settings") as mock_settings:
            mock_settings.return_value.websocket_compression_enabled = True
            mock_settings.return_value.websocket_compression_threshold = 1024
            assert should_compress(large_message)

    def test_should_not_compress_below_threshold(self):
        """Should return False for messages below threshold."""
        small_message = "x" * 500  # 500 bytes
        with patch("backend.core.websocket.compression.get_settings") as mock_settings:
            mock_settings.return_value.websocket_compression_enabled = True
            mock_settings.return_value.websocket_compression_threshold = 1024
            assert not should_compress(small_message)

    def test_should_not_compress_when_disabled(self):
        """Should return False when compression is disabled."""
        large_message = "x" * 2000
        with patch("backend.core.websocket.compression.get_settings") as mock_settings:
            mock_settings.return_value.websocket_compression_enabled = False
            mock_settings.return_value.websocket_compression_threshold = 1024
            assert not should_compress(large_message)

    def test_should_compress_with_override_threshold(self):
        """Should use override threshold when provided."""
        message = "x" * 500  # 500 bytes
        with patch("backend.core.websocket.compression.get_settings") as mock_settings:
            mock_settings.return_value.websocket_compression_enabled = True
            mock_settings.return_value.websocket_compression_threshold = 1024
            # Override threshold to 100 bytes
            assert should_compress(message, threshold=100)

    def test_should_compress_bytes_input(self):
        """Should handle bytes input correctly."""
        large_bytes = b"x" * 2000
        with patch("backend.core.websocket.compression.get_settings") as mock_settings:
            mock_settings.return_value.websocket_compression_enabled = True
            mock_settings.return_value.websocket_compression_threshold = 1024
            assert should_compress(large_bytes)


class TestCompressMessage:
    """Tests for message compression."""

    def test_compress_string_message(self):
        """Should compress string messages with magic byte prefix."""
        message = '{"type": "event", "data": "x" * 1000}'
        with patch("backend.core.websocket.compression.get_settings") as mock_settings:
            mock_settings.return_value.websocket_compression_level = 6
            compressed = compress_message(message, track_stats=False)

        # Should have magic byte prefix
        assert compressed.startswith(COMPRESSION_MAGIC_BYTE)

        # Should decompress correctly
        decompressed = zlib.decompress(compressed[1:])
        assert decompressed.decode("utf-8") == message

    def test_compress_dict_message(self):
        """Should serialize and compress dict messages."""
        message = {"type": "event", "data": {"key": "value" * 100}}
        with patch("backend.core.websocket.compression.get_settings") as mock_settings:
            mock_settings.return_value.websocket_compression_level = 6
            compressed = compress_message(message, track_stats=False)

        # Should have magic byte prefix
        assert compressed.startswith(COMPRESSION_MAGIC_BYTE)

        # Should decompress to JSON
        decompressed = zlib.decompress(compressed[1:])
        assert json.loads(decompressed) == message

    def test_compress_with_different_levels(self):
        """Should respect compression level setting."""
        message = "x" * 10000
        with patch("backend.core.websocket.compression.get_settings") as mock_settings:
            mock_settings.return_value.websocket_compression_level = 1
            fast_compressed = compress_message(message, track_stats=False)

        with patch("backend.core.websocket.compression.get_settings") as mock_settings:
            mock_settings.return_value.websocket_compression_level = 9
            best_compressed = compress_message(message, level=9, track_stats=False)

        # Best compression should be smaller (for repetitive data)
        # Note: For very repetitive data, both might be similar
        assert len(best_compressed) <= len(fast_compressed)


class TestDecompressMessage:
    """Tests for message decompression."""

    def test_decompress_compressed_message(self):
        """Should decompress messages with magic byte prefix."""
        original = '{"type": "event"}'
        compressed_data = zlib.compress(original.encode("utf-8"))
        message = COMPRESSION_MAGIC_BYTE + compressed_data

        result = decompress_message(message)
        assert result == original

    def test_decompress_uncompressed_message(self):
        """Should return uncompressed messages as-is."""
        original = b'{"type": "event"}'
        result = decompress_message(original)
        assert result == '{"type": "event"}'

    def test_decompress_invalid_compressed_data(self):
        """Should raise error for invalid compressed data."""
        invalid = COMPRESSION_MAGIC_BYTE + b"not valid zlib data"
        with pytest.raises(ValueError, match="Decompression failed"):
            decompress_message(invalid)


class TestPrepareMessage:
    """Tests for prepare_message (main entry point)."""

    def test_prepare_compresses_large_message(self):
        """Should compress messages above threshold."""
        large_message = {"type": "event", "data": "x" * 2000}
        with patch("backend.core.websocket.compression.get_settings") as mock_settings:
            mock_settings.return_value.websocket_compression_enabled = True
            mock_settings.return_value.websocket_compression_threshold = 1024
            mock_settings.return_value.websocket_compression_level = 6

            reset_compression_stats()
            prepared, was_compressed = prepare_message(large_message)

        assert was_compressed
        assert isinstance(prepared, bytes)
        assert prepared.startswith(COMPRESSION_MAGIC_BYTE)

    def test_prepare_does_not_compress_small_message(self):
        """Should not compress messages below threshold."""
        small_message = {"type": "event"}
        with patch("backend.core.websocket.compression.get_settings") as mock_settings:
            mock_settings.return_value.websocket_compression_enabled = True
            mock_settings.return_value.websocket_compression_threshold = 1024
            mock_settings.return_value.websocket_compression_level = 6

            reset_compression_stats()
            prepared, was_compressed = prepare_message(small_message)

        assert not was_compressed
        assert isinstance(prepared, str)
        assert json.loads(prepared) == small_message

    def test_prepare_returns_json_string_for_uncompressed(self):
        """Should return JSON string when not compressing."""
        message = {"type": "ping"}
        with patch("backend.core.websocket.compression.get_settings") as mock_settings:
            mock_settings.return_value.websocket_compression_enabled = True
            mock_settings.return_value.websocket_compression_threshold = 1024

            prepared, was_compressed = prepare_message(message, track_stats=False)

        assert not was_compressed
        assert prepared == '{"type": "ping"}'


class TestCompressionStats:
    """Tests for compression statistics tracking."""

    def test_stats_initial_state(self):
        """Stats should start at zero."""
        stats = CompressionStats()
        assert stats.total_messages == 0
        assert stats.compressed_messages == 0
        assert stats.uncompressed_messages == 0
        assert stats.compression_errors == 0
        assert stats.decompression_errors == 0

    def test_stats_compression_ratio_no_data(self):
        """Compression ratio should be 1.0 when no data."""
        stats = CompressionStats()
        assert stats.compression_ratio == 1.0

    def test_stats_compression_ratio_with_data(self):
        """Compression ratio should reflect actual compression."""
        stats = CompressionStats()
        stats.total_original_bytes = 1000
        stats.total_compressed_bytes = 500
        assert stats.compression_ratio == 0.5

    def test_stats_bytes_saved(self):
        """Bytes saved should be difference between original and compressed."""
        stats = CompressionStats()
        stats.total_original_bytes = 1000
        stats.total_compressed_bytes = 300
        assert stats.bytes_saved == 700

    def test_stats_to_dict(self):
        """Should convert stats to dictionary."""
        stats = CompressionStats()
        stats.total_messages = 10
        stats.compressed_messages = 7
        stats.uncompressed_messages = 3
        stats.total_original_bytes = 10000
        stats.total_compressed_bytes = 5000

        result = stats.to_dict()
        assert result["total_messages"] == 10
        assert result["compressed_messages"] == 7
        assert result["uncompressed_messages"] == 3
        assert result["compression_ratio"] == 0.5
        assert result["bytes_saved"] == 5000

    def test_global_stats_tracking(self):
        """Should track stats globally."""
        reset_compression_stats()

        with patch("backend.core.websocket.compression.get_settings") as mock_settings:
            mock_settings.return_value.websocket_compression_enabled = True
            mock_settings.return_value.websocket_compression_threshold = 100
            mock_settings.return_value.websocket_compression_level = 6

            # Compress a message
            compress_message("x" * 200)

            # Prepare a small message (not compressed)
            prepare_message({"type": "ping"})

        stats = get_compression_stats()
        assert stats.total_messages == 2
        assert stats.compressed_messages == 1
        assert stats.uncompressed_messages == 1


class TestRoundTrip:
    """End-to-end compression/decompression tests."""

    def test_roundtrip_text(self):
        """Text message should survive compression roundtrip."""
        original = '{"type": "event", "data": "test data " * 100}'
        with patch("backend.core.websocket.compression.get_settings") as mock_settings:
            mock_settings.return_value.websocket_compression_level = 6
            compressed = compress_message(original, track_stats=False)
            decompressed = decompress_message(compressed)

        assert decompressed == original

    def test_roundtrip_dict(self):
        """Dict message should survive compression roundtrip."""
        original = {"type": "event", "data": {"nested": "value" * 50}}
        with patch("backend.core.websocket.compression.get_settings") as mock_settings:
            mock_settings.return_value.websocket_compression_level = 6
            compressed = compress_message(original, track_stats=False)
            decompressed = decompress_message(compressed)

        assert json.loads(decompressed) == original

    def test_roundtrip_unicode(self):
        """Unicode message should survive compression roundtrip."""
        original = '{"message": "Hello, \u4e16\u754c! \U0001f600"}'
        with patch("backend.core.websocket.compression.get_settings") as mock_settings:
            mock_settings.return_value.websocket_compression_level = 6
            compressed = compress_message(original, track_stats=False)
            decompressed = decompress_message(compressed)

        assert decompressed == original

    def test_prepare_and_decompress_roundtrip(self):
        """prepare_message -> decompress_message should work correctly."""
        large_message = {"type": "detection", "data": {"image": "x" * 5000}}

        with patch("backend.core.websocket.compression.get_settings") as mock_settings:
            mock_settings.return_value.websocket_compression_enabled = True
            mock_settings.return_value.websocket_compression_threshold = 1024
            mock_settings.return_value.websocket_compression_level = 6

            prepared, was_compressed = prepare_message(large_message, track_stats=False)

        assert was_compressed

        # Decompress and verify
        decompressed = decompress_message(prepared)
        assert json.loads(decompressed) == large_message


class TestSerializationFormat:
    """Tests for SerializationFormat enum (NEM-3737)."""

    def test_from_query_param_json(self):
        """Should parse 'json' query param."""
        assert SerializationFormat.from_query_param("json") == SerializationFormat.JSON

    def test_from_query_param_zlib(self):
        """Should parse 'zlib' query param."""
        assert SerializationFormat.from_query_param("zlib") == SerializationFormat.ZLIB

    def test_from_query_param_msgpack(self):
        """Should parse 'msgpack' query param."""
        assert SerializationFormat.from_query_param("msgpack") == SerializationFormat.MSGPACK

    def test_from_query_param_case_insensitive(self):
        """Should handle case-insensitive input."""
        assert SerializationFormat.from_query_param("MSGPACK") == SerializationFormat.MSGPACK
        assert SerializationFormat.from_query_param("MsgPack") == SerializationFormat.MSGPACK

    def test_from_query_param_none(self):
        """Should default to JSON for None."""
        assert SerializationFormat.from_query_param(None) == SerializationFormat.JSON

    def test_from_query_param_empty(self):
        """Should default to JSON for empty string."""
        assert SerializationFormat.from_query_param("") == SerializationFormat.JSON

    def test_from_query_param_invalid(self):
        """Should default to JSON for invalid value."""
        assert SerializationFormat.from_query_param("invalid") == SerializationFormat.JSON


class TestFormatDetection:
    """Tests for format detection (NEM-3737)."""

    def test_detect_format_zlib(self):
        """Should detect zlib format by magic byte."""
        data = b"\x00compressed_data"
        assert detect_format(data) == SerializationFormat.ZLIB

    def test_detect_format_msgpack(self):
        """Should detect MessagePack format by magic byte."""
        data = b"\x01msgpack_data"
        assert detect_format(data) == SerializationFormat.MSGPACK

    def test_detect_format_json_bytes(self):
        """Should detect JSON for bytes without magic byte."""
        data = b'{"type": "event"}'
        assert detect_format(data) == SerializationFormat.JSON

    def test_detect_format_json_string(self):
        """Should detect JSON for string input."""
        data = '{"type": "event"}'
        assert detect_format(data) == SerializationFormat.JSON

    def test_detect_format_empty(self):
        """Should default to JSON for empty bytes."""
        assert detect_format(b"") == SerializationFormat.JSON

    def test_is_msgpack_message(self):
        """Should identify MessagePack messages."""
        msgpack_data = MSGPACK_MAGIC_BYTE + b"data"
        assert is_msgpack_message(msgpack_data)
        assert not is_msgpack_message(b'{"json": true}')
        assert not is_msgpack_message(COMPRESSION_MAGIC_BYTE + b"zlib")


class TestDecodeMessageAuto:
    """Tests for auto-detecting decode function (NEM-3737)."""

    def test_decode_json_string(self):
        """Should decode JSON string."""
        data = '{"type": "event", "value": 42}'
        result = decode_message_auto(data)
        assert result == {"type": "event", "value": 42}

    def test_decode_json_bytes(self):
        """Should decode JSON bytes."""
        data = b'{"type": "event", "value": 42}'
        result = decode_message_auto(data)
        assert result == {"type": "event", "value": 42}

    def test_decode_zlib_compressed(self):
        """Should decode zlib-compressed JSON."""
        original = {"type": "event", "data": "test"}
        compressed = COMPRESSION_MAGIC_BYTE + zlib.compress(json.dumps(original).encode("utf-8"))
        result = decode_message_auto(compressed)
        assert result == original

    def test_decode_msgpack(self):
        """Should decode MessagePack."""
        from backend.core.websocket.msgpack_serialization import encode_msgpack

        original = {"type": "event", "value": 123}
        encoded = encode_msgpack(original, track_stats=False)
        result = decode_message_auto(encoded)
        assert result == original

    def test_decode_invalid_json_raises(self):
        """Should raise ValueError for invalid JSON."""
        with pytest.raises(ValueError, match="Failed to decode JSON"):
            decode_message_auto("not json")


class TestPrepareMessageWithFormat:
    """Tests for prepare_message_with_format (NEM-3737)."""

    def test_prepare_json_format(self):
        """Should return JSON string for JSON format."""
        message = {"type": "event"}
        prepared, format_used = prepare_message_with_format(
            message, format=SerializationFormat.JSON, track_stats=False
        )

        assert format_used == SerializationFormat.JSON
        assert isinstance(prepared, str)
        assert json.loads(prepared) == message

    def test_prepare_msgpack_format(self):
        """Should return MessagePack bytes for MSGPACK format."""
        message = {"type": "event", "value": 42}
        prepared, format_used = prepare_message_with_format(
            message, format=SerializationFormat.MSGPACK, track_stats=False
        )

        assert format_used == SerializationFormat.MSGPACK
        assert isinstance(prepared, bytes)
        assert prepared.startswith(MSGPACK_MAGIC_BYTE)

        # Verify it decodes correctly
        result = decode_message_auto(prepared)
        assert result == message

    def test_prepare_zlib_format_large_message(self):
        """Should return zlib-compressed bytes for ZLIB format when above threshold."""
        large_message = {"type": "event", "data": "x" * 2000}

        with patch("backend.core.websocket.compression.get_settings") as mock_settings:
            mock_settings.return_value.websocket_compression_enabled = True
            mock_settings.return_value.websocket_compression_threshold = 1024
            mock_settings.return_value.websocket_compression_level = 6

            prepared, format_used = prepare_message_with_format(
                large_message, format=SerializationFormat.ZLIB, track_stats=False
            )

        assert format_used == SerializationFormat.ZLIB
        assert isinstance(prepared, bytes)
        assert prepared.startswith(COMPRESSION_MAGIC_BYTE)

    def test_prepare_zlib_format_small_message(self):
        """Should return JSON for ZLIB format when below threshold."""
        small_message = {"type": "ping"}

        with patch("backend.core.websocket.compression.get_settings") as mock_settings:
            mock_settings.return_value.websocket_compression_enabled = True
            mock_settings.return_value.websocket_compression_threshold = 1024
            mock_settings.return_value.websocket_compression_level = 6

            prepared, format_used = prepare_message_with_format(
                small_message, format=SerializationFormat.ZLIB, track_stats=False
            )

        # Falls back to JSON since message is below threshold
        assert format_used == SerializationFormat.JSON
        assert isinstance(prepared, str)

    def test_prepare_msgpack_from_json_string(self):
        """Should parse JSON string and encode as MessagePack."""
        json_str = '{"type": "event", "value": 123}'
        prepared, format_used = prepare_message_with_format(
            json_str, format=SerializationFormat.MSGPACK, track_stats=False
        )

        assert format_used == SerializationFormat.MSGPACK
        assert isinstance(prepared, bytes)

        result = decode_message_auto(prepared)
        assert result == {"type": "event", "value": 123}


class TestMagicByteDistinction:
    """Tests verifying magic bytes don't conflict."""

    def test_zlib_and_msgpack_magic_bytes_distinct(self):
        """Magic bytes should be distinct."""
        assert COMPRESSION_MAGIC_BYTE != MSGPACK_MAGIC_BYTE
        assert COMPRESSION_MAGIC_BYTE == b"\x00"
        assert MSGPACK_MAGIC_BYTE == b"\x01"

    def test_format_detection_zlib_vs_msgpack(self):
        """Should correctly distinguish zlib from MessagePack."""
        zlib_data = b"\x00" + b"compressed"
        msgpack_data = b"\x01" + b"msgpack"
        json_data = b'{"json": true}'

        assert is_compressed_message(zlib_data)
        assert not is_msgpack_message(zlib_data)

        assert is_msgpack_message(msgpack_data)
        assert not is_compressed_message(msgpack_data)

        assert not is_compressed_message(json_data)
        assert not is_msgpack_message(json_data)
