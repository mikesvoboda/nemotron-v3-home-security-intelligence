"""WebSocket infrastructure for real-time event broadcasting.

This module provides centralized WebSocket event management including:
- Event type registry with standardized event types
- Event payload schemas with Pydantic validation
- WebSocket emitter service for broadcasting events
- Subscription management for event filtering (NEM-2383)
- Message compression for bandwidth optimization (NEM-3154)

Usage:
    from backend.core.websocket import (
        WebSocketEventType,
        WebSocketEvent,
        create_event,
        get_event_channel,
        validate_payload,
    )

    # Create an event
    event = create_event(
        WebSocketEventType.ALERT_CREATED,
        {"alert_id": "123", "severity": "high"},
        correlation_id="req-abc123",
    )

    # Validate a payload
    from backend.core.websocket.event_schemas import AlertCreatedPayload
    payload = AlertCreatedPayload.model_validate(data)

    # Use subscription manager for event filtering
    from backend.core.websocket import get_subscription_manager, SubscriptionManager
    manager = get_subscription_manager()
    manager.subscribe("conn-123", ["alert.*", "camera.status_changed"])
    if manager.should_send("conn-123", "alert.created"):
        # Send the event
        pass

    # Use compression for large messages (NEM-3154)
    from backend.core.websocket import prepare_message, get_compression_stats
    prepared, was_compressed = prepare_message(large_payload)
    if was_compressed:
        await websocket.send_bytes(prepared)
    else:
        await websocket.send_text(prepared)
"""

from backend.core.websocket.compression import (
    COMPRESSION_MAGIC_BYTE,
    MSGPACK_MAGIC_BYTE,
    CompressionStats,
    SerializationFormat,
    compress_message,
    decode_message_auto,
    decode_msgpack,
    decompress_message,
    detect_format,
    encode_msgpack,
    get_compression_stats,
    is_compressed_message,
    is_msgpack_message,
    prepare_message,
    prepare_message_with_format,
    reset_compression_stats,
    should_compress,
)
from backend.core.websocket.connection_health import (
    ConnectionHealth,
    ConnectionHealthStatus,
    ConnectionHealthTracker,
    ConnectionMetrics,
    get_health_tracker,
    reset_health_tracker_state,
)
from backend.core.websocket.event_types import (
    EVENT_TYPE_METADATA,
    WebSocketEvent,
    WebSocketEventType,
    create_event,
    get_all_channels,
    get_all_event_types,
    get_event_channel,
    get_event_description,
    get_event_types_by_channel,
    get_required_payload_fields,
    validate_event_type,
)
from backend.core.websocket.message_batcher import (
    BatchedMessage,
    BatchMetrics,
    MessageBatcher,
    get_message_batcher,
    reset_message_batcher_state,
    stop_message_batcher,
)
from backend.core.websocket.sequence_tracker import (
    SequenceTracker,
    get_sequence_tracker,
    reset_sequence_tracker_state,
)
from backend.core.websocket.subscription_manager import (
    SubscriptionManager,
    SubscriptionRequest,
    SubscriptionResponse,
    get_subscription_manager,
    reset_subscription_manager_state,
)

__all__ = [
    "COMPRESSION_MAGIC_BYTE",
    "EVENT_TYPE_METADATA",
    "MSGPACK_MAGIC_BYTE",
    "BatchMetrics",
    "BatchedMessage",
    "CompressionStats",
    "ConnectionHealth",
    "ConnectionHealthStatus",
    "ConnectionHealthTracker",
    "ConnectionMetrics",
    "MessageBatcher",
    "SequenceTracker",
    "SerializationFormat",
    "SubscriptionManager",
    "SubscriptionRequest",
    "SubscriptionResponse",
    "WebSocketEvent",
    "WebSocketEventType",
    "compress_message",
    "create_event",
    "decode_message_auto",
    "decode_msgpack",
    "decompress_message",
    "detect_format",
    "encode_msgpack",
    "get_all_channels",
    "get_all_event_types",
    "get_compression_stats",
    "get_event_channel",
    "get_event_description",
    "get_event_types_by_channel",
    "get_health_tracker",
    "get_message_batcher",
    "get_required_payload_fields",
    "get_sequence_tracker",
    "get_subscription_manager",
    "is_compressed_message",
    "is_msgpack_message",
    "prepare_message",
    "prepare_message_with_format",
    "reset_compression_stats",
    "reset_health_tracker_state",
    "reset_message_batcher_state",
    "reset_sequence_tracker_state",
    "reset_subscription_manager_state",
    "should_compress",
    "stop_message_batcher",
    "validate_event_type",
]
