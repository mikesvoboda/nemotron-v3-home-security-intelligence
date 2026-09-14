"""Example tests demonstrating WebSocket mock fixture usage.

This module provides practical examples of using the mock_websocket_client
fixture and websocket_utils helpers for testing WebSocket functionality.

These examples demonstrate:
- Basic connection lifecycle testing
- Message broadcasting simulation
- Subscription management
- Error injection for testing error handling
"""

from __future__ import annotations

import json

import pytest

from backend.tests.websocket_utils import (
    assert_ws_connected,
    assert_ws_message_sent,
    assert_ws_subscribed,
    create_ws_message,
    get_ws_sent_messages,
    simulate_ws_broadcast,
)


class TestWebSocketMockExamples:
    """Example tests showing common WebSocket testing patterns."""

    @pytest.mark.asyncio
    async def test_basic_connection_lifecycle(self, mock_websocket_client):
        """Example: Test basic WebSocket connection lifecycle.

        This demonstrates:
        1. Accepting a WebSocket connection
        2. Verifying connection state
        3. Closing the connection
        4. Verifying disconnection
        """
        # Initially disconnected
        assert not hasattr(mock_websocket_client, "client_state") or (
            mock_websocket_client.client_state.name == "DISCONNECTED"
        )

        # Accept connection
        await mock_websocket_client.accept()
        assert_ws_connected(mock_websocket_client)

        # Close connection
        await mock_websocket_client.close(code=1000)
        assert mock_websocket_client.close_code == 1000

    @pytest.mark.asyncio
    async def test_broadcasting_events(self, mock_websocket_client):
        """Example: Test broadcasting events to WebSocket clients.

        This demonstrates:
        1. Creating properly formatted WebSocket messages
        2. Simulating broadcasts to connected clients
        3. Verifying messages were sent
        4. Inspecting sent message content
        """
        # Create an event message
        event_data = {
            "id": 1,
            "event_id": 1,
            "batch_id": "batch_123",
            "camera_id": "camera_456",
            "risk_score": 75,
            "risk_level": "high",
            "summary": "Person detected at front door",
            "reasoning": "A person was detected approaching the entry point",
            "started_at": "2025-01-21T12:00:00",
        }
        message = create_ws_message("event", event_data)

        # Simulate broadcasting to the WebSocket
        await simulate_ws_broadcast(mock_websocket_client, "security_events", message)

        # Verify the message was sent
        assert_ws_message_sent(mock_websocket_client, event_type="event", count=1)

        # Inspect the sent message
        sent_messages = get_ws_sent_messages(mock_websocket_client, event_type="event")
        assert len(sent_messages) == 1
        assert sent_messages[0]["data"]["id"] == 1
        assert sent_messages[0]["data"]["risk_score"] == 75

    @pytest.mark.asyncio
    async def test_subscription_management(self, mock_websocket_client):
        """Example: Test WebSocket subscription management.

        This demonstrates:
        1. Subscribing to channels
        2. Verifying subscription state
        3. Unsubscribing from channels
        4. Verifying non-subscription
        """
        # Subscribe to security_events channel
        mock_websocket_client.subscriptions.add("security_events")
        assert_ws_subscribed(mock_websocket_client, "security_events")

        # Subscribe to system_status channel
        mock_websocket_client.subscriptions.add("system_status")
        assert_ws_subscribed(mock_websocket_client, "system_status")

        # Unsubscribe from security_events
        mock_websocket_client.subscriptions.remove("security_events")
        from backend.tests.websocket_utils import assert_ws_not_subscribed

        assert_ws_not_subscribed(mock_websocket_client, "security_events")
        assert_ws_subscribed(mock_websocket_client, "system_status")

    @pytest.mark.asyncio
    async def test_multiple_message_types(self, mock_websocket_client):
        """Example: Test handling multiple message types.

        This demonstrates:
        1. Sending different message types (event, system_status, detection)
        2. Filtering messages by type
        3. Counting messages of specific types
        """
        # Send various message types
        event_msg = create_ws_message("event", {"id": 1, "risk_score": 75})
        status_msg = create_ws_message("system_status", {"uptime": 3600})
        detection_msg = create_ws_message("detection", {"object_type": "person"})

        await simulate_ws_broadcast(mock_websocket_client, "channel", event_msg)
        await simulate_ws_broadcast(mock_websocket_client, "channel", status_msg)
        await simulate_ws_broadcast(mock_websocket_client, "channel", detection_msg)
        await simulate_ws_broadcast(mock_websocket_client, "channel", event_msg)

        # Verify total messages
        assert len(mock_websocket_client.sent_messages) == 4

        # Filter by event type
        event_messages = get_ws_sent_messages(mock_websocket_client, event_type="event")
        assert len(event_messages) == 2

        status_messages = get_ws_sent_messages(mock_websocket_client, event_type="system_status")
        assert len(status_messages) == 1

    @pytest.mark.asyncio
    async def test_message_format_validation(self, mock_websocket_client):
        """Example: Test that messages follow the correct format.

        This demonstrates:
        1. Creating messages with the envelope format
        2. Verifying message structure
        3. Validating required fields
        """
        # Create a properly formatted message
        message = create_ws_message(
            "event",
            {
                "id": 1,
                "event_id": 1,
                "batch_id": "batch_123",
                "camera_id": "camera_456",
                "risk_score": 75,
                "risk_level": "high",
                "summary": "Test event",
                "reasoning": "Test reasoning",
                "started_at": "2025-01-21T12:00:00",
            },
        )

        # Verify envelope structure
        assert "type" in message
        assert "data" in message
        assert message["type"] == "event"

        # Verify data fields
        assert message["data"]["id"] == 1
        assert message["data"]["risk_score"] == 75

        # Broadcast and verify
        await simulate_ws_broadcast(mock_websocket_client, "security_events", message)

        sent = get_ws_sent_messages(mock_websocket_client)[0]
        assert sent == message

    @pytest.mark.asyncio
    async def test_query_params_and_headers(self, mock_websocket_client):
        """Example: Test WebSocket with query parameters and headers.

        This demonstrates:
        1. Setting query parameters (e.g., for authentication)
        2. Setting headers
        3. Accessing these values in tests
        """
        # Set query params (e.g., for API key authentication)
        mock_websocket_client.query_params["api_key"] = "test_key_123"  # pragma: allowlist secret
        mock_websocket_client.query_params["channel"] = "security_events"

        # Set headers
        mock_websocket_client.headers["user-agent"] = "TestClient/1.0"
        mock_websocket_client.headers["sec-websocket-protocol"] = (
            "api-key.test_key_123"  # pragma: allowlist secret
        )

        # Verify values are accessible
        expected_api_key = "test_key_123"  # pragma: allowlist secret
        assert mock_websocket_client.query_params["api_key"] == expected_api_key
        assert mock_websocket_client.headers["user-agent"] == "TestClient/1.0"

    @pytest.mark.asyncio
    async def test_send_different_formats(self, mock_websocket_client):
        """Example: Test sending messages in different formats.

        This demonstrates:
        1. Sending text messages
        2. Sending JSON messages
        3. Sending binary data
        4. Verifying message format in sent_messages
        """
        # Send text message
        await mock_websocket_client.send_text('{"type": "event", "data": {}}')

        # Send JSON directly
        await mock_websocket_client.send_json({"type": "system_status", "data": {}})

        # Send bytes
        await mock_websocket_client.send_bytes(b"binary data")

        # Verify formats
        assert len(mock_websocket_client.sent_messages) == 3
        assert mock_websocket_client.sent_messages[0]["type"] == "text"
        assert mock_websocket_client.sent_messages[1]["type"] == "json"
        assert mock_websocket_client.sent_messages[2]["type"] == "bytes"


class TestWebSocketErrorHandlingExamples:
    """Example tests showing error handling patterns."""

    @pytest.mark.asyncio
    async def test_connection_with_error_injection(self, mock_websocket_client):
        """Example: Test error handling with error injection.

        This demonstrates:
        1. Using the inject_error feature to simulate errors
        2. Testing error recovery
        3. Verifying error handling logic
        """
        # Accept connection normally
        await mock_websocket_client.accept()
        assert_ws_connected(mock_websocket_client)

        # Note: Error injection can be used in custom test scenarios
        # where you need to test how your code handles WebSocket errors
        mock_websocket_client.inject_error = Exception("Simulated error")

        # Your code under test would check inject_error and handle it
        if mock_websocket_client.inject_error:
            # Simulate error handling
            await mock_websocket_client.close(code=1011)
            assert mock_websocket_client.close_code == 1011

    @pytest.mark.asyncio
    async def test_receive_text_with_mock_data(self, mock_websocket_client):
        """Example: Test receiving text messages from client.

        This demonstrates:
        1. Configuring receive_text to return test data
        2. Simulating client messages
        3. Processing received data
        """
        # Configure what the client will send
        mock_websocket_client.receive_text.return_value = json.dumps(
            {"action": "subscribe", "channel": "security_events"}
        )

        # Simulate receiving a message
        received = await mock_websocket_client.receive_text()
        data = json.loads(received)

        assert data["action"] == "subscribe"
        assert data["channel"] == "security_events"
