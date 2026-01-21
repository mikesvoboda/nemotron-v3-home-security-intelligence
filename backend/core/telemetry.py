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

    # Using the trace_span context manager
    from backend.core.telemetry import trace_span
    with trace_span("process_detection", camera_id=camera_id) as span:
        span.set_attribute("detection_count", len(detections))

    # Using the trace_function decorator
    from backend.core.telemetry import trace_function
    @trace_function("analyze_batch")
    async def analyze_batch(batch_id: str) -> Result:
        ...

    # Getting trace IDs for log correlation
    from backend.core.telemetry import get_trace_id, get_span_id
    logger.info("Processing", extra={"trace_id": get_trace_id()})

    # In app shutdown
    shutdown_telemetry()

NEM-1503: Added trace_span context manager, trace_function decorator, and trace ID utilities.
"""

from __future__ import annotations

import functools
import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING, ParamSpec, Protocol, TypeVar, runtime_checkable

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


# =============================================================================
# Trace ID and Span ID Utilities (NEM-1503)
# =============================================================================


def get_trace_id() -> str | None:
    """Get the current trace ID as a hex string for log correlation.

    The trace ID is a 32-character lowercase hex string that uniquely identifies
    the entire request/transaction across all services. Include this in logs
    to correlate log entries with distributed traces.

    Returns:
        32-character lowercase hex string trace ID, or None if no trace is active
        or OpenTelemetry is not enabled.

    Example:
        >>> from backend.core.telemetry import get_trace_id
        >>> logger.info("Processing request", extra={"trace_id": get_trace_id()})
    """
    try:
        span = get_current_span()
        # Check if span has get_span_context method (real OTel span)
        if hasattr(span, "get_span_context"):
            span_context = span.get_span_context()
            if span_context and span_context.is_valid:
                return format(span_context.trace_id, "032x")
    except Exception as e:
        # Log at debug level to avoid noise while still providing visibility
        logger.debug("Failed to get trace_id: %s", e)
    return None


def get_span_id() -> str | None:
    """Get the current span ID as a hex string.

    The span ID is a 16-character lowercase hex string that uniquely identifies
    the current operation within a trace.

    Returns:
        16-character lowercase hex string span ID, or None if no span is active
        or OpenTelemetry is not enabled.

    Example:
        >>> from backend.core.telemetry import get_span_id
        >>> span_id = get_span_id()
    """
    try:
        span = get_current_span()
        if hasattr(span, "get_span_context"):
            span_context = span.get_span_context()
            if span_context and span_context.is_valid:
                return format(span_context.span_id, "016x")
    except Exception as e:
        # Log at debug level to avoid noise while still providing visibility
        logger.debug("Failed to get span_id: %s", e)
    return None


def get_trace_context() -> dict[str, str | None]:
    """Get the current trace context for log enrichment.

    Returns a dictionary with trace_id and span_id that can be merged
    into log extra fields for correlation.

    Returns:
        Dictionary with trace_id and span_id keys (values may be None)

    Example:
        >>> from backend.core.telemetry import get_trace_context
        >>> logger.info("Operation complete", extra={**get_trace_context(), "result": "success"})
    """
    return {
        "trace_id": get_trace_id(),
        "span_id": get_span_id(),
    }


# =============================================================================
# W3C Trace Context Propagation (NEM-3147)
# =============================================================================


def get_trace_headers() -> dict[str, str]:
    """Get W3C Trace Context headers for propagation to downstream services.

    This function extracts the current trace context and returns HTTP headers
    that can be included in outgoing requests to propagate the trace across
    service boundaries. Uses the W3C Trace Context standard (traceparent and
    tracestate headers).

    When OpenTelemetry is enabled, this uses the standard W3CTraceContextPropagator.
    When disabled, returns an empty dict (no-op).

    Returns:
        Dictionary with traceparent and tracestate headers if trace is active,
        empty dict otherwise.

    Example:
        >>> from backend.core.telemetry import get_trace_headers
        >>> headers = {"Content-Type": "application/json"}
        >>> headers.update(get_trace_headers())
        >>> # headers now contains traceparent and tracestate if tracing is active
    """
    try:
        from opentelemetry.propagate import inject

        headers: dict[str, str] = {}
        inject(headers)
        return headers
    except ImportError:
        # OpenTelemetry not installed, return empty headers
        return {}
    except Exception as e:
        # Log at debug level to avoid noise
        logger.debug("Failed to get trace headers: %s", e)
        return {}


# =============================================================================
# trace_span Context Manager (NEM-1503)
# =============================================================================


@contextmanager
def trace_span(
    name: str,
    record_exception_on_error: bool = True,
    **attributes: str | int | float | bool,
) -> Iterator[SpanProtocol]:
    """Context manager for creating a traced span with automatic exception recording.

    This provides a convenient way to create spans with attributes and automatic
    exception handling. The span is set as the current span in context.

    Args:
        name: Name of the span (e.g., "detect_objects", "analyze_batch")
        record_exception_on_error: If True, automatically record exceptions on the span
        **attributes: Key-value pairs to set as span attributes

    Yields:
        The created Span object (SpanProtocol compatible)

    Example:
        >>> from backend.core.telemetry import trace_span
        >>> with trace_span("detect_objects", camera_id="front_door") as span:
        ...     results = await detector.detect(image_path)
        ...     span.set_attribute("detection_count", len(results))

        >>> # With exception handling
        >>> with trace_span("risky_operation") as span:
        ...     result = perform_risky_operation()  # Exceptions auto-recorded
    """
    tracer = get_tracer("trace_span")

    # When using OTel, start_as_current_span returns a context manager.
    # We need to enter the context first to get the actual span.
    span_context = tracer.start_as_current_span(name)

    try:
        with span_context as span:
            # Set initial attributes after entering context
            for key, value in attributes.items():
                span.set_attribute(key, value)
            yield span
    except Exception as e:
        if record_exception_on_error:
            record_exception(e)
        raise


# =============================================================================
# trace_function Decorator (NEM-1503)
# =============================================================================

P = ParamSpec("P")
R = TypeVar("R")


def trace_function(
    name: str | None = None,
    **static_attributes: str | int | float | bool,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator to trace a function execution with automatic span management.

    Creates a span around the decorated function, capturing execution time
    and optionally recording exceptions. Works with both sync and async functions.

    Args:
        name: Optional span name (defaults to function name)
        **static_attributes: Attributes to add to every span created by this decorator

    Returns:
        A decorator function

    Example:
        >>> from backend.core.telemetry import trace_function
        >>>
        >>> @trace_function("rtdetr_detection")
        ... async def detect_objects(image_path: str) -> list[Detection]:
        ...     return await client.detect(image_path)
        >>>
        >>> @trace_function(service="nemotron")
        ... async def analyze_batch(batch: Batch) -> AnalysisResult:
        ...     return await analyzer.analyze(batch)
        >>>
        >>> # Sync functions also work
        >>> @trace_function("compute_risk")
        ... def compute_risk_score(detections: list) -> int:
        ...     return sum(d.confidence for d in detections)
    """
    import asyncio

    # Convert static_attributes for use in trace_span
    attrs: dict[str, str | int | float | bool] = dict(static_attributes)

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        span_name = name or func.__name__

        @functools.wraps(func)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            with trace_span(span_name, record_exception_on_error=True, **attrs):
                result = func(*args, **kwargs)
                # Await if coroutine
                if asyncio.iscoroutine(result):
                    return await result  # type: ignore[return-value,no-any-return]
                return result  # type: ignore[return-value]

        @functools.wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            with trace_span(span_name, record_exception_on_error=True, **attrs):
                return func(*args, **kwargs)

        # Check if the function is async
        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore[return-value]
        return sync_wrapper  # type: ignore[return-value]

    return decorator


# =============================================================================
# AI Service Span Helper (NEM-3147)
# =============================================================================


@contextmanager
def ai_service_span(
    service_name: str,
    operation: str,
    *,
    endpoint_url: str | None = None,
    **attributes: str | int | float | bool,
) -> Iterator[SpanProtocol]:
    """Context manager for AI service call tracing with semantic conventions.

    Creates a span with OpenTelemetry semantic conventions for HTTP client calls,
    including proper span kind and attributes for distributed tracing correlation.

    This is optimized for AI service calls (RT-DETR, Nemotron, Florence, CLIP, etc.)
    and includes attributes that help correlate circuit breaker events with traces.

    Args:
        service_name: Name of the AI service (e.g., "rtdetr", "nemotron", "florence")
        operation: Operation being performed (e.g., "detect", "analyze", "embed")
        endpoint_url: Optional URL of the service endpoint
        **attributes: Additional attributes to set on the span

    Yields:
        The created Span object (SpanProtocol compatible)

    Example:
        >>> from backend.core.telemetry import ai_service_span
        >>> with ai_service_span("florence", "extract", endpoint_url=url) as span:
        ...     response = await client.post(url, json=payload)
        ...     span.set_attribute("ai.response_tokens", len(response.text))
    """
    span_name = f"{service_name}.{operation}"

    # Build semantic attributes for AI service calls
    span_attributes: dict[str, str | int | float | bool] = {
        "ai.service": service_name,
        "ai.operation": operation,
        "peer.service": service_name,  # Standard OTEL attribute for remote service
    }
    if endpoint_url:
        span_attributes["http.url"] = endpoint_url
        span_attributes["server.address"] = (
            endpoint_url.split("://")[-1].split("/")[0].split(":")[0]
        )

    # Merge with caller-provided attributes
    span_attributes.update(attributes)

    with trace_span(span_name, record_exception_on_error=True, **span_attributes) as span:
        yield span


def set_ai_response_attributes(
    span: SpanProtocol,
    *,
    status_code: int | None = None,
    response_size_bytes: int | None = None,
    inference_time_ms: float | None = None,
    model_name: str | None = None,
    tokens_used: int | None = None,
    error: str | None = None,
) -> None:
    """Set standard response attributes on an AI service span.

    Convenience function to add response-related attributes after an AI service
    call completes. These attributes help with performance analysis and debugging.

    Args:
        span: The span to add attributes to
        status_code: HTTP response status code
        response_size_bytes: Size of the response body in bytes
        inference_time_ms: AI model inference time in milliseconds
        model_name: Name of the AI model used
        tokens_used: Number of tokens consumed (for LLM calls)
        error: Error message if the call failed
    """
    if status_code is not None:
        span.set_attribute("http.response.status_code", status_code)
    if response_size_bytes is not None:
        span.set_attribute("http.response.body.size", response_size_bytes)
    if inference_time_ms is not None:
        span.set_attribute("ai.inference_time_ms", inference_time_ms)
    if model_name is not None:
        span.set_attribute("ai.model", model_name)
    if tokens_used is not None:
        span.set_attribute("ai.tokens_used", tokens_used)
    if error is not None:
        span.set_attribute("error", True)
        span.set_attribute("error.message", error)


# =============================================================================
# Pyroscope Continuous Profiling (NEM-3103)
# =============================================================================


def init_profiling() -> None:
    """Initialize Pyroscope continuous profiling for backend service.

    This function configures Pyroscope for continuous profiling of the backend
    service. It enables CPU and GIL profiling to identify performance bottlenecks
    in both synchronous and asynchronous code paths.

    Configuration is via environment variables:
    - PYROSCOPE_ENABLED: Enable/disable profiling (default: true)
    - PYROSCOPE_SERVER: Pyroscope server address (default: http://pyroscope:4040)
    - ENVIRONMENT: Environment tag for profiles (default: production)

    The function gracefully handles:
    - Missing pyroscope-io package (ImportError)
    - Configuration errors (logs warning, doesn't fail startup)

    Example:
        >>> from backend.core.telemetry import init_profiling
        >>> init_profiling()  # Called during app startup
    """
    import os

    # Skip if Pyroscope is disabled
    if os.getenv("PYROSCOPE_ENABLED", "true").lower() != "true":
        logger.info("Pyroscope profiling disabled (PYROSCOPE_ENABLED != true)")
        return

    try:
        import pyroscope

        pyroscope_server = os.getenv("PYROSCOPE_SERVER", "http://pyroscope:4040")

        pyroscope.configure(
            application_name="nemotron-backend",
            server_address=pyroscope_server,
            tags={
                "service": "backend",
                "environment": os.getenv("ENVIRONMENT", "development"),
            },
            oncpu=True,
            gil=True,
            enable_logging=True,
        )
        logger.info(f"Pyroscope profiling initialized: server={pyroscope_server}")
    except ImportError:
        # pyroscope-io not installed, skip profiling
        logger.debug("Pyroscope profiling skipped: pyroscope-io not installed")
    except Exception as e:
        # Log but don't fail if profiling setup fails
        logger.warning(f"Failed to initialize Pyroscope profiling: {e}")
