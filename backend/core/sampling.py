"""Priority-based trace sampling for OpenTelemetry.

NEM-3793: Implements intelligent trace sampling that reduces telemetry volume
while preserving important traces based on priority rules.

Sampling Strategy:
1. Error traces: Always sample (100%) - critical for debugging
2. High-risk events: Always sample (100%) - security-relevant traces
3. High-priority API endpoints: Always sample (100%) - events, alerts, detections
4. Medium-priority endpoints: Configurable rate (default 50%)
5. Background tasks: Lower sample rate (default 10-20%)
6. Default: Configurable base rate (default 10%)

Configuration via environment variables:
- OTEL_SAMPLING_ERROR_RATE: Error trace sampling rate (default: 1.0)
- OTEL_SAMPLING_HIGH_RISK_RATE: High-risk event sampling rate (default: 1.0)
- OTEL_SAMPLING_HIGH_PRIORITY_RATE: High-priority endpoint rate (default: 1.0)
- OTEL_SAMPLING_MEDIUM_PRIORITY_RATE: Medium-priority endpoint rate (default: 0.5)
- OTEL_SAMPLING_BACKGROUND_RATE: Background task rate (default: 0.1)
- OTEL_SAMPLING_DEFAULT_RATE: Default sampling rate (default: 0.1)
- OTEL_SAMPLING_HIGH_PRIORITY_PATHS: Comma-separated high-priority paths
- OTEL_SAMPLING_MEDIUM_PRIORITY_PATHS: Comma-separated medium-priority paths
- OTEL_SAMPLING_BACKGROUND_PATHS: Comma-separated background task paths

Usage:
    from backend.core.sampling import PriorityBasedSampler, create_priority_sampler
    from backend.core.config import Settings

    settings = Settings()
    sampler = create_priority_sampler(settings)
    provider = TracerProvider(resource=resource, sampler=sampler)
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from opentelemetry.context import Context
    from opentelemetry.trace import Link, SpanKind
    from opentelemetry.util.types import Attributes

    from backend.core.config import Settings

logger = logging.getLogger(__name__)


# Default high-priority paths (security-critical endpoints)
DEFAULT_HIGH_PRIORITY_PATHS: list[str] = [
    "/api/events",
    "/api/alerts",
    "/api/detections",
    "/api/cameras",
    "/api/analysis",
]

# Default medium-priority paths (important but less critical)
DEFAULT_MEDIUM_PRIORITY_PATHS: list[str] = [
    "/api/timeline",
    "/api/system",
    "/api/settings",
    "/api/household",
    "/api/notifications",
]

# Default background task paths (internal operations)
DEFAULT_BACKGROUND_PATHS: list[str] = [
    "/api/health",
    "/health",
    "/metrics",
    "/api/debug",
    "/_internal",
]


class SamplingConfig:
    """Configuration for priority-based sampling.

    Provides configurable sampling rates and path classifications that can be
    set via environment variables or programmatically.
    """

    def __init__(
        self,
        *,
        error_rate: float = 1.0,
        high_risk_rate: float = 1.0,
        high_priority_rate: float = 1.0,
        medium_priority_rate: float = 0.5,
        background_rate: float = 0.1,
        default_rate: float = 0.1,
        high_priority_paths: list[str] | None = None,
        medium_priority_paths: list[str] | None = None,
        background_paths: list[str] | None = None,
    ) -> None:
        """Initialize sampling configuration.

        Args:
            error_rate: Sampling rate for error traces (0.0-1.0, default 1.0)
            high_risk_rate: Sampling rate for high-risk events (0.0-1.0, default 1.0)
            high_priority_rate: Sampling rate for high-priority endpoints (0.0-1.0, default 1.0)
            medium_priority_rate: Sampling rate for medium-priority endpoints (0.0-1.0, default 0.5)
            background_rate: Sampling rate for background tasks (0.0-1.0, default 0.1)
            default_rate: Default sampling rate for unclassified spans (0.0-1.0, default 0.1)
            high_priority_paths: List of high-priority API paths
            medium_priority_paths: List of medium-priority API paths
            background_paths: List of background task paths
        """
        # Validate and clamp rates to [0.0, 1.0]
        self.error_rate = max(0.0, min(1.0, error_rate))
        self.high_risk_rate = max(0.0, min(1.0, high_risk_rate))
        self.high_priority_rate = max(0.0, min(1.0, high_priority_rate))
        self.medium_priority_rate = max(0.0, min(1.0, medium_priority_rate))
        self.background_rate = max(0.0, min(1.0, background_rate))
        self.default_rate = max(0.0, min(1.0, default_rate))

        # Path classifications
        self.high_priority_paths = high_priority_paths or DEFAULT_HIGH_PRIORITY_PATHS.copy()
        self.medium_priority_paths = medium_priority_paths or DEFAULT_MEDIUM_PRIORITY_PATHS.copy()
        self.background_paths = background_paths or DEFAULT_BACKGROUND_PATHS.copy()

    @classmethod
    def from_env(cls) -> SamplingConfig:
        """Create SamplingConfig from environment variables.

        Environment variables:
            OTEL_SAMPLING_ERROR_RATE: Error trace sampling rate
            OTEL_SAMPLING_HIGH_RISK_RATE: High-risk event sampling rate
            OTEL_SAMPLING_HIGH_PRIORITY_RATE: High-priority endpoint rate
            OTEL_SAMPLING_MEDIUM_PRIORITY_RATE: Medium-priority endpoint rate
            OTEL_SAMPLING_BACKGROUND_RATE: Background task rate
            OTEL_SAMPLING_DEFAULT_RATE: Default sampling rate
            OTEL_SAMPLING_HIGH_PRIORITY_PATHS: Comma-separated paths
            OTEL_SAMPLING_MEDIUM_PRIORITY_PATHS: Comma-separated paths
            OTEL_SAMPLING_BACKGROUND_PATHS: Comma-separated paths

        Returns:
            SamplingConfig instance configured from environment
        """

        def get_rate(key: str, default: float) -> float:
            """Get sampling rate from environment with validation."""
            value = os.getenv(key)
            if value is None:
                return default
            try:
                return float(value)
            except ValueError:
                logger.warning(
                    "Invalid sampling rate for %s: %s, using default %f", key, value, default
                )
                return default

        def get_paths(key: str, default: list[str]) -> list[str]:
            """Get path list from environment."""
            value = os.getenv(key)
            if value is None:
                return default
            # Parse comma-separated paths, strip whitespace
            paths = [p.strip() for p in value.split(",") if p.strip()]
            return paths if paths else default

        return cls(
            error_rate=get_rate("OTEL_SAMPLING_ERROR_RATE", 1.0),
            high_risk_rate=get_rate("OTEL_SAMPLING_HIGH_RISK_RATE", 1.0),
            high_priority_rate=get_rate("OTEL_SAMPLING_HIGH_PRIORITY_RATE", 1.0),
            medium_priority_rate=get_rate("OTEL_SAMPLING_MEDIUM_PRIORITY_RATE", 0.5),
            background_rate=get_rate("OTEL_SAMPLING_BACKGROUND_RATE", 0.1),
            default_rate=get_rate("OTEL_SAMPLING_DEFAULT_RATE", 0.1),
            high_priority_paths=get_paths(
                "OTEL_SAMPLING_HIGH_PRIORITY_PATHS", DEFAULT_HIGH_PRIORITY_PATHS.copy()
            ),
            medium_priority_paths=get_paths(
                "OTEL_SAMPLING_MEDIUM_PRIORITY_PATHS", DEFAULT_MEDIUM_PRIORITY_PATHS.copy()
            ),
            background_paths=get_paths(
                "OTEL_SAMPLING_BACKGROUND_PATHS", DEFAULT_BACKGROUND_PATHS.copy()
            ),
        )


class PriorityBasedSampler:
    """Priority-based trace sampler for OpenTelemetry.

    This sampler implements intelligent sampling decisions based on trace priority:
    - Error traces are always sampled for debugging
    - High-risk security events are always sampled
    - API endpoints are sampled based on their importance
    - Background tasks have lower sampling rates to reduce noise

    The sampler respects parent span decisions for trace consistency:
    - If parent is sampled, child is always sampled (preserves complete traces)
    - If parent is not sampled, child follows parent (consistent decisions)
    - Root spans use priority-based sampling logic
    """

    def __init__(self, config: SamplingConfig | None = None) -> None:
        """Initialize the priority-based sampler.

        Args:
            config: Sampling configuration. If None, loads from environment.
        """
        self.config = config or SamplingConfig.from_env()
        self._description = (
            f"PriorityBasedSampler(error={self.config.error_rate}, "
            f"high_risk={self.config.high_risk_rate}, "
            f"high_priority={self.config.high_priority_rate}, "
            f"medium_priority={self.config.medium_priority_rate}, "
            f"background={self.config.background_rate}, "
            f"default={self.config.default_rate})"
        )

    def should_sample(
        self,
        parent_context: Context | None,  # noqa: ARG002 - required by interface
        trace_id: int,
        name: str,
        kind: SpanKind | None = None,  # noqa: ARG002 - required by interface
        attributes: Attributes | None = None,
        links: list[Link] | None = None,  # noqa: ARG002 - required by interface
    ) -> tuple[Any, dict[str, Any]]:
        """Determine if a span should be sampled based on priority rules.

        Args:
            parent_context: Parent span context (may contain sampling decision)
            trace_id: Unique trace identifier
            name: Span name (e.g., "GET /api/events")
            kind: Span kind (CLIENT, SERVER, INTERNAL, etc.)
            attributes: Span attributes containing metadata
            links: Links to other spans

        Returns:
            Tuple of (SamplingDecision, attributes dict)
        """
        from opentelemetry.sdk.trace.sampling import Decision

        # Convert attributes to dict for easier access
        attrs = dict(attributes) if attributes else {}

        # Determine sampling rate based on priority
        rate = self._get_sampling_rate(name, attrs)

        # Make sampling decision based on rate
        # Use trace_id for deterministic sampling (same trace always gets same decision)
        threshold = int(rate * (2**64 - 1))
        sample = (trace_id & 0xFFFFFFFFFFFFFFFF) < threshold

        if sample:
            # Add sampling metadata as span attributes
            sampling_attrs = {
                "sampling.rate": rate,
                "sampling.priority": self._get_priority_name(name, attrs),
            }
            return Decision.RECORD_AND_SAMPLE, sampling_attrs
        else:
            return Decision.DROP, {}

    def _get_sampling_rate(self, name: str, attrs: dict[str, Any]) -> float:
        """Determine the sampling rate based on span characteristics.

        Args:
            name: Span name
            attrs: Span attributes

        Returns:
            Sampling rate between 0.0 and 1.0
        """
        # 1. Always sample error traces (highest priority)
        if self._is_error_trace(attrs):
            return self.config.error_rate

        # 2. Always sample high-risk security events
        if self._is_high_risk_event(attrs):
            return self.config.high_risk_rate

        # 3. Check path-based priority
        path = self._extract_path(name, attrs)

        # High-priority paths (events, alerts, detections)
        if self._matches_paths(path, self.config.high_priority_paths):
            return self.config.high_priority_rate

        # Medium-priority paths (timeline, system, settings)
        if self._matches_paths(path, self.config.medium_priority_paths):
            return self.config.medium_priority_rate

        # Background tasks (health checks, metrics)
        if self._matches_paths(path, self.config.background_paths):
            return self.config.background_rate

        # Default rate for unclassified spans
        return self.config.default_rate

    def _get_priority_name(self, name: str, attrs: dict[str, Any]) -> str:
        """Get the priority classification name for a span.

        Args:
            name: Span name
            attrs: Span attributes

        Returns:
            Priority classification name
        """
        if self._is_error_trace(attrs):
            return "error"
        if self._is_high_risk_event(attrs):
            return "high_risk"

        path = self._extract_path(name, attrs)
        if self._matches_paths(path, self.config.high_priority_paths):
            return "high_priority"
        if self._matches_paths(path, self.config.medium_priority_paths):
            return "medium_priority"
        if self._matches_paths(path, self.config.background_paths):
            return "background"

        return "default"

    def _is_error_trace(self, attrs: dict[str, Any]) -> bool:
        """Check if this is an error trace that should always be sampled.

        Args:
            attrs: Span attributes

        Returns:
            True if this is an error trace
        """
        # Check common error indicators
        if attrs.get("error"):
            return True
        if attrs.get("otel.status_code") == "ERROR":
            return True
        if attrs.get("http.status_code", 0) >= 500:
            return True
        return bool(attrs.get("exception.type"))

    def _is_high_risk_event(self, attrs: dict[str, Any]) -> bool:
        """Check if this is a high-risk security event.

        High-risk events include:
        - Events with high risk scores (>= 70)
        - Alert-related operations
        - Security-critical detections

        Args:
            attrs: Span attributes

        Returns:
            True if this is a high-risk event
        """
        # Check risk score from detection/analysis
        risk_score = attrs.get("risk_score") or attrs.get("event.risk_score", 0)
        if isinstance(risk_score, int | float) and risk_score >= 70:
            return True

        # Check for alert indicators
        if attrs.get("alert.created") or attrs.get("alert.triggered"):
            return True

        # Check for security-critical operations
        operation = attrs.get("ai.operation", "")
        return operation in ["analyze", "detect", "alert"]

    def _extract_path(self, name: str, attrs: dict[str, Any]) -> str:
        """Extract the API path from span name or attributes.

        Args:
            name: Span name (may contain path like "GET /api/events")
            attrs: Span attributes (may contain http.route or http.target)

        Returns:
            Extracted path or empty string
        """
        # Check attributes first (more reliable)
        path = attrs.get("http.route") or attrs.get("http.target") or attrs.get("url.path", "")
        if path:
            # Remove query string if present
            return str(path).split("?")[0]

        # Extract from span name (e.g., "GET /api/events" -> "/api/events")
        parts = name.split(" ", 1)
        if len(parts) > 1 and parts[0] in ("GET", "POST", "PUT", "DELETE", "PATCH"):
            return parts[1].split("?")[0]

        return name

    def _matches_paths(self, path: str, patterns: list[str]) -> bool:
        """Check if a path matches any of the priority patterns.

        Uses prefix matching to support path hierarchies.

        Args:
            path: The path to check
            patterns: List of path patterns to match against

        Returns:
            True if path matches any pattern
        """
        if not path:
            return False

        for pattern in patterns:
            # Exact match or prefix match (for hierarchical paths)
            if path == pattern or path.startswith(pattern + "/"):
                return True
            # Also match if the pattern is a prefix of the path
            if path.startswith(pattern):
                return True

        return False

    def get_description(self) -> str:
        """Get a human-readable description of this sampler.

        Returns:
            Description string
        """
        return self._description


class ParentBasedPrioritySampler:
    """Parent-based sampler wrapper that respects parent decisions.

    This sampler combines parent-based sampling with priority-based root sampling:
    - If there's a sampled parent, always sample the child
    - If there's a non-sampled parent, don't sample the child
    - For root spans (no parent), use priority-based sampling

    This ensures trace consistency while applying intelligent sampling to new traces.
    """

    def __init__(self, root_sampler: PriorityBasedSampler) -> None:
        """Initialize the parent-based priority sampler.

        Args:
            root_sampler: Sampler to use for root spans (no parent)
        """
        self.root_sampler = root_sampler
        self._description = f"ParentBasedPrioritySampler({root_sampler.get_description()})"

    def should_sample(
        self,
        parent_context: Context | None,
        trace_id: int,
        name: str,
        kind: SpanKind | None = None,
        attributes: Attributes | None = None,
        links: list[Link] | None = None,
    ) -> tuple[Any, dict[str, Any]]:
        """Determine if a span should be sampled.

        Args:
            parent_context: Parent span context
            trace_id: Unique trace identifier
            name: Span name
            kind: Span kind
            attributes: Span attributes
            links: Links to other spans

        Returns:
            Tuple of (SamplingDecision, attributes dict)
        """
        from opentelemetry import trace
        from opentelemetry.sdk.trace.sampling import Decision

        # Check for parent span
        parent_span_context = None
        if parent_context is not None:
            parent_span_context = trace.get_current_span(parent_context).get_span_context()

        # If parent exists and has valid trace flags
        if parent_span_context is not None and parent_span_context.is_valid:
            # Check if parent is sampled
            if parent_span_context.trace_flags.sampled:
                return Decision.RECORD_AND_SAMPLE, {"sampling.inherited": True}
            else:
                return Decision.DROP, {}

        # No parent (root span) - use priority-based sampling
        return self.root_sampler.should_sample(
            parent_context, trace_id, name, kind, attributes, links
        )

    def get_description(self) -> str:
        """Get a human-readable description of this sampler.

        Returns:
            Description string
        """
        return self._description


def create_priority_sampler(settings: Settings | None = None) -> Any:
    """Create a configured priority-based sampler.

    This function creates a ParentBasedPrioritySampler that:
    1. Respects parent span sampling decisions for trace consistency
    2. Uses priority-based sampling for root spans
    3. Is configurable via environment variables or Settings

    Args:
        settings: Optional Settings instance. If None, loads from environment.

    Returns:
        Configured sampler instance ready for use with TracerProvider
    """
    # Create configuration, preferring Settings if available
    if settings is not None:
        config = SamplingConfig(
            error_rate=settings.otel_sampling_error_rate,
            high_risk_rate=settings.otel_sampling_high_risk_rate,
            high_priority_rate=settings.otel_sampling_high_priority_rate,
            medium_priority_rate=settings.otel_sampling_medium_priority_rate,
            background_rate=settings.otel_sampling_background_rate,
            default_rate=settings.otel_sampling_default_rate,
            # Use environment variables for paths (not in Settings to keep it simple)
        )

        # Apply otel_trace_sample_rate as a global scaling factor
        # This maintains backward compatibility with existing configuration
        base_rate = settings.otel_trace_sample_rate
        if base_rate < 1.0:
            config.default_rate = min(config.default_rate, base_rate)
            config.background_rate = min(config.background_rate, base_rate)
            config.medium_priority_rate = min(config.medium_priority_rate, base_rate)
    else:
        # Load from environment variables
        config = SamplingConfig.from_env()

    # Create the priority sampler
    priority_sampler = PriorityBasedSampler(config)

    # Wrap in parent-based sampler for trace consistency
    return ParentBasedPrioritySampler(priority_sampler)


def create_otel_sampler(settings: Settings | None = None) -> Any:
    """Create an OpenTelemetry-compatible sampler using the SDK's Sampler base class.

    This function creates a proper OpenTelemetry SDK sampler that integrates
    with the TracerProvider. It wraps the priority-based logic in the
    required OpenTelemetry Sampler interface.

    Args:
        settings: Optional Settings instance. If None, loads from environment.

    Returns:
        OpenTelemetry SDK Sampler instance
    """
    try:
        from opentelemetry.sdk.trace.sampling import (
            ALWAYS_OFF,
            ALWAYS_ON,
            ParentBased,
            Sampler,
            SamplingResult,
        )

        # Create configuration, preferring Settings if available
        if settings is not None:
            config = SamplingConfig(
                error_rate=settings.otel_sampling_error_rate,
                high_risk_rate=settings.otel_sampling_high_risk_rate,
                high_priority_rate=settings.otel_sampling_high_priority_rate,
                medium_priority_rate=settings.otel_sampling_medium_priority_rate,
                background_rate=settings.otel_sampling_background_rate,
                default_rate=settings.otel_sampling_default_rate,
            )

            # Apply otel_trace_sample_rate as a global scaling factor
            base_rate = settings.otel_trace_sample_rate
            if base_rate < 1.0:
                config.default_rate = min(config.default_rate, base_rate)
                config.background_rate = min(config.background_rate, base_rate)
                config.medium_priority_rate = min(config.medium_priority_rate, base_rate)
        else:
            config = SamplingConfig.from_env()

        class _PrioritySampler(Sampler):
            """Internal OpenTelemetry Sampler implementation using priority rules."""

            def __init__(self, sampling_config: SamplingConfig) -> None:
                self._config = sampling_config
                self._priority_sampler = PriorityBasedSampler(sampling_config)

            def should_sample(
                self,
                parent_context: Any,
                trace_id: int,
                name: str,
                kind: Any = None,
                attributes: Any = None,
                links: Any = None,
                trace_state: Any = None,  # noqa: ARG002 - required by SDK interface
            ) -> SamplingResult:
                """Make sampling decision using priority rules."""
                from opentelemetry.sdk.trace.sampling import Decision

                decision, attrs = self._priority_sampler.should_sample(
                    parent_context, trace_id, name, kind, attributes, links
                )

                # Convert Decision to TraceFlags
                if decision == Decision.RECORD_AND_SAMPLE:
                    return SamplingResult(
                        decision=Decision.RECORD_AND_SAMPLE,
                        attributes=attrs,
                        trace_state=None,
                    )
                else:
                    return SamplingResult(
                        decision=Decision.DROP,
                        attributes=None,
                        trace_state=None,
                    )

            def get_description(self) -> str:
                return self._priority_sampler.get_description()

        # Create the priority sampler
        priority_sampler = _PrioritySampler(config)

        # Wrap in ParentBased for proper parent context handling
        # This uses OpenTelemetry's ParentBased which properly handles:
        # - Local parent sampled: always sample
        # - Local parent not sampled: always drop
        # - Remote parent sampled: always sample
        # - Remote parent not sampled: always drop
        # - No parent (root): use our priority sampler
        return ParentBased(
            root=priority_sampler,
            local_parent_sampled=ALWAYS_ON,
            local_parent_not_sampled=ALWAYS_OFF,
            remote_parent_sampled=ALWAYS_ON,
            remote_parent_not_sampled=ALWAYS_OFF,
        )

    except ImportError:
        logger.warning("OpenTelemetry SDK not available, returning None for sampler")
        return None
