"""Health event emitter for WebSocket system health notifications.

This module provides a service that tracks system health state and emits
WebSocket events when health status transitions occur. It prevents spamming
clients with events on every health check by only emitting when actual
status changes happen.

Health Components Monitored:
- database: PostgreSQL connection pool and query latency
- redis: Redis connection status and memory usage
- ai_service: llama.cpp server (Nemotron) and RT-DETRv2 health
- gpu: CUDA availability and memory usage
- storage: Disk space for /export/foscam/

Event Types Emitted:
- system.health_changed: When overall or component health status changes
- system.error: When a system-level error occurs

Usage:
    from backend.services.health_event_emitter import (
        get_health_event_emitter,
        emit_system_error,
    )

    # Get the singleton emitter
    emitter = get_health_event_emitter()

    # Check and emit health changes
    await emitter.check_and_emit(
        component="database",
        new_status="unhealthy",
        details={"error": "Connection refused"},
    )

    # Emit a system error
    await emit_system_error(
        error_code="AI_SERVICE_CRASH",
        message="Nemotron service crashed unexpectedly",
        severity="high",
        details={"exit_code": 137},
    )
"""

from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any, ClassVar

from backend.core.logging import get_logger
from backend.core.websocket.event_schemas import SystemHealth
from backend.core.websocket.event_types import WebSocketEventType

if TYPE_CHECKING:
    from backend.services.websocket_emitter import WebSocketEmitterService

logger = get_logger(__name__)


class HealthStatus(StrEnum):
    """Health status values for components."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class ErrorSeverity(StrEnum):
    """Severity levels for system errors."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(slots=True)
class ComponentHealthState:
    """Tracks health state for a single component.

    Attributes:
        status: Current health status
        last_changed: Timestamp of last status change
        details: Additional details about the component state
    """

    status: HealthStatus = HealthStatus.UNKNOWN
    last_changed: datetime = field(default_factory=lambda: datetime.now(UTC))
    details: dict[str, Any] = field(default_factory=dict)


class HealthEventEmitter:
    """Service for tracking health state and emitting WebSocket events.

    This service maintains the previous health state for each system component
    and emits WebSocket events only when the status actually changes. This
    prevents flooding clients with duplicate notifications on each health check.

    The service supports both individual component health changes and overall
    system health aggregation.

    Thread-safe singleton pattern ensures consistent state across the application.

    Attributes:
        _component_states: Dictionary mapping component names to their health state
        _overall_status: Current overall system health status
        _emitter: WebSocket emitter service for broadcasting events
    """

    # Health status priority for overall system calculation
    # Lower number = higher priority (worse status takes precedence)
    _STATUS_PRIORITY: ClassVar[dict[HealthStatus, int]] = {
        HealthStatus.UNHEALTHY: 0,
        HealthStatus.DEGRADED: 1,
        HealthStatus.UNKNOWN: 2,
        HealthStatus.HEALTHY: 3,
    }

    # Components that are critical for overall system health
    CRITICAL_COMPONENTS: ClassVar[set[str]] = {"database", "redis"}

    def __init__(self) -> None:
        """Initialize the health event emitter."""
        self._component_states: dict[str, ComponentHealthState] = {}
        self._overall_status: HealthStatus = HealthStatus.UNKNOWN
        self._emitter: WebSocketEmitterService | None = None
        self._lock = asyncio.Lock()

        logger.info("HealthEventEmitter initialized")

    def set_emitter(self, emitter: WebSocketEmitterService) -> None:
        """Set the WebSocket emitter service.

        Args:
            emitter: WebSocket emitter service instance
        """
        self._emitter = emitter
        logger.debug("WebSocket emitter set for HealthEventEmitter")

    def get_component_status(self, component: str) -> HealthStatus:
        """Get the current status of a component.

        Args:
            component: Component name

        Returns:
            Current health status, or UNKNOWN if not tracked
        """
        state = self._component_states.get(component)
        return state.status if state else HealthStatus.UNKNOWN

    def get_all_component_statuses(self) -> dict[str, str]:
        """Get status of all tracked components.

        Returns:
            Dictionary mapping component names to status strings
        """
        return {
            component: state.status.value for component, state in self._component_states.items()
        }

    def get_overall_status(self) -> HealthStatus:
        """Get the current overall system health status.

        Returns:
            Overall system health status
        """
        return self._overall_status

    def _calculate_overall_status(self) -> HealthStatus:
        """Calculate overall system health from component states.

        The overall status is determined by:
        1. If any critical component (database, redis) is unhealthy -> unhealthy
        2. Otherwise, take the worst status across all components

        Returns:
            Calculated overall system health status
        """
        if not self._component_states:
            return HealthStatus.UNKNOWN

        # Check critical components first
        for component in self.CRITICAL_COMPONENTS:
            state = self._component_states.get(component)
            if state and state.status == HealthStatus.UNHEALTHY:
                return HealthStatus.UNHEALTHY

        # Find worst status across all components
        worst_priority = max(self._STATUS_PRIORITY.values())
        for state in self._component_states.values():
            priority = self._STATUS_PRIORITY.get(state.status, worst_priority)
            worst_priority = min(worst_priority, priority)

        # Convert priority back to status
        for status, priority in self._STATUS_PRIORITY.items():
            if priority == worst_priority:
                return status

        return HealthStatus.UNKNOWN

    async def check_and_emit(
        self,
        component: str,
        new_status: str | HealthStatus,
        details: dict[str, Any] | None = None,
    ) -> bool:
        """Check if component status changed and emit event if so.

        This is the primary method for updating component health status.
        It compares the new status with the previous status and emits a
        WebSocket event only if there's an actual change.

        Args:
            component: Component name (database, redis, ai_service, gpu, storage)
            new_status: New health status (healthy, degraded, unhealthy)
            details: Optional details about the component state

        Returns:
            True if status changed and event was emitted, False otherwise
        """
        # Normalize status to enum
        if isinstance(new_status, str):
            try:
                new_status = HealthStatus(new_status.lower())
            except ValueError:
                logger.warning(f"Invalid health status: {new_status}, defaulting to unknown")
                new_status = HealthStatus.UNKNOWN

        async with self._lock:
            previous_state = self._component_states.get(component)
            previous_status = previous_state.status if previous_state else HealthStatus.UNKNOWN

            # Check if status actually changed
            if previous_status == new_status:
                # Update details even if status unchanged
                if previous_state and details:
                    previous_state.details = details
                return False

            # Status changed - update state
            now = datetime.now(UTC)
            self._component_states[component] = ComponentHealthState(
                status=new_status,
                last_changed=now,
                details=details or {},
            )

            # Calculate new overall status
            previous_overall = self._overall_status
            self._overall_status = self._calculate_overall_status()

            # Emit health changed event
            await self._emit_health_changed(
                component=component,
                previous_status=previous_status,
                new_status=new_status,
                previous_overall=previous_overall,
                new_overall=self._overall_status,
            )

            logger.info(
                f"Health status changed: {component} {previous_status.value} -> {new_status.value}",
                extra={
                    "component": component,
                    "previous_status": previous_status.value,
                    "new_status": new_status.value,
                    "overall_status": self._overall_status.value,
                },
            )

            return True

    async def update_all_components(
        self,
        statuses: dict[str, str | HealthStatus],
        details: dict[str, dict[str, Any]] | None = None,
    ) -> list[str]:
        """Update multiple components and emit events for any changes.

        Efficiently updates multiple components in a single call, emitting
        events only for components whose status actually changed.

        Args:
            statuses: Dictionary mapping component names to their new status
            details: Optional dictionary mapping component names to details

        Returns:
            List of component names that had status changes
        """
        changed_components: list[str] = []
        details = details or {}

        for component, status in statuses.items():
            component_details = details.get(component)
            if await self.check_and_emit(component, status, component_details):
                changed_components.append(component)

        return changed_components

    async def _emit_health_changed(
        self,
        component: str,
        previous_status: HealthStatus,
        new_status: HealthStatus,
        previous_overall: HealthStatus,
        new_overall: HealthStatus,
    ) -> None:
        """Emit a system.health_changed WebSocket event.

        Args:
            component: Component that changed
            previous_status: Previous component status
            new_status: New component status
            previous_overall: Previous overall system status
            new_overall: New overall system status
        """
        if self._emitter is None:
            logger.debug("No emitter configured, skipping health changed event")
            return

        # Build component status map
        components = self.get_all_component_statuses()

        # Map our HealthStatus to the schema's SystemHealth
        health_map = {
            HealthStatus.HEALTHY: SystemHealth.HEALTHY,
            HealthStatus.DEGRADED: SystemHealth.DEGRADED,
            HealthStatus.UNHEALTHY: SystemHealth.UNHEALTHY,
            HealthStatus.UNKNOWN: SystemHealth.UNHEALTHY,  # Unknown treated as unhealthy
        }

        payload = {
            "health": health_map[new_overall].value,
            "previous_health": health_map[previous_overall].value,
            "components": components,
            "changed_component": component,
            "component_previous_status": previous_status.value,
            "component_new_status": new_status.value,
            "timestamp": datetime.now(UTC).isoformat(),
        }

        try:
            await self._emitter.emit(
                WebSocketEventType.SYSTEM_HEALTH_CHANGED,
                payload,
            )
            logger.debug(
                f"Emitted system.health_changed event: {component} -> {new_status.value}",
                extra={"component": component, "new_status": new_status.value},
            )
        except Exception as e:
            logger.error(f"Failed to emit health changed event: {e}", exc_info=True)

    async def emit_system_error(
        self,
        error_code: str,
        message: str,
        severity: str | ErrorSeverity = ErrorSeverity.MEDIUM,
        details: dict[str, Any] | None = None,
        recoverable: bool = True,
    ) -> bool:
        """Emit a system.error WebSocket event.

        Use this method to notify clients of system-level errors such as
        service crashes, configuration issues, or resource exhaustion.

        Args:
            error_code: Short error code/type (e.g., AI_SERVICE_CRASH)
            message: Human-readable error message
            severity: Error severity (low, medium, high, critical)
            details: Optional additional error details
            recoverable: Whether the error is recoverable

        Returns:
            True if event was emitted successfully, False otherwise
        """
        if self._emitter is None:
            logger.debug("No emitter configured, skipping system error event")
            return False

        # Normalize severity
        if isinstance(severity, str):
            try:
                severity = ErrorSeverity(severity.lower())
            except ValueError:
                severity = ErrorSeverity.MEDIUM

        payload = {
            "error": error_code,
            "message": message,
            "timestamp": datetime.now(UTC).isoformat(),
            "details": details,
            "recoverable": recoverable,
        }

        try:
            await self._emitter.emit(
                WebSocketEventType.SYSTEM_ERROR,
                payload,
            )
            logger.info(
                f"Emitted system.error event: {error_code}",
                extra={
                    "error_code": error_code,
                    "severity": severity.value,
                    "recoverable": recoverable,
                },
            )
            return True
        except Exception as e:
            logger.error(f"Failed to emit system error event: {e}", exc_info=True)
            return False

    def reset(self) -> None:
        """Reset all tracked state.

        Warning: Only use this in tests or during system restart.
        """
        self._component_states.clear()
        self._overall_status = HealthStatus.UNKNOWN
        logger.info("HealthEventEmitter state reset")


# =============================================================================
# Global Singleton Instance (Legacy + DI Support - NEM-2611)
# =============================================================================

_health_event_emitter: HealthEventEmitter | None = None
_emitter_lock = threading.Lock()


def get_health_event_emitter() -> HealthEventEmitter:
    """Get or create the health event emitter instance.

    This function supports both dependency injection and legacy global patterns:
    1. First, tries to get the emitter from the DI container
    2. Falls back to the legacy global singleton pattern

    Thread-safe singleton pattern ensures a single emitter instance
    across the application.

    Returns:
        HealthEventEmitter singleton instance
    """
    global _health_event_emitter  # noqa: PLW0603

    # Try to get from DI container first (NEM-2611)
    try:
        from backend.core.container import ServiceNotFoundError, get_container

        container = get_container()
        registration = container._registrations.get("health_event_emitter")
        if registration and registration.instance is not None:
            # Cast to proper type since container stores Any
            emitter: HealthEventEmitter = registration.instance
            return emitter
        # If registered but not yet instantiated, get it from container
        if "health_event_emitter" in container._registrations:
            result = container.get("health_event_emitter")
            # Cast to proper type since container returns Any
            return result  # type: ignore[no-any-return]
    except (ServiceNotFoundError, ImportError, AttributeError):
        # Container not available or service not registered, use legacy pattern
        pass

    # Fall back to legacy global singleton
    if _health_event_emitter is None:
        with _emitter_lock:
            if _health_event_emitter is None:
                _health_event_emitter = HealthEventEmitter()
                logger.info("Global HealthEventEmitter initialized (legacy pattern)")

    return _health_event_emitter


async def emit_system_error(
    error_code: str,
    message: str,
    severity: str | ErrorSeverity = ErrorSeverity.MEDIUM,
    details: dict[str, Any] | None = None,
    recoverable: bool = True,
) -> bool:
    """Convenience function to emit a system error event.

    This is a module-level function for easy access to error emission
    without needing to get the emitter instance directly.

    Args:
        error_code: Short error code/type (e.g., AI_SERVICE_CRASH)
        message: Human-readable error message
        severity: Error severity (low, medium, high, critical)
        details: Optional additional error details
        recoverable: Whether the error is recoverable

    Returns:
        True if event was emitted successfully, False otherwise
    """
    emitter = get_health_event_emitter()
    return await emitter.emit_system_error(
        error_code=error_code,
        message=message,
        severity=severity,
        details=details,
        recoverable=recoverable,
    )


def reset_health_event_emitter() -> None:
    """Reset the health event emitter state (both DI and legacy).

    This function resets both the DI container instance and the legacy
    global singleton to ensure clean state for testing.

    Warning: Only use this in tests or during system restart.
    """
    global _health_event_emitter  # noqa: PLW0603

    # Reset DI container instance if available (NEM-2611)
    try:
        from backend.core.container import get_container

        container = get_container()
        registration = container._registrations.get("health_event_emitter")
        if registration and registration.instance is not None:
            registration.instance.reset()
            registration.instance = None
    except (ImportError, AttributeError):
        pass

    # Reset legacy global singleton
    with _emitter_lock:
        if _health_event_emitter is not None:
            _health_event_emitter.reset()
        _health_event_emitter = None
