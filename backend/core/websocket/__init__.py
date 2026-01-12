"""WebSocket infrastructure for real-time event broadcasting.

This module provides centralized WebSocket event management including:
- Event type registry with standardized event types
- Event payload schemas with Pydantic validation
- WebSocket emitter service for broadcasting events
- Subscription management for event filtering (NEM-2383)

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
"""

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
from backend.core.websocket.subscription_manager import (
    SubscriptionManager,
    SubscriptionRequest,
    SubscriptionResponse,
    get_subscription_manager,
    reset_subscription_manager_state,
)

__all__ = [
    "EVENT_TYPE_METADATA",
    "SubscriptionManager",
    "SubscriptionRequest",
    "SubscriptionResponse",
    "WebSocketEvent",
    "WebSocketEventType",
    "create_event",
    "get_all_channels",
    "get_all_event_types",
    "get_event_channel",
    "get_event_description",
    "get_event_types_by_channel",
    "get_required_payload_fields",
    "get_subscription_manager",
    "reset_subscription_manager_state",
    "validate_event_type",
]
