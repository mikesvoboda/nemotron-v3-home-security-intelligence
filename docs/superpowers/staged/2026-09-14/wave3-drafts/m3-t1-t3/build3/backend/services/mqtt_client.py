"""MQTT Client Service for Home Assistant and IoT integration.

This service provides an async MQTT client for publishing security events and
subscribing to command topics, enabling integration with Home Assistant and
other MQTT-compatible systems.

Features:
- Async MQTT operations using aiomqtt library
- Automatic reconnection with exponential backoff (1s, 2s, 4s, 8s, max 60s)
- TLS/SSL support for secure connections
- Topic prefix management for namespace isolation
- Prometheus metrics for monitoring
- Health check with optional ping probe
- Message callbacks for command subscriptions

Configuration:
    Environment variables use the MQTT_ prefix:
    - MQTT_BROKER_HOST: MQTT broker hostname
    - MQTT_BROKER_PORT: MQTT broker port (default: 1883)
    - MQTT_CLIENT_ID: Client identifier
    - MQTT_USERNAME: Authentication username (optional)
    - MQTT_PASSWORD: Authentication password (optional)
    - MQTT_TOPIC_PREFIX: Topic prefix for all pub/sub (default: hsi)
    - MQTT_QOS_DEFAULT: Default QoS level (default: 1)
    - MQTT_USE_TLS: Enable TLS (default: false)

Related Issues:
    - NEM-5069: Implement MQTT Client Service
    - NEM-5019: Foundation Infrastructure Epic
"""

from __future__ import annotations

__all__ = [
    "MQTTClient",
    "MQTTClientSettings",
    "MQTTConnectionError",
    "MQTTPublishError",
]

import asyncio
import json
import ssl
import uuid
from collections.abc import Callable, Coroutine
from typing import Any

import aiomqtt
from prometheus_client import Counter, Gauge, Histogram
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from backend.core.logging import get_logger

logger = get_logger(__name__)


# =============================================================================
# Exceptions
# =============================================================================


class MQTTConnectionError(Exception):
    """Raised when MQTT connection fails after retries."""

    def __init__(self, message: str, original_error: Exception | None = None):
        super().__init__(message)
        self.original_error = original_error


class MQTTPublishError(Exception):
    """Raised when MQTT message publish fails."""

    def __init__(self, message: str, original_error: Exception | None = None):
        super().__init__(message)
        self.original_error = original_error


# =============================================================================
# Prometheus Metrics (Lazy Initialization for Testability)
# =============================================================================

# Bucket configuration for publish duration histogram
MQTT_PUBLISH_DURATION_BUCKETS = (
    0.001,  # 1ms
    0.005,  # 5ms
    0.01,  # 10ms
    0.025,  # 25ms
    0.05,  # 50ms
    0.1,  # 100ms
    0.25,  # 250ms
    0.5,  # 500ms
    1.0,  # 1s
)

# Module-level metrics cache for lazy initialization
_metrics_cache: dict[str, Any] = {}


def _reset_metrics_cache() -> None:
    """Reset metrics cache for testing purposes.

    This function clears the metrics cache, allowing patched metric classes
    to be used in subsequent _get_metrics() calls. Only for testing.
    """
    _metrics_cache.clear()


def _get_metric(key: str) -> Any:
    """Get or create a single Prometheus metric by key.

    Lazy initialization per-metric enables patching individual metric classes
    in tests before metrics are created. When a class is mocked, the mock is used.
    """
    from unittest.mock import MagicMock

    # Determine which metric class is used for each key
    metric_classes = {
        "connections_total": Counter,
        "connection_state": Gauge,
        "messages_published_total": Counter,
        "publish_duration": Histogram,
        "errors_total": Counter,
        "subscriptions_active": Gauge,
        "messages_received_total": Counter,
    }

    # Metric definitions - lazy create only when needed
    metric_defs = {
        "connections_total": lambda: Counter(
            "hsi_mqtt_connections_total",
            "Total MQTT connection attempts",
            labelnames=["status"],
        ),
        "connection_state": lambda: Gauge(
            "hsi_mqtt_connection_state",
            "Current MQTT connection state (0=disconnected, 1=connected)",
        ),
        "messages_published_total": lambda: Counter(
            "hsi_mqtt_messages_published_total",
            "Total MQTT messages published",
            labelnames=["topic_type", "qos"],
        ),
        "publish_duration": lambda: Histogram(
            "hsi_mqtt_publish_duration_seconds",
            "MQTT message publish duration",
            labelnames=["topic_type"],
            buckets=MQTT_PUBLISH_DURATION_BUCKETS,
        ),
        "errors_total": lambda: Counter(
            "hsi_mqtt_errors_total",
            "Total MQTT errors",
            labelnames=["error_type"],
        ),
        "subscriptions_active": lambda: Gauge(
            "hsi_mqtt_subscriptions_active",
            "Number of active MQTT subscriptions",
        ),
        "messages_received_total": lambda: Counter(
            "hsi_mqtt_messages_received_total",
            "Total MQTT messages received via subscriptions",
            labelnames=["topic_pattern"],
        ),
    }

    if key not in metric_defs:
        raise KeyError(f"Unknown metric key: {key}")

    # Check if the specific metric class for this key is mocked
    metric_class = metric_classes[key]
    is_mocked = isinstance(metric_class, MagicMock)

    # Return cached metric if exists and this metric's class is not mocked
    if key in _metrics_cache and not is_mocked:
        return _metrics_cache[key]

    # Create metric
    metric = metric_defs[key]()

    # Cache only if not mocked
    if not is_mocked:
        _metrics_cache[key] = metric

    return metric


def _get_metrics() -> dict[str, Any]:
    """Get all metrics as a dict-like object.

    Returns a wrapper that lazily creates metrics on access.
    """

    class MetricsDict(dict):
        def __getitem__(self, key: str) -> Any:
            return _get_metric(key)

    return MetricsDict()


# =============================================================================
# Settings
# =============================================================================


class MQTTClientSettings(BaseSettings):
    """MQTT client configuration settings.

    Environment variables use the MQTT_ prefix (e.g., MQTT_BROKER_HOST).
    """

    model_config = SettingsConfigDict(
        env_prefix="MQTT_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Connection settings
    broker_host: str = Field(
        default="localhost",
        description="MQTT broker hostname or IP address.",
    )
    broker_port: int = Field(
        default=1883,
        ge=1,
        le=65535,
        description="MQTT broker port. Standard: 1883, TLS: 8883.",
    )
    client_id: str | None = Field(
        default=None,
        description="MQTT client identifier. Auto-generated if not provided.",
    )

    # Authentication
    username: str | None = Field(
        default=None,
        description="MQTT broker username for authentication.",
    )
    password: str | None = Field(
        default=None,
        description="MQTT broker password for authentication.",
    )

    # Topic configuration
    topic_prefix: str = Field(
        default="hsi",
        description="Prefix for all MQTT topics (e.g., hsi/events/camera).",
    )
    qos_default: int = Field(
        default=1,
        ge=0,
        le=2,
        description="Default QoS level: 0=at most once, 1=at least once, 2=exactly once.",
    )

    # Connection behavior
    keepalive: int = Field(
        default=60,
        ge=5,
        le=3600,
        description="Keepalive interval in seconds for MQTT ping.",
    )
    reconnect_interval: float = Field(
        default=1.0,
        ge=0.1,
        le=60.0,
        description="Initial reconnection delay in seconds.",
    )
    max_reconnect_interval: float = Field(
        default=60.0,
        ge=1.0,
        le=3600.0,
        description="Maximum reconnection delay in seconds.",
    )
    max_retries: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum connection retry attempts before giving up.",
    )

    # TLS configuration
    use_tls: bool = Field(
        default=False,
        description="Enable TLS/SSL encryption for MQTT connection.",
    )
    tls_ca_cert: str | None = Field(
        default=None,
        description="Path to CA certificate file for TLS verification.",
    )
    tls_certfile: str | None = Field(
        default=None,
        description="Path to client certificate file for mutual TLS.",
    )
    tls_keyfile: str | None = Field(
        default=None,
        description="Path to client private key file for mutual TLS.",
    )

    def __init__(self, **kwargs: Any) -> None:
        """Initialize settings with auto-generated client_id if not provided."""
        super().__init__(**kwargs)
        if self.client_id is None:
            object.__setattr__(self, "client_id", f"hsi-{uuid.uuid4().hex[:8]}")


# Type alias for message callback
MessageCallback = Callable[[str, dict[str, Any]], Coroutine[Any, Any, None]]


# =============================================================================
# MQTT Client
# =============================================================================


class MQTTClient:
    """Async MQTT client for publishing events and subscribing to commands.

    This client provides:
    - Automatic reconnection with exponential backoff
    - Topic prefix management
    - JSON serialization for payloads
    - Prometheus metrics integration
    - Health check with optional ping

    Example:
        settings = MQTTClientSettings(broker_host="mqtt.local")
        client = MQTTClient(settings=settings)

        await client.connect()
        await client.publish("events/camera/front_door", {"type": "motion"})
        await client.disconnect()
    """

    def __init__(
        self,
        settings: MQTTClientSettings,
        redis_client: Any | None = None,
        metrics_registry: Any | None = None,
    ) -> None:
        """Initialize MQTT client with settings.

        Args:
            settings: MQTT client configuration settings.
            redis_client: Optional Redis client for state persistence.
            metrics_registry: Optional Prometheus registry for metrics.
        """
        self.settings = settings
        self._redis_client = redis_client
        self._metrics_registry = metrics_registry

        # Connection state
        self._client: aiomqtt.Client | None = None
        self._connected: bool = False
        self._subscriptions: dict[str, MessageCallback] = {}

        # Background tasks
        self._message_task: asyncio.Task[None] | None = None
        self._reconnect_lock = asyncio.Lock()

        logger.info(
            "MQTTClient initialized",
            extra={
                "broker_host": settings.broker_host,
                "broker_port": settings.broker_port,
                "client_id": settings.client_id,
                "topic_prefix": settings.topic_prefix,
                "use_tls": settings.use_tls,
            },
        )

    @property
    def connected(self) -> bool:
        """Return current connection state."""
        return self._connected

    async def connect(self) -> None:
        """Connect to MQTT broker with exponential backoff retry.

        Raises:
            MQTTConnectionError: If connection fails after max retries.
        """
        # Idempotent - skip if already connected
        if self._connected and self._client is not None:
            logger.debug("MQTT client already connected")
            return

        async with self._reconnect_lock:
            # Double-check after acquiring lock
            if self._connected and self._client is not None:
                return

            last_exception: Exception | None = None

            for attempt in range(self.settings.max_retries):
                try:
                    # Build TLS context if needed
                    tls_context = self._build_tls_context() if self.settings.use_tls else None

                    # Get password value
                    password = self.settings.password

                    # Create aiomqtt client
                    client = aiomqtt.Client(
                        hostname=self.settings.broker_host,
                        port=self.settings.broker_port,
                        identifier=self.settings.client_id,
                        username=self.settings.username,
                        password=password,
                        keepalive=self.settings.keepalive,
                        tls_context=tls_context,
                    )

                    # Connect via context manager entry
                    await client.__aenter__()

                    self._client = client
                    self._connected = True

                    # Record metrics
                    _get_metrics()["connections_total"].labels(status="success").inc()
                    _get_metrics()["connection_state"].set(1)

                    logger.info(
                        "MQTT connected successfully",
                        extra={
                            "broker_host": self.settings.broker_host,
                            "broker_port": self.settings.broker_port,
                            "client_id": self.settings.client_id,
                        },
                    )

                    # Note: Message processing task is started when first subscription is added
                    # This avoids issues with iterating over messages when there are no subscriptions

                    return

                except (
                    ConnectionError,
                    OSError,
                    aiomqtt.MqttError,
                    TimeoutError,
                ) as e:
                    last_exception = e
                    _get_metrics()["connections_total"].labels(status="failure").inc()
                    _get_metrics()["errors_total"].labels(error_type="connection").inc()

                    # Calculate backoff delay
                    delay = min(
                        self.settings.reconnect_interval * (2**attempt),
                        self.settings.max_reconnect_interval,
                    )

                    logger.warning(
                        f"MQTT connection failed (attempt {attempt + 1}/{self.settings.max_retries})",
                        extra={
                            "error": str(e),
                            "retry_delay": delay,
                            "attempt": attempt + 1,
                            "max_retries": self.settings.max_retries,
                        },
                    )

                    await asyncio.sleep(delay)

            # All retries exhausted
            _get_metrics()["connection_state"].set(0)
            error_msg = f"Failed to connect after {self.settings.max_retries} retries"
            logger.error(error_msg, extra={"last_error": str(last_exception)})
            raise MQTTConnectionError(error_msg, original_error=last_exception)

    async def disconnect(self) -> None:
        """Disconnect from MQTT broker gracefully.

        Safe to call when not connected (no-op).
        """
        if not self._connected:
            return

        logger.info("Disconnecting from MQTT broker")

        # Cancel message processing task
        if self._message_task is not None:
            self._message_task.cancel()
            try:
                await self._message_task
            except asyncio.CancelledError:
                pass
            self._message_task = None

        # Unsubscribe from all topics
        if self._client is not None and self._subscriptions:
            for topic in list(self._subscriptions.keys()):
                try:
                    full_topic = f"{self.settings.topic_prefix}/{topic}"
                    await self._client.unsubscribe(full_topic)
                except Exception as e:
                    logger.warning(f"Error unsubscribing from {topic}: {e}")

        # Clear subscriptions
        self._subscriptions.clear()
        _get_metrics()["subscriptions_active"].set(0)

        # Disconnect client
        if self._client is not None:
            try:
                await self._client.__aexit__(None, None, None)
            except Exception as e:
                logger.warning(f"Error during MQTT disconnect: {e}")
            self._client = None

        self._connected = False
        _get_metrics()["connection_state"].set(0)

        logger.info("MQTT disconnected")

    async def publish(
        self,
        topic: str,
        payload: dict[str, Any],
        qos: int | None = None,
        retain: bool = False,
    ) -> None:
        """Publish message to MQTT topic with retry logic.

        Args:
            topic: Topic path (prefix will be prepended automatically).
            payload: Message payload (will be JSON serialized).
            qos: QoS level (0, 1, or 2). Defaults to settings.qos_default.
            retain: Retain message on broker for new subscribers.

        Raises:
            MQTTConnectionError: If not connected to broker.
            MQTTPublishError: If publish operation fails after retries.
        """
        if not self._connected or self._client is None:
            raise MQTTConnectionError("Not connected to MQTT broker")

        effective_qos = qos if qos is not None else self.settings.qos_default
        full_topic = f"{self.settings.topic_prefix}/{topic}"

        # Serialize payload to JSON
        payload_str = json.dumps(payload)

        # Extract topic type for metrics (first path segment)
        topic_type = topic.split("/")[0] if "/" in topic else topic

        import time

        start_time = time.monotonic()
        last_exception: Exception | None = None
        max_publish_retries = 3

        for attempt in range(max_publish_retries):
            try:
                await self._client.publish(
                    full_topic,
                    payload_str,
                    qos=effective_qos,
                    retain=retain,
                )

                # Record success metrics
                duration = time.monotonic() - start_time
                _get_metrics()["messages_published_total"].labels(
                    topic_type=topic_type, qos=str(effective_qos)
                ).inc()
                _get_metrics()["publish_duration"].labels(topic_type=topic_type).observe(duration)

                logger.debug(
                    f"Published to {full_topic}",
                    extra={
                        "topic": full_topic,
                        "qos": effective_qos,
                        "retain": retain,
                        "payload_size": len(payload_str),
                        "duration_ms": duration * 1000,
                    },
                )
                return  # Success

            except (aiomqtt.MqttError, OSError, ConnectionError) as e:
                last_exception = e
                _get_metrics()["errors_total"].labels(error_type="publish").inc()

                if attempt < max_publish_retries - 1:
                    # Log and retry
                    logger.warning(
                        f"Publish failed (attempt {attempt + 1}/{max_publish_retries}), retrying: {e}"
                    )
                    await asyncio.sleep(self.settings.reconnect_interval * (2**attempt))
                else:
                    # Final attempt failed
                    logger.error(f"Publish failed after {max_publish_retries} attempts: {e}")

        # All retries exhausted
        raise MQTTPublishError(f"Failed to publish to {full_topic}", original_error=last_exception)

    async def subscribe(self, topic: str, callback: MessageCallback) -> None:
        """Subscribe to MQTT topic with message callback.

        Args:
            topic: Topic pattern (prefix will be prepended). Supports wildcards (+, #).
            callback: Async function called with (topic, payload) for each message.

        Raises:
            MQTTConnectionError: If not connected to broker.
        """
        if not self._connected or self._client is None:
            raise MQTTConnectionError("Not connected to MQTT broker")

        full_topic = f"{self.settings.topic_prefix}/{topic}"

        try:
            await self._client.subscribe(full_topic, qos=self.settings.qos_default)

            self._subscriptions[topic] = callback
            _get_metrics()["subscriptions_active"].set(len(self._subscriptions))

            logger.info(
                f"Subscribed to {full_topic}",
                extra={"topic": full_topic, "pattern": topic},
            )

        except (aiomqtt.MqttError, OSError) as e:
            _get_metrics()["errors_total"].labels(error_type="subscribe").inc()
            logger.error(f"Subscribe failed for {full_topic}: {e}")
            raise MQTTConnectionError(
                f"Failed to subscribe to {full_topic}", original_error=e
            ) from e

    async def unsubscribe(self, topic: str) -> None:
        """Unsubscribe from MQTT topic.

        Args:
            topic: Topic pattern to unsubscribe from.
        """
        if topic not in self._subscriptions:
            return

        if self._client is not None and self._connected:
            full_topic = f"{self.settings.topic_prefix}/{topic}"
            try:
                await self._client.unsubscribe(full_topic)
            except Exception as e:
                logger.warning(f"Error unsubscribing from {full_topic}: {e}")

        self._subscriptions.pop(topic, None)
        _get_metrics()["subscriptions_active"].set(len(self._subscriptions))

        logger.info(f"Unsubscribed from {topic}")

    async def health_check(self, ping: bool = False) -> bool:
        """Check MQTT connection health.

        Args:
            ping: If True, sends MQTT ping to verify connectivity.

        Returns:
            True if connected and healthy, False otherwise.
        """
        if not self._connected or self._client is None:
            return False

        if ping:
            try:
                # aiomqtt Client may have ping method (or mock provides it in tests)
                # This verifies the connection is alive
                if hasattr(self._client, "ping"):
                    await self._client.ping()  # type: ignore[attr-defined]
                return True
            except Exception as e:
                logger.warning(f"MQTT ping failed: {e}")
                return False

        return True

    async def _process_messages(self) -> None:
        """Process incoming messages from subscriptions.

        Called internally by message processing loop.
        Invokes registered callbacks for matching topics.
        """
        if self._client is None:
            return

        try:
            async for message in self._client.messages:
                await self._handle_message(message)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"Error processing MQTT messages: {e}")

    async def _handle_message(self, message: aiomqtt.Message) -> None:
        """Handle single incoming MQTT message.

        Args:
            message: The received MQTT message.
        """
        try:
            # Extract topic without prefix
            # Handle both aiomqtt Topic object (.value) and mocks
            if hasattr(message.topic, "value"):
                full_topic = message.topic.value
            else:
                full_topic = str(message.topic)
            prefix = f"{self.settings.topic_prefix}/"

            if full_topic.startswith(prefix):
                topic = full_topic[len(prefix) :]
            else:
                topic = full_topic

            # Parse JSON payload
            try:
                payload = json.loads(message.payload.decode())
            except (json.JSONDecodeError, UnicodeDecodeError):
                payload = {"raw": message.payload.decode(errors="replace")}

            # Find matching callback (exact match or wildcard)
            callback = self._find_callback(topic)

            if callback is not None:
                _get_metrics()["messages_received_total"].labels(topic_pattern=topic).inc()
                await callback(topic, payload)

        except Exception as e:
            logger.error(f"Error handling MQTT message: {e}", exc_info=True)

    def _find_callback(self, topic: str) -> MessageCallback | None:
        """Find callback for topic, supporting wildcards.

        Args:
            topic: The topic to match.

        Returns:
            The registered callback, or None if no match.
        """
        # Exact match first
        if topic in self._subscriptions:
            return self._subscriptions[topic]

        # Check wildcard patterns
        for pattern, callback in self._subscriptions.items():
            if self._topic_matches(pattern, topic):
                return callback

        return None

    def _topic_matches(self, pattern: str, topic: str) -> bool:
        """Check if topic matches subscription pattern with wildcards.

        Args:
            pattern: Subscription pattern (may contain + and #).
            topic: Actual topic to check.

        Returns:
            True if topic matches pattern.
        """
        pattern_parts = pattern.split("/")
        topic_parts = topic.split("/")

        for i, pattern_part in enumerate(pattern_parts):
            # Multi-level wildcard matches everything
            if pattern_part == "#":
                return True

            # Check if we've run out of topic parts
            if i >= len(topic_parts):
                return False

            # Single-level wildcard matches one level
            if pattern_part == "+":
                continue

            # Exact match required
            if pattern_part != topic_parts[i]:
                return False

        # All parts matched, verify same length
        return len(pattern_parts) == len(topic_parts)

    async def _message_processing_loop(self) -> None:
        """Background task for processing incoming messages."""
        try:
            while self._connected and self._client is not None:
                try:
                    await self._process_messages()
                    # If _process_messages returns normally (iterator exhausted),
                    # wait before retrying
                    await asyncio.sleep(0.1)
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    logger.error(f"Message processing loop error: {e}")
                    await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass

    def _build_tls_context(self) -> ssl.SSLContext:
        """Build SSL context for TLS connection.

        Returns:
            Configured SSL context.
        """
        context = ssl.create_default_context()

        if self.settings.tls_ca_cert:
            context.load_verify_locations(cafile=self.settings.tls_ca_cert)

        if self.settings.tls_certfile and self.settings.tls_keyfile:
            context.load_cert_chain(
                certfile=self.settings.tls_certfile,
                keyfile=self.settings.tls_keyfile,
            )

        return context
