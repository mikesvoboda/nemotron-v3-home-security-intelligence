"""Protocol definitions for service interfaces.

This module defines Protocol classes for structural subtyping, enabling type-safe
interface definitions without requiring explicit inheritance. Protocols allow
duck typing with full static type checking support.

Protocol Definitions:
    - AIServiceProtocol: For AI clients (detector, nemotron, enrichment)
    - QueueProcessorProtocol: For batch aggregator, evaluation queue
    - BroadcasterProtocol: For event/system broadcasters
    - ModelLoaderProtocol: For model loading and management
    - HealthCheckableProtocol: For services with health check capability
    - SubscribableProtocol: For services supporting pub/sub subscriptions

Usage:
    Services don't need to explicitly inherit from these protocols.
    They are structural subtypes if they implement the required methods.

    # Type hinting with protocols
    async def process_with_service(service: AIServiceProtocol) -> dict[str, Any]:
        if await service.health_check():
            return await service.process(input_data)

    # Works with any class that has matching methods
    detector = DetectorClient()  # Implements AIServiceProtocol structurally
    await process_with_service(detector)

See Also:
    - backend/services/detector_client.py - Implements AIServiceProtocol
    - backend/services/nemotron_analyzer.py - Implements AIServiceProtocol
    - backend/services/enrichment_client.py - Implements AIServiceProtocol
    - backend/services/evaluation_queue.py - Implements QueueProcessorProtocol
    - backend/services/event_broadcaster.py - Implements BroadcasterProtocol
    - backend/services/model_zoo.py - Implements ModelLoaderProtocol
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Protocol, TypeVar, runtime_checkable

# Type variable for generic input/output types
InputT = TypeVar("InputT")
OutputT = TypeVar("OutputT")


@runtime_checkable
class HealthCheckableProtocol(Protocol):
    """Protocol for services that support health checking.

    This is the most basic protocol for any service that needs to report
    its health status. Many services implement this to support liveness
    and readiness probes.

    Example Implementation:
        class MyService:
            async def health_check(self) -> bool:
                try:
                    # Check dependencies
                    return True
                except Exception:
                    return False
    """

    async def health_check(self) -> bool:
        """Check if the service is healthy and available.

        Returns:
            True if service is healthy and ready to accept requests,
            False otherwise.
        """
        ...


@runtime_checkable
class AIServiceProtocol(Protocol):
    """Protocol for AI service clients (detector, nemotron, enrichment).

    AI services are HTTP clients that communicate with external AI inference
    servers. They typically support health checking and provide metrics for
    monitoring.

    This protocol defines the common interface for:
        - DetectorClient: YOLO26 object detection
        - NemotronAnalyzer: LLM risk analysis
        - EnrichmentClient: Vehicle/pet/clothing classification

    Example Implementation:
        class MyAIClient:
            async def health_check(self) -> bool:
                async with httpx.AsyncClient() as client:
                    response = await client.get(f"{self.url}/health")
                    return response.status_code == 200

            async def process(self, input_data: Any) -> Any:
                # Send to AI service, parse response
                return result

            def get_metrics(self) -> dict[str, Any]:
                return {
                    "requests_total": self._requests,
                    "errors_total": self._errors,
                    "latency_avg_ms": self._latency_avg,
                }
    """

    async def health_check(self) -> bool:
        """Check if the AI service is healthy and available.

        Typically performs an HTTP health check against the AI server.

        Returns:
            True if AI service is responding, False otherwise.
        """
        ...

    async def process(self, input_data: Any) -> Any:
        """Process input data through the AI service.

        Args:
            input_data: Input to process (image path, text, etc.)

        Returns:
            Processed result from the AI service (detections, analysis, etc.)

        Raises:
            Exception: If processing fails due to service unavailability,
                timeout, or invalid input.
        """
        ...

    def get_metrics(self) -> dict[str, Any]:
        """Get service metrics for monitoring.

        Returns:
            Dictionary containing metrics such as:
                - requests_total: Total number of requests made
                - errors_total: Total number of errors
                - latency_avg_ms: Average latency in milliseconds
                - circuit_breaker_state: Current circuit breaker state
        """
        ...


@runtime_checkable
class QueueProcessorProtocol(Protocol):
    """Protocol for queue-based processors (batch aggregator, evaluation queue).

    Queue processors manage items in a queue for asynchronous processing.
    They support basic queue operations: enqueue, dequeue, and processing.

    This protocol defines the common interface for:
        - EvaluationQueue: Priority queue for AI audit evaluations
        - BatchAggregator: Time-based batching of detections

    Example Implementation:
        class MyQueue:
            async def enqueue(self, item: Any) -> bool:
                await self.redis.lpush(self.key, json.dumps(item))
                return True

            async def dequeue(self) -> Any | None:
                result = await self.redis.rpop(self.key)
                return json.loads(result) if result else None

            async def process_item(self, item: Any) -> None:
                # Process the dequeued item
                pass
    """

    async def enqueue(self, item: Any) -> bool:
        """Add an item to the queue for processing.

        Args:
            item: The item to enqueue (typically an ID or data payload)

        Returns:
            True if item was successfully enqueued, False otherwise.
        """
        ...

    async def dequeue(self) -> Any | None:
        """Remove and return the next item from the queue.

        Returns:
            The next item to process, or None if the queue is empty.
        """
        ...

    async def process_item(self, item: Any) -> None:
        """Process a single item from the queue.

        Args:
            item: The item to process

        Raises:
            Exception: If processing fails
        """
        ...


@runtime_checkable
class BroadcasterProtocol(Protocol):
    """Protocol for event/system broadcasters (WebSocket message distribution).

    Broadcasters manage WebSocket connections and distribute messages to
    connected clients. They typically use Redis pub/sub for multi-instance
    coordination.

    This protocol defines the common interface for:
        - EventBroadcaster: Security event distribution
        - SystemBroadcaster: System status updates

    Example Implementation:
        class MyBroadcaster:
            async def broadcast(self, channel: str, message: dict[str, Any]) -> int:
                # Publish to Redis and send to WebSocket clients
                sent_count = 0
                for ws in self.connections:
                    await ws.send_json(message)
                    sent_count += 1
                return sent_count

            async def subscribe(self, channel: str) -> AsyncIterator[dict[str, Any]]:
                pubsub = await self.redis.subscribe(channel)
                async for message in pubsub.listen():
                    if message["type"] == "message":
                        yield json.loads(message["data"])
    """

    async def broadcast(self, channel: str, message: dict[str, Any]) -> int:
        """Broadcast a message to all connected clients on a channel.

        Args:
            channel: The channel/topic to broadcast on
            message: The message payload to send

        Returns:
            Number of clients the message was sent to.
        """
        ...

    async def subscribe(self, channel: str) -> AsyncIterator[dict[str, Any]]:
        """Subscribe to messages on a channel.

        Args:
            channel: The channel/topic to subscribe to

        Yields:
            Messages received on the channel as dictionaries.
        """
        ...


@runtime_checkable
class ModelLoaderProtocol(Protocol):
    """Protocol for model loaders (CLIP, ViTPose, Florence, etc.).

    Model loaders manage the lifecycle of ML models, including loading
    into GPU memory, unloading, and running inference.

    This protocol defines the common interface for:
        - ModelManager: Central model management
        - Individual model loaders (clip_loader, vitpose_loader, etc.)

    Example Implementation:
        class MyModelLoader:
            async def load(self) -> None:
                self.model = await load_model_async(self.model_path)
                self._loaded = True

            async def unload(self) -> None:
                del self.model
                torch.cuda.empty_cache()
                self._loaded = False

            def is_loaded(self) -> bool:
                return self._loaded

            async def predict(self, input_data: Any) -> Any:
                if not self.is_loaded():
                    raise RuntimeError("Model not loaded")
                return self.model(input_data)
    """

    async def load(self) -> None:
        """Load the model into memory (CPU/GPU).

        This method should handle model initialization, weight loading,
        and moving the model to the appropriate device.

        Raises:
            RuntimeError: If model loading fails
            ImportError: If required dependencies are missing
        """
        ...

    async def unload(self) -> None:
        """Unload the model and free memory.

        This method should release model resources and clear GPU cache
        if applicable.
        """
        ...

    def is_loaded(self) -> bool:
        """Check if the model is currently loaded.

        Returns:
            True if the model is loaded and ready for inference,
            False otherwise.
        """
        ...

    async def predict(self, input_data: Any) -> Any:
        """Run inference on the input data.

        Args:
            input_data: Input for the model (image, text, etc.)

        Returns:
            Model output (predictions, embeddings, etc.)

        Raises:
            RuntimeError: If model is not loaded
            Exception: If inference fails
        """
        ...


@runtime_checkable
class SubscribableProtocol(Protocol):
    """Protocol for services supporting pub/sub subscriptions.

    Services implementing this protocol allow clients to subscribe to
    channels and receive real-time updates.

    Example Implementation:
        class MyPubSubService:
            async def subscribe(self, *channels: str) -> AsyncIterator[dict[str, Any]]:
                pubsub = await self.redis.subscribe(*channels)
                async for message in pubsub.listen():
                    yield message

            async def unsubscribe(self, *channels: str) -> None:
                await self.pubsub.unsubscribe(*channels)
    """

    async def subscribe(self, *channels: str) -> AsyncIterator[dict[str, Any]]:
        """Subscribe to one or more channels.

        Args:
            *channels: Channel names to subscribe to

        Yields:
            Messages received on the subscribed channels.
        """
        ...

    async def unsubscribe(self, *channels: str) -> None:
        """Unsubscribe from one or more channels.

        Args:
            *channels: Channel names to unsubscribe from
        """
        ...


@runtime_checkable
class CacheProtocol(Protocol):
    """Protocol for cache services.

    Cache services provide key-value storage with optional TTL support.

    Example Implementation:
        class MyCache:
            async def get(self, key: str) -> Any | None:
                return await self.redis.get(key)

            async def set(self, key: str, value: Any, ttl: int | None = None) -> bool:
                return await self.redis.set(key, value, ex=ttl)

            async def delete(self, key: str) -> bool:
                return await self.redis.delete(key) > 0

            async def exists(self, key: str) -> bool:
                return await self.redis.exists(key) > 0
    """

    async def get(self, key: str) -> Any | None:
        """Get a value from the cache.

        Args:
            key: The cache key

        Returns:
            The cached value, or None if not found.
        """
        ...

    async def set(self, key: str, value: Any, ttl: int | None = None) -> bool:
        """Set a value in the cache.

        Args:
            key: The cache key
            value: The value to cache
            ttl: Optional time-to-live in seconds

        Returns:
            True if the value was set successfully.
        """
        ...

    async def delete(self, key: str) -> bool:
        """Delete a value from the cache.

        Args:
            key: The cache key to delete

        Returns:
            True if the key was deleted, False if it didn't exist.
        """
        ...

    async def exists(self, key: str) -> bool:
        """Check if a key exists in the cache.

        Args:
            key: The cache key to check

        Returns:
            True if the key exists, False otherwise.
        """
        ...


@runtime_checkable
class MetricsProviderProtocol(Protocol):
    """Protocol for services that provide metrics for monitoring.

    Services implementing this protocol expose metrics that can be
    collected by monitoring systems like Prometheus.

    Example Implementation:
        class MyService:
            def get_metrics(self) -> dict[str, Any]:
                return {
                    "requests_total": self._request_count,
                    "errors_total": self._error_count,
                    "latency_p99_ms": self._latency_histogram.p99(),
                }
    """

    def get_metrics(self) -> dict[str, Any]:
        """Get service metrics for monitoring.

        Returns:
            Dictionary of metric name to value mappings.
        """
        ...


@runtime_checkable
class LifecycleProtocol(Protocol):
    """Protocol for services with start/stop lifecycle management.

    Services implementing this protocol can be started and stopped
    gracefully, typically used for background tasks and workers.

    Example Implementation:
        class MyWorker:
            async def start(self) -> None:
                self._running = True
                self._task = asyncio.create_task(self._run_loop())

            async def stop(self) -> None:
                self._running = False
                if self._task:
                    self._task.cancel()
                    with suppress(asyncio.CancelledError):
                        await self._task

            def is_running(self) -> bool:
                return self._running
    """

    async def start(self) -> None:
        """Start the service.

        This method should initialize resources and start background tasks.
        """
        ...

    async def stop(self) -> None:
        """Stop the service gracefully.

        This method should clean up resources and stop background tasks.
        """
        ...

    def is_running(self) -> bool:
        """Check if the service is currently running.

        Returns:
            True if the service is running, False otherwise.
        """
        ...


# Type aliases for common protocol combinations
AIServiceWithLifecycle = AIServiceProtocol | LifecycleProtocol
BroadcasterWithMetrics = BroadcasterProtocol | MetricsProviderProtocol


__all__ = [
    # Core protocols
    "AIServiceProtocol",
    # Type aliases
    "AIServiceWithLifecycle",
    "BroadcasterProtocol",
    "BroadcasterWithMetrics",
    "CacheProtocol",
    "HealthCheckableProtocol",
    # Type variables
    "InputT",
    "LifecycleProtocol",
    "MetricsProviderProtocol",
    "ModelLoaderProtocol",
    "OutputT",
    "QueueProcessorProtocol",
    "SubscribableProtocol",
]
