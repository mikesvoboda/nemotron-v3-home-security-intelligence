"""Circuit breaker module - DEPRECATED, use backend.services.circuit_breaker instead.

This module re-exports from backend.services.circuit_breaker for backward compatibility.
All new code should import directly from backend.services.circuit_breaker.

The canonical implementation is in backend.services.circuit_breaker which provides:
- CircuitBreaker: Full-featured circuit breaker with Prometheus metrics
- CircuitBreakerConfig: Configuration dataclass
- CircuitBreakerError: Exception for open circuit
- CircuitBreakerOpenError: Alias for CircuitBreakerError
- CircuitOpenError: Exception raised by protect() with recovery_time_remaining
- CircuitBreakerRegistry: Registry for managing multiple circuit breakers
- CircuitState: Enum of circuit states (CLOSED, OPEN, HALF_OPEN)

Prometheus metrics are exported:
- CIRCUIT_BREAKER_STATE: Current state gauge (0=closed, 1=open, 2=half_open)
- CIRCUIT_BREAKER_FAILURES_TOTAL: Counter of failures
- CIRCUIT_BREAKER_STATE_CHANGES_TOTAL: Counter of state transitions

Usage:
    # Preferred - import from services
    from backend.services.circuit_breaker import CircuitBreaker, CircuitBreakerConfig

    # Legacy - still works via this module
    from backend.core.circuit_breaker import CircuitBreaker, CircuitState
"""

from __future__ import annotations

# Re-export everything from the canonical implementation
from backend.services.circuit_breaker import (
    CIRCUIT_BREAKER_CALLS_TOTAL,
    CIRCUIT_BREAKER_FAILURES_TOTAL,
    CIRCUIT_BREAKER_REJECTED_TOTAL,
    CIRCUIT_BREAKER_STATE,
    CIRCUIT_BREAKER_STATE_CHANGES_TOTAL,
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerError,
    CircuitBreakerMetrics,
    CircuitBreakerOpenError,
    CircuitBreakerRegistry,
    CircuitOpenError,
    CircuitState,
    get_circuit_breaker,
    reset_circuit_breaker_registry,
)

__all__ = [  # noqa: RUF022  # Intentionally organized by category
    # Classes
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitBreakerError",
    "CircuitBreakerMetrics",
    "CircuitBreakerOpenError",
    "CircuitBreakerRegistry",
    "CircuitOpenError",
    "CircuitState",
    # Prometheus metrics
    "CIRCUIT_BREAKER_CALLS_TOTAL",
    "CIRCUIT_BREAKER_FAILURES_TOTAL",
    "CIRCUIT_BREAKER_REJECTED_TOTAL",
    "CIRCUIT_BREAKER_STATE",
    "CIRCUIT_BREAKER_STATE_CHANGES_TOTAL",
    # Functions
    "get_circuit_breaker",
    "reset_circuit_breaker_registry",
]
