"""Unit tests for WebSocket testing utilities.

This module tests the WebSocket mock fixture and helper utilities
to ensure they work correctly for testing WebSocket functionality.
"""

from __future__ import annotations

import json

import pytest
from fastapi.websockets import WebSocketState

from backend.tests.websocket_utils import (
    assert_ws_connected,
    assert_ws_disconnected,
    assert_ws_message_sent,
    assert_ws_not_subscribed,
    assert_ws_subscribed,
    create_mock_ws_connection_manager,
    create_ws_message,
    get_ws_sent_messages,
    simulate_ws_broadcast,
)


class TestCreateWsMessage:
    """Tests for create_ws_message utility."""

    def test_creates_message_with_correct_structure(self):
        """Test that create_ws_message creates properly formatted messages."""
        message = create_ws_message("event", {"id": 1, "risk_score": 75})

        assert "type" in message
        assert "data" in message
        assert message["type"] == "event"
        assert message["data"]["id"] == 1
        assert message["data"]["risk_score"] == 75

    def test_creates_message_with_nested_payload(self):
        """Test creating messages with complex nested payloads."""
        payload = {
            "event": {
                "id": 1,
                "metadata": {"camera": "front_door", "detections": [1, 2, 3]},
            }
        }
        message = create_ws_message("event", payload)

        assert message["type"] == "event"
        assert message["data"]["event"]["id"] == 1
        assert len(message["data"]["event"]["metadata"]["detections"]) == 3

    def test_creates_message_with_empty_payload(self):
        """Test creating messages with empty payloads."""
        message = create_ws_message("ping", {})

        assert message["type"] == "ping"
        assert message["data"] == {}


class TestSimulateWsBroadcast:
    """Tests for simulate_ws_broadcast utility."""

    @pytest.mark.asyncio
    async def test_broadcasts_dict_message(self, mock_websocket_client):
        """Test broadcasting a dict message to WebSocket."""
        message = create_ws_message("event", {"id": 1})

        await simulate_ws_broadcast(mock_websocket_client, "security_events", message)

        # Verify send_text was called
        assert mock_websocket_client.send_text.called
        assert len(mock_websocket_client.sent_messages) == 1

        # Verify message content
        sent_msg = mock_websocket_client.sent_messages[0]
        assert sent_msg["type"] == "text"
        assert json.loads(sent_msg["data"]) == message

    @pytest.mark.asyncio
    async def test_broadcasts_string_message(self, mock_websocket_client):
        """Test broadcasting a string message to WebSocket."""
        message = '{"type": "event", "data": {"id": 1}}'

        await simulate_ws_broadcast(mock_websocket_client, "security_events", message)

        assert mock_websocket_client.send_text.called
        sent_msg = mock_websocket_client.sent_messages[0]
        assert sent_msg["data"] == message


class TestAssertWsSubscribed:
    """Tests for assert_ws_subscribed utility."""

    def test_passes_when_subscribed(self, mock_websocket_client):
        """Test assertion passes when WebSocket is subscribed."""
        mock_websocket_client.subscriptions.add("security_events")

        # Should not raise
        assert_ws_subscribed(mock_websocket_client, "security_events")

    def test_fails_when_not_subscribed(self, mock_websocket_client):
        """Test assertion fails when WebSocket is not subscribed."""
        with pytest.raises(AssertionError, match="WebSocket not subscribed"):
            assert_ws_subscribed(mock_websocket_client, "security_events")

    def test_shows_current_subscriptions_in_error(self, mock_websocket_client):
        """Test error message shows current subscriptions."""
        mock_websocket_client.subscriptions.add("system_status")

        with pytest.raises(AssertionError, match="system_status"):
            assert_ws_subscribed(mock_websocket_client, "security_events")


class TestAssertWsNotSubscribed:
    """Tests for assert_ws_not_subscribed utility."""

    def test_passes_when_not_subscribed(self, mock_websocket_client):
        """Test assertion passes when WebSocket is not subscribed."""
        # Should not raise
        assert_ws_not_subscribed(mock_websocket_client, "security_events")

    def test_fails_when_subscribed(self, mock_websocket_client):
        """Test assertion fails when WebSocket is subscribed."""
        mock_websocket_client.subscriptions.add("security_events")

        with pytest.raises(AssertionError, match="unexpectedly subscribed"):
            assert_ws_not_subscribed(mock_websocket_client, "security_events")


class TestAssertWsConnected:
    """Tests for assert_ws_connected utility."""

    @pytest.mark.asyncio
    async def test_passes_when_connected(self, mock_websocket_client):
        """Test assertion passes when WebSocket is connected."""
        await mock_websocket_client.accept()

        # Should not raise
        assert_ws_connected(mock_websocket_client)
        assert mock_websocket_client.client_state == WebSocketState.CONNECTED

    def test_fails_when_disconnected(self, mock_websocket_client):
        """Test assertion fails when WebSocket is disconnected."""
        # Default state is disconnected
        with pytest.raises(AssertionError, match="not connected"):
            assert_ws_connected(mock_websocket_client)


class TestAssertWsDisconnected:
    """Tests for assert_ws_disconnected utility."""

    def test_passes_when_disconnected(self, mock_websocket_client):
        """Test assertion passes when WebSocket is disconnected."""
        # Default state is disconnected
        assert_ws_disconnected(mock_websocket_client)

    @pytest.mark.asyncio
    async def test_fails_when_connected(self, mock_websocket_client):
        """Test assertion fails when WebSocket is connected."""
        await mock_websocket_client.accept()

        with pytest.raises(AssertionError, match="not disconnected"):
            assert_ws_disconnected(mock_websocket_client)

    @pytest.mark.asyncio
    async def test_passes_after_close(self, mock_websocket_client):
        """Test assertion passes after closing connection."""
        await mock_websocket_client.accept()
        await mock_websocket_client.close()

        assert_ws_disconnected(mock_websocket_client)


class TestAssertWsMessageSent:
    """Tests for assert_ws_message_sent utility."""

    @pytest.mark.asyncio
    async def test_passes_when_messages_sent(self, mock_websocket_client):
        """Test assertion passes when messages were sent."""
        await mock_websocket_client.send_text('{"type": "event", "data": {}}')

        # Should not raise
        assert_ws_message_sent(mock_websocket_client)

    def test_fails_when_no_messages_sent(self, mock_websocket_client):
        """Test assertion fails when no messages were sent."""
        # No messages sent
        with pytest.raises(AssertionError):
            assert_ws_message_sent(mock_websocket_client, count=1)

    @pytest.mark.asyncio
    async def test_verifies_message_count(self, mock_websocket_client):
        """Test assertion verifies exact message count."""
        await mock_websocket_client.send_text('{"type": "event", "data": {}}')
        await mock_websocket_client.send_text('{"type": "event", "data": {}}')

        assert_ws_message_sent(mock_websocket_client, count=2)

        with pytest.raises(AssertionError, match="Expected 3 messages"):
            assert_ws_message_sent(mock_websocket_client, count=3)

    @pytest.mark.asyncio
    async def test_filters_by_event_type(self, mock_websocket_client):
        """Test assertion filters messages by event type."""
        await mock_websocket_client.send_text('{"type": "event", "data": {}}')
        await mock_websocket_client.send_text('{"type": "system_status", "data": {}}')

        # Should find event type
        assert_ws_message_sent(mock_websocket_client, event_type="event")

        # Should not find unknown type
        with pytest.raises(AssertionError, match="No messages with event_type"):
            assert_ws_message_sent(mock_websocket_client, event_type="unknown")


class TestGetWsSentMessages:
    """Tests for get_ws_sent_messages utility."""

    @pytest.mark.asyncio
    async def test_returns_all_messages(self, mock_websocket_client):
        """Test getting all sent messages."""
        msg1 = create_ws_message("event", {"id": 1})
        msg2 = create_ws_message("event", {"id": 2})

        await mock_websocket_client.send_text(json.dumps(msg1))
        await mock_websocket_client.send_text(json.dumps(msg2))

        messages = get_ws_sent_messages(mock_websocket_client)
        assert len(messages) == 2
        assert messages[0]["data"]["id"] == 1
        assert messages[1]["data"]["id"] == 2

    @pytest.mark.asyncio
    async def test_filters_by_event_type(self, mock_websocket_client):
        """Test filtering messages by event type."""
        event_msg = create_ws_message("event", {"id": 1})
        system_msg = create_ws_message("system_status", {"uptime": 100})

        await mock_websocket_client.send_text(json.dumps(event_msg))
        await mock_websocket_client.send_text(json.dumps(system_msg))

        event_messages = get_ws_sent_messages(mock_websocket_client, event_type="event")
        assert len(event_messages) == 1
        assert event_messages[0]["data"]["id"] == 1

    def test_returns_empty_list_when_no_messages(self, mock_websocket_client):
        """Test returns empty list when no messages sent."""
        messages = get_ws_sent_messages(mock_websocket_client)
        assert messages == []


class TestMockWebsocketClient:
    """Tests for mock_websocket_client fixture."""

    @pytest.mark.asyncio
    async def test_tracks_connection_state(self, mock_websocket_client):
        """Test that connection state is tracked correctly."""
        assert mock_websocket_client.client_state == WebSocketState.DISCONNECTED

        await mock_websocket_client.accept()
        assert mock_websocket_client.client_state == WebSocketState.CONNECTED

        await mock_websocket_client.close()
        assert mock_websocket_client.client_state == WebSocketState.DISCONNECTED

    @pytest.mark.asyncio
    async def test_tracks_sent_messages(self, mock_websocket_client):
        """Test that sent messages are tracked."""
        assert len(mock_websocket_client.sent_messages) == 0

        await mock_websocket_client.send_text("message1")
        assert len(mock_websocket_client.sent_messages) == 1

        await mock_websocket_client.send_json({"key": "value"})
        assert len(mock_websocket_client.sent_messages) == 2

    @pytest.mark.asyncio
    async def test_tracks_close_code(self, mock_websocket_client):
        """Test that close code is tracked."""
        await mock_websocket_client.accept()
        await mock_websocket_client.close(code=1008)

        assert mock_websocket_client.close_code == 1008

    def test_has_query_params_and_headers(self, mock_websocket_client):
        """Test that query params and headers are available."""
        assert hasattr(mock_websocket_client, "query_params")
        assert hasattr(mock_websocket_client, "headers")

        mock_websocket_client.query_params["api_key"] = "test_key"  # pragma: allowlist secret
        assert mock_websocket_client.query_params["api_key"] == "test_key"

    def test_has_subscription_tracking(self, mock_websocket_client):
        """Test that subscription tracking is available."""
        assert hasattr(mock_websocket_client, "subscriptions")
        assert len(mock_websocket_client.subscriptions) == 0

        mock_websocket_client.subscriptions.add("test_channel")
        assert "test_channel" in mock_websocket_client.subscriptions


class TestCreateMockWsConnectionManager:
    """Tests for create_mock_ws_connection_manager utility."""

    def test_creates_connection_manager(self):
        """Test creating a mock connection manager."""
        manager = create_mock_ws_connection_manager()

        assert hasattr(manager, "connections")
        assert hasattr(manager, "broadcast")
        assert hasattr(manager, "connect")
        assert hasattr(manager, "disconnect")

    @pytest.mark.asyncio
    async def test_connection_manager_tracks_connections(self):
        """Test that connection manager tracks connections."""
        manager = create_mock_ws_connection_manager()
        mock_ws = object()  # Simple object to represent connection

        manager.connections.add(mock_ws)
        assert mock_ws in manager.connections

        manager.connections.remove(mock_ws)
        assert mock_ws not in manager.connections

    @pytest.mark.asyncio
    async def test_connection_manager_broadcast(self):
        """Test that broadcast method is available."""
        manager = create_mock_ws_connection_manager()
        message = create_ws_message("event", {"id": 1})

        await manager.broadcast(message)
        assert manager.broadcast.called
