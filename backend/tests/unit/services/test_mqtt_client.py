"""Unit tests for MQTT Client Service (TDD Phase 1 - RED).

This module contains comprehensive unit tests for the MQTTClient service, which
manages async MQTT connections for publishing security events and subscribing to
command topics with automatic reconnection and health tracking.

Related Issues:
    - NEM-5068: TDD Phase 1 - Write tests for MQTT Client Service

Test Organization:
    - Initialization tests: Constructor parameters and settings
    - Connection tests: Broker connection, reconnection, disconnect
    - Publish tests: Message publishing with QoS levels and retain
    - Subscribe tests: Topic subscription and message callbacks
    - Health check tests: Connection health monitoring
    - Configuration tests: Settings and environment variables
    - Metrics tests: Prometheus metrics recording
    - Error handling tests: Retry logic and failure recovery

Acceptance Criteria:
    - MQTTClient accepts settings and dependencies
    - connect() establishes broker connection with retry
    - disconnect() cleans up gracefully
    - publish() sends messages with configurable QoS
    - subscribe() registers topic callbacks
    - health_check() returns connection status
    - Exponential backoff: 1s, 2s, 4s, 8s, max 60s
    - Connection failures trigger automatic reconnection
    - Prometheus metrics: hsi_mqtt_* prefix
    - Configuration via MQTT_ prefixed environment variables

Design Decisions:
    - Uses aiomqtt library for async MQTT operations
    - Follows patterns from DetectorClient and StreamManager
    - Redis optional for state persistence (not required)
    - Event broadcaster integration for publishing events
    - Graceful degradation when broker unavailable

Notes:
    Tests use mocks for aiomqtt client and Prometheus metrics.
    These tests will FAIL until the implementation is created.
"""

import asyncio
import ssl
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from backend.services.mqtt_client import (
    MQTT_PUBLISH_DURATION_BUCKETS,
    MQTTClient,
    MQTTClientSettings,
    MQTTConnectionError,
    MQTTPublishError,
)

# Test constants
MQTT_BROKER_HOST = "localhost"
MQTT_BROKER_PORT = 1883
MQTT_CLIENT_ID = "hsi-test-client"
MQTT_USERNAME = "test_user"
MQTT_PASSWORD = "test_pass"  # pragma: allowlist secret
MQTT_TOPIC_PREFIX = "hsi/test"


# Fixtures


@pytest.fixture
def mqtt_settings():
    """Create MQTT settings for testing."""
    return MQTTClientSettings(
        broker_host=MQTT_BROKER_HOST,
        broker_port=MQTT_BROKER_PORT,
        client_id=MQTT_CLIENT_ID,
        username=MQTT_USERNAME,
        password=MQTT_PASSWORD,
        topic_prefix=MQTT_TOPIC_PREFIX,
        qos_default=1,
        keepalive=60,
        reconnect_interval=1,
        max_reconnect_interval=60,
    )


@pytest.fixture
def mock_aiomqtt_client():
    """Create mock aiomqtt.Client."""
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.publish = AsyncMock()
    mock_client.subscribe = AsyncMock()
    mock_client.unsubscribe = AsyncMock()
    mock_client.messages = AsyncMock()
    return mock_client


@pytest.fixture
def mock_prometheus_metrics():
    """Mock Prometheus metrics."""
    with (
        patch("backend.services.mqtt_client.Counter", autospec=True) as mock_counter,
        patch("backend.services.mqtt_client.Histogram", autospec=True) as mock_histogram,
        patch("backend.services.mqtt_client.Gauge", autospec=True) as mock_gauge,
    ):
        # Create mock metric instances
        mock_counter_instance = MagicMock()
        mock_counter_instance.labels.return_value.inc = MagicMock()
        mock_counter.return_value = mock_counter_instance

        mock_histogram_instance = MagicMock()
        mock_histogram_instance.labels.return_value.observe = MagicMock()
        mock_histogram.return_value = mock_histogram_instance

        mock_gauge_instance = MagicMock()
        mock_gauge_instance.set = MagicMock()
        mock_gauge.return_value = mock_gauge_instance

        yield {
            "counter": mock_counter,
            "histogram": mock_histogram,
            "gauge": mock_gauge,
            "counter_instance": mock_counter_instance,
            "histogram_instance": mock_histogram_instance,
            "gauge_instance": mock_gauge_instance,
        }


@pytest.fixture
def mqtt_client(mqtt_settings):
    """Create MQTTClient instance with test settings."""
    return MQTTClient(settings=mqtt_settings)


# Initialization tests


def test_mqtt_client_accepts_settings(mqtt_settings):
    """Test MQTTClient __init__ accepts settings parameter.

    ACCEPTANCE: MQTTClient must accept MQTTClientSettings for configuration.
    """
    client = MQTTClient(settings=mqtt_settings)
    assert client.settings is mqtt_settings


def test_mqtt_client_initializes_with_default_state(mqtt_settings):
    """Test MQTTClient initializes with correct default state.

    ACCEPTANCE: Client should start disconnected with no active subscriptions.
    """
    client = MQTTClient(settings=mqtt_settings)
    assert client.connected is False
    assert len(client._subscriptions) == 0
    assert client._client is None


def test_mqtt_client_accepts_optional_dependencies(mqtt_settings):
    """Test MQTTClient accepts optional dependency injection.

    ACCEPTANCE: Client should accept optional params for testing/customization.
    """
    mock_redis = AsyncMock()
    mock_metrics_registry = MagicMock()

    client = MQTTClient(
        settings=mqtt_settings,
        redis_client=mock_redis,
        metrics_registry=mock_metrics_registry,
    )

    assert client.settings is mqtt_settings
    assert client._redis_client is mock_redis
    assert client._metrics_registry is mock_metrics_registry


# Configuration tests


def test_settings_from_env():
    """Test MQTTClientSettings loads from environment variables.

    ACCEPTANCE: Settings must support MQTT_ prefixed environment variables.
    """
    with patch.dict(
        "os.environ",
        {
            "MQTT_BROKER_HOST": "mqtt.example.com",
            "MQTT_BROKER_PORT": "8883",
            "MQTT_CLIENT_ID": "hsi-prod-client",
            "MQTT_USERNAME": "prod_user",
            "MQTT_PASSWORD": "prod_pass",  # pragma: allowlist secret
            "MQTT_TOPIC_PREFIX": "hsi/prod",
            "MQTT_QOS_DEFAULT": "2",
            "MQTT_KEEPALIVE": "120",
        },
    ):
        settings = MQTTClientSettings()

        assert settings.broker_host == "mqtt.example.com"
        assert settings.broker_port == 8883
        assert settings.client_id == "hsi-prod-client"
        assert settings.username == "prod_user"
        assert settings.password == "prod_pass"  # pragma: allowlist secret
        assert settings.topic_prefix == "hsi/prod"
        assert settings.qos_default == 2
        assert settings.keepalive == 120


def test_settings_defaults():
    """Test MQTTClientSettings uses correct default values.

    ACCEPTANCE: Settings must provide sensible defaults for optional params.
    """
    settings = MQTTClientSettings(broker_host="localhost")

    assert settings.broker_port == 1883
    assert settings.client_id is not None  # Should auto-generate
    assert settings.qos_default == 1
    assert settings.keepalive == 60
    assert settings.reconnect_interval == 1
    assert settings.max_reconnect_interval == 60
    assert settings.use_tls is False
    assert settings.topic_prefix == "hsi"


def test_tls_configuration():
    """Test MQTTClientSettings TLS/SSL configuration.

    ACCEPTANCE: Settings must support TLS configuration for secure connections.
    """
    settings = MQTTClientSettings(
        broker_host="secure.mqtt.example.com",
        broker_port=8883,
        use_tls=True,
        tls_ca_cert="/path/to/ca.crt",
        tls_certfile="/path/to/client.crt",
        tls_keyfile="/path/to/client.key",
    )

    assert settings.use_tls is True
    assert settings.tls_ca_cert == "/path/to/ca.crt"
    assert settings.tls_certfile == "/path/to/client.crt"
    assert settings.tls_keyfile == "/path/to/client.key"


# Connection tests


@pytest.mark.asyncio
async def test_connect_success(mqtt_client, mock_aiomqtt_client, mqtt_settings):
    """Test successful connection to MQTT broker.

    ACCEPTANCE: connect() must establish connection and set connected=True.
    """
    with patch(
        "backend.services.mqtt_client.aiomqtt.Client",
        return_value=mock_aiomqtt_client,
        autospec=True,
    ):
        await mqtt_client.connect()

        assert mqtt_client.connected is True
        assert mqtt_client._client is not None


@pytest.mark.asyncio
async def test_connect_failure_retry(mqtt_client, mqtt_settings):
    """Test connection failure with exponential backoff retry.

    ACCEPTANCE: Failed connections should retry with backoff: 1s, 2s, 4s, 8s, max 60s.
    """
    connection_attempts = []

    async def mock_connect_fail():
        connection_attempts.append(asyncio.get_event_loop().time())
        raise ConnectionError("Connection refused")

    with (
        patch("backend.services.mqtt_client.aiomqtt.Client", autospec=True) as mock_client_class,
        patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
    ):
        mock_client_class.return_value.__aenter__.side_effect = mock_connect_fail

        # Limit retries for test to avoid long run time
        mqtt_client.settings.max_retries = 4

        with pytest.raises(MQTTConnectionError, match=r"Failed to connect after .* retries"):
            await mqtt_client.connect()

        # Verify exponential backoff: 1s, 2s, 4s, 8s
        expected_sleeps = [1, 2, 4, 8]
        actual_sleeps = [call_args[0][0] for call_args in mock_sleep.call_args_list]

        assert len(actual_sleeps) == len(expected_sleeps)
        for actual, expected in zip(actual_sleeps, expected_sleeps, strict=False):
            assert actual == expected


@pytest.mark.asyncio
async def test_disconnect_graceful(mqtt_client, mock_aiomqtt_client):
    """Test graceful disconnection from MQTT broker.

    ACCEPTANCE: disconnect() must clean up resources and set connected=False.
    """
    with patch(
        "backend.services.mqtt_client.aiomqtt.Client",
        return_value=mock_aiomqtt_client,
        autospec=True,
    ):
        await mqtt_client.connect()
        assert mqtt_client.connected is True

        await mqtt_client.disconnect()

        assert mqtt_client.connected is False
        assert mqtt_client._client is None


@pytest.mark.asyncio
async def test_auto_reconnect(mqtt_client, mock_aiomqtt_client):
    """Test automatic reconnection on unexpected disconnect.

    ACCEPTANCE: Client should automatically reconnect when connection is lost.
    """
    reconnect_count = 0

    async def mock_publish_with_disconnect(*args, **kwargs):
        nonlocal reconnect_count
        if reconnect_count == 0:
            reconnect_count += 1
            raise ConnectionError("Connection lost")
        # Second attempt succeeds

    with patch(
        "backend.services.mqtt_client.aiomqtt.Client",
        return_value=mock_aiomqtt_client,
        autospec=True,
    ):
        mock_aiomqtt_client.publish.side_effect = mock_publish_with_disconnect

        await mqtt_client.connect()

        # This should trigger reconnection
        await mqtt_client.publish("test/topic", {"data": "test"})

        # Verify reconnection occurred
        assert reconnect_count == 1
        assert mqtt_client.connected is True


@pytest.mark.asyncio
async def test_connect_is_idempotent(mqtt_client, mock_aiomqtt_client):
    """Test calling connect() multiple times is safe.

    ACCEPTANCE: Double-connect should not cause errors or duplicate connections.
    """
    with patch(
        "backend.services.mqtt_client.aiomqtt.Client",
        return_value=mock_aiomqtt_client,
        autospec=True,
    ):
        await mqtt_client.connect()
        await mqtt_client.connect()  # Should be safe

        assert mqtt_client.connected is True


@pytest.mark.asyncio
async def test_disconnect_when_not_connected(mqtt_client):
    """Test calling disconnect() when not connected is safe.

    ACCEPTANCE: Disconnecting when already disconnected should be a no-op.
    """
    assert mqtt_client.connected is False

    await mqtt_client.disconnect()  # Should not raise

    assert mqtt_client.connected is False


# Publish tests


@pytest.mark.asyncio
async def test_publish_message_success(mqtt_client, mock_aiomqtt_client):
    """Test successful message publishing with default QoS.

    ACCEPTANCE: publish() should send message with configured QoS level.
    """
    with patch(
        "backend.services.mqtt_client.aiomqtt.Client",
        return_value=mock_aiomqtt_client,
        autospec=True,
    ):
        await mqtt_client.connect()

        topic = "events/camera/front_door"
        payload = {"event_type": "detection", "camera_id": "front_door"}

        await mqtt_client.publish(topic, payload)

        # Verify publish was called with correct parameters
        mock_aiomqtt_client.publish.assert_called_once()
        call_args = mock_aiomqtt_client.publish.call_args

        # Topic should include prefix
        assert call_args[0][0] == f"{MQTT_TOPIC_PREFIX}/{topic}"
        # QoS should be default from settings
        assert call_args[1]["qos"] == 1


@pytest.mark.asyncio
async def test_publish_with_qos_levels(mqtt_client, mock_aiomqtt_client):
    """Test publishing with different QoS levels (0, 1, 2).

    ACCEPTANCE: publish() should support QoS 0 (at most once), 1 (at least once), 2 (exactly once).
    """
    with patch(
        "backend.services.mqtt_client.aiomqtt.Client",
        return_value=mock_aiomqtt_client,
        autospec=True,
    ):
        await mqtt_client.connect()

        topic = "events/test"
        payload = {"data": "test"}

        # Test QoS 0
        await mqtt_client.publish(topic, payload, qos=0)
        assert mock_aiomqtt_client.publish.call_args[1]["qos"] == 0

        # Test QoS 1
        await mqtt_client.publish(topic, payload, qos=1)
        assert mock_aiomqtt_client.publish.call_args[1]["qos"] == 1

        # Test QoS 2
        await mqtt_client.publish(topic, payload, qos=2)
        assert mock_aiomqtt_client.publish.call_args[1]["qos"] == 2


@pytest.mark.asyncio
async def test_publish_with_retain(mqtt_client, mock_aiomqtt_client):
    """Test publishing with retain flag for persistent messages.

    ACCEPTANCE: publish() should support retain flag for last will messages.
    """
    with patch(
        "backend.services.mqtt_client.aiomqtt.Client",
        return_value=mock_aiomqtt_client,
        autospec=True,
    ):
        await mqtt_client.connect()

        topic = "status/system"
        payload = {"status": "online"}

        # Publish with retain=True
        await mqtt_client.publish(topic, payload, retain=True)

        call_args = mock_aiomqtt_client.publish.call_args
        assert call_args[1]["retain"] is True


@pytest.mark.asyncio
async def test_publish_failure_retry(mqtt_client, mock_aiomqtt_client):
    """Test retry logic when publish fails.

    ACCEPTANCE: Failed publish should retry with exponential backoff.
    """
    publish_attempts = []

    async def mock_publish_fail(*args, **kwargs):
        publish_attempts.append(1)
        if len(publish_attempts) < 3:
            raise ConnectionError("Publish failed")
        # Third attempt succeeds

    with (
        patch(
            "backend.services.mqtt_client.aiomqtt.Client",
            return_value=mock_aiomqtt_client,
            autospec=True,
        ),
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        mock_aiomqtt_client.publish.side_effect = mock_publish_fail

        await mqtt_client.connect()
        await mqtt_client.publish("test/topic", {"data": "test"})

        # Should have retried
        assert len(publish_attempts) == 3


@pytest.mark.asyncio
async def test_publish_when_disconnected(mqtt_client):
    """Test publishing when not connected raises error or queues message.

    ACCEPTANCE: publish() should handle disconnected state gracefully.
    """
    assert mqtt_client.connected is False

    with pytest.raises(MQTTConnectionError, match="Not connected"):
        await mqtt_client.publish("test/topic", {"data": "test"})


@pytest.mark.asyncio
async def test_publish_json_serialization(mqtt_client, mock_aiomqtt_client):
    """Test automatic JSON serialization of payload.

    ACCEPTANCE: publish() should serialize dict payloads to JSON.
    """
    with patch(
        "backend.services.mqtt_client.aiomqtt.Client",
        return_value=mock_aiomqtt_client,
        autospec=True,
    ):
        await mqtt_client.connect()

        payload = {"nested": {"data": [1, 2, 3]}, "timestamp": "2026-02-01T00:00:00Z"}

        await mqtt_client.publish("test/topic", payload)

        # Verify JSON serialization
        call_args = mock_aiomqtt_client.publish.call_args
        payload_arg = call_args[0][1]

        # Should be JSON string
        import json

        assert isinstance(payload_arg, str)
        parsed = json.loads(payload_arg)
        assert parsed == payload


# Subscribe tests


@pytest.mark.asyncio
async def test_subscribe_topic(mqtt_client, mock_aiomqtt_client):
    """Test subscribing to a topic with callback.

    ACCEPTANCE: subscribe() should register topic and callback for message handling.
    """
    callback_invoked = False

    async def test_callback(topic: str, payload: dict):
        nonlocal callback_invoked
        callback_invoked = True

    with patch(
        "backend.services.mqtt_client.aiomqtt.Client",
        return_value=mock_aiomqtt_client,
        autospec=True,
    ):
        await mqtt_client.connect()

        topic = "commands/zone/arm"
        await mqtt_client.subscribe(topic, test_callback)

        # Verify subscription registered
        assert topic in mqtt_client._subscriptions
        assert mqtt_client._subscriptions[topic] == test_callback

        # Verify aiomqtt subscribe called
        mock_aiomqtt_client.subscribe.assert_called_once()
        assert mock_aiomqtt_client.subscribe.call_args[0][0] == f"{MQTT_TOPIC_PREFIX}/{topic}"


@pytest.mark.asyncio
async def test_subscribe_starts_message_pump(mqtt_client, mock_aiomqtt_client):
    """R-T9-MQTTPUMP regression lock: subscribe() must start the pump that
    feeds registered callbacks. Before the fix, _message_processing_loop had
    zero callers — subscribe() registered callbacks that could never fire
    (the disconnect() cancel-path was dead plumbing for a task never born).

    Rides the shared aiomqtt fake; its AsyncMock .messages keeps the pump
    parked on a non-terminating iterator, so the asserts are race-free and
    the fixture teardown (disconnect) is what proves the cancel-path leak
    check — a live task surviving disconnect would fail the final assert.
    """

    async def cb(topic: str, payload: dict) -> None:  # pragma: no cover - never fires
        pass

    assert mqtt_client._message_task is None  # no pump before subscribe

    with patch(
        "backend.services.mqtt_client.aiomqtt.Client",
        return_value=mock_aiomqtt_client,
        autospec=True,
    ):
        await mqtt_client.connect()
        await mqtt_client.subscribe("commands/pump-probe", cb)

        task = mqtt_client._message_task
        assert task is not None, "subscribe() started no message pump (R-T9-MQTTPUMP)"
        assert not task.done()

        await mqtt_client.disconnect()
        assert mqtt_client._message_task is None  # cancel-path ran, no leaked task


@pytest.mark.asyncio
async def test_subscribe_wildcard(mqtt_client, mock_aiomqtt_client):
    """Test subscribing to wildcard topic patterns.

    ACCEPTANCE: subscribe() should support MQTT wildcard patterns (+, #).
    """

    async def test_callback(topic: str, payload: dict):
        pass

    with patch(
        "backend.services.mqtt_client.aiomqtt.Client",
        return_value=mock_aiomqtt_client,
        autospec=True,
    ):
        await mqtt_client.connect()

        # Single-level wildcard
        await mqtt_client.subscribe("commands/+/arm", test_callback)
        assert "commands/+/arm" in mqtt_client._subscriptions

        # Multi-level wildcard
        await mqtt_client.subscribe("events/#", test_callback)
        assert "events/#" in mqtt_client._subscriptions


@pytest.mark.asyncio
async def test_unsubscribe(mqtt_client, mock_aiomqtt_client):
    """Test unsubscribing from a topic.

    ACCEPTANCE: unsubscribe() should remove topic callback and unsubscribe from broker.
    """

    async def test_callback(topic: str, payload: dict):
        pass

    with patch(
        "backend.services.mqtt_client.aiomqtt.Client",
        return_value=mock_aiomqtt_client,
        autospec=True,
    ):
        await mqtt_client.connect()

        topic = "commands/test"
        await mqtt_client.subscribe(topic, test_callback)
        assert topic in mqtt_client._subscriptions

        await mqtt_client.unsubscribe(topic)

        assert topic not in mqtt_client._subscriptions
        mock_aiomqtt_client.unsubscribe.assert_called_once()


@pytest.mark.asyncio
async def test_message_callback_invoked(mqtt_client, mock_aiomqtt_client):
    """Test that message callbacks are invoked when messages arrive.

    ACCEPTANCE: Incoming messages should trigger registered callbacks with topic and payload.
    """
    received_messages = []

    async def test_callback(topic: str, payload: dict):
        received_messages.append({"topic": topic, "payload": payload})

    # Mock incoming message
    mock_message = MagicMock()
    mock_message.topic.value = f"{MQTT_TOPIC_PREFIX}/commands/zone/1/arm"
    mock_message.payload = b'{"action": "arm", "zone_id": 1}'

    # Mock async iterator for messages
    async def mock_messages():
        yield mock_message

    mock_aiomqtt_client.messages = mock_messages()

    with patch(
        "backend.services.mqtt_client.aiomqtt.Client",
        return_value=mock_aiomqtt_client,
        autospec=True,
    ):
        await mqtt_client.connect()
        await mqtt_client.subscribe("commands/zone/1/arm", test_callback)

        # Start message processing (should be done in background task)
        await mqtt_client._process_messages()

        # Verify callback was invoked
        assert len(received_messages) == 1
        assert received_messages[0]["topic"] == "commands/zone/1/arm"
        assert received_messages[0]["payload"]["action"] == "arm"


# Health check tests


@pytest.mark.asyncio
async def test_health_check_connected(mqtt_client, mock_aiomqtt_client):
    """Test health check returns True when connected.

    ACCEPTANCE: health_check() should return True for active connections.
    """
    with patch(
        "backend.services.mqtt_client.aiomqtt.Client",
        return_value=mock_aiomqtt_client,
        autospec=True,
    ):
        await mqtt_client.connect()

        result = await mqtt_client.health_check()

        assert result is True


@pytest.mark.asyncio
async def test_health_check_disconnected(mqtt_client):
    """Test health check returns False when disconnected.

    ACCEPTANCE: health_check() should return False when not connected.
    """
    assert mqtt_client.connected is False

    result = await mqtt_client.health_check()

    assert result is False


@pytest.mark.asyncio
async def test_health_check_with_ping(mqtt_client, mock_aiomqtt_client):
    """Test health check performs broker ping to verify connectivity.

    ACCEPTANCE: health_check() should optionally ping broker to verify connection is alive.
    """
    with patch(
        "backend.services.mqtt_client.aiomqtt.Client",
        return_value=mock_aiomqtt_client,
        autospec=True,
    ):
        await mqtt_client.connect()

        # Mock ping/pong
        mock_aiomqtt_client.ping = AsyncMock()

        result = await mqtt_client.health_check(ping=True)

        assert result is True
        mock_aiomqtt_client.ping.assert_called_once()


# Metrics tests


@pytest.mark.asyncio
async def test_connection_metrics_recorded(
    mqtt_client, mock_aiomqtt_client, mock_prometheus_metrics
):
    """Test connection events are recorded in Prometheus metrics.

    ACCEPTANCE: Connection success/failure should increment hsi_mqtt_connections_total counter.
    """
    with patch(
        "backend.services.mqtt_client.aiomqtt.Client",
        return_value=mock_aiomqtt_client,
        autospec=True,
    ):
        await mqtt_client.connect()

        # Verify metrics were recorded
        counter_instance = mock_prometheus_metrics["counter_instance"]
        counter_instance.labels.assert_called()
        counter_instance.labels.return_value.inc.assert_called()


@pytest.mark.asyncio
async def test_publish_metrics_recorded(mqtt_client, mock_aiomqtt_client, mock_prometheus_metrics):
    """Test publish operations record duration histogram.

    ACCEPTANCE: publish() should record hsi_mqtt_publish_duration_seconds histogram.
    """
    with patch(
        "backend.services.mqtt_client.aiomqtt.Client",
        return_value=mock_aiomqtt_client,
        autospec=True,
    ):
        await mqtt_client.connect()
        await mqtt_client.publish("test/topic", {"data": "test"})

        # Verify histogram was recorded
        histogram_instance = mock_prometheus_metrics["histogram_instance"]
        histogram_instance.labels.assert_called()
        histogram_instance.labels.return_value.observe.assert_called()


@pytest.mark.asyncio
async def test_error_metrics_recorded(mqtt_client, mqtt_settings):
    """Test errors are recorded in Prometheus error counter.

    ACCEPTANCE: Connection/publish errors should increment hsi_mqtt_errors_total counter.
    """
    with (
        patch("backend.services.mqtt_client.aiomqtt.Client", autospec=True) as mock_client_class,
        patch("backend.services.mqtt_client.Counter", autospec=True) as mock_counter,
    ):
        mock_counter_instance = MagicMock()
        mock_counter_instance.labels.return_value.inc = MagicMock()
        mock_counter.return_value = mock_counter_instance

        mock_client_class.return_value.__aenter__.side_effect = ConnectionError("Connection failed")
        mqtt_client.settings.max_retries = 1

        with pytest.raises(MQTTConnectionError):
            await mqtt_client.connect()

        # Verify error counter was incremented
        mock_counter_instance.labels.assert_called()
        mock_counter_instance.labels.return_value.inc.assert_called()


# Integration patterns


@pytest.mark.asyncio
async def test_event_broadcaster_integration_pattern(mqtt_client, mock_aiomqtt_client):
    """Test MQTT client can be integrated with event broadcaster.

    ACCEPTANCE: Client should support publishing events from event_broadcaster.py.
    """
    with patch(
        "backend.services.mqtt_client.aiomqtt.Client",
        return_value=mock_aiomqtt_client,
        autospec=True,
    ):
        await mqtt_client.connect()

        # Simulate event broadcaster pattern
        event_type = "detection.new"
        event_data = {
            "event_id": "evt_123",
            "camera_id": "front_door",
            "detection_count": 2,
            "timestamp": "2026-02-01T00:00:00Z",
        }

        # Publish to event topic
        await mqtt_client.publish(f"events/{event_type}", event_data)

        # Verify publish called with correct topic structure
        call_args = mock_aiomqtt_client.publish.call_args
        assert "events/detection.new" in call_args[0][0]


@pytest.mark.asyncio
async def test_multiple_topics_publish(mqtt_client, mock_aiomqtt_client):
    """Test publishing to multiple topic types.

    ACCEPTANCE: Client should handle various topic structures from design doc.
    """
    with patch(
        "backend.services.mqtt_client.aiomqtt.Client",
        return_value=mock_aiomqtt_client,
        autospec=True,
    ):
        await mqtt_client.connect()

        # Test various topic patterns from design doc
        topics = [
            ("events/camera/front_door", {"type": "motion"}),
            ("alerts/critical", {"alert_id": "alert_123"}),
            ("detections/camera/front_door/person", {"count": 1}),
            ("zones/zone_1/crossing", {"entity_id": "entity_456"}),
            ("health/cameras/front_door", {"status": "online"}),
            ("health/system", {"status": "healthy"}),
        ]

        for topic, payload in topics:
            await mqtt_client.publish(topic, payload)

        # Verify all publishes succeeded
        assert mock_aiomqtt_client.publish.call_count == len(topics)


@pytest.mark.asyncio
async def test_command_subscription_pattern(mqtt_client, mock_aiomqtt_client):
    """Test subscribing to command topics.

    ACCEPTANCE: Client should support command subscription pattern from design doc.
    """
    command_received = []

    async def handle_zone_command(topic: str, payload: dict):
        command_received.append({"topic": topic, "payload": payload})

    with patch(
        "backend.services.mqtt_client.aiomqtt.Client",
        return_value=mock_aiomqtt_client,
        autospec=True,
    ):
        await mqtt_client.connect()

        # Subscribe to command topics
        await mqtt_client.subscribe("commands/zones/+/arm", handle_zone_command)
        await mqtt_client.subscribe("commands/zones/+/disarm", handle_zone_command)
        await mqtt_client.subscribe("commands/alerts/acknowledge/+", handle_zone_command)

        # Verify subscriptions registered
        assert len(mqtt_client._subscriptions) == 3


@pytest.mark.asyncio
async def test_graceful_shutdown_with_active_subscriptions(mqtt_client, mock_aiomqtt_client):
    """Test graceful shutdown cleans up subscriptions.

    ACCEPTANCE: disconnect() should unsubscribe from all topics before disconnecting.
    """

    async def test_callback(topic: str, payload: dict):
        pass

    with patch(
        "backend.services.mqtt_client.aiomqtt.Client",
        return_value=mock_aiomqtt_client,
        autospec=True,
    ):
        await mqtt_client.connect()

        # Add multiple subscriptions
        await mqtt_client.subscribe("topic1", test_callback)
        await mqtt_client.subscribe("topic2", test_callback)
        await mqtt_client.subscribe("topic3", test_callback)

        assert len(mqtt_client._subscriptions) == 3

        # Disconnect should clean up
        await mqtt_client.disconnect()

        assert len(mqtt_client._subscriptions) == 0
        assert mqtt_client.connected is False


# =============================================================================
# WP4.4 kill battery (frozen triage feed archive/wp25-feed/wp44-triage,
# mqtt_client.md clusters T1-T8/T10-T12 — 70 TEST-GAP survivors of 232;
# 141 LOW-VALUE log/metric-name mutants and 21 EQUIVALENT stay
# per-cluster justified in the dossier). Root cause: tests asserted that
# labels()/inc()/observe() HAPPENED, never with which values; the
# aiomqtt.Client(...) construction was never inspected; unsubscribe
# asserts were arity-only. Production asserted exactly as shipped.
# =============================================================================


class TestConnectionContract:
    """T3/T4/T5/T9: the aiomqtt ctor contract, TLS gating, error cause, idempotency."""

    @pytest.mark.asyncio
    async def test_connect_passes_all_settings_to_aiomqtt_client(
        self, mqtt_client, mock_aiomqtt_client, mqtt_settings
    ):
        """Every aiomqtt.Client kwarg must come from settings (T3: 14 keys)."""
        with patch(
            "backend.services.mqtt_client.aiomqtt.Client",
            return_value=mock_aiomqtt_client,
            autospec=True,
        ) as mock_cls:
            await mqtt_client.connect()

        kwargs = mock_cls.call_args.kwargs
        assert kwargs["hostname"] == MQTT_BROKER_HOST
        assert kwargs["port"] == MQTT_BROKER_PORT
        assert kwargs["identifier"] == MQTT_CLIENT_ID
        assert kwargs["username"] == MQTT_USERNAME
        assert kwargs["password"] == MQTT_PASSWORD
        assert kwargs["keepalive"] == 60
        assert kwargs["tls_context"] is None  # use_tls False in fixture

    @pytest.mark.asyncio
    async def test_connect_builds_tls_context_when_use_tls_true(self, mock_aiomqtt_client):
        """use_tls=True passes a real SSLContext; use_tls=False passes None (T4: 3 keys)."""
        # use_tls passed explicitly: SettingsConfigDict(env_file=".env") could
        # otherwise pick MQTT_USE_TLS up from a developer .env.
        client = MQTTClient(settings=MQTTClientSettings(broker_host=MQTT_BROKER_HOST, use_tls=True))
        with patch(
            "backend.services.mqtt_client.aiomqtt.Client",
            return_value=mock_aiomqtt_client,
            autospec=True,
        ) as mock_cls:
            await client.connect()
            tls_ctx = mock_cls.call_args.kwargs["tls_context"]
            assert isinstance(tls_ctx, ssl.SSLContext)  # kills tls_context=None mutants

        plain = MQTTClient(settings=MQTTClientSettings(broker_host=MQTT_BROKER_HOST, use_tls=False))
        with patch(
            "backend.services.mqtt_client.aiomqtt.Client",
            return_value=mock_aiomqtt_client,
            autospec=True,
        ) as mock_cls2:
            await plain.connect()
            assert mock_cls2.call_args.kwargs["tls_context"] is None

    @pytest.mark.asyncio
    async def test_connect_exhaustion_chains_original_error(self, mqtt_client):
        """MQTTConnectionError.original_error carries the LAST broker exception (T5)."""
        boom = ConnectionError("refused-xyz")
        with (
            patch("backend.services.mqtt_client.aiomqtt.Client", autospec=True) as cls,
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            cls.return_value.__aenter__.side_effect = boom
            mqtt_client.settings.max_retries = 1

            with pytest.raises(MQTTConnectionError) as exc_info:
                await mqtt_client.connect()

            assert exc_info.value.original_error is boom

    @pytest.mark.asyncio
    async def test_second_connect_does_not_recreate_the_client(
        self, mqtt_client, mock_aiomqtt_client
    ):
        """Idempotency guard must skip the ctor AND __aenter__ on reconnect (T9)."""
        with patch(
            "backend.services.mqtt_client.aiomqtt.Client",
            return_value=mock_aiomqtt_client,
            autospec=True,
        ) as mock_cls:
            await mqtt_client.connect()
            await mqtt_client.connect()

            mock_cls.assert_called_once()
            assert mock_aiomqtt_client.__aenter__.await_count == 1


class TestMetricsContracts:
    """T1/T2/T11: metric label VALUES and histogram config, not just call presence."""

    @pytest.mark.asyncio
    async def test_metrics_record_exact_label_values_and_gauges(
        self, mqtt_client, mock_aiomqtt_client, mock_prometheus_metrics
    ):
        """connections_total{status}, connection_state 1/0, publish labels + sane seconds (T1)."""
        counter = mock_prometheus_metrics["counter_instance"]
        gauge = mock_prometheus_metrics["gauge_instance"]
        histogram = mock_prometheus_metrics["histogram_instance"]

        with patch(
            "backend.services.mqtt_client.aiomqtt.Client",
            return_value=mock_aiomqtt_client,
            autospec=True,
        ):
            await mqtt_client.connect()
            assert call(status="success") in counter.labels.call_args_list
            gauge.set.assert_called_with(1)

            await mqtt_client.publish("events/cam1", {"a": 1})
            assert call(topic_type="events", qos="1") in counter.labels.call_args_list
            assert call(topic_type="events") in histogram.labels.call_args_list
            observed = [c.args[0] for c in histogram.labels.return_value.observe.call_args_list]
            assert observed and all(0 <= d < 60 for d in observed)  # kills +duration mutants

            await mqtt_client.disconnect()
            # subscriptions_active.set(0) then connection_state.set(0)
            assert gauge.set.call_args_list[-2:] == [call(0), call(0)]

        # exhausted connect: exact failure labels
        with (
            patch("backend.services.mqtt_client.aiomqtt.Client", autospec=True) as cls,
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            cls.return_value.__aenter__.side_effect = ConnectionError("boom")
            client2 = MQTTClient(settings=mqtt_client.settings)
            client2.settings.max_retries = 1
            with pytest.raises(MQTTConnectionError):
                await client2.connect()

            assert call(status="failure") in counter.labels.call_args_list
            assert call(error_type="connection") in counter.labels.call_args_list

    @pytest.mark.asyncio
    async def test_publish_metrics_use_first_path_segment_as_topic_type(
        self, mqtt_client, mock_aiomqtt_client, mock_prometheus_metrics
    ):
        """topic_type = FIRST '/'-segment (maxsplit=1) — rsplit/[1]/condition flips die (T2)."""
        counter = mock_prometheus_metrics["counter_instance"]
        with patch(
            "backend.services.mqtt_client.aiomqtt.Client",
            return_value=mock_aiomqtt_client,
            autospec=True,
        ):
            await mqtt_client.connect()

            await mqtt_client.publish("events/camera/front_door", {"a": 1})
            assert call(topic_type="events", qos="1") in counter.labels.call_args_list

            counter.labels.reset_mock()
            await mqtt_client.publish("health", {"a": 1})
            assert call(topic_type="health", qos="1") in counter.labels.call_args_list

    @pytest.mark.asyncio
    async def test_publish_duration_histogram_carries_declared_buckets(
        self, mqtt_client, mock_prometheus_metrics
    ):
        """The Histogram is built with the module's buckets tuple (T11)."""
        histogram = mock_prometheus_metrics["histogram"]
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        with patch(
            "backend.services.mqtt_client.aiomqtt.Client",
            return_value=mock_client,
            autospec=True,
        ):
            await mqtt_client.connect()
        await mqtt_client.publish("events/c1", {"a": 1})
        assert histogram.call_args.kwargs["buckets"] == MQTT_PUBLISH_DURATION_BUCKETS


class TestPublishRetryContract:
    """T6/T7: exactly 3 attempts and the doubling publish-path backoff schedule."""

    @pytest.mark.asyncio
    async def test_publish_exhausts_exactly_three_attempts_with_doubling_backoff(
        self, mqtt_client, mock_aiomqtt_client
    ):
        with (
            patch(
                "backend.services.mqtt_client.aiomqtt.Client",
                return_value=mock_aiomqtt_client,
                autospec=True,
            ),
            patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
        ):
            boom = ConnectionError("down")
            mock_aiomqtt_client.publish.side_effect = boom
            await mqtt_client.connect()

            with pytest.raises(MQTTPublishError) as exc_info:
                await mqtt_client.publish("t/x", {"a": 1})

            assert mock_aiomqtt_client.publish.call_count == 3  # kills 3->4 and guard flips
            assert [c.args[0] for c in mock_sleep.call_args_list] == [1, 2]
            # raised error keeps its cause (kills last_exception=None)
            assert exc_info.value.original_error is boom


class TestSubscriptionContract:
    """T8/T10/T12: broker receives PREFIXED topics on subscribe/unsubscribe fan-out."""

    @pytest.mark.asyncio
    async def test_subscribe_passes_prefixed_topic_and_qos(self, mqtt_client, mock_aiomqtt_client):
        """Broker sees prefix/topic with the settings' default QoS (T12)."""

        async def cb(topic: str, payload: dict) -> None:
            pass

        with patch(
            "backend.services.mqtt_client.aiomqtt.Client",
            return_value=mock_aiomqtt_client,
            autospec=True,
        ):
            await mqtt_client.connect()
            await mqtt_client.subscribe("commands/test", cb)

            mock_aiomqtt_client.subscribe.assert_called_once_with(
                f"{MQTT_TOPIC_PREFIX}/commands/test", qos=1
            )

    @pytest.mark.asyncio
    async def test_unsubscribe_paths_pass_prefixed_topic_to_broker(
        self, mqtt_client, mock_aiomqtt_client
    ):
        """Direct unsubscribe AND the disconnect fan-out must hit the broker with the FULL topic (T8/T10)."""

        async def cb(topic: str, payload: dict) -> None:
            pass

        with patch(
            "backend.services.mqtt_client.aiomqtt.Client",
            return_value=mock_aiomqtt_client,
            autospec=True,
        ):
            await mqtt_client.connect()
            await mqtt_client.subscribe("commands/test", cb)

            mock_aiomqtt_client.unsubscribe.reset_mock()
            await mqtt_client.unsubscribe("commands/test")
            mock_aiomqtt_client.unsubscribe.assert_called_once_with(
                f"{MQTT_TOPIC_PREFIX}/commands/test"
            )

            await mqtt_client.subscribe("status/a", cb)
            await mqtt_client.subscribe("status/b", cb)
            mock_aiomqtt_client.unsubscribe.reset_mock()
            await mqtt_client.disconnect()
            called = [c.args[0] for c in mock_aiomqtt_client.unsubscribe.call_args_list]
            assert f"{MQTT_TOPIC_PREFIX}/status/a" in called
            assert f"{MQTT_TOPIC_PREFIX}/status/b" in called  # kills skip-the-loop mutant
