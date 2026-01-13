"""AI service fallback strategies for graceful degradation.

This module provides fallback behavior when AI services (RT-DETRv2, Nemotron,
Florence-2, CLIP) become unavailable. It integrates with circuit breakers
and the degradation manager to provide seamless degradation.

Features:
    - Per-service fallback strategies
    - Cached result retrieval
    - Default value generation
    - Health-based routing
    - WebSocket status broadcasting

Usage:
    fallback = get_ai_fallback_service()

    # Check service availability
    if fallback.is_service_available("nemotron"):
        result = await analyzer.analyze(detection)
    else:
        result = await fallback.get_fallback_risk_analysis(detection)

    # Get overall degradation status
    status = fallback.get_degradation_status()
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from backend.core.logging import get_logger
from backend.services.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
)

if TYPE_CHECKING:
    from backend.services.clip_client import CLIPClient
    from backend.services.detector_client import DetectorClient
    from backend.services.florence_client import FlorenceClient
    from backend.services.nemotron_analyzer import NemotronAnalyzer

logger = get_logger(__name__)


class AIService(StrEnum):
    """AI service identifiers."""

    RTDETR = "rtdetr"
    NEMOTRON = "nemotron"
    FLORENCE = "florence"
    CLIP = "clip"


class DegradationLevel(StrEnum):
    """System degradation levels based on AI service availability."""

    NORMAL = "normal"  # All services healthy
    DEGRADED = "degraded"  # Non-critical services down
    MINIMAL = "minimal"  # Critical services partially available
    OFFLINE = "offline"  # All AI services down


class ServiceStatus(StrEnum):
    """Individual service status."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


@dataclass(slots=True)
class ServiceState:
    """State information for a single AI service.

    Attributes:
        service: Service identifier
        status: Current service status
        circuit_state: Circuit breaker state
        last_success: Timestamp of last successful call
        failure_count: Consecutive failure count
        error_message: Last error message if any
        last_check: Timestamp of last health check
    """

    service: AIService
    status: ServiceStatus = ServiceStatus.HEALTHY
    circuit_state: CircuitState = CircuitState.CLOSED
    last_success: datetime | None = None
    failure_count: int = 0
    error_message: str | None = None
    last_check: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "service": self.service.value,
            "status": self.status.value,
            "circuit_state": self.circuit_state.value,
            "last_success": self.last_success.isoformat() if self.last_success else None,
            "failure_count": self.failure_count,
            "error_message": self.error_message,
            "last_check": self.last_check.isoformat() if self.last_check else None,
        }


@dataclass(slots=True)
class FallbackRiskAnalysis:
    """Fallback risk analysis result when Nemotron is unavailable.

    Attributes:
        risk_score: Default or cached risk score (0-100)
        reasoning: Explanation of the fallback
        is_fallback: Always True for fallback results
        source: Source of the fallback value
    """

    risk_score: int
    reasoning: str
    is_fallback: bool = True
    source: str = "default"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "risk_score": self.risk_score,
            "reasoning": self.reasoning,
            "is_fallback": self.is_fallback,
            "source": self.source,
        }


@dataclass(slots=True)
class RiskScoreCache:
    """Cache for risk score patterns.

    Attributes:
        camera_scores: Last known risk scores per camera
        object_type_scores: Default scores by object type
        ttl_seconds: Cache TTL in seconds
    """

    camera_scores: dict[str, int] = field(default_factory=dict)
    object_type_scores: dict[str, int] = field(
        default_factory=lambda: {
            "person": 60,
            "vehicle": 50,
            "car": 50,
            "truck": 55,
            "motorcycle": 45,
            "bicycle": 30,
            "dog": 25,
            "cat": 20,
            "bird": 10,
            "unknown": 50,
        }
    )
    ttl_seconds: int = 300
    _timestamps: dict[str, float] = field(default_factory=dict)

    def get_cached_score(self, camera_name: str) -> int | None:
        """Get cached score if still valid."""
        if camera_name not in self.camera_scores:
            return None
        timestamp = self._timestamps.get(camera_name, 0)
        if time.monotonic() - timestamp > self.ttl_seconds:
            return None
        return self.camera_scores[camera_name]

    def set_cached_score(self, camera_name: str, score: int) -> None:
        """Cache a risk score for a camera."""
        self.camera_scores[camera_name] = score
        self._timestamps[camera_name] = time.monotonic()

    def get_object_type_score(self, object_type: str) -> int:
        """Get default score for an object type."""
        return self.object_type_scores.get(object_type.lower(), 50)


# Default circuit breaker configurations per service
DEFAULT_CB_CONFIGS: dict[AIService, CircuitBreakerConfig] = {
    AIService.RTDETR: CircuitBreakerConfig(
        failure_threshold=3,
        recovery_timeout=60.0,
        half_open_max_calls=2,
        success_threshold=2,
    ),
    AIService.NEMOTRON: CircuitBreakerConfig(
        failure_threshold=5,
        recovery_timeout=90.0,
        half_open_max_calls=3,
        success_threshold=2,
    ),
    AIService.FLORENCE: CircuitBreakerConfig(
        failure_threshold=5,
        recovery_timeout=60.0,
        half_open_max_calls=3,
        success_threshold=2,
    ),
    AIService.CLIP: CircuitBreakerConfig(
        failure_threshold=5,
        recovery_timeout=60.0,
        half_open_max_calls=3,
        success_threshold=2,
    ),
}

# Critical services that affect degradation level more severely
CRITICAL_SERVICES = {AIService.RTDETR, AIService.NEMOTRON}


class AIFallbackService:
    """Manages AI service fallbacks and degradation status.

    This service tracks the health of all AI services and provides
    fallback values when services are unavailable.

    Usage:
        service = AIFallbackService()
        await service.start()

        # Check availability before calling
        if service.is_service_available(AIService.NEMOTRON):
            result = await analyzer.analyze(...)
        else:
            result = service.get_fallback_risk_analysis(...)
    """

    def __init__(
        self,
        detector_client: DetectorClient | None = None,
        nemotron_analyzer: NemotronAnalyzer | None = None,
        florence_client: FlorenceClient | None = None,
        clip_client: CLIPClient | None = None,
        health_check_interval: float = 15.0,
    ) -> None:
        """Initialize the AI fallback service.

        Args:
            detector_client: RT-DETRv2 client (optional, for health checks)
            nemotron_analyzer: Nemotron analyzer (optional, for health checks)
            florence_client: Florence-2 client (optional, for health checks)
            clip_client: CLIP client (optional, for health checks)
            health_check_interval: Interval between health checks in seconds
        """
        self._detector_client = detector_client
        self._nemotron_analyzer = nemotron_analyzer
        self._florence_client = florence_client
        self._clip_client = clip_client
        self._health_check_interval = health_check_interval

        # Initialize service states
        self._service_states: dict[AIService, ServiceState] = {
            service: ServiceState(service=service) for service in AIService
        }

        # Risk score cache for fallback
        self._risk_cache = RiskScoreCache()

        # Circuit breakers managed externally (by each client)
        # We track their states here for unified status reporting
        self._circuit_breakers: dict[AIService, CircuitBreaker | None] = dict.fromkeys(AIService)

        # Background task for health checks
        self._running = False
        self._health_check_task: asyncio.Task[None] | None = None
        self._lock = asyncio.Lock()

        # Status change callbacks for WebSocket broadcasting
        self._status_callbacks: list[Any] = []

        logger.info(
            "AIFallbackService initialized",
            extra={"health_check_interval": health_check_interval},
        )

    def register_circuit_breaker(
        self,
        service: AIService,
        circuit_breaker: CircuitBreaker,
    ) -> None:
        """Register a circuit breaker for a service.

        Args:
            service: AI service identifier
            circuit_breaker: Circuit breaker instance to register
        """
        self._circuit_breakers[service] = circuit_breaker
        logger.debug(f"Registered circuit breaker for {service.value}")

    def register_status_callback(self, callback: Any) -> None:
        """Register a callback for status changes.

        The callback will be called with the full status dict when any
        service status changes.

        Args:
            callback: Async callable that receives status dict
        """
        self._status_callbacks.append(callback)

    def unregister_status_callback(self, callback: Any) -> None:
        """Unregister a status callback.

        Args:
            callback: The callback to remove
        """
        if callback in self._status_callbacks:
            self._status_callbacks.remove(callback)

    async def start(self) -> None:
        """Start the health check background task."""
        if self._running:
            logger.warning("AIFallbackService already running")
            return

        self._running = True
        self._health_check_task = asyncio.create_task(self._health_check_loop())
        logger.info("AIFallbackService started")

    async def stop(self) -> None:
        """Stop the health check background task."""
        if not self._running:
            return

        self._running = False
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                # Task was intentionally cancelled via cancel().
                # This is normal cleanup behavior, not an error condition.
                # See: NEM-2540 for rationale
                pass
            self._health_check_task = None

        logger.info("AIFallbackService stopped")

    async def _health_check_loop(self) -> None:
        """Background loop for health checks."""
        while self._running:
            try:
                await self._check_all_services()
                await asyncio.sleep(self._health_check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check loop error: {e}", exc_info=True)
                await asyncio.sleep(self._health_check_interval)

    async def _check_all_services(self) -> None:
        """Check health of all AI services."""
        status_changed = False

        for service in AIService:
            old_status = self._service_states[service].status
            await self._check_service_health(service)
            new_status = self._service_states[service].status

            if old_status != new_status:
                status_changed = True
                logger.info(
                    f"AI service {service.value} status changed: {old_status.value} -> {new_status.value}"
                )

        if status_changed:
            await self._notify_status_change()

    async def _check_service_health(self, service: AIService) -> None:
        """Check health of a specific service.

        Args:
            service: Service to check
        """
        state = self._service_states[service]
        state.last_check = datetime.now(UTC)

        # Get circuit breaker state if registered
        cb = self._circuit_breakers.get(service)
        if cb is not None:
            state.circuit_state = cb.get_state()
            state.failure_count = cb.failure_count

            # Determine status from circuit state
            if state.circuit_state == CircuitState.OPEN:
                state.status = ServiceStatus.UNAVAILABLE
            elif state.circuit_state == CircuitState.HALF_OPEN:
                state.status = ServiceStatus.DEGRADED
            else:
                state.status = ServiceStatus.HEALTHY
            return

        # Fallback to health check if no circuit breaker registered
        try:
            healthy = await self._perform_health_check(service)
            if healthy:
                state.status = ServiceStatus.HEALTHY
                state.last_success = datetime.now(UTC)
                state.failure_count = 0
                state.error_message = None
            else:
                state.failure_count += 1
                if state.failure_count >= 3:
                    state.status = ServiceStatus.UNAVAILABLE
                else:
                    state.status = ServiceStatus.DEGRADED
        except Exception as e:
            state.failure_count += 1
            state.error_message = str(e)
            state.status = ServiceStatus.UNAVAILABLE

    async def _perform_health_check(self, service: AIService) -> bool:
        """Perform a health check for a service.

        Args:
            service: Service to check

        Returns:
            True if service is healthy
        """
        if service == AIService.RTDETR and self._detector_client:
            return await self._detector_client.health_check()
        elif service == AIService.NEMOTRON and self._nemotron_analyzer:
            return await self._nemotron_analyzer.health_check()
        elif service == AIService.FLORENCE and self._florence_client:
            return await self._florence_client.check_health()
        elif service == AIService.CLIP and self._clip_client:
            return await self._clip_client.check_health()

        # No client registered, assume healthy
        return True

    async def _notify_status_change(self) -> None:
        """Notify all registered callbacks of status change."""
        status = self.get_degradation_status()

        for callback in self._status_callbacks:
            try:
                await callback(status)
            except Exception as e:
                logger.error(f"Status callback error: {e}", exc_info=True)

    def is_service_available(self, service: AIService | str) -> bool:
        """Check if a service is available for use.

        Args:
            service: Service identifier (AIService enum or string)

        Returns:
            True if service is available (healthy or degraded)
        """
        if isinstance(service, str):
            service = AIService(service)

        state = self._service_states[service]
        return state.status != ServiceStatus.UNAVAILABLE

    def get_service_state(self, service: AIService | str) -> ServiceState:
        """Get the current state of a service.

        Args:
            service: Service identifier

        Returns:
            ServiceState for the service
        """
        if isinstance(service, str):
            service = AIService(service)
        return self._service_states[service]

    def get_degradation_level(self) -> DegradationLevel:
        """Get the current system degradation level.

        Returns:
            DegradationLevel based on service availability
        """
        critical_unavailable = 0
        non_critical_unavailable = 0

        for service, state in self._service_states.items():
            if state.status == ServiceStatus.UNAVAILABLE:
                if service in CRITICAL_SERVICES:
                    critical_unavailable += 1
                else:
                    non_critical_unavailable += 1

        # Determine level
        if critical_unavailable == len(CRITICAL_SERVICES):
            return DegradationLevel.OFFLINE
        elif critical_unavailable > 0:
            return DegradationLevel.MINIMAL
        elif non_critical_unavailable > 0:
            return DegradationLevel.DEGRADED
        else:
            return DegradationLevel.NORMAL

    def get_available_features(self) -> list[str]:
        """Get list of currently available features.

        Returns:
            List of feature names that are available
        """
        features = []

        # Detection features (requires RT-DETRv2)
        if self.is_service_available(AIService.RTDETR):
            features.extend(["object_detection", "detection_alerts"])

        # Risk analysis features (requires Nemotron)
        if self.is_service_available(AIService.NEMOTRON):
            features.extend(["risk_analysis", "llm_reasoning"])

        # Caption features (requires Florence-2)
        if self.is_service_available(AIService.FLORENCE):
            features.extend(["image_captioning", "ocr", "dense_captioning"])

        # Re-identification features (requires CLIP)
        if self.is_service_available(AIService.CLIP):
            features.extend(["entity_tracking", "re_identification", "anomaly_detection"])

        # Basic features always available
        features.extend(["event_history", "camera_feeds", "system_monitoring"])

        return features

    def get_degradation_status(self) -> dict[str, Any]:
        """Get comprehensive degradation status.

        Returns:
            Dictionary with all degradation information
        """
        return {
            "timestamp": datetime.now(UTC).isoformat(),
            "degradation_mode": self.get_degradation_level().value,
            "services": {
                service.value: state.to_dict() for service, state in self._service_states.items()
            },
            "available_features": self.get_available_features(),
        }

    # =========================================================================
    # Fallback Methods
    # =========================================================================

    def get_fallback_risk_analysis(
        self,
        camera_name: str | None = None,
        object_types: list[str] | None = None,
    ) -> FallbackRiskAnalysis:
        """Get fallback risk analysis when Nemotron is unavailable.

        Uses cached values or object-type based defaults.

        Args:
            camera_name: Camera name for cached lookup
            object_types: Detected object types for estimation

        Returns:
            FallbackRiskAnalysis with estimated risk score
        """
        # Try cached value first
        if camera_name:
            cached = self._risk_cache.get_cached_score(camera_name)
            if cached is not None:
                return FallbackRiskAnalysis(
                    risk_score=cached,
                    reasoning=(
                        f"Using cached risk score from camera '{camera_name}'. "
                        "Nemotron analyzer is currently unavailable."
                    ),
                    source="cache",
                )

        # Calculate from object types
        if object_types:
            scores = [self._risk_cache.get_object_type_score(obj) for obj in object_types]
            avg_score = int(sum(scores) / len(scores)) if scores else 50

            return FallbackRiskAnalysis(
                risk_score=avg_score,
                reasoning=(
                    f"Estimated risk score based on detected objects: {', '.join(object_types)}. "
                    "Nemotron analyzer is currently unavailable."
                ),
                source="object_type_estimate",
            )

        # Default fallback
        return FallbackRiskAnalysis(
            risk_score=50,
            reasoning=(
                "Using default medium risk score. "
                "Nemotron analyzer is currently unavailable for detailed analysis."
            ),
            source="default",
        )

    def cache_risk_score(self, camera_name: str, risk_score: int) -> None:
        """Cache a successful risk score for fallback use.

        Args:
            camera_name: Camera name
            risk_score: Risk score to cache (0-100)
        """
        self._risk_cache.set_cached_score(camera_name, risk_score)

    def get_fallback_caption(
        self,
        object_types: list[str] | None = None,
        camera_name: str | None = None,
    ) -> str:
        """Get fallback caption when Florence-2 is unavailable.

        Args:
            object_types: Detected object types
            camera_name: Camera name for context

        Returns:
            Simple caption based on detections
        """
        if not object_types:
            if camera_name:
                return f"Activity detected at {camera_name}"
            return "Activity detected"

        # Build caption from object types
        objects_str = ", ".join(object_types)
        if camera_name:
            return f"{objects_str.capitalize()} detected at {camera_name}"
        return f"{objects_str.capitalize()} detected"

    def get_fallback_embedding(self) -> list[float]:
        """Get fallback embedding when CLIP is unavailable.

        Returns a zero vector that will not match any existing embeddings.

        Returns:
            768-dimensional zero vector
        """
        return [0.0] * 768

    def should_skip_detection(self) -> bool:
        """Check if detection should be skipped due to RT-DETRv2 unavailability.

        Returns:
            True if detection should be skipped
        """
        return not self.is_service_available(AIService.RTDETR)

    def should_use_default_risk(self) -> bool:
        """Check if default risk score should be used.

        Returns:
            True if Nemotron is unavailable
        """
        return not self.is_service_available(AIService.NEMOTRON)

    def should_skip_captions(self) -> bool:
        """Check if caption generation should be skipped.

        Returns:
            True if Florence-2 is unavailable
        """
        return not self.is_service_available(AIService.FLORENCE)

    def should_skip_reid(self) -> bool:
        """Check if re-identification should be skipped.

        Returns:
            True if CLIP is unavailable
        """
        return not self.is_service_available(AIService.CLIP)


# Global instance
_ai_fallback_service: AIFallbackService | None = None


def get_ai_fallback_service() -> AIFallbackService:
    """Get or create the global AI fallback service.

    Returns:
        AIFallbackService instance
    """
    global _ai_fallback_service  # noqa: PLW0603
    if _ai_fallback_service is None:
        _ai_fallback_service = AIFallbackService()
    return _ai_fallback_service


def reset_ai_fallback_service() -> None:
    """Reset the global AI fallback service (for testing)."""
    global _ai_fallback_service  # noqa: PLW0603
    _ai_fallback_service = None
