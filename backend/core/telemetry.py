"""OpenTelemetry distributed tracing setup for cross-service request correlation.

NEM-1629: This module provides OpenTelemetry instrumentation for distributed tracing
across the home security intelligence system. It enables:

1. Automatic trace propagation across services (backend, RT-DETRv2, Nemotron, etc.)
2. Correlation of logs with trace IDs for debugging
3. Performance monitoring via span timings
4. Integration with Jaeger, Tempo, or other OTLP-compatible backends

Configuration is via environment variables:
- OTEL_ENABLED: Enable/disable tracing (default: False)
- OTEL_SERVICE_NAME: Service name in traces (default: nemotron-backend)
- OTEL_EXPORTER_OTLP_ENDPOINT: OTLP endpoint (default: http://localhost:4317)
- OTEL_EXPORTER_OTLP_INSECURE: Use insecure connection (default: True)
- OTEL_TRACE_SAMPLE_RATE: Sampling rate 0.0-1.0 (default: 1.0)

Usage:
    from backend.core.telemetry import setup_telemetry, get_tracer, shutdown_telemetry

    # In app startup (lifespan)
    setup_telemetry(app, settings)

    # In services for custom spans
    tracer = get_tracer(__name__)
    with tracer.start_as_current_span("my_operation"):
        # ... operation code

    # In app shutdown
    shutdown_telemetry()
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from types import TracebackType

    from fastapi import FastAPI

    from backend.core.config import Settings

logger = logging.getLogger(__name__)


@runtime_checkable
class SpanProtocol(Protocol):
    """Protocol for OpenTelemetry-compatible spans.

    This protocol defines the minimal interface needed for span operations,
    allowing both real OpenTelemetry spans and no-op spans to be used
    interchangeably with proper type checking.
    """

    def set_attribute(self, key: str, value: object) -> None:
        """Set an attribute on the span."""
        ...

    def record_exception(
        self, exception: Exception, attributes: dict[str, object] | None = None
    ) -> None:
        """Record an exception on the span."""
        ...

    def set_status(self, status: object, description: str | None = None) -> None:
        """Set the status of the span."""
        ...

    def __enter__(self) -> SpanProtocol:
        """Enter context manager."""
        ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit context manager."""
        ...


@runtime_checkable
class TracerProtocol(Protocol):
    """Protocol for OpenTelemetry-compatible tracers.

    This protocol defines the minimal interface needed for tracer operations,
    allowing both real OpenTelemetry tracers and no-op tracers to be used
    interchangeably with proper type checking.
    """

    def start_as_current_span(self, name: str, **kwargs: object) -> SpanProtocol:
        """Start a new span as the current span in context."""
        ...

    def start_span(self, name: str, **kwargs: object) -> SpanProtocol:
        """Start a new span without setting it as current."""
        ...


# Module-level state for telemetry
_tracer_provider: object | None = None
_is_initialized: bool = False


def setup_telemetry(app: FastAPI, settings: Settings) -> bool:
    """Initialize OpenTelemetry tracing for the application.

    This function sets up:
    1. TracerProvider with service name and resource attributes
    2. OTLP exporter for sending traces to a collector (Jaeger, Tempo, etc.)
    3. FastAPI auto-instrumentation for HTTP request/response tracing
    4. HTTPX auto-instrumentation for outgoing HTTP requests (AI services)
    5. SQLAlchemy instrumentation for database query tracing
    6. Redis instrumentation for cache operation tracing

    Args:
        app: FastAPI application instance to instrument
        settings: Application settings with OTEL configuration

    Returns:
        True if telemetry was initialized, False if disabled or already initialized
    """
    global _tracer_provider, _is_initialized  # noqa: PLW0603 - singleton pattern

    if _is_initialized:
        logger.debug("OpenTelemetry already initialized, skipping")
        return False

    if not settings.otel_enabled:
        logger.info("OpenTelemetry tracing disabled (OTEL_ENABLED=False)")
        return False

    try:
        # Import OpenTelemetry modules only when needed
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from opentelemetry.instrumentation.redis import RedisInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        from opentelemetry.sdk.resources import SERVICE_NAME, Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.trace.sampling import TraceIdRatioBased

        # Create resource with service information
        resource = Resource.create(
            {
                SERVICE_NAME: settings.otel_service_name,
                "service.version": settings.app_version,
                "deployment.environment": "production" if not settings.debug else "development",
            }
        )

        # Configure sampler based on sample rate
        sampler = TraceIdRatioBased(settings.otel_trace_sample_rate)

        # Create tracer provider
        provider = TracerProvider(resource=resource, sampler=sampler)

        # Configure OTLP exporter
        exporter = OTLPSpanExporter(
            endpoint=settings.otel_exporter_otlp_endpoint,
            insecure=settings.otel_exporter_otlp_insecure,
        )

        # Add batch processor for efficient trace export
        provider.add_span_processor(BatchSpanProcessor(exporter))

        # Set as global tracer provider
        trace.set_tracer_provider(provider)
        _tracer_provider = provider

        # Instrument FastAPI
        FastAPIInstrumentor.instrument_app(app)
        logger.debug("FastAPI instrumented for tracing")

        # Instrument HTTPX for outgoing AI service calls
        HTTPXClientInstrumentor().instrument()
        logger.debug("HTTPX instrumented for tracing")

        # Instrument SQLAlchemy for database queries
        # Note: Engine instrumentation happens automatically when engine is created
        SQLAlchemyInstrumentor().instrument()
        logger.debug("SQLAlchemy instrumented for tracing")

        # Instrument Redis for cache operations
        RedisInstrumentor().instrument()
        logger.debug("Redis instrumented for tracing")

        _is_initialized = True
        logger.info(
            f"OpenTelemetry tracing initialized: service={settings.otel_service_name}, "
            f"endpoint={settings.otel_exporter_otlp_endpoint}, "
            f"sample_rate={settings.otel_trace_sample_rate}"
        )
        return True

    except ImportError as e:
        logger.warning(f"OpenTelemetry dependencies not installed: {e}")
        return False
    except Exception as e:
        logger.error(f"Failed to initialize OpenTelemetry: {e}")
        return False


def shutdown_telemetry() -> None:
    """Shutdown OpenTelemetry and flush any pending traces.

    This should be called during application shutdown to ensure all
    pending traces are exported before the process exits.
    """
    global _tracer_provider, _is_initialized  # noqa: PLW0603 - singleton pattern

    if not _is_initialized or _tracer_provider is None:
        return

    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from opentelemetry.instrumentation.redis import RedisInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        from opentelemetry.sdk.trace import TracerProvider

        # Uninstrument all libraries
        FastAPIInstrumentor.uninstrument()
        HTTPXClientInstrumentor().uninstrument()
        SQLAlchemyInstrumentor().uninstrument()
        RedisInstrumentor().uninstrument()

        # Shutdown tracer provider (flushes pending spans)
        if isinstance(_tracer_provider, TracerProvider):
            _tracer_provider.shutdown()

        _tracer_provider = None
        _is_initialized = False
        logger.info("OpenTelemetry tracing shut down")

    except Exception as e:
        logger.error(f"Error shutting down OpenTelemetry: {e}")


def get_tracer(name: str) -> TracerProtocol:
    """Get a tracer instance for creating custom spans.

    This function returns a tracer that can be used to create custom spans
    for operations not automatically instrumented. If telemetry is not
    initialized, returns a no-op tracer.

    Args:
        name: Name for the tracer, typically __name__ of the calling module

    Returns:
        Tracer instance for creating spans (TracerProtocol compatible)

    Example:
        tracer = get_tracer(__name__)
        with tracer.start_as_current_span("process_detection") as span:
            span.set_attribute("camera_id", camera_id)
            # ... detection processing
    """
    try:
        from opentelemetry import trace

        # cast() is not needed since both real Tracer and _NoOpTracer
        # conform to TracerProtocol at runtime
        return trace.get_tracer(name)  # type: ignore[return-value,no-any-return]
    except ImportError:
        # Return a no-op tracer if OpenTelemetry is not installed
        return _NoOpTracer()


def get_current_span() -> SpanProtocol:
    """Get the current active span from context.

    Returns:
        Current span if one is active, or a no-op span otherwise (SpanProtocol compatible)
    """
    try:
        from opentelemetry import trace

        return trace.get_current_span()  # type: ignore[return-value,no-any-return]
    except ImportError:
        return _NoOpSpan()


def add_span_attributes(**attributes: str | int | float | bool) -> None:
    """Add attributes to the current span.

    This is a convenience function to add attributes to the current span
    without needing to manage span context directly.

    Args:
        **attributes: Key-value pairs to add as span attributes
    """
    span = get_current_span()
    for key, value in attributes.items():
        if hasattr(span, "set_attribute"):
            span.set_attribute(key, value)


def record_exception(exception: Exception, attributes: dict[str, object] | None = None) -> None:
    """Record an exception on the current span.

    This marks the span as having an error and records exception details
    for debugging in trace viewers.

    Args:
        exception: The exception to record
        attributes: Additional attributes to add to the exception event
    """
    span = get_current_span()
    if hasattr(span, "record_exception"):
        span.record_exception(exception, attributes=attributes or {})
        if hasattr(span, "set_status"):
            from opentelemetry.trace import StatusCode

            span.set_status(StatusCode.ERROR, str(exception))


def is_telemetry_enabled() -> bool:
    """Check if telemetry has been initialized.

    Returns:
        True if OpenTelemetry tracing is active
    """
    return _is_initialized


class _NoOpSpan:
    """No-op span for when OpenTelemetry is not available."""

    def set_attribute(self, key: str, value: object) -> None:
        """No-op set_attribute."""

    def record_exception(
        self, exception: Exception, attributes: dict[str, object] | None = None
    ) -> None:
        """No-op record_exception."""

    def set_status(self, status: object, description: str | None = None) -> None:
        """No-op set_status."""

    def __enter__(self) -> _NoOpSpan:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object | None,
    ) -> None:
        """No-op exit context manager."""


class _NoOpTracer:
    """No-op tracer for when OpenTelemetry is not available."""

    def start_as_current_span(self, name: str, **kwargs: object) -> _NoOpSpan:  # noqa: ARG002
        """Return a no-op span."""
        return _NoOpSpan()

    def start_span(self, name: str, **kwargs: object) -> _NoOpSpan:  # noqa: ARG002
        """Return a no-op span."""
        return _NoOpSpan()
