"""MessagePack binary serialization for WebSocket messages (NEM-3737).

This module provides MessagePack serialization as an alternative to JSON for
WebSocket messages, offering 30-50% smaller payloads and faster serialization.

Serialization Protocol:
- MessagePack messages use magic byte 0x01 prefix for identification
- JSON messages remain unchanged (no prefix or 0x00 for zlib compression)
- Content negotiation happens during WebSocket handshake via query param

Performance Benefits:
- 30-50% smaller payloads than JSON
- Faster serialization/deserialization
- Native binary support (no base64 encoding needed)
- Reduced CPU overhead vs zlib compression

Usage:
    from backend.core.websocket.msgpack_serialization import (
        MessagePackEncoder,
        encode_msgpack,
        decode_msgpack,
        prepare_msgpack_message,
    )

    # Encode a message
    encoded = MessagePackEncoder.encode({"type": "event", "data": {...}})
    await ws.send_bytes(encoded)

    # Decode a message
    data = MessagePackEncoder.decode(received_bytes)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import msgpack

from backend.core.logging import get_logger

logger = get_logger(__name__)

# Magic byte prefix for MessagePack messages (0x01 - distinct from zlib's 0x00)
# This allows the frontend to distinguish between:
# - 0x00: zlib-compressed JSON
# - 0x01: MessagePack binary
# - Other: Plain JSON text
MSGPACK_MAGIC_BYTE = b"\x01"


@dataclass
class MessagePackStats:
    """Statistics for MessagePack serialization.

    Tracks serialization performance metrics for monitoring and debugging.
    Thread-safe via atomic increments (in CPython due to GIL).
    """

    total_messages: int = 0
    total_original_bytes: int = 0
    total_encoded_bytes: int = 0
    encode_errors: int = 0
    decode_errors: int = 0

    @property
    def compression_ratio(self) -> float:
        """Average size ratio (encoded / original JSON).

        Returns 1.0 if no encoding has occurred yet.
        Lower is better (0.7 = 30% reduction in size).
        """
        if self.total_original_bytes == 0:
            return 1.0
        return self.total_encoded_bytes / self.total_original_bytes

    @property
    def bytes_saved(self) -> int:
        """Total bytes saved through MessagePack encoding."""
        return self.total_original_bytes - self.total_encoded_bytes

    def to_dict(self) -> dict[str, Any]:
        """Convert stats to dictionary for API/metrics exposure."""
        return {
            "total_messages": self.total_messages,
            "total_original_bytes": self.total_original_bytes,
            "total_encoded_bytes": self.total_encoded_bytes,
            "compression_ratio": round(self.compression_ratio, 4),
            "bytes_saved": self.bytes_saved,
            "encode_errors": self.encode_errors,
            "decode_errors": self.decode_errors,
        }


# Global MessagePack statistics instance
_msgpack_stats = MessagePackStats()


def get_msgpack_stats() -> MessagePackStats:
    """Get the global MessagePack statistics.

    Returns:
        MessagePackStats instance with current metrics.
    """
    return _msgpack_stats


def reset_msgpack_stats() -> None:
    """Reset MessagePack statistics (for testing)."""
    global _msgpack_stats  # noqa: PLW0603
    _msgpack_stats = MessagePackStats()


def _default_encoder(obj: Any) -> Any:
    """Custom encoder for types not natively supported by MessagePack.

    Handles:
    - datetime objects (converted to ISO 8601 string)
    - Other objects with __dict__ (converted to dict)

    Args:
        obj: Object to encode

    Returns:
        Encodable representation of the object

    Raises:
        TypeError: If object cannot be encoded
    """
    if isinstance(obj, datetime):
        # Convert to ISO 8601 format with timezone
        if obj.tzinfo is None:
            # Assume UTC for naive datetimes
            obj = obj.replace(tzinfo=UTC)
        return obj.isoformat()
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    msg = f"Object of type {type(obj).__name__} is not MessagePack serializable"
    raise TypeError(msg)


class MessagePackEncoder:
    """Static class for MessagePack encoding/decoding operations.

    Provides a clean interface for MessagePack serialization with:
    - Magic byte prefix for message identification
    - Custom type handlers for datetime, etc.
    - Error handling and logging
    """

    @staticmethod
    def encode(data: dict[str, Any], *, track_stats: bool = True) -> bytes:
        """Encode a dictionary to MessagePack binary format with magic byte prefix.

        Args:
            data: Dictionary to encode
            track_stats: Whether to update global statistics

        Returns:
            MessagePack encoded bytes with magic byte prefix

        Raises:
            ValueError: If encoding fails
        """
        import base64
        import json

        try:
            # Encode with MessagePack first
            encoded = msgpack.packb(data, default=_default_encoder, use_bin_type=True)
            encoded_size = len(encoded)

            # Calculate original JSON size for comparison (using custom encoder)
            def json_default_encoder(obj: Any) -> Any:
                if isinstance(obj, datetime):
                    if obj.tzinfo is None:
                        obj = obj.replace(tzinfo=UTC)
                    return obj.isoformat()
                if isinstance(obj, bytes):
                    # JSON would need base64 encoding for binary
                    return base64.b64encode(obj).decode("ascii")
                msg = f"Object of type {type(obj).__name__} is not JSON serializable"
                raise TypeError(msg)

            json_bytes = json.dumps(data, default=json_default_encoder).encode("utf-8")
            original_size = len(json_bytes)

            # Prepend magic byte
            result: bytes = MSGPACK_MAGIC_BYTE + encoded

            # Update statistics
            if track_stats:
                _msgpack_stats.total_messages += 1
                _msgpack_stats.total_original_bytes += original_size
                _msgpack_stats.total_encoded_bytes += encoded_size

            logger.debug(
                "Encoded MessagePack message",
                extra={
                    "original_size": original_size,
                    "encoded_size": encoded_size,
                    "ratio": round(encoded_size / original_size, 4) if original_size > 0 else 1.0,
                },
            )

            return result

        except (TypeError, msgpack.PackException) as e:
            if track_stats:
                _msgpack_stats.encode_errors += 1
            logger.error(f"Failed to encode MessagePack message: {e}")
            raise ValueError(f"MessagePack encoding failed: {e}") from e

    @staticmethod
    def decode(data: bytes, *, track_stats: bool = True) -> dict[str, Any]:
        """Decode MessagePack binary data to a dictionary.

        Checks for and removes the magic byte prefix if present.

        Args:
            data: MessagePack encoded bytes (with or without magic byte)
            track_stats: Whether to update global statistics on error

        Returns:
            Decoded dictionary

        Raises:
            ValueError: If decoding fails
        """
        try:
            # Remove magic byte if present
            if data.startswith(MSGPACK_MAGIC_BYTE):
                data = data[len(MSGPACK_MAGIC_BYTE) :]

            # Decode MessagePack
            result = msgpack.unpackb(data, raw=False)

            if not isinstance(result, dict):
                raise TypeError(f"Expected dict, got {type(result).__name__}")

            return dict(result)

        except (msgpack.UnpackException, msgpack.ExtraData, TypeError) as e:
            if track_stats:
                _msgpack_stats.decode_errors += 1
            logger.error(f"Failed to decode MessagePack message: {e}")
            raise ValueError(f"MessagePack decoding failed: {e}") from e


def is_msgpack_message(data: bytes) -> bool:
    """Check if a message is MessagePack encoded (has magic byte prefix).

    Args:
        data: The message bytes to check.

    Returns:
        True if the message has the MessagePack magic byte prefix.
    """
    return isinstance(data, bytes) and data.startswith(MSGPACK_MAGIC_BYTE)


def encode_msgpack(data: dict[str, Any], *, track_stats: bool = True) -> bytes:
    """Encode data to MessagePack with magic byte prefix.

    Convenience function that wraps MessagePackEncoder.encode().

    Args:
        data: Dictionary to encode
        track_stats: Whether to update global statistics

    Returns:
        MessagePack encoded bytes with magic byte prefix
    """
    return MessagePackEncoder.encode(data, track_stats=track_stats)


def decode_msgpack(data: bytes, *, track_stats: bool = True) -> dict[str, Any]:
    """Decode MessagePack data to dictionary.

    Convenience function that wraps MessagePackEncoder.decode().

    Args:
        data: MessagePack encoded bytes
        track_stats: Whether to update global statistics

    Returns:
        Decoded dictionary
    """
    return MessagePackEncoder.decode(data, track_stats=track_stats)


def prepare_msgpack_message(
    message: str | dict[str, Any],
    *,
    track_stats: bool = True,
) -> tuple[bytes, bool]:
    """Prepare a message for sending using MessagePack serialization.

    This is the MessagePack equivalent of compression.prepare_message().
    Always encodes as MessagePack (no threshold - MessagePack is efficient for all sizes).

    Args:
        message: The message to prepare (JSON string or dict).
        track_stats: Whether to update global statistics.

    Returns:
        Tuple of (prepared_bytes, was_encoded).
        - (bytes with magic header, True) on success
        - Falls back to JSON string on error
    """
    import json

    # Parse JSON string to dict if needed
    message_dict: dict[str, Any]
    if isinstance(message, str):
        try:
            parsed = json.loads(message)
            if not isinstance(parsed, dict):
                logger.warning("JSON parsed to non-dict, cannot encode as MessagePack")
                return message.encode("utf-8"), False
            message_dict = parsed
        except json.JSONDecodeError:
            # Not valid JSON, can't encode as MessagePack
            logger.warning("Cannot encode non-JSON string as MessagePack")
            return message.encode("utf-8"), False
    else:
        message_dict = message

    try:
        encoded = MessagePackEncoder.encode(message_dict, track_stats=track_stats)
        return encoded, True
    except ValueError:
        # Fall back to JSON on encoding error
        logger.warning("MessagePack encoding failed, falling back to JSON")
        return json.dumps(message_dict).encode("utf-8"), False
