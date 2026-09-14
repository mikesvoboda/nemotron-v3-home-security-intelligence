"""WebSocket message compression and serialization utilities (NEM-3154, NEM-3737).

This module provides application-level compression and serialization for WebSocket
messages, supporting both zlib compression and MessagePack binary serialization.

Serialization Formats:
- JSON (default): Plain text JSON messages, no magic byte
- ZLIB: Compressed JSON with magic byte 0x00 prefix (threshold-based)
- MSGPACK: MessagePack binary with magic byte 0x01 prefix (30-50% smaller than JSON)

Magic Byte Protocol:
- 0x00: zlib-compressed JSON (NEM-3154)
- 0x01: MessagePack binary (NEM-3737)
- Other: Plain JSON text (no prefix)

Content Negotiation:
- Format is negotiated during WebSocket handshake via query param: ?format=msgpack
- Default is JSON with zlib compression for large messages
- MessagePack is recommended for high-throughput scenarios

Usage:
    from backend.core.websocket.compression import (
        compress_message,
        decompress_message,
        should_compress,
        get_compression_stats,
        SerializationFormat,
        prepare_message_with_format,
    )

    # Using specific format
    prepared, format_used = prepare_message_with_format(
        message, format=SerializationFormat.MSGPACK
    )
    await ws.send_bytes(prepared)

    # Auto-detect and decode
    decoded = decode_message_auto(received_bytes)
"""

from __future__ import annotations

import json
import zlib
from dataclasses import dataclass
from enum import Enum
from typing import Any

from backend.core.config import get_settings
from backend.core.logging import get_logger

logger = get_logger(__name__)

# Magic byte prefix for zlib-compressed messages (0x00 is not valid JSON/UTF-8 start)
COMPRESSION_MAGIC_BYTE = b"\x00"

# Magic byte prefix for MessagePack messages (0x01 - distinct from zlib's 0x00)
MSGPACK_MAGIC_BYTE = b"\x01"


class SerializationFormat(str, Enum):
    """WebSocket message serialization format.

    Supported formats for WebSocket message encoding (NEM-3737).
    Format is negotiated during WebSocket handshake via query param.
    """

    JSON = "json"  # Plain JSON text (default, no magic byte)
    ZLIB = "zlib"  # zlib-compressed JSON (magic byte 0x00)
    MSGPACK = "msgpack"  # MessagePack binary (magic byte 0x01)

    @classmethod
    def from_query_param(cls, value: str | None) -> SerializationFormat:
        """Parse serialization format from query parameter.

        Args:
            value: Query parameter value (e.g., "msgpack", "json", "zlib")

        Returns:
            SerializationFormat enum value, defaults to JSON if invalid/missing
        """
        if not value:
            return cls.JSON
        try:
            return cls(value.lower())
        except ValueError:
            logger.warning(f"Unknown serialization format: {value}, defaulting to JSON")
            return cls.JSON


@dataclass
class CompressionStats:
    """Statistics for WebSocket message compression.

    Tracks compression performance metrics for monitoring and debugging.
    Thread-safe via atomic increments (in CPython due to GIL).
    """

    total_messages: int = 0
    compressed_messages: int = 0
    uncompressed_messages: int = 0
    total_original_bytes: int = 0
    total_compressed_bytes: int = 0
    compression_errors: int = 0
    decompression_errors: int = 0

    @property
    def compression_ratio(self) -> float:
        """Average compression ratio (compressed / original).

        Returns 1.0 if no compression has occurred yet.
        Lower is better (0.5 = 50% reduction in size).
        """
        if self.total_original_bytes == 0:
            return 1.0
        return self.total_compressed_bytes / self.total_original_bytes

    @property
    def bytes_saved(self) -> int:
        """Total bytes saved through compression."""
        return self.total_original_bytes - self.total_compressed_bytes

    def to_dict(self) -> dict[str, Any]:
        """Convert stats to dictionary for API/metrics exposure."""
        return {
            "total_messages": self.total_messages,
            "compressed_messages": self.compressed_messages,
            "uncompressed_messages": self.uncompressed_messages,
            "total_original_bytes": self.total_original_bytes,
            "total_compressed_bytes": self.total_compressed_bytes,
            "compression_ratio": round(self.compression_ratio, 4),
            "bytes_saved": self.bytes_saved,
            "compression_errors": self.compression_errors,
            "decompression_errors": self.decompression_errors,
        }


# Global compression statistics instance
_compression_stats = CompressionStats()


def get_compression_stats() -> CompressionStats:
    """Get the global compression statistics.

    Returns:
        CompressionStats instance with current metrics.
    """
    return _compression_stats


def reset_compression_stats() -> None:
    """Reset compression statistics (for testing)."""
    global _compression_stats  # noqa: PLW0603
    _compression_stats = CompressionStats()


def should_compress(message: str | bytes, *, threshold: int | None = None) -> bool:
    """Determine if a message should be compressed.

    Args:
        message: The message to potentially compress (JSON string or bytes).
        threshold: Override the configured compression threshold.
                   If None, uses settings.websocket_compression_threshold.

    Returns:
        True if the message should be compressed, False otherwise.
    """
    settings = get_settings()

    # Check if compression is enabled
    if not settings.websocket_compression_enabled:
        return False

    # Get threshold from settings or override
    compression_threshold = (
        threshold if threshold is not None else settings.websocket_compression_threshold
    )

    # Get message size
    message_size = len(message.encode("utf-8")) if isinstance(message, str) else len(message)

    return message_size >= compression_threshold


def compress_message(
    message: str | dict[str, Any],
    *,
    level: int | None = None,
    track_stats: bool = True,
) -> bytes:
    """Compress a WebSocket message using zlib/deflate.

    Compresses the message and prepends a magic byte header to indicate
    that the message is compressed.

    Args:
        message: The message to compress (JSON string or dict).
        level: Compression level (1-9). If None, uses settings.websocket_compression_level.
        track_stats: Whether to update global compression statistics.

    Returns:
        Compressed message bytes with magic byte prefix.

    Raises:
        ValueError: If compression fails.
    """
    settings = get_settings()
    compression_level = level if level is not None else settings.websocket_compression_level

    # Serialize dict to JSON string if needed
    message_str = json.dumps(message) if isinstance(message, dict) else message

    # Encode to bytes
    message_bytes = message_str.encode("utf-8")
    original_size = len(message_bytes)

    try:
        # Compress with zlib (deflate algorithm)
        compressed = zlib.compress(message_bytes, level=compression_level)
        compressed_size = len(compressed)

        # Prepend magic byte
        result = COMPRESSION_MAGIC_BYTE + compressed

        # Update statistics
        if track_stats:
            _compression_stats.total_messages += 1
            _compression_stats.compressed_messages += 1
            _compression_stats.total_original_bytes += original_size
            _compression_stats.total_compressed_bytes += compressed_size

        logger.debug(
            "Compressed WebSocket message",
            extra={
                "original_size": original_size,
                "compressed_size": compressed_size,
                "ratio": round(compressed_size / original_size, 4) if original_size > 0 else 1.0,
                "level": compression_level,
            },
        )

        return result

    except zlib.error as e:
        if track_stats:
            _compression_stats.compression_errors += 1
        logger.error(f"Failed to compress WebSocket message: {e}")
        raise ValueError(f"Compression failed: {e}") from e


def decompress_message(data: bytes) -> str:
    """Decompress a WebSocket message.

    Checks for the magic byte prefix and decompresses if present.
    If the message is not compressed (no magic byte), returns it as-is.

    Args:
        data: The potentially compressed message bytes.

    Returns:
        Decompressed message as a string.

    Raises:
        ValueError: If decompression fails.
    """
    # Check for magic byte prefix
    if not data.startswith(COMPRESSION_MAGIC_BYTE):
        # Not compressed, return as-is (decode if bytes)
        return data.decode("utf-8") if isinstance(data, bytes) else data

    try:
        # Remove magic byte and decompress
        compressed_data = data[len(COMPRESSION_MAGIC_BYTE) :]
        decompressed = zlib.decompress(compressed_data)
        return decompressed.decode("utf-8")

    except zlib.error as e:
        _compression_stats.decompression_errors += 1
        logger.error(f"Failed to decompress WebSocket message: {e}")
        raise ValueError(f"Decompression failed: {e}") from e


def prepare_message(
    message: str | dict[str, Any],
    *,
    threshold: int | None = None,
    level: int | None = None,
    track_stats: bool = True,
) -> tuple[bytes | str, bool]:
    """Prepare a message for sending, compressing if beneficial.

    This is the main entry point for sending messages. It automatically
    decides whether to compress based on message size and configuration.

    Args:
        message: The message to prepare (JSON string or dict).
        threshold: Override the compression threshold.
        level: Override the compression level.
        track_stats: Whether to update global compression statistics.

    Returns:
        Tuple of (prepared_message, was_compressed).
        - If compressed: (bytes with magic header, True)
        - If not compressed: (JSON string, False)
    """
    # Serialize dict to JSON string if needed
    message_str = json.dumps(message) if isinstance(message, dict) else message

    # Check if we should compress
    if should_compress(message_str, threshold=threshold):
        try:
            compressed = compress_message(message_str, level=level, track_stats=track_stats)
            return compressed, True
        except ValueError:
            # Fall back to uncompressed on error
            logger.warning("Compression failed, falling back to uncompressed message")

    # Track uncompressed message stats
    if track_stats:
        _compression_stats.total_messages += 1
        _compression_stats.uncompressed_messages += 1

    return message_str, False


def is_compressed_message(data: bytes) -> bool:
    """Check if a message is zlib-compressed (has magic byte prefix 0x00).

    Args:
        data: The message bytes to check.

    Returns:
        True if the message has the compression magic byte prefix.
    """
    return isinstance(data, bytes) and data.startswith(COMPRESSION_MAGIC_BYTE)


def is_msgpack_message(data: bytes) -> bool:
    """Check if a message is MessagePack encoded (has magic byte prefix 0x01).

    Args:
        data: The message bytes to check.

    Returns:
        True if the message has the MessagePack magic byte prefix.
    """
    return isinstance(data, bytes) and data.startswith(MSGPACK_MAGIC_BYTE)


def detect_format(data: bytes | str) -> SerializationFormat:
    """Detect the serialization format of a message.

    Args:
        data: The message data (bytes or string).

    Returns:
        Detected SerializationFormat.
    """
    if isinstance(data, str):
        return SerializationFormat.JSON
    if is_compressed_message(data):
        return SerializationFormat.ZLIB
    if is_msgpack_message(data):
        return SerializationFormat.MSGPACK
    return SerializationFormat.JSON


def encode_msgpack(data: dict[str, Any], *, track_stats: bool = True) -> bytes:
    """Encode a dictionary to MessagePack binary format with magic byte prefix.

    Args:
        data: Dictionary to encode
        track_stats: Whether to update global statistics (passed through)

    Returns:
        MessagePack encoded bytes with magic byte prefix (0x01)

    Raises:
        ValueError: If encoding fails
    """
    from backend.core.websocket.msgpack_serialization import MessagePackEncoder

    return MessagePackEncoder.encode(data, track_stats=track_stats)


def decode_msgpack(data: bytes, *, track_stats: bool = True) -> dict[str, Any]:
    """Decode MessagePack binary data to a dictionary.

    Args:
        data: MessagePack encoded bytes (with or without magic byte)
        track_stats: Whether to update global statistics on error

    Returns:
        Decoded dictionary

    Raises:
        ValueError: If decoding fails
    """
    from backend.core.websocket.msgpack_serialization import MessagePackEncoder

    return MessagePackEncoder.decode(data, track_stats=track_stats)


def decode_message_auto(data: bytes | str) -> dict[str, Any]:
    """Decode a WebSocket message, auto-detecting the format.

    Handles all supported formats:
    - MessagePack (magic byte 0x01)
    - zlib-compressed JSON (magic byte 0x00)
    - Plain JSON text

    Args:
        data: The message data in any supported format.

    Returns:
        Decoded dictionary.

    Raises:
        ValueError: If decoding fails for any format.
    """
    if isinstance(data, str):
        try:
            parsed = json.loads(data)
            return dict(parsed) if isinstance(parsed, dict) else parsed
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to decode JSON string: {e}") from e

    detected = detect_format(data)

    if detected == SerializationFormat.MSGPACK:
        result = decode_msgpack(data)
        return dict(result) if isinstance(result, dict) else result
    if detected == SerializationFormat.ZLIB:
        decompressed = decompress_message(data)
        parsed = json.loads(decompressed)
        return dict(parsed) if isinstance(parsed, dict) else parsed
    # Plain JSON bytes
    try:
        parsed = json.loads(data.decode("utf-8"))
        return dict(parsed) if isinstance(parsed, dict) else parsed
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise ValueError(f"Failed to decode JSON bytes: {e}") from e


def prepare_message_with_format(
    message: str | dict[str, Any],
    *,
    format: SerializationFormat = SerializationFormat.JSON,
    threshold: int | None = None,
    level: int | None = None,
    track_stats: bool = True,
) -> tuple[bytes | str, SerializationFormat]:
    """Prepare a message for sending using the specified format.

    This is the unified entry point for message serialization, supporting
    all formats: JSON, zlib compression, and MessagePack.

    Args:
        message: The message to prepare (JSON string or dict).
        format: Serialization format to use.
        threshold: Override compression threshold (for zlib format).
        level: Override compression level (for zlib format).
        track_stats: Whether to update global statistics.

    Returns:
        Tuple of (prepared_message, format_used).
        - JSON: (JSON string, SerializationFormat.JSON)
        - ZLIB: (bytes with 0x00 magic header, SerializationFormat.ZLIB)
        - MSGPACK: (bytes with 0x01 magic header, SerializationFormat.MSGPACK)
    """
    # Serialize dict to JSON string/dict depending on format
    if format == SerializationFormat.MSGPACK:
        # MessagePack works directly with dicts
        message_dict = json.loads(message) if isinstance(message, str) else message
        try:
            encoded = encode_msgpack(message_dict, track_stats=track_stats)
            return encoded, SerializationFormat.MSGPACK
        except ValueError:
            logger.warning("MessagePack encoding failed, falling back to JSON")
            # Fall through to JSON

    if format == SerializationFormat.ZLIB:
        # Use existing compression logic
        prepared, was_compressed = prepare_message(
            message, threshold=threshold, level=level, track_stats=track_stats
        )
        if was_compressed:
            return prepared, SerializationFormat.ZLIB
        return prepared, SerializationFormat.JSON

    # For JSON format, serialize the message to a JSON string
    message_str = json.dumps(message) if isinstance(message, dict) else message

    if track_stats:
        _compression_stats.total_messages += 1
        _compression_stats.uncompressed_messages += 1

    return message_str, SerializationFormat.JSON
