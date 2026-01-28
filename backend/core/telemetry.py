"""OpenTelemetry distributed tracing setup for cross-service request correlation.

NEM-1629: This module provides OpenTelemetry instrumentation for distributed tracing
across the home security intelligence system. It enables:

1. Automatic trace propagation across services (backend, YOLO26, Nemotron, etc.)
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

    # Using baggage for cross-service context (NEM-3382)
    from backend.core.telemetry import set_baggage, get_baggage
    set_baggage("camera_id", "front_door")
    camera_id = get_baggage("camera_id")

    # In app shutdown
    shutdown_telemetry()

NEM-1503: Added trace_span context manager, trace_function decorator, and trace ID utilities.
NEM-3380: Added ParentBased composite sampler for smarter trace sampling.
NEM-3382: Added Baggage for cross-service context propagation.
NEM-3793: Added priority-based sampling to preserve important traces while reducing volume.
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

    def add_event(
        self,
        name: str,
        attributes: dict[str, object] | None = None,
        timestamp: int | None = None,
    ) -> None:
        """Add an event (milestone) to the span (NEM-3434)."""
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
    2. ParentBased composite sampler for smarter sampling (NEM-3380)
    3. OTLP exporter for sending traces to a collector (Jaeger, Tempo, etc.)
    4. FastAPI auto-instrumentation for HTTP request/response tracing
    5. HTTPX auto-instrumentation for outgoing HTTP requests (AI services)
    6. SQLAlchemy instrumentation for database query tracing
    7. Redis instrumentation for cache operation tracing
    8. Composite propagator with W3C Trace Context and Baggage (NEM-3382)

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
        from opentelemetry.baggage.propagation import W3CBaggagePropagator
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from opentelemetry.instrumentation.redis import RedisInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        from opentelemetry.propagate import set_global_textmap
        from opentelemetry.propagators.composite import CompositePropagator
        from opentelemetry.sdk.resources import (
            SERVICE_NAME,
            OsResourceDetector,
            ProcessResourceDetector,
            Resource,
            get_aggregated_resources,
        )
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.trace.sampling import (
            ALWAYS_OFF,
            ALWAYS_ON,
            ParentBased,
            TraceIdRatioBased,
        )
        from opentelemetry.trace.propagation.tracecontext import (
            TraceContextTextMapPropagator,
        )

        # NEM-3383: Create resource with automatic container/host detection
        # Start with service-specific attributes
        service_resource = Resource.create(
            {
                SERVICE_NAME: settings.otel_service_name,
                "service.version": settings.app_version,
                "deployment.environment": "production" if not settings.debug else "development",
            }
        )

        # Collect resource detectors for automatic attribute detection
        resource_detectors = [
            ProcessResourceDetector(),  # Process PID, runtime info
            OsResourceDetector(),  # OS type, version
        ]

        # Try to add Docker/container resource detector if available
        # NEM-3383: Provides container ID for correlation with container logs/metrics
        try:
            from opentelemetry_resourcedetector_docker import DockerResourceDetector

            resource_detectors.append(DockerResourceDetector())
            logger.debug("Docker resource detector enabled for container correlation")
        except ImportError:
            logger.debug("Docker resource detector not available, skipping container detection")

        # Aggregate detected resources with service attributes
        detected_resource = get_aggregated_resources(resource_detectors)
        resource = service_resource.merge(detected_resource)

        # Configure priority-based sampler (NEM-3793)
        # This provides intelligent sampling decisions based on trace priority:
        # - Error traces: Always sample (100%) for debugging
        # - High-risk events: Always sample (100%) for security monitoring
        # - High-priority endpoints (/api/events, /api/alerts): Always sample
        # - Medium-priority endpoints: Configurable rate (default 50%)
        # - Background tasks (/health, /metrics): Lower sample rate (default 10%)
        # - Default: Configurable base rate (default 10%)
        #
        # Parent-based behavior is preserved:
        # - Local parent sampled: Always sample to maintain complete traces
        # - Local parent not sampled: Always drop to maintain decision consistency
        # - Remote parent sampled: Always sample to honor upstream decision
        # - Remote parent not sampled: Always drop to honor upstream decision
        #
        # Configuration via environment variables (see backend/core/sampling.py):
        # - OTEL_SAMPLING_ERROR_RATE, OTEL_SAMPLING_HIGH_RISK_RATE, etc.
        try:
            from backend.core.sampling import create_otel_sampler

            sampler = create_otel_sampler(settings)
            if sampler is None:
                # Fallback to simple TraceIdRatioBased if sampling module fails
                root_sampler = TraceIdRatioBased(settings.otel_trace_sample_rate)
                sampler = ParentBased(
                    root=root_sampler,
                    local_parent_sampled=ALWAYS_ON,
                    local_parent_not_sampled=ALWAYS_OFF,
                    remote_parent_sampled=ALWAYS_ON,
                    remote_parent_not_sampled=ALWAYS_OFF,
                )
                logger.debug("Using fallback TraceIdRatioBased sampler")
            else:
                logger.debug("Priority-based sampler configured successfully")
        except ImportError:
            # Fallback if sampling module is not available
            root_sampler = TraceIdRatioBased(settings.otel_trace_sample_rate)
            sampler = ParentBased(
                root=root_sampler,
                local_parent_sampled=ALWAYS_ON,
                local_parent_not_sampled=ALWAYS_OFF,
                remote_parent_sampled=ALWAYS_ON,
                remote_parent_not_sampled=ALWAYS_OFF,
            )
            logger.debug("Using fallback TraceIdRatioBased sampler (sampling module not available)")

        # Create tracer provider
        provider = TracerProvider(resource=resource, sampler=sampler)

        # Configure OTLP exporter
        exporter = OTLPSpanExporter(
            endpoint=settings.otel_exporter_otlp_endpoint,
            insecure=settings.otel_exporter_otlp_insecure,
        )

        # Configure BatchSpanProcessor for high-throughput scenarios (NEM-3433)
        # These settings are tuned for production workloads (100+ spans/sec)
        batch_processor = BatchSpanProcessor(
            exporter,
            max_queue_size=settings.otel_batch_max_queue_size,
            max_export_batch_size=settings.otel_batch_max_export_batch_size,
            schedule_delay_millis=settings.otel_batch_schedule_delay_ms,
            export_timeout_millis=settings.otel_batch_export_timeout_ms,
        )
        provider.add_span_processor(batch_processor)
        logger.debug(
            "BatchSpanProcessor configured: queue_size=%d, batch_size=%d, delay_ms=%d",
            settings.otel_batch_max_queue_size,
            settings.otel_batch_max_export_batch_size,
            settings.otel_batch_schedule_delay_ms,
        )

        # Set as global tracer provider
        trace.set_tracer_provider(provider)
        _tracer_provider = provider

        # Configure composite propagator with W3C Trace Context and Baggage (NEM-3382)
        # This enables propagation of both trace context and baggage across services
        composite_propagator = CompositePropagator(
            [TraceContextTextMapPropagator(), W3CBaggagePropagator()]
        )
        set_global_textmap(composite_propagator)
        logger.debug("Configured composite propagator with W3C Trace Context and Baggage")

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

        # NEM-3792: Instrument Python logging for trace-log correlation
        # This adds trace_id and span_id to log records, enabling unified observability
        _setup_otel_logging(settings.otel_service_name)

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


def _setup_otel_logging(service_name: str) -> None:
    """Configure OpenTelemetry logging instrumentation for trace-log correlation (NEM-3792).

    This function instruments Python's logging module to automatically inject
    trace_id and span_id into log records when a span is active. This enables
    unified observability by correlating logs with distributed traces.

    The logging instrumentation:
    1. Adds trace_id and span_id fields to log records
    2. Sets otelTraceID and otelSpanID attributes for structured logging
    3. Enables correlation in log aggregators (ELK, Loki, etc.)

    Note: This uses the OTEL logging instrumentation which adds context to
    existing Python logs, rather than the full OTEL Logs SDK which would
    export logs via OTLP. This approach integrates better with existing
    logging infrastructure while still enabling trace correlation.

    Args:
        service_name: Service name for identifying log source
    """
    try:
        from opentelemetry.instrumentation.logging import LoggingInstrumentor

        # Instrument Python logging to include trace context
        # This adds trace_id and span_id to log records automatically
        LoggingInstrumentor().instrument(set_logging_format=False)
        logger.debug(f"OpenTelemetry logging instrumentation enabled for {service_name}")

    except ImportError:
        logger.warning("OpenTelemetry logging instrumentation not available")
    except Exception as e:
        logger.warning(f"Failed to setup OpenTelemetry logging: {e}")


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
        from opentelemetry.instrumentation.logging import LoggingInstrumentor
        from opentelemetry.instrumentation.redis import RedisInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        from opentelemetry.sdk.trace import TracerProvider

        # Uninstrument all libraries
        FastAPIInstrumentor.uninstrument()
        HTTPXClientInstrumentor().uninstrument()
        SQLAlchemyInstrumentor().uninstrument()
        RedisInstrumentor().uninstrument()
        # NEM-3792: Uninstrument logging
        LoggingInstrumentor().uninstrument()

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


# =============================================================================
# Span Events for Pipeline Milestones (NEM-3434)
# =============================================================================


def add_span_event(
    name: str,
    attributes: dict[str, str | int | float | bool] | None = None,
    timestamp_ns: int | None = None,
) -> None:
    """Add an event (milestone) to the current span.

    Events are timestamped annotations that mark significant points during
    a span's lifetime. Use them to record pipeline milestones, state transitions,
    and other notable moments.

    Args:
        name: Name of the event (e.g., "detection.started", "enrichment.complete")
        attributes: Optional attributes to attach to the event
        timestamp_ns: Optional timestamp in nanoseconds since epoch. If not provided,
            the current time is used.

    Example:
        >>> from backend.core.telemetry import add_span_event, trace_span
        >>> with trace_span("process_batch", batch_id=batch_id) as span:
        ...     add_span_event("batch.started", {"detection_count": 10})
        ...     # ... processing
        ...     add_span_event("detection.complete", {"duration_ms": 150})
        ...     # ... more processing
        ...     add_span_event("enrichment.complete", {"enriched_count": 8})
    """
    span = get_current_span()
    if hasattr(span, "add_event"):
        # Convert to dict[str, object] for type compatibility
        attrs: dict[str, object] = dict(attributes) if attributes else {}
        if timestamp_ns is not None:
            span.add_event(name, attributes=attrs, timestamp=timestamp_ns)
        else:
            span.add_event(name, attributes=attrs)


def record_pipeline_milestone(
    milestone: str,
    *,
    stage: str | None = None,
    camera_id: str | None = None,
    batch_id: str | None = None,
    detection_count: int | None = None,
    duration_ms: float | None = None,
    **extra_attributes: str | int | float | bool,
) -> None:
    """Record a pipeline processing milestone as a span event.

    Convenience function for recording common pipeline milestones with
    standardized attribute names.

    Args:
        milestone: Name of the milestone (e.g., "started", "detection_complete",
            "enrichment_complete", "analysis_complete", "event_created")
        stage: Pipeline stage name (e.g., "watch", "detect", "batch", "analyze")
        camera_id: Camera identifier if applicable
        batch_id: Batch identifier if applicable
        detection_count: Number of detections if applicable
        duration_ms: Duration in milliseconds if applicable
        **extra_attributes: Additional custom attributes

    Example:
        >>> from backend.core.telemetry import record_pipeline_milestone
        >>> record_pipeline_milestone(
        ...     "detection_complete",
        ...     stage="detect",
        ...     camera_id="front_door",
        ...     detection_count=5,
        ...     duration_ms=245.3,
        ... )
    """
    event_name = f"pipeline.{milestone}"
    attributes: dict[str, str | int | float | bool] = {}

    if stage:
        attributes["pipeline.stage"] = stage
    if camera_id:
        attributes["camera.id"] = camera_id
    if batch_id:
        attributes["batch.id"] = batch_id
    if detection_count is not None:
        attributes["pipeline.detection_count"] = detection_count
    if duration_ms is not None:
        attributes["pipeline.duration_ms"] = duration_ms

    attributes.update(extra_attributes)
    add_span_event(event_name, attributes)


# =============================================================================
# Span Links for Async Batch Correlation (NEM-3435)
# =============================================================================


class SpanLinkContext:
    """Holds span context information for creating links.

    This class captures the trace_id and span_id from a span context,
    allowing them to be passed across async boundaries and used to
    create span links in child spans.
    """

    def __init__(self, trace_id: str, span_id: str) -> None:
        """Initialize with trace and span IDs.

        Args:
            trace_id: 32-character hex trace ID
            span_id: 16-character hex span ID
        """
        self.trace_id = trace_id
        self.span_id = span_id

    def to_dict(self) -> dict[str, str]:
        """Convert to dictionary for serialization.

        Returns:
            Dictionary with trace_id and span_id keys
        """
        return {"trace_id": self.trace_id, "span_id": self.span_id}

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> SpanLinkContext | None:
        """Create from dictionary.

        Args:
            data: Dictionary with trace_id and span_id keys

        Returns:
            SpanLinkContext instance or None if data is invalid
        """
        trace_id = data.get("trace_id")
        span_id = data.get("span_id")
        if trace_id and span_id:
            return cls(trace_id, span_id)
        return None


def capture_span_context() -> SpanLinkContext | None:
    """Capture the current span context for creating links later.

    Call this in the parent span to capture context that can be passed
    to async operations (like batch processing) for correlation.

    Returns:
        SpanLinkContext with trace_id and span_id, or None if no valid span

    Example:
        >>> from backend.core.telemetry import capture_span_context, trace_span
        >>> with trace_span("queue_detection") as span:
        ...     context = capture_span_context()
        ...     # Pass context to batch aggregator via Redis
        ...     await redis.add_to_queue(batch_key, {
        ...         "detection_id": detection_id,
        ...         "span_context": context.to_dict() if context else None,
        ...     })
    """
    trace_id = get_trace_id()
    span_id = get_span_id()
    if trace_id and span_id:
        return SpanLinkContext(trace_id, span_id)
    return None


def create_span_with_links(
    name: str,
    links: list[SpanLinkContext | dict[str, str] | None] | None = None,
    **attributes: str | int | float | bool,
) -> SpanProtocol:
    """Create a new span with links to related spans.

    Use this to create spans that are correlated with parent operations
    that occurred in a different async context (e.g., batch processing
    linked to the original detection spans).

    Args:
        name: Name of the span
        links: List of SpanLinkContext objects or dicts with trace_id/span_id
        **attributes: Attributes to set on the span

    Returns:
        The created span (must be used as context manager)

    Example:
        >>> from backend.core.telemetry import create_span_with_links, SpanLinkContext
        >>> # In batch processor, after retrieving detection contexts from Redis
        >>> contexts = [SpanLinkContext.from_dict(ctx) for ctx in detection_contexts]
        >>> with create_span_with_links(
        ...     "process_batch",
        ...     links=contexts,
        ...     batch_id=batch_id,
        ...     detection_count=len(detections),
        ... ) as span:
        ...     # Process the batch...
    """
    _tracer = get_tracer("span_links")

    # Convert links to OpenTelemetry Link objects if OTEL is available
    otel_links: list[object] = []
    if links:
        try:
            from opentelemetry.trace import Link, SpanContext, TraceFlags

            for link in links:
                if link is None:
                    continue

                # Handle dict or SpanLinkContext
                if isinstance(link, dict):
                    link_ctx = SpanLinkContext.from_dict(link)
                else:
                    link_ctx = link

                if link_ctx:
                    # Convert hex strings to integers
                    try:
                        trace_id_int = int(link_ctx.trace_id, 16)
                        span_id_int = int(link_ctx.span_id, 16)
                        span_context = SpanContext(
                            trace_id=trace_id_int,
                            span_id=span_id_int,
                            is_remote=True,
                            trace_flags=TraceFlags(0x01),  # Sampled
                        )
                        otel_links.append(Link(span_context))
                    except (ValueError, TypeError):
                        # Invalid hex string, skip this link
                        continue
        except ImportError:
            # OpenTelemetry not available, keep empty list
            pass

    # Start span with links
    try:
        from opentelemetry import trace as otel_trace

        tracer_impl = otel_trace.get_tracer("span_links")
        span = tracer_impl.start_span(name, links=otel_links)  # type: ignore[arg-type]

        # Set attributes
        for key, value in attributes.items():
            span.set_attribute(key, value)

        # Add link count as attribute for observability
        if otel_links:
            span.set_attribute("span.link_count", len(otel_links))

        return span  # type: ignore[no-any-return,return-value]
    except ImportError:
        # Return no-op span
        return _NoOpSpan()


@contextmanager
def trace_span_with_links(
    name: str,
    links: list[SpanLinkContext | dict[str, str] | None] | None = None,
    record_exception_on_error: bool = True,
    **attributes: str | int | float | bool,
) -> Iterator[SpanProtocol]:
    """Context manager for creating a span with links to related spans.

    Combines the convenience of trace_span with the ability to link to
    parent operations from async contexts.

    Args:
        name: Name of the span
        links: List of SpanLinkContext objects or dicts with trace_id/span_id
        record_exception_on_error: If True, automatically record exceptions
        **attributes: Key-value pairs to set as span attributes

    Yields:
        The created span

    Example:
        >>> from backend.core.telemetry import trace_span_with_links
        >>> # In batch analyzer
        >>> with trace_span_with_links(
        ...     "analyze_batch",
        ...     links=detection_contexts,
        ...     batch_id=batch_id,
        ... ) as span:
        ...     result = await analyzer.analyze(batch)
        ...     span.set_attribute("risk_score", result.risk_score)
    """
    _tracer = get_tracer("span_links")

    # Convert links to OpenTelemetry Link objects if OTEL is available
    otel_links: list[object] = []
    if links:
        try:
            from opentelemetry.trace import Link, SpanContext, TraceFlags

            for link in links:
                if link is None:
                    continue

                # Handle dict or SpanLinkContext
                if isinstance(link, dict):
                    link_ctx = SpanLinkContext.from_dict(link)
                else:
                    link_ctx = link

                if link_ctx:
                    try:
                        trace_id_int = int(link_ctx.trace_id, 16)
                        span_id_int = int(link_ctx.span_id, 16)
                        span_context = SpanContext(
                            trace_id=trace_id_int,
                            span_id=span_id_int,
                            is_remote=True,
                            trace_flags=TraceFlags(0x01),
                        )
                        otel_links.append(Link(span_context))
                    except (ValueError, TypeError):
                        continue
        except ImportError:
            # OpenTelemetry not available, keep empty list
            pass

    # Start span with links
    try:
        from opentelemetry import trace as otel_trace

        tracer_impl = otel_trace.get_tracer("span_links")
        span = tracer_impl.start_as_current_span(name, links=otel_links)  # type: ignore[arg-type]

        with span as s:
            # Set attributes
            for key, value in attributes.items():
                s.set_attribute(key, value)

            # Add link count
            if otel_links:
                s.set_attribute("span.link_count", len(otel_links))

            try:
                yield s  # type: ignore[misc]
            except Exception as e:
                if record_exception_on_error:
                    record_exception(e)
                raise
    except ImportError:
        # Fallback to regular trace_span
        with trace_span(
            name, record_exception_on_error=record_exception_on_error, **attributes
        ) as s:
            yield s


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

    def add_event(
        self,
        name: str,
        attributes: dict[str, object] | None = None,
        timestamp: int | None = None,
    ) -> None:
        """No-op add_event for span events (NEM-3434)."""

    def get_span_context(self) -> None:
        """No-op get_span_context, returns None."""
        return None

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
# OpenTelemetry Baggage for Cross-Service Context (NEM-3382)
# =============================================================================


def set_baggage(key: str, value: str) -> None:
    """Set a baggage entry in the current context.

    Baggage is used to propagate application-specific context across service
    boundaries. Unlike span attributes (which are per-span), baggage entries
    are propagated to all downstream services automatically.

    Common use cases:
    - request_id: Correlate requests across services
    - camera_id: Track which camera originated a detection
    - user_id: Track user context for debugging (if applicable)
    - batch_id: Correlate detections within a batch

    Args:
        key: The baggage key (e.g., "request_id", "camera_id")
        value: The baggage value (must be a string)

    Example:
        >>> from backend.core.telemetry import set_baggage
        >>> set_baggage("camera_id", "front_door")
        >>> set_baggage("batch_id", "batch-12345")
    """
    try:
        from opentelemetry import baggage, context

        ctx = baggage.set_baggage(key, value)
        context.attach(ctx)
    except ImportError:
        # OpenTelemetry not installed, silently ignore
        pass
    except Exception as e:
        logger.debug("Failed to set baggage %s: %s", key, e)


def get_baggage(key: str) -> str | None:
    """Get a baggage entry from the current context.

    Args:
        key: The baggage key to retrieve

    Returns:
        The baggage value if set, None otherwise.

    Example:
        >>> from backend.core.telemetry import get_baggage
        >>> camera_id = get_baggage("camera_id")
    """
    try:
        from opentelemetry import baggage

        value = baggage.get_baggage(key)
        # OpenTelemetry baggage values are always strings when set
        return str(value) if value is not None else None
    except ImportError:
        return None
    except Exception as e:
        logger.debug("Failed to get baggage %s: %s", key, e)
        return None


def get_all_baggage() -> dict[str, str]:
    """Get all baggage entries from the current context.

    Returns:
        Dictionary of all baggage key-value pairs.

    Example:
        >>> from backend.core.telemetry import get_all_baggage
        >>> all_baggage = get_all_baggage()
        >>> # {'camera_id': 'front_door', 'batch_id': 'batch-12345'}
    """
    try:
        from opentelemetry import baggage

        # OpenTelemetry baggage values are always strings when set
        return {k: str(v) for k, v in baggage.get_all().items()}
    except ImportError:
        return {}
    except Exception as e:
        logger.debug("Failed to get all baggage: %s", e)
        return {}


def clear_baggage(key: str) -> None:
    """Remove a baggage entry from the current context.

    Args:
        key: The baggage key to remove

    Example:
        >>> from backend.core.telemetry import clear_baggage
        >>> clear_baggage("camera_id")
    """
    try:
        from opentelemetry import baggage, context

        ctx = baggage.remove_baggage(key)
        context.attach(ctx)
    except ImportError:
        pass
    except Exception as e:
        logger.debug("Failed to clear baggage %s: %s", key, e)


def set_request_baggage(
    *,
    request_id: str | None = None,
    correlation_id: str | None = None,
    camera_id: str | None = None,
    batch_id: str | None = None,
) -> None:
    """Set common request-related baggage entries for cross-service propagation.

    This is a convenience function for setting multiple baggage entries
    commonly used in the detection pipeline.

    Args:
        request_id: The request ID for correlation
        correlation_id: The correlation ID for distributed tracing
        camera_id: The camera identifier
        batch_id: The batch identifier

    Example:
        >>> from backend.core.telemetry import set_request_baggage
        >>> set_request_baggage(
        ...     request_id="req-123",
        ...     camera_id="front_door",
        ...     batch_id="batch-456"
        ... )
    """
    if request_id:
        set_baggage("request_id", request_id)
    if correlation_id:
        set_baggage("correlation_id", correlation_id)
    if camera_id:
        set_baggage("camera_id", camera_id)
    if batch_id:
        set_baggage("batch_id", batch_id)


def extract_context_from_headers(headers: dict[str, str]) -> None:
    """Extract trace context and baggage from incoming HTTP headers.

    This function should be called when receiving requests from upstream services
    to restore the trace context and baggage. It uses the composite propagator
    configured in setup_telemetry.

    Args:
        headers: Dictionary of HTTP headers from the incoming request

    Example:
        >>> from backend.core.telemetry import extract_context_from_headers
        >>> # In your request handler
        >>> headers = dict(request.headers)
        >>> extract_context_from_headers(headers)
        >>> # Now trace context and baggage are restored
        >>> camera_id = get_baggage("camera_id")
    """
    try:
        from opentelemetry import context
        from opentelemetry.propagate import extract

        ctx = extract(headers)
        context.attach(ctx)
    except ImportError:
        pass
    except Exception as e:
        logger.debug("Failed to extract context from headers: %s", e)


# =============================================================================
# W3C Trace Context Propagation (NEM-3147)
# =============================================================================


def get_trace_headers() -> dict[str, str]:
    """Get W3C Trace Context and Baggage headers for propagation to downstream services.

    This function extracts the current trace context and baggage, returning HTTP
    headers that can be included in outgoing requests to propagate both trace
    information and application context across service boundaries.

    Headers included:
    - traceparent: W3C Trace Context parent header (OpenTelemetry)
    - tracestate: W3C Trace Context state header (OpenTelemetry)
    - baggage: W3C Baggage header for cross-service context (NEM-3382)

    When OpenTelemetry is enabled, this uses the composite propagator that
    includes both W3CTraceContextPropagator and W3CBaggagePropagator.
    When disabled, returns an empty dict (no-op).

    Returns:
        Dictionary with traceparent, tracestate, and baggage headers if active,
        empty dict otherwise.

    Example:
        >>> from backend.core.telemetry import get_trace_headers
        >>> headers = {"Content-Type": "application/json"}
        >>> headers.update(get_trace_headers())
        >>> # headers now contains traceparent, tracestate, and baggage if active
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
        >>> @trace_function("yolo26_detection")
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

    This is optimized for AI service calls (YOLO26, Nemotron, Florence, CLIP, etc.)
    and includes attributes that help correlate circuit breaker events with traces.

    Args:
        service_name: Name of the AI service (e.g., "yolo26", "nemotron", "florence")
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


@contextmanager
def profile_with_trace_context() -> Iterator[None]:
    """Tag profiling data with current trace ID for correlation.

    This context manager tags Pyroscope profiling data with the current
    OpenTelemetry trace_id and span_id. This enables correlation between
    profiles and distributed traces, allowing you to view the exact CPU
    profile for a specific slow request.

    Use cases:
    - Debugging slow requests by viewing their exact profiles
    - Correlating performance bottlenecks with specific traces
    - Root cause analysis combining tracing and profiling data

    The function gracefully handles:
    - No active trace (yields without tagging)
    - Pyroscope not installed (yields without tagging)
    - Invalid span context (yields without tagging)

    Example:
        >>> from backend.core.telemetry import profile_with_trace_context
        >>> with profile_with_trace_context():
        ...     # Code here will have profiling data tagged with trace context
        ...     process_request()

    NEM-4127: Added for profile-to-trace correlation in observability stack.
    """
    # Try to get trace context and pyroscope tag_wrapper
    tag_wrapper_ctx = None

    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        span_context = span.get_span_context()

        if span_context.is_valid:
            trace_id = format(span_context.trace_id, "032x")
            span_id = format(span_context.span_id, "016x")

            try:
                import pyroscope

                tag_wrapper_ctx = pyroscope.tag_wrapper({"trace_id": trace_id, "span_id": span_id})
            except ImportError:
                # Pyroscope not installed, continue without tagging
                pass
    except ImportError:
        # OpenTelemetry not installed, continue without tagging
        pass
    except Exception as e:
        # Log but don't fail on unexpected errors
        logger.debug(f"Failed to tag profiling with trace context: {e}")

    # Single yield point with optional tag wrapper
    if tag_wrapper_ctx is not None:
        with tag_wrapper_ctx:
            yield
    else:
        yield


def init_profiling() -> None:
    """Initialize Pyroscope continuous profiling for backend service.

    This function configures Pyroscope for continuous profiling of the backend
    service. It enables CPU, GIL, and memory allocation profiling to identify
    performance bottlenecks in both synchronous and asynchronous code paths.

    Configuration is via environment variables:
    - PYROSCOPE_ENABLED: Enable/disable profiling (default: true)
    - PYROSCOPE_URL: Pyroscope server address (default: http://pyroscope:4040)
      (PYROSCOPE_SERVER is also accepted for backward compatibility)
    - PYROSCOPE_SAMPLE_RATE: Profiling sample rate in Hz (default: 100)
    - PYROSCOPE_MEMORY_ENABLED: Enable memory allocation profiling (default: true)
    - ENVIRONMENT: Environment tag for profiles (default: production)

    The function gracefully handles:
    - Missing pyroscope-io package (ImportError)
    - Unsupported Python versions (pyroscope-io native lib requires Python 3.9-3.12)
    - Configuration errors (logs warning, doesn't fail startup)

    Compatibility Notes (NEM-3514):
        The "unknown profile type: seconds" error was caused by a server-side bug
        in Pyroscope's Speedscope profile type handling. Requirements:
        - pyroscope-io SDK >= 0.8.7 (pyproject.toml specifies >=0.8.7)
        - Pyroscope server >= 1.9.2 (docker-compose.prod.yml uses 1.18.0)
        Fix: https://github.com/grafana/pyroscope/pull/4568

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

        # Support both PYROSCOPE_URL (docker-compose standard) and PYROSCOPE_SERVER (legacy)
        pyroscope_server = os.getenv("PYROSCOPE_URL") or os.getenv(
            "PYROSCOPE_SERVER", "http://pyroscope:4040"
        )

        # Get sample rate from environment (default: 100 Hz)
        # Higher values = more detail but higher overhead
        sample_rate = int(os.getenv("PYROSCOPE_SAMPLE_RATE", "100"))

        # Memory profiling: captures alloc_objects and alloc_space data
        # Enabled by default for comprehensive memory leak detection
        memory_profiling = os.getenv("PYROSCOPE_MEMORY_ENABLED", "true").lower() == "true"

        pyroscope.configure(
            application_name="nemotron-backend",
            server_address=pyroscope_server,
            sample_rate=sample_rate,
            tags={
                "service": "backend",
                "environment": os.getenv("ENVIRONMENT", "development"),
            },
            oncpu=True,
            gil_only=False,  # Profile all threads, not just GIL-holding threads
            enable_logging=True,
            # Memory allocation profiling (NEM-4126)
            # Captures alloc_objects (allocation count) and alloc_space (bytes allocated)
            alloc_objects=memory_profiling,
            alloc_space=memory_profiling,
        )
        logger.info(
            f"Pyroscope profiling initialized: server={pyroscope_server}, "
            f"sample_rate={sample_rate}Hz, memory_profiling={memory_profiling}"
        )
    except ImportError:
        # pyroscope-io not installed, skip profiling
        logger.debug("Pyroscope profiling skipped: pyroscope-io not installed")
    except Exception as e:
        # Log but don't fail if profiling setup fails
        logger.warning(f"Failed to initialize Pyroscope profiling: {e}")
