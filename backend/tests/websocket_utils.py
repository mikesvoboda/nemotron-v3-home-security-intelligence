"""WebSocket testing utilities for backend tests.

This module provides helper functions for WebSocket testing:
- Message creation with proper formatting
- Broadcast simulation
- Subscription state assertions
- Connection state verification

Usage:
    from backend.tests.websocket_utils import create_ws_message, simulate_ws_broadcast

    # Create properly formatted WebSocket message
    message = create_ws_message("event", {"id": 1, "risk_score": 75})

    # Simulate broadcast to WebSocket
    await simulate_ws_broadcast(mock_websocket, "security_events", message)

    # Assert subscription state
    assert_ws_subscribed(mock_websocket, "security_events")
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock

if TYPE_CHECKING:
    from unittest.mock import MagicMock


def create_ws_message(event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Create a properly formatted WebSocket message.

    WebSocket messages follow the envelope format:
        {
            "type": "<event_type>",
            "data": <payload>
        }

    Args:
        event_type: The message type (e.g., "event", "detection", "system_status")
        payload: The message payload/data

    Returns:
        A properly formatted WebSocket message dict

    Example:
        >>> message = create_ws_message("event", {"id": 1, "risk_score": 75})
        >>> assert message["type"] == "event"
        >>> assert message["data"]["id"] == 1
    """
    return {"type": event_type, "data": payload}


async def simulate_ws_broadcast(
    mock_websocket: MagicMock, channel: str, message: dict[str, Any] | str
) -> None:
    """Simulate a broadcast message being sent to a WebSocket client.

    This helper simulates the EventBroadcaster or SystemBroadcaster
    sending a message to a connected WebSocket client.

    Args:
        mock_websocket: Mock WebSocket client (from mock_websocket_client fixture)
        channel: Channel name (e.g., "security_events", "system_status")
        message: Message to broadcast (dict will be JSON-encoded)

    Example:
        >>> await simulate_ws_broadcast(
        ...     mock_ws,
        ...     "security_events",
        ...     create_ws_message("event", {"id": 1})
        ... )
        >>> assert mock_ws.send_text.called
    """
    # Convert dict to JSON string if needed
    message_str = json.dumps(message) if isinstance(message, dict) else message

    # Simulate broadcast by calling send_text
    await mock_websocket.send_text(message_str)


def assert_ws_subscribed(mock_websocket: MagicMock, channel: str) -> None:
    """Assert that a WebSocket client is subscribed to a specific channel.

    Args:
        mock_websocket: Mock WebSocket client (from mock_websocket_client fixture)
        channel: Channel name to verify subscription

    Raises:
        AssertionError: If the WebSocket is not subscribed to the channel

    Example:
        >>> mock_ws.subscriptions.add("security_events")
        >>> assert_ws_subscribed(mock_ws, "security_events")
    """
    if not hasattr(mock_websocket, "subscriptions"):
        raise AssertionError(
            "WebSocket mock does not have 'subscriptions' attribute. "
            "Ensure you're using the mock_websocket_client fixture."
        )

    if channel not in mock_websocket.subscriptions:
        raise AssertionError(
            f"WebSocket not subscribed to channel '{channel}'. "
            f"Current subscriptions: {mock_websocket.subscriptions}"
        )


def assert_ws_not_subscribed(mock_websocket: MagicMock, channel: str) -> None:
    """Assert that a WebSocket client is NOT subscribed to a specific channel.

    Args:
        mock_websocket: Mock WebSocket client (from mock_websocket_client fixture)
        channel: Channel name to verify non-subscription

    Raises:
        AssertionError: If the WebSocket IS subscribed to the channel

    Example:
        >>> assert_ws_not_subscribed(mock_ws, "unknown_channel")
    """
    if not hasattr(mock_websocket, "subscriptions"):
        raise AssertionError(
            "WebSocket mock does not have 'subscriptions' attribute. "
            "Ensure you're using the mock_websocket_client fixture."
        )

    if channel in mock_websocket.subscriptions:
        raise AssertionError(
            f"WebSocket unexpectedly subscribed to channel '{channel}'. "
            f"Current subscriptions: {mock_websocket.subscriptions}"
        )


def assert_ws_connected(mock_websocket: MagicMock) -> None:
    """Assert that a WebSocket client is in connected state.

    Args:
        mock_websocket: Mock WebSocket client (from mock_websocket_client fixture)

    Raises:
        AssertionError: If the WebSocket is not connected

    Example:
        >>> await mock_ws.accept()
        >>> assert_ws_connected(mock_ws)
    """
    from fastapi.websockets import WebSocketState

    if not hasattr(mock_websocket, "client_state"):
        raise AssertionError(
            "WebSocket mock does not have 'client_state' attribute. "
            "Ensure you're using the mock_websocket_client fixture."
        )

    if mock_websocket.client_state != WebSocketState.CONNECTED:
        raise AssertionError(
            f"WebSocket not connected. Current state: {mock_websocket.client_state}"
        )


def assert_ws_disconnected(mock_websocket: MagicMock) -> None:
    """Assert that a WebSocket client is in disconnected state.

    Args:
        mock_websocket: Mock WebSocket client (from mock_websocket_client fixture)

    Raises:
        AssertionError: If the WebSocket is not disconnected

    Example:
        >>> await mock_ws.close()
        >>> assert_ws_disconnected(mock_ws)
    """
    from fastapi.websockets import WebSocketState

    if not hasattr(mock_websocket, "client_state"):
        raise AssertionError(
            "WebSocket mock does not have 'client_state' attribute. "
            "Ensure you're using the mock_websocket_client fixture."
        )

    if mock_websocket.client_state != WebSocketState.DISCONNECTED:
        raise AssertionError(
            f"WebSocket not disconnected. Current state: {mock_websocket.client_state}"
        )


def assert_ws_message_sent(
    mock_websocket: MagicMock, event_type: str | None = None, count: int | None = None
) -> None:
    """Assert that a WebSocket client has sent messages.

    Args:
        mock_websocket: Mock WebSocket client (from mock_websocket_client fixture)
        event_type: Optional event type to filter messages (checks message["data"] if JSON)
        count: Optional exact count of messages expected

    Raises:
        AssertionError: If the expected messages were not sent

    Example:
        >>> await mock_ws.send_text('{"type": "event", "data": {...}}')
        >>> assert_ws_message_sent(mock_ws, event_type="event", count=1)
    """
    if not hasattr(mock_websocket, "sent_messages"):
        raise AssertionError(
            "WebSocket mock does not have 'sent_messages' attribute. "
            "Ensure you're using the mock_websocket_client fixture."
        )

    messages = mock_websocket.sent_messages

    if count is not None and len(messages) != count:
        raise AssertionError(
            f"Expected {count} messages sent, but found {len(messages)}. Messages: {messages}"
        )

    if event_type is not None:
        # Filter messages by event type
        matching_messages = []
        for msg in messages:
            if msg.get("type") == "text":
                try:
                    data = json.loads(msg["data"])
                    if data.get("type") == event_type:
                        matching_messages.append(msg)
                except (json.JSONDecodeError, KeyError):
                    pass
            elif msg.get("type") == "json":
                data = msg.get("data", {})
                if data.get("type") == event_type:
                    matching_messages.append(msg)

        if not matching_messages:
            raise AssertionError(
                f"No messages with event_type='{event_type}' found. Total messages: {len(messages)}"
            )


def get_ws_sent_messages(
    mock_websocket: MagicMock, event_type: str | None = None, as_json: bool = True
) -> list[dict[str, Any]]:
    """Get messages sent by a WebSocket client.

    Args:
        mock_websocket: Mock WebSocket client (from mock_websocket_client fixture)
        event_type: Optional event type to filter messages
        as_json: If True, parse text messages as JSON

    Returns:
        List of sent messages (as dicts if as_json=True)

    Example:
        >>> messages = get_ws_sent_messages(mock_ws, event_type="event")
        >>> assert len(messages) == 1
        >>> assert messages[0]["data"]["id"] == 1
    """
    if not hasattr(mock_websocket, "sent_messages"):
        return []

    messages = []
    for msg in mock_websocket.sent_messages:
        msg_data = None

        if msg.get("type") == "text" and as_json:
            try:
                msg_data = json.loads(msg["data"])
            except json.JSONDecodeError:
                msg_data = msg["data"]
        elif msg.get("type") == "json" or msg.get("type") == "text":
            msg_data = msg["data"]

        # Filter by event type if specified
        if event_type is not None and isinstance(msg_data, dict):
            if msg_data.get("type") == event_type:
                messages.append(msg_data)
        elif msg_data is not None:
            messages.append(msg_data)

    return messages


def create_mock_ws_connection_manager() -> AsyncMock:
    """Create a mock WebSocket connection manager.

    This simulates the EventBroadcaster or SystemBroadcaster connection manager
    for testing broadcast functionality.

    Returns:
        AsyncMock configured as a connection manager

    Example:
        >>> manager = create_mock_ws_connection_manager()
        >>> await manager.broadcast(create_ws_message("event", {...}))
        >>> assert manager.broadcast.called
    """
    manager = AsyncMock()
    manager.connections = set()
    manager.broadcast = AsyncMock()
    manager.connect = AsyncMock()
    manager.disconnect = AsyncMock()
    manager.add_connection = AsyncMock()
    manager.remove_connection = AsyncMock()
    return manager
