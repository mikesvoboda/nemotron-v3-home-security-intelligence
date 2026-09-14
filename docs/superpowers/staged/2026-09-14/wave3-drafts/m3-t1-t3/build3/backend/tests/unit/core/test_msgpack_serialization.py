"""Unit tests for MessagePack serialization utilities (NEM-3737).

Tests cover:
- MessagePack encoding and decoding
- Magic byte protocol
- DateTime handling
- Error handling
- Statistics tracking
- Round-trip serialization
"""

import json
from datetime import UTC, datetime

import pytest

from backend.core.websocket.msgpack_serialization import (
    MSGPACK_MAGIC_BYTE,
    MessagePackEncoder,
    MessagePackStats,
    decode_msgpack,
    encode_msgpack,
    get_msgpack_stats,
    is_msgpack_message,
    prepare_msgpack_message,
    reset_msgpack_stats,
)


class TestMsgpackMagicByte:
    """Tests for MessagePack magic byte handling."""

    def test_magic_byte_value(self):
        """Magic byte should be 0x01 (distinct from zlib's 0x00)."""
        assert MSGPACK_MAGIC_BYTE == b"\x01"
        assert len(MSGPACK_MAGIC_BYTE) == 1

    def test_is_msgpack_message_with_magic_byte(self):
        """Should detect MessagePack messages by magic byte prefix."""
        msgpack_data = MSGPACK_MAGIC_BYTE + b"msgpack_data"
        assert is_msgpack_message(msgpack_data)

    def test_is_msgpack_message_without_magic_byte(self):
        """Should return False for messages without magic byte."""
        json_data = b'{"type": "event"}'
        assert not is_msgpack_message(json_data)

    def test_is_msgpack_message_with_zlib_magic_byte(self):
        """Should return False for zlib-compressed messages (0x00 prefix)."""
        zlib_data = b"\x00compressed_data"
        assert not is_msgpack_message(zlib_data)

    def test_is_msgpack_message_empty(self):
        """Should return False for empty messages."""
        assert not is_msgpack_message(b"")

    def test_is_msgpack_message_string(self):
        """Should return False for string messages (not bytes)."""
        assert not is_msgpack_message("not bytes")


class TestMessagePackEncoder:
    """Tests for MessagePackEncoder class."""

    def test_encode_simple_dict(self):
        """Should encode a simple dictionary with magic byte prefix."""
        data = {"type": "event", "value": 42}
        encoded = MessagePackEncoder.encode(data, track_stats=False)

        assert encoded.startswith(MSGPACK_MAGIC_BYTE)
        assert len(encoded) > 1

    def test_encode_nested_dict(self):
        """Should encode nested dictionaries."""
        data = {
            "type": "detection",
            "data": {
                "camera_id": "front_door",
                "detections": [{"label": "person", "confidence": 0.95}],
            },
        }
        encoded = MessagePackEncoder.encode(data, track_stats=False)

        assert encoded.startswith(MSGPACK_MAGIC_BYTE)
        # Should decode back correctly
        decoded = MessagePackEncoder.decode(encoded, track_stats=False)
        assert decoded == data

    def test_encode_with_datetime(self):
        """Should handle datetime objects (converted to ISO 8601)."""
        now = datetime.now(tz=UTC)
        data = {"timestamp": now, "type": "event"}
        encoded = MessagePackEncoder.encode(data, track_stats=False)

        decoded = MessagePackEncoder.decode(encoded, track_stats=False)
        assert decoded["timestamp"] == now.isoformat()
        assert decoded["type"] == "event"

    def test_encode_with_naive_datetime(self):
        """Should handle naive datetime objects (assumed UTC)."""
        naive_dt = datetime(2024, 1, 15, 10, 30, 0)
        data = {"timestamp": naive_dt}
        encoded = MessagePackEncoder.encode(data, track_stats=False)

        decoded = MessagePackEncoder.decode(encoded, track_stats=False)
        # Should include timezone info
        assert "+00:00" in decoded["timestamp"] or "Z" in decoded["timestamp"]

    def test_encode_with_binary_data(self):
        """Should handle binary data."""
        data = {"image": b"\x89PNG\r\n\x1a\n", "type": "frame"}
        encoded = MessagePackEncoder.encode(data, track_stats=False)

        decoded = MessagePackEncoder.decode(encoded, track_stats=False)
        assert decoded["image"] == b"\x89PNG\r\n\x1a\n"
        assert decoded["type"] == "frame"

    def test_decode_with_magic_byte(self):
        """Should remove magic byte when decoding."""
        data = {"type": "test"}
        encoded = MessagePackEncoder.encode(data, track_stats=False)

        decoded = MessagePackEncoder.decode(encoded, track_stats=False)
        assert decoded == data

    def test_decode_without_magic_byte(self):
        """Should decode data without magic byte prefix."""
        import msgpack

        data = {"type": "test"}
        raw_encoded = msgpack.packb(data)

        decoded = MessagePackEncoder.decode(raw_encoded, track_stats=False)
        assert decoded == data

    def test_decode_invalid_data(self):
        """Should raise ValueError for invalid MessagePack data."""
        invalid = MSGPACK_MAGIC_BYTE + b"not valid msgpack"
        with pytest.raises(ValueError, match="MessagePack decoding failed"):
            MessagePackEncoder.decode(invalid, track_stats=False)

    def test_decode_non_dict(self):
        """Should raise ValueError when decoded data is not a dict."""
        import msgpack

        # Encode a list instead of a dict
        raw_encoded = msgpack.packb([1, 2, 3])
        with pytest.raises(ValueError, match="Expected dict"):
            MessagePackEncoder.decode(raw_encoded, track_stats=False)


class TestMessagePackStats:
    """Tests for MessagePack statistics tracking."""

    def test_stats_initial_state(self):
        """Stats should start at zero."""
        stats = MessagePackStats()
        assert stats.total_messages == 0
        assert stats.total_original_bytes == 0
        assert stats.total_encoded_bytes == 0
        assert stats.encode_errors == 0
        assert stats.decode_errors == 0

    def test_stats_compression_ratio_no_data(self):
        """Compression ratio should be 1.0 when no data."""
        stats = MessagePackStats()
        assert stats.compression_ratio == 1.0

    def test_stats_compression_ratio_with_data(self):
        """Compression ratio should reflect actual encoding."""
        stats = MessagePackStats()
        stats.total_original_bytes = 1000
        stats.total_encoded_bytes = 700
        assert stats.compression_ratio == 0.7

    def test_stats_bytes_saved(self):
        """Bytes saved should be difference between original and encoded."""
        stats = MessagePackStats()
        stats.total_original_bytes = 1000
        stats.total_encoded_bytes = 700
        assert stats.bytes_saved == 300

    def test_stats_to_dict(self):
        """Should convert stats to dictionary."""
        stats = MessagePackStats()
        stats.total_messages = 10
        stats.total_original_bytes = 10000
        stats.total_encoded_bytes = 7000

        result = stats.to_dict()
        assert result["total_messages"] == 10
        assert result["compression_ratio"] == 0.7
        assert result["bytes_saved"] == 3000

    def test_global_stats_tracking(self):
        """Should track stats globally."""
        reset_msgpack_stats()

        # Encode a message
        data = {"type": "test", "data": "x" * 100}
        encode_msgpack(data)

        stats = get_msgpack_stats()
        assert stats.total_messages == 1
        assert stats.total_original_bytes > 0
        assert stats.total_encoded_bytes > 0


class TestConvenienceFunctions:
    """Tests for encode_msgpack and decode_msgpack functions."""

    def test_encode_decode_roundtrip(self):
        """encode_msgpack and decode_msgpack should work together."""
        reset_msgpack_stats()

        original = {"type": "event", "data": {"value": 123}}
        encoded = encode_msgpack(original)
        decoded = decode_msgpack(encoded)

        assert decoded == original

    def test_prepare_msgpack_message_dict(self):
        """Should prepare dict as MessagePack."""
        data = {"type": "event"}
        prepared, was_encoded = prepare_msgpack_message(data, track_stats=False)

        assert was_encoded
        assert isinstance(prepared, bytes)
        assert prepared.startswith(MSGPACK_MAGIC_BYTE)

    def test_prepare_msgpack_message_json_string(self):
        """Should parse JSON string and encode as MessagePack."""
        json_str = '{"type": "event", "value": 42}'
        prepared, was_encoded = prepare_msgpack_message(json_str, track_stats=False)

        assert was_encoded
        assert isinstance(prepared, bytes)
        decoded = decode_msgpack(prepared, track_stats=False)
        assert decoded == {"type": "event", "value": 42}

    def test_prepare_msgpack_message_invalid_json(self):
        """Should return unencoded for invalid JSON string."""
        invalid_json = "not json"
        prepared, was_encoded = prepare_msgpack_message(invalid_json, track_stats=False)

        assert not was_encoded
        assert prepared == b"not json"


class TestRoundTrip:
    """End-to-end MessagePack serialization tests."""

    def test_roundtrip_complex_message(self):
        """Complex message should survive roundtrip."""
        original = {
            "type": "detection.batch",
            "data": {
                "batch_id": "batch_abc123",
                "camera_id": "front_door",
                "detections": [
                    {"id": 1, "label": "person", "confidence": 0.95, "bbox": [10, 20, 100, 200]},
                    {"id": 2, "label": "car", "confidence": 0.87, "bbox": [200, 150, 400, 300]},
                ],
                "started_at": "2024-01-15T10:00:00Z",
            },
        }

        encoded = encode_msgpack(original, track_stats=False)
        decoded = decode_msgpack(encoded, track_stats=False)

        assert decoded == original

    def test_roundtrip_unicode(self):
        """Unicode message should survive roundtrip."""
        original = {"message": "Hello, 世界! 🎉", "type": "notification"}

        encoded = encode_msgpack(original, track_stats=False)
        decoded = decode_msgpack(encoded, track_stats=False)

        assert decoded == original

    def test_roundtrip_null_values(self):
        """Null values should survive roundtrip."""
        original = {"value": None, "list": [None, 1, None], "nested": {"null_field": None}}

        encoded = encode_msgpack(original, track_stats=False)
        decoded = decode_msgpack(encoded, track_stats=False)

        assert decoded == original


class TestSizeComparison:
    """Tests comparing MessagePack size to JSON."""

    def test_smaller_than_json(self):
        """MessagePack should be smaller than JSON for typical messages."""
        data = {
            "type": "detection.new",
            "data": {
                "detection_id": 12345,
                "batch_id": "batch_abc123def456",
                "camera_id": "front_door_camera",
                "label": "person",
                "confidence": 0.9523,
                "bbox": [123, 456, 789, 1011],
                "timestamp": "2024-01-15T10:30:00.123456Z",
            },
        }

        json_bytes = json.dumps(data).encode("utf-8")
        msgpack_bytes = encode_msgpack(data, track_stats=False)

        # MessagePack should be smaller (magic byte adds 1 byte)
        # Typical reduction is 30-50%
        assert len(msgpack_bytes) < len(json_bytes)

    def test_significantly_smaller_for_binary(self):
        """MessagePack should be much smaller for binary data (no base64)."""
        # Simulated small binary blob
        binary_data = bytes(range(256)) * 4  # 1KB of binary

        data_with_binary = {
            "type": "frame",
            "image_data": binary_data,
        }

        # For JSON, we'd need to base64 encode, adding ~33% overhead
        import base64

        data_for_json = {
            "type": "frame",
            "image_data": base64.b64encode(binary_data).decode("ascii"),
        }
        json_bytes = json.dumps(data_for_json).encode("utf-8")

        # MessagePack stores binary natively
        msgpack_bytes = encode_msgpack(data_with_binary, track_stats=False)

        # MessagePack should be significantly smaller (no base64 overhead)
        assert len(msgpack_bytes) < len(json_bytes) * 0.8  # At least 20% smaller
